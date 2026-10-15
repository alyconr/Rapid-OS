"""Process ancestry, used by `rapid approve` to refuse running under an agent harness.

Standard library only:
- Linux: /proc/<pid>/stat and /proc/<pid>/cmdline.
- macOS and other Unix: `ps -o ppid=,comm=,args= -p <pid>` (two calls, so a `comm` with spaces
  cannot be confused with the arguments).
- Windows: CreateToolhelp32Snapshot through ctypes (names only; the snapshot has no command line).

If the ancestry cannot be read, the result carries the reason and the caller must NOT reject on
that basis (`rapid doctor` reports it).

Harnesses recognised (only what is confirmed in the official documentation or in a real install):
- Claude Code: the `claude` / `claude.exe` binary. https://code.claude.com/docs/en/setup documents
  the native installer (`~/.local/bin/claude` -> `~/.local/share/claude/versions/<version>`, so on
  macOS and Linux the process may be named after the version while argv[0] is `claude`), the npm
  package `@anthropic-ai/claude-code` and its per-platform binary packages. On Windows the real
  process observed under the VS Code extension is `.../native-binary/claude.exe`.
Codex and Cursor are deliberately not listed: their process names were not confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable

MAX_DEPTH = 32

# argv[0] basename / process name of the harness binary.
_AGENT_NAMES = {"claude": "claude"}
# Documented install locations, searched in the first two arguments (argv[0] and argv[1]).
_AGENT_PATH_MARKERS = (
    ("@anthropic-ai/claude-code", "claude"),
    ("/.local/share/claude/versions/", "claude"),
)


@dataclass(frozen=True)
class Ancestor:
    pid: int
    name: str
    args: tuple[str, ...] = ()


@dataclass(frozen=True)
class AncestryResult:
    ancestors: tuple[Ancestor, ...]
    error: str | None = None  # why the chain could not be (fully) read


@dataclass(frozen=True)
class AgentAncestor:
    harness: str
    ancestor: Ancestor


def _base(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def match_agent(ancestor: Ancestor) -> str | None:
    """Return the harness id when `ancestor` looks like an agent harness process."""
    if _base(ancestor.name) in _AGENT_NAMES:
        return _AGENT_NAMES[_base(ancestor.name)]
    if ancestor.args and _base(ancestor.args[0]) in _AGENT_NAMES:
        return _AGENT_NAMES[_base(ancestor.args[0])]
    for token in ancestor.args[:2]:
        normalized = token.replace("\\", "/")
        for marker, harness in _AGENT_PATH_MARKERS:
            if marker in normalized:
                return harness
    return None


def find_agent_ancestor(result: AncestryResult) -> AgentAncestor | None:
    for ancestor in result.ancestors:
        harness = match_agent(ancestor)
        if harness:
            return AgentAncestor(harness, ancestor)
    return None


# ------------------------------------------------------------------------- readers
# A reader returns (ppid, name, args) for a pid, or raises OSError/ValueError.

Reader = Callable[[int], "tuple[int, str, tuple[str, ...]]"]


def _linux_reader(pid: int) -> tuple[int, str, tuple[str, ...]]:
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    # "pid (comm) state ppid ...": comm may contain spaces and parentheses.
    left, right = stat.index("("), stat.rindex(")")
    name = stat[left + 1 : right]
    ppid = int(stat[right + 2 :].split()[1])
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
        args = tuple(part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part)
    except OSError:
        args = ()
    return ppid, name, args


def _ps_reader(pid: int) -> tuple[int, str, tuple[str, ...]]:
    def ps(*fields: str) -> str:
        proc = subprocess.run(
            ["ps", *fields, "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            raise OSError(f"ps could not describe pid {pid}")
        return proc.stdout.strip("\n")

    head = ps("-o", "ppid=,comm=").strip()
    ppid_text, _, name = head.partition(" ")
    args = ps("-o", "args=").strip()
    return int(ppid_text), name.strip(), tuple(args.split())


def _windows_snapshot() -> dict[int, tuple[int, str]]:
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if snapshot in (None, wintypes.HANDLE(-1).value):
        raise OSError("CreateToolhelp32Snapshot failed")
    processes: dict[int, tuple[int, str]] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            processes[int(entry.th32ProcessID)] = (int(entry.th32ParentProcessID), entry.szExeFile)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return processes


def _windows_reader() -> Reader:
    processes = _windows_snapshot()

    def read(pid: int) -> tuple[int, str, tuple[str, ...]]:
        if pid not in processes:
            raise OSError(f"pid {pid} is not in the process snapshot")
        ppid, name = processes[pid]
        return ppid, name, ()

    return read


def default_reader() -> Reader:
    if sys.platform.startswith("win"):
        return _windows_reader()
    if sys.platform.startswith("linux"):
        return _linux_reader
    return _ps_reader


def read_ancestry(pid: int | None = None, reader: Reader | None = None) -> AncestryResult:
    """Parents of `pid` (default: this process), nearest first. Never raises."""
    try:
        read = reader or default_reader()
    except Exception as exc:  # noqa: BLE001 - e.g. ctypes unavailable
        return AncestryResult((), f"process ancestry is not available on this platform: {exc}")

    current = os.getpid() if pid is None else pid
    ancestors: list[Ancestor] = []
    seen = {current}
    try:
        parent, _, _ = read(current)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError) as exc:
        return AncestryResult((), f"cannot read the parent of pid {current}: {exc}")

    while parent > 0 and parent not in seen and len(ancestors) < MAX_DEPTH:
        seen.add(parent)
        try:
            grandparent, name, args = read(parent)
        except (OSError, ValueError, IndexError, subprocess.SubprocessError) as exc:
            ancestors_error = f"cannot read ancestor pid {parent}: {exc}"
            return AncestryResult(tuple(ancestors), ancestors_error if not ancestors else None)
        ancestors.append(Ancestor(parent, name, args))
        parent = grandparent
    return AncestryResult(tuple(ancestors))

"""Pure decision logic for the Claude Code hooks (`rapid hook stop|pre-tool`).

No I/O here: a parsed payload (plus the NextAction and guard state, resolved by the caller)
goes in, an optional decision comes out. Project resolution, the loop-guard file and the log
live in `rapid_os.orchestration.hook_runtime`.

Claude Code hook contract, verified against the official documentation:
- Hooks reference (stdin schema, Stop and PreToolUse output, exit codes, environment):
  https://code.claude.com/docs/en/hooks
  * Every hook receives JSON on stdin with `session_id`, `transcript_path`, `cwd`,
    `permission_mode` and `hook_event_name`.
  * Stop adds `stop_hook_active`, true "when Claude Code is already continuing as a result of
    a stop hook"; Stop blocks with `{"decision": "block", "reason": "..."}` (or exit code 2 with
    the reason on stderr). Claude Code itself caps consecutive stop-hook continuations at 8.
  * PreToolUse adds `tool_name`, `tool_input` and `tool_use_id`; it denies with
    `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
    "permissionDecisionReason": "..."}}` (or exit code 2). Exit 0 without output means "no
    decision".
  * Command hooks receive `CLAUDE_PROJECT_DIR` (the directory where the session started; it does
    not change when Claude enters a worktree).
- Tool names and input fields: https://code.claude.com/docs/en/tools-reference
  * Built-in file tools: `Write` and `Edit` (`file_path`), `NotebookEdit`; shell tools: `Bash`
    and, on Windows, `PowerShell` (`command`). The docs do not list `MultiEdit` and do not
    document NotebookEdit's input fields, so any of `file_path`, `notebook_path` and `path` is
    inspected.

The shell analysis is best-effort: it recognises the common ways of invoking a reserved command
(chains, subshells, wrappers, `python -m rapid_os`) but cannot stop an agent determined to hide
a command (for example by building the string at runtime).
"""

from __future__ import annotations

from dataclasses import dataclass
import posixpath
import re
import shlex
from typing import Mapping, Sequence

from rapid_os.orchestration.actions import ActionKind, NextAction

DEFAULT_MAX_STOP_BLOCKS = 3

STOP_BLOCKING_KINDS = frozenset(
    {
        ActionKind.RUN_BASELINE,
        ActionKind.ACTIVATE,
        ActionKind.IMPLEMENT_TASK,
        ActionKind.VERIFY,
        ActionKind.FINISH,
    }
)

SHELL_TOOLS = frozenset({"Bash", "PowerShell"})
FILE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
PATH_KEYS = ("file_path", "notebook_path", "path")


class HookPayloadError(ValueError):
    """The hook stdin is not the JSON object Claude Code documents."""


@dataclass(frozen=True)
class HookPayload:
    event: str
    session_id: str
    cwd: str
    tool_name: str = ""
    tool_input: Mapping[str, object] | None = None
    stop_hook_active: bool = False


def parse_payload(raw: object) -> HookPayload:
    if not isinstance(raw, dict):
        raise HookPayloadError("hook payload must be a JSON object")
    tool_input = raw.get("tool_input")
    return HookPayload(
        event=str(raw.get("hook_event_name") or ""),
        session_id=str(raw.get("session_id") or ""),
        cwd=str(raw.get("cwd") or ""),
        tool_name=str(raw.get("tool_name") or ""),
        tool_input=tool_input if isinstance(tool_input, dict) else {},
        stop_hook_active=raw.get("stop_hook_active") is True,
    )


# ----------------------------------------------------------------------------- Stop


@dataclass(frozen=True)
class StopGuard:
    """Consecutive blocks issued for the same action within one session."""

    key: str
    count: int


def action_key(action: NextAction) -> str:
    return f"{action.kind.value}|{action.task_id or ''}|{','.join(action.gate_ids)}"


def _format_command(argv: Sequence[str]) -> str:
    return shlex.join(list(argv))


def stop_reason(action: NextAction) -> str:
    parts = []
    instructions = action.instructions.strip()
    if instructions:
        parts.append(instructions if instructions.endswith((".", "!", "?")) else instructions + ".")
    if action.command:
        parts.append(f"Run: `{_format_command(action.command)}`.")
        if action.after:
            parts.append(f"Then, once the work is done: `{_format_command(action.after)}`.")
    elif action.after:
        parts.append(
            f"Do the work for {action.task_id or 'the task'}, then run: `{_format_command(action.after)}`."
        )
    parts.append("Run `rapid next --json` for the full state; do not stop until the run reaches await_human_approval.")
    return " ".join(parts)


def decide_stop(
    payload: HookPayload,
    action: NextAction | None,
    guard: StopGuard | None,
    max_blocks: int = DEFAULT_MAX_STOP_BLOCKS,
) -> tuple[dict | None, StopGuard | None]:
    """Return (output, new_guard). `output` is None when the agent may stop.

    Blocks only while the run still has work the agent can do (baseline, activation, task,
    verification, finish). It never blocks on author_spec, await_human_approval, blocked (which
    includes the `rapid abort` proposed after a rejected review) or done.
    """
    if action is None or action.kind not in STOP_BLOCKING_KINDS:
        return None, None

    key = action_key(action)
    # A stop that does not come from a previous block is a fresh attempt: the count restarts.
    previous = guard.count if (guard and guard.key == key and payload.stop_hook_active) else 0
    if previous >= max_blocks:
        return None, StopGuard(key, previous)

    output = {"decision": "block", "reason": stop_reason(action)}
    return output, StopGuard(key, previous + 1)


# ------------------------------------------------------------------------- PreToolUse

_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PYTHON = re.compile(r"^(python|python\d+(\.\d+)*|py|pypy\d*)$")
_RAPID_PROGRAMS = frozenset({"rapid", "rapid.py"})
_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "fish", "powershell", "pwsh", "cmd"})
_SHELL_COMMAND_FLAGS = frozenset({"-c", "-command", "-commandwithargs", "/c", "-lc", "-ic"})
_KEYWORDS = frozenset({"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "for", "!", "{", "}", "time"})
_WRAPPERS = {
    # wrapper -> options that consume the following token
    "env": {"-u", "-C", "-S", "--unset", "--chdir"},
    "command": set(),
    "builtin": set(),
    "exec": {"-a"},
    "nohup": set(),
    "nice": {"-n"},
    "ionice": {"-c", "-n"},
    "stdbuf": {"-i", "-o", "-e"},
    "setsid": set(),
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-U"},
    "doas": {"-u", "-C"},
    "timeout": {"-s", "-k"},
    "xargs": {"-I", "-n", "-P", "-d", "-L", "-s", "-E", "-a"},
    "watch": {"-n", "-d"},
}
_RUNNERS = frozenset({"uv", "poetry", "pipenv", "pipx"})
_WRITERS_ANY = frozenset(
    {
        "tee", "mv", "rm", "rmdir", "touch", "truncate", "ln", "unlink", "shred", "install",
        # PowerShell cmdlets and aliases
        "set-content", "add-content", "out-file", "remove-item", "new-item", "copy-item",
        "move-item", "clear-content", "rename-item", "ri", "rni", "mi", "ni", "sc", "ac", "del", "erase",
    }
)
_WRITERS_LAST = frozenset({"cp", "copy"})

_RESERVED = {
    ("approve",): "approve",
    ("abort",): "abort",
    ("run", "gate"): "run gate",
    ("run", "status"): "run status",
    ("evidence", "add"): "evidence add",
    ("spec", "status"): "spec status",
}

_PYTHON_CODE_HINT = re.compile(
    r"\b(approve|abort)\b|run['\", ]+(gate|status)|evidence['\", ]+add|spec['\", ]+status"
)


def _base(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for ext in (".exe", ".cmd", ".bat", ".ps1"):
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


def _strip_heredocs(command: str) -> str:
    lines = command.split("\n")
    out: list[str] = []
    delimiter: str | None = None
    for line in lines:
        if delimiter is not None:
            if line.strip() == delimiter:
                delimiter = None
            continue
        out.append(line)
        match = re.search(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", line)
        if match:
            delimiter = match.group(2)
    return "\n".join(out)


def _extract_substitutions(command: str) -> tuple[str, list[str]]:
    """Pull out $(...), <(...), >(...) and `...` bodies; return the outer text and the bodies."""
    inner: list[str] = []
    out: list[str] = []
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if ch in "$<>" and i + 1 < n and command[i + 1] == "(":
            depth = 1
            j = i + 2
            while j < n and depth:
                if command[j] == "(":
                    depth += 1
                elif command[j] == ")":
                    depth -= 1
                j += 1
            inner.append(command[i + 2 : j - 1 if depth == 0 else j])
            out.append(" SUBST ")
            i = j
            continue
        if ch == "`":
            j = command.find("`", i + 1)
            if j == -1:
                j = n
            inner.append(command[i + 1 : j])
            out.append(" SUBST ")
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out), inner


def _tokenize(text: str) -> list[list[str]]:
    """Split into simple commands; each is a token list with redirections as separate tokens."""
    commands: list[list[str]] = []
    tokens: list[str] = []
    buf: list[str] = []
    in_token = False
    quote: str | None = None
    i = 0
    n = len(text)

    def flush_token() -> None:
        nonlocal in_token
        if in_token:
            tokens.append("".join(buf))
            buf.clear()
            in_token = False

    def flush_command() -> None:
        flush_token()
        if tokens:
            commands.append(list(tokens))
            tokens.clear()

    while i < n:
        ch = text[i]
        if quote:
            if ch == quote:
                quote = None
            elif ch == "\\" and quote == '"' and i + 1 < n and text[i + 1] in '"\\$`':
                buf.append(text[i + 1])
                i += 1
            else:
                buf.append(ch)
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            in_token = True
            i += 1
            continue
        if ch == "\\" and i + 1 < n and text[i + 1] in " \t\"'\\$`;&|<>()":
            buf.append(text[i + 1])
            in_token = True
            i += 2
            continue
        if ch in " \t\r":
            flush_token()
            i += 1
            continue
        if ch in "\n;()":
            flush_command()
            i += 1
            continue
        if ch == "|":
            flush_command()
            i += 2 if text[i : i + 2] == "||" else 1
            continue
        if ch == "&":
            if text[i : i + 2] == "&>":
                flush_token()
                op = "&>>" if text[i : i + 3] == "&>>" else "&>"
                tokens.append(op)
                i += len(op)
                continue
            flush_command()
            i += 2 if text[i : i + 2] == "&&" else 1
            continue
        if ch in "<>":
            fd_only = in_token and "".join(buf).isdigit()
            if fd_only:
                buf.clear()
                in_token = False
            else:
                flush_token()
            j = i
            while j < n and text[j] in "<>|&" and j - i < 3:
                j += 1
            tokens.append(text[i:j])
            i = j
            continue
        buf.append(ch)
        in_token = True
        i += 1
    flush_command()
    return commands


def _split_redirections(tokens: list[str]) -> tuple[list[str], list[str]]:
    words: list[str] = []
    targets: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t and t[0] in "<>&" and set(t) <= set("<>|&"):
            if ">" in t and i + 1 < len(tokens):
                targets.append(tokens[i + 1])
            i += 2
            continue
        words.append(t)
        i += 1
    return words, targets


def _skip_wrappers(words: list[str]) -> list[str]:
    i = 0
    while i < len(words):
        word = words[i]
        base = _base(word)
        if _ENV_ASSIGN.match(word) or base in _KEYWORDS:
            i += 1
            continue
        if base in _WRAPPERS:
            valued = _WRAPPERS[base]
            i += 1
            while i < len(words):
                tok = words[i]
                if tok in valued:
                    i += 2
                elif tok.startswith("-") or _ENV_ASSIGN.match(tok):
                    i += 1
                elif base == "timeout" and re.match(r"^[0-9.]+[smhd]?$", tok):
                    i += 1
                else:
                    break
            continue
        if base in _RUNNERS and i + 1 < len(words) and words[i + 1] in ("run", "tool"):
            i += 2
            if i < len(words) and words[i - 1] == "tool" and words[i] == "run":
                i += 1
            continue
        break
    return words[i:]


def _positionals(args: Sequence[str]) -> list[str]:
    return [a for a in args if not a.startswith("-")]


@dataclass(frozen=True)
class ReservedUse:
    command: str  # approve | abort | run gate | ...
    gate: str | None = None


def _reserved_in_rapid_args(args: Sequence[str]) -> ReservedUse | None:
    positional = _positionals(args)
    for pattern, name in _RESERVED.items():
        if tuple(p.lower() for p in positional[: len(pattern)]) == pattern:
            gate = None
            if name == "approve":
                gate = next((p for p in positional[1:] if p.startswith("gate.")), None)
            return ReservedUse(name, gate)
    return None


def _python_rapid_args(args: Sequence[str]) -> list[str] | None:
    """Arguments passed to rapid when python is running rapid_os or rapid.py, else None."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-m" and i + 1 < len(args):
            module = args[i + 1]
            if module == "rapid_os" or module.startswith("rapid_os."):
                return list(args[i + 2 :])
            return None
        if a in ("-W", "-X", "-c"):
            if a == "-c" and i + 1 < len(args):
                return None
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return list(args[i + 1 :]) if _base(a) in _RAPID_PROGRAMS else None
    return None


def _shell_payload(program: str, args: Sequence[str]) -> str | None:
    base = _base(program)
    if base == "eval":
        return " ".join(args)
    if base in _SHELLS:
        for idx, a in enumerate(args):
            if a.lower() in _SHELL_COMMAND_FLAGS and idx + 1 < len(args):
                return " ".join(args[idx + 1 :])
    return None


def find_reserved_use(command: str, depth: int = 0) -> ReservedUse | None:
    """First reserved rapid invocation found anywhere in a shell command line."""
    if depth > 4 or not command.strip():
        return None
    outer, inner = _extract_substitutions(_strip_heredocs(command))
    for body in inner:
        found = find_reserved_use(body, depth + 1)
        if found:
            return found
    for tokens in _tokenize(outer):
        words, _ = _split_redirections(tokens)
        words = _skip_wrappers(words)
        if not words:
            continue
        program, args = words[0], words[1:]
        nested = _shell_payload(program, args)
        if nested is not None:
            found = find_reserved_use(nested, depth + 1)
            if found:
                return found
            continue
        base = _base(program)
        if base in _RAPID_PROGRAMS:
            found = _reserved_in_rapid_args(args)
            if found:
                return found
        elif _PYTHON.match(base):
            rapid_args = _python_rapid_args(args)
            if rapid_args is not None:
                found = _reserved_in_rapid_args(rapid_args)
                if found:
                    return found
            elif "-c" in args:
                code = args[args.index("-c") + 1] if args.index("-c") + 1 < len(args) else ""
                if "rapid_os" in code and _PYTHON_CODE_HINT.search(code):
                    return ReservedUse("approve" if "approve" in code else "abort")
    return None


def _norm_path(path: str, cwd: str) -> str:
    text = path.replace("\\", "/")
    is_abs = text.startswith("/") or re.match(r"^[A-Za-z]:/", text) is not None
    if not is_abs and cwd:
        text = posixpath.join(cwd.replace("\\", "/"), text)
    return posixpath.normpath(text).lower()


def is_protected_path(path: str, cwd: str, protected_dirs: Sequence[str]) -> bool:
    """True if `path` is inside one of the `.rapid-os` directories (compared case-insensitively)."""
    if not path:
        return False
    if path.startswith(("$", "~")):
        # Cannot be resolved without a shell: a literal .rapid-os segment is enough to refuse it.
        return ".rapid-os" in path.replace("\\", "/").split("/")
    resolved = _norm_path(path, cwd)
    for directory in protected_dirs:
        d = directory.replace("\\", "/").rstrip("/").lower()
        if resolved == d or resolved.startswith(d + "/"):
            return True
    return False


def find_protected_write(command: str, cwd: str, protected_dirs: Sequence[str], depth: int = 0) -> str | None:
    """Return the offending path when the shell command writes inside `.rapid-os/` (best-effort)."""
    if depth > 4 or not command.strip():
        return None
    outer, inner = _extract_substitutions(_strip_heredocs(command))
    for body in inner:
        found = find_protected_write(body, cwd, protected_dirs, depth + 1)
        if found:
            return found
    for tokens in _tokenize(outer):
        words, redirect_targets = _split_redirections(tokens)
        for target in redirect_targets:
            if is_protected_path(target, cwd, protected_dirs):
                return target
        words = _skip_wrappers(words)
        if not words:
            continue
        program, args = words[0], words[1:]
        nested = _shell_payload(program, args)
        if nested is not None:
            found = find_protected_write(nested, cwd, protected_dirs, depth + 1)
            if found:
                return found
            continue
        base = _base(program)
        positional = _positionals(args)
        candidates: list[str] = []
        if base in _WRITERS_ANY:
            candidates = positional
        elif base in _WRITERS_LAST:
            candidates = positional[-1:]
            for idx, a in enumerate(args):
                if a in ("-t", "--target-directory") and idx + 1 < len(args):
                    candidates.append(args[idx + 1])
        elif base in ("sed", "perl", "gsed") and any(
            a == "--in-place" or (a.startswith("-") and not a.startswith("--") and "i" in a[1:] and base != "perl")
            or (base == "perl" and a.startswith("-") and not a.startswith("--") and "i" in a[1:])
            for a in args
        ):
            candidates = positional
        elif base == "dd":
            candidates = [a[3:] for a in args if a.startswith("of=")]
        for candidate in candidates:
            if is_protected_path(candidate, cwd, protected_dirs):
                return candidate
    return None


@dataclass(frozen=True)
class PreToolDecision:
    reason: str


def _approve_reason(use: ReservedUse) -> str:
    if use.command == "approve":
        typed = f"rapid approve {use.gate}" if use.gate else "rapid approve <gate-id>"
        return (
            "Human gates are approved by a person, never by the agent. Ask the person to run "
            f"`{typed}` in their own terminal, summarise the evidence for them, and meanwhile follow "
            "`rapid next --json`."
        )
    if use.command == "abort":
        return (
            "Aborting a run is the person's decision. Explain why the run cannot continue and ask "
            "them to run `rapid abort` in their own terminal; meanwhile follow `rapid next --json`."
        )
    return (
        f"`rapid {use.command}` is reserved for the person and changes the ledger outside the porcelain "
        "flow. Run `rapid next --json` and follow action.command instead."
    )


def decide_pre_tool(payload: HookPayload, protected_dirs: Sequence[str]) -> PreToolDecision | None:
    """Return a denial for reserved rapid commands and for edits inside `.rapid-os/`, else None."""
    tool_input = payload.tool_input or {}
    cwd = payload.cwd

    if payload.tool_name in SHELL_TOOLS:
        command = tool_input.get("command")
        if not isinstance(command, str):
            return None
        use = find_reserved_use(command)
        if use:
            return PreToolDecision(_approve_reason(use))
        offending = find_protected_write(command, cwd, protected_dirs)
        if offending:
            return PreToolDecision(
                f"`{offending}` is inside .rapid-os/, which only the rapid commands may change (the ledger "
                "is append-only). Run `rapid next --json` and use its commands instead of writing there."
            )
        return None

    if payload.tool_name in FILE_TOOLS:
        for key in PATH_KEYS:
            value = tool_input.get(key)
            if isinstance(value, str) and is_protected_path(value, cwd, protected_dirs):
                return PreToolDecision(
                    f"`{value}` is inside .rapid-os/, which only the rapid commands may change (the ledger "
                    "is append-only). Run `rapid next --json` and use its commands instead of editing there."
                )
    return None


def pre_tool_output(decision: PreToolDecision) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": decision.reason,
        }
    }

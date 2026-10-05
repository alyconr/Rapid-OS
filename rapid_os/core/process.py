import os
import shutil
import subprocess
from typing import Sequence


NPX_WINDOWS_CANDIDATES = ("npx.cmd", "npx.exe", "npx")
NPX_POSIX_CANDIDATES = ("npx",)


def resolve_npx_executable(which_fn=shutil.which, os_name=None) -> str | None:
    """Resolve the npx executable safely across Windows and POSIX platforms."""
    active_os = os.name if os_name is None else os_name
    candidates = (
        NPX_WINDOWS_CANDIDATES if active_os == "nt" else NPX_POSIX_CANDIDATES
    )
    for candidate in candidates:
        resolved = which_fn(candidate)
        if resolved:
            return resolved
    return None


def run_command(
    args: Sequence[str],
    *,
    check: bool = True,
    capture_output: bool = False,
    quiet: bool = False,
    cwd=None,
    env=None,
    runner=subprocess.run,
):
    """Execute a subprocess using a direct argument vector with shell=False."""
    if isinstance(args, (str, bytes)) or not args:
        raise ValueError("Subprocess arguments must be a non-empty sequence of strings.")

    argv = []
    for item in args:
        if not isinstance(item, str):
            raise TypeError(f"Subprocess argument must be a string, got {type(item).__name__}.")
        if "\x00" in item:
            raise ValueError("Subprocess argument cannot contain null bytes.")
        argv.append(item)

    kwargs = {
        "check": check,
        "shell": False,
    }
    if cwd is not None:
        kwargs["cwd"] = cwd
    if env is not None:
        kwargs["env"] = env
    if quiet:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    elif capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE

    return runner(argv, **kwargs)


def build_npx_skills_add_command(skill_name: str, npx_executable: str = "npx") -> list[str]:
    """Build the argument vector for `npx skills add <skill_name>`."""
    if not isinstance(skill_name, str) or not skill_name.strip():
        raise ValueError("Remote skill name cannot be empty.")
    if "\x00" in skill_name:
        raise ValueError("Remote skill name cannot contain null bytes.")
    executable = (npx_executable or "").strip() or "npx"
    return [executable, "skills", "add", skill_name.strip()]


def run_npx_skills_add(
    skill_name: str,
    *,
    which_fn=shutil.which,
    os_name=None,
    runner=subprocess.run,
):
    """Run `npx skills add <skill_name>` without invoking a shell."""
    npx_executable = resolve_npx_executable(which_fn=which_fn, os_name=os_name) or "npx"
    argv = build_npx_skills_add_command(skill_name, npx_executable=npx_executable)
    return run_command(argv, check=True, runner=runner)


def is_npx_available(*, which_fn=shutil.which, os_name=None, runner=subprocess.run) -> bool:
    """Return True when npx is installed and responds to `--version` without a shell."""
    npx_executable = resolve_npx_executable(which_fn=which_fn, os_name=os_name)
    if not npx_executable:
        npx_executable = "npx.cmd" if (os.name if os_name is None else os_name) == "nt" else "npx"
    try:
        completed = run_command(
            [npx_executable, "--version"],
            check=True,
            quiet=True,
            runner=runner,
        )
        returncode = getattr(completed, "returncode", 0)
        return returncode == 0
    except (OSError, subprocess.SubprocessError, ValueError):
        return False

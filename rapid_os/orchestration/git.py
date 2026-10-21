"""The one door to git.

Every git command Rapid OS runs goes through `run_git`, so the two settings that make that safe
are never forgotten:

- `safe.directory=<root>`: inside the Codex sandbox on Windows the commands run as another
  Windows user, and git refuses a folder whose owner is not the one asking ("dubious
  ownership"). Rapid OS trusts only the project root, never `*`.
- `core.fsmonitor=false`: the fsmonitor is what lets a repository that is not ours run a program
  when it is read.

`person_git_trust` is the exception on purpose: it asks git the way the *person's own terminal*
would (without those settings) to learn whether they need the exception for themselves.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

PERSON_ACTION_ID = "git-safe-directory"
PERSON_ACTION_WHY = (
    "El harness ejecuta los comandos con otro usuario de Windows y git exige que el dueño "
    "de la carpeta sea el mismo usuario que lo usa."
)
PERSON_ACTION_TEXT = "Para usar git tú mismo en esta carpeta, ejecuta en tu terminal: {command}"


def git_root(root: Path | str | None) -> Path:
    """The absolute project root git runs in."""
    return Path(root if root is not None else ".").absolute()


def is_untrusted_message(stderr: str | None) -> bool:
    """git's refusal to read a folder somebody else owns."""
    text = stderr or ""
    return "dubious ownership" in text or "safe.directory" in text


def run_git(root: Path | str | None, *args: str) -> subprocess.CompletedProcess:
    """Run `git <args>` in `root`, trusting `root` (and only `root`) and without the fsmonitor.

    Raises OSError when git cannot be executed (not installed, or `root` is not a directory).
    """
    base = git_root(root)
    return subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={base.as_posix()}",
            "-c",
            "core.fsmonitor=false",
            *args,
        ],
        cwd=str(base),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )


@dataclass(frozen=True)
class PersonGitTrust:
    """Whether the person needs `safe.directory` to use git by hand in this folder."""

    needs_exception: bool = False
    command: str | None = None


def person_git_trust(root: Path | str | None) -> PersonGitTrust:
    """Ask git as the person's terminal would (no `-c`). If git refuses with "dubious ownership"
    but `run_git` works, the folder needs the exception for whoever uses git by hand.

    The command is per user (`--global` is read only by them, no administrator rights). Never
    `--system` and never `*`.
    """
    base = git_root(root)
    try:
        person = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(base),
            capture_output=True,
            text=True,
            check=False,
            shell=False,
        )
        if person.returncode == 0 or not is_untrusted_message(person.stderr):
            return PersonGitTrust()
        ours = run_git(base, "rev-parse", "--is-inside-work-tree")
    except OSError:
        return PersonGitTrust()
    if ours.returncode == 0 and ours.stdout.strip() == "true":
        return PersonGitTrust(True, f"git config --global --add safe.directory {base.as_posix()}")
    return PersonGitTrust()


def person_actions(root: Path | str | None) -> list[dict[str, str]]:
    """What only the person can do, each with its exact command. Empty when nothing applies."""
    trust = person_git_trust(root)
    if not trust.needs_exception:
        return []
    return [{"id": PERSON_ACTION_ID, "why": PERSON_ACTION_WHY, "command": trust.command or ""}]


def person_action_lines(actions: list[dict[str, str]]) -> list[str]:
    """The text form of `person_actions`."""
    lines: list[str] = []
    for action in actions:
        lines.append(PERSON_ACTION_TEXT.format(command=action["command"]))
        lines.append(f"  Por qué: {action['why']}")
    return lines

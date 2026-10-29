"""The architecture violations a run did not cause: the photo taken when the run starts.

The architecture rule applies to new code; the migration of old code is `/rapid-refactor`. So `rapid start`
keeps a photo of the violations the project already has (file, rule and import, without the line number,
which moves when the file is edited), and `gate.architecture` and the final check of `rapid finish` fail only
for violations that are not in it. The previous ones are reported as debt and do not block the run.

- No active run, or a run that started before this existed (no photo): every violation counts as previous.
- Refactor runs: a previous violation in a file the run touched counts as new. A file cannot be touched and
  left violating.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from rapid_os.adapters.architecture_files import collect_sources
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.domain.architecture import ArchitectureConfigError, Violation, check_architecture
from rapid_os.orchestration.architecture_rule import main_project_rapid_dir, resolve_architecture_rule
from rapid_os.orchestration.session import load_session, observed_changes

REFACTOR_MODE = "refactor"
# (file, rule, imported): what identifies a violation across edits of its file.
ViolationKey = tuple[str, str, str]


@dataclass(frozen=True)
class RunBaseline:
    run_id: str
    mode: str
    keys: frozenset[ViolationKey]
    # Files the run changed; only filled in refactor mode, where touching a file makes its debt count.
    touched: frozenset[str] = frozenset()


def violation_key(violation: Violation) -> ViolationKey:
    return (violation.file, violation.rule, violation.imported)


def current_violations(current_dir: Path, project_rapid_dir: Path) -> list[Violation] | None:
    """Every violation of the code in `current_dir`, or None when there is no rule to judge it by.

    A rule that delegates to an external tool (packwerk) has nothing to photograph and is skipped."""
    try:
        rule = resolve_architecture_rule(current_dir, project_rapid_dir)
    except ArchitectureConfigError:
        return None
    if not rule.configs:
        return None
    found: list[Violation] = []
    for config in rule.configs:
        if config.delegate:
            continue
        found.extend(check_architecture(config, collect_sources(current_dir, config)).violations)
    return found


def capture_snapshot(project_root: Path, project_rapid_dir: Path) -> tuple[ViolationKey, ...] | None:
    """The photo `rapid start` stores: the keys of today's violations; None without an architecture rule."""
    violations = current_violations(project_root, project_rapid_dir)
    if violations is None:
        return None
    return tuple(sorted({violation_key(v) for v in violations}))


def active_baseline(current_dir: Path, project_rapid_dir: Path) -> RunBaseline | None:
    """The photo of the active run, or None (no run, a closed run, or a run that has no photo)."""
    for rapid_dir in (Path(project_rapid_dir), main_project_rapid_dir(Path(current_dir))):
        if rapid_dir is None:
            continue
        try:
            session = load_session(rapid_dir)
        except Exception:  # a broken session is reported elsewhere; here it only means "no photo"
            continue
        if session is None or not session.active_run_id or session.start_architecture is None:
            continue
        try:
            state = RunRegistry(rapid_dir.parent, rapid_dir).get_state(session.active_run_id)
        except Exception:
            continue
        if state.status.is_terminal:
            continue
        touched: frozenset[str] = frozenset()
        if session.mode == REFACTOR_MODE:
            workspace = Path(session.workspace_path) if session.workspace_path else rapid_dir.parent
            touched = frozenset(observed_changes(workspace, session.start_head, session.start_untracked or ()))
        return RunBaseline(session.active_run_id, session.mode, frozenset(session.start_architecture), touched)
    return None


def classify(
    violations: Iterable[Violation], baseline: RunBaseline | None
) -> tuple[list[Violation], list[Violation]]:
    """`(new, previous)`. Without a photo nothing is new."""
    if baseline is None:
        return [], list(violations)
    new: list[Violation] = []
    previous: list[Violation] = []
    for violation in violations:
        if violation_key(violation) in baseline.keys and violation.file not in baseline.touched:
            previous.append(violation)
        else:
            new.append(violation)
    return new, previous


def previous_debt_line(previous: Sequence[Violation], baseline: RunBaseline | None) -> str:
    """The sentence that says how many violations are old debt and what to do about them."""
    count = len(previous)
    noun = "violación previa" if count == 1 else "violaciones previas"
    return (
        f"{count} {noun}; no bloquean este run (son deuda anterior a él: corrígelas con /rapid-refactor"
        + (", que no deja un archivo tocado violando" if baseline is not None and baseline.mode == REFACTOR_MODE else "")
        + ")."
    )

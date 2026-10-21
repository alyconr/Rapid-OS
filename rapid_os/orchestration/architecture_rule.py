"""Where `rapid arch check` finds the architecture rule, and whether the run demands it.

A run in a git worktree analyses the worktree's code, but the ledger and the rule live in the
main project: the worktree has no `.rapid-os/`. So, when the rule is not in the current
directory and there is an active run whose contract has `gate.architecture`, the rule is read
from the project the session belongs to. A run that demands the gate never passes without a rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rapid_os.adapters.architecture_files import config_path, load_config
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.domain.architecture import ArchitectureConfig
from rapid_os.domain.policy import ARCHITECTURE_GATE_ID
from rapid_os.orchestration.git import run_git
from rapid_os.orchestration.session import load_session

RUN_DEMANDS_RULE_MESSAGE = "RAPID1420 el run exige gate.architecture y no hay architecture.json"


@dataclass(frozen=True)
class ArchitectureRule:
    config: ArchitectureConfig | None
    source: Path | None  # the architecture.json that was read
    run_demands_gate: bool


def _main_project_rapid_dir(current_dir: Path) -> Path | None:
    """`.rapid-os` of the main project when `current_dir` is a linked git worktree, else None."""
    try:
        proc = run_git(current_dir, "rev-parse", "--git-common-dir")
    except OSError:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    common = (current_dir / proc.stdout.strip()).resolve()
    own_git = (current_dir / ".git").resolve()
    if common.name != ".git" or common == own_git:
        return None
    return common.parent / ".rapid-os"


def _run_demands_gate(rapid_dir: Path) -> bool:
    """True when the active run of `rapid_dir`'s session has `gate.architecture` in its contract."""
    try:
        session = load_session(rapid_dir)
        if session is None or not session.active_run_id:
            return False
        contract = RunRegistry(rapid_dir.parent, rapid_dir).get_contract(session.active_run_id)
    except Exception:  # a broken ledger is reported elsewhere; here it only means "not demanded"
        return False
    return any(gate.id == ARCHITECTURE_GATE_ID for gate in contract.gates)


def resolve_architecture_rule(current_dir: Path, project_rapid_dir: Path) -> ArchitectureRule:
    """The rule to check against. Raises `ArchitectureConfigError` when the file is invalid."""
    current_dir, project_rapid_dir = Path(current_dir), Path(project_rapid_dir)
    main_rapid_dir = _main_project_rapid_dir(current_dir)
    demanded_by = next(
        (d for d in (project_rapid_dir, main_rapid_dir) if d is not None and _run_demands_gate(d)), None
    )
    demands = demanded_by is not None

    for candidate in (project_rapid_dir, demanded_by if demands and demanded_by != project_rapid_dir else None):
        if candidate is not None and config_path(candidate).is_file():
            return ArchitectureRule(load_config(candidate), config_path(candidate), demands)
    return ArchitectureRule(None, None, demands)

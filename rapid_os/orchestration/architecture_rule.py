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
FINAL_CHECK_CODE = "RAPID1422"


@dataclass(frozen=True)
class ArchitectureRule:
    configs: tuple[ArchitectureConfig, ...]
    source: Path | None  # the architecture.json that was read
    run_demands_gate: bool

    @property
    def config(self) -> ArchitectureConfig | None:
        """The first rule (the backend's): kept for callers that look at one."""
        return self.configs[0] if self.configs else None


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
            return ArchitectureRule(tuple(load_config(candidate) or ()), config_path(candidate), demands)
    return ArchitectureRule((), None, demands)


def final_architecture_failure(current_dir: Path, project_rapid_dir: Path) -> str | None:
    """Runs the architecture check again over the code as it is now; None when it holds.

    `rapid finish` calls it before the verdict: `gate.architecture` may have passed earlier in the
    run and a violation been added afterwards. The message lists every violation (RAPID1422)."""
    # Late imports: the check itself is a use case of its own and this module is imported by the CLI.
    from rapid_os.adapters.architecture_files import collect_sources
    from rapid_os.domain.architecture import ArchitectureConfigError, check_architecture
    from rapid_os.orchestration.arch_delegate import run_delegate

    try:
        rule = resolve_architecture_rule(current_dir, project_rapid_dir)
    except ArchitectureConfigError as exc:
        return f"{FINAL_CHECK_CODE} rapid finish no da PASS: {exc}"
    if not rule.configs:
        return f"{FINAL_CHECK_CODE} rapid finish no da PASS: {RUN_DEMANDS_RULE_MESSAGE}"
    lines: list[str] = []
    for config in rule.configs:
        if config.delegate:
            result = run_delegate(config.delegate, current_dir)
            if not result.ok:
                lines.append(result.output or f"{config.delegate} no pasó")
            continue
        report = check_architecture(config, collect_sources(current_dir, config))
        lines.extend(violation.to_line() for violation in report.violations)
    if not lines:
        return None
    return (
        f"{FINAL_CHECK_CODE} rapid finish no da PASS: gate.architecture falla sobre el estado final del run "
        f"({len(lines)} problema(s)); el run sigue abierto.\n"
        + "\n".join(lines)
        + "\nCorrige las violaciones y vuelve a ejecutar `rapid finish`."
    )

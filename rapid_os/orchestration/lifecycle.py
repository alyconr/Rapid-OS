"""Porcelain lifecycle operations for Rapid OS intent layer (start, finish, approve, abort).

Encapsulates state orchestration, evidence recording, and eval integration
using domain models and registries without direct CLI dependence.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence

from rapid_os.adapters.eval_registry import EvalRegistry
from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.project_snapshot import resolve_project_snapshot_path, write_project_snapshot
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.core.ancestry import AncestryResult, find_agent_ancestor, read_ancestry
from rapid_os.core.config import load_project_config
from rapid_os.core.harness_detect import detect_harness
from rapid_os.domain.evals import (
    BehavioralEvaluator,
    EvaluationVerdict,
    REVIEW_GATE_KIND_TO_REVIEW_TYPE,
)
from rapid_os.domain.evidence import EvidenceKind
from rapid_os.domain.execution import (
    InvalidGateTransitionError,
    GateDisposition,
    GatePhase,
    GateKind,
    RunStatus,
    TaskStatus,
    WorkspaceRequirement,
)
from rapid_os.domain.execution import (
    BASELINE_WAIVER_EMPTY_REPOSITORY,
    enforce_gate_transition_preconditions,
    validate_gate_transition,
)
from rapid_os.domain.policy import ExecutionError
from rapid_os.domain.scanner import build_project_model
from rapid_os.orchestration.actions import ActionKind, NextAction
from rapid_os.orchestration.check import run_check
from rapid_os.orchestration.conductor import (
    HUMAN_GATE_KINDS,
    _rejected_human_gate_ids,
    gate_satisfied,
    next_action,
    next_action_without_run,
)
from rapid_os.orchestration.playbooks import load_playbook
from rapid_os.orchestration.git import run_git
from rapid_os.orchestration.session import (
    Session,
    clear_session,
    load_session,
    resolve_git_head,
    git_trust_command,
    git_work_tree_state,
    observed_changes,
    resolve_git_untracked,
    save_session,
)
from rapid_os.orchestration.workspace import WorkspaceError, create_run_worktree


NOT_A_GIT_REPOSITORY_MESSAGE = (
    "RAPID1416 Rapid OS observa los cambios del run con git y esta carpeta no es un repositorio. "
    "Ejecuta: git init  (o rapid setup finish, que lo crea)"
)
SCAFFOLD_TASK_TEXT = "Scaffold mínimo con un test que pase"
# Modes that need existing code: in a brand-new repository they cannot start.
EMPTY_REPO_REFUSED_VERBS = {
    "bugfix": "arreglar",
    "refactor": "refactorizar",
    "hardening": "endurecer",
}
_TASK_PREFIX_RE = re.compile(r"^T\d+\s*[:.\-]\s*")


def has_scaffold_task(tasks) -> bool:
    return bool(tasks) and SCAFFOLD_TASK_TEXT in str(tasks[0])


SCAFFOLD_TEST_COMMAND_HINT = "Configura el comando con rapid setup set test-command <cmd> antes de cerrarla"


def with_scaffold_task(tasks, *, needs_test_command: bool = False) -> list[str]:
    """The scaffold as the first task. Contract task ids start at T001, so the scaffold is T001
    and the written `T00n:` prefixes of the other tasks move down by one to keep matching.

    Without a `test_command` the task says how to set one: `rapid task done` needs it."""
    if has_scaffold_task(tasks):
        return list(tasks)
    renumbered = []
    for index, task in enumerate(tasks, start=2):
        text = str(task)
        renumbered.append(
            f"T{index:03d}: {text[_TASK_PREFIX_RE.match(text).end():]}" if _TASK_PREFIX_RE.match(text) else text
        )
    scaffold = f"T001: {SCAFFOLD_TASK_TEXT}"
    if needs_test_command:
        scaffold += f". {SCAFFOLD_TEST_COMMAND_HINT}"
    return [scaffold, *renumbered]


def scaffold_notes(original, injected) -> tuple[str, ...]:
    """What the scaffold changed in the task list the agent wrote, so nobody is surprised.

    Contract task ids start at T001, so the scaffold takes T001 and the written `T00n:`
    prefixes move down: the note maps them (`T001→T002`).
    """
    moved = []
    for before, after in zip(original, injected[1:]):
        old, new = re.match(r"T\d+", str(before)), re.match(r"T\d+", str(after))
        if old and new and old.group(0) != new.group(0):
            moved.append(f"{old.group(0)}→{new.group(0)}")
    note = (
        f"Proyecto nuevo (sin código ni tests): Rapid OS añadió la tarea T001, «{SCAFFOLD_TASK_TEXT}», "
        "y el run no tiene baseline."
    )
    if moved:
        note += f" Tus tareas se renumeraron para coincidir con el run: {', '.join(moved)}."
    return (note,)


def _author_spec_action(
    mode: str,
    playbook: Playbook,
    project_root: Path,
    project_rapid_dir: Path,
    templates_dir: Path | None,
) -> NextAction:
    """`author_spec`, with the brief's open stories as `seed` for the feature mode."""
    seed = None
    if mode == "feature":
        # Lazy: the adapters import the orchestration package.
        from rapid_os.adapters.project_docs import build_brief_seed

        seed = build_brief_seed(project_root, project_rapid_dir, templates_dir)
    return next_action_without_run(mode, playbook, seed)


def _decorate_action(action: NextAction, sess: Session | None) -> NextAction:
    """Tell the agent where to work when the run has an isolated worktree."""
    if sess is None or not sess.workspace_path:
        return action
    if action.kind in (ActionKind.DONE, ActionKind.AUTHOR_SPEC):
        return action
    note = (
        f"Work inside the isolated worktree '{sess.workspace_path}' (edit files there); "
        "keep running rapid commands from the main repository."
    )
    return replace(
        action,
        instructions=f"{action.instructions} {note}".strip(),
        workspace_path=sess.workspace_path,
    )


def execute_start(
    project_root: Path,
    project_rapid_dir: Path,
    mode: str | None = None,
    *,
    objective: str | None = None,
    spec_id: str | None = None,
    spec_file: str | None = None,
    harness: str | None = None,
    resume: bool = False,
    environ: dict[str, str] | None = None,
    config_file: Path | None = None,
    templates_dir: Path | None = None,
    stdin_content: str | None = None,
    worktree: bool = False,
) -> tuple[int, NextAction | str]:
    """Execute porcelain `rapid start` workflow.

    Returns (exit_code, NextAction | error_message).
    """
    standards_dir = project_rapid_dir / "standards"
    if not standards_dir.exists() or not standards_dir.is_dir():
        return (
            1,
            "RAPID1309 Project not initialized (.rapid-os/standards/ missing). Run 'rapid init' first.",
        )

    # Check active session
    existing_session = load_session(project_rapid_dir)
    run_reg = RunRegistry(project_root, project_rapid_dir)

    if resume:
        if not existing_session or not existing_session.active_run_id:
            return 1, "RAPID1307 No active run session found to resume."
        active_run_id = existing_session.active_run_id
        contract = run_reg.get_contract(active_run_id)
        current_state = run_reg.get_state(active_run_id)
        mode = mode or existing_session.mode
    else:
        if not mode:
            return 1, "Mode is required when starting a run (e.g. 'rapid start feature')."
        if existing_session and existing_session.active_run_id:
            try:
                active_state = run_reg.get_state(existing_session.active_run_id)
                if not active_state.status.is_terminal:
                    return (
                        1,
                        f"RAPID1308 An active non-terminal run '{existing_session.active_run_id}' ({active_state.status.value}) already exists in session. Use 'rapid next' to continue or 'rapid abort' to cancel it.",
                    )
            except Exception:
                pass

    playbook = load_playbook(mode, templates_dir=templates_dir)

    # A run's changes are observed with git: without it the run could never pass.
    if not resume:
        git_state = git_work_tree_state(project_root)
        if git_state == "untrusted":
            return (
                1,
                "RAPID1416 git no confía en esta carpeta (dubious ownership), así que Rapid OS no puede "
                f"observar los cambios. Ejecuta: {git_trust_command(project_root)}",
            )
        if git_state != "inside":
            return 1, NOT_A_GIT_REPOSITORY_MESSAGE

    # A brand-new repository (no source code, no tests) has nothing to fix, refactor or harden,
    # and nothing to take a baseline of: only `feature` starts there, with a scaffold task.
    empty_repository = False
    baseline_waived: str | None = None
    run_notes: tuple[str, ...] = ()
    if not resume:
        from rapid_os.domain.scanner import is_empty_repository

        empty_repository = is_empty_repository(project_root)
        if empty_repository and mode in EMPTY_REPO_REFUSED_VERBS:
            return (
                1,
                f"RAPID1413 No hay código que {EMPTY_REPO_REFUSED_VERBS[mode]}; usa /rapid-feature",
            )

    # 1.c Ensure .rapid-os/project.json exists
    snapshot_path = resolve_project_snapshot_path(project_rapid_dir)
    if not snapshot_path.exists():
        model = build_project_model(project_root)
        write_project_snapshot(model, project_rapid_dir, backup=False)

    spec_reg = SpecRegistry(project_root, project_rapid_dir)
    evaluator = BehavioralEvaluator()

    if not resume:
        # 1.d Spec resolution
        resolved_spec_id: str | None = None
        if spec_id:
            rec = spec_reg.get(spec_id)
            if rec.status.value != "ready":
                return (
                    1,
                    f"Spec '{spec_id}' is in status '{rec.status.value}', expected 'ready'.",
                )
            resolved_spec_id = rec.id
            if empty_repository and mode == "feature":
                if has_scaffold_task(spec_reg.get_revision(rec.id).implementation_tasks):
                    baseline_waived = BASELINE_WAIVER_EMPTY_REPOSITORY
        elif spec_file:
            raw_json: str
            if spec_file == "-":
                raw_json = stdin_content if stdin_content is not None else sys.stdin.read()
            else:
                p = Path(spec_file)
                if not p.is_absolute():
                    p = project_root / p
                raw_json = p.read_text(encoding="utf-8")

            payload = json.loads(raw_json)
            if not isinstance(payload, dict):
                return 1, "Spec file content must be a JSON object."

            spec_fields: dict[str, Any] = dict(payload)
            spec_fields["mode"] = mode
            if objective and "business_objective" not in spec_fields:
                spec_fields["business_objective"] = objective

            # Map possible field aliases
            if "objective" in spec_fields and "business_objective" not in spec_fields:
                spec_fields["business_objective"] = spec_fields.pop("objective")
            if "problem" in spec_fields and "problem_statement" not in spec_fields:
                spec_fields["problem_statement"] = spec_fields.pop("problem")
            if "acceptance" in spec_fields and "acceptance_criteria" not in spec_fields:
                spec_fields["acceptance_criteria"] = spec_fields.pop("acceptance")
            if "tasks" in spec_fields and "implementation_tasks" not in spec_fields:
                spec_fields["implementation_tasks"] = spec_fields.pop("tasks")

            if empty_repository and mode == "feature":
                written_tasks = list(spec_fields.get("implementation_tasks") or [])
                scaffold_config = load_project_config(config_file or (project_rapid_dir / "config.json"))
                spec_fields["implementation_tasks"] = with_scaffold_task(
                    written_tasks, needs_test_command=not scaffold_config.get("test_command")
                )
                if not has_scaffold_task(written_tasks):
                    run_notes = scaffold_notes(written_tasks, spec_fields["implementation_tasks"])
                baseline_waived = BASELINE_WAIVER_EMPTY_REPOSITORY

            existing = spec_reg.compare_existing(**spec_fields)
            if existing is None:
                created_spec = spec_reg.create(**spec_fields)
                ready_spec = spec_reg.set_status(created_spec.id, "ready")
                resolved_spec_id = ready_spec.id
            else:
                existing_record, identical = existing
                if not identical or existing_record.status.value == "archived":
                    return (
                        1,
                        f"RAPID1322 Spec '{existing_record.id}' already exists with different content "
                        f"(or is archived). Reuse it with `rapid start {mode} --spec {existing_record.id}` "
                        "or change the title/id in the spec file.",
                    )
                # Same identity and content: a previous `rapid start` created it and then failed.
                if existing_record.status.value == "draft":
                    existing_record = spec_reg.set_status(existing_record.id, "ready")
                resolved_spec_id = existing_record.id
        else:
            # Neither --spec nor --spec-file: do NOT create anything, return author_spec
            action = _author_spec_action(mode, playbook, project_root, project_rapid_dir, templates_dir)
            return 0, action

        # 1.e Run creation
        cfg = config_file or (project_rapid_dir / "config.json")
        project_cfg = load_project_config(cfg)
        env_map = environ if environ is not None else dict(sys.modules["os"].environ)
        detection = detect_harness(harness, env_map, project_cfg)

        try:
            record = run_reg.create(
                spec_id=resolved_spec_id,
                harness=detection.harness_id,
                baseline_waived=baseline_waived,
            )
        except ExecutionError as exc:
            # Expected failures (e.g. a required context source is missing for the mode).
            return 1, f"{exc.code} Cannot create run: {exc}"
        active_run_id = record.id
        contract = run_reg.get_contract(active_run_id)
        current_state = run_reg.get_state(active_run_id)

    # Session object creation
    if resume and existing_session and existing_session.start_head:
        start_head = existing_session.start_head
    else:
        start_head = resolve_git_head(project_root)

    if resume and existing_session:
        start_untracked = existing_session.start_untracked
        workspace_path = existing_session.workspace_path
    else:
        start_untracked = resolve_git_untracked(project_root)
        workspace_path = None

    sess = Session(
        active_run_id=active_run_id,
        mode=mode,
        harness=contract.harness,
        start_head=start_head,
        start_untracked=start_untracked,
        workspace_path=workspace_path,
    )
    save_session(project_rapid_dir, sess)

    evidence_reg = EvidenceRegistry(project_root, project_rapid_dir)

    # 1.f Workspace declaration
    if contract.workspace == WorkspaceRequirement.ISOLATED_REQUIRED:
        if sess.workspace_path is None and not worktree:
            action = NextAction(
                schema_version=1,
                run_id=active_run_id,
                mode=mode,
                kind=ActionKind.BLOCKED,
                instructions=(
                    "Execution contract requires an isolated workspace (worktree). "
                    "Workspace isolation must be established before execution: "
                    "run `rapid start --resume --worktree` to create it."
                ),
                command=("rapid", "start", "--resume", "--worktree"),
                after=None,
                awaiting_human=(),
                missing=("gate.workspace-isolation",),
                tasks_done=0,
                tasks_total=len(contract.tasks),
                outcome=None,
            )
            return 0, action

        if sess.workspace_path is None:
            try:
                created = create_run_worktree(project_root, active_run_id)
            except WorkspaceError as exc:
                return 1, str(exc)
            sess = replace(sess, workspace_path=str(created))
            save_session(project_rapid_dir, sess)

        existing_evs = evidence_reg.list(active_run_id)
        if not any(
            e.kind == EvidenceKind.WORKSPACE and e.payload.get("mode") == "isolated"
            for e in existing_evs
        ):
            evidence_reg.add(
                active_run_id,
                {
                    "kind": EvidenceKind.WORKSPACE.value,
                    "producer": "rapid:start",
                    "summary": "Workspace isolated in a git worktree",
                    "state_revision": run_reg.get_state(active_run_id).revision,
                    "task_ids": [],
                    "gate_ids": [
                        g.id for g in contract.gates if g.kind == GateKind.WORKSPACE_ISOLATION
                    ],
                    "capability_ids": ["workspace.isolated"],
                    "payload": {"mode": "isolated"},
                    "artifacts": [],
                },
                base_dir=project_root,
            )

        isolation_state = run_reg.get_state(active_run_id)
        isolation_evidence = evidence_reg.list(active_run_id)
        for iso_gate in contract.gates:
            if iso_gate.kind != GateKind.WORKSPACE_ISOLATION:
                continue
            iso_st = next((g for g in isolation_state.gates if g.id == iso_gate.id), None)
            if (
                iso_st is not None
                and iso_st.disposition == GateDisposition.PENDING
                and gate_satisfied(
                    contract, isolation_state, isolation_evidence, iso_gate.id, evaluator=evaluator
                )
            ):
                iso_ev = [e.id for e in isolation_evidence if e.kind == EvidenceKind.WORKSPACE]
                run_reg.transition_gate(
                    active_run_id,
                    iso_gate.id,
                    GateDisposition.ACKNOWLEDGED,
                    reason=f"verified by {iso_ev[-1] if iso_ev else 'evidence'} (isolated worktree)",
                )

    if contract.workspace == WorkspaceRequirement.CURRENT_ALLOWED:
        existing_evs = evidence_reg.list(active_run_id)
        has_ws_ev = any(
            e.kind == EvidenceKind.WORKSPACE and e.payload.get("mode") == "current"
            for e in existing_evs
        )
        if not has_ws_ev:
            evidence_reg.add(
                active_run_id,
                {
                    "kind": EvidenceKind.WORKSPACE.value,
                    "producer": "rapid:start",
                    "summary": "Workspace operates in current directory",
                    "state_revision": current_state.revision,
                    "task_ids": [],
                    "gate_ids": [],
                    "capability_ids": ["workspace.current"],
                    "payload": {"mode": "current"},
                    "artifacts": [],
                },
                base_dir=project_root,
            )

    # 1.g Baseline check & activation
    cfg = config_file or (project_rapid_dir / "config.json")
    project_cfg = load_project_config(cfg)
    test_cmd = project_cfg.get("test_command")
    timeout = float(project_cfg.get("check_timeout_s", 600))

    baseline_gate = next(
        (g for g in contract.gates if g.kind == GateKind.BASELINE_CHECK or g.id == "gate.baseline"),
        None,
    )

    current_state = run_reg.get_state(active_run_id)
    ev_records = evidence_reg.list(active_run_id)
    if current_state.status == RunStatus.PREPARED and baseline_gate:
        b_state = next((g for g in current_state.gates if g.id == baseline_gate.id), None)
        if b_state and b_state.disposition == GateDisposition.PENDING:
            if gate_satisfied(
                contract,
                current_state,
                ev_records,
                baseline_gate.id,
                evaluator=evaluator,
            ):
                matching_evs = [
                    e.id for e in ev_records
                    if baseline_gate.id in e.gate_ids and e.kind == EvidenceKind.TEST_RESULT
                ]
                ev_ref = matching_evs[-1] if matching_evs else "evidence"
                current_state = run_reg.transition_gate(
                    active_run_id,
                    baseline_gate.id,
                    GateDisposition.ACKNOWLEDGED,
                    reason=f"verified by {ev_ref}",
                )
                current_state = run_reg.transition_status(
                    active_run_id,
                    RunStatus.ACTIVE,
                    reason="Baseline verified and active",
                )
            elif not resume:
                if test_cmd and isinstance(test_cmd, (list, tuple)):
                    try:
                        chk_res = run_check(
                            project_root,
                            project_rapid_dir,
                            active_run_id,
                            test_cmd,
                            gate_ids=[baseline_gate.id],
                            kind="test_result",
                            test_command=test_cmd,
                            timeout=timeout,
                            cwd=Path(sess.workspace_path) if sess.workspace_path else None,
                        )
                        ev_records = evidence_reg.list(active_run_id)
                        if chk_res.exit_code == 0 and gate_satisfied(
                            contract,
                            current_state,
                            ev_records,
                            baseline_gate.id,
                            evaluator=evaluator,
                        ):
                            evidence_id = chk_res.evidence.id if chk_res.evidence else "E001"
                            current_state = run_reg.transition_gate(
                                active_run_id,
                                baseline_gate.id,
                                GateDisposition.ACKNOWLEDGED,
                                reason=f"verified by {evidence_id} (rapid:check)",
                            )
                            current_state = run_reg.transition_status(
                                active_run_id,
                                RunStatus.ACTIVE,
                                reason="Baseline verified and active",
                            )
                    except Exception:
                        pass

    # 1.g' A prepared run with no PRE_EXECUTION gate left pending (no baseline gate in low-risk
    # spikes, or the baseline and the workspace already verified) becomes active; otherwise
    # `next` would propose `start --resume` forever.
    current_state = run_reg.get_state(active_run_id)
    if current_state.status == RunStatus.PREPARED and not any(
        g.phase == GatePhase.PRE_EXECUTION and g.disposition == GateDisposition.PENDING
        for g in current_state.gates
    ):
        run_reg.transition_status(
            active_run_id,
            RunStatus.ACTIVE,
            reason="Pre-execution gates satisfied; run active",
        )

    # 1.h Return NextAction
    current_state = run_reg.get_state(active_run_id)
    ev_records = evidence_reg.list(active_run_id)
    action = next_action(
        contract,
        current_state,
        ev_records,
        playbook,
        evaluator=evaluator,
        test_command=test_cmd if isinstance(test_cmd, (list, tuple)) else None,
        workspace_ready=bool(sess.workspace_path),
    )
    if run_notes:
        action = replace(action, notes=run_notes)
    return 0, _decorate_action(action, sess)


def execute_next(
    project_root: Path,
    project_rapid_dir: Path,
    *,
    config_file: Path | None = None,
    templates_dir: Path | None = None,
) -> tuple[int, NextAction]:
    """Execute porcelain `rapid next` workflow."""
    sess = load_session(project_rapid_dir)
    cfg = config_file or (project_rapid_dir / "config.json")
    project_cfg = load_project_config(cfg)
    test_cmd = project_cfg.get("test_command")

    if not sess or not sess.active_run_id:
        mode = "feature"
        playbook = load_playbook(mode, templates_dir=templates_dir)
        action = _author_spec_action(mode, playbook, project_root, project_rapid_dir, templates_dir)
        return 0, action

    run_reg = RunRegistry(project_root, project_rapid_dir)
    evidence_reg = EvidenceRegistry(project_root, project_rapid_dir)
    evaluator = BehavioralEvaluator()

    try:
        contract = run_reg.get_contract(sess.active_run_id)
        current_state = run_reg.get_state(sess.active_run_id)
    except Exception:
        mode = sess.mode or "feature"
        playbook = load_playbook(mode, templates_dir=templates_dir)
        action = _author_spec_action(mode, playbook, project_root, project_rapid_dir, templates_dir)
        return 0, action

    playbook = load_playbook(sess.mode, templates_dir=templates_dir)
    ev_records = evidence_reg.list(sess.active_run_id)

    action = next_action(
        contract,
        current_state,
        ev_records,
        playbook,
        evaluator=evaluator,
        test_command=test_cmd if isinstance(test_cmd, (list, tuple)) else None,
        workspace_ready=bool(sess.workspace_path),
    )
    return 0, _decorate_action(action, sess)


def execute_finish(
    project_root: Path,
    project_rapid_dir: Path,
    *,
    config_file: Path | None = None,
    templates_dir: Path | None = None,
) -> tuple[int, EvaluationVerdict | NextAction | str]:
    """Execute porcelain `rapid finish` workflow.

    Returns (exit_code, EvaluationVerdict | NextAction | error_message).
    """
    sess = load_session(project_rapid_dir)
    if not sess or not sess.active_run_id:
        return 1, "RAPID1307 No active run session found (.rapid-os/session.json)."

    run_id = sess.active_run_id
    run_reg = RunRegistry(project_root, project_rapid_dir)
    evidence_reg = EvidenceRegistry(project_root, project_rapid_dir)
    eval_reg = EvalRegistry(project_root, project_rapid_dir)
    evaluator = BehavioralEvaluator()

    contract = run_reg.get_contract(run_id)
    current_state = run_reg.get_state(run_id)
    playbook = load_playbook(sess.mode, templates_dir=templates_dir)

    cfg = config_file or (project_rapid_dir / "config.json")
    project_cfg = load_project_config(cfg)
    test_cmd = project_cfg.get("test_command")

    if current_state.status.is_terminal:
        # The run already ended: finishing again records nothing and returns the stored verdict.
        # Exit 0 only for a passing verdict; a run that ended without a report exits 1.
        reports = eval_reg.list_reports(run_id)
        if reports:
            latest = reports[-1]
            passing = latest.verdict in (EvaluationVerdict.PASS, EvaluationVerdict.PASS_WITH_WAIVERS)
            return (0 if passing else 1), latest
        done = next_action(
            contract,
            current_state,
            evidence_reg.list(run_id),
            playbook,
            evaluator=evaluator,
            test_command=test_cmd if isinstance(test_cmd, (list, tuple)) else None,
        )
        return 1, done

    # 3.a Record file_change evidence from git
    start_head = sess.start_head
    changed_files: list[str] = []
    diff_cwd = project_root
    if sess.workspace_path:
        diff_cwd = Path(sess.workspace_path)
        if not diff_cwd.is_dir():
            return (
                1,
                f"RAPID1335 Workspace '{diff_cwd}' of run '{run_id}' no longer exists. "
                "Restore it with 'git worktree add' or run 'rapid abort'.",
            )
    # A repository without commits has no start_head, but its untracked files are still changes.
    # Tool artifacts (`__pycache__`, `*.pyc`...) are not writes of the project.
    if start_head or sess.start_untracked is not None:
        changed_files = observed_changes(diff_cwd, start_head, sess.start_untracked or ())

    if changed_files:
        current_state = run_reg.get_state(run_id)
        evidence_reg.add(
            run_id,
            {
                "kind": EvidenceKind.FILE_CHANGE.value,
                "producer": "rapid:finish",
                "summary": f"Recorded changes across {len(changed_files)} repository file(s)",
                "state_revision": current_state.revision,
                "task_ids": [],
                "gate_ids": [],
                "capability_ids": ["repository.write"],
                "payload": {"paths": sorted(changed_files)},
                "artifacts": [],
            },
            base_dir=project_root,
        )

    # 3.b Acknowledge machine gates that satisfy gate_satisfied
    current_state = run_reg.get_state(run_id)
    ev_records = evidence_reg.list(run_id)
    contract_gates_by_id = {g.id: g for g in contract.gates}

    for g_st in current_state.gates:
        c_gate = contract_gates_by_id.get(g_st.id)
        if not c_gate:
            continue
        if c_gate.kind in HUMAN_GATE_KINDS:
            continue
        if g_st.disposition == GateDisposition.PENDING:
            if gate_satisfied(contract, current_state, ev_records, g_st.id, evaluator=evaluator):
                matching_evs = [
                    e.id for e in ev_records
                    if g_st.id in e.gate_ids or any(cap in ("tests.execute", "shell.execute") for cap in e.capability_ids)
                ]
                cite = f"verified by {', '.join(matching_evs) if matching_evs else 'evidence'}"
                current_state = run_reg.transition_gate(
                    run_id,
                    g_st.id,
                    GateDisposition.ACKNOWLEDGED,
                    reason=cite,
                )
                ev_records = evidence_reg.list(run_id)

    # 3.c Check if there are UNVERIFIED assertions, open tasks, or pending human gates
    action = next_action(
        contract,
        current_state,
        ev_records,
        playbook,
        evaluator=evaluator,
        test_command=test_cmd if isinstance(test_cmd, (list, tuple)) else None,
    )
    if action.kind != ActionKind.FINISH:
        return 0, _decorate_action(action, sess)

    # 3.d Transition to finished and evaluate
    finished_state = run_reg.transition_status(
        run_id,
        RunStatus.FINISHED,
        reason="Run successfully finished by rapid finish",
    )
    report = eval_reg.evaluate_run(run_id, write=True)

    exit_code = 0 if report.verdict in (EvaluationVerdict.PASS, EvaluationVerdict.PASS_WITH_WAIVERS) else 1
    return exit_code, report


def _git_user_name(project_root: Path) -> str | None:
    try:
        proc = run_git(project_root, "config", "user.name")
    except OSError:
        return None
    name = proc.stdout.strip() if proc.returncode == 0 else ""
    return name or None


def _list_pending_human_gates(project_rapid_dir: Path, project_root: Path) -> tuple[int, str]:
    sess = load_session(project_rapid_dir)
    if not sess or not sess.active_run_id:
        return 1, "RAPID1307 No active run session found (.rapid-os/session.json)."
    run_reg = RunRegistry(project_root, project_rapid_dir)
    evidence_reg = EvidenceRegistry(project_root, project_rapid_dir)
    contract = run_reg.get_contract(sess.active_run_id)
    state = run_reg.get_state(sess.active_run_id)
    rejected = set(_rejected_human_gate_ids(contract, evidence_reg.list(sess.active_run_id)))
    kinds = {g.id: g.kind for g in contract.gates}

    lines = []
    for g_st in state.gates:
        kind = kinds.get(g_st.id)
        if kind not in HUMAN_GATE_KINDS or g_st.disposition != GateDisposition.PENDING:
            continue
        flags = "waivable" if g_st.waivable else "not waivable"
        if g_st.id in rejected:
            flags += ", rejected (changes_requested): run 'rapid abort'"
        lines.append(f"  {g_st.id}  [{kind.value}]  {flags}")
    if not lines:
        return 0, f"No pending human gates for run '{sess.active_run_id}'."
    header = f"Pending human gates for run '{sess.active_run_id}':"
    footer = "Approve with: rapid approve <gate-id>   (waive: --waive --reason TEXT; reject: --reject --reason TEXT)"
    return 0, "\n".join([header, *lines, footer])


def unverified_reason(report, project_root: Path | str) -> str | None:
    """Why an UNVERIFIED report has no write observation, or None when that is not the cause.

    Only when the verdict is `unverified` and `capability.repository.write.observed` did not
    pass: the folder is not a git repository, or git works and the run changed no project file.
    """
    if report.verdict.value != "unverified":
        return None
    observed = next(
        (a for a in report.assertions if a.id == "capability.repository.write.observed"), None
    )
    if observed is None or observed.status.value != "unverified":
        return None
    git_state = git_work_tree_state(project_root)
    if git_state == "untrusted":
        return "No se observaron cambios de archivos: git no confía en esta carpeta (dubious ownership)"
    if git_state != "inside":
        return "No se observaron cambios de archivos: la carpeta no es un repositorio git"
    return (
        "No se observaron cambios de archivos: git funciona pero el run no cambió ningún archivo "
        "del proyecto (fuera de .rapid-os/ y de artefactos de herramientas)"
    )


def stdin_is_windows_nul() -> bool:
    """True when stdin is the Windows NUL device, which reports `isatty() == True`.

    A console is the only character device where `GetConsoleMode` succeeds, so a character
    device that fails it is NUL: no person is there to confirm, and the TTY check must say so
    before the ledger is touched. False everywhere else and whenever it cannot be told.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        import msvcrt

        file_type_char = 2
        handle = ctypes.c_void_p(msvcrt.get_osfhandle(sys.stdin.fileno()))
        kernel32 = ctypes.windll.kernel32
        if kernel32.GetFileType(handle) != file_type_char:
            return False
        return not kernel32.GetConsoleMode(handle, ctypes.byref(ctypes.c_uint32()))
    except Exception:
        return False


def execute_approve(
    project_root: Path,
    project_rapid_dir: Path,
    gate_id: str | None = None,
    *,
    reviewer: str | None = None,
    reject: bool = False,
    waive: bool = False,
    reason: str | None = None,
    is_tty: bool | None = None,
    input_func: Any = None,
    environ: dict[str, str] | None = None,
    ancestry: AncestryResult | None = None,
) -> tuple[int, str]:
    """Execute porcelain `rapid approve` workflow.

    Without `gate_id` it lists the pending human gates (read-only). With a gate it approves,
    waives (`waive`, waivable gates only) or rejects it (`reject`: review outcome
    `changes_requested`, which leaves the gate FAIL for the rest of the run).
    """
    if reject and waive:
        return 1, "RAPID1330 '--reject' and '--waive' cannot be combined."
    if (reject or waive) and not gate_id:
        return 1, "RAPID1330 '--reject' and '--waive' require a gate id (see 'rapid approve')."
    if reject and (not reason or not str(reason).strip()):
        return 1, "RAPID1333 Reason is required (--reason) when rejecting a gate approval."
    if waive and (not reason or not str(reason).strip()):
        return 1, "RAPID1333 A non-empty '--reason' is required when waiving a gate."

    if environ is not None:
        env_map = environ
    else:
        import os

        env_map = dict(os.environ)

    if not gate_id:
        # Read-only listing: needs neither a TTY nor to be outside an agent session.
        return _list_pending_human_gates(project_rapid_dir, project_root)

    if env_map.get("CLAUDE_CODE_CHILD_SESSION") == "1":
        return (
            1,
            "RAPID1310 Human gate approval cannot be run inside Claude Code agent session (CLAUDE_CODE_CHILD_SESSION=1). La aprobación debe hacerla una persona en su propia terminal.",
        )

    # An agent harness among the ancestors means an agent (or a script it spawned) is asking, even
    # if it dropped the session variables and found a pty. Unreadable ancestry never rejects.
    agent = find_agent_ancestor(ancestry if ancestry is not None else read_ancestry())
    if agent is not None:
        return (
            1,
            f"RAPID1310 Human gate approval cannot be run under an agent harness (ancestor process "
            f"'{agent.ancestor.name}', pid {agent.ancestor.pid}, {agent.harness}). "
            "La aprobación debe hacerla una persona en su propia terminal.",
        )

    # TTY check comes before touching the ledger so every mutating case fails the same way.
    tty_active = (sys.stdin.isatty() and not stdin_is_windows_nul()) if is_tty is None else is_tty
    if not tty_active:
        return (
            1,
            "RAPID1310 Human gate approval requires interactive terminal confirmation (TTY). Stdin is not a TTY.",
        )
    raw_input_func = input_func if input_func is not None else input
    no_terminal = (
        "RAPID1310 Human gate approval requires interactive terminal confirmation (TTY). "
        "Stdin was closed before the answer (EOF)."
    )

    def ask_input(prompt: str) -> str | None:
        # On Windows a stdin redirected to NUL reports isatty() == True; EOF means no terminal.
        try:
            return raw_input_func(prompt)
        except EOFError:
            return None

    sess = load_session(project_rapid_dir)
    if not sess or not sess.active_run_id:
        return 1, "RAPID1307 No active run session found (.rapid-os/session.json)."

    run_id = sess.active_run_id
    run_reg = RunRegistry(project_root, project_rapid_dir)
    evidence_reg = EvidenceRegistry(project_root, project_rapid_dir)

    contract = run_reg.get_contract(run_id)
    current_state = run_reg.get_state(run_id)

    gate = next((g for g in contract.gates if g.id == gate_id), None)
    if not gate:
        return 1, f"RAPID1332 Gate '{gate_id}' not found in contract."

    gate_st = next((g for g in current_state.gates if g.id == gate_id), None)
    if not gate_st:
        return 1, f"RAPID1332 Gate '{gate_id}' not found in state."

    if gate.kind not in HUMAN_GATE_KINDS:
        return 1, f"RAPID1332 Gate '{gate_id}' is a machine gate ({gate.kind.value}); manual approval is only for human review gates."

    if gate_st.disposition != GateDisposition.PENDING:
        return 1, f"RAPID1332 Gate '{gate_id}' is already {gate_st.disposition.value}; nothing to do."

    if gate_id in _rejected_human_gate_ids(contract, evidence_reg.list(run_id)):
        return (
            1,
            f"RAPID1332 Gate '{gate_id}' was rejected (changes_requested) and stays FAIL for this run. "
            "Run 'rapid abort' and start a new run.",
        )

    if waive:
        try:
            validate_gate_transition(
                gate_st.disposition,
                GateDisposition.WAIVED,
                waivable=gate_st.waivable,
                reason=reason or "",
            )
        except InvalidGateTransitionError as exc:
            return 1, f"RAPID1333 {exc}"

    if not reject:
        # Approve/waive modify the gate: refuse early, before writing review evidence, when the
        # run is not active or tasks are still open.
        try:
            enforce_gate_transition_preconditions(current_state, gate_st)
        except ExecutionError as exc:
            message = f"{exc.code} {exc}"
            # RAPID1014 names the open tasks for machines; add the sentence a person can act on.
            for task in current_state.tasks:
                if task.status.value == "in_progress":
                    message += (
                        f"\n{task.id} sigue en curso; espera a que el agente ejecute "
                        f"`rapid task done {task.id}`."
                    )
            return 1, message

    reviewer_name = reviewer.strip() if reviewer and reviewer.strip() else None
    if reviewer_name is None:
        reviewer_name = _git_user_name(project_root)
    if reviewer_name is None:
        answer = ask_input("Reviewer name (git config user.name is not set): ")
        if answer is None:
            return 1, no_terminal
        reviewer_name = answer.strip()
    if not reviewer_name:
        return 1, "RAPID1331 A reviewer name is required: pass --reviewer or set 'git config user.name'."

    if waive:
        expected_confirm = f"dispensar {gate_id}"
        accepted = {expected_confirm}
    elif reject:
        expected_confirm = f"aprobar {gate_id}"
        accepted = {expected_confirm, f"rechazar {gate_id}"}
    else:
        expected_confirm = f"aprobar {gate_id}"
        accepted = {expected_confirm}
    answer = ask_input(f"Escribe '{expected_confirm}' para confirmar la acción sobre el gate: ")
    if answer is None:
        return 1, no_terminal
    typed = answer.strip()
    if typed not in accepted:
        return 1, f"Confirmación abortada (se esperaba '{expected_confirm}')."

    if waive:
        try:
            run_reg.transition_gate(
                run_id,
                gate_id,
                GateDisposition.WAIVED,
                reason=f"{reason} (waived by {reviewer_name})",
            )
        except ExecutionError as exc:
            return 1, f"{exc.code} {exc}"
        return 0, f"Gate '{gate_id}' dispensado (waived)."

    review_type = REVIEW_GATE_KIND_TO_REVIEW_TYPE.get(gate.kind, "manual")
    outcome = "changes_requested" if reject else "approved"
    summary = f"Gate {gate_id} {outcome} by {reviewer_name}"
    if reject:
        summary = f"{summary}: {str(reason).strip()}"

    evidence_reg.add(
        run_id,
        {
            "kind": EvidenceKind.REVIEW.value,
            "producer": "user",
            "summary": summary,
            "state_revision": current_state.revision,
            "task_ids": [],
            "gate_ids": [gate_id],
            "capability_ids": [],
            "payload": {
                "review_type": review_type,
                "outcome": outcome,
                "reviewer": reviewer_name,
            },
            "artifacts": [],
        },
        base_dir=project_root,
    )

    if reject:
        return 0, f"Gate '{gate_id}' rechazado (changes_requested). Ejecuta 'rapid abort' e inicia un run nuevo."

    try:
        run_reg.transition_gate(
            run_id,
            gate_id,
            GateDisposition.ACKNOWLEDGED,
            reason=reason or f"Approved by {reviewer_name}",
        )
    except ExecutionError as exc:
        return 1, f"{exc.code} {exc}"
    return 0, f"Gate '{gate_id}' aprobado y reconocido."


def execute_attach(
    project_root: Path,
    project_rapid_dir: Path,
    path: str,
    label: str,
    task_id: str | None = None,
) -> tuple[int, str]:
    """Execute porcelain `rapid attach`: record a file as `artifact` evidence (producer rapid:attach).

    The evidence is linked to `task_id`, or to the only in_progress task when omitted, so it
    backs the task assertion (research spikes have no mandatory tests).
    """
    sess = load_session(project_rapid_dir)
    if not sess or not sess.active_run_id:
        return 1, "RAPID1307 No active run session found (.rapid-os/session.json)."
    if not label or not str(label).strip():
        return 1, "RAPID1336 A non-empty '--label' is required to attach an artifact."

    roots = [Path(project_root).resolve()]
    if sess.workspace_path:
        roots.append(Path(sess.workspace_path).resolve())

    candidate = Path(path)
    candidates = [candidate] if candidate.is_absolute() else [r / candidate for r in roots]
    source = next((c.resolve() for c in candidates if c.is_file()), None)
    if source is None:
        return 1, f"RAPID1336 File to attach not found: '{path}'."

    base_dir = next((r for r in roots if source.is_relative_to(r)), None)
    if base_dir is None:
        return 1, f"RAPID1336 File to attach must live inside the project or the run workspace: '{path}'."
    relative = source.relative_to(base_dir).as_posix()
    if relative.startswith(".rapid-os/"):
        return 1, "RAPID1336 Files under .rapid-os/ cannot be attached."

    run_id = sess.active_run_id
    run_reg = RunRegistry(project_root, project_rapid_dir)
    evidence_reg = EvidenceRegistry(project_root, project_rapid_dir)
    try:
        state = run_reg.get_state(run_id)
        linked_tasks: list[str] = []
        if task_id:
            if not any(t.id == task_id for t in state.tasks):
                return 1, f"RAPID1336 Task '{task_id}' not found in run '{run_id}'."
            linked_tasks = [task_id]
        else:
            in_progress = [t.id for t in state.tasks if t.status == TaskStatus.IN_PROGRESS]
            if len(in_progress) == 1:
                linked_tasks = in_progress
        evidence = evidence_reg.add(
            run_id,
            {
                "kind": EvidenceKind.ARTIFACT.value,
                "producer": "rapid:attach",
                "summary": f"Attached {relative}: {str(label).strip()}",
                "state_revision": state.revision,
                "task_ids": linked_tasks,
                "gate_ids": [],
                "capability_ids": [],
                "payload": {"label": str(label).strip()},
                "artifacts": [relative],
            },
            base_dir=base_dir,
        )
    except Exception as exc:
        return 1, f"RAPID1336 Could not attach '{relative}': {exc}"
    suffix = f" (task {linked_tasks[0]})" if linked_tasks else ""
    return 0, f"Attached '{relative}' as evidence {evidence.id}{suffix}."


def execute_abort(
    project_root: Path,
    project_rapid_dir: Path,
    *,
    reason: str | None = None,
) -> tuple[int, str]:
    """Execute porcelain `rapid abort` workflow."""
    sess = load_session(project_rapid_dir)
    if not sess or not sess.active_run_id:
        return 1, "RAPID1307 No active run session found (.rapid-os/session.json)."

    run_id = sess.active_run_id
    run_reg = RunRegistry(project_root, project_rapid_dir)
    try:
        current_state = run_reg.get_state(run_id)
        if not current_state.status.is_terminal:
            run_reg.transition_status(
                run_id,
                RunStatus.CANCELLED,
                reason=reason or "Aborted by rapid abort",
            )
    except Exception as exc:
        clear_session(project_rapid_dir)
        return 1, f"Error aborting run '{run_id}': {exc}"

    clear_session(project_rapid_dir)
    message = f"Run '{run_id}' cancelado y sesión limpiada."
    if sess.workspace_path:
        message += (
            f" El worktree '{sess.workspace_path}' (rama rapid/{run_id}) se conserva; "
            "elimínalo con 'git worktree remove' cuando ya no lo necesites."
        )
    return 0, message

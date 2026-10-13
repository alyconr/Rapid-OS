"""Porcelain lifecycle operations for Rapid OS intent layer (start, finish, approve, abort).

Encapsulates state orchestration, evidence recording, and eval integration
using domain models and registries without direct CLI dependence.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

from rapid_os.adapters.eval_registry import EvalRegistry
from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.project_snapshot import resolve_project_snapshot_path, write_project_snapshot
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.core.config import load_project_config
from rapid_os.core.harness_detect import detect_harness
from rapid_os.domain.evals import (
    BehavioralEvaluator,
    EvaluationVerdict,
    REVIEW_GATE_KIND_TO_REVIEW_TYPE,
)
from rapid_os.domain.evidence import EvidenceKind
from rapid_os.domain.execution import (
    GateDisposition,
    GateKind,
    RunStatus,
    TaskStatus,
    WorkspaceRequirement,
)
from rapid_os.domain.scanner import build_project_model
from rapid_os.orchestration.actions import ActionKind, NextAction
from rapid_os.orchestration.check import run_check
from rapid_os.orchestration.conductor import (
    HUMAN_GATE_KINDS,
    gate_satisfied,
    next_action,
    next_action_without_run,
)
from rapid_os.orchestration.playbooks import load_playbook
from rapid_os.orchestration.session import (
    Session,
    clear_session,
    load_session,
    resolve_git_head,
    save_session,
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

            created_spec = spec_reg.create(**spec_fields)
            ready_spec = spec_reg.set_status(created_spec.id, "ready")
            resolved_spec_id = ready_spec.id
        else:
            # Neither --spec nor --spec-file: do NOT create anything, return author_spec
            action = next_action_without_run(mode, playbook)
            return 0, action

        # 1.e Run creation
        cfg = config_file or (project_rapid_dir / "config.json")
        project_cfg = load_project_config(cfg)
        env_map = environ if environ is not None else dict(sys.modules["os"].environ)
        detection = detect_harness(harness, env_map, project_cfg)

        record = run_reg.create(
            spec_id=resolved_spec_id,
            harness=detection.harness_id,
        )
        active_run_id = record.id
        contract = run_reg.get_contract(active_run_id)
        current_state = run_reg.get_state(active_run_id)

    # Session object creation
    if resume and existing_session and existing_session.start_head:
        start_head = existing_session.start_head
    else:
        start_head = resolve_git_head(project_root)

    sess = Session(
        active_run_id=active_run_id,
        mode=mode,
        harness=contract.harness,
        start_head=start_head,
    )
    save_session(project_rapid_dir, sess)

    evidence_reg = EvidenceRegistry(project_root, project_rapid_dir)

    # 1.f Workspace declaration
    if contract.workspace == WorkspaceRequirement.ISOLATED_REQUIRED:
        action = NextAction(
            schema_version=1,
            run_id=active_run_id,
            mode=mode,
            kind=ActionKind.BLOCKED,
            instructions=(
                "Execution contract requires an isolated workspace (worktree). "
                "Workspace isolation must be established before execution."
            ),
            command=None,
            after=None,
            awaiting_human=(),
            missing=("gate.workspace-isolation",),
            tasks_done=0,
            tasks_total=len(contract.tasks),
            outcome=None,
        )
        return 0, action

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
    )
    return 0, action


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
        action = next_action_without_run(mode, playbook)
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
        action = next_action_without_run(mode, playbook)
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
    )
    return 0, action


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

    # 3.a Record file_change evidence from git
    start_head = sess.start_head
    changed_files: list[str] = []
    if start_head:
        try:
            p_diff = subprocess.run(
                ["git", "diff", "--name-only", start_head],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                check=False,
            )
            p_untracked = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                check=False,
            )
            raw_lines = p_diff.stdout.splitlines() + p_untracked.stdout.splitlines()
            for r in raw_lines:
                r_clean = r.strip().replace("\\", "/")
                if r_clean and not r_clean.startswith(".rapid-os/"):
                    if r_clean not in changed_files:
                        changed_files.append(r_clean)
        except Exception:
            pass

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
        return 0, action

    # 3.d Transition to finished and evaluate
    finished_state = run_reg.transition_status(
        run_id,
        RunStatus.FINISHED,
        reason="Run successfully finished by rapid finish",
    )
    report = eval_reg.evaluate_run(run_id, write=True)

    exit_code = 0 if report.verdict in (EvaluationVerdict.PASS, EvaluationVerdict.PASS_WITH_WAIVERS) else 1
    return exit_code, report


def execute_approve(
    project_root: Path,
    project_rapid_dir: Path,
    gate_id: str,
    *,
    reviewer: str | None = None,
    reject: bool = False,
    reason: str | None = None,
    is_tty: bool | None = None,
    input_func: Any = None,
    environ: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Execute porcelain `rapid approve` workflow."""
    if reject and (not reason or not str(reason).strip()):
        return 1, "Reason is required (--reason) when rejecting a gate approval."

    env_map = environ if environ is not None else dict(sys.modules.get("os", {}).environ if "os" in sys.modules else {})
    if not env_map:
        import os
        env_map = dict(os.environ)

    if env_map.get("CLAUDE_CODE_CHILD_SESSION") == "1":
        return (
            1,
            "RAPID1310 Human gate approval cannot be run inside Claude Code agent session (CLAUDE_CODE_CHILD_SESSION=1). La aprobación debe hacerla una persona en su propia terminal.",
        )

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
        return 1, f"Gate '{gate_id}' not found in contract."

    gate_st = next((g for g in current_state.gates if g.id == gate_id), None)
    if not gate_st:
        return 1, f"Gate '{gate_id}' not found in state."

    if gate.kind not in HUMAN_GATE_KINDS:
        return 1, f"Gate '{gate_id}' is a machine gate ({gate.kind.value}); manual approval is only for human review gates."

    # TTY check
    tty_active = sys.stdin.isatty() if is_tty is None else is_tty
    if not tty_active:
        return (
            1,
            f"RAPID1310 Human gate approval requires interactive terminal confirmation (TTY). Stdin is not a TTY.",
        )

    ask_input = input_func if input_func is not None else input
    expected_confirm = f"aprobar {gate_id}"
    typed = ask_input(f"Escribe '{expected_confirm}' para confirmar la acción sobre el gate: ").strip()
    if typed != expected_confirm and not (reject and typed == f"rechazar {gate_id}"):
        return 1, f"Confirmación abortada (se esperaba '{expected_confirm}')."

    review_type = REVIEW_GATE_KIND_TO_REVIEW_TYPE.get(gate.kind, "manual")
    outcome = "rejected" if reject else "approved"
    reviewer_name = reviewer.strip() if reviewer else "user"

    evidence_reg.add(
        run_id,
        {
            "kind": EvidenceKind.REVIEW.value,
            "producer": "user",
            "summary": f"Gate {gate_id} {outcome} by {reviewer_name}",
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

    disp = GateDisposition.ACKNOWLEDGED if not reject else GateDisposition.PENDING
    if not reject:
        run_reg.transition_gate(
            run_id,
            gate_id,
            disp,
            reason=reason or f"Approved by {reviewer_name}",
        )
        return 0, f"Gate '{gate_id}' aprobado y reconocido."
    else:
        return 0, f"Gate '{gate_id}' rechazado."


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
    return 0, f"Run '{run_id}' cancelado y sesión limpiada."

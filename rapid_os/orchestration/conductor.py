from dataclasses import replace
from typing import Iterable, Sequence

from rapid_os.domain.evals import (
    BehavioralEvaluator,
    EvalAssertionStatus,
    EvaluationReport,
)
from rapid_os.domain.evidence import RunEvidence
from rapid_os.domain.execution import (
    ExecutionContract,
    GateDisposition,
    GateKind,
    RunState,
    RunStatus,
    TaskStatus,
)
from rapid_os.orchestration.actions import ActionKind, NextAction
from rapid_os.orchestration.playbooks import Playbook

HUMAN_GATE_KINDS = frozenset(
    {
        GateKind.PEER_REVIEW,
        GateKind.SECURITY_REVIEW,
        GateKind.MIGRATION_REVIEW,
        GateKind.MANUAL_APPROVAL,
        GateKind.FINAL_VERIFICATION,
    }
)

MACHINE_GATE_KINDS = frozenset(
    {
        GateKind.BASELINE_CHECK,
        GateKind.IMPLEMENTATION_TESTS,
        GateKind.WORKSPACE_ISOLATION,
    }
)


def gate_satisfied(
    contract: ExecutionContract,
    state: RunState,
    evidence: Iterable[RunEvidence],
    gate_id: str,
    *,
    evaluator: BehavioralEvaluator,
) -> bool:
    """Hypothetically evaluate whether `gate_id` achieves a PASS assertion if acknowledged."""
    raw_evidence = tuple(evidence)
    gate_state = next((g for g in state.gates if g.id == gate_id), None)
    if not gate_state:
        return False

    hypothetical_gate = replace(gate_state, disposition=GateDisposition.ACKNOWLEDGED)
    hypothetical_gates = tuple(
        hypothetical_gate if g.id == gate_id else g for g in state.gates
    )
    hypothetical_state = replace(
        state,
        gates=hypothetical_gates,
        content_digest="",
    )

    hypothetical_report = evaluator.evaluate(
        contract, hypothetical_state, raw_evidence
    )
    for assertion in hypothetical_report.assertions:
        if assertion.category == "gate" and assertion.subject_id == gate_id:
            return assertion.status == EvalAssertionStatus.PASS
    return False


def next_action_without_run(mode: str, playbook: Playbook) -> NextAction:
    """Return initial `author_spec` action when no active run exists."""
    return NextAction(
        schema_version=1,
        run_id=None,
        mode=mode,
        kind=ActionKind.AUTHOR_SPEC,
        instructions=playbook.get_instruction(ActionKind.AUTHOR_SPEC),
        command=None,
        after=None,
        awaiting_human=(),
        missing=(),
        tasks_done=0,
        tasks_total=0,
        outcome=None,
    )


def next_action(
    contract: ExecutionContract,
    state: RunState,
    evidence: Iterable[RunEvidence],
    playbook: Playbook,
    *,
    evaluator: BehavioralEvaluator,
    test_command: Sequence[str] | None = None,
) -> NextAction:
    """Determine deterministically the next action for a run using pure domain evaluation."""
    raw_evidence = tuple(evidence)
    gate_by_id = {g.id: g for g in contract.gates}
    state_gate_by_id = {g.id: g for g in state.gates}

    pending_human_ids = tuple(
        sorted(
            [
                g.id
                for g in state.gates
                if gate_by_id.get(g.id)
                and gate_by_id[g.id].kind in HUMAN_GATE_KINDS
                and g.disposition == GateDisposition.PENDING
            ]
        )
    )

    tasks_total = len(contract.tasks)
    tasks_done = sum(
        1 for t in state.tasks if t.status in (TaskStatus.DONE, TaskStatus.SKIPPED)
    )
    mode = getattr(contract, "mode", None) or playbook.mode

    # Evaluate in memory
    report = evaluator.evaluate(contract, state, raw_evidence)
    missing = tuple(
        sorted(
            [
                a.id
                for a in report.assertions
                if a.status in (EvalAssertionStatus.UNVERIFIED, EvalAssertionStatus.FAIL)
            ]
        )
    )

    # a. RunStatus terminal -> done
    if state.status.is_terminal:
        if state.status == RunStatus.CANCELLED:
            outcome = "cancelled"
            missing_terminal = ()
        elif state.status == RunStatus.FAILED:
            outcome = "failed"
            missing_terminal = ()
        else:  # FINISHED
            outcome = report.verdict.value
            missing_terminal = missing

        return NextAction(
            schema_version=1,
            run_id=contract.run_id,
            mode=mode,
            kind=ActionKind.DONE,
            instructions=playbook.get_instruction(ActionKind.DONE),
            command=None,
            after=None,
            awaiting_human=pending_human_ids,
            missing=missing_terminal,
            tasks_done=tasks_done,
            tasks_total=tasks_total,
            outcome=outcome,
        )

    # b. RunStatus blocked -> blocked
    if state.status == RunStatus.BLOCKED:
        return NextAction(
            schema_version=1,
            run_id=contract.run_id,
            mode=mode,
            kind=ActionKind.BLOCKED,
            instructions=state.reason or playbook.get_instruction(ActionKind.BLOCKED),
            command=None,
            after=None,
            awaiting_human=pending_human_ids,
            missing=missing,
            tasks_done=tasks_done,
            tasks_total=tasks_total,
            outcome=None,
        )

    # c. prepared con gate.baseline
    if state.status == RunStatus.PREPARED:
        baseline_gate = next(
            (
                g
                for g in contract.gates
                if g.kind == GateKind.BASELINE_CHECK or g.id == "gate.baseline"
            ),
            None,
        )
        baseline_state = (
            state_gate_by_id.get(baseline_gate.id) if baseline_gate else None
        )

        if baseline_gate and baseline_state:
            if baseline_state.disposition == GateDisposition.PENDING:
                if gate_satisfied(
                    contract,
                    state,
                    raw_evidence,
                    baseline_gate.id,
                    evaluator=evaluator,
                ):
                    return NextAction(
                        schema_version=1,
                        run_id=contract.run_id,
                        mode=mode,
                        kind=ActionKind.ACTIVATE,
                        instructions=playbook.get_instruction(ActionKind.ACTIVATE),
                        command=("rapid", "start", "--resume"),
                        after=None,
                        awaiting_human=pending_human_ids,
                        missing=missing,
                        tasks_done=tasks_done,
                        tasks_total=tasks_total,
                        outcome=None,
                    )
                else:
                    if test_command:
                        cmd = ("rapid", "check", "--gate", baseline_gate.id, "--", *test_command)
                        instr = playbook.get_instruction(ActionKind.RUN_BASELINE)
                    else:
                        cmd = None
                        instr = (
                            f"{playbook.get_instruction(ActionKind.RUN_BASELINE)} "
                            "No test_command configured (RAPID1301). Please configure test_command in .rapid-os/config.json or pass --test-command."
                        )
                    return NextAction(
                        schema_version=1,
                        run_id=contract.run_id,
                        mode=mode,
                        kind=ActionKind.RUN_BASELINE,
                        gate_ids=(baseline_gate.id,),
                        instructions=instr,
                        command=cmd,
                        after=None,
                        awaiting_human=pending_human_ids,
                        missing=missing,
                        tasks_done=tasks_done,
                        tasks_total=tasks_total,
                        outcome=None,
                    )
            else:
                # baseline disposition already acknowledged or waived
                return NextAction(
                    schema_version=1,
                    run_id=contract.run_id,
                    mode=mode,
                    kind=ActionKind.ACTIVATE,
                    instructions=playbook.get_instruction(ActionKind.ACTIVATE),
                    command=("rapid", "start", "--resume"),
                    after=None,
                    awaiting_human=pending_human_ids,
                    missing=missing,
                    tasks_done=tasks_done,
                    tasks_total=tasks_total,
                    outcome=None,
                )
        else:
            # No baseline gate required
            return NextAction(
                schema_version=1,
                run_id=contract.run_id,
                mode=mode,
                kind=ActionKind.ACTIVATE,
                instructions=playbook.get_instruction(ActionKind.ACTIVATE),
                command=("rapid", "start", "--resume"),
                after=None,
                awaiting_human=pending_human_ids,
                missing=missing,
                tasks_done=tasks_done,
                tasks_total=tasks_total,
                outcome=None,
            )

    # d. active con tareas no terminales
    non_terminal_tasks = [t for t in state.tasks if not t.status.is_terminal]
    if state.status == RunStatus.ACTIVE and non_terminal_tasks:
        blocked_task = next(
            (t for t in state.tasks if t.status == TaskStatus.BLOCKED), None
        )
        if blocked_task:
            return NextAction(
                schema_version=1,
                run_id=contract.run_id,
                mode=mode,
                kind=ActionKind.BLOCKED,
                task_id=blocked_task.id,
                instructions=f"Task {blocked_task.id} is blocked: {blocked_task.reason or playbook.get_instruction(ActionKind.BLOCKED)}",
                command=None,
                after=None,
                awaiting_human=pending_human_ids,
                missing=missing,
                tasks_done=tasks_done,
                tasks_total=tasks_total,
                outcome=None,
            )

        in_prog = next(
            (t for t in state.tasks if t.status == TaskStatus.IN_PROGRESS), None
        )
        pending = next((t for t in state.tasks if t.status == TaskStatus.PENDING), None)
        target_task = in_prog if in_prog is not None else pending

        if target_task is not None:
            cmd = (
                ("rapid", "task", "start", target_task.id)
                if target_task.status == TaskStatus.PENDING
                else None
            )
            after = ("rapid", "task", "done", target_task.id)
            return NextAction(
                schema_version=1,
                run_id=contract.run_id,
                mode=mode,
                kind=ActionKind.IMPLEMENT_TASK,
                task_id=target_task.id,
                instructions=playbook.get_instruction(ActionKind.IMPLEMENT_TASK),
                command=cmd,
                after=after,
                awaiting_human=pending_human_ids,
                missing=missing,
                tasks_done=tasks_done,
                tasks_total=tasks_total,
                outcome=None,
            )

    # e. Todas las tareas terminales:
    # 1) Aserción FAIL -> blocked con la razón
    fail_assertion = next(
        (a for a in report.assertions if a.status == EvalAssertionStatus.FAIL), None
    )
    if fail_assertion is not None:
        return NextAction(
            schema_version=1,
            run_id=contract.run_id,
            mode=mode,
            kind=ActionKind.BLOCKED,
            instructions=fail_assertion.reason
            or playbook.get_instruction(ActionKind.BLOCKED),
            command=None,
            after=None,
            awaiting_human=pending_human_ids,
            missing=missing,
            tasks_done=tasks_done,
            tasks_total=tasks_total,
            outcome=None,
        )

    # 2) Tarea con aserción UNVERIFIED -> verify con ["rapid", "check", "--task", "T00N", "--", *test_command]
    unverified_task_assertion = next(
        (
            a
            for a in report.assertions
            if a.status == EvalAssertionStatus.UNVERIFIED and a.category == "task"
        ),
        None,
    )
    if unverified_task_assertion is not None:
        target_task_id = unverified_task_assertion.subject_id
        if test_command:
            cmd = ("rapid", "check", "--task", target_task_id, "--", *test_command)
            instr = playbook.get_instruction(ActionKind.VERIFY)
        else:
            cmd = None
            instr = (
                f"{playbook.get_instruction(ActionKind.VERIFY)} "
                "No test_command configured (RAPID1301). Please configure test_command in .rapid-os/config.json or pass --test-command."
            )
        return NextAction(
            schema_version=1,
            run_id=contract.run_id,
            mode=mode,
            kind=ActionKind.VERIFY,
            task_id=target_task_id,
            instructions=instr,
            command=cmd,
            after=None,
            awaiting_human=pending_human_ids,
            missing=missing,
            tasks_done=tasks_done,
            tasks_total=tasks_total,
            outcome=None,
        )

    # 3) Gate de máquina pendiente que NO cumple gate_satisfied -> verify con su comando
    pending_machine_gates = [
        g
        for g in state.gates
        if gate_by_id.get(g.id)
        and gate_by_id[g.id].kind in MACHINE_GATE_KINDS
        and g.disposition == GateDisposition.PENDING
    ]
    unsatisfied_machine_gates = [
        g
        for g in pending_machine_gates
        if not gate_satisfied(
            contract, state, raw_evidence, g.id, evaluator=evaluator
        )
    ]
    if unsatisfied_machine_gates:
        first_mg = unsatisfied_machine_gates[0]
        gate_kind = gate_by_id[first_mg.id].kind
        if gate_kind in (GateKind.BASELINE_CHECK, GateKind.IMPLEMENTATION_TESTS):
            if test_command:
                cmd = ("rapid", "check", "--gate", first_mg.id, "--", *test_command)
                instr = playbook.get_instruction(ActionKind.VERIFY)
            else:
                cmd = None
                instr = (
                    f"{playbook.get_instruction(ActionKind.VERIFY)} "
                    "No test_command configured (RAPID1301). Please configure test_command in .rapid-os/config.json or pass --test-command."
                )
        else:
            cmd = ("rapid", "check", "--gate", first_mg.id)
            instr = playbook.get_instruction(ActionKind.VERIFY)

        return NextAction(
            schema_version=1,
            run_id=contract.run_id,
            mode=mode,
            kind=ActionKind.VERIFY,
            gate_ids=tuple(g.id for g in unsatisfied_machine_gates),
            instructions=instr,
            command=cmd,
            after=None,
            awaiting_human=pending_human_ids,
            missing=missing,
            tasks_done=tasks_done,
            tasks_total=tasks_total,
            outcome=None,
        )

    # 4) Capacidad UNVERIFIED: repository.write no cuenta (la registra finish);
    #    workspace.* -> blocked con la razón (la registra start); cualquier otra -> verify.
    unverified_caps = [
        a
        for a in report.assertions
        if a.status == EvalAssertionStatus.UNVERIFIED
        and a.category == "capability"
        and a.subject_id != "repository.write"
    ]
    if unverified_caps:
        workspace_cap = next(
            (c for c in unverified_caps if c.subject_id.startswith("workspace.")),
            None,
        )
        if workspace_cap is not None:
            return NextAction(
                schema_version=1,
                run_id=contract.run_id,
                mode=mode,
                kind=ActionKind.BLOCKED,
                instructions=workspace_cap.reason
                or playbook.get_instruction(ActionKind.BLOCKED),
                command=None,
                after=None,
                awaiting_human=pending_human_ids,
                missing=missing,
                tasks_done=tasks_done,
                tasks_total=tasks_total,
                outcome=None,
            )

        first_cap = unverified_caps[0]
        if first_cap.subject_id == "tests.execute":
            if test_command:
                cmd = ("rapid", "check", "--capability", first_cap.subject_id, "--", *test_command)
                instr = playbook.get_instruction(ActionKind.VERIFY)
            else:
                cmd = None
                instr = (
                    f"{playbook.get_instruction(ActionKind.VERIFY)} "
                    "No test_command configured (RAPID1301). Please configure test_command in .rapid-os/config.json or pass --test-command."
                )
        else:
            cmd = ("rapid", "check", "--capability", first_cap.subject_id)
            instr = playbook.get_instruction(ActionKind.VERIFY)

        return NextAction(
            schema_version=1,
            run_id=contract.run_id,
            mode=mode,
            kind=ActionKind.VERIFY,
            instructions=instr,
            command=cmd,
            after=None,
            awaiting_human=pending_human_ids,
            missing=missing,
            tasks_done=tasks_done,
            tasks_total=tasks_total,
            outcome=None,
        )

    # f. Gates humanos pendientes -> await_human_approval
    if pending_human_ids:
        return NextAction(
            schema_version=1,
            run_id=contract.run_id,
            mode=mode,
            kind=ActionKind.AWAIT_HUMAN_APPROVAL,
            gate_ids=pending_human_ids,
            instructions=playbook.get_instruction(ActionKind.AWAIT_HUMAN_APPROVAL),
            command=None,
            after=None,
            awaiting_human=pending_human_ids,
            missing=missing,
            tasks_done=tasks_done,
            tasks_total=tasks_total,
            outcome=None,
        )

    # g. Todo resuelto -> finish
    return NextAction(
        schema_version=1,
        run_id=contract.run_id,
        mode=mode,
        kind=ActionKind.FINISH,
        instructions=playbook.get_instruction(ActionKind.FINISH),
        command=("rapid", "finish"),
        after=None,
        awaiting_human=pending_human_ids,
        missing=missing,
        tasks_done=tasks_done,
        tasks_total=tasks_total,
        outcome=None,
    )

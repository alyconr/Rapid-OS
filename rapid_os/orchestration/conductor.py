from dataclasses import replace
from typing import Iterable, Sequence

from rapid_os.domain.evals import (
    BehavioralEvaluator,
    EvalAssertionStatus,
    EvaluationReport,
)
from rapid_os.domain.evidence import EvidenceKind, RunEvidence
from rapid_os.domain.execution import (
    TEST_COMMAND_FIX,
    ExecutionContract,
    GateDisposition,
    GateKind,
    RunState,
    RunStatus,
    TaskStatus,
    WorkspaceRequirement,
)
from rapid_os.orchestration.actions import ActionKind, NextAction
from rapid_os.orchestration.playbooks import Playbook

NO_TEST_COMMAND_NOTICE = f"No test_command configured (RAPID1301). {TEST_COMMAND_FIX}."


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
        GateKind.ARCHITECTURE_CHECK,
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


REJECTING_REVIEW_OUTCOMES = frozenset({"changes_requested", "rejected"})


def _rejected_human_gate_ids(
    contract: ExecutionContract, evidence: Sequence[RunEvidence]
) -> tuple[str, ...]:
    """Human gates with a rejecting review: their assertion is FAIL for the rest of the run."""
    gate_by_id = {g.id: g for g in contract.gates}
    rejected: list[str] = []
    for ev in evidence:
        if ev.kind != EvidenceKind.REVIEW:
            continue
        if str(ev.payload.get("outcome")) not in REJECTING_REVIEW_OUTCOMES:
            continue
        for gate_id in ev.gate_ids:
            gate = gate_by_id.get(gate_id)
            if gate and gate.kind in HUMAN_GATE_KINDS and gate_id not in rejected:
                rejected.append(gate_id)
    return tuple(sorted(rejected))


def _refactor_regression(
    contract: ExecutionContract, evidence: Sequence[RunEvidence]
) -> tuple[int, int] | None:
    """Return (baseline_passed, latest_passed) when the latest tests pass fewer than the baseline."""
    baseline_gate = next(
        (g for g in contract.gates if g.kind == GateKind.BASELINE_CHECK or g.id == "gate.baseline"),
        None,
    )
    if baseline_gate is None:
        return None
    real_tests = [
        ev
        for ev in evidence
        if ev.kind == EvidenceKind.TEST_RESULT and ev.payload.get("expectation") != "fail"
    ]
    baselines = [ev for ev in real_tests if baseline_gate.id in ev.gate_ids]
    if not baselines or not real_tests:
        return None
    baseline_passed = int(baselines[0].payload["passed"])
    latest_passed = int(real_tests[-1].payload["passed"])
    if latest_passed < baseline_passed:
        return baseline_passed, latest_passed
    return None


def next_action_without_run(
    mode: str, playbook: Playbook, seed: dict[str, object] | None = None
) -> NextAction:
    """Return initial `author_spec` action when no active run exists.

    `seed` (optional) carries the open stories of the product brief; without it the action is
    exactly what it always was.
    """
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
        spec_template=dict(playbook.spec_template) if playbook.spec_template else None,
        seed=dict(seed) if seed else None,
    )


def next_action(
    contract: ExecutionContract,
    state: RunState,
    evidence: Iterable[RunEvidence],
    playbook: Playbook,
    *,
    evaluator: BehavioralEvaluator,
    test_command: Sequence[str] | None = None,
    workspace_ready: bool = True,
) -> NextAction:
    """Determine deterministically the next action for a run using pure domain evaluation.

    `workspace_ready` is False when the session has no `workspace_path`: an `isolated_required`
    contract is then blocked until `rapid start --resume --worktree` creates the worktree.
    """
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

    # b2. Revisión humana rechazada: el gate queda en FAIL para siempre en este run.
    rejected_gate_ids = _rejected_human_gate_ids(contract, raw_evidence)
    if rejected_gate_ids:
        return NextAction(
            schema_version=1,
            run_id=contract.run_id,
            mode=mode,
            kind=ActionKind.BLOCKED,
            gate_ids=rejected_gate_ids,
            instructions=(
                f"Review rejected (changes_requested) for {', '.join(rejected_gate_ids)}; "
                "the gate stays FAIL for the rest of this run. Run `rapid abort` and start a new run "
                f"(`rapid start {mode}`) addressing the requested changes."
            ),
            command=("rapid", "abort"),
            after=None,
            awaiting_human=pending_human_ids,
            missing=missing,
            tasks_done=tasks_done,
            tasks_total=tasks_total,
            outcome=None,
        )

    # b3. Contrato con workspace aislado y la sesión aún sin worktree (igual que `rapid start`).
    if contract.workspace == WorkspaceRequirement.ISOLATED_REQUIRED and not workspace_ready:
        return NextAction(
            schema_version=1,
            run_id=contract.run_id,
            mode=mode,
            kind=ActionKind.BLOCKED,
            instructions=(
                "Execution contract requires an isolated workspace (worktree). "
                "Workspace isolation must be established before execution: "
                "run `rapid start --resume --worktree` to create it."
            ),
            command=("rapid", "start", "--resume", "--worktree"),
            after=None,
            awaiting_human=pending_human_ids,
            missing=("gate.workspace-isolation",),
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
                            f"{playbook.get_instruction(ActionKind.RUN_BASELINE)} {NO_TEST_COMMAND_NOTICE}"
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
            instructions = playbook.get_instruction(ActionKind.IMPLEMENT_TASK)

            # bugfix: la primera tarea (T001) debe reproducir el bug con un test en rojo.
            if (
                mode == "bugfix"
                and target_task.status == TaskStatus.IN_PROGRESS
                and contract.tasks
                and target_task.id == contract.tasks[0].id
            ):
                reproduced = any(
                    a.id == f"reproduction.{target_task.id}"
                    and a.status == EvalAssertionStatus.PASS
                    for a in report.assertions
                )
                if reproduced:
                    # The task is red by design and the reproduction evidence backs it:
                    # do not rerun the whole suite when closing it.
                    after = ("rapid", "task", "done", target_task.id, "--no-check")
                elif test_command:
                    cmd = (
                        "rapid", "check", "--expect", "fail", "--task", target_task.id,
                        "--", *test_command,
                    )
                    instructions = (
                        f"{instructions} First write the failing test that reproduces the bug, "
                        f"then run the command to record the expected failure for {target_task.id}; "
                        "the fix belongs to the next task."
                    )
                else:
                    instructions = (
                        f"{instructions} {NO_TEST_COMMAND_NOTICE}"
                    )
            # research: spike without mandatory tests; findings are attached as evidence.
            if mode == "research" and target_task.status == TaskStatus.IN_PROGRESS:
                after = ("rapid", "task", "done", target_task.id, "--no-check")
                instructions = (
                    f"{instructions} No tests are required: record the findings with "
                    f"`rapid attach <path> --label TEXT --task {target_task.id}` before closing the task."
                )
            return NextAction(
                schema_version=1,
                run_id=contract.run_id,
                mode=mode,
                kind=ActionKind.IMPLEMENT_TASK,
                task_id=target_task.id,
                instructions=instructions,
                command=cmd,
                after=after,
                awaiting_human=pending_human_ids,
                missing=missing,
                tasks_done=tasks_done,
                tasks_total=tasks_total,
                outcome=None,
            )

    # e. Todas las tareas terminales:
    # 0) refactor: los tests pasados no pueden bajar respecto a la baseline (regla del Conductor).
    if mode == "refactor":
        regression = _refactor_regression(contract, raw_evidence)
        if regression is not None:
            baseline_passed, latest_passed = regression
            return NextAction(
                schema_version=1,
                run_id=contract.run_id,
                mode=mode,
                kind=ActionKind.BLOCKED,
                instructions=(
                    f"Refactor lost test coverage: baseline had {baseline_passed} passed, "
                    f"the latest test run has {latest_passed} passed "
                    f"({baseline_passed - latest_passed} fewer). "
                    "A refactor must not reduce passing tests; restore them and re-run `rapid check`."
                ),
                command=None,
                after=None,
                awaiting_human=pending_human_ids,
                missing=missing,
                tasks_done=tasks_done,
                tasks_total=tasks_total,
                outcome=None,
            )

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
        if mode == "research":
            return NextAction(
                schema_version=1,
                run_id=contract.run_id,
                mode=mode,
                kind=ActionKind.VERIFY,
                task_id=target_task_id,
                instructions=(
                    f"Task {target_task_id} has no linked evidence. Research spikes need no tests: "
                    f"attach the findings with `rapid attach <path> --label TEXT --task {target_task_id}`."
                ),
                command=None,
                after=None,
                awaiting_human=pending_human_ids,
                missing=missing,
                tasks_done=tasks_done,
                tasks_total=tasks_total,
                outcome=None,
            )
        if test_command:
            cmd = ("rapid", "check", "--task", target_task_id, "--", *test_command)
            instr = playbook.get_instruction(ActionKind.VERIFY)
        else:
            cmd = None
            instr = (
                f"{playbook.get_instruction(ActionKind.VERIFY)} {NO_TEST_COMMAND_NOTICE}"
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
                    f"{playbook.get_instruction(ActionKind.VERIFY)} {NO_TEST_COMMAND_NOTICE}"
                )
        elif gate_kind == GateKind.ARCHITECTURE_CHECK:
            cmd = ("rapid", "check", "--gate", first_mg.id, "--", "rapid", "arch", "check")
            instr = playbook.get_instruction(ActionKind.VERIFY)
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
                cmd = ("rapid", "check", "--", *test_command)
                instr = playbook.get_instruction(ActionKind.VERIFY)
            else:
                cmd = None
                instr = (
                    f"{playbook.get_instruction(ActionKind.VERIFY)} {NO_TEST_COMMAND_NOTICE}"
                )
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

        # Cualquier otra capacidad -> blocked con la razón
        return NextAction(
            schema_version=1,
            run_id=contract.run_id,
            mode=mode,
            kind=ActionKind.BLOCKED,
            instructions=first_cap.reason
            or f"Required capability '{first_cap.subject_id}' is unverified.",
            command=None,
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

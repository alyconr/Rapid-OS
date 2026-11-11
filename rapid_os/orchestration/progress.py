"""What a person sees of a run's progress: tasks and gates with their state and the evidence behind them.

`rapid status` lists it and `rapid approve` shows it before asking. The state lives in
`.rapid-os/runs/<run>/states/`, not in the spec's `tasks.md` (an immutable revision)."""

from __future__ import annotations

from pathlib import Path

from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.domain.execution import TaskStatus

STATUS_TITLE_WIDTH = 72


def short_title(task_id: str, description: str, width: int = STATUS_TITLE_WIDTH) -> str:
    """The task's title for one line: without a repeated `T002:` prefix, cut with an ellipsis."""
    title = " ".join(str(description or "").split())
    for prefix in (f"{task_id}:", f"{task_id} -", f"{task_id}"):
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
            break
    return title if len(title) <= width else title[: width - 1].rstrip() + "…"


def evidence_result(evidence) -> str | None:
    """PASS or FAIL of one evidence record as a person reads it, or None when it has no result.

    A check passes with exit 0 and no failed test; an expected failure (`--expect fail`) is `FAIL (esperado)`;
    a review is PASS when approved and FAIL when it asked for changes."""
    payload = getattr(evidence, "payload", None) or {}
    if "exit_code" in payload:
        if payload.get("expectation") == "fail":
            return "FAIL (esperado)"
        failed = payload.get("failed") or 0
        return "PASS" if payload.get("exit_code") == 0 and not failed else "FAIL"
    outcome = payload.get("outcome")
    if outcome == "approved":
        return "PASS"
    if outcome in ("changes_requested", "rejected"):
        return "FAIL"
    return None


def run_progress(project_root, project_rapid_dir, run_reg, run_id: str) -> dict[str, object]:
    """Tasks and gates of a run with their state and the evidence ids that back them.

    Evidence ids come from the behavioral evaluator (what it counts for each task and gate) and, for a task or a
    gate, also from the records that name it. A task or gate that is still `pending` also carries the result of
    its last evidence (`last_evidence_result`): its `rapid check` may already have passed. A run whose evidence
    cannot be read still lists its tasks and gates."""
    from rapid_os.orchestration.conductor import _rejected_human_gate_ids
    from rapid_os.orchestration.lifecycle import run_evaluator

    contract = run_reg.get_contract(run_id)
    state = run_reg.get_state(run_id)
    try:
        evidence = EvidenceRegistry(project_root, project_rapid_dir).list(run_id)
        evidence_error = None
    except Exception as exc:  # a progress view never fails on unreadable evidence
        evidence, evidence_error = (), f"{getattr(exc, 'code', 'RAPID1200')} {exc}"
    assertions: dict[tuple[str, str], object] = {}
    try:
        report = run_evaluator(contract).evaluate(contract, state, evidence)
        for assertion in report.assertions:
            assertions.setdefault((assertion.category, assertion.subject_id), assertion)
    except Exception:
        pass

    def ids(*groups) -> list[str]:
        seen: list[str] = []
        for group in groups:
            for value in group:
                if value not in seen:
                    seen.append(value)
        return seen

    def last_result(entry: dict[str, object], linked) -> None:
        # Not evaluated yet, but a check may already have run: say so, or the person reads "pending" as "not done".
        last = next((ev for ev in reversed(linked) if evidence_result(ev) is not None), None)
        entry["last_evidence_result"] = evidence_result(last) if last is not None else None
        entry["last_evidence_id"] = last.id if last is not None else None

    tasks = []
    for task in state.tasks:
        assertion = assertions.get(("task", task.id))
        linked = [ev for ev in evidence if task.id in ev.task_ids]
        entry = {
            **task.to_dict(),
            "title": short_title(task.id, task.description),
            "evidence_ids": ids(getattr(assertion, "evidence_ids", ()), [ev.id for ev in linked]),
        }
        if task.status == TaskStatus.PENDING:
            last_result(entry, linked)
        tasks.append(entry)
    rejected = set(_rejected_human_gate_ids(contract, evidence))
    gates = []
    for gate in state.gates:
        assertion = assertions.get(("gate", gate.id))
        linked = [ev for ev in evidence if gate.id in ev.gate_ids]
        if gate.id in rejected:
            status = "fail"
        elif gate.disposition.value == "pending":
            status = "pending"
        elif assertion is not None:
            status = assertion.status.value
        else:
            status = gate.disposition.value
        entry = {
            **gate.to_dict(),
            "status": status,
            "evidence_ids": ids(getattr(assertion, "evidence_ids", ()), [ev.id for ev in linked]),
        }
        if status == "pending":
            last_result(entry, linked)
        gates.append(entry)
    progress: dict[str, object] = {"run_id": run_id, "status": state.status.value, "tasks": tasks, "gates": gates}
    if evidence_error:
        progress["evidence_error"] = evidence_error
    return progress


def gate_label(item: dict[str, object]) -> str:
    """`pending · última evidencia: PASS` for a pending task or gate whose last evidence has a result, else its status."""
    if item.get("status") == "pending" and item.get("last_evidence_result"):
        return f"pending · última evidencia: {item['last_evidence_result']}"
    return str(item.get("status"))


def evidence_note(item: dict[str, object]) -> str:
    found = item.get("evidence_ids") or []
    return f"  (evidencia: {', '.join(found)})" if found else ""


def progress_lines(progress: dict[str, object]) -> list[str]:
    tasks = progress["tasks"]
    done = sum(1 for t in tasks if t["status"] in (TaskStatus.DONE.value, TaskStatus.SKIPPED.value))
    lines = [f"Tasks:         {done}/{len(tasks)} terminal"]
    for task in tasks:
        lines.append(f"  {task['id']} [{gate_label(task)}] {task['title']}{evidence_note(task)}")
    lines.append("Gates:")
    for gate in progress["gates"] or ():
        lines.append(f"  {gate['id']} [{gate_label(gate)}]{evidence_note(gate)}")
    if not progress["gates"]:
        lines.append("  none")
    if progress.get("evidence_error"):
        lines.append(f"WARNING evidence could not be read: {progress['evidence_error']}")
    return lines


def last_run_id(run_reg, project_rapid_dir) -> str | None:
    """The run whose state was written last (run ids carry no date): what `rapid status` shows with no active run."""
    try:
        records = run_reg.list_runs()
    except Exception:
        return None

    def written_at(run_id: str) -> float:
        run_dir = Path(project_rapid_dir) / "runs" / run_id
        stamps = [p.stat().st_mtime for p in (run_dir / "states").glob("*") if p.is_file()]
        return max(stamps) if stamps else run_dir.stat().st_mtime

    try:
        return max((r.id for r in records), key=written_at, default=None)
    except OSError:
        return None

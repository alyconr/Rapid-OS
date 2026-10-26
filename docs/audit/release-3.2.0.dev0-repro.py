"""Reproduce audit findings in temporary repositories (not regression acceptance tests).

Run from the checkout: python docs/audit/release-3.2.0.dev0-repro.py
Assertions intentionally describe the vulnerable behavior of the audited revision.
No network, approvals, or changes to the user's project are required.
"""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.test_evidence_evals import _setup_ready_project
from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.domain.architecture import default_config
from rapid_os.domain.evals import BehavioralEvaluator
from rapid_os.domain.execution import GateKind
from rapid_os.orchestration.check import parse_test_output, run_check
from rapid_os.orchestration.git import run_git
from rapid_os.orchestration.session import observed_changes, resolve_git_head


def main():
    with tempfile.TemporaryDirectory(prefix="rapid-audit-") as directory:
        root = Path(directory)
        rapid_dir, _, registry, _ = _setup_ready_project(root)
        (rapid_dir / "standards/architecture.json").write_text(
            json.dumps(default_config("python-api")), encoding="utf-8"
        )
        record = registry.create(
            spec_id="checkout-idempotency", harness="codex",
            classification="bounded", risk="high",
        )
        check = run_check(
            root, rapid_dir, record.id, [sys.executable, "-c", "pass"],
            gate_ids=["gate.architecture"],
        )
        evaluator = BehavioralEvaluator()
        classify = lambda evidence: evaluator._classify_gate_evidence_item(
            GateKind.ARCHITECTURE_CHECK, evidence
        ).value
        assert classify(check.evidence) == "pass"
        print("A1: an executed no-op qualifies as passing architecture evidence")

        source = root / "app/modules/orders/domain/model.py"
        source.parent.mkdir(parents=True)
        source.write_text("import sqlalchemy\n", encoding="utf-8")
        failed = run_check(
            root, rapid_dir, record.id,
            [sys.executable, "-c", "raise SystemExit(1)"],
            gate_ids=["gate.architecture"],
        )
        records = EvidenceRegistry(root, rapid_dir).list(record.id)
        assert failed.exit_code == 1 and failed.evidence is None
        assert len(records) == 1 and classify(records[0]) == "pass"
        print("A2: after a source edit and a failed check, only the old passing evidence remains")

    with tempfile.TemporaryDirectory(prefix="rapid-audit-") as directory:
        root = Path(directory)
        assert run_git(root, "init").returncode == 0
        source = root / "app.py"
        source.write_text("original\n", encoding="utf-8")
        assert run_git(root, "add", "app.py").returncode == 0
        commit = run_git(
            root, "-c", "user.name=Audit", "-c", "user.email=audit@example.invalid",
            "commit", "-m", "baseline",
        )
        assert commit.returncode == 0, commit.stderr
        source.write_text("pre-existing dirty edit\n", encoding="utf-8")
        head_at_start = resolve_git_head(root)
        # Nothing is written after capturing the run's start state.
        changes = observed_changes(root, head_at_start, ())
        assert changes == ["app.py"], changes
        print("A4: a tracked edit predating the run is attributed to the run")

    counts = parse_test_output("Ran 10 tests in 0.001s\n\nOK (skipped=10)", 0)
    assert counts == {"passed": 10, "failed": 0, "skipped": 0}, counts
    print("A5: ten skipped unittest tests are reported as ten passed tests")
    print("Four audit reproductions confirmed; this does NOT assert a full run verdict.")


if __name__ == "__main__":
    main()

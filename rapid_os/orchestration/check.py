"""Execution and recording of porcelain checks in Rapid OS.

Executes direct argv commands without shell, captures combined output into
`.rapid-os/scratch/checks/<run-id>/<n>.log`, parses test outcomes (unittest/pytest),
and registers append-only RunEvidence on success (exit_code == 0).
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.core.filesystem import safe_write_text
from rapid_os.domain.evidence import EvidenceKind, RunEvidence


PYTEST_SUMMARY_RE = re.compile(
    r"(?:=+\s*)?(?:(\d+)\s+passed)?(?:[,\s]+(\d+)\s+failed)?(?:[,\s]+(\d+)\s+skipped)?.*?(?:in\s+[\d\.]+\s*s)?",
    re.IGNORECASE,
)
PYTEST_PASSED_IN_RE = re.compile(r"(\d+)\s+passed\s+in\s+[\d\.]+s", re.IGNORECASE)
PYTEST_FAILED_RE = re.compile(r"(\d+)\s+failed", re.IGNORECASE)
PYTEST_PASSED_RE = re.compile(r"(\d+)\s+passed", re.IGNORECASE)
PYTEST_SKIPPED_RE = re.compile(r"(\d+)\s+skipped", re.IGNORECASE)

UNITTEST_RAN_RE = re.compile(r"Ran\s+(\d+)\s+tests?\s+in\s+[\d\.]+s", re.IGNORECASE)
UNITTEST_FAILED_RE = re.compile(r"FAILED\s*\((?:failures=(\d+))?(?:[,\s]*errors=(\d+))?(?:[,\s]*skipped=(\d+))?\)", re.IGNORECASE)
UNITTEST_OK_RE = re.compile(r"\bOK\b")


@dataclass(frozen=True)
class CheckResult:
    run_id: str
    argv: tuple[str, ...]
    exit_code: int
    log_path: Path
    kind: str
    output: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    evidence: RunEvidence | None = None


def parse_test_output(output: str, exit_code: int) -> dict[str, int]:
    """Parse test counts (passed, failed, skipped) from unittest or pytest output."""
    passed = 0
    failed = 0
    skipped = 0

    # 1. Try pytest
    # Look for patterns like "10 passed, 2 failed in 1.2s"
    has_pytest = False
    for line in reversed(output.splitlines()):
        line_clean = line.strip("= ")
        m_p = PYTEST_PASSED_RE.search(line)
        m_f = PYTEST_FAILED_RE.search(line)
        m_s = PYTEST_SKIPPED_RE.search(line)
        if m_p or m_f or m_s:
            has_pytest = True
            if m_p:
                passed += int(m_p.group(1))
            if m_f:
                failed += int(m_f.group(1))
            if m_s:
                skipped += int(m_s.group(1))
            break

    if has_pytest:
        return {"passed": passed, "failed": failed, "skipped": skipped}

    # 2. Try unittest
    m_ran = UNITTEST_RAN_RE.search(output)
    if m_ran:
        total = int(m_ran.group(1))
        m_fail = UNITTEST_FAILED_RE.search(output)
        if m_fail:
            failures = int(m_fail.group(1) or 0)
            errors = int(m_fail.group(2) or 0)
            skipped_cnt = int(m_fail.group(3) or 0)
            failed = failures + errors
            skipped = skipped_cnt
            passed = max(0, total - failed - skipped)
        elif UNITTEST_OK_RE.search(output) or exit_code == 0:
            passed = total
            failed = 0
            skipped = 0
        else:
            failed = total if exit_code != 0 else 0
            passed = max(0, total - failed)
        return {"passed": passed, "failed": failed, "skipped": skipped}

    # 3. Fallback based on exit_code
    if exit_code == 0:
        return {"passed": 0, "failed": 0, "skipped": 0}
    else:
        return {"passed": 0, "failed": 1, "skipped": 0}


def run_check(
    project_root: Path,
    project_rapid_dir: Path,
    run_id: str,
    argv: Sequence[str],
    *,
    task_ids: Sequence[str] = (),
    gate_ids: Sequence[str] = (),
    kind: str | None = None,
    test_command: Sequence[str] | None = None,
    timeout: float = 600.0,
) -> CheckResult:
    """Execute argv without shell, write scratch log, and record RunEvidence if successful."""
    clean_argv = tuple(str(a) for a in argv)
    if not clean_argv:
        raise ValueError("Cannot run check with empty argv.")

    # Determine kind: test_result or command_result
    if kind in ("test", "test_result", EvidenceKind.TEST_RESULT.value):
        effective_kind = EvidenceKind.TEST_RESULT.value
    elif kind in ("command", "command_result", EvidenceKind.COMMAND_RESULT.value):
        effective_kind = EvidenceKind.COMMAND_RESULT.value
    elif test_command is not None and list(clean_argv) == list(test_command):
        effective_kind = EvidenceKind.TEST_RESULT.value
    else:
        effective_kind = EvidenceKind.COMMAND_RESULT.value

    # Prepare log destination: .rapid-os/scratch/checks/<run-id>/<n>.log
    checks_dir = Path(project_rapid_dir) / "scratch" / "checks" / run_id
    checks_dir.mkdir(parents=True, exist_ok=True)

    existing_logs = list(checks_dir.glob("*.log"))
    next_num = len(existing_logs) + 1
    log_file = checks_dir / f"{next_num}.log"

    # Execute subprocess
    proc = subprocess.run(
        list(clean_argv),
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        shell=False,
        timeout=timeout,
    )
    output = proc.stdout or ""
    exit_code = proc.returncode

    # Write log to scratch
    safe_write_text(
        log_file,
        output,
        encoding="utf-8",
        allow_overwrite=True,
        create_parents=True,
    )

    counts = {"passed": 0, "failed": 0, "skipped": 0}
    if effective_kind == EvidenceKind.TEST_RESULT.value:
        counts = parse_test_output(output, exit_code)

    # Invariant: append-only ledger must NOT record failed checks
    if exit_code != 0:
        return CheckResult(
            run_id=run_id,
            argv=clean_argv,
            exit_code=exit_code,
            log_path=log_file,
            kind=effective_kind,
            output=output,
            passed=counts["passed"],
            failed=counts["failed"],
            skipped=counts["skipped"],
            evidence=None,
        )

    # Success: record evidence in EvidenceRegistry
    evidence_reg = EvidenceRegistry(project_root, project_rapid_dir)
    run_reg = RunRegistry(project_root, project_rapid_dir)
    run_state = run_reg.get_state(run_id)

    # Calculate relative log path from project_root
    try:
        rel_log_path = log_file.relative_to(project_root).as_posix()
    except ValueError:
        rel_log_path = log_file.name

    # Normalize cmd display string for portable text (no backslashes or slashes if problematic)
    cmd_token = clean_argv[0] if clean_argv else "command"
    cmd_token = Path(cmd_token).name.replace("\\", "/").split("/")[-1]
    safe_cmd_summary = " ".join(clean_argv).replace("\\", "/")
    if len(safe_cmd_summary) > 60:
        safe_cmd_summary = safe_cmd_summary[:57] + "..."

    authoring_payload: dict[str, object]
    if effective_kind == EvidenceKind.TEST_RESULT.value:
        authoring_payload = {
            "suite": cmd_token or "test",
            "exit_code": exit_code,
            "passed": counts["passed"],
            "failed": counts["failed"],
            "skipped": counts["skipped"],
        }
        capability_ids = ["tests.execute"]
    else:
        authoring_payload = {
            "label": safe_cmd_summary,
            "exit_code": exit_code,
        }
        capability_ids = ["shell.execute"]

    summary = f"Check '{safe_cmd_summary}' passed (exit 0)"
    if effective_kind == EvidenceKind.TEST_RESULT.value:
        summary = f"Test check '{safe_cmd_summary}' passed ({counts['passed']} passed, {counts['failed']} failed)"

    authoring_input = {
        "kind": effective_kind,
        "producer": "rapid:check",
        "summary": summary,
        "state_revision": run_state.revision,
        "task_ids": tuple(task_ids),
        "gate_ids": tuple(gate_ids),
        "capability_ids": tuple(capability_ids),
        "payload": authoring_payload,
        "artifacts": [rel_log_path],
    }

    evidence = evidence_reg.add(
        run_id,
        authoring_input,
        base_dir=project_root,
    )

    return CheckResult(
        run_id=run_id,
        argv=clean_argv,
        exit_code=exit_code,
        log_path=log_file,
        kind=effective_kind,
        output=output,
        passed=counts["passed"],
        failed=counts["failed"],
        skipped=counts["skipped"],
        evidence=evidence,
    )

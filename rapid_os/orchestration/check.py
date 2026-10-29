"""Execution and recording of porcelain checks in Rapid OS.

Executes direct argv commands without shell, captures combined output into
`.rapid-os/scratch/checks/<run-id>/<n>.log`, parses test outcomes (unittest/pytest),
and registers append-only RunEvidence on success (exit_code == 0).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.core.filesystem import safe_write_text
from rapid_os.domain.evidence import EvidenceKind, RunEvidence
from rapid_os.domain.policy import GateKind
from rapid_os.orchestration import tree_fingerprint


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
# `cargo test`: one `test result: ok. 12 passed; 0 failed; 1 ignored; ...` line per test binary.
CARGO_RESULT_RE = re.compile(r"test result:\s*\w+\.\s*(\d+)\s+passed;\s*(\d+)\s+failed;\s*(\d+)\s+ignored", re.IGNORECASE)
# `go test -v`: one `--- PASS|FAIL|SKIP: Name` line per test.
GO_RESULT_RE = re.compile(r"^\s*--- (PASS|FAIL|SKIP):", re.MULTILINE)
# Modes whose tasks are verified with tests; a research spike is not.
MODES_WITHOUT_TESTS = frozenset({"research"})


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
    # The check was bound to a test gate or to a task of a mode that needs tests...
    tests_expected: bool = False
    # ...and its output had a test summary that could be counted.
    counted: bool = False


def resolve_executable(argv: Sequence[str]) -> list[str]:
    """`argv` with its first element replaced by the path `shutil.which` finds (`pnpm` -> `...\\pnpm.cmd`).

    Left as typed when it cannot be found: running it then fails with the usual "command not found"."""
    resolved = list(argv)
    if resolved:
        found = shutil.which(resolved[0])
        if found:
            resolved[0] = found
    return resolved


def parse_test_summary(output: str) -> dict[str, int] | None:
    """Test counts from the summary of pytest, unittest, vitest, jest, `cargo test` or `go test -v`.

    None when the output has no summary that can be read (a command that is not a test runner, or a
    runner whose output has no counts, such as `go test` without `-v`): the caller must say so."""
    cargo = CARGO_RESULT_RE.findall(output)
    if cargo:
        return {
            "passed": sum(int(p) for p, _f, _i in cargo),
            "failed": sum(int(f) for _p, f, _i in cargo),
            "skipped": sum(int(i) for _p, _f, i in cargo),
        }
    go = GO_RESULT_RE.findall(output)
    if go:
        return {
            "passed": go.count("PASS"),
            "failed": go.count("FAIL"),
            "skipped": go.count("SKIP"),
        }
    for line in reversed(output.splitlines()):
        m_p = PYTEST_PASSED_RE.search(line)
        m_f = PYTEST_FAILED_RE.search(line)
        m_s = PYTEST_SKIPPED_RE.search(line)
        if m_p or m_f or m_s:  # pytest, vitest and jest all end with a line like this
            return {
                "passed": int(m_p.group(1)) if m_p else 0,
                "failed": int(m_f.group(1)) if m_f else 0,
                "skipped": int(m_s.group(1)) if m_s else 0,
            }
    m_ran = UNITTEST_RAN_RE.search(output)
    if m_ran:
        total = int(m_ran.group(1))
        m_fail = UNITTEST_FAILED_RE.search(output)
        if m_fail:
            failed = int(m_fail.group(1) or 0) + int(m_fail.group(2) or 0)
            skipped = int(m_fail.group(3) or 0)
            return {"passed": max(0, total - failed - skipped), "failed": failed, "skipped": skipped}
        skipped_ok = re.search(r"OK \(skipped=(\d+)\)", output)
        skipped = int(skipped_ok.group(1)) if skipped_ok else 0
        return {"passed": max(0, total - skipped), "failed": 0, "skipped": skipped}
    return None


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
    expect: str = "pass",
    cwd: Path | None = None,
) -> CheckResult:
    """Execute argv without shell, write scratch log, and record RunEvidence if successful.

    The command runs in `cwd` (the run's isolated worktree) or in `project_root`; the
    ledger, logs and evidence always stay under `project_root`.
    """
    clean_argv = tuple(str(a) for a in argv)
    if not clean_argv:
        raise ValueError("Cannot run check with empty argv.")

    # `rapid check -- rapid arch check` (what `rapid next` proposes for gate.architecture) runs this
    # same Rapid OS: the `rapid` on PATH may be another version, or none.
    exec_argv = list(clean_argv)
    child_env = None
    if exec_argv[0] == "rapid":
        exec_argv = [sys.executable, "-m", "rapid_os.cli.main", *exec_argv[1:]]
        # The child must import the package that is running, also from an uninstalled checkout.
        package_root = str(Path(__file__).resolve().parents[2])
        child_env = dict(os.environ)
        child_env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_root, child_env.get("PYTHONPATH")]))

    run_reg = RunRegistry(project_root, project_rapid_dir)
    # A check bound to a test gate, or to a task of a mode that needs tests, is a test run even when its argv is
    # not exactly `test_command` (`uv run --directory backend pytest -q` is `pytest`): the output decides.
    contract = run_reg.get_contract(run_id)
    test_gate_ids = {g.id for g in contract.gates if g.kind in (GateKind.BASELINE_CHECK, GateKind.IMPLEMENTATION_TESTS)}
    tests_expected = bool(set(gate_ids) & test_gate_ids) or (
        bool(task_ids) and str(getattr(contract, "mode", "") or "") not in MODES_WITHOUT_TESTS
    )
    explicit_command = kind in ("command", "command_result", EvidenceKind.COMMAND_RESULT.value)

    # Windows: `subprocess` with shell=False does not find `pnpm`, `npm` or `yarn` (they are `.cmd` shims). The
    # executable is resolved with the PATH and PATHEXT; the argv that is compared with `test_command` and recorded
    # in the evidence stays the one that was typed.
    exec_argv = resolve_executable(exec_argv)

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
        exec_argv,
        env=child_env,
        cwd=str(cwd if cwd is not None else project_root),
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
    summary = parse_test_summary(output)
    counted = False
    if effective_kind == EvidenceKind.COMMAND_RESULT.value and tests_expected and not explicit_command and summary:
        effective_kind = EvidenceKind.TEST_RESULT.value  # same run, recognised by its output
    if effective_kind == EvidenceKind.TEST_RESULT.value:
        counts = summary if summary is not None else parse_test_output(output, exit_code)
        counted = summary is not None

    reproduced_failure = False
    if expect == "fail":
        if effective_kind == EvidenceKind.TEST_RESULT.value:
            reproduced_failure = (exit_code != 0 or counts["failed"] > 0)
        else:
            reproduced_failure = (exit_code != 0)

    # If expect == "fail" but command succeeded without failure, reproduction failed!
    if expect == "fail" and not reproduced_failure:
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

    # For standard checks (expect == "pass"), non-zero exit is failure and no evidence is recorded
    if expect != "fail" and exit_code != 0:
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
    run_state = run_reg.get_state(run_id)

    # Calculate relative log path from project_root
    try:
        rel_log_path = log_file.relative_to(project_root).as_posix()
    except ValueError:
        rel_log_path = log_file.name

    cmd_token = clean_argv[0] if clean_argv else "command"
    cmd_token = Path(cmd_token).name.replace("\\", "/").split("/")[-1]
    clean_tokens = [cmd_token]
    for tok in clean_argv[1:]:
        t = str(tok).replace("\\", "/")
        if re.match(r"^[A-Za-z]:", t) or t.startswith("/"):
            t = Path(t).name
        clean_tokens.append(t)
    safe_cmd_summary = " ".join(clean_tokens)
    if len(safe_cmd_summary) > 60:
        safe_cmd_summary = safe_cmd_summary[:57] + "..."

    full_command = " ".join(clean_tokens)
    authoring_payload: dict[str, object]
    if effective_kind == EvidenceKind.TEST_RESULT.value:
        authoring_payload = {
            "suite": cmd_token or "test",
            "exit_code": exit_code,
            "passed": counts["passed"],
            "failed": counts["failed"],
            "skipped": counts["skipped"],
        }
        if expect == "fail":
            authoring_payload["expectation"] = "fail"
        # So a baseline and a later check can be compared (they must be the same command).
        if len(full_command) <= 200 and ".." not in full_command and "\\" not in full_command:
            authoring_payload["command"] = full_command
        capability_ids = ["tests.execute"]
    else:
        authoring_payload = {
            "label": safe_cmd_summary,
            "exit_code": exit_code,
        }
        if expect == "fail":
            authoring_payload["expectation"] = "fail"
        capability_ids = ["shell.execute"]
    # The working tree this check saw: `approve` and `finish` compare against it.
    snapshot = tree_fingerprint.working_tree_snapshot(cwd if cwd is not None else project_root)
    if snapshot is not None:
        authoring_payload["tree"] = tree_fingerprint.save_snapshot(project_rapid_dir, run_id, snapshot)

    if expect == "fail":
        summary = f"Reproduction check '{safe_cmd_summary}' confirmed expected failure (exit {exit_code})"
    else:
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
        tests_expected=tests_expected,
        counted=counted,
    )

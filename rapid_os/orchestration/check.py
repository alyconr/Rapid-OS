"""Execution and recording of porcelain checks in Rapid OS.

Executes direct argv commands without shell, captures combined output into
`.rapid-os/scratch/checks/<run-id>/<n>.log`, parses test outcomes (unittest/pytest),
and registers append-only RunEvidence on success (exit_code == 0).
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

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
# pytest: the final line, `==== 3 failed, 5 passed, 1 skipped, 2 errors in 2.10s ====` (`-q`: without the `=`).
PYTEST_LINE_RE = re.compile(
    r"^[=\s]*(\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?|rerun)\b.*?)"
    r"\s+in\s+[\d.]+\s*s\b",
    re.IGNORECASE,
)
PYTEST_ERRORS_RE = re.compile(r"(\d+)\s+errors?\b", re.IGNORECASE)
# vitest: `      Tests  1 failed | 2 passed | 1 skipped (4)` (not `Test Files`).
VITEST_LINE_RE = re.compile(r"^\s*Tests\s{2,}(\d+\s+\w+(?:\s*\|\s*\d+\s+\w+)*)\s*\(\d+\)\s*$")
# jest: `Tests:       1 failed, 1 skipped, 11 passed, 13 total`.
JEST_LINE_RE = re.compile(r"^\s*Tests:\s+(.*?)\d+\s+total\s*$")
# karma/jasmine (`ng test` before Vitest): `Executed 5 of 6 (1 FAILED) (skipped 1) (0.1 secs / 0.05 secs)`.
KARMA_LINE_RE = re.compile(r"Executed\s+(\d+)\s+of\s+(\d+)\b(.*)$")
KARMA_FAILED_RE = re.compile(r"\((\d+)\s+FAILED\)")
KARMA_SKIPPED_RE = re.compile(r"\(skipped\s+(\d+)\)")
# Modes whose tasks are verified with tests; a research spike is not.
MODES_WITHOUT_TESTS = frozenset({"research"})


def _run_mode(project_root: Path, project_rapid_dir: Path, contract) -> str:
    """The mode of a run: the `ExecutionContract` has none, the spec revision it was created from does.

    Falls back to the session (the active run) when the spec cannot be read; "" when neither says."""
    from rapid_os.adapters.spec_registry import SpecRegistry
    from rapid_os.orchestration.session import load_session

    try:
        revision = SpecRegistry(project_root, project_rapid_dir).get_revision(contract.spec_id, contract.spec_revision)
        return str(getattr(revision.mode, "value", revision.mode) or "")
    except Exception:
        session = load_session(project_rapid_dir)
        if session is not None and session.active_run_id == contract.run_id:
            return session.mode or ""
        return ""


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
    # `--kind test` was asked for a command whose output had no test summary and that is not `test_command`:
    # it was recorded as a command_result, which no test gate accepts.
    not_a_test_run: bool = False
    # Test gates (gate.tests, gate.baseline) the check was bound to and that it does not satisfy: its argv is not
    # the project's `test_command` and no person accepted it (RAPID1440). The check is recorded without them.
    refused_gates: tuple[str, ...] = ()
    # The count of each component of the combined test command, or of each runner found in the output (H-66).
    components: tuple[dict, ...] = ()


# Outside the project, an argument is recorded by its name only: the evidence is versioned and portable.
EXTERNAL_PREFIX = "<externo>/"
MAX_ARGV_TOKEN = 4096
MAX_COMPONENT_COMMAND = 200


def argv_digest(argv: Sequence[str]) -> str:
    """SHA-256 of an argv (canonical JSON): two checks ran the same command when their digests are equal."""
    return hashlib.sha256(json.dumps([str(a) for a in argv], ensure_ascii=False).encode("utf-8")).hexdigest()


def _as_file(token: str, cwd: Path) -> Path | None:
    if not token or "\x00" in token or len(token) > 1024 or "\n" in token:
        return None
    try:
        candidate = Path(token)
        candidate = candidate if candidate.is_absolute() else cwd / candidate
        return candidate if candidate.is_file() else None
    except (OSError, ValueError):
        return None


def _portable_path(path: Path, roots: Sequence[Path]) -> str:
    resolved = path.resolve()
    for root in roots:
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return EXTERNAL_PREFIX + path.name


def portable_argv(argv: Sequence[str], cwd: Path, roots: Sequence[Path]) -> tuple[list[str], list[dict[str, str]]]:
    """`(argv, files)` to record for a command a person accepted instead of `test_command`.

    Each argument that is a file becomes a path relative to the project (or `<externo>/<name>` outside it), and
    `files` has the SHA-256 of each of those files when the check starts: the evidence says what ran."""
    tokens: list[str] = []
    files: list[dict[str, str]] = []
    for raw in argv:
        token = str(raw)
        found = _as_file(token, cwd)
        if found is not None:
            portable = _portable_path(found, roots)
            try:
                files.append({"path": portable, "sha256": hashlib.sha256(found.read_bytes()).hexdigest()})
            except OSError:
                pass
            token = portable
        tokens.append(token.replace("\x00", "")[:MAX_ARGV_TOKEN])
    return tokens, files


def _short(argv: Sequence[str], limit: int = 80) -> str:
    text = " ".join(str(a) for a in argv)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def refused_gate_message(argv: Sequence[str], gates: Sequence[str], evidence: RunEvidence | None) -> str:
    """RAPID1440: a check bound to a test gate ran another command than `test_command`."""
    gate = gates[0] if gates else "gate.tests"
    recorded = f" (evidencia {evidence.id})" if evidence is not None else ""
    return (
        f"RAPID1440 El check ejecutó `{_short(argv)}`, que no es el test_command del proyecto: se registró como un "
        f"check normal{recorded} y no satisface {', '.join(gates)}. Ejecuta `rapid check --gate {gate}` sin "
        "comando: Rapid OS ejecuta el test_command configurado. Aceptar otro comando es decisión de la persona, "
        f"en su terminal: `rapid check --gate {gate} --accept-test-command \"MOTIVO\" -- <comando>`."
    )


def combined_components(argv: Sequence[str]) -> list[list[str]] | None:
    """The commands of a test command Rapid OS combined (`COMBINED_TEST_RUNNER`), or None for any other argv.

    `rapid setup set test-command --recommended` joins the backend and frontend commands in one `python -c`
    argv; `rapid check` runs each one by itself to count each summary (H-66)."""
    from rapid_os.orchestration.setup_conductor import COMBINED_TEST_RUNNER

    if len(argv) != 3 or argv[1] != "-c":
        return None
    head, _, tail = COMBINED_TEST_RUNNER.partition("{commands!r}")
    code = str(argv[2])
    if not (code.startswith(head) and code.endswith(tail)) or len(code) <= len(head) + len(tail):
        return None
    try:
        commands = ast.literal_eval(code[len(head):len(code) - len(tail)])
    except (ValueError, SyntaxError):
        return None
    if (
        not isinstance(commands, list) or len(commands) < 2
        or not all(isinstance(c, list) and c and all(isinstance(a, str) for a in c) for c in commands)
    ):
        return None
    return [list(c) for c in commands]


def _run_combined(components, cwd, child_env, timeout) -> tuple[str, int, list[dict[str, object]]]:
    """Run each component like `COMBINED_TEST_RUNNER` does (in order, all of them, exit 1 if any fails) and keep
    the output, exit code and summary of each one."""
    deadline = time.monotonic() + timeout
    parts: list[str] = []
    breakdown: list[dict[str, object]] = []
    for command in components:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        proc = subprocess.run(
            resolve_executable(command), env=child_env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", check=False, shell=False, timeout=remaining,
        )
        out = proc.stdout or ""
        shown = " ".join(command)
        parts.append(f"===== rapid check: {shown} (exit {proc.returncode}) =====\n{out}")
        counts = parse_test_summary(out)
        breakdown.append({
            "command": shown[:MAX_COMPONENT_COMMAND],
            "exit_code": proc.returncode,
            "passed": counts["passed"] if counts else 0,
            "failed": counts["failed"] if counts else 0,
            "skipped": counts["skipped"] if counts else 0,
            "counted": counts is not None,
        })
    exit_code = 1 if any(item["exit_code"] != 0 for item in breakdown) else 0
    return "\n".join(parts), exit_code, breakdown


def resolve_executable(argv: Sequence[str]) -> list[str]:
    """`argv` with its first element replaced by the path `shutil.which` finds (`pnpm` -> `...\\pnpm.cmd`).

    Left as typed when it cannot be found: running it then fails with the usual "command not found"."""
    resolved = list(argv)
    if resolved:
        found = shutil.which(resolved[0])
        if found:
            resolved[0] = found
    return resolved


def _counts(passed: int, failed: int, skipped: int, runner: str) -> dict[str, object]:
    return {"runner": runner, "passed": passed, "failed": failed, "skipped": skipped}


def _word_counts(text: str) -> dict[str, int]:
    """`{"passed": 5, "failed": 3, ...}` from `5 passed, 3 failed` or `3 failed | 5 passed`."""
    found: dict[str, int] = {}
    for number, word in re.findall(r"(\d+)\s+([A-Za-z]+)", text):
        found[word.lower()] = found.get(word.lower(), 0) + int(number)
    return found


def _last(regex: re.Pattern, lines: Sequence[str]) -> re.Match | None:
    for line in reversed(lines):
        if line.lstrip().lower().startswith("test result:"):
            continue  # `cargo test` has its own line
        match = regex.search(line)
        if match:
            return match
    return None


def _unittest_summary(output: str) -> dict[str, object] | None:
    ran = list(UNITTEST_RAN_RE.finditer(output))
    if not ran:
        return None
    last = ran[-1]
    total = int(last.group(1))
    after = output[last.end():]
    m_fail = UNITTEST_FAILED_RE.search(after)
    if m_fail:
        failed = int(m_fail.group(1) or 0) + int(m_fail.group(2) or 0)
        skipped = int(m_fail.group(3) or 0)
        return _counts(max(0, total - failed - skipped), failed, skipped, "unittest")
    skipped_ok = re.search(r"OK \(skipped=(\d+)\)", after)
    skipped = int(skipped_ok.group(1)) if skipped_ok else 0
    return _counts(max(0, total - skipped), 0, skipped, "unittest")


def _legacy_summary(lines: Sequence[str]) -> dict[str, object] | None:
    """The last line that names passed, failed or skipped tests (an unrecognized runner)."""
    for line in reversed(lines):
        m_p = PYTEST_PASSED_RE.search(line)
        m_f = PYTEST_FAILED_RE.search(line)
        m_s = PYTEST_SKIPPED_RE.search(line)
        if m_p or m_f or m_s:
            return _counts(
                int(m_p.group(1)) if m_p else 0,
                int(m_f.group(1)) if m_f else 0,
                int(m_s.group(1)) if m_s else 0,
                "unknown",
            )
    return None


def parse_test_summaries(output: str) -> list[dict[str, object]]:
    """One summary per test runner recognized in the output: `{runner, passed, failed, skipped}`.

    A command that runs several runners (a backend with pytest and a frontend with Vitest, H-66) prints one
    summary each; each runner contributes its last summary (`cargo test` the sum of its binaries, `go test -v`
    its per-test lines). An output with none of them falls back to the last line that names passed, failed or
    skipped tests. Empty when there is no summary at all."""
    lines = output.splitlines()
    found: list[dict[str, object]] = []
    cargo = CARGO_RESULT_RE.findall(output)
    if cargo:
        found.append(_counts(
            sum(int(p) for p, _f, _i in cargo), sum(int(f) for _p, f, _i in cargo),
            sum(int(i) for _p, _f, i in cargo), "cargo test",
        ))
    go = GO_RESULT_RE.findall(output)
    if go:
        found.append(_counts(go.count("PASS"), go.count("FAIL"), go.count("SKIP"), "go test"))
    pytest = _last(PYTEST_LINE_RE, lines)
    if pytest:
        words = _word_counts(pytest.group(1))
        failed = words.get("failed", 0) + words.get("error", 0) + words.get("errors", 0)
        found.append(_counts(words.get("passed", 0), failed, words.get("skipped", 0), "pytest"))
    vitest = _last(VITEST_LINE_RE, lines)
    if vitest:
        words = _word_counts(vitest.group(1))
        found.append(_counts(words.get("passed", 0), words.get("failed", 0),
                             words.get("skipped", 0) + words.get("todo", 0), "vitest"))
    jest = _last(JEST_LINE_RE, lines)
    if jest:
        words = _word_counts(jest.group(1))
        found.append(_counts(words.get("passed", 0), words.get("failed", 0),
                             words.get("skipped", 0) + words.get("todo", 0), "jest"))
    karma = _last(KARMA_LINE_RE, lines)
    if karma:
        rest = karma.group(3)
        failed_match = KARMA_FAILED_RE.search(rest)
        skipped_match = KARMA_SKIPPED_RE.search(rest)
        failed = int(failed_match.group(1)) if failed_match else 0
        found.append(_counts(max(0, int(karma.group(1)) - failed), failed,
                             int(skipped_match.group(1)) if skipped_match else 0, "karma"))
    unittest_summary = _unittest_summary(output)
    if unittest_summary:
        found.append(unittest_summary)
    if not found:
        legacy = _legacy_summary(lines)
        if legacy:
            found.append(legacy)
    return found


def sum_summaries(summaries: Sequence[Mapping[str, object]]) -> dict[str, int] | None:
    if not summaries:
        return None
    return {key: sum(int(s[key]) for s in summaries) for key in ("passed", "failed", "skipped")}  # type: ignore[arg-type]


def parse_test_summary(output: str) -> dict[str, int] | None:
    """Test counts from the summary of pytest, unittest, vitest, jest, karma, `cargo test` or `go test -v`,
    added up when the output has the summaries of several runners (`parse_test_summaries`).

    None when the output has no summary that can be read (a command that is not a test runner, or a
    runner whose output has no counts, such as `go test` without `-v`): the caller must say so."""
    return sum_summaries(parse_test_summaries(output))


# The tests a runner names as failed, by file: pytest (`FAILED tests/test_x.py::test_y`, `ERROR tests/test_x.py`),
# vitest and jest (`FAIL  src/x.test.ts > suite > case`), unittest (`FAIL: test_y (tests.test_x.Case.test_y)`).
PYTEST_FAILED_TEST_RE = re.compile(r"^(?:FAILED|ERROR)\s+([^\s:]+\.[A-Za-z0-9]+)(?:::|\s|$)", re.MULTILINE)
JS_FAILED_TEST_RE = re.compile(r"^\s*FAIL\s+([^\s>]+\.(?:[cm]?[jt]sx?|vue|svelte))\b", re.MULTILINE)
UNITTEST_FAILED_TEST_RE = re.compile(r"^(?:FAIL|ERROR):\s+\w+\s+\(([\w.]+)\)", re.MULTILINE)


def parse_failed_test_files(output: str) -> list[str]:
    """The files of the tests the output names as failed (pytest, vitest, jest, unittest), in order, once each.

    A unittest test is named by its module (`tests.test_x.Case.test_y` -> `tests/test_x`, without extension).
    Empty when the runner names no failed test: then the count is all there is."""
    found: list[str] = []

    def add(path: str) -> None:
        path = path.replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]
        if path and path not in found:
            found.append(path)

    for match in PYTEST_FAILED_TEST_RE.finditer(output):
        add(match.group(1))
    for match in JS_FAILED_TEST_RE.finditer(output):
        add(match.group(1))
    for match in UNITTEST_FAILED_TEST_RE.finditer(output):
        parts = match.group(1).split(".")
        # `module.Class.method` (3.11+) or `module.Class`: the module is what comes before the class.
        upper = next((i for i, part in enumerate(parts) if part[:1].isupper()), None)
        module = parts[:upper] if upper is not None else parts[:-1]
        if module:
            add("/".join(module))
    return found


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


def _run_single(exec_argv, child_env, cwd, timeout) -> tuple[str, int]:
    proc = subprocess.run(
        exec_argv,
        env=child_env,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        # Test runners print UTF-8 (Vitest's ✓, ⎯, ❯). Without an explicit encoding Windows decodes with the
        # code page (cp1252), whose reader thread dies on a byte such as 0x9d: the log loses the output and
        # the summary is not counted. A byte that is not UTF-8 becomes U+FFFD instead of failing (H-57).
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        shell=False,
        timeout=timeout,
    )
    return proc.stdout or "", proc.returncode


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
    accepted: dict[str, str] | None = None,
) -> CheckResult:
    """Execute argv without shell, write scratch log, and record RunEvidence if successful.

    The command runs in `cwd` (the run's isolated worktree) or in `project_root`; the
    ledger, logs and evidence always stay under `project_root`.

    Only the project's `test_command` satisfies a test gate (gate.tests, gate.baseline). Another argv bound to one
    is recorded without that gate (`refused_gates`), unless a person accepted it in their terminal: `accepted` is
    `{"reviewer", "reason"}` and the evidence keeps the argv and the digest of every file it received.
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
    is_test_command = test_command is not None and list(clean_argv) == list(test_command)
    # H-68: `python -c "print('31 passed')"` printed a summary and satisfied gate.tests. A test gate is satisfied
    # by the configured test command, which Rapid OS runs itself (`rapid check --gate gate.tests` without argv);
    # another command needs a person's acceptance.
    refused_gates: tuple[str, ...] = ()
    if test_command is not None and not is_test_command and accepted is None:
        refused_gates = tuple(g for g in gate_ids if g in test_gate_ids)
        gate_ids = [g for g in gate_ids if g not in test_gate_ids]
    accepted_argv: tuple[list[str], list[dict[str, str]]] | None = None
    if accepted is not None and not is_test_command:
        work_dir = Path(cwd if cwd is not None else project_root)
        accepted_argv = portable_argv(clean_argv, work_dir, [work_dir, Path(project_root)])
    tests_expected = bool(set(gate_ids) & test_gate_ids) or (
        bool(task_ids) and _run_mode(project_root, project_rapid_dir, contract) not in MODES_WITHOUT_TESTS
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
    elif is_test_command:
        effective_kind = EvidenceKind.TEST_RESULT.value
    else:
        effective_kind = EvidenceKind.COMMAND_RESULT.value

    # Prepare log destination: .rapid-os/scratch/checks/<run-id>/<n>.log
    checks_dir = Path(project_rapid_dir) / "scratch" / "checks" / run_id
    checks_dir.mkdir(parents=True, exist_ok=True)

    existing_logs = list(checks_dir.glob("*.log"))
    next_num = len(existing_logs) + 1
    log_file = checks_dir / f"{next_num}.log"

    # The test command Rapid OS combined (backend and frontend) runs one component at a time, so each summary is
    # counted and kept apart (H-66); any other argv runs as typed.
    components = combined_components(clean_argv)
    breakdown: list[dict[str, object]] | None = None
    if components is not None:
        output, exit_code, breakdown = _run_combined(
            components, str(cwd if cwd is not None else project_root), child_env, timeout
        )
    else:
        output, exit_code = _run_single(exec_argv, child_env, cwd if cwd is not None else project_root, timeout)

    # Write log to scratch
    safe_write_text(
        log_file,
        output,
        encoding="utf-8",
        allow_overwrite=True,
        create_parents=True,
    )

    counts = {"passed": 0, "failed": 0, "skipped": 0}
    if breakdown is not None:
        counted_parts = [item for item in breakdown if item["counted"]]
        summary = sum_summaries(counted_parts)
    else:
        runners = parse_test_summaries(output)
        summary = sum_summaries(runners)
        if len(runners) > 1:  # a command we did not build ran several runners: keep each summary
            breakdown = [{k: item[k] for k in ("runner", "passed", "failed", "skipped")} for item in runners]
    counted = False
    not_a_test_run = False
    if effective_kind == EvidenceKind.COMMAND_RESULT.value and tests_expected and not explicit_command and summary:
        effective_kind = EvidenceKind.TEST_RESULT.value  # same run, recognised by its output
    if effective_kind == EvidenceKind.TEST_RESULT.value and summary is None and not is_test_command:
        # `--kind test` does not turn `python -c "print('hello')"` into a test run: with no summary to count,
        # only the project's own test command is trusted to be one.
        effective_kind = EvidenceKind.COMMAND_RESULT.value
        not_a_test_run = True
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
            not_a_test_run=not_a_test_run,
            refused_gates=refused_gates,
            components=tuple(breakdown or ()),
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
            not_a_test_run=not_a_test_run,
            refused_gates=refused_gates,
            components=tuple(breakdown or ()),
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
            # What a test gate needs (ruleset 3): a summary that was counted, or the project's test command.
            "counted": counted,
            "test_command": is_test_command,
            # The exact argv, so a baseline and a later check are compared even when `command` is not kept.
            "argv_digest": argv_digest(clean_argv),
        }
        if breakdown is not None:
            # H-66: the count of each component (the combined test command) or of each runner in the output.
            authoring_payload["components"] = breakdown
        if accepted_argv is not None and accepted is not None:
            authoring_payload["argv"] = accepted_argv[0]
            authoring_payload["argv_files"] = accepted_argv[1]
            authoring_payload["accepted"] = {
                "reviewer": str(accepted["reviewer"]),
                "reason": str(accepted["reason"]),
                "via": "rapid:check",
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
        not_a_test_run=not_a_test_run,
        refused_gates=refused_gates,
        components=tuple(breakdown or ()),
    )

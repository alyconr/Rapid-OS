"""Smoke test of an installed wheel on Windows: what broke in the 3.2.0rc1 end-to-end run.

Standard library only. It drives the `rapid` executable of a clean venv, in a temporary folder:

    python scripts/windows_smoke.py <path to rapid.exe>

1. `rapid --version`.
2. A minimal onboarding (`rapid setup set ...`, `rapid setup finish`).
3. H-29: `rapid start research --spec-file -` with a spec with accents and an n with tilde sent through a pipe; the id
   and the text must be stored intact.
4. H-32: `rapid check` with an executable that only exists as a `.cmd` on the PATH, typed without its extension.
5. H-51: evidence with LF and with mixed line endings, committed and cloned with core.autocrlf=true: the clone verifies
   with the `.gitattributes` of `rapid setup finish`; without it, verification fails and names the cause.
6. H-55: in a second project, a spec with accents and an n with tilde piped by Windows PowerShell 5.1
   (`powershell.exe -NoProfile -Command`) to `rapid start research --spec-file -` arrives with '?' and is refused with
   RAPID1415 and no run; the same text written with `Set-Content -Encoding utf8` (UTF-8 with BOM) and passed with
   `--spec-file <path>` creates the spec with its title intact and the id with "publica".
7. H-57: `rapid check` of a command that prints UTF-8 outside cp1252 (Vitest's ✓, ⎯, ❯) and a test summary: the log
   keeps those characters, the summary is counted and there is no traceback.
8. H-71: in a linked git worktree that is not the worktree of a run (what Codex creates for itself), `rapid next` and
   `rapid start` are refused with RAPID1450 naming the main checkout and write nothing; from the main checkout
   `rapid next` still works.
9. H-66 and H-68: in a feature run whose test_command is the combined command Rapid OS builds (backend and
   frontend, from `combine_test_commands` of the installed wheel), `rapid check --gate gate.tests` without a
   command, run from Windows PowerShell 5.1, adds both summaries and keeps the breakdown per component; and
   `rapid check --gate gate.tests -- python -c "print('==== 31 passed ====')"` is refused with RAPID1440 and exit 1.
10. H-81: a feature run driven with `rapid next` up to its human gate. `rapid approve <gate>` of the wheel, run from
   Windows PowerShell 5.1 with "s" piped, is refused with RAPID1310 (no terminal, or an agent among its ancestors).
   The [s/N] itself cannot be reached from a script through the real executable (that is the barrier), so the
   wheel's `execute_approve` is called with the barrier inputs injected (a terminal, no agent ancestor) and the
   answer read from the stdin PowerShell 5.1 pipes: an empty answer and "x" exit 1 with "Sin cambios" and the gate
   stays pending, with no review recorded.
11. H-79: an onboarded project whose `.rapid-os/standards/security.md` has no stamp and a body of its own:
   `rapid doctor --json` (from PowerShell 5.1) reports RAPID1444 for it, and `rapid setup standards --regenerate`
   writes `security.md.new` (stamped) and leaves the original byte for byte.
12. H-82: `detect_harness` of the wheel with an injected Windows-like process tree (names only, as the
   CreateToolhelp32Snapshot reader gives them, read through `read_ancestry` with an injected reader) that ends in
   `codex.exe` resolves to codex from the ancestry, in a project whose `tools` lists claude and codex. A real Codex
   is not needed and not used.

PYTHONUTF8 and PYTHONIOENCODING are removed from the environment, because either of them hides H-29: the point is to
run with the console code page of a real Windows machine.
"""

from __future__ import annotations

import json
import locale
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SPEC = {
    "title": "Notificación de dueño",
    "mode": "research",
    "business_objective": "Decidir cómo avisar al dueño",
    "problem_statement": "No hay notificación",
    "scope": ["notificación"],
    "acceptance_criteria": ["Las fechas son válidas", "El módulo avisa al dueño"],
    "tasks": ["T001: Comparar opciones"],
}
SPEC_ID = "notificacion-de-dueno"
PIPED_SPEC = {
    "title": "Reserva pública",
    "mode": "research",
    "business_objective": "Decidir la reserva pública",
    "problem_statement": "No hay reserva",
    "scope": ["reserva"],
    "acceptance_criteria": ["La reserva queda guardada"],
    "tasks": ["T001: Añadir la creación atómica del módulo"],
}
PIPED_SPEC_ID = "reserva-publica"
ONBOARDING = (
    ("stack", "python-fastapi"), ("topology", "backend-only"), ("archetype", "mvp"), ("ai", "no"),
    ("agents", "claude"), ("test-command", "smoke-tests"), ("services", "none"),
)
MOJIBAKE = ("Ã", "Â", "�")
# What Vitest prints: ✓ (E2 9C 93), ⎯ (E2 8E AF) and ❯ (E2 9D AF; 0x9d is not a cp1252 byte).
VITEST_LIKE = (
    "import sys; sys.stdout.buffer.write("
    "' \\u2713 src/reserva.test.ts (3 tests) 4ms\\n\\u23af\\u23af\\u23af\\n \\u276f done\\n"
    "      Tests  3 passed (3)\\n'.encode('utf-8')); sys.stdout.flush()"
)
SHIM = "@echo off\r\necho Ran 1 test in 0.001s\r\necho.\r\necho OK\r\nexit /b 0\r\n"
# The two components of a combined test command (H-66): a pytest-like backend and a Vitest-like frontend.
COMPONENT_SHIMS = {
    "backend-tests": "@echo off\r\necho ==== 31 passed, 7 skipped in 1.00s ====\r\nexit /b 0\r\n",
    "frontend-tests": "@echo off\r\necho  Test Files  1 passed (1)\r\necho       Tests  2 passed (2)\r\nexit /b 0\r\n",
}
FEATURE_SPEC = {
    "title": "Booking availability",
    "mode": "feature",
    "business_objective": "Reject double bookings",
    "problem_statement": "Bookings can overlap",
    "scope": ["bookings"],
    "acceptance_criteria": ["overlapping bookings are rejected"],
    "tasks": ["T001: Implement availability control"],
}
FAKE_SUMMARY = "print('==== 31 passed ====')"


def fail(message: str) -> None:
    print(f"FAIL {message}".encode(sys.stdout.encoding or "utf-8", "replace").decode(sys.stdout.encoding or "utf-8"))
    raise SystemExit(1)


def clean_environment(base: Path, bin_dir: Path) -> dict[str, str]:
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in ("PYTHONUTF8", "PYTHONIOENCODING", "PYTHONPATH", "CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")
    }
    gitconfig = base / "gitconfig"
    gitconfig.write_text("[user]\n\tname = Smoke\n\temail = smoke@example.com\n[init]\n\tdefaultBranch = main\n", encoding="utf-8")
    env["GIT_CONFIG_GLOBAL"] = str(gitconfig)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    return env


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    if os.name != "nt":
        fail("this smoke test checks Windows behaviour (code page, .cmd shims)")
    rapid_exe = str(Path(argv[1]).resolve())
    print(f"Code page in use: {locale.getpreferredencoding(False)}")

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        project = base / "project"
        project.mkdir()
        bin_dir = base / "bin"
        bin_dir.mkdir()
        (bin_dir / "smoke-tests.cmd").write_text(SHIM, encoding="ascii", newline="")
        for name, shim in COMPONENT_SHIMS.items():
            (bin_dir / f"{name}.cmd").write_text(shim, encoding="ascii", newline="")
        env = clean_environment(base, bin_dir)

        def rapid(*args: str, raw: bytes | None = None, cwd: Path = project) -> str:
            result = subprocess.run(
                [rapid_exe, *args], cwd=cwd, env=env, input=raw, capture_output=True, timeout=120,
                stdin=None if raw is not None else subprocess.DEVNULL,
            )
            out = result.stdout.decode("utf-8", "replace")
            if result.returncode != 0:
                fail(f"rapid {' '.join(args)} exited {result.returncode}:\n{out}\n{result.stderr.decode('utf-8', 'replace')}")
            return out

        def onboard(cwd: Path) -> None:
            for step in ONBOARDING:
                rapid("setup", "set", *step, cwd=cwd)
            for doc in ("brief", "business", "data-model", "architecture", "deployment"):
                rapid("setup", "doc", doc, "--skip", cwd=cwd)
            rapid("setup", "finish", cwd=cwd)

        # 1. The executable runs and reports a version.
        version = rapid("--version").strip()
        if not version.startswith("Rapid OS "):
            fail(f"unexpected version line: {version!r}")
        print(f"ok  --version: {version}")

        # 2. Minimal onboarding in an empty folder.
        onboard(project)
        if not (project / ".rapid-os" / "config.json").is_file():
            fail("onboarding did not write .rapid-os/config.json")
        print("ok  onboarding")

        # 3. H-29: UTF-8 through a pipe, whatever the console code page is.
        rapid("start", "research", "--spec-file", "-", "--json", raw=json.dumps(SPEC, ensure_ascii=False).encode("utf-8"))
        spec_dir = project / ".rapid-os" / "specs" / SPEC_ID
        if not spec_dir.is_dir():
            found = sorted(p.name for p in (project / ".rapid-os" / "specs").iterdir())
            fail(f"H-29: the spec id came out altered: expected {SPEC_ID!r}, found {found}")
        stored = "\n".join(p.read_text(encoding="utf-8") for p in sorted(spec_dir.rglob("revision.json")))
        for text in (SPEC["title"], "Las fechas son válidas", "El módulo avisa al dueño"):
            if text not in stored and json.dumps(text) not in stored:
                fail(f"H-29: {text!r} was not stored intact")
        altered = [mark for mark in MOJIBAKE if mark in stored]
        if altered:
            fail(f"H-29: the stored spec holds altered text ({altered})")
        print(f"ok  H-29: id {SPEC_ID}, text intact")

        # 4. H-32: an executable that is only a .cmd shim, typed without its extension.
        result = json.loads(rapid("check", "--json", "--", "smoke-tests"))
        if result.get("exit_code") != 0:
            fail(f"H-32: unexpected result of rapid check: {result}")
        print("ok  H-32: rapid check ran the .cmd shim")

        # 5. H-51: what git for Windows does by default (core.autocrlf=true) must not break the evidence of a clone.
        if ".rapid-os/** -text" not in (project / ".gitattributes").read_text(encoding="utf-8"):
            fail("H-51: rapid setup finish did not write the rule to .gitattributes")
        experiments = project / "experiments"
        experiments.mkdir()
        (experiments / "lf.md").write_bytes(b"uno\ndos\n")
        (experiments / "mixed.md").write_bytes(b"uno\r\ndos\n")
        rapid("attach", "experiments/lf.md", "--label", "lf")
        rapid("attach", "experiments/mixed.md", "--label", "mixed")

        def git(cwd: Path, *args: str) -> None:
            result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, timeout=120)
            if result.returncode != 0:
                fail(f"git {' '.join(args)} exited {result.returncode}: {result.stderr.decode('utf-8', 'replace')}")

        run_id = next((project / ".rapid-os" / "runs").iterdir()).name

        def verify_clone(source: Path, name: str) -> subprocess.CompletedProcess:
            git(source, "-c", "core.autocrlf=true", "add", "-A")
            git(source, "-c", "core.autocrlf=true", "commit", "-q", "-m", name)
            git(base, "clone", "-q", "-c", "core.autocrlf=true", str(source), name)
            return subprocess.run(
                [rapid_exe, "evidence", "verify", "--run", run_id], cwd=base / name, env=env, capture_output=True, timeout=120,
                stdin=subprocess.DEVNULL,
            )

        kept = verify_clone(project, "with-rule")
        if kept.returncode != 0:
            fail(f"H-51: the clone does not verify with the rule:\n{kept.stderr.decode('utf-8', 'replace')}")

        # The same files, in a repository that never had the rule.
        no_rule = base / "no-rule"
        shutil.copytree(project, no_rule, ignore=shutil.ignore_patterns(".git", ".gitattributes"))
        git(no_rule, "init", "-q")
        broken = verify_clone(no_rule, "without-rule")
        stderr = broken.stderr.decode("utf-8", "replace")
        if broken.returncode == 0 or "RAPID1205" not in stderr or "RAPID1437" not in stderr:
            fail(f"H-51: expected RAPID1205 and RAPID1437 without the rule, got exit {broken.returncode}:\n{stderr}")
        print("ok  H-51: the clone verifies with the rule and names the cause without it")

        # 6. H-55: Windows PowerShell 5.1 turns accents into '?' in a pipe to a native program.
        piped = base / "piped"
        piped.mkdir()
        onboard(piped)
        source = base / "spec-source.json"
        source.write_text(json.dumps(PIPED_SPEC, ensure_ascii=False), encoding="utf-8")
        spec_file = base / "rapid-spec.json"

        def powershell(script: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                cwd=piped, env=env, capture_output=True, timeout=180, stdin=subprocess.DEVNULL,
            )

        def ps_quote(value: Path | str) -> str:
            return "'" + str(value).replace("'", "''") + "'"

        read_spec = f"$spec = Get-Content -Raw -Encoding UTF8 -Path {ps_quote(source)}; "
        through_pipe = powershell(
            read_spec + f"$spec | & {ps_quote(rapid_exe)} start research --spec-file -; exit $LASTEXITCODE"
        )
        pipe_err = through_pipe.stderr.decode("utf-8", "replace") + through_pipe.stdout.decode("utf-8", "replace")
        runs_dir = piped / ".rapid-os" / "runs"
        if through_pipe.returncode == 0 or "RAPID1415" not in pipe_err:
            fail(f"H-55: the piped spec was not refused with RAPID1415 (exit {through_pipe.returncode}):\n{pipe_err}")
        if runs_dir.is_dir() and any(runs_dir.iterdir()):
            fail("H-55: a run was created from the piped spec")
        print("ok  H-55: the PowerShell pipe is refused with RAPID1415 and no run")

        through_file = powershell(
            read_spec
            + f"$spec | Set-Content -Encoding utf8 -Path {ps_quote(spec_file)}; "
            + f"& {ps_quote(rapid_exe)} start research --spec-file {ps_quote(spec_file)} --json; exit $LASTEXITCODE"
        )
        if through_file.returncode != 0:
            fail(
                f"H-55: the spec by file failed (exit {through_file.returncode}):\n"
                f"{through_file.stdout.decode('utf-8', 'replace')}\n{through_file.stderr.decode('utf-8', 'replace')}"
            )
        if not spec_file.read_bytes().startswith(b"\xef\xbb\xbf"):
            fail("H-55: Set-Content -Encoding utf8 did not write a BOM; the check no longer covers it")
        piped_dir = piped / ".rapid-os" / "specs" / PIPED_SPEC_ID
        if not piped_dir.is_dir():
            found = sorted(p.name for p in (piped / ".rapid-os" / "specs").iterdir())
            fail(f"H-55: expected the spec id {PIPED_SPEC_ID!r}, found {found}")
        revision = json.loads(next(piped_dir.rglob("revision.json")).read_text(encoding="utf-8"))
        if revision["title"] != PIPED_SPEC["title"] or revision["implementation_tasks"] != PIPED_SPEC["tasks"]:
            fail(f"H-55: the spec by file was not stored intact: {revision['title']!r} {revision['implementation_tasks']!r}")
        print(f"ok  H-55: by file (UTF-8 with BOM) the spec is {PIPED_SPEC_ID}, text intact")

        # 7. H-57: the output of the checked command is UTF-8, whatever the code page is.
        checked = subprocess.run(
            [rapid_exe, "check", "--json", "--kind", "test", "--", sys.executable, "-c", VITEST_LIKE],
            cwd=piped, env=env, capture_output=True, timeout=120, stdin=subprocess.DEVNULL,
        )
        check_err = checked.stderr.decode("utf-8", "replace")
        if checked.returncode != 0 or "Traceback" in check_err or "UnicodeDecodeError" in check_err:
            fail(f"H-57: rapid check failed (exit {checked.returncode}):\n{check_err}")
        if '"passed": 3' not in checked.stdout.decode("utf-8", "replace"):
            fail(f"H-57: the test summary was not counted:\n{checked.stdout.decode('utf-8', 'replace')}")
        log = sorted((piped / ".rapid-os" / "scratch" / "checks").rglob("*.log"))[-1].read_text(encoding="utf-8")
        missing = [mark for mark in ("\u2713", "\u23af", "\u276f", "Tests  3 passed (3)") if mark not in log]
        if missing:
            fail(f"H-57: the log lost {missing!r}")
        print("ok  H-57: rapid check logs the UTF-8 output and counts its summary")

        # 8. H-71: a harness's own worktree is not where Rapid OS runs.
        harness_worktree = base / "codex-worktree"
        git(project, "worktree", "add", "-q", "-b", "codex/task", str(harness_worktree))
        for args in (("next", "--json"), ("start", "--resume", "--worktree", "--json")):
            refused = subprocess.run(
                [rapid_exe, *args], cwd=harness_worktree, env=env, capture_output=True, timeout=120,
                stdin=subprocess.DEVNULL,
            )
            refused_err = refused.stderr.decode("utf-8", "replace")
            if refused.returncode != 1 or "RAPID1450" not in refused_err:
                fail(f"H-71: rapid {' '.join(args)} in a harness worktree was not refused (exit {refused.returncode}):\n{refused_err}")
            if os.path.normcase(str(project.resolve())) not in os.path.normcase(refused_err):
                fail(f"H-71: the refusal does not name the main checkout {project}:\n{refused_err}")
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=harness_worktree, env=env, capture_output=True, timeout=120
        ).stdout.decode("utf-8", "replace")
        if status.strip():
            fail(f"H-71: the refused commands wrote in the harness worktree:\n{status}")
        rapid("next", "--json")
        print("ok  H-71: a harness worktree is refused with RAPID1450 naming the main checkout")

        # 9. H-66 and H-68: gate.tests from Windows PowerShell 5.1 with the combined test command Rapid OS builds.
        combined = base / "combined"
        combined.mkdir()
        onboard(combined)
        venv_python = Path(rapid_exe).with_name("python.exe")
        built = subprocess.run(
            [str(venv_python), "-c",
             "import json; from rapid_os.orchestration.setup_conductor import combine_test_commands; "
             "print(json.dumps(combine_test_commands([['backend-tests'], ['frontend-tests']])))"],
            env=env, capture_output=True, timeout=120, stdin=subprocess.DEVNULL,
        )
        if built.returncode != 0:
            fail(f"H-66: could not build the combined test command with {venv_python}:\n{built.stderr.decode('utf-8', 'replace')}")
        config_file = combined / ".rapid-os" / "config.json"
        config = json.loads(config_file.read_text(encoding="utf-8"))
        config["test_command"] = json.loads(built.stdout)
        config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
        feature_spec = base / "feature-spec.json"
        feature_spec.write_text(json.dumps(FEATURE_SPEC), encoding="utf-8")
        rapid("start", "feature", "--spec-file", str(feature_spec), "--json", cwd=combined)
        rapid("task", "start", "T001", cwd=combined)

        def in_powershell(command: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command + "; exit $LASTEXITCODE"],
                cwd=combined, env=env, capture_output=True, timeout=180, stdin=subprocess.DEVNULL,
            )

        gate = in_powershell(f"& {ps_quote(rapid_exe)} check --json --gate gate.tests")
        gate_out = gate.stdout.decode("utf-8", "replace")
        if gate.returncode != 0:
            fail(f"H-66: rapid check --gate gate.tests failed in PowerShell (exit {gate.returncode}):\n{gate_out}\n"
                 f"{gate.stderr.decode('utf-8', 'replace')}")
        result = json.loads(gate_out)
        parts = result.get("components") or []
        counts = [(Path(str(p["command"])).name, p["passed"], p["skipped"], p["counted"]) for p in parts]
        if (result.get("passed"), result.get("skipped")) != (33, 7) or counts != [
            ("backend-tests", 31, 7, True), ("frontend-tests", 2, 0, True)
        ]:
            fail(f"H-66: expected 33 passed and 7 skipped from both components, got {result}")
        if "gate.tests" in result.get("refused_gates", []):
            fail(f"H-66: the configured test command did not satisfy gate.tests: {result}")
        print("ok  H-66: gate.tests from PowerShell 5.1: 33 passed, 7 skipped (backend-tests 31+7, frontend-tests 2)")

        fake = in_powershell(
            f"& {ps_quote(rapid_exe)} check --gate gate.tests -- {ps_quote(sys.executable)} -c \"{FAKE_SUMMARY}\""
        )
        fake_err = fake.stderr.decode("utf-8", "replace") + fake.stdout.decode("utf-8", "replace")
        if fake.returncode != 1 or "RAPID1440" not in fake_err:
            fail(f"H-68: python -c print(...) for gate.tests was not refused with RAPID1440 and exit 1 "
                 f"(exit {fake.returncode}):\n{fake_err}")
        print("ok  H-68: python -c print('==== 31 passed ====') for gate.tests -> RAPID1440, exit 1")

        # 10. H-81: only "s" approves; any other answer changes nothing.
        approval = base / "approval"
        approval.mkdir()
        onboard(approval)
        (approval / "app.py").write_text("x = 1\n", encoding="utf-8")
        git(approval, "add", "-A")
        git(approval, "commit", "-q", "-m", "base")
        rapid("start", "feature", "--spec-file", str(feature_spec), "--json", cwd=approval)
        action: dict = {}
        for _ in range(25):
            action = json.loads(rapid("next", "--json", cwd=approval))["action"]
            if action["kind"] == "await_human_approval":
                break
            for key in ("command", "after"):
                if action.get(key):
                    rapid(*action[key][1:], cwd=approval)
        else:
            fail(f"H-81: the run never reached a human gate; last action: {action}")
        human_gate = action["gate_ids"][0]
        approval_run = next((approval / ".rapid-os" / "runs").iterdir()).name

        def gate_snapshot() -> tuple[str, int]:
            gates = json.loads(rapid("status", "--json", cwd=approval))["run"]["gates"]
            disposition = next(g["disposition"] for g in gates if g["id"] == human_gate)
            counted = subprocess.run(
                [str(venv_python), "-c",
                 "import sys; from pathlib import Path\n"
                 "from rapid_os.adapters.evidence_registry import EvidenceRegistry\n"
                 "root = Path.cwd()\n"
                 "print(sum(e.kind.value == 'review' for e in EvidenceRegistry(root, root / '.rapid-os').list(sys.argv[1])))",
                 approval_run],
                cwd=approval, env=env, capture_output=True, timeout=120, stdin=subprocess.DEVNULL,
            )
            if counted.returncode != 0:
                fail(f"H-81: could not count the reviews:\n{counted.stderr.decode('utf-8', 'replace')}")
            return disposition, int(counted.stdout)

        before = gate_snapshot()
        if before[0] != "pending":
            fail(f"H-81: {human_gate} should be pending before approve, is {before[0]}")

        def powershell_in(cwd: Path, script: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script + "; exit $LASTEXITCODE"],
                cwd=cwd, env=env, capture_output=True, timeout=180, stdin=subprocess.DEVNULL,
            )

        real = powershell_in(approval, f"'s' | & {ps_quote(rapid_exe)} approve {human_gate}")
        real_out = real.stdout.decode("utf-8", "replace") + real.stderr.decode("utf-8", "replace")
        if real.returncode != 1 or "RAPID1310" not in real_out or gate_snapshot() != before:
            fail(f"H-81: rapid approve with a piped 's' was not refused with RAPID1310 (exit {real.returncode}):\n{real_out}")
        prompt_script = approval.parent / "approve_prompt.py"
        prompt_script.write_text(
            "import sys\nfrom pathlib import Path\n"
            "sys.stdout.reconfigure(encoding='utf-8')  # what the smoke decodes; the answer still comes through PS 5.1\n"
            "from rapid_os.core.ancestry import AncestryResult\n"
            "from rapid_os.orchestration.lifecycle import execute_approve\n"
            "root = Path.cwd()\n"
            "code, message = execute_approve(root, root / '.rapid-os', sys.argv[1], is_tty=True, environ={},\n"
            "                                ancestry=AncestryResult(()))\n"
            "print()\nprint(message)\nraise SystemExit(code)\n",
            encoding="utf-8",
        )
        for label, piped_answer in (("empty", "''"), ("x", "'x'")):
            answered = powershell_in(
                approval, f"{piped_answer} | & {ps_quote(venv_python)} {ps_quote(prompt_script)} {human_gate}"
            )
            answered_out = answered.stdout.decode("utf-8", "replace") + answered.stderr.decode("utf-8", "replace")
            if f"¿Apruebas {human_gate}? [s/N]" not in answered_out:
                fail(f"H-81 ({label}): the [s/N] question was not asked:\n{answered_out}")
            if answered.returncode != 1 or "Sin cambios" not in answered_out:
                fail(f"H-81 ({label}): expected exit 1 and 'Sin cambios', got exit {answered.returncode}:\n{answered_out}")
            if gate_snapshot() != before:
                fail(f"H-81 ({label}): the gate or the reviews changed: {before} -> {gate_snapshot()}")
        print(f"ok  H-81: approve {human_gate} with 's' piped -> RAPID1310; an empty answer and 'x' at the [s/N] "
              "-> exit 1, gate still pending")

        # 11. H-79: a standard without the stamp is reported by doctor and regenerated beside the original.
        security = project / ".rapid-os" / "standards" / "security.md"
        from_template = security.read_text(encoding="utf-8")
        stamp_at = from_template.rfind("<!-- rapid-os-standard:")
        if stamp_at < 0:
            fail("H-79: rapid setup finish wrote security.md without the stamp")
        security.write_text(
            from_template[:stamp_at].rstrip("\n") + "\n\n- Regla local del equipo, de una versión anterior.\n",
            encoding="utf-8",
        )
        original = security.read_bytes()
        doctor = powershell_in(project, f"& {ps_quote(rapid_exe)} doctor --json")
        try:
            diagnostics = json.loads(doctor.stdout.decode("utf-8"))["diagnostics"]
        except (ValueError, KeyError) as exc:
            fail(f"H-79: rapid doctor --json gave no report ({exc}):\n{doctor.stdout.decode('utf-8', 'replace')}"
                 f"\n{doctor.stderr.decode('utf-8', 'replace')}")
        flagged = [d for d in diagnostics if d.get("code") == "RAPID1444" and "security.md" in json.dumps(d)]
        if not flagged:
            fail(f"H-79: rapid doctor did not report RAPID1444 for security.md: {[d.get('code') for d in diagnostics]}")
        regenerated = powershell_in(project, f"& {ps_quote(rapid_exe)} setup standards --regenerate")
        regen_out = regenerated.stdout.decode("utf-8", "replace") + regenerated.stderr.decode("utf-8", "replace")
        new_file = security.with_name("security.md.new")
        if regenerated.returncode != 0 or not new_file.is_file():
            fail(f"H-79: --regenerate did not write security.md.new (exit {regenerated.returncode}):\n{regen_out}")
        if security.read_bytes() != original:
            fail("H-79: --regenerate changed the unstamped security.md")
        if "<!-- rapid-os-standard: security sha256=" not in new_file.read_text(encoding="utf-8"):
            fail("H-79: security.md.new has no stamp")
        print("ok  H-79: doctor -> RAPID1444 (security.md without stamp); --regenerate wrote security.md.new, "
              "original untouched")

        # 12. H-82: a process tree that ends in codex.exe is a codex run.
        detected = subprocess.run(
            [str(venv_python), "-c",
             "import json\n"
             "from rapid_os.core.ancestry import read_ancestry\n"
             "from rapid_os.core.harness_detect import detect_harness\n"
             "tree = {100: (200, 'python.exe'), 200: (300, 'rapid.exe'), 300: (400, 'powershell.exe'),\n"
             "        400: (0, 'codex.exe')}\n"
             "ancestry = read_ancestry(100, reader=lambda pid: (*tree[pid], ()))\n"
             "found = detect_harness(None, {}, {'tools': ['claude', 'codex']}, ancestry=ancestry)\n"
             "print(json.dumps([found.harness_id, found.source, [a.name for a in ancestry.ancestors]]))"],
            env=env, capture_output=True, timeout=120, stdin=subprocess.DEVNULL,
        )
        if detected.returncode != 0:
            fail(f"H-82: detect_harness failed:\n{detected.stderr.decode('utf-8', 'replace')}")
        harness_id, source, chain = json.loads(detected.stdout)
        if (harness_id, source) != ("codex", "ancestry") or chain[-1] != "codex.exe":
            fail(f"H-82: expected codex from the ancestry, got {harness_id!r} ({source}) for {chain}")
        print(f"ok  H-82: {' <- '.join(chain)} -> harness codex (source ancestry)")
    print("Windows smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

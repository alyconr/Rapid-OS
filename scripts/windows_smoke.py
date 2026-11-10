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


def fail(message: str) -> None:
    print(f"FAIL {message}")
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
    print("Windows smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

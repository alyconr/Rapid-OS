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
MOJIBAKE = ("Ã", "Â", "�")
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

        def rapid(*args: str, raw: bytes | None = None) -> str:
            result = subprocess.run(
                [rapid_exe, *args], cwd=project, env=env, input=raw, capture_output=True, timeout=120,
                stdin=None if raw is not None else subprocess.DEVNULL,
            )
            out = result.stdout.decode("utf-8", "replace")
            if result.returncode != 0:
                fail(f"rapid {' '.join(args)} exited {result.returncode}:\n{out}\n{result.stderr.decode('utf-8', 'replace')}")
            return out

        # 1. The executable runs and reports a version.
        version = rapid("--version").strip()
        if not version.startswith("Rapid OS "):
            fail(f"unexpected version line: {version!r}")
        print(f"ok  --version: {version}")

        # 2. Minimal onboarding in an empty folder.
        for step in (("stack", "python-fastapi"), ("topology", "backend-only"), ("archetype", "mvp"), ("ai", "no"),
                     ("agents", "claude"), ("test-command", "smoke-tests"), ("services", "none")):
            rapid("setup", "set", *step)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            rapid("setup", "doc", doc, "--skip")
        rapid("setup", "finish")
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
    print("Windows smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

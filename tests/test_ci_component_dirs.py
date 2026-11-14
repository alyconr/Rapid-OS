"""H-78: the security workflow audited nothing and went green.

In the rc.3 e2e (talleres-rc2: python-fastapi in backend/, angular with pnpm in frontend/, topology
fullstack-separated) the job "Dependencias (pip-audit)" said "Sin dependencias declaradas todavía: nada que
auditar." and the TypeScript one "Sin lockfile todavía", both green, because they looked for the manifest and the
lockfile in the root. Now the jobs that read a manifest run once in the folder of each component, a folder with
code and no manifest or lockfile fails saying what is missing and where, and only a folder that does not exist or
has no code yet passes, with a visible warning. `rapid doctor` and `rapid setup ci --regenerate` bring an existing
project's workflows up to date without overwriting one the person edited.

Golden files live in tests/golden/ci/. Regenerate them after an intentional template change with:
    RAPID_UPDATE_GOLDEN=1 python -m unittest tests.test_ci_component_dirs
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from rapid_os.domain.security import (
    ci_component_dirs,
    ci_workflow_path,
    ci_workflow_state,
    render_ci_workflow,
    stamp_ci_workflow,
)
from rapid_os.domain.setup import DocState, SetupState, StackChoice
from rapid_os.orchestration.setup_apply import expected_ci_workflows
from tests.test_no_git import GitIsolated

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
GOLDEN = ROOT / "tests" / "golden" / "ci"
RC3_PYTHON = ROOT / "tests" / "fixtures" / "ci" / "rc3-python-security.yml"
DOCS = ("brief", "business", "data-model", "architecture", "deployment")


def state_for(topology: str, stacks: dict[str, str], archetype: str = "mvp") -> SetupState:
    return SetupState(
        stacks={c: StackChoice(s, "catalog") for c, s in stacks.items()}, topology=topology, archetype=archetype,
        ai=False, agents=("codex",), test_command=(), services=(),
        docs={doc: DocState("skipped") for doc in DOCS},
    )


TALLERES = state_for("fullstack-separated", {"backend": "python-fastapi", "frontend": "angular"})
BACKEND_ONLY = state_for("backend-only", {"backend": "python-fastapi"})
FRONT_END_ONLY = state_for("front-end-only", {"frontend": "react-vite"})
NODE_FULLSTACK = state_for("fullstack-separated", {"backend": "node-nestjs", "frontend": "angular"})


def workflows(state: SetupState) -> dict[str, str]:
    return {path: content for path, _language, content in expected_ci_workflows(TEMPLATES, state)}


def matrix_dirs(text: str) -> list[list[str]]:
    return [json.loads(m) for m in re.findall(r"^        dir: (\[.*\])$", text, flags=re.MULTILINE)]


def step_script(text: str, step_name: str) -> str:
    """The `run: |` block of the step called `step_name` (the first one), without its indentation."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {step_name}")
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    indent = len(lines[run + 1]) - len(lines[run + 1].lstrip())
    body = []
    for line in lines[run + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        body.append(line[indent:])
    return "\n".join(body).rstrip() + "\n"


def find_bash() -> str | None:
    """A POSIX bash: Git for Windows' on Windows (never WSL's launcher), the PATH's elsewhere."""
    if os.name == "nt":
        git = shutil.which("git")
        if git:  # <Git>/cmd/git.exe or <Git>/mingw64/bin/git.exe
            for parent in Path(git).parents:
                candidate = parent / "bin" / "bash.exe"
                if candidate.is_file():
                    return str(candidate)
        return None
    return shutil.which("bash")


BASH = find_bash()


class ComponentFoldersTests(unittest.TestCase):
    def test_fullstack_separated_audits_each_component_in_its_folder(self):
        found = workflows(TALLERES)
        python = found[ci_workflow_path("python")]
        typescript = found[ci_workflow_path("typescript")]
        self.assertEqual(matrix_dirs(python), [["backend"]])
        self.assertEqual(matrix_dirs(typescript), [["frontend"]])
        self.assertIn("working-directory: ${{ matrix.dir }}", python)
        self.assertIn(
            'uv export --frozen --format requirements.txt --no-emit-project -o "$RUNNER_TEMP/requirements-audit.txt"', python
        )
        self.assertIn('pip-audit --disable-pip -r "$RUNNER_TEMP/requirements-audit.txt"', python)
        self.assertIn("package_json_file: ${{ matrix.dir }}/package.json", typescript)
        self.assertIn("pnpm audit --audit-level high", typescript)
        self.assertNotIn("{RAPID_COMPONENT_DIRS}", python + typescript)

    def test_one_folder_topologies_stay_in_the_root(self):
        self.assertEqual(matrix_dirs(workflows(BACKEND_ONLY)[ci_workflow_path("python")]), [["."]])
        self.assertEqual(matrix_dirs(workflows(FRONT_END_ONLY)[ci_workflow_path("typescript")]), [["."]])
        baas = state_for("fullstack-baas", {"frontend": "react-vite", "baas": "supabase"})
        self.assertEqual(ci_component_dirs({c: s.id for c, s in baas.stacks.items()}), {"typescript": ["."]})

    def test_two_components_of_one_language_are_both_audited(self):
        typescript = workflows(NODE_FULLSTACK)[ci_workflow_path("typescript")]
        self.assertEqual(matrix_dirs(typescript), [["backend", "frontend"]])

    def test_every_template_with_a_manifest_job_takes_the_folders(self):
        for template in sorted((TEMPLATES / "ci").glob("*-security.yml")):
            language = template.name.removesuffix("-security.yml")
            with self.subTest(language=language):
                text = render_ci_workflow(template.read_text("utf-8"), archetype="mvp", language=language, dirs=["backend"])
                self.assertNotIn("{RAPID_COMPONENT_DIRS}", text)
                if language in ("java", "kotlin"):  # GitHub's dependency graph: the whole repository
                    continue
                self.assertIn('dir: ["backend"]', text)
                self.assertIn("::warning title=Nada que auditar::", text)
                self.assertIn('>> "$GITHUB_STEP_SUMMARY"', text)
                self.assertIn("::error title=Falta", text)

    def test_each_language_has_its_own_workflow_name(self):
        found = workflows(TALLERES)
        names = {re.search(r"^name: (.+)$", text, flags=re.MULTILINE).group(1) for text in found.values()}
        self.assertEqual(names, {"rapid-security-python", "rapid-security-typescript"})

    def test_the_workflows_match_the_golden_files(self):
        update = os.environ.get("RAPID_UPDATE_GOLDEN") == "1"
        cases = {
            "fullstack-separated": TALLERES,
            "backend-only": BACKEND_ONLY,
            "front-end-only": FRONT_END_ONLY,
            "fullstack-separated-node": NODE_FULLSTACK,
        }
        for case, state in cases.items():
            for path, content in workflows(state).items():
                golden = GOLDEN / case / Path(path).name
                with self.subTest(golden=str(golden.relative_to(ROOT))):
                    if update:
                        golden.parent.mkdir(parents=True, exist_ok=True)
                        golden.write_text(content, encoding="utf-8", newline="\n")
                    self.assertEqual(content, golden.read_text("utf-8").replace("\r\n", "\n"))


@unittest.skipUnless(BASH, "needs a POSIX bash (Git for Windows' bash on Windows)")
class StepScriptTests(unittest.TestCase):
    """The scripts of the steps, run as GitHub runs them (bash, with GITHUB_OUTPUT and GITHUB_STEP_SUMMARY)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.output = self.base / "output"
        self.summary = self.base / "summary"
        self.calls = self.base / "calls"
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for tool in ("python", "uv", "pip-audit"):  # record the call instead of reaching the network
            stub = self.bin / tool
            stub.write_text(f'#!/usr/bin/env bash\necho "{tool} $*" >> "$CALLS"\n', encoding="utf-8", newline="\n")
            stub.chmod(0o755)
        found = workflows(TALLERES)
        self.python = found[ci_workflow_path("python")]
        self.typescript = found[ci_workflow_path("typescript")]

    def run_step(self, text: str, step: str, folder: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        for path in (self.output, self.summary, self.calls):
            path.write_text("", encoding="utf-8")
        script = self.base / "step.sh"
        script.write_text(step_script(text, step), encoding="utf-8", newline="\n")
        env = {
            **os.environ, "DIR": folder, "GITHUB_OUTPUT": str(self.output), "GITHUB_STEP_SUMMARY": str(self.summary),
            "RUNNER_TEMP": str(self.base), "CALLS": str(self.calls),
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
        }
        return subprocess.run([BASH, str(script)], cwd=cwd or self.repo, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)

    def outputs(self) -> dict[str, str]:
        pairs = [line.split("=", 1) for line in self.output.read_text("utf-8").splitlines() if "=" in line]
        return {k: v for k, v in pairs}

    def write(self, relative: str, text: str = "x\n") -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    # Python
    def test_an_empty_repository_warns_and_passes(self):
        result = self.run_step(self.python, "Comprobar que la carpeta del componente tiene código", "backend")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.outputs()["audit"], "false")
        self.assertIn("::warning title=Nada que auditar::backend no existe", result.stdout)
        self.assertIn("Nada que auditar: backend", self.summary.read_text("utf-8"))

    def test_an_empty_folder_warns_and_passes(self):
        (self.repo / "backend").mkdir()
        result = self.run_step(self.python, "Comprobar que la carpeta del componente tiene código", "backend")
        self.assertEqual((result.returncode, self.outputs()["audit"]), (0, "false"))

    def test_code_without_a_manifest_fails_saying_what_and_where(self):
        self.write("backend/app/main.py")
        check = self.run_step(self.python, "Comprobar que la carpeta del componente tiene código", "backend")
        self.assertEqual(self.outputs()["audit"], "true", check.stdout)
        audit = self.run_step(self.python, "Auditar las dependencias declaradas", "backend", cwd=self.repo / "backend")
        self.assertEqual(audit.returncode, 1)
        self.assertIn("::error title=Faltan las dependencias::backend tiene código Python", audit.stdout)
        self.assertIn("uv.lock, requirements.txt ni pyproject.toml", audit.stdout)
        self.assertEqual(self.calls.read_text("utf-8"), "")  # nothing installed

    def test_a_uv_lock_is_exported_and_audited_with_pip_audit(self):
        self.write("backend/app/main.py")
        self.write("backend/pyproject.toml", "[project]\nname = 'x'\n")
        self.write("backend/uv.lock")
        audit = self.run_step(self.python, "Auditar las dependencias declaradas", "backend", cwd=self.repo / "backend")
        self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)
        calls = self.calls.read_text("utf-8").splitlines()
        self.assertEqual(calls[0], "python -m pip install pip-audit==2.10.1 uv==0.13.8")
        self.assertEqual(
            calls[1], f"uv export --frozen --format requirements.txt --no-emit-project -o {self.base}/requirements-audit.txt"
        )
        self.assertEqual(calls[2], f"pip-audit --disable-pip -r {self.base}/requirements-audit.txt")

    def test_requirements_txt_is_audited_as_before(self):
        self.write("backend/requirements.txt", "fastapi==0.1\n")
        audit = self.run_step(self.python, "Auditar las dependencias declaradas", "backend", cwd=self.repo / "backend")
        self.assertEqual(audit.returncode, 0, audit.stdout)
        self.assertIn("pip-audit -r requirements.txt", self.calls.read_text("utf-8"))

    # TypeScript
    def detect(self, folder="frontend"):
        return self.run_step(self.typescript, "Detectar el gestor de paquetes por el lockfile de la carpeta", folder)

    def test_pnpm_in_the_frontend_folder(self):
        self.write("frontend/src/main.ts")
        self.write("frontend/package.json", "{}\n")
        self.write("frontend/pnpm-lock.yaml")
        self.write("pnpm-lock.yaml")  # a lockfile in the root is not the frontend's
        result = self.detect()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.outputs(), {"manager": "pnpm", "pnpm_version": "10"})

    def test_the_pnpm_version_comes_from_the_folders_package_json(self):
        self.write("frontend/package.json", '{"packageManager": "pnpm@10.34.9"}\n')
        self.write("frontend/pnpm-lock.yaml")
        self.detect()
        self.assertEqual(self.outputs(), {"manager": "pnpm", "pnpm_version": ""})

    def test_a_package_json_without_a_lockfile_fails(self):
        self.write("frontend/src/main.ts")
        self.write("frontend/package.json", "{}\n")
        result = self.detect()
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error title=Falta el lockfile::frontend tiene package.json pero ningún lockfile", result.stdout)

    def test_code_without_package_json_fails(self):
        self.write("frontend/src/main.ts")
        result = self.detect()
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error title=Faltan las dependencias::frontend tiene código JavaScript/TypeScript", result.stdout)

    def test_a_missing_frontend_folder_warns_and_passes(self):
        result = self.detect()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.outputs(), {"manager": "none"})
        self.assertIn("::warning title=Nada que auditar::frontend no existe", result.stdout)
        self.assertIn("Nada que auditar: frontend", self.summary.read_text("utf-8"))


class WorkflowStateTests(unittest.TestCase):
    def test_states(self):
        current = stamp_ci_workflow("name: x\njobs: {}\n", "python")
        self.assertEqual(ci_workflow_state(current, current), "current")
        self.assertEqual(ci_workflow_state(current.replace("\n", "\r\n"), current), "current")  # core.autocrlf
        older = stamp_ci_workflow("name: old\n", "python")
        self.assertEqual(ci_workflow_state(older, current), "outdated")
        self.assertEqual(ci_workflow_state(older.replace("old", "mine"), current), "edited")
        legacy = RC3_PYTHON.read_text("utf-8")
        from rapid_os.domain.ci_legacy import LEGACY_CI_DIGESTS

        self.assertEqual(ci_workflow_state(legacy, current, LEGACY_CI_DIGESTS), "outdated")
        self.assertEqual(ci_workflow_state(legacy + "# mío\n", current, LEGACY_CI_DIGESTS), "edited")


class DoctorAndRegenerateTests(GitIsolated):
    def finish(self, state: SetupState = TALLERES):
        path = self.root / ".rapid-os" / "setup.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
        result = self.rapid("setup", "finish")
        self.assertEqual(result.returncode, 0, result.stderr)

    def doctor_1443(self):
        report = json.loads(self.rapid("doctor", "--json").stdout)
        return [d for d in report["diagnostics"] if d["code"] == "RAPID1443"]

    def ci(self, *args):
        result = self.rapid("setup", "ci", "--json", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return {item["file"]: item for item in json.loads(result.stdout)["workflows"]}

    @property
    def python_workflow(self) -> Path:
        return self.root / ci_workflow_path("python")

    def test_a_new_project_is_current(self):
        self.finish()
        self.assertTrue(self.python_workflow.read_text("utf-8").startswith("# rapid-os-ci: python sha256="))
        self.assertEqual({item["status"] for item in self.ci().values()}, {"current"})
        self.assertEqual(self.doctor_1443(), [])

    def test_an_rc3_workflow_nobody_edited_is_replaced(self):
        self.finish()
        self.python_workflow.write_text(RC3_PYTHON.read_text("utf-8"), encoding="utf-8")
        [diagnostic] = self.doctor_1443()
        self.assertEqual(diagnostic["level"], "warning")
        self.assertIn("rapid-security-python.yml lo generó una versión anterior", diagnostic["message"])
        self.assertIn("rapid setup ci --regenerate", diagnostic["hint"])
        status = self.ci()[ci_workflow_path("python")]
        self.assertEqual(status["status"], "outdated")
        regenerated = self.ci("--regenerate")[ci_workflow_path("python")]
        self.assertEqual((regenerated["action"], regenerated["written"]), ("replaced", ci_workflow_path("python")))
        self.assertIn('dir: ["backend"]', self.python_workflow.read_text("utf-8"))
        backups = list((self.root / ".rapid-os" / "backups").glob("rapid-security-python.yml.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.doctor_1443(), [])

    def test_an_edited_workflow_is_not_overwritten(self):
        self.finish()
        edited = self.python_workflow.read_text("utf-8") + "# un paso mío\n"
        self.python_workflow.write_text(edited, encoding="utf-8")
        [diagnostic] = self.doctor_1443()
        self.assertEqual(diagnostic["level"], "info")
        regenerated = self.ci("--regenerate")[ci_workflow_path("python")]
        self.assertEqual((regenerated["status"], regenerated["action"]), ("edited", "new"))
        self.assertEqual(self.python_workflow.read_text("utf-8"), edited)
        new = self.root / (ci_workflow_path("python") + ".new")
        self.assertEqual(new.read_text("utf-8"), workflows(TALLERES)[ci_workflow_path("python")])
        text = self.rapid("setup", "ci", "--regenerate").stdout
        self.assertIn("no se toca; el nuevo está en .github/workflows/rapid-security-python.yml.new", text)

    def test_a_missing_workflow_is_written(self):
        self.finish()
        self.python_workflow.unlink()
        self.assertEqual(self.ci()[ci_workflow_path("python")]["status"], "missing")
        self.assertEqual(self.ci("--regenerate")[ci_workflow_path("python")]["action"], "written")
        self.assertTrue(self.python_workflow.is_file())

    def test_the_text_output_names_the_command(self):
        self.finish()
        self.python_workflow.write_text(RC3_PYTHON.read_text("utf-8"), encoding="utf-8")
        text = self.rapid("setup", "ci").stdout
        self.assertIn("rapid-security-python.yml: generado por una versión anterior de Rapid OS", text)
        self.assertIn("rapid setup ci --regenerate", text)


if __name__ == "__main__":
    unittest.main()

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from rapid_os.cli import main as cli_main
from rapid_os.domain.catalog import (
    CatalogError,
    build_generic_stack,
    load_catalog,
    load_setup_doc_banks,
    load_stack_questions,
)
from rapid_os.domain.project import Confidence, Evidence, ProjectFact, ProjectModel
from rapid_os.domain.validation import (
    infer_stack,
    infer_topology,
    validate_stack_topology,
    validate_templates,
)

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"

# Tabla congelada del comportamiento previo a los sidecars (F5.1): códigos no informativos.
EXPECTED_STACK_TOPOLOGY = {
    ("docs-modern", "doc-site"): [],
    ("docs-modern", "front-end-only"): ["RAPID402"],
    ("docs-modern", "fullstack-baas"): ["RAPID402"],
    ("docs-modern", "fullstack-separated"): ["RAPID402"],
    ("frontend-creative", "doc-site"): ["RAPID403"],
    ("frontend-creative", "front-end-only"): [],
    ("frontend-creative", "fullstack-baas"): [],
    ("frontend-creative", "fullstack-separated"): [],
    ("nodejs-ai", "doc-site"): ["RAPID403"],
    ("nodejs-ai", "front-end-only"): ["RAPID404"],
    ("nodejs-ai", "fullstack-baas"): [],
    ("nodejs-ai", "fullstack-separated"): [],
    ("python-ai", "doc-site"): ["RAPID403"],
    ("python-ai", "front-end-only"): ["RAPID404"],
    ("python-ai", "fullstack-baas"): ["RAPID405"],
    ("python-ai", "fullstack-separated"): [],
    ("web-modern", "doc-site"): ["RAPID403"],
    ("web-modern", "front-end-only"): [],
    ("web-modern", "fullstack-baas"): [],
    ("web-modern", "fullstack-separated"): [],
}


def _diagnostic_codes(stack, topology):
    with tempfile.TemporaryDirectory() as tmp:
        standards = Path(tmp) / "standards"
        standards.mkdir()
        for target, folder, name in (
            ("tech-stack.md", "stacks", stack),
            ("topology.md", "topologies", topology),
        ):
            text = (TEMPLATES / folder / f"{name}.md").read_text(encoding="utf-8")
            (standards / target).write_text(text, encoding="utf-8")
        report = validate_stack_topology(Path(tmp), TEMPLATES)
    return sorted(d.code for d in report.diagnostics if d.level != "info")


def _fact(category, value):
    return ProjectFact(category, value, Confidence.HIGH, (Evidence(Path("marker"), 'test'),))


def _copy_templates(tmp: str) -> Path:
    target = Path(tmp) / "templates"
    for folder in ("stacks", "topologies", "archetypes", "mcp"):
        shutil.copytree(TEMPLATES / folder, target / folder)
    return target


def _run_rapid(cwd: Path, *argv: str):
    return subprocess.run(
        [sys.executable, str(REPO / "rapid.py"), *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "CLAUDECODE": "", "PYTHONPATH": str(REPO)},
    )


class StackTopologyParityTests(unittest.TestCase):
    def test_table_covers_every_stack_and_topology_pair(self):
        stacks = {p.stem for p in (TEMPLATES / "stacks").glob("*.md")}
        topologies = {p.stem for p in (TEMPLATES / "topologies").glob("*.md")}
        self.assertEqual(
            set(EXPECTED_STACK_TOPOLOGY),
            {(s, t) for s in stacks for t in topologies},
        )

    def test_stack_topology_table_matches_legacy_behavior(self):
        for (stack, topology), expected in EXPECTED_STACK_TOPOLOGY.items():
            with self.subTest(stack=stack, topology=topology):
                self.assertEqual(_diagnostic_codes(stack, topology), expected)


class CatalogSidecarTests(unittest.TestCase):
    def test_every_stack_and_topology_has_a_valid_sidecar(self):
        catalog = load_catalog(TEMPLATES)
        for folder, entries in (("stacks", catalog.stacks), ("topologies", catalog.topologies)):
            for markdown in (TEMPLATES / folder).glob("*.md"):
                with self.subTest(template=markdown.name):
                    self.assertIn(markdown.stem, entries)
        self.assertIn("generic", catalog.stacks)
        self.assertEqual(
            set(catalog.stacks["generic"].compatible_topologies),
            set(catalog.topologies) - {"doc-site"},
        )

    def test_default_topology_is_compatible_and_only_docs_default_to_doc_site(self):
        catalog = load_catalog(TEMPLATES)
        for stack_id, entry in catalog.stacks.items():
            with self.subTest(stack=stack_id):
                self.assertTrue(catalog.is_compatible(stack_id, entry.default_topology))
                if stack_id != "docs-modern":
                    self.assertNotEqual(entry.default_topology, "doc-site")

    def test_setup_banks_load_and_cover_required_documents(self):
        banks = load_setup_doc_banks(TEMPLATES)
        self.assertEqual(set(banks), {"brief", "business", "data-model", "architecture"})
        for bank in banks.values():
            self.assertTrue(bank.questions and bank.required_sections)
        self.assertEqual(
            {q.id for q in load_stack_questions(TEMPLATES)},
            {"product_type", "team_language", "hosting", "relational_data", "ai", "realtime"},
        )

    def test_broken_sidecars_raise_rapid1401(self):
        cases = {
            "missing field": lambda d: d.pop("language"),
            "id mismatch": lambda d: d.update(id="other"),
            "bad schema": lambda d: d.update(schema_version=2),
            "unknown topology": lambda d: d.update(compatible_topologies=["nope"]),
            "default outside list": lambda d: d.update(default_topology="doc-site"),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                templates = _copy_templates(tmp)
                sidecar = templates / "stacks" / "web-modern.json"
                data = json.loads(sidecar.read_text(encoding="utf-8"))
                mutate(data)
                sidecar.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(CatalogError) as ctx:
                    load_catalog(templates)
                self.assertEqual(ctx.exception.code, "RAPID1401")
                report = validate_templates(templates)
                self.assertIn("RAPID1401", [d.code for d in report.diagnostics])

    def test_unreadable_json_and_missing_sidecar_raise_rapid1401(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates = _copy_templates(tmp)
            sidecar = templates / "topologies" / "doc-site.json"
            sidecar.write_text("{", encoding="utf-8")
            with self.assertRaises(CatalogError):
                load_catalog(templates)
            sidecar.unlink()
            with self.assertRaises(CatalogError):
                load_catalog(templates)

    def test_init_with_broken_sidecar_reports_rapid1401_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates = _copy_templates(tmp)
            (templates / "stacks" / "web-modern.json").write_text("[]", encoding="utf-8")
            project = Path(tmp) / "project"
            project.mkdir()
            stdout = io.StringIO()
            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project / ".rapid-os"
            ), patch.object(
                cli_main, "CONFIG_FILE", project / ".rapid-os" / "config.json"
            ), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main.init_project(Namespace(stack="web-modern", yes=True, no_scan=True))
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("RAPID1401", stdout.getvalue())
            self.assertNotIn("Traceback", stdout.getvalue())


class GenericStackTests(unittest.TestCase):
    def test_build_generic_stack_is_pure_and_lists_detected_facts(self):
        model = ProjectModel(
            root=Path("."),
            facts=(
                _fact("language", "python"),
                _fact("package_manager", "uv"),
                _fact("framework", "fastapi"),
                _fact("testing", "pytest"),
            ),
        )
        text = build_generic_stack(model)
        self.assertEqual(text, build_generic_stack(model))
        for expected in ("Python", "uv", "fastapi", "pytest", "existing conventions"):
            self.assertIn(expected, text)
        self.assertEqual(infer_stack(text), "generic")

    def test_empty_model_renders_not_detected(self):
        text = build_generic_stack(ProjectModel(root=Path(".")))
        self.assertIn("not detected", text)
        self.assertEqual(infer_stack(text), "generic")


class InitDefaultsTests(unittest.TestCase):
    def test_pyproject_only_project_gets_generic_stack_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "pyproject.toml").write_text("", encoding="utf-8")
            init = _run_rapid(project, "init", "--yes")
            self.assertEqual(init.returncode, 0, init.stderr)
            standards = project / ".rapid-os" / "standards"
            stack = (standards / "tech-stack.md").read_text(encoding="utf-8")
            self.assertEqual(infer_stack(stack), "generic")
            self.assertIn("Python", stack)
            topology = infer_topology((standards / "topology.md").read_text(encoding="utf-8"))
            self.assertIsNotNone(topology)
            self.assertNotEqual(topology, "doc-site")
            validate = _run_rapid(project, "validate")
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

    def test_nextjs_project_still_selects_web_modern(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "package.json").write_text(
                json.dumps({"dependencies": {"next": "14.0.0", "react": "18.0.0"}}),
                encoding="utf-8",
            )
            init = _run_rapid(project, "init", "--yes")
            self.assertEqual(init.returncode, 0, init.stderr)
            stack = (project / ".rapid-os" / "standards" / "tech-stack.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(infer_stack(stack), "web-modern")


class PackagingTests(unittest.TestCase):
    def test_pyproject_ships_every_templates_directory_with_json(self):
        try:
            import tomllib
        except ImportError:  # Python 3.10
            self.skipTest("tomllib requires Python 3.11+")
        config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]
        packages = set(config["packages"])
        package_dir = config["package-dir"]
        package_data = config["package-data"]
        self.assertIn(
            "recursive-include templates *.md *.json",
            (REPO / "MANIFEST.in").read_text(encoding="utf-8"),
        )
        for directory in sorted({p.parent for p in TEMPLATES.rglob("*.json")}):
            relative = directory.relative_to(REPO).as_posix()
            package = "rapid_os." + relative.replace("/", ".")
            with self.subTest(package=package):
                self.assertIn(package, packages)
                self.assertEqual(package_dir.get(package), relative)
                self.assertIn("*.json", package_data.get(package, []))


if __name__ == "__main__":
    unittest.main()

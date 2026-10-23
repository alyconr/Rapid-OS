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
    GENERIC_STACK_HEADER,
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

# Tabla generada ejecutando el código de 7cf4878 (antes del refactor): códigos no informativos.
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
    # python-api (added with the catalog, not part of the 7cf4878 table): compatible with both backends.
    ("python-api", "doc-site"): ["RAPID403"],
    ("python-api", "front-end-only"): ["RAPID404"],
    ("python-api", "fullstack-baas"): [],
    ("python-api", "fullstack-separated"): [],
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


LEGACY_DEFAULT_TOPOLOGY_BY_STACK = {
    "docs-modern": "doc-site",
    "python-ai": "fullstack-separated",
    "nodejs-ai": "fullstack-separated",
    "web-modern": "fullstack-separated",
    "frontend-creative": "front-end-only",
}


def _legacy_default_topology(stack_name, suggested_topology, topologies):
    """Copy of default_topology_for_stack from 7cf4878 (oracle)."""
    if stack_name == "docs-modern":
        return "doc-site" if "doc-site" in topologies else None
    if (
        suggested_topology in topologies
        and suggested_topology != "doc-site"
        and not (suggested_topology == "front-end-only" and stack_name in ("python-ai", "nodejs-ai"))
    ):
        return suggested_topology
    required = LEGACY_DEFAULT_TOPOLOGY_BY_STACK.get(stack_name)
    if required in topologies:
        return required
    for name in topologies:
        if name != "doc-site":
            return name
    return None


class DefaultTopologyTests(unittest.TestCase):
    def test_matches_legacy_function_for_every_stack_and_suggestion(self):
        catalog = load_catalog(TEMPLATES)
        topologies = sorted(catalog.topologies)
        # The oracle knows the stacks that existed in 7cf4878; later stacks have their own test.
        for stack in sorted(LEGACY_DEFAULT_TOPOLOGY_BY_STACK):
            for suggestion in [None, *topologies]:
                with self.subTest(stack=stack, suggestion=suggestion):
                    self.assertEqual(
                        catalog.default_topology_for_stack(stack, suggestion, topologies),
                        _legacy_default_topology(stack, suggestion, topologies),
                    )

    def test_python_api_behaves_like_python_ai_but_without_ai(self):
        catalog = load_catalog(TEMPLATES)
        topologies = sorted(catalog.topologies)
        for suggestion in [None, *topologies]:
            with self.subTest(suggestion=suggestion):
                self.assertEqual(
                    catalog.default_topology_for_stack("python-api", suggestion, topologies),
                    catalog.default_topology_for_stack("python-ai", suggestion, topologies),
                )
        entry = catalog.stacks["python-api"]
        self.assertEqual(entry.compatible_topologies, ("fullstack-baas", "fullstack-separated"))
        self.assertEqual(entry.default_topology, "fullstack-separated")
        self.assertEqual(entry.fits, ("APIs de negocio en Python",))
        self.assertEqual(catalog.stacks["python-ai"].fits, ("agentes de IA y pipelines de datos",))
        text = (TEMPLATES / "stacks" / "python-api.md").read_text(encoding="utf-8")
        for name in ("LangChain", "CrewAI"):
            self.assertNotIn(name, text)
        for name in ("FastAPI", "Pydantic V2", "SQLAlchemy 2", "Alembic", "PostgreSQL", "pytest", "httpx"):
            self.assertIn(name, text)

    def test_infer_stack_recognizes_python_api_before_python_ai(self):
        from rapid_os.domain.validation import infer_stack

        for stack in ("python-api", "python-ai"):
            text = (TEMPLATES / "stacks" / f"{stack}.md").read_text(encoding="utf-8")
            self.assertEqual(infer_stack(text), stack)

    def test_web_modern_defaults_to_fullstack_separated(self):
        catalog = load_catalog(TEMPLATES)
        self.assertEqual(
            catalog.default_topology_for_stack("web-modern", None, sorted(catalog.topologies)),
            "fullstack-separated",
        )


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
        self.assertEqual(set(banks), {"brief", "business", "data-model", "architecture", "deployment"})
        for bank in banks.values():
            self.assertTrue(bank.questions and bank.required_sections)
            for section in bank.required_sections:
                self.assertGreaterEqual(len(section.titles), 2)
        brief_titles = {t for sec in banks["brief"].required_sections for t in sec.titles}
        self.assertTrue({"Problema", "Problem"} <= brief_titles)
        stories = next(q for q in banks["brief"].questions if q.id == "stories")
        self.assertIn("- [ ] H001:", stories.text)
        self.assertEqual(
            {q.id for q in load_stack_questions(TEMPLATES)},
            {"product_type", "team_language", "hosting", "relational_data", "ai", "realtime"},
        )

    def test_setup_banks_have_the_agreed_values(self):
        expected = {
            "brief": ("docs/PRODUCT_BRIEF.md", "HIGH", 5000, {
                "problem": ("Problema", "Problem"), "users": ("Usuarios", "Users"),
                "stories": ("Historias", "Stories")}),
            "business": ("docs/BUSINESS_RULES.md", "HIGH", 6000, {
                "goal": ("Objetivo", "Goal"),
                "rules": ("Reglas no negociables", "Non-negotiable rules"),
                "constraints": ("Restricciones", "Constraints"),
                "assumptions": ("Supuestos", "Assumptions"),
                "glossary": ("Glosario", "Glossary")}),
            "data-model": ("docs/DATA_MODEL.md", "MEDIUM", 5000, {
                "entities": ("Entidades", "Entities"),
                "relationships": ("Relaciones", "Relationships"),
                "invariants": ("Invariantes", "Invariants"),
                "states": ("Estados", "States")}),
            "architecture": ("docs/ARCHITECTURE.md", "HIGH", 6000, {
                "decision": ("Decisión", "Decision"), "rationale": ("Por qué", "Rationale"),
                "alternatives": ("Alternativas descartadas", "Rejected alternatives"),
                "consequences": ("Consecuencias", "Consequences"),
                "modules": ("Módulos", "Modules"),
                "dependency_rules": ("Reglas de dependencia", "Dependency rules"),
                "services": ("Servicios de infraestructura", "Infrastructure services")}),
            "deployment": ("docs/DEPLOYMENT.md", "LOW", 5000, {
                "target": ("Destino", "Target"),
                "config": ("Configuración y secretos", "Configuration and secrets"),
                "managed": ("Servicios gestionados", "Managed services"),
                "verification": ("Verificación y reversión", "Verification and rollback")}),
        }
        banks = load_setup_doc_banks(TEMPLATES)
        for doc_id, (file, priority, max_chars, sections) in expected.items():
            with self.subTest(doc=doc_id):
                bank = banks[doc_id]
                self.assertEqual((bank.file, bank.context_priority, bank.max_chars), (file, priority, max_chars))
                self.assertEqual({s.id: s.titles for s in bank.required_sections}, sections)
                self.assertEqual([s.id for s in bank.required_sections], list(sections))
                question_ids = {question.id for question in bank.questions}
                for section_id in sections:
                    self.assertIn(section_id, question_ids)
                for question in bank.questions:
                    self.assertIsInstance(question.required, bool)

    def test_bank_section_without_matching_question_raises_rapid1401(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(TEMPLATES / "setup", Path(tmp) / "setup")
            brief = Path(tmp) / "setup" / "docs" / "brief.json"
            data = json.loads(brief.read_text(encoding="utf-8"))
            data["questions"] = [q for q in data["questions"] if q["id"] != "users"]
            brief.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(CatalogError):
                load_setup_doc_banks(Path(tmp))

    def test_rapid404_message_names_compatible_topologies_unless_backend_case(self):
        def message(stack, topology):
            with tempfile.TemporaryDirectory() as tmp:
                templates = _copy_templates(tmp)
                sidecar = templates / "stacks" / "python-ai.json"
                data = json.loads(sidecar.read_text(encoding="utf-8"))
                data.update(compatible_topologies=["fullstack-separated"], default_topology="fullstack-separated")
                sidecar.write_text(json.dumps(data), encoding="utf-8")
                standards = Path(tmp) / "standards"
                standards.mkdir()
                (standards / "tech-stack.md").write_text(
                    (templates / "stacks" / f"{stack}.md").read_text(encoding="utf-8"), encoding="utf-8")
                (standards / "topology.md").write_text(
                    (templates / "topologies" / f"{topology}.md").read_text(encoding="utf-8"), encoding="utf-8")
                report = validate_stack_topology(Path(tmp), templates)
            return next(d.message for d in report.diagnostics if d.code == "RAPID404")

        self.assertIn("requires backend/database capabilities", message("python-ai", "front-end-only"))
        generic = message("python-ai", "fullstack-baas")
        self.assertNotIn("requires backend/database capabilities", generic)
        self.assertEqual(
            generic,
            "python-ai is not compatible with fullstack-baas (compatible: fullstack-separated).",
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

    def test_unreadable_sidecar_json_raises_rapid1401(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates = _copy_templates(tmp)
            (templates / "topologies" / "doc-site.json").write_text("{", encoding="utf-8")
            with self.assertRaises(CatalogError):
                load_catalog(templates)

    def test_template_without_sidecar_is_a_warning_and_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates = _copy_templates(tmp)
            (templates / "stacks" / "custom.md").write_text("# Custom stack\n", encoding="utf-8")
            (templates / "topologies" / "edge.md").write_text("# Edge\n", encoding="utf-8")
            (templates / "topologies" / "doc-site.json").unlink()
            catalog = load_catalog(templates)
            self.assertEqual(catalog.sidecarless_stacks, ("custom",))
            self.assertEqual(set(catalog.sidecarless_topologies), {"edge", "doc-site"})
            self.assertTrue(catalog.is_compatible("custom", "edge"))
            self.assertTrue(catalog.is_compatible("custom", "fullstack-baas"))
            self.assertFalse(catalog.is_compatible("custom", "doc-site"))
            report = validate_templates(templates)
            self.assertFalse(report.has_errors, [d.message for d in report.diagnostics if d.level == "error"])
            warnings = [d for d in report.diagnostics if d.code == "RAPID1412"]
            self.assertEqual(len(warnings), 3)
            self.assertTrue(all(d.level == "warning" for d in warnings))

    def test_rapid_validate_exits_zero_with_custom_stack_without_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates = _copy_templates(tmp)
            (templates / "stacks" / "custom.md").write_text("# Custom stack\n", encoding="utf-8")
            project = Path(tmp) / "project"
            project.mkdir()
            (project / "pyproject.toml").write_text("", encoding="utf-8")
            self.assertEqual(_run_rapid(project, "init", "--yes").returncode, 0)
            stdout = io.StringIO()
            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project / ".rapid-os"
            ), patch.object(
                cli_main, "CONFIG_FILE", project / ".rapid-os" / "config.json"
            ), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), contextlib.redirect_stdout(stdout):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main.validate_command(Namespace(json=False, strict=False))
            self.assertEqual(ctx.exception.code, 0, stdout.getvalue())
            self.assertIn("RAPID1412", stdout.getvalue())

    def test_custom_stack_without_sidecar_never_defaults_to_doc_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            templates = _copy_templates(tmp)
            (templates / "stacks" / "custom.md").write_text("# Custom stack\n", encoding="utf-8")
            catalog = load_catalog(templates)
            self.assertEqual(
                catalog.default_topology_for_stack("custom", None, ["doc-site", "edge-free"]),
                "edge-free",
            )

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

    def test_generic_is_detected_by_exact_header_not_by_body_heuristics(self):
        text = build_generic_stack(ProjectModel(root=Path(".")))
        self.assertEqual(text.splitlines()[0], GENERIC_STACK_HEADER)
        text += "- **Framework:** Next.js, FastAPI (docusaurus, bun.js)\n"
        self.assertEqual(infer_stack(text), "generic")
        self.assertEqual(infer_stack("Detected Next.js\n" + GENERIC_STACK_HEADER + " extra\n"), "web-modern")

    def test_no_scan_does_not_claim_nothing_was_detected(self):
        text = build_generic_stack(ProjectModel(root=Path(".")), scanned=False)
        self.assertIn("not scanned (--no-scan)", text)
        self.assertNotIn("not detected", text)
        self.assertEqual(infer_stack(text), "generic")

    def test_init_no_scan_writes_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            init = _run_rapid(project, "init", "--yes", "--no-scan")
            self.assertEqual(init.returncode, 0, init.stderr)
            stack = (project / ".rapid-os" / "standards" / "tech-stack.md").read_text(encoding="utf-8")
            self.assertIn("not scanned (--no-scan)", stack)
            self.assertNotIn("not detected", stack)

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

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rapid_os.adapters.context_sources import KNOWN_CONTEXT_SOURCE_SPECS, ContextSourceLoader
from rapid_os.cli import main as cli_main
from rapid_os.core.context import compose_project_context
from rapid_os.domain.catalog import load_setup_doc_banks
from rapid_os.domain.context import ContextCompiler, ContextPriority, ContextRequest
from rapid_os.domain.project_docs import (
    DRAFT_BANNER,
    parse_doc_frontmatter,
    validate_doc_body,
)
from rapid_os.domain.validation import validate_project_docs

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"
BANKS = load_setup_doc_banks(TEMPLATES)

FULL_BRIEF = (
    "## Problema\nP\n\n## Usuarios\nU\n\n## Historias\n- [ ] H001: algo\n"
)
FILES = {
    "brief": "docs/PRODUCT_BRIEF.md",
    "business": "docs/BUSINESS_RULES.md",
    "data-model": "docs/DATA_MODEL.md",
    "architecture": "docs/ARCHITECTURE.md",
}


def run_rapid(cwd, *argv):
    return subprocess.run(
        [sys.executable, str(REPO / "rapid.py"), *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "CLAUDECODE": "", "PYTHONPATH": str(REPO)},
    )


def make_project(root: Path, *, business_standard: str | None = None) -> Path:
    standards = root / ".rapid-os" / "standards"
    standards.mkdir(parents=True)
    (standards / "tech-stack.md").write_text("# TECH STACK: GENERIC\n- **Language:** Python.\n", encoding="utf-8")
    (standards / "topology.md").write_text("# TOPOLOGY\n- **Type:** Decoupled.\n", encoding="utf-8")
    (root / ".rapid-os" / "config.json").write_text(json.dumps({"tools": ["claude"]}), encoding="utf-8")
    if business_standard is not None:
        (standards / "business.md").write_text(business_standard, encoding="utf-8")
    return root


def write_doc(root: Path, doc_id: str, body: str, *, source="drafted", status="draft", rapid_doc=None):
    path = root / FILES[doc_id]
    path.parent.mkdir(parents=True, exist_ok=True)
    front = f"---\nrapid-doc: {rapid_doc or doc_id}\nsource: {source}\nstatus: {status}\nsha256: abc\n---\n"
    path.write_text(front + body, encoding="utf-8")
    return path


def write_setup(root: Path, **doc_status):
    docs = {k: {"status": v, "confirmed": False, "sha256": ""} for k, v in doc_status.items()}
    (root / ".rapid-os" / "setup.json").write_text(
        json.dumps({"schema_version": 1, "docs": docs}), encoding="utf-8"
    )


def load_sources(root: Path):
    return ContextSourceLoader().load(root, root / ".rapid-os", include_project_intelligence=False)


def compiled_content(root: Path):
    discovery = load_sources(root)
    return ContextCompiler().compile(ContextRequest(), sources=discovery.sources)


def codes(report):
    return [(d.level, d.code) for d in report.diagnostics]


class FrontmatterTests(unittest.TestCase):
    def test_parse_splits_fields_and_body(self):
        fields, body = parse_doc_frontmatter("---\nrapid-doc: brief\nsource: 'drafted'\n---\n## A\ntext\n")
        self.assertEqual(fields, {"rapid-doc": "brief", "source": "drafted"})
        self.assertEqual(body, "## A\ntext\n")

    def test_without_valid_frontmatter_the_text_is_the_body(self):
        for text in ("# readme\n", "---\nunterminated\n", ""):
            with self.subTest(text=text):
                self.assertEqual(parse_doc_frontmatter(text), ({}, text))

    def test_crlf_is_normalized(self):
        fields, body = parse_doc_frontmatter("---\r\nrapid-doc: brief\r\n---\r\nbody\r\n")
        self.assertEqual((fields, body), ({"rapid-doc": "brief"}, "body\n"))

    def test_validate_doc_body_matches_headings_case_and_edge_whitespace_insensitively(self):
        body = "## problema  \n.\n##   USERS\n.\n## Stories\n- [ ] H001: x\n"
        self.assertEqual(validate_doc_body(body, BANKS["brief"]), ())

    def test_validate_doc_body_reports_missing_sections_and_size(self):
        issues = validate_doc_body("### Problema\n## Usuarios\n" + "x" * 6000, BANKS["brief"])
        self.assertEqual(
            sorted(i.code for i in issues), ["RAPID1403", "RAPID1403", "RAPID1404"]
        )
        missing = " ".join(i.message for i in issues if i.code == "RAPID1403")
        self.assertIn("'problem'", missing)  # "###" is not a "## " heading
        self.assertIn("'stories'", missing)


class ContextSourceSpecTests(unittest.TestCase):
    def test_doc_specs_match_the_question_banks(self):
        specs = {s.id: s for s in KNOWN_CONTEXT_SOURCE_SPECS if s.managed_doc}
        self.assertEqual(set(specs), {f"doc.{doc_id}" for doc_id in BANKS})
        for doc_id, bank in BANKS.items():
            with self.subTest(doc=doc_id):
                spec = specs[f"doc.{doc_id}"]
                self.assertEqual(spec.relative_path, bank.file)
                self.assertEqual(spec.priority, ContextPriority.coerce(bank.context_priority))
                self.assertFalse(spec.under_rapid_dir)
        tags = {s.id: set(s.tags) for s in specs.values()}
        self.assertEqual(tags["doc.brief"], {"product", "feature", "spec"})
        self.assertEqual(tags["doc.business"], {"business", "domain", "product"})
        self.assertEqual(tags["doc.data-model"], {"data", "database", "backend", "domain"})
        self.assertEqual(tags["doc.architecture"], {"architecture", "topology", "backend", "frontend"})


class ContextProvenanceTests(unittest.TestCase):
    def test_docs_readme_without_rapid_doc_frontmatter_stays_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            (root / "docs").mkdir()
            (root / "docs" / "README.md").write_text("# Project docs\n", encoding="utf-8")
            (root / FILES["brief"]).write_text("# hand written brief, no frontmatter\n", encoding="utf-8")
            write_doc(root, "architecture", "## Decision\nx\n", rapid_doc="brief")  # id does not match
            ids = [s.id for s in load_sources(root).sources]
            self.assertFalse([i for i in ids if i.startswith("doc.")], ids)
            self.assertNotIn("Project docs", compose_project_context(root / ".rapid-os", root))

    def test_unconfirmed_draft_goes_under_the_banner_in_context_and_agent_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            write_doc(root, "brief", FULL_BRIEF)
            content = compiled_content(root).content
            self.assertIn(f"{DRAFT_BANNER}\n\n## Problema", content)
            self.assertNotIn("rapid-doc", content)  # frontmatter is never injected
            self.assertNotIn("sha256", content)

            run_rapid(root, "init", "--yes", "--agents", "claude", "--no-scan").returncode
            with patch.object(cli_main, "CURRENT_DIR", root), patch.object(
                cli_main, "PROJECT_RAPID_DIR", root / ".rapid-os"
            ), patch.object(
                cli_main, "CONFIG_FILE", root / ".rapid-os" / "config.json"
            ), contextlib.redirect_stdout(io.StringIO()):
                cli_main.regenerate_context()
            claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn(DRAFT_BANNER, claude)
            self.assertIn("## Problema", claude)
            self.assertNotIn("rapid-doc", claude)

    def test_rapid_context_json_carries_the_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            write_doc(root, "brief", FULL_BRIEF)
            result = run_rapid(root, "context", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(DRAFT_BANNER, json.loads(result.stdout)["content"])

    def test_confirmed_draft_and_provided_docs_have_no_banner(self):
        for source, status in (("drafted", "confirmed"), ("provided", "draft")):
            with self.subTest(source=source, status=status), tempfile.TemporaryDirectory() as tmp:
                root = make_project(Path(tmp))
                write_doc(root, "brief", FULL_BRIEF, source=source, status=status)
                content = compiled_content(root).content
                self.assertIn("## Problema", content)
                self.assertNotIn(DRAFT_BANNER, content)
                self.assertNotIn(DRAFT_BANNER, compose_project_context(root / ".rapid-os", root))

    def test_skipped_doc_asks_instead_of_inventing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            write_setup(root, **{"data-model": "skipped"})
            line = "Modelo de datos: sin definir. Pregunta, no inventes."
            self.assertIn(line, compiled_content(root).content)
            self.assertIn(line, compose_project_context(root / ".rapid-os", root))

    def test_provided_status_in_setup_json_alone_adds_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            write_setup(root, brief="provided", business="pending")
            self.assertEqual([s.id for s in load_sources(root).sources if s.id.startswith("doc.")], [])

    def test_doc_business_supersedes_the_legacy_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), business_standard="Regla heredada: nunca borrar pedidos.\n")
            write_doc(root, "business", "## Objetivo\nVender.\n", source="provided", status="confirmed")
            compiled = compiled_content(root)
            skipped = {e.source_id: e.reason for e in compiled.manifest.skipped}
            self.assertEqual(skipped.get("standard.business"), "superseded by doc.business")
            self.assertIn("doc.business", [e.source_id for e in compiled.manifest.selected])
            self.assertNotIn("Regla heredada", compiled.content)
            self.assertNotIn("Regla heredada", compose_project_context(root / ".rapid-os", root))
            report = validate_project_docs(root / ".rapid-os", root, TEMPLATES)
            self.assertIn(("warning", "RAPID1410"), codes(report))

    def test_same_business_body_does_not_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), business_standard="## Objetivo\n\nVender.\n")
            write_doc(root, "business", "## Objetivo\nVender.\n", source="provided", status="confirmed")
            report = validate_project_docs(root / ".rapid-os", root, TEMPLATES)
            self.assertNotIn("RAPID1410", [c for _l, c in codes(report)])

    def test_only_legacy_business_standard_behaves_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), business_standard="Regla heredada.\n")
            compiled = compiled_content(root)
            self.assertIn("standard.business", [e.source_id for e in compiled.manifest.selected])
            self.assertEqual([e for e in compiled.manifest.skipped if e.source_id == "standard.business"], [])
            self.assertIn("Regla heredada.", compose_project_context(root / ".rapid-os", root))

    def test_skipped_business_yields_to_an_existing_legacy_standard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), business_standard="Regla heredada.\n")
            write_setup(root, business="skipped")
            self.assertEqual([s.id for s in load_sources(root).sources if s.id == "doc.business"], [])

    def test_project_without_docs_composes_exactly_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp), business_standard="Regla.\n")
            (root / "docs").mkdir()
            (root / "docs" / "README.md").write_text("# docs\n", encoding="utf-8")
            (root / "references").mkdir()
            (root / "references" / "VISION_CONTEXT.md").write_text("vision", encoding="utf-8")

            standards = root / ".rapid-os" / "standards"
            expected = ""
            for filename in ("tech-stack.md", "topology.md", "security.md", "design.md", "business.md", "coding-rules.md"):
                path = standards / filename
                if path.exists():
                    expected += f"\n### 🛑 {filename.replace('.md', '').upper().replace('-', ' ')}\n"
                    expected += path.read_text(encoding="utf-8") + "\n"
            expected += "\n### 👁️ VISUAL STANDARDS\n" + "vision"
            self.assertEqual(compose_project_context(root / ".rapid-os", root), expected)
            self.assertEqual([s.id for s in load_sources(root).sources if s.id.startswith("doc.")], [])


class ValidateDocsTests(unittest.TestCase):
    def test_drafted_doc_missing_a_section_gets_rapid1403_but_provided_does_not(self):
        body = "## Problema\nP\n\n## Usuarios\nU\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            write_doc(root, "brief", body, source="drafted", status="confirmed")
            report = validate_project_docs(root / ".rapid-os", root, TEMPLATES)
            self.assertIn(("warning", "RAPID1403"), codes(report))
            self.assertNotIn("RAPID1408", [c for _l, c in codes(report)])  # confirmed
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            write_doc(root, "brief", body, source="provided", status="draft")
            report = validate_project_docs(root / ".rapid-os", root, TEMPLATES)
            self.assertEqual(codes(report), [])

    def test_drafted_doc_over_max_chars_gets_rapid1404(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            write_doc(root, "brief", FULL_BRIEF + "x" * 6000, source="drafted", status="confirmed")
            report = validate_project_docs(root / ".rapid-os", root, TEMPLATES)
            self.assertEqual(codes(report), [("warning", "RAPID1404")])

    def test_unconfirmed_drafts_warn_rapid1408_once_each(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            write_doc(root, "brief", FULL_BRIEF)
            write_doc(root, "architecture", "## Decision\nd\n\n## Rationale\nr\n\n## Rejected alternatives\na\n\n## Consequences\nc\n")
            report = validate_project_docs(root / ".rapid-os", root, TEMPLATES)
            self.assertEqual(sorted(codes(report)), [("warning", "RAPID1408")] * 2)

    def test_setup_json_validity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp))
            self.assertEqual(codes(validate_project_docs(root / ".rapid-os", root, TEMPLATES)), [])
            write_setup(root, brief="pending")
            self.assertEqual(
                codes(validate_project_docs(root / ".rapid-os", root, TEMPLATES)), [("info", "RAPID1400")]
            )
            (root / ".rapid-os" / "setup.json").write_text("{", encoding="utf-8")
            self.assertEqual(
                codes(validate_project_docs(root / ".rapid-os", root, TEMPLATES)), [("error", "RAPID1406")]
            )

    def test_rapid_validate_reports_the_docs_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("", encoding="utf-8")
            self.assertEqual(run_rapid(root, "init", "--yes").returncode, 0)
            write_doc(root, "brief", "## Problema\nP\n")
            write_setup(root, brief="drafted")
            result = run_rapid(root, "validate", "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            found = {d["code"] for d in json.loads(result.stdout)["diagnostics"]}
            self.assertTrue({"RAPID1400", "RAPID1403", "RAPID1408"} <= found, found)


if __name__ == "__main__":
    unittest.main()

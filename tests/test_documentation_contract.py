"""Static Product Truth guardrails for the Docusaurus documentation surface.

These tests use the Python standard library so documentation contracts remain
checked by the existing Rapid OS test matrix, independently of Node.js.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
WEBSITE = ROOT / "website"


class DocumentationContractTests(unittest.TestCase):
    def test_docusaurus_uses_single_canonical_docs_directory(self):
        config = (WEBSITE / "docusaurus.config.ts").read_text(encoding="utf-8")
        self.assertRegex(config, r"path:\s*['\"]\.\./docs['\"]")
        self.assertIn("routeBasePath: '/'", config)
        self.assertFalse((WEBSITE / "docs").exists(), "Duplicate website/docs/ is forbidden")

    def test_all_sidebar_document_ids_resolve_to_canonical_files(self):
        sidebars = (WEBSITE / "sidebars.ts").read_text(encoding="utf-8")
        ids = re.findall(r"^\s*'([a-z0-9][a-z0-9/_-]*)',?\s*$", sidebars, re.MULTILINE)
        self.assertGreaterEqual(len(ids), 10, "Sidebar unexpectedly empty")
        missing = [doc_id for doc_id in ids if not (DOCS / (doc_id + ".md")).is_file() and not (DOCS / (doc_id + ".mdx")).is_file()]
        self.assertFalse(missing, f"Unknown documentation IDs: {missing}")

    def test_product_boundaries_are_explicit(self):
        concept = (DOCS / "concepts" / "what-is-rapid-os.md").read_text(encoding="utf-8").lower()
        capability = (DOCS / "guides" / "permissions-capabilities.md").read_text(encoding="utf-8").lower()
        self.assertIn("no invoca automáticamente", concept)
        self.assertIn("no crea branches o worktrees", concept)
        self.assertIn("capability", capability)
        self.assertIn("evidencia", capability)
        self.assertIn("unknown", capability)

    def test_reference_contains_all_governance_commands(self):
        reference = (DOCS / "cli.md").read_text(encoding="utf-8")
        for command in ("scan", "spec", "context", "policy", "run", "harness", "evidence", "eval", "validate"):
            with self.subTest(command=command):
                self.assertIn("rapid " + command, reference)

    def test_documentation_workflow_checks_build(self):
        workflow = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
        self.assertIn("npm run typecheck", workflow)
        self.assertIn("npm run build", workflow)
        self.assertIn("pull_request:", workflow)
        config = (WEBSITE / "docusaurus.config.ts").read_text(encoding="utf-8")
        self.assertIn("onBrokenLinks: 'throw'", config)


if __name__ == "__main__":
    unittest.main()

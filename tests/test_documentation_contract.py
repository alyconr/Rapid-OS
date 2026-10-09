"""Static Product Truth guardrails for the Docusaurus documentation surface.

These tests use the Python standard library so documentation contracts remain
checked by the existing Rapid OS test matrix, independently of Node.js.
"""

from pathlib import Path
import json
import re
import unittest

from rapid_os.cli.main import create_parser


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
WEBSITE = ROOT / "website"


class DocumentationContractTests(unittest.TestCase):
    def test_docusaurus_uses_single_canonical_docs_directory(self):
        """1 & 2: Canonical source is docs/ and duplicate website/docs/ is forbidden."""
        config = (WEBSITE / "docusaurus.config.ts").read_text(encoding="utf-8")
        self.assertRegex(config, r"path:\s*['\"]\.\./docs['\"]")
        self.assertIn("routeBasePath: '/'", config)
        self.assertFalse((WEBSITE / "docs").exists(), "Duplicate website/docs/ is forbidden")

    def test_all_sidebar_document_ids_resolve_to_canonical_files(self):
        """3: All sidebar document IDs resolve to canonical files in docs/."""
        sidebars = (WEBSITE / "sidebars.ts").read_text(encoding="utf-8")
        ids = re.findall(r"^\s*'([a-z0-9][a-z0-9/_-]*)',?\s*$", sidebars, re.MULTILINE)
        self.assertGreaterEqual(len(ids), 10, "Sidebar unexpectedly empty")
        missing = [doc_id for doc_id in ids if not (DOCS / (doc_id + ".md")).is_file() and not (DOCS / (doc_id + ".mdx")).is_file()]
        self.assertFalse(missing, f"Unknown documentation IDs: {missing}")

    def test_fundamental_documents_exist(self):
        """4: Verify all fundamental documents exist in docs/."""
        fundamental_docs = [
            "index.md",
            "concepts/what-is-rapid-os.md",
            "getting-started.md",
            "governance-loop.md",
            "cli.md",
            "architecture/rapid-os-v3.md",
            "guides/use-cases.md",
            "guides/permissions-capabilities.md",
            "guides/project-layout.md",
            "release-v3.0.0.md",
        ]
        for rel_path in fundamental_docs:
            with self.subTest(document=rel_path):
                self.assertTrue((DOCS / rel_path).is_file(), f"Missing fundamental document: {rel_path}")

    def test_product_boundaries_are_explicit(self):
        """5: Product boundaries and non-claims are clearly articulated."""
        concept = (DOCS / "concepts" / "what-is-rapid-os.md").read_text(encoding="utf-8").lower()
        capability = (DOCS / "guides" / "permissions-capabilities.md").read_text(encoding="utf-8").lower()
        self.assertIn("no invoca automáticamente", concept)
        self.assertIn("no crea branches o worktrees", concept)
        self.assertIn("capability", capability)
        self.assertIn("evidencia", capability)
        self.assertIn("unknown", capability)

    def test_reference_contains_all_governance_commands(self):
        """6: All governance commands are documented in cli.md and match CLI parser."""
        reference = (DOCS / "cli.md").read_text(encoding="utf-8")
        parser = create_parser()
        import argparse
        subparsers_action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
        parser_commands = subparsers_action.choices

        governance_commands = ("scan", "spec", "context", "policy", "run", "harness", "evidence", "eval", "validate")
        for command in governance_commands:
            with self.subTest(command=command):
                self.assertIn(command, parser_commands, f"Command rapid {command} not found in parser")
                self.assertIn("rapid " + command, reference, f"rapid {command} not documented in cli.md")

    def test_documented_flags_exist_in_parser(self):
        """7: Detect nonexistent or hallucinated flags in cli.md."""
        import argparse
        cli_text = (DOCS / "cli.md").read_text(encoding="utf-8")
        raw_flags = set(re.findall(r"--[a-z0-9-]+", cli_text))
        documented_flags = {f for f in raw_flags if not f.startswith("---")}

        parser = create_parser()
        all_parser_flags = set()

        def collect_flags(p):
            for a in p._actions:
                all_parser_flags.update(a.option_strings)
                if isinstance(a, argparse._SubParsersAction):
                    for sub_p in a.choices.values():
                        collect_flags(sub_p)

        collect_flags(parser)
        valid_flags = {f for f in all_parser_flags if f.startswith("--")}
        unknown_flags = documented_flags - valid_flags
        self.assertEqual(unknown_flags, set(), f"Documented flags not present in parser: {unknown_flags}")

    def test_documentation_workflow_checks_build(self):
        """8 & 9: docs.yml runs npm ci, typecheck, build, and enforces strict broken links."""
        workflow = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
        self.assertIn("npm ci", workflow)
        self.assertIn("npm run typecheck", workflow)
        self.assertIn("npm run build", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("website/package-lock.json", workflow)

        config = (WEBSITE / "docusaurus.config.ts").read_text(encoding="utf-8")
        self.assertIn("onBrokenLinks: 'throw'", config)

    def test_package_json_and_lockfile_consistency(self):
        """10: website/package.json and website/package-lock.json are consistent."""
        pkg_json_file = WEBSITE / "package.json"
        lock_file = WEBSITE / "package-lock.json"
        self.assertTrue(pkg_json_file.is_file(), "website/package.json must exist")
        self.assertTrue(lock_file.is_file(), "website/package-lock.json must exist")

        with open(pkg_json_file, encoding="utf-8") as f:
            pkg_data = json.load(f)
        with open(lock_file, encoding="utf-8") as f:
            lock_data = json.load(f)

        self.assertEqual(pkg_data["name"], lock_data["name"], "Package name mismatch")
        self.assertEqual(pkg_data["version"], lock_data["version"], "Package version mismatch")
        self.assertGreaterEqual(lock_data.get("lockfileVersion", 0), 2, "lockfileVersion must be >= 2")

        # Verify all direct dependencies in package.json are tracked in the lockfile
        all_declared_deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
        root_packages = lock_data.get("packages", {}).get("", {})
        root_deps = {**root_packages.get("dependencies", {}), **root_packages.get("devDependencies", {})}
        for dep in all_declared_deps:
            self.assertIn(dep, root_deps, f"Dependency {dep} in package.json is missing in lockfile root")


if __name__ == "__main__":
    unittest.main()

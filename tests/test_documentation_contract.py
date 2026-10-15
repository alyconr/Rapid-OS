"""Static and functional Product Truth guardrails for the Docusaurus documentation surface.

These tests use the Python standard library so documentation contracts remain
checked by the existing Rapid OS test matrix, independently of Node.js.
"""

from pathlib import Path
import json
import os
import re
import subprocess
import sys
import tempfile
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
        self.assertGreaterEqual(len(ids), 15, "Sidebar unexpectedly small for Sprint 2")
        missing = [doc_id for doc_id in ids if not (DOCS / (doc_id + ".md")).is_file() and not (DOCS / (doc_id + ".mdx")).is_file()]
        self.assertFalse(missing, f"Unknown documentation IDs: {missing}")

    def test_sprint_2_mandatory_documents_exist(self):
        """Verify presence of all mandatory Sprint 2 documents."""
        sprint_2_docs = [
            "index.md",
            "concepts/what-is-rapid-os.md",
            "concepts/why-rapid-os.md",
            "concepts/core-concepts.md",
            "concepts/product-boundaries.md",
            "installation/index.md",
            "installation/requirements.md",
            "installation/windows.md",
            "installation/linux.md",
            "installation/macos.md",
            "installation/wsl.md",
            "installation/verification.md",
            "installation/upgrade.md",
            "troubleshooting/installation.md",
            "getting-started.md",
            "getting-started/first-project.md",
            "getting-started/existing-project.md",
            "getting-started/first-spec.md",
            "getting-started/first-context.md",
            "getting-started/next-steps.md",
            "governance-loop.md",
            "cli.md",
            "architecture/rapid-os-v3.md",
            "guides/use-cases.md",
            "guides/permissions-capabilities.md",
            "guides/project-layout.md",
            "release-v3.0.0.md",
            "audit/sprint-2-validation.md",
        ]
        for rel_path in sprint_2_docs:
            with self.subTest(document=rel_path):
                self.assertTrue((DOCS / rel_path).is_file(), f"Missing required document: {rel_path}")

    def test_product_boundaries_are_explicit(self):
        """Product boundaries and non-claims are clearly articulated."""
        concept = (DOCS / "concepts" / "what-is-rapid-os.md").read_text(encoding="utf-8").lower()
        boundaries = (DOCS / "concepts" / "product-boundaries.md").read_text(encoding="utf-8").lower()
        capability = (DOCS / "guides" / "permissions-capabilities.md").read_text(encoding="utf-8").lower()

        self.assertIn("no invoca automáticamente", concept)
        self.assertIn("no crea branches o worktrees", concept)
        self.assertIn("rapid shortcuts install", concept)
        self.assertIn("rapid hook stop|pre-tool", concept)
        self.assertIn("algún ancestro es un harness de agente", boundaries)
        self.assertIn("los hooks deniegan herramientas al agente, pero rapid os no invoca agentes", boundaries)
        self.assertIn("de mejor esfuerzo", boundaries)
        self.assertIn("rapid start --worktree", concept)
        self.assertIn("rapid start --worktree", boundaries)
        self.assertIn("rapid abort` nunca lo elimina", boundaries)
        self.assertIn("no instala shortcuts de harness por su cuenta", boundaries)
        self.assertIn("nunca aprueban gates humanos", boundaries)
        self.assertIn("no invoca automáticamente", boundaries)
        self.assertIn("no utiliza llm-as-a-judge", boundaries)
        self.assertIn("capability", capability)
        self.assertIn("evidencia", capability)
        self.assertIn("unknown", capability)

    def test_python_requirements_align_with_pyproject(self):
        """Python versions documented in requirements align with pyproject.toml."""
        pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        req_text = (DOCS / "installation" / "requirements.md").read_text(encoding="utf-8")

        self.assertIn('requires-python = ">=3.10"', pyproject_text)
        self.assertIn("3.10", req_text)
        self.assertIn("3.13", req_text)

    def test_stable_vs_development_installation_distinct(self):
        """Installation docs clearly distinguish stable release from development checkout."""
        install_index = (DOCS / "installation" / "index.md").read_text(encoding="utf-8")
        self.assertIn("v3.0.0", install_index)
        self.assertIn("main", install_index)
        self.assertIn("Estable", install_index)
        self.assertIn("Desarrollo", install_index)

    def test_reference_contains_all_governance_commands(self):
        """All governance commands are documented in cli.md and match CLI parser."""
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
        """Detect nonexistent or hallucinated flags in cli.md and first-project.md."""
        import argparse
        cli_text = (DOCS / "cli.md").read_text(encoding="utf-8")
        quickstart_text = (DOCS / "getting-started" / "first-project.md").read_text(encoding="utf-8")

        raw_flags = set(re.findall(r"--[a-z0-9-]+", cli_text + "\n" + quickstart_text))
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
        """docs.yml runs npm ci, typecheck, build, and enforces strict broken links."""
        workflow = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
        self.assertIn("npm ci", workflow)
        self.assertIn("npm run typecheck", workflow)
        self.assertIn("npm run build", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("website/package-lock.json", workflow)

        config = (WEBSITE / "docusaurus.config.ts").read_text(encoding="utf-8")
        self.assertIn("onBrokenLinks: 'throw'", config)

    def test_package_json_and_lockfile_consistency(self):
        """website/package.json and website/package-lock.json are consistent."""
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

        all_declared_deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
        root_packages = lock_data.get("packages", {}).get("", {})
        root_deps = {**root_packages.get("dependencies", {}), **root_packages.get("devDependencies", {})}
        for dep in all_declared_deps:
            self.assertIn(dep, root_deps, f"Dependency {dep} in package.json is missing in lockfile root")

    def test_quickstart_functional_end_to_end(self):
        """Execute non-interactive Quickstart steps in an isolated temp directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT)
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"

            rapid_cli = [sys.executable, str(ROOT / "rapid.py")]

            # Step 1: Pre-populate app.py
            (Path(tmpdir) / "app.py").write_text("print('hello')\n", encoding="utf-8")

            # Step 2: rapid init non-interactive
            res = subprocess.run(
                rapid_cli + ["init", "--stack", "docs-modern", "--archetype", "mvp", "--no-scan"],
                cwd=tmpdir,
                input="1\n1\n\nn\n\nn\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"rapid init failed: {res.stderr}")
            self.assertTrue((Path(tmpdir) / ".rapid-os" / "config.json").is_file())

            # Step 3 & 4: rapid scan --write
            res = subprocess.run(
                rapid_cli + ["scan", "--write"],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"rapid scan --write failed: {res.stderr}")
            self.assertTrue((Path(tmpdir) / ".rapid-os" / "project.json").is_file())

            # Step 5: rapid spec create
            res = subprocess.run(
                rapid_cli + [
                    "spec", "create",
                    "--id", "validate-username",
                    "--title", "Validate Username Function",
                    "--mode", "feature",
                    "--objective", "Validar formato seguro de nombres de usuario",
                    "--problem", "Actualmente el sistema no valida caracteres especiales",
                    "--scope", "Crear funcion validate_username",
                    "--acceptance", "validate_username('juan_123') retorna True",
                    "--task", "Implementar funcion validate_username en app.py",
                    "--status", "ready",
                ],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"rapid spec create failed: {res.stderr}")
            self.assertTrue((Path(tmpdir) / ".rapid-os" / "specs" / "validate-username" / "spec.json").is_file())

            # Step 6: rapid spec list
            res = subprocess.run(
                rapid_cli + ["spec", "list"],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("validate-username", res.stdout)

            # Step 7: rapid context
            res = subprocess.run(
                rapid_cli + ["context", "--mode", "feature", "--spec", "validate-username", "--harness", "codex", "--manifest"],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"rapid context failed: {res.stderr}")
            self.assertIn("Rapid OS Context Manifest", res.stdout)

            # Step 8: rapid validate
            res = subprocess.run(
                rapid_cli + ["validate"],
                cwd=tmpdir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=15,
            )
            self.assertEqual(res.returncode, 0, f"rapid validate failed: {res.stderr}")

    def test_sprint_3_mandatory_documents_exist(self):
        """Verify presence of all mandatory Sprint 3 documents."""
        sprint_3_docs = [
            "guides/modes/index.md",
            "guides/modes/feature.md",
            "guides/modes/bugfix.md",
            "guides/modes/refactor.md",
            "guides/modes/hardening.md",
            "guides/modes/research.md",
            "cookbooks/policies-and-contracts.md",
            "cookbooks/harness-profiles.md",
            "cookbooks/evidence-engine.md",
            "cookbooks/behavioral-evaluations.md",
            "troubleshooting/diagnostics.md",
            "guides/ci-cd-integration.md",
            "audit/sprint-3-validation.md",
        ]
        for rel_path in sprint_3_docs:
            with self.subTest(document=rel_path):
                self.assertTrue((DOCS / rel_path).is_file(), f"Missing required Sprint 3 document: {rel_path}")

    def test_all_canonical_evidence_kinds_documented(self):
        """Verify all 9 EvidenceKind enum values are documented in evidence-engine cookbook."""
        from rapid_os.domain.evidence import EvidenceKind
        cookbook = (DOCS / "cookbooks" / "evidence-engine.md").read_text(encoding="utf-8")
        for kind in EvidenceKind:
            with self.subTest(evidence_kind=kind.value):
                self.assertIn(f"`{kind.value}`", cookbook, f"Evidence kind {kind.value} not documented")

    def test_all_engineering_modes_documented(self):
        """Verify all 5 execution modes are documented in modes index."""
        from rapid_os.domain.context import ContextMode
        modes_doc = (DOCS / "guides" / "modes" / "index.md").read_text(encoding="utf-8")
        for mode in ContextMode:
            if mode.value == "general":
                continue
            with self.subTest(mode=mode.value):
                self.assertIn(f"`{mode.value}`", modes_doc, f"Mode {mode.value} not documented in modes index")

    def test_diagnostics_catalog_covers_canonical_ranges(self):
        """Verify diagnostics catalog covers all major RAPIDxxx code ranges."""
        diagnostics = (DOCS / "troubleshooting" / "diagnostics.md").read_text(encoding="utf-8")
        ranges = ["RAPID100", "RAPID600", "RAPID700", "RAPID800", "RAPID1000", "RAPID1100", "RAPID1200", "RAPID1220"]
        for prefix in ranges:
            with self.subTest(prefix=prefix):
                self.assertIn(prefix, diagnostics, f"Diagnostic range {prefix} missing from catalog")

    # ------------------------------------------------------------------ shortcuts documentation
    INTEGRATION_SHORTCUTS = {
        # page -> (harness id, invocation of its shortcut)
        "claude-code.md": ("claude", "/rapid-feature"),
        "codex.md": ("codex", "$rapid-feature"),
        "cursor.md": ("cursor", "/rapid-feature"),
        "antigravity.md": ("antigravity", "/rapid-feature"),
        "vscode.md": ("vscode", "/rapid-feature"),
    }
    MODE_NAMES = ("feature", "bugfix", "refactor", "hardening", "research")

    def test_integration_pages_present_the_shortcuts_flow(self):
        """Every harness page (except index.md) installs and invokes its own shortcut, and keeps the v3 flow."""
        pages = sorted(p.name for p in (DOCS / "integrations").glob("*.md") if p.name != "index.md")
        self.assertEqual(sorted(self.INTEGRATION_SHORTCUTS), pages, "Unknown integration page: add it here")
        for page, (harness, invocation) in self.INTEGRATION_SHORTCUTS.items():
            text = (DOCS / "integrations" / page).read_text(encoding="utf-8")
            with self.subTest(page=page):
                self.assertIn("rapid shortcuts install", text)
                self.assertIn(f"--harness {harness}", text)
                self.assertIn(invocation, text)
                self.assertIn("## Flujo principal: shortcuts", text)
                self.assertIn("## Modo avanzado (comandos v3)", text)
                self.assertIn("guides/shortcuts.md", text)
                # The main flow comes right after the configuration sections and before the advanced one.
                self.assertLess(text.index("## Flujo principal: shortcuts"), text.index("## Modo avanzado (comandos v3)"))
                self.assertIn("rapid eval run", text)  # the v3 flow is kept, not deleted

    def test_integrations_index_mentions_shortcuts_and_the_advanced_mode(self):
        text = (DOCS / "integrations" / "index.md").read_text(encoding="utf-8")
        self.assertIn("shortcuts", text)
        self.assertIn("Modo avanzado", text)
        self.assertIn("guides/shortcuts.md", text)

    def test_mode_guides_open_with_their_shortcut(self):
        """Each mode guide names its /rapid-<mode> shortcut before the manual v3 flow."""
        for mode in self.MODE_NAMES:
            text = (DOCS / "guides" / "modes" / f"{mode}.md").read_text(encoding="utf-8")
            with self.subTest(mode=mode):
                self.assertIn(f"/rapid-{mode}", text)
                self.assertIn(f"## Con el shortcut `/rapid-{mode}`", text)
                self.assertIn("Modo avanzado", text)
                self.assertIn("../shortcuts.md", text)
                if "rapid spec create" in text:
                    self.assertLess(text.index(f"/rapid-{mode}"), text.index("rapid spec create"))
        index = (DOCS / "guides" / "modes" / "index.md").read_text(encoding="utf-8")
        for mode in self.MODE_NAMES:
            self.assertIn(f"/rapid-{mode}", index)

    def test_mode_guides_state_their_playbook_rules(self):
        """The playbook rules come from templates/modes/*.json and the Conductor, not from memory."""
        rules = {
            "bugfix": ("rapid check --expect fail --task T001", "antes"),
            "refactor": ("tests pasados", "baseline"),
            "hardening": ("rapid start hardening --spec-file - --worktree", "rapid/<run-id>"),
            "research": ("rapid attach", "tests obligatorios"),
        }
        for mode, needles in rules.items():
            text = (DOCS / "guides" / "modes" / f"{mode}.md").read_text(encoding="utf-8")
            for needle in needles:
                with self.subTest(mode=mode, needle=needle):
                    self.assertIn(needle, text)
        playbook = json.loads((ROOT / "templates" / "modes" / "bugfix.json").read_text(encoding="utf-8"))
        self.assertEqual(playbook["spec_template"]["implementation_tasks"][0], "T001: Reproducir con un test en rojo")

    def test_shortcuts_guide_is_registered_in_the_sidebar(self):
        sidebars = (WEBSITE / "sidebars.ts").read_text(encoding="utf-8")
        self.assertTrue((DOCS / "guides" / "shortcuts.md").is_file())
        self.assertIn("'guides/shortcuts'", sidebars)
        # First item of "Primeros pasos" (its own category arrives in a later PR).
        self.assertLess(sidebars.index("'guides/shortcuts'"), sidebars.index("'getting-started/first-project'"))
        self.assertLess(sidebars.index("label: 'Primeros pasos'"), sidebars.index("'guides/shortcuts'"))

    def test_shortcuts_guide_table_matches_the_adapters(self):
        """The folder of each harness in the guide is what the adapters really generate."""
        from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
        from rapid_os.adapters.shortcut_installer import load_templates

        guide = (DOCS / "guides" / "shortcuts.md").read_text(encoding="utf-8")
        templates = load_templates(ROOT / "templates")
        self.assertEqual(len(templates), 8)
        for template in templates:
            self.assertIn(f"`{template.name}`", guide)
        for adapter in DEFAULT_AGENT_REGISTRY.adapters():
            outputs = adapter.shortcut_outputs(templates)
            self.assertTrue(outputs, adapter.id)
            sample = next(iter(outputs)).as_posix()
            folder = sample[: sample.index("rapid-")]
            with self.subTest(harness=adapter.id):
                self.assertIn(f"`{adapter.id}`", guide)
                self.assertIn(folder, guide)

    def test_shortcuts_guide_problem_codes_exist_in_the_diagnostics_catalog(self):
        guide = (DOCS / "guides" / "shortcuts.md").read_text(encoding="utf-8")
        diagnostics = (DOCS / "troubleshooting" / "diagnostics.md").read_text(encoding="utf-8")
        for code in ("1301", "1307", "1308", "1310", "1312", "1315", "1320", "1321", "1337", "1339"):
            with self.subTest(code=code):
                self.assertIn(f"| `RAPID{code}` |", guide)
                self.assertIn(f"| `RAPID{code}` |", diagnostics)
        self.assertIn("diagnostics.md", guide)

    def test_readme_leads_with_the_shortcuts_quick_start(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Quick start con shortcuts", readme)
        self.assertLess(readme.index("Quick start con shortcuts"), readme.index('## Usage <a name="usage">'))
        for needle in ("rapid init --shortcuts", "/rapid-feature", "$rapid-feature", "guides/shortcuts"):
            self.assertIn(needle, readme)
        reference = readme[readme.index('<a name="cli-reference">'):]
        porcelain = reference.index("Flujo principal: verbos porcelain")
        advanced = reference.index("Comandos v3 y utilidades (Modo avanzado)")
        self.assertLess(porcelain, advanced)
        block = reference[porcelain:advanced]
        for verb in ("rapid start", "rapid next", "rapid check", "rapid task", "rapid attach", "rapid finish",
                     "rapid approve", "rapid status", "rapid abort", "rapid shortcuts", "rapid hook"):
            with self.subTest(verb=verb):
                self.assertIn(verb, block)


if __name__ == "__main__":
    unittest.main()

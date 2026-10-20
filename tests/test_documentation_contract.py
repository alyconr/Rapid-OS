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
            "release-v3.1.0.md",
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
        # What actually runs: the plumbing nothing; the porcelain only test_command / the rapid check argv.
        self.assertIn("el plumbing", concept)
        self.assertIn("no ejecuta nada del repositorio", concept)
        self.assertIn("el porcelain ejecuta solo el `test_command`", concept)
        self.assertIn("rapid check -- <comando>", concept)
        self.assertIn("nunca aprueba gates humanos", concept)
        self.assertIn("el plumbing no ejecuta nada del repositorio; el porcelain ejecuta solo lo que se le pide", boundaries)
        self.assertIn("solo el `test_command` de `.rapid-os/config.json`", boundaries)
        self.assertIn("nunca aprueba gates humanos", boundaries)
        self.assertIn("rapid start --worktree", capability)
        self.assertIn("nunca crea contenedores ni sandboxes", capability)
        self.assertIn("rapid shortcuts install", concept)
        self.assertIn("rapid hook stop|pre-tool", concept)
        self.assertIn("algún ancestro es un harness de agente", boundaries)
        self.assertIn("los hooks deniegan herramientas al agente, pero rapid os no invoca agentes", boundaries)
        self.assertIn("de mejor esfuerzo", boundaries)
        self.assertIn("rapid start --worktree", concept)
        self.assertIn("rapid start --worktree", boundaries)
        self.assertIn("rapid abort` nunca lo elimina", boundaries)
        self.assertIn("no instala shortcuts de harness por su cuenta", boundaries)
        # Onboarding: what rapid setup / rapid init write, and that nothing is confirmed for the person.
        self.assertIn("nunca marca como confirmado lo que la persona no confirmó", concept)
        self.assertIn("rapid setup doc <id> --confirm", concept)
        self.assertIn("rapid setup finish", concept)
        self.assertIn("no confirma por la persona ni crea documentación por su cuenta", boundaries)
        self.assertIn("`source: drafted` y `status: draft`", boundaries)
        self.assertIn("andamiaje `todo` de `docs/`", boundaries)
        # Shortcuts: --global is the only way Rapid OS writes outside the project.
        self.assertIn("rapid shortcuts install --global", concept)
        self.assertIn("rapid shortcuts install --global", boundaries)
        self.assertIn("nunca por defecto", concept)
        self.assertIn("nunca por defecto", boundaries)
        # Brief stories and agent-file backups.
        self.assertIn("no marca las historias del brief como hechas", concept)
        self.assertIn(".rapid-os/backups/", concept)
        self.assertIn("no marca historias del brief", boundaries)
        self.assertIn(".rapid-os/backups/", boundaries)
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
        self.assertIn("v3.1.1", install_index)
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

        governance_commands = (
            # v3 plumbing
            "scan", "spec", "context", "policy", "run", "harness", "evidence", "eval", "validate",
            # porcelain
            "start", "next", "check", "task", "attach", "finish", "approve", "status", "abort",
            "shortcuts", "hook",
        )
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
        ranges = [
            "RAPID100", "RAPID600", "RAPID700", "RAPID800", "RAPID1000", "RAPID1100", "RAPID1200", "RAPID1220",
            "RAPID1300",
        ]
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
        # It lives in its own category, right after "Primeros pasos" and before "Modos de ingeniería".
        category = sidebars.index("label: 'Shortcuts y orquestación'")
        self.assertLess(sidebars.index("label: 'Primeros pasos'"), category)
        self.assertLess(category, sidebars.index("label: 'Modos de ingeniería'"))
        self.assertLess(category, sidebars.index("'guides/shortcuts'"))
        self.assertLess(sidebars.index("'guides/shortcuts'"), sidebars.index("label: 'Modos de ingeniería'"))
        # ...and no longer in "Primeros pasos".
        first_steps = sidebars[sidebars.index("label: 'Primeros pasos'"):category]
        self.assertNotIn("guides/shortcuts", first_steps)

    def test_shortcuts_guide_table_matches_the_adapters(self):
        """The folder of each harness in the guide is what the adapters really generate."""
        from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
        from rapid_os.adapters.shortcut_installer import load_templates

        guide = (DOCS / "guides" / "shortcuts.md").read_text(encoding="utf-8")
        templates = load_templates(ROOT / "templates")
        self.assertEqual(len(templates), 9)
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
        for code in ("1301", "1307", "1308", "1310", "1312", "1315", "1320", "1321", "1337", "1339", "1413", "1414"):
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

    # ------------------------------------------------------------------ portal navigation and architecture
    # Pages that are intentionally outside the sidebar. Nothing is deleted; each needs a reason.
    SIDEBAR_ALLOWLIST = {
        "architecture/rapid-os-v2": (
            "Snapshot histórico de la arquitectura v2; ninguna página lo enlaza y se conserva solo por referencia "
            "hasta decidir su archivado."
        ),
    }

    @staticmethod
    def _sidebar_doc_ids():
        sidebars = (WEBSITE / "sidebars.ts").read_text(encoding="utf-8")
        ids = set(re.findall(r"^\s*'([A-Za-z0-9][A-Za-z0-9._/-]*)',?\s*$", sidebars, re.MULTILINE))
        ids |= set(re.findall(r"link:\s*\{type:\s*'doc',\s*id:\s*'([^']+)'", sidebars))
        return ids

    def test_every_docs_page_is_in_the_sidebar_or_allowlisted(self):
        """No page of docs/ is left out of the navigation (a category link counts)."""
        ids = self._sidebar_doc_ids()
        pages = {
            p.relative_to(DOCS).with_suffix("").as_posix()
            for pattern in ("*.md", "*.mdx")
            for p in DOCS.rglob(pattern)
        }
        orphans = sorted(pages - ids - set(self.SIDEBAR_ALLOWLIST))
        self.assertEqual(orphans, [], f"Pages missing from website/sidebars.ts (add them or allowlist with a reason): {orphans}")
        for page, reason in self.SIDEBAR_ALLOWLIST.items():
            with self.subTest(page=page):
                self.assertTrue(reason.strip(), "Allowlist entries need a reason")
                self.assertIn(page, pages, "Stale allowlist entry: the page no longer exists")
                self.assertNotIn(page, ids, "Allowlisted page is in the sidebar now: remove it from the allowlist")

    def test_sidebar_ids_that_do_not_resolve_are_reported_including_dotted_ones(self):
        missing = [i for i in self._sidebar_doc_ids() if not (DOCS / (i + ".md")).is_file() and not (DOCS / (i + ".mdx")).is_file()]
        self.assertEqual(missing, [])

    def test_navbar_and_footer_link_the_shortcuts_without_touching_the_release_link(self):
        config = (WEBSITE / "docusaurus.config.ts").read_text(encoding="utf-8")
        navbar = config[config.index("navbar: {"):config.index("footer: {")]
        footer = config[config.index("footer: {"):]
        self.assertIn("{to: '/guides/shortcuts', label: 'Shortcuts', position: 'left'}", navbar)
        self.assertLess(navbar.index("label: 'Primeros pasos'"), navbar.index("label: 'Shortcuts'"))
        self.assertLess(navbar.index("label: 'Shortcuts'"), navbar.index("label: 'Modos'"))
        self.assertIn("{label: 'Shortcuts', to: '/guides/shortcuts'}", footer)
        self.assertIn("{label: 'Arquitectura de orquestación', to: '/architecture/orchestration'}", footer)
        self.assertIn("{label: 'Release v3.1.1', to: '/release-v3.1.1'}", footer)

    def test_orchestration_architecture_covers_the_porcelain_design(self):
        text = (DOCS / "architecture" / "orchestration.md").read_text(encoding="utf-8")
        for needle in (
            "Porcelain sobre plumbing", "next_action", "BehavioralEvaluator", "gate_satisfied",
            "NextAction", "action.kind", "awaiting_human", "workspace_path", ".rapid-os/session.json",
            "start_head", "start_untracked", "rapid:check", "rapid:start", "rapid:finish", "rapid:attach",
            "expectation", "harness:*", "RAPID1310", "ascendencia", "mejor esfuerzo", "una persona aprueba",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        # markdown.mermaid is not enabled in the portal, so the loop is drawn as plain text (no npm dependency).
        config = (WEBSITE / "docusaurus.config.ts").read_text(encoding="utf-8")
        if "mermaid" not in config:
            self.assertNotIn("```mermaid", text)
            self.assertIn("rapid next --json", text)

    def test_governance_loop_has_the_porcelain_to_plumbing_table(self):
        text = (DOCS / "governance-loop.md").read_text(encoding="utf-8")
        self.assertIn("Porcelain Verbs", text)
        for verb in ("rapid start", "rapid next", "rapid check", "rapid task", "rapid attach", "rapid finish",
                     "rapid approve", "rapid status", "rapid abort"):
            with self.subTest(verb=verb):
                self.assertIn(f"| `{verb}", text)
        self.assertIn("rapid evidence add", text)
        self.assertIn("rapid run gate", text)

    def test_default_docusaurus_template_site_directory_is_gone(self):
        self.assertFalse((ROOT / "site").exists(), "site/ was the unused default Docusaurus template")
        maintenance = (DOCS / "operations" / "documentation-maintenance.md").read_text(encoding="utf-8")
        self.assertIn("`site/`", maintenance)
        self.assertIn("website/", maintenance)

    # ------------------------------------------------------------------ audits against the code
    def test_rapid13xx_codes_match_between_code_and_the_diagnostics_catalog(self):
        """Every RAPID13xx used in rapid_os/ is a row of diagnostics.md, and every row is used."""
        in_code = set()
        for path in (ROOT / "rapid_os").rglob("*.py"):
            in_code |= set(re.findall(r"RAPID(13\d\d)", path.read_text(encoding="utf-8", errors="replace")))
        diagnostics = (DOCS / "troubleshooting" / "diagnostics.md").read_text(encoding="utf-8")
        documented = set(re.findall(r"^\| `RAPID(13\d\d)` \|", diagnostics, re.MULTILINE))
        self.assertEqual(sorted(in_code - documented), [], "Used in rapid_os/ but not documented")
        self.assertEqual(sorted(documented - in_code), [], "Documented but not used in rapid_os/")

    def test_cli_reference_documents_every_parser_flag(self):
        """The reverse of test_documented_flags_exist_in_parser: no parser flag is missing from cli.md."""
        import argparse

        cli_text = (DOCS / "cli.md").read_text(encoding="utf-8")
        missing = []

        def walk(parser, path):
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for name, sub_parser in action.choices.items():
                        walk(sub_parser, path + [name])
                else:
                    for option in action.option_strings:
                        if option.startswith("--") and option != "--help" and option not in cli_text:
                            missing.append((" ".join(path), option))

        walk(create_parser(), [])
        self.assertEqual(missing, [])

    # ------------------------------------------------------------------ README, CHANGELOG, quickstart, labs
    def test_readme_boundaries_no_longer_make_false_claims(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for stale in ("run tests automatically", "create git worktrees automatically", "execute shell commands for runs",
                      "ni ejecuta tests automáticamente"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, readme)
        block = readme[readme.index("Rapid OS DOES NOT:"):]
        for needle in ("`rapid start --worktree`", "approve human gates", "Rapid OS RUNS, only through the porcelain",
                       "`rapid check`", "test_command"):
            with self.subTest(needle=needle):
                self.assertIn(needle, block)
        self.assertIn("nunca aprueba gates humanos", readme)

    def test_readme_canonical_suite_links_shortcuts_and_orchestration(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        start = readme.index("### 📚 Suite Canónica de Documentación")
        suite = readme[start:readme.index('<p align="right">', start)]
        self.assertIn("/guides/shortcuts", suite)
        self.assertIn("/architecture/orchestration", suite)

    def test_changelog_has_unreleased_and_the_3_1_0_section(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertLess(changelog.index("## [Unreleased]"), changelog.index("## [3.1.1] - "))
        self.assertLess(changelog.index("## [3.1.1] - "), changelog.index("## [3.1.0] - "))
        self.assertLess(changelog.index("## [3.1.0] - "), changelog.index("## [3.0.0]"))
        patch = changelog[changelog.index("## [3.1.1] - "):changelog.index("## [3.1.0] - ")]
        self.assertIn("real `rapid` executable on `PATH`", patch)
        released = changelog[changelog.index("## [3.1.0] - "):changelog.index("## [3.0.0]")]
        for needle in ("Porcelain layer", "ruleset v2", "Five engineering modes", "Shortcuts", "RAPID1321",
                       "Claude Code hooks", "`rapid approve` hardened", "ancestor process", "best-effort",
                       "`rapid finish`", "Shortcuts JSON contract"):
            with self.subTest(needle=needle):
                self.assertIn(needle, released)

    def test_release_3_1_0_pages_are_registered_and_cover_the_contract(self):
        sidebars = (ROOT / "website" / "sidebars.ts").read_text(encoding="utf-8")
        self.assertIn("'release-v3.1.0'", sidebars)
        self.assertIn("'release-v3.0.0'", sidebars)  # kept as history
        notes = (DOCS / "release-v3.1.0.md").read_text(encoding="utf-8")
        for needle in ("--ruleset 1", "v1 reports stay valid", "double fork", "renamed `claude.exe`", "reused pid",
                       "Codex and Cursor", "unchanged", "optional fields"):
            with self.subTest(needle=needle):
                self.assertIn(needle, notes)
        upgrade = (DOCS / "installation" / "upgrade.md").read_text(encoding="utf-8")
        self.assertIn("## 5. De 3.0 a 3.1", upgrade)
        for needle in ("rapid init --shortcuts", "rapid shortcuts install", "--hooks", ".rapid-os/session.json",
                       ".rapid-os/scratch/", "test_command", "nada que migrar"):
            with self.subTest(needle=needle):
                self.assertIn(needle, upgrade)

    def test_onboarding_pages_lead_with_shortcuts_or_declare_advanced_mode(self):
        pages = sorted(
            [*(DOCS / "getting-started").glob("*.md"), *(DOCS / "installation").glob("*.md"), *(DOCS / "tutorials").glob("*.md")]
        )
        pages.append(DOCS / "getting-started.md")
        for page in pages:
            if page.name == "requirements.md" and page.parent.name == "installation":
                continue
            text = page.read_text(encoding="utf-8")
            with self.subTest(page=page.relative_to(DOCS).as_posix()):
                self.assertTrue(
                    "rapid shortcuts" in text or "/rapid-" in text or "Modo avanzado" in text,
                    "must mention `rapid shortcuts` or `/rapid-`, or declare 'Modo avanzado'",
                )

    def test_getting_started_is_the_shortcuts_route_with_a_map_and_advanced_mode(self):
        text = (DOCS / "getting-started.md").read_text(encoding="utf-8")
        for needle in ("rapid init --shortcuts", "/rapid-feature", "## 2. Mapa de esta sección", "## Modo avanzado",
                       "rapid scan --write", "rapid spec create", "rapid evidence verify", "rapid eval run"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        for sub in ("first-project", "existing-project", "first-spec", "first-context", "next-steps"):
            self.assertIn(f"getting-started/{sub}.md", text)
        self.assertNotIn("Getting Started with", text)

    def test_onboarding_pages_have_a_with_shortcuts_section(self):
        for relative in ("existing-project.md", "first-spec.md", "first-context.md"):
            text = (DOCS / "getting-started" / relative).read_text(encoding="utf-8")
            with self.subTest(page=relative):
                self.assertIn("## Con shortcuts", text)
                self.assertIn("## Modo avanzado", text)
        spec = (DOCS / "getting-started" / "first-spec.md").read_text(encoding="utf-8")
        for needle in ("author_spec", "spec_template", "rapid start <modo> --spec-file -"):
            self.assertIn(needle, spec)

    def test_tutorials_index_maps_labs_to_shortcuts_and_first_lab_is_flagged_advanced(self):
        index = (DOCS / "tutorials" / "index.md").read_text(encoding="utf-8")
        for shortcut in ("/rapid-feature", "/rapid-bugfix", "/rapid-refactor", "/rapid-hardening", "/rapid-research"):
            self.assertIn(shortcut, index)
        first = (DOCS / "tutorials" / "first-governed-project.md").read_text(encoding="utf-8")
        self.assertIn("**Modo avanzado.**", first)
        self.assertIn("feature-lab.md", first)

    def test_project_layout_covers_the_porcelain_files_and_verb_classes(self):
        text = (DOCS / "guides" / "project-layout.md").read_text(encoding="utf-8")
        for needle in (".rapid-os/session.json", ".rapid-os/scratch/", "hooks.json", "hooks.log", ".claude/skills",
                       ".agents/skills", ".cursor/skills", ".github/prompts", ".claude/settings.json",
                       "../<repo>-<run-id>", "`rapid next`, `rapid status`, `rapid shortcuts list`",
                       "`rapid start`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`, `rapid approve`, `rapid abort`"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_core_concepts_cover_the_porcelain_vocabulary(self):
        text = (DOCS / "concepts" / "core-concepts.md").read_text(encoding="utf-8")
        for needle in ("Sesión", "NextAction", "Playbook", "Shortcut", "Productor porcelain", "Gate humano",
                       "architecture/orchestration.md"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_installation_pages_install_shortcuts_and_verification_checks_them(self):
        for page in ("linux", "macos", "windows", "wsl"):
            with self.subTest(page=page):
                self.assertIn("rapid init --shortcuts", (DOCS / "installation" / f"{page}.md").read_text(encoding="utf-8"))
        verification = (DOCS / "installation" / "verification.md").read_text(encoding="utf-8")
        for needle in ("rapid shortcuts list", "rapid doctor", "RAPID1319", "RAPID1339"):
            self.assertIn(needle, verification)

    def test_tutorial_troubleshooting_covers_the_shortcuts_route(self):
        text = (DOCS / "troubleshooting" / "tutorials.md").read_text(encoding="utf-8")
        for code in ("RAPID1301", "RAPID1307", "RAPID1308", "RAPID1310", "RAPID1321"):
            self.assertIn(code, text)
        self.assertIn("guides/shortcuts.md", text)
        self.assertIn("diagnostics.md", text)

    def test_docs_deploy_is_documented_as_manual_and_mandatory_after_the_tag(self):
        workflow = (ROOT / ".github" / "workflows" / "docs-deploy.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("push:", workflow)
        deployment = (DOCS / "operations" / "documentation-deployment.md").read_text(encoding="utf-8")
        self.assertIn("Solo `workflow_dispatch` (manual)", deployment)
        self.assertNotIn("workflow_dispatch` o push a `main`", deployment)
        self.assertIn("paso obligatorio", deployment)
        checklist = (DOCS / "release-checklist.md").read_text(encoding="utf-8")
        self.assertIn("docs-deploy.yml", checklist)
        self.assertIn("mandatory after the tag", checklist)

    def test_quickstart_leads_with_shortcuts_and_keeps_the_advanced_path(self):
        for relative in ("index.md", "getting-started/first-project.md"):
            text = (DOCS / relative).read_text(encoding="utf-8")
            with self.subTest(page=relative):
                self.assertIn("rapid init", text)
                self.assertIn("--shortcuts", text)
                self.assertIn("/rapid-feature", text)
                self.assertIn("Modo avanzado", text)
                self.assertLess(text.index("--shortcuts"), text.index("Modo avanzado"))
        first_project = (DOCS / "getting-started" / "first-project.md").read_text(encoding="utf-8")
        self.assertLess(first_project.index("--shortcuts"), first_project.index("## Paso 1"))
        self.assertIn("rapid scan --write", first_project)  # the plumbing route is kept

    def test_shortcuts_quickstart_functional_end_to_end(self):
        """The shortcut route: init --shortcuts, then the agent step simulated with `rapid start feature --spec-file -`."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT)
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            for name in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION"):
                env.pop(name, None)
            rapid_cli = [sys.executable, str(ROOT / "rapid.py")]

            def run(*args, stdin_text=None):
                return subprocess.run(
                    rapid_cli + list(args),
                    cwd=tmpdir,
                    input=stdin_text,
                    stdin=None if stdin_text is not None else subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    timeout=60,
                )

            (Path(tmpdir) / "app.py").write_text("print('hello')\n", encoding="utf-8")
            res = run("init", "--yes", "--no-scan", "--agents", "claude", "--shortcuts",
                      "--test-command", f'"{sys.executable}" -c "pass"')
            self.assertEqual(res.returncode, 0, f"rapid init --shortcuts failed: {res.stderr}")
            skill = Path(tmpdir) / ".claude" / "skills" / "rapid-feature" / "SKILL.md"
            self.assertTrue(skill.is_file())

            res = run("shortcuts", "list", "--harness", "claude", "--json")
            self.assertEqual(res.returncode, 0, res.stderr)
            states = {entry["state"] for entry in json.loads(res.stdout)["shortcuts"]}
            self.assertEqual(states, {"installed"})

            # What the shortcut tells the agent to do first.
            res = run("next", "--json")
            self.assertEqual(res.returncode, 0, res.stderr)
            action = json.loads(res.stdout)["action"]
            self.assertEqual(action["kind"], "author_spec")
            self.assertIn("title", action["spec_template"])

            # The agent drafts the spec from the objective and pipes it to `rapid start`.
            spec = {
                "title": "Validate username",
                "business_objective": "Reject unsafe usernames",
                "problem_statement": "validate_username does not exist",
                "acceptance_criteria": ["validate_username('juan_123') returns True"],
                "tasks": ["T001: Implement validate_username in app.py"],
            }
            res = run("start", "feature", "--spec-file", "-", "--json", stdin_text=json.dumps(spec))
            self.assertEqual(res.returncode, 0, f"rapid start failed: {res.stderr}")
            started = json.loads(res.stdout)
            self.assertTrue(started["run_id"])
            self.assertEqual(started["action"]["kind"], "implement_task")

            res = run("status", "--json")
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(json.loads(res.stdout)["run"]["status"], "active")

            # The human gate is a person's call: an agent-like (non-TTY) approve is refused.
            res = run("approve", "gate.final-verification")
            self.assertEqual(res.returncode, 1)
            self.assertIn("RAPID1310", res.stderr)

    def test_labs_open_with_shortcuts_and_keep_the_plumbing_route(self):
        for lab in ("feature", "bugfix", "refactor", "hardening", "research"):
            text = (DOCS / "tutorials" / f"{lab}-lab.md").read_text(encoding="utf-8")
            with self.subTest(lab=lab):
                self.assertIn("## Con shortcuts", text)
                self.assertIn(f"/rapid-{lab}", text)
                self.assertIn("--shortcuts", text)
                self.assertIn("modo avanzado", text.lower())
                self.assertLess(text.index("## Con shortcuts"), text.index("## 1. Overview"))
                self.assertIn("## 5. Guided Procedure", text)  # not deleted
                self.assertIn("rapid run create", text)
        hardening = (DOCS / "tutorials" / "hardening-lab.md").read_text(encoding="utf-8")
        self.assertIn("--archetype corporate", hardening)
        self.assertIn("--worktree", hardening)

    def test_antigravity_advanced_mode_includes_baseline_and_activation(self):
        text = (DOCS / "integrations" / "antigravity.md").read_text(encoding="utf-8")
        for needle in ("**Verificar Baseline:**", "rapid run gate <run-id> gate.baseline acknowledged",
                       "rapid run status <run-id> active", "rapid run task <run-id> T001 in_progress"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertLess(text.index("rapid run create --spec"), text.index("gate.baseline acknowledged"))
        self.assertLess(text.index("gate.baseline acknowledged"), text.index("rapid eval run"))

    def test_frontmatter_values_with_a_colon_are_quoted(self):
        """An unquoted `title:`/`description:` containing ': ' is invalid YAML and breaks the Docusaurus build."""
        offenders = []
        for page in sorted(DOCS.rglob("*.md")):
            text = page.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            header = text.split("---", 2)[1]
            for line in header.splitlines():
                key, _, value = line.partition(":")
                value = value.strip()
                if key.strip() in ("title", "description", "sidebar_label") and ": " in value:
                    if not (value[0] in "\"'" and value[-1] == value[0]):
                        offenders.append(f"{page.relative_to(DOCS).as_posix()}: {key.strip()}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()

"""F5: every project is born with concrete security rules traceable to standards, and with
scans that run in CI from the first PR. MVP and Corporate share the base; the level changes."""

from __future__ import annotations

import json
import re
import unittest
from dataclasses import replace
from pathlib import Path

from rapid_os.domain.catalog import load_catalog, load_setup_doc_banks, load_stack_questions
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.security import (
    CI_WORKFLOW_PATH,
    ci_workflow_path,
    ci_language,
    effective_ai,
    render_conditionals,
    render_security_standard,
)
from rapid_os.domain.setup import DocState, SetupActionKind, SetupState, SetupStateError, StackChoice
from rapid_os.orchestration.setup_conductor import ARCHETYPE_SUMMARIES, next_setup_action
from tests.stack_helpers import complete_stacks
from tests.test_no_git import GitIsolated

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
CATALOG = load_catalog(TEMPLATES)
BANKS = load_setup_doc_banks(TEMPLATES)
STACK_QUESTIONS = load_stack_questions(TEMPLATES)
BASELINE = (TEMPLATES / "security" / "baseline.md").read_text(encoding="utf-8")

TOP10_2025 = (
    "A01 Broken Access Control", "A02 Security Misconfiguration", "A03 Software Supply Chain Failures",
    "A04 Cryptographic Failures", "A05 Injection", "A06 Insecure Design", "A07 Authentication Failures",
    "A08 Software or Data Integrity Failures", "A09 Security Logging and Alerting Failures",
    "A10 Mishandling of Exceptional Conditions",
)
API_TOP10_2023 = (
    "API1 Broken Object Level Authorization", "API2 Broken Authentication",
    "API3 Broken Object Property Level Authorization", "API4 Unrestricted Resource Consumption",
    "API5 Broken Function Level Authorization", "API6 Unrestricted Access to Sensitive Business Flows",
    "API7 Server Side Request Forgery", "API8 Security Misconfiguration", "API9 Improper Inventory Management",
    "API10 Unsafe Consumption of APIs",
)
AGENTIC_2026 = (
    "ASI01 Agent Goal Hijack", "ASI02 Tool Misuse and Exploitation", "ASI03 Identity and Privilege Abuse",
    "ASI04 Agentic Supply Chain Vulnerabilities", "ASI05 Unexpected Code Execution (RCE)",
    "ASI06 Memory & Context Poisoning", "ASI08 Cascading Failures", "ASI09 Human-Agent Trust Exploitation",
)


def render(archetype="mvp", stack="python-api", ai=None):
    return render_security_standard(BASELINE, archetype=archetype, stack_id=stack, ai=ai)


def decided(stack="python-api", archetype="mvp", **extra) -> SetupState:
    return SetupState(
        stacks=complete_stacks(stack), topology="fullstack-separated", archetype=archetype, **extra
    )


def next_action(state):
    return next_setup_action(
        state, ProjectModel(root=Path(".")), CATALOG, BANKS,
        stack_questions=STACK_QUESTIONS, agent_ids=("claude", "codex"),
    )


class RenderTests(unittest.TestCase):
    def test_mvp_verifies_asvs_l1_and_the_ten_categories(self):
        text = render("mvp")
        self.assertIn("OWASP ASVS 5.0.0 nivel L1", text)
        self.assertNotIn("nivel L2", text)
        for category in TOP10_2025:
            with self.subTest(category=category):
                self.assertIn(category, text)
        self.assertNotIn("Build L2", text)
        self.assertNotIn("Source L2", text)

    def test_corporate_verifies_l2_and_slsa_build_l2(self):
        text = render("corporate")
        self.assertIn("OWASP ASVS 5.0.0 nivel L2", text)
        self.assertNotIn("nivel L1", text)
        self.assertIn("SLSA 1.2 Build L2", text)
        self.assertIn("procedencia firmada", text)
        self.assertIn("Source L2", text)
        for category in TOP10_2025:
            self.assertIn(category, text)  # the base is shared

    def test_no_marker_or_placeholder_is_left(self):
        for archetype in ("mvp", "corporate"):
            for stack in ("python-api", "python-ai", "docs-modern"):
                text = render(archetype, stack)
                for leftover in ("<!-- if", "<!-- endif", "{ASVS_LEVEL}", "TODO", "{{"):
                    self.assertNotIn(leftover, text, (archetype, stack, leftover))

    def test_api_items_only_for_stacks_with_an_api(self):
        for stack in ("python-api", "python-ai", "nodejs-ai", "web-modern"):
            text = render("mvp", stack)
            for item in API_TOP10_2023:
                with self.subTest(stack=stack, item=item):
                    self.assertIn(item, text)
        for stack in ("docs-modern", "frontend-creative", "generic"):
            self.assertNotIn("## OWASP API Security Top 10:2023", render("mvp", stack), stack)

    def test_the_explicit_api_rules_are_there(self):
        text = render("mvp", "python-api")
        for expected in (
            "autoriza por objeto en cada endpoint que recibe un id",
            "esquemas de salida explícitos sin campos sensibles",
            "rechaza la asignación masiva",
            "límites de tamaño de petición, paginación con tope y límites de tasa",
            "valida la firma y el contenido de los webhooks y de las respuestas de terceros",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_ssdf_slsa_cwe_cvss(self):
        text = render("mvp")
        for expected in (
            "PO (Prepare the Organization)", "PS (Protect Software)", "PW (Produce Well-Secured Software)",
            "RV (Respond to Vulnerabilities)", "modelo de amenazas breve", "autenticación, pagos o datos personales",
            "revisión humana del gate final", "severidad CVSS",
            "lockfile", "SHA completo", "CWE", "CVSS v4.0", "CVSS:4.0/",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_every_rule_names_its_reference_in_brackets(self):
        for archetype, stack, ai in (("corporate", "python-ai", True), ("mvp", "web-modern", False)):
            text = render(archetype, stack, ai)
            body = text.split("<!-- Fuentes verificadas:")[0]
            rules = [line for line in body.splitlines() if line.startswith("- ")]
            self.assertGreater(len(rules), 25)
            for line in rules:
                with self.subTest(rule=line[:60]):
                    self.assertRegex(line, r"\[[^\]]+\]")

    def test_official_sources_are_listed_in_an_html_comment(self):
        tail = BASELINE.split("<!-- Fuentes verificadas:")[1]
        for url in (
            "https://github.com/OWASP/ASVS", "https://top10.owasp.org/2025",
            "https://owasp.org/API-Security/editions/2023/en/0x11-t10/", "https://genai.owasp.org/llm-top-10/",
            "https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/",
            "https://csrc.nist.gov/pubs/sp/800/218/final", "https://slsa.dev/spec/v1.2/",
            "https://www.first.org/cvss/v4-0/specification-document", "https://cwe.mitre.org/",
        ):
            with self.subTest(url=url):
                self.assertIn(url, tail)
        self.assertTrue(BASELINE.rstrip().endswith("-->"))


class AiSectionTests(unittest.TestCase):
    def test_ai_stacks_get_the_section_without_an_answer(self):
        for stack in ("python-ai", "nodejs-ai"):
            self.assertIn("## Seguridad de IA", render("mvp", stack, ai=None), stack)
            self.assertTrue(effective_ai(stack, None))
            self.assertTrue(effective_ai(stack, False))

    def test_the_answer_decides_for_the_other_stacks(self):
        self.assertNotIn("## Seguridad de IA", render("mvp", "python-api", ai=False))
        self.assertNotIn("## Seguridad de IA", render("mvp", "python-api", ai=None))
        with_ai = render("mvp", "python-api", ai=True)
        self.assertIn("## Seguridad de IA", with_ai)
        for expected in (
            "salida del modelo es entrada no confiable", "inyección de instrucciones", "lista permitida y con el mínimo privilegio",
            "aprobación humana explícita", "pagos, borrados, mensajes a clientes", "Ningún secreto en los prompts ni en la memoria",
            "límites de costo y de iteraciones", "LLM01:2025 Prompt Injection", "LLM05:2025 Improper Output Handling",
            "LLM06:2025 Excessive Agency", "LLM10:2025 Unbounded Consumption",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, with_ai)
        for item in AGENTIC_2026:
            self.assertIn(item, with_ai)

    def test_the_conditional_markers(self):
        text = "a\n<!-- if x -->\nb\n<!-- if y -->\nc\n<!-- endif -->\nd\n<!-- endif -->\ne\n"
        self.assertEqual(render_conditionals(text, {"x", "y"}), "a\nb\nc\nd\ne\n")
        self.assertEqual(render_conditionals(text, {"x"}), "a\nb\nd\ne\n")
        self.assertEqual(render_conditionals(text, set()), "a\ne\n")
        yaml = "a\n# if corporate\nb\n# endif\nc\n"
        self.assertEqual(render_conditionals(yaml, {"corporate"}), "a\nb\nc\n")
        self.assertEqual(render_conditionals("# a comment\nx: 1\n", set()), "# a comment\nx: 1\n")


class ConductorTests(unittest.TestCase):
    def test_choose_ai_comes_after_the_archetype_and_only_for_non_ai_stacks(self):
        action = next_action(decided("python-api"))
        self.assertEqual(action.kind, SetupActionKind.CHOOSE_AI)
        payload = action.to_dict()
        self.assertEqual(
            payload["question"],
            "¿El producto usará modelos de IA o agentes (por ejemplo, un asistente que responda por WhatsApp)?",
        )
        self.assertEqual(payload["command"], ["rapid", "setup", "set", "ai", "<yes|no>"])
        self.assertEqual([o["id"] for o in payload["options"]], ["yes", "no"])
        for stack in ("python-ai", "nodejs-ai"):
            # (the ids of before the component catalog answer `ai: yes` themselves)
            self.assertEqual(next_action(decided(stack, ai=True)).kind, SetupActionKind.CHOOSE_AGENTS, stack)

    def test_an_answer_moves_on_to_the_agents(self):
        for answer in (True, False):
            self.assertEqual(next_action(decided("python-api", ai=answer)).kind, SetupActionKind.CHOOSE_AGENTS)

    def test_the_archetype_comes_first(self):
        state = SetupState(stacks=complete_stacks("python-api"), topology="fullstack-separated")
        self.assertEqual(next_action(state).kind, SetupActionKind.CHOOSE_ARCHETYPE)

    def test_both_archetypes_say_they_include_the_baseline(self):
        for summary in ARCHETYPE_SUMMARIES.values():
            self.assertIn("security baseline", summary)
        self.assertIn("ASVS L2", ARCHETYPE_SUMMARIES["corporate"])
        self.assertIn("Build L2", ARCHETYPE_SUMMARIES["corporate"])


class StateCompatibilityTests(unittest.TestCase):
    def data(self, **extra):
        base = replace(decided(), agents=("codex",), test_command=()).to_dict()
        base.pop("ai", None)
        return {**base, **extra}

    def test_a_file_without_the_field_is_undecided_unless_the_setup_is_finished(self):
        self.assertIsNone(SetupState.from_dict(self.data(finished=False)).ai)
        self.assertIs(SetupState.from_dict(self.data(finished=True)).ai, False)

    def test_the_field_round_trips_and_is_omitted_while_undecided(self):
        self.assertNotIn("ai", decided().to_dict())
        for value in (True, False):
            state = decided(ai=value)
            self.assertIs(SetupState.from_dict(state.to_dict()).ai, value)
            self.assertIs(state.to_dict()["ai"], value)

    def test_a_non_boolean_is_rejected(self):
        with self.assertRaises(SetupStateError):
            SetupState.from_dict(self.data(ai="yes"))


class Project(GitIsolated):
    def decide(self, stack, topology, archetype, ai=None):
        steps = [("stack", stack), ("topology", topology)]
        if topology == "fullstack-separated" and stack in ("python-api", "python-ai", "nodejs-ai"):
            steps.append(("stack", "react-vite"))  # the frontend of the topology
        steps.append(("archetype", archetype))
        if ai is not None:
            steps.append(("ai", ai))
        steps += [("agents", "codex"), ("test-command", "none"), ("services", "none")]
        for key, value in steps:
            result = self.rapid("setup", "set", key, value)
            self.assertEqual(result.returncode, 0, result.stderr)

    def write_decisions(self, stack, topology, archetype, ai):
        """The decisions of a complete onboarding, written as `setup.json` (what the `set` and `doc
        --skip` commands leave), so the tests that are not about those commands stay fast."""
        state = SetupState(
            stacks=complete_stacks(stack), topology=topology, archetype=archetype,
            ai=None if ai is None else ai == "yes", agents=("codex",), test_command=(), services=(),
            docs={doc: DocState("skipped") for doc in ("brief", "business", "data-model", "architecture", "deployment")},
        )
        path = self.root / ".rapid-os" / "setup.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")

    def finish(self, stack="python-api", topology="fullstack-separated", archetype="mvp", ai="no"):
        self.write_decisions(stack, topology, archetype, ai)
        result = self.rapid("setup", "finish")
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    @property
    def standards(self) -> Path:
        return self.root / ".rapid-os" / "standards"

    def security(self) -> str:
        return (self.standards / "security.md").read_text(encoding="utf-8")

    def workflow(self, language: str = "python") -> Path:
        return self.root / ci_workflow_path(language)


class SecurityStandardInTheProjectTests(Project):
    def test_mvp_python_api(self):
        self.finish("python-api", archetype="mvp", ai="no")
        text = self.security()
        self.assertIn("ASVS 5.0.0 nivel L1", text)
        for category in TOP10_2025 + API_TOP10_2023:
            self.assertIn(category, text)
        self.assertNotIn("## Seguridad de IA", text)

    def test_corporate_is_l2_with_slsa(self):
        self.finish("python-api", archetype="corporate", ai="no")
        text = self.security()
        self.assertIn("ASVS 5.0.0 nivel L2", text)
        self.assertIn("SLSA 1.2 Build L2", text)

    def test_docs_modern_has_no_api_section(self):
        self.finish("docs-modern", "doc-site", ai="no")
        self.assertNotIn("## OWASP API Security Top 10:2023", self.security())
        self.assertIn("A01 Broken Access Control", self.security())

    def test_python_ai_is_never_asked_and_gets_the_ai_section(self):
        for key, value in (
            ("stack", "python-ai"), ("topology", "fullstack-separated"), ("stack", "react-vite"), ("archetype", "mvp"),
        ):
            self.assertEqual(self.rapid("setup", "set", key, value).returncode, 0)
        action = json.loads(self.rapid("setup", "next", "--json").stdout)
        self.assertEqual(action["kind"], "choose_agents")
        self.assertEqual(self.rapid("setup", "set", "agents", "codex").returncode, 0)
        self.assertEqual(self.rapid("setup", "set", "test-command", "none").returncode, 0)
        self.assertEqual(self.rapid("setup", "set", "services", "none").returncode, 0)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            self.rapid("setup", "doc", doc, "--skip")
        self.assertEqual(self.rapid("setup", "finish").returncode, 0)
        self.assertIn("## Seguridad de IA (LLM y agentes)", self.security())

    def test_python_api_follows_the_answer(self):
        self.finish("python-api", ai="no")
        self.assertNotIn("## Seguridad de IA", self.security())
        # Answering yes afterwards applies at once (the setup is finished) and keeps a backup.
        changed = self.rapid("setup", "set", "ai", "yes")
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.assertIn("## Seguridad de IA", self.security())
        self.assertTrue((self.standards / "security.md.bak").exists() or list(self.standards.glob("security*.bak")))
        shown = json.loads(self.rapid("setup", "show", "--json").stdout)["state"]
        self.assertIs(shown["ai"], True)
        self.assertTrue(shown["finished"])

    def test_the_ai_answer_must_be_yes_or_no(self):
        result = self.rapid("setup", "set", "ai", "maybe")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1413", result.stderr)

    def test_the_agent_files_carry_the_baseline(self):
        self.finish("python-api", ai="no")
        self.assertIn("SEGURIDAD: BASE OBLIGATORIA", (self.root / "AGENTS.md").read_text("utf-8"))


class CiWorkflowTests(Project):
    def uses_lines(self, language="python"):
        return [l.strip() for l in self.workflow(language).read_text("utf-8").splitlines() if "uses:" in l]

    def test_setup_finish_in_an_empty_repository_writes_the_workflow(self):
        result = self.finish("python-api", archetype="mvp", ai="no")
        self.assertTrue(self.workflow().is_file())
        self.assertIn("Rapid OS añadió este workflow; revísalo antes del primer commit", result.stdout)
        self.assertIn(ci_workflow_path("python"), result.stdout)

    def test_the_json_output_names_the_added_file(self):
        self.write_decisions("python-api", "fullstack-separated", "mvp", "no")
        done = self.rapid("setup", "finish", "--json")
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertEqual(
            payload["added_files"],
            [{"file": ci_workflow_path("python"), "note": "Rapid OS añadió este workflow; revísalo antes del primer commit"}],
        )

    def test_the_review_of_the_drafts_announces_it_beforehand(self):
        self.decide("python-api", "fullstack-separated", "mvp", "no")
        self.assertEqual(
            self.rapid("setup", "doc", "brief", "--source", "drafted", "--file", "-",
                       stdin="## Problema\nx\n\n## Usuarios\nx\n\n## Historias\n- [ ] H001: x\n").returncode, 0)
        for doc in ("business", "data-model", "architecture", "deployment"):
            self.rapid("setup", "doc", doc, "--skip")
        review = json.loads(self.rapid("setup", "next", "--json").stdout)
        self.assertEqual(review["kind"], "review_drafts")
        self.assertEqual(review["planned_files"][0]["file"], ci_workflow_path("python"))
        self.assertIn("revísalo antes del primer commit", review["planned_files"][0]["note"])
        self.assertFalse(self.workflow().exists())  # nothing is written until the onboarding closes

    def test_an_existing_workflow_is_never_overwritten(self):
        self.workflow().parent.mkdir(parents=True)
        self.workflow().write_text("name: mine\n", encoding="utf-8")
        result = self.finish("python-api", ai="no")
        self.assertEqual(self.workflow().read_text("utf-8"), "name: mine\n")
        self.assertNotIn("Rapid OS añadió este workflow", result.stdout)

    def test_a_project_with_the_workflow_of_before_is_left_as_it_is(self):
        legacy = self.root / CI_WORKFLOW_PATH
        legacy.parent.mkdir(parents=True)
        legacy.write_text("name: rapid-security\n", encoding="utf-8")
        result = self.finish("python-api", ai="no")
        self.assertEqual(legacy.read_text("utf-8"), "name: rapid-security\n")
        self.assertFalse(self.workflow().exists())  # no second workflow next to the one it already has
        self.assertNotIn("Rapid OS añadió este workflow", result.stdout)

    def test_the_workflow_is_named_after_its_language_also_with_one_component(self):
        self.finish("python-api", ai="no")
        self.assertFalse((self.root / CI_WORKFLOW_PATH).exists())
        self.assertTrue(self.workflow().read_text("utf-8").startswith("# Escaneos"))
        self.assertIn("\nname: rapid-security (python)\n", self.workflow().read_text("utf-8"))

    def test_a_repository_with_code_does_not_get_it(self):
        (self.root / "app").mkdir()
        (self.root / "app" / "main.py").write_text("print('hi')\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_main.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        self.finish("python-api", ai="no")
        self.assertFalse(self.workflow().exists())

    def test_python_jobs(self):
        self.finish("python-api", archetype="mvp", ai="no")
        text = self.workflow().read_text("utf-8")
        for expected in (
            "pull_request:", "branches: [main]", "gitleaks", "semgrep scan --config p/owasp-top-ten",
            "bandit", "pip-audit",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)
        self.assertNotIn("npm audit", text)
        self.assertNotIn("sbom", text)
        self.assertNotIn("attest-build-provenance", text)

    def test_typescript_jobs(self):
        self.finish("web-modern", "fullstack-baas", archetype="mvp", ai="no")
        text = self.workflow("typescript").read_text("utf-8")
        self.assertIn("npm audit --audit-level=high", text)
        self.assertIn("semgrep scan --config p/owasp-top-ten", text)
        self.assertNotIn("bandit", text)
        self.assertNotIn("pip-audit", text)

    def test_corporate_adds_the_sbom_and_the_provenance(self):
        self.finish("python-api", archetype="corporate", ai="no")
        text = self.workflow().read_text("utf-8")
        self.assertIn("anchore/sbom-action@", text)
        self.assertIn("actions/attest-build-provenance@", text)
        self.assertIn("attestations: write", text)

    def test_every_action_is_pinned_by_a_full_sha_with_its_version(self):
        for stack, topology, archetype in (
            ("python-api", "fullstack-separated", "corporate"),
            ("web-modern", "fullstack-baas", "corporate"),
        ):
            with self.subTest(stack=stack):
                language = "python" if stack == "python-api" else "typescript"
                self.workflow(language).unlink(missing_ok=True)
                self.finish(stack, topology, archetype, ai="no")  # `setup set` again: the setup is finished
                lines = self.uses_lines(language)
                self.assertGreater(len(lines), 5)
                for line in lines:
                    self.assertRegex(line, r"uses: [\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+$", line)

    def test_no_action_is_referenced_by_a_tag_or_branch(self):
        for name in ("python-security.yml", "typescript-security.yml"):
            text = (TEMPLATES / "ci" / name).read_text("utf-8")
            for match in re.finditer(r"uses:\s*(\S+)", text):
                self.assertRegex(match.group(1), r"@[0-9a-f]{40}$", (name, match.group(1)))
            self.assertIn("sha256sum -c", text)  # the gitleaks binary is checked, not trusted

    def test_the_stack_without_a_language_gets_no_workflow(self):
        self.assertIsNone(ci_language("custom"))
        self.assertIsNone(ci_language("generic"))
        self.assertEqual(ci_language("generic", ["Python"]), "python")
        self.assertEqual(ci_language("generic", ["javascript"]), "typescript")


class RefreshAndDoctorTests(Project):
    OLD = "# 🛡️ SECURITY STANDARD (MINIMAL)\n\n1. **Secrets:** never commit `.env` files.\n"

    def doctor_codes(self):
        report = json.loads(self.rapid("doctor", "--json").stdout)
        return {d["code"]: d for d in report["diagnostics"]}

    def test_doctor_warns_when_security_md_does_not_mention_asvs(self):
        self.finish("python-api", archetype="mvp", ai="no")
        self.assertNotIn("RAPID1421", self.doctor_codes())
        (self.standards / "security.md").write_text(self.OLD, encoding="utf-8")
        diagnostic = self.doctor_codes()["RAPID1421"]
        self.assertEqual(diagnostic["level"], "warning")
        self.assertIn("ASVS", diagnostic["message"])
        self.assertIn("rapid setup set archetype mvp --refresh", diagnostic["hint"])

    def test_the_hint_names_the_archetype_of_the_project(self):
        self.finish("python-api", archetype="corporate", ai="no")
        (self.standards / "security.md").write_text(self.OLD, encoding="utf-8")
        self.assertIn("set archetype corporate --refresh", self.doctor_codes()["RAPID1421"]["hint"])

    def test_refresh_regenerates_both_files_with_a_backup_and_clears_the_warning(self):
        self.finish("python-api", archetype="mvp", ai="no")
        (self.standards / "security.md").write_text(self.OLD, encoding="utf-8")
        (self.standards / "coding-rules.md").write_text("old rules\n", encoding="utf-8")
        refreshed = self.rapid("setup", "set", "archetype", "mvp", "--refresh")
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
        self.assertIn("ASVS 5.0.0 nivel L1", self.security())
        self.assertIn("La velocidad nunca rebaja la base", (self.standards / "coding-rules.md").read_text("utf-8"))
        # The previous copies go to .rapid-os/backups/, not next to the standards the agent reads.
        self.assertEqual(list(self.standards.glob("*.bak")), [])
        backups_dir = self.root / ".rapid-os" / "backups"
        backups = {p.read_text("utf-8") for p in backups_dir.glob("*.bak")}
        self.assertIn(self.OLD, backups)
        self.assertIn("old rules\n", backups)
        self.assertTrue(any(p.name.startswith("security.md.") for p in backups_dir.glob("*.bak")))
        self.assertTrue(any(p.name.startswith("coding-rules.md.") for p in backups_dir.glob("*.bak")))
        self.assertNotIn("RAPID1421", self.doctor_codes())
        self.assertIn("SEGURIDAD: BASE OBLIGATORIA", (self.root / "AGENTS.md").read_text("utf-8"))

    def test_refresh_only_goes_with_the_archetype(self):
        self.finish("python-api", ai="no")
        result = self.rapid("setup", "set", "agents", "codex", "--refresh")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1413", result.stderr)

    def test_without_a_security_standard_doctor_stays_quiet(self):
        self.assertNotIn("RAPID1421", self.doctor_codes())


class TemplatesTests(unittest.TestCase):
    def test_mvp_rules_keep_no_loose_typing_and_add_the_base(self):
        text = (TEMPLATES / "archetypes" / "mvp" / "coding-rules.md").read_text("utf-8")
        self.assertNotIn("any", text.replace("Anything", "").replace("many", ""))
        self.assertNotIn("loose typing", text)
        self.assertIn("La velocidad nunca rebaja la base de seguridad ni la arquitectura modular", text)

    def test_corporate_security_is_gone_and_the_minimal_one_stays_for_hardening(self):
        self.assertFalse((TEMPLATES / "archetypes" / "corporate" / "security.md").exists())
        self.assertTrue((TEMPLATES / "archetypes" / "default-security.md").is_file())

    def test_hardening_template_asks_for_classified_findings(self):
        data = json.loads((TEMPLATES / "modes" / "hardening.json").read_text("utf-8"))
        (finding,) = data["spec_template"]["findings"]
        self.assertEqual(set(finding), {"id", "title", "cwe", "cvss_v4_vector", "severity", "standard_ref"})
        self.assertTrue(finding["cvss_v4_vector"].startswith("CVSS:4.0/"))
        instruction = data["instructions"]["author_spec"]
        for expected in ("CWE", "CVSS v4.0", "security.md", "acceptance_criteria"):
            self.assertIn(expected, instruction)

    def test_spec_cli_accepts_structured_finding_json(self):
        from rapid_os.cli.main import _extract_non_interactive_spec_fields, create_parser

        raw = '{"id":"H001","title":"Reject input","cwe":"CWE-20","cvss_v4_vector":"CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N","severity":"medium","standard_ref":"CWE, CVSS v4.0"}'
        args = create_parser().parse_args(["spec", "create", "--finding-json", raw])
        self.assertEqual(_extract_non_interactive_spec_fields(args)["findings"][0]["id"], "H001")

    def test_a_hardening_spec_with_findings_is_accepted(self):
        import tempfile

        from rapid_os.adapters.spec_registry import SpecRegistry

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".rapid-os").mkdir()
            data = json.loads((TEMPLATES / "modes" / "hardening.json").read_text("utf-8"))
            fields = {k: v for k, v in data["spec_template"].items() if k != "title"}
            record = SpecRegistry(root, root / ".rapid-os").create(title="Endurecer entradas", mode="hardening", **fields)
            self.assertEqual(record.id, "endurecer-entradas")

    def test_the_init_shortcut_covers_the_new_steps(self):
        text = (TEMPLATES / "shortcuts" / "rapid-init.md").read_text("utf-8")
        for expected in ("choose_ai", "action.question", "planned_files", "added_files", "rapid-security"):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()

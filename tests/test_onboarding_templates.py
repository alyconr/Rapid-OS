"""Fixes of the 3.2.0rc1 e2e for the onboarding: hooks without duplicated skills, the architecture
standard in the draft, the test command by package manager, the backend-only topology, the stack
templates, the backups of the confirmed documents, doctor and the hook log."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.adapters.shortcut_installer import detect_scope_duplicates
from rapid_os.domain.architecture import architecture_document, architecture_standard, load_rules
from rapid_os.domain.catalog import load_catalog
from rapid_os.domain.validation import validate_project_standards
from rapid_os.orchestration.hook_runtime import describe_stdin
from rapid_os.orchestration import setup_apply

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


class Project(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.root = self.base / "project"
        self.root.mkdir()
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def rapid(self, *argv, cwd=None, stdin=None, raw=None):
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *argv],
            cwd=cwd or self.root, capture_output=True, env=self.env,
            input=raw if raw is not None else (stdin.encode("utf-8") if stdin is not None else None),
        )

    def run_text(self, *argv, **kwargs):
        result = self.rapid(*argv, **kwargs)
        return result.returncode, result.stdout.decode("utf-8", "replace"), result.stderr.decode("utf-8", "replace")

    def ok(self, *argv, **kwargs):
        code, out, err = self.run_text(*argv, **kwargs)
        self.assertEqual(code, 0, f"{argv}: {out}{err}")
        return out

    def decide(self, topology, *stacks, ai="no", agents="claude"):
        for spec in stacks:
            if ":" in spec:
                stack, component = spec.split(":")
                self.ok("setup", "set", "stack", stack, "--component", component)
            else:
                self.ok("setup", "set", "stack", spec)
        self.ok("setup", "set", "topology", topology)
        self.ok("setup", "set", "archetype", "mvp")
        self.ok("setup", "set", "ai", ai)
        self.ok("setup", "set", "agents", agents)

    def next_json(self):
        return json.loads(self.ok("setup", "next", "--json"))

    def finish_onboarding(self, test_command="none"):
        self.ok("setup", "set", "test-command", test_command)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            if doc == "data-model":
                self.ok("setup", "set", "services", "none")
            self.ok("setup", "doc", doc, "--skip")
        return self.ok("setup", "finish")


class HooksWithoutDuplicatedSkillsTests(Project):
    def test_setup_finish_installs_the_claude_hooks_and_no_skills(self):
        self.decide("backend-only", "python-fastapi")
        output = self.finish_onboarding()
        self.assertIn("instaló los hooks de Claude Code", output)
        settings = json.loads((self.root / ".claude" / "settings.json").read_text("utf-8"))
        self.assertEqual(sorted(settings["hooks"]), ["PreToolUse", "Stop"])
        self.assertFalse((self.root / ".claude" / "skills").exists())

    def test_other_agents_get_no_hooks(self):
        self.decide("backend-only", "python-fastapi", agents="codex")
        output = self.finish_onboarding()
        self.assertNotIn("hooks de Claude Code", output)
        self.assertFalse((self.root / ".claude" / "settings.json").exists())

    def test_global_with_hooks_outside_a_project_is_rapid1413_with_the_way_out(self):
        code, _out, err = self.run_text("shortcuts", "install", "--global", "--harness", "claude", "--hooks")
        self.assertEqual(code, 1)
        self.assertIn("RAPID1413", err)
        self.assertIn("dentro de un proyecto", err)
        self.assertFalse((self.home / ".claude").exists())

    def test_global_with_hooks_inside_a_project_installs_user_skills_and_project_hooks(self):
        self.decide("backend-only", "python-fastapi")
        self.finish_onboarding()
        (self.root / ".claude" / "settings.json").unlink()
        self.ok("shortcuts", "install", "--global", "--harness", "claude", "--hooks")
        self.assertTrue((self.home / ".claude" / "skills" / "rapid-init" / "SKILL.md").is_file())
        self.assertTrue((self.root / ".claude" / "settings.json").is_file())
        self.assertFalse((self.root / ".claude" / "skills").exists())

    def test_a_shortcut_in_the_user_and_in_the_project_is_reported_as_rapid1321(self):
        self.decide("backend-only", "python-fastapi")
        self.finish_onboarding()
        self.ok("shortcuts", "install", "--global", "--harness", "claude")
        self.assertEqual(detect_scope_duplicates(self.home, self.root, ["claude"], TEMPLATES), [])
        code, _out, err = self.run_text("shortcuts", "install", "--harness", "claude")
        self.assertEqual(code, 0)
        self.assertIn("RAPID1321 claude: 9 shortcut(s)", err)
        self.assertIn("rapid shortcuts remove --global --harness claude", err)
        found = detect_scope_duplicates(self.home, self.root, ["claude"], TEMPLATES)
        self.assertEqual([d.harness for d in found], ["claude"])
        self.assertIn("rapid-init", found[0].shortcuts)
        _code, out, _err = self.run_text("doctor")
        self.assertIn("RAPID1321", out)


class ArchitectureStandardInTheDraftTests(Project):
    def reach_architecture(self):
        self.ok("setup", "set", "test-command", "none")
        self.ok("setup", "doc", "brief", "--skip")
        self.ok("setup", "doc", "business", "--skip")
        self.ok("setup", "set", "services", "none")
        self.ok("setup", "doc", "data-model", "--skip")
        action = self.next_json()
        self.assertEqual((action["kind"], action["doc"]), ("resolve_doc", "architecture"))
        return action

    def test_the_action_carries_the_standard_per_component_from_the_catalog(self):
        self.decide("fullstack-separated", "python-fastapi", "nextjs:frontend")
        action = self.reach_architecture()
        by_component = {item["component"]: item for item in action["standard"]}
        backend, frontend = by_component["backend"], by_component["frontend"]
        self.assertEqual((backend["modules_root"], backend["public_entry"]), ("backend/app/modules", "public.py"))
        self.assertEqual((frontend["modules_root"], frontend["public_entry"]), ("frontend/src/features", "index.ts"))
        self.assertEqual([l["layer"] for l in backend["layers"]], ["api", "application", "domain", "infrastructure"])
        self.assertTrue(any("public.py" in rule for rule in backend["dependency_rules"]))
        self.assertIn("no inventes otro punto público", action["standard_instruction"])
        # The standard is the one `finish` will write: the same rule, from the same catalog.
        written = {c.component: c for c in load_rules(architecture_document({"backend": "python-fastapi", "frontend": "nextjs"}))}
        self.assertEqual(backend["modules_root"], written["backend"].modules_root)
        self.assertEqual(backend["public_entry"], written["backend"].public_entry)

    def test_a_backend_only_project_has_one_component_at_the_root(self):
        self.decide("backend-only", "python-fastapi")
        action = self.reach_architecture()
        self.assertEqual([(i["component"], i["modules_root"]) for i in action["standard"]], [("backend", "app/modules")])

    def test_the_dependency_rules_question_cites_the_standard_of_the_action(self):
        bank = json.loads((TEMPLATES / "setup" / "docs" / "architecture.json").read_text("utf-8"))
        question = next(q for q in bank["questions"] if q["id"] == "dependency_rules")
        self.assertIn("`standard` de esta acción", question["text"])
        self.assertNotIn("cita las del estándar de arquitectura", question["text"])

    def test_no_standard_for_a_stack_without_a_rule(self):
        self.assertEqual(architecture_standard({"docs": "docs-modern"}), [])


class TestCommandTests(Project):
    def test_a_separated_project_gets_a_combined_command_with_the_folders(self):
        self.decide("fullstack-separated", "python-fastapi", "nextjs:frontend")
        action = self.next_json()
        self.assertEqual(action["kind"], "set_test_command")
        commands = {item["component"]: item["command"] for item in action["components"]}
        self.assertEqual(commands["backend"], ["uv", "run", "--directory", "backend", "pytest"])
        self.assertEqual(commands["frontend"], ["pnpm", "--dir", "frontend", "exec", "vitest", "run"])
        recommended = action["recommended"]
        self.assertEqual(recommended[:2], ["python", "-c"])
        self.assertIn("uv", recommended[2])
        self.assertIn("frontend", recommended[2])

    def test_one_component_at_the_root_is_its_plain_command(self):
        self.decide("backend-only", "python-fastapi")
        action = self.next_json()
        self.assertEqual(action["recommended"], ["uv", "run", "pytest"])

    def test_the_combined_command_fails_when_any_part_fails(self):
        from rapid_os.orchestration.setup_conductor import combine_test_commands

        ok, bad = [sys.executable, "-c", "pass"], [sys.executable, "-c", "raise SystemExit(3)"]
        self.assertEqual(subprocess.run(combine_test_commands([ok, ok])).returncode, 0)
        self.assertEqual(subprocess.run(combine_test_commands([ok, bad])).returncode, 3)
        self.assertEqual(subprocess.run(combine_test_commands([bad, ok])).returncode, 3)
        self.assertEqual(combine_test_commands([ok]), ok)

    def test_every_catalog_stack_with_a_subdir_command_names_the_folder(self):
        catalog = load_catalog(TEMPLATES)
        for entry in catalog.stacks.values():
            if entry.test_command_subdir:
                with self.subTest(stack=entry.id):
                    self.assertTrue(any("{root}" in token for token in entry.test_command_subdir))
                    self.assertIn("web", " ".join(entry.test_command("web")) if entry.test_command("web") else "web")
                    self.assertNotIn("{root}", " ".join(entry.test_command("web")))


class BackendOnlyTopologyTests(Project):
    def test_the_topology_is_in_the_catalog_with_one_backend_component(self):
        catalog = load_catalog(TEMPLATES)
        self.assertEqual(catalog.topologies["backend-only"].components, ("backend",))
        for stack in ("python-fastapi", "go", "node-fastify", "java-spring-boot"):
            self.assertIn("backend-only", catalog.stacks[stack].compatible_topologies)
        self.assertNotIn("backend-only", catalog.stacks["nextjs"].compatible_topologies)
        self.assertNotIn("backend-only", catalog.stacks["docs-modern"].compatible_topologies)
        self.assertTrue((TEMPLATES / "topologies" / "backend-only.md").is_file())

    def test_the_conductor_offers_it_after_a_backend_stack_and_asks_no_frontend(self):
        self.ok("setup", "set", "stack", "python-fastapi")
        options = [o["id"] for o in self.next_json()["options"]]
        self.assertIn("backend-only", options)
        self.ok("setup", "set", "topology", "backend-only")
        self.ok("setup", "set", "archetype", "mvp")
        self.assertEqual(self.next_json()["kind"], "choose_ai")  # no choose_stack for a frontend

    def test_a_frontend_stack_is_not_compatible(self):
        self.ok("setup", "set", "stack", "react-vite")
        code, _out, err = self.run_text("setup", "set", "topology", "backend-only")
        self.assertEqual(code, 1)
        self.assertIn("RAPID1402", err)

    def test_the_onboarding_closes_with_the_architecture_at_the_root_and_the_topology_text(self):
        self.decide("backend-only", "python-fastapi")
        self.finish_onboarding()
        rule = json.loads((self.root / ".rapid-os" / "standards" / "architecture.json").read_text("utf-8"))
        self.assertEqual((rule["modules_root"], rule["public_entry"]), ("app/modules", "public.py"))
        self.assertNotIn("root", rule)
        topology = (self.root / ".rapid-os" / "standards" / "topology.md").read_text("utf-8")
        self.assertIn("BACKEND ONLY", topology)
        self.assertIn("Frontend:** NONE", topology)

    def test_the_shortcut_offers_it_when_the_brief_describes_an_api(self):
        text = (TEMPLATES / "shortcuts" / "rapid-init.md").read_text("utf-8")
        self.assertIn("`backend-only`", text)
        self.assertIn("sin interfaz", text)


class StackTemplateTests(Project):
    def tech_stack(self):
        return (self.root / ".rapid-os" / "standards" / "tech-stack.md").read_text("utf-8")

    def test_a_separated_frontend_does_not_declare_a_database(self):
        self.decide("fullstack-separated", "python-fastapi", "nextjs:frontend")
        self.finish_onboarding()
        text = self.tech_stack()
        next_block = text[text.index("TECH STACK: NEXT.JS"):]
        self.assertNotIn("Database", next_block)
        self.assertIn("Framework:** Next.js", next_block)

    def test_nextjs_alone_keeps_its_database_line(self):
        self.decide("fullstack-baas", "nextjs")
        self.finish_onboarding()
        self.assertIn("Database", self.tech_stack())

    def test_ai_yes_leaves_the_orchestration_as_a_decision(self):
        self.decide("backend-only", "python-fastapi", ai="yes")
        self.finish_onboarding()
        text = self.tech_stack()
        self.assertIn("to decide, not imposed", text)
        self.assertNotIn("LangChain / CrewAI / LangGraph", text)

    def test_the_python_version_is_explicit_and_comes_from_the_environment(self):
        (self.root / ".python-version").write_text("3.13.1\n", encoding="utf-8")
        self.decide("backend-only", "python-fastapi")
        self.finish_onboarding()
        self.assertIn("Runtime:** Python 3.13 (taken from .python-version", self.tech_stack())
        self.assertNotIn("{python_version}", self.tech_stack())

    def test_python_version_sources_in_order(self):
        for relative, content, expected in (
            (".python-version", "3.11\n", "3.11"),
            ("pyproject.toml", '[project]\nrequires-python = ">=3.12"\n', "3.12"),
        ):
            with self.subTest(source=relative), tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / relative).write_text(content, encoding="utf-8")
                version, source = setup_apply.detect_python_version(Path(tmp))
                self.assertEqual(version, expected)
                self.assertTrue(source.startswith(relative))
        with tempfile.TemporaryDirectory() as tmp:
            version, source = setup_apply.detect_python_version(Path(tmp))
            self.assertRegex(version, r"^3\.\d+$")
            self.assertIn("Rapid OS", source)

    def test_the_gitignore_has_what_each_stack_generates(self):
        (self.root / ".gitignore").write_text("custom\n", encoding="utf-8")
        self.decide("fullstack-separated", "python-fastapi", "nextjs:frontend")
        self.finish_onboarding()
        lines = (self.root / ".gitignore").read_text("utf-8").splitlines()
        for expected in (".rapid-os/session.json", ".venv/", "node_modules/", ".next/", ".env"):
            self.assertIn(expected, lines)

    def test_a_missing_gitignore_is_not_created(self):
        self.decide("backend-only", "python-fastapi")
        self.finish_onboarding()
        self.assertFalse((self.root / ".gitignore").exists())

    def test_an_existing_gitignore_only_gets_what_is_missing(self):
        (self.root / ".gitignore").write_text("node_modules/\ncustom\n", encoding="utf-8")
        added = setup_apply.update_gitignore(self.root, ["node_modules/", ".next/"])
        self.assertIn(".next/", added)
        self.assertNotIn("node_modules/", added)
        text = (self.root / ".gitignore").read_text("utf-8")
        self.assertEqual(text.count("node_modules/"), 1)
        self.assertTrue(text.startswith("node_modules/\ncustom\n"))


class ConfirmBackupsTests(Project):
    DRAFT = (
        "## Problema\nAgendar talleres.\n\n## Usuarios\nOrganizadores.\n\n## Historias\n- [ ] H001: Crear taller\n"
    )

    def test_confirm_leaves_no_bak_next_to_the_document(self):
        self.decide("backend-only", "python-fastapi")
        self.ok("setup", "doc", "brief", "--source", "drafted", "--file", "-", stdin=self.DRAFT)
        self.ok("setup", "doc", "brief", "--confirm")
        self.ok("setup", "doc", "brief", "--reopen")
        self.ok("setup", "doc", "brief", "--confirm")
        self.assertEqual(sorted(p.name for p in (self.root / "docs").glob("*.bak")), [])
        self.assertEqual(sorted(p.name for p in (self.root / "docs").iterdir()), ["PRODUCT_BRIEF.md"])
        backups = list((self.root / ".rapid-os" / "backups").glob("PRODUCT_BRIEF*"))
        self.assertTrue(backups)
        self.assertIn("status: confirmed", (self.root / "docs" / "PRODUCT_BRIEF.md").read_text("utf-8"))


class SetupShowAndDoctorTests(Project):
    def test_setup_show_says_draft_or_confirmed(self):
        self.decide("backend-only", "python-fastapi")
        self.ok("setup", "doc", "brief", "--source", "drafted", "--file", "-", stdin=ConfirmBackupsTests.DRAFT)
        self.assertIn("brief=drafted (draft)", self.ok("setup", "show"))
        self.ok("setup", "doc", "brief", "--confirm")
        self.assertIn("brief=drafted (confirmed)", self.ok("setup", "show"))
        self.ok("setup", "doc", "business", "--skip")
        self.assertIn("business=skipped", self.ok("setup", "show"))

    def standards(self, with_business_doc):
        rapid = self.root / ".rapid-os"
        (rapid / "standards").mkdir(parents=True)
        for name in ("tech-stack.md", "topology.md", "security.md", "coding-rules.md"):
            (rapid / "standards" / name).write_text(f"# {name}\n\nContenido.\n", encoding="utf-8")
        if with_business_doc:
            (self.root / "docs").mkdir()
            (self.root / "docs" / "BUSINESS_RULES.md").write_text("# Reglas\n", encoding="utf-8")
        return rapid

    def codes(self, rapid):
        return [d.code for d in validate_project_standards(rapid).diagnostics]

    def test_rapid203_is_not_raised_for_business_md_when_business_rules_exist(self):
        self.assertIn("RAPID203", self.codes(self.standards(with_business_doc=False)))

    def test_rapid203_stays_quiet_with_docs_business_rules(self):
        self.assertNotIn("RAPID203", self.codes(self.standards(with_business_doc=True)))

    def test_rapid908_explains_how_the_harness_is_resolved(self):
        self.decide("backend-only", "python-fastapi", agents="claude,codex")
        self.finish_onboarding()
        _code, out, _err = self.run_text("doctor")
        line = next(l for l in out.splitlines() if "Default harness" in l)
        self.assertNotIn("fallback: cursor", line)
        self.assertIn("claude, codex", line)
        self.assertIn("--harness, RAPID_HARNESS", line)


class ServicesMessageTests(unittest.TestCase):
    def test_it_does_not_say_the_sandbox_cannot_run_docker(self):
        from rapid_os.domain.services import LOCAL_SERVICES_ACTION

        why = LOCAL_SERVICES_ACTION["why"]
        self.assertNotIn("sandbox", why)
        self.assertIn("La persona levanta los servicios", why)
        self.assertIn("DATABASE_URL", why)
        shortcut = (TEMPLATES / "shortcuts" / "rapid-init.md").read_text("utf-8")
        self.assertNotIn("el sandbox no ejecuta Docker", shortcut)
        self.assertIn("no concluyas que no puedes probar contra la base de datos", shortcut)


class HookInputTests(Project):
    def project(self):
        self.decide("backend-only", "python-fastapi")
        self.finish_onboarding()
        return self.root / ".rapid-os" / "scratch" / "hooks.log"

    def test_an_invalid_payload_is_logged_with_its_size_and_start(self):
        log = self.project()
        # What Windows PowerShell 5.1 pipes: the JSON re-encoded as UTF-16 with a BOM.
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash"}).encode("utf-16")
        result = self.rapid("hook", "pre-tool", raw=payload)
        self.assertEqual(result.returncode, 0)
        text = log.read_text("utf-8")
        self.assertIn("stdin is not valid JSON", text)
        self.assertIn(f"{len(payload)} bytes, starting with", text)
        self.assertIn("hex ff fe", text)

    def test_a_utf8_bom_is_accepted(self):
        log = self.project()
        payload = b"\xef\xbb\xbf" + json.dumps(
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(self.root)}
        ).encode("utf-8")
        result = self.rapid("hook", "pre-tool", raw=payload)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(not log.exists() or "not valid JSON" not in log.read_text("utf-8"))

    def test_describe_stdin(self):
        self.assertEqual(describe_stdin(b""), "0 bytes, starting with b'' (hex )")
        self.assertIn("hex 7b 22", describe_stdin(b'{"a":1}'))

    def test_the_manual_test_with_a_file_is_documented(self):
        text = (ROOT / "docs" / "cli.md").read_text("utf-8")
        self.assertIn('cmd /c "rapid hook pre-tool < payload.json"', text)


if __name__ == "__main__":
    unittest.main()

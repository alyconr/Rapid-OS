import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.catalog import load_catalog, load_setup_doc_banks, load_stack_questions
from rapid_os.domain.project import Confidence, Evidence, ProjectFact, ProjectModel
from rapid_os.domain.setup import (
    DocState,
    ServiceChoice,
    SetupActionKind,
    SetupState,
    SetupStateError,
    StackChoice,
)
from rapid_os.orchestration.setup_conductor import next_setup_action
from tests.stack_helpers import complete_stacks

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"
CATALOG = load_catalog(TEMPLATES)
BANKS = load_setup_doc_banks(TEMPLATES)
STACK_QUESTIONS = load_stack_questions(TEMPLATES)
AGENT_IDS = ("antigravity", "claude", "codex", "cursor", "vscode")


def fact(category, value):
    return ProjectFact(category, value, Confidence.HIGH, (Evidence(Path("marker"), "test"),))


def model(*facts):
    return ProjectModel(root=Path("."), facts=tuple(fact(c, v) for c, v in facts))


def next_action(state, project_model=None):
    return next_setup_action(
        state,
        project_model or ProjectModel(root=Path(".")),
        CATALOG,
        BANKS,
        stack_questions=STACK_QUESTIONS,
        agent_ids=AGENT_IDS,
    )


def run_rapid(cwd, *argv):
    return subprocess.run(
        [sys.executable, str(REPO / "rapid.py"), *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "CLAUDECODE": "", "PYTHONPATH": str(REPO)},
    )


def tree_snapshot(root):
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*"))


FULL_DOCS = {doc: DocState("provided", True, "x") for doc in BANKS}
FULL_STATE = SetupState(
    stacks=complete_stacks("generic"),
    topology="fullstack-separated",
    archetype="mvp",
    ai=False,
    agents=("cursor",),
    test_command=(),
    services=(),
    docs=FULL_DOCS,
)


class ConductorTests(unittest.TestCase):
    def test_is_pure_same_input_same_dict(self):
        states = [
            SetupState(),
            SetupState(stacks=complete_stacks("web-modern")),
            SetupState(
                stacks=complete_stacks("web-modern"),
                topology="fullstack-baas",
                archetype="mvp",
                ai=False,
                agents=("cursor",),
                test_command=("npm", "test"),
            ),
        ]
        project = model(("language", "typescript"), ("framework", "nextjs"))
        for state in states:
            with self.subTest(state=state.to_dict()):
                first = next_action(state, project).to_dict()
                second = next_action(state, project).to_dict()
                self.assertEqual(first, second)
                self.assertEqual(json.dumps(first), json.dumps(second))

    def test_full_order_until_done(self):
        state = SetupState()
        project = model(("testing", "pytest"))
        expected = [
            # The first stack can be of any component; the topology follows from it.
            ("choose_stack", {"stacks": {"backend": StackChoice("python-fastapi", "catalog")}}),
            ("choose_topology", {"topology": "fullstack-separated"}),
            # ...and the component the topology still needs is asked next.
            ("choose_stack", {"stacks": complete_stacks("python-fastapi")}),
            ("choose_archetype", {"archetype": "mvp"}),
            ("choose_ai", {"ai": True}),
            ("choose_agents", {"agents": ("cursor",)}),
            ("set_test_command", {"test_command": ("python", "-m", "pytest")}),
        ]
        for kind, change in expected:
            with self.subTest(step=kind):
                self.assertEqual(next_action(state, project).kind.value, kind)
                state = SetupState(**{**state.__dict__, **change})
        docs = {}
        for doc_id in ("brief", "business", "data-model", "architecture", "deployment"):
            if doc_id == "data-model":
                self.assertEqual(
                    next_action(SetupState(**{**state.__dict__, "docs": dict(docs)}), project).kind,
                    SetupActionKind.CHOOSE_SERVICES,
                )
                state = SetupState(**{**state.__dict__, "services": ()})
            action = next_action(SetupState(**{**state.__dict__, "docs": dict(docs)}), project)
            self.assertEqual((action.kind.value, action.payload["doc"]), ("resolve_doc", doc_id))
            docs[doc_id] = DocState("provided", True, "")
        state = SetupState(**{**state.__dict__, "docs": docs})
        self.assertEqual(next_action(state, project).kind, SetupActionKind.FINISH)
        state = SetupState(**{**state.__dict__, "finished": True})
        self.assertEqual(next_action(state, project).kind, SetupActionKind.DONE)

    def test_skipped_and_drafted_docs_count_as_resolved_and_unconfirmed_is_reported(self):
        state = SetupState(
            stacks=complete_stacks("generic"),
            topology="fullstack-separated",
            archetype="mvp",
            ai=False,
            agents=("cursor",),
            test_command=(),
            services=(),
            docs={
                "brief": DocState("drafted", False, "a"),
                "business": DocState("skipped"),
                "data-model": DocState("provided", True, "b"),
                "architecture": DocState("drafted", True, "c"),
                "deployment": DocState("skipped"),
            },
            drafts_reviewed=True,  # the review of the unconfirmed draft is done: finish comes next
        )
        action = next_action(state)
        self.assertEqual(action.kind, SetupActionKind.FINISH)
        self.assertEqual(action.payload["unconfirmed_docs"], ["brief"])

    def test_choose_stack_ranks_by_language_and_framework_with_scanner_recommendation(self):
        action = next_action(
            SetupState(), model(("language", "typescript"), ("framework", "nextjs"))
        ).to_dict()
        self.assertEqual(action["options"][0]["id"], "nextjs")
        self.assertEqual(action["recommended"], "nextjs")
        self.assertTrue(action["questions"])  # asked whatever the scanner recommends: the brief may not answer them
        self.assertIn("factors", action["instruction"].lower() + " factors")
        scores = [o["score"] for o in action["options"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(action["options"][-1]["id"], "generic")

    def test_choose_stack_without_recommendation_carries_stack_questions(self):
        action = next_action(SetupState(), model(("language", "python"))).to_dict()
        self.assertIsNone(action["recommended"])
        self.assertEqual(action["options"][0]["language"], "Python")
        self.assertEqual(
            [q["id"] for q in action["questions"]],
            ["product_type", "team_languages", "load_latency", "infra_budget", "realtime", "compute_ai",
             "maintenance_horizon", "org_constraints"],
        )
        self.assertIn("No afirmes nada que el catálogo no diga", action["instruction"])
        python_fastapi = next(o for o in action["options"] if o["id"] == "python-fastapi")
        self.assertEqual(
            set(python_fastapi["factors"]),
            {"performance", "memory_footprint", "cold_start", "concurrency_model", "typing", "productivity",
             "learning_curve", "maintainability", "ecosystem_maturity", "hiring_pool", "hosting_fit"},
        )

    def test_choose_topology_lists_only_compatible_ones(self):
        cases = {
            "docs-modern": {"doc-site"},
            "python-ai": {"backend-only", "fullstack-separated"},
            "web-modern": {"front-end-only", "fullstack-baas", "fullstack-separated"},
            "generic": {"backend-only", "front-end-only", "fullstack-baas", "fullstack-separated"},
        }
        for stack, topologies in cases.items():
            with self.subTest(stack=stack):
                action = next_action(SetupState(stacks=complete_stacks(stack))).to_dict()
                self.assertEqual(action["kind"], "choose_topology")
                self.assertEqual({o["id"] for o in action["options"]}, topologies)
                self.assertIn(action["recommended"], topologies)

    def test_resolve_doc_is_read_from_the_bank(self):
        state = SetupState(
            stacks=complete_stacks("generic"),
            topology="fullstack-separated",
            archetype="corporate",
            ai=False,
            agents=("claude",),
            test_command=(),
        )
        data = next_action(state).to_dict()
        bank = BANKS["brief"]
        self.assertEqual(data["kind"], "resolve_doc")
        self.assertEqual(data["doc"], "brief")
        self.assertEqual(data["target"], bank.file)
        self.assertEqual(data["choices"], ["provided", "drafted", "skip"])
        self.assertEqual(data["max_chars"], bank.max_chars)
        self.assertEqual([q["id"] for q in data["questions"]], [q.id for q in bank.questions])
        self.assertEqual([s["id"] for s in data["required_sections"]], [s.id for s in bank.required_sections])
        self.assertEqual(
            data["command"],
            ["rapid", "setup", "doc", "brief", "--source", "<provided|drafted>", "--file", "-"],
        )

    def test_every_action_carries_its_command_except_done(self):
        project = model(("testing", "pytest"))
        steps = [
            (SetupState(), ["rapid", "setup", "set", "stack", "<id>"]),
            (
                SetupState(stacks=complete_stacks("generic")),
                ["rapid", "setup", "set", "topology", "<id>"],
            ),
            (
                SetupState(stacks=complete_stacks("generic"), topology="fullstack-separated"),
                ["rapid", "setup", "set", "archetype", "<id>"],
            ),
            (
                SetupState(
                    stacks=complete_stacks("generic"),
                    topology="fullstack-separated",
                    archetype="mvp",
                ),
                ["rapid", "setup", "set", "ai", "<yes|no>"],
            ),
            (
                SetupState(
                    stacks=complete_stacks("generic"),
                    topology="fullstack-separated",
                    archetype="mvp",
                    ai=False,
                ),
                ["rapid", "setup", "set", "agents", "<id,id>"],
            ),
            (
                SetupState(
                    stacks=complete_stacks("generic"),
                    topology="fullstack-separated",
                    archetype="mvp",
                    ai=False,
                    agents=("cursor",),
                ),
                ["rapid", "setup", "set", "test-command", "<cmd>"],
            ),
            (FULL_STATE, ["rapid", "setup", "finish"]),
        ]
        for state, command in steps:
            with self.subTest(command=command):
                self.assertEqual(next_action(state, project).to_dict()["command"], command)
        self.assertNotIn("command", next_action(SetupState(**{**FULL_STATE.__dict__, "finished": True})).to_dict())
        self.assertEqual(
            next_action(SetupState(), project).to_dict()["alt_command"],
            ["rapid", "setup", "stack", "--custom", "--file", "-"],
        )

    def test_stack_options_carry_sidecar_lists(self):
        options = {o["id"]: o for o in next_action(SetupState()).to_dict()["options"]}
        entry = CATALOG.stacks["python-fastapi"]
        self.assertEqual(options["python-fastapi"]["fits"], list(entry.fits))
        self.assertEqual(options["python-fastapi"]["avoid_if"], list(entry.avoid_if))
        self.assertEqual(options["python-fastapi"]["compatible_topologies"], list(entry.compatible_topologies))

    def test_stack_without_sidecar_has_empty_lists(self):
        import dataclasses

        catalog = dataclasses.replace(CATALOG, sidecarless_stacks=("custom-stack",))
        data = next_setup_action(
            SetupState(), ProjectModel(root=Path(".")), catalog, BANKS
        ).to_dict()
        custom = next(o for o in data["options"] if o["id"] == "custom-stack")
        self.assertEqual(
            (custom["source"], custom["fits"], custom["avoid_if"], custom["compatible_topologies"]),
            ("custom", [], [], []),
        )

    def test_test_command_and_agent_come_from_arguments(self):
        state = SetupState(
            stacks=complete_stacks("generic"),
            topology="fullstack-separated",
            archetype="mvp",
            ai=False,
        )
        agents = next_setup_action(
            state, ProjectModel(root=Path(".")), CATALOG, BANKS, agent_ids=AGENT_IDS, detected_agent="claude"
        ).to_dict()
        self.assertEqual((agents["kind"], agents["recommended"]), ("choose_agents", "claude"))
        unknown = next_setup_action(
            state, ProjectModel(root=Path(".")), CATALOG, BANKS, agent_ids=AGENT_IDS, detected_agent="nope"
        ).to_dict()
        self.assertIsNone(unknown["recommended"])
        state = SetupState(**{**state.__dict__, "agents": ("cursor",)})
        proposed = next_setup_action(
            state, ProjectModel(root=Path(".")), CATALOG, BANKS, proposed_test_command=["npm", "test"]
        ).to_dict()
        self.assertEqual((proposed["kind"], proposed["recommended"]), ("set_test_command", ["npm", "test"]))


class StateTests(unittest.TestCase):
    def test_round_trip(self):
        state = SetupState(
            stacks=complete_stacks("custom"),
            topology="doc-site",
            archetype="mvp",
            agents=("cursor", "claude"),
            test_command=("pytest",),
            docs={"brief": DocState("drafted", False, "abc")},
            finished=True,
            ai=False,
            services=(ServiceChoice("database", "postgresql", "now"), ServiceChoice("cache", "redis", "later")),
        )
        self.assertEqual(SetupState.from_dict(state.to_dict()), state)

    def test_invalid_documents_raise_rapid1406(self):
        bad = [
            [],
            {"schema_version": 2},
            {"schema_version": 1, "stack": {"id": "x", "source": "nope"}},
            {"schema_version": 1, "agents": "cursor"},
            {"schema_version": 1, "docs": {"brief": {"status": "weird", "confirmed": False}}},
            {"schema_version": 1, "docs": {"unknown": {"status": "pending", "confirmed": False}}},
            {"schema_version": 1, "finished": "yes"},
        ]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(SetupStateError) as ctx:
                SetupState.from_dict(data)
            self.assertEqual(ctx.exception.code, "RAPID1406")


class ProposeTestCommandTests(unittest.TestCase):
    def js_repo(self, root, *, with_script):
        (root / "tests").mkdir()
        (root / "tests" / "a.test.js").write_text("", encoding="utf-8")
        scripts = {"test": "jest"} if with_script else {}
        (root / "package.json").write_text(json.dumps({"scripts": scripts}), encoding="utf-8")

    def test_order_of_proposals(self):
        from rapid_os.adapters.project_commands import propose_test_command

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(propose_test_command(root, model()))
            self.assertEqual(
                propose_test_command(root, model(("testing", "pytest"), ("testing", "tests-directory"))),
                ["python", "-m", "pytest"],
            )
            self.assertEqual(
                propose_test_command(root, model(("testing", "tests-directory"), ("language", "python"))),
                ["python", "-m", "unittest", "discover"],
            )
            self.assertIsNone(
                propose_test_command(root, model(("testing", "tests-directory"), ("language", "javascript")))
            )
            (root / "package.json").write_text(json.dumps({"scripts": {"test": "x"}}), encoding="utf-8")
            self.assertEqual(
                propose_test_command(root, model(("testing", "pytest"))), ["npm", "test"]
            )
            (root / "package.json").write_text("{", encoding="utf-8")
            self.assertIsNone(propose_test_command(root, model()))

    def test_js_repo_with_test_script_gets_npm_test_in_init_and_setup_next(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.js_repo(project, with_script=True)
            self.assertEqual(run_rapid(project, "init", "--yes").returncode, 0)
            config = json.loads((project / ".rapid-os" / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["test_command"], ["npm", "test"])

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.js_repo(project, with_script=True)
            (project / ".rapid-os").mkdir()
            state = SetupState(
                stacks=complete_stacks("generic"),
                topology="fullstack-separated",
                archetype="mvp",
                ai=False,
                agents=("cursor",),
            )
            (project / ".rapid-os" / "setup.json").write_text(json.dumps(state.to_dict()), encoding="utf-8")
            action = json.loads(run_rapid(project, "setup", "next", "--json").stdout)
            self.assertEqual(action["kind"], "set_test_command")
            self.assertEqual(action["recommended"], ["npm", "test"])

    def test_js_repo_with_tests_dir_but_no_script_gets_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.js_repo(project, with_script=False)
            self.assertEqual(run_rapid(project, "init", "--yes").returncode, 0)
            config = json.loads((project / ".rapid-os" / "config.json").read_text(encoding="utf-8"))
            self.assertNotIn("test_command", config)

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.js_repo(project, with_script=False)
            (project / ".rapid-os").mkdir()
            state = SetupState(
                stacks=complete_stacks("generic"),
                topology="fullstack-separated",
                archetype="mvp",
                ai=False,
                agents=("cursor",),
            )
            (project / ".rapid-os" / "setup.json").write_text(json.dumps(state.to_dict()), encoding="utf-8")
            action = json.loads(run_rapid(project, "setup", "next", "--json").stdout)
            self.assertEqual(action["kind"], "set_test_command")
            self.assertIsNone(action["recommended"])


class SetupCliTests(unittest.TestCase):
    def test_choose_agents_recommends_the_detected_harness(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".rapid-os").mkdir()
            state = SetupState(
                stacks=complete_stacks("generic"), topology="fullstack-separated", archetype="mvp", ai=False
            )
            (project / ".rapid-os" / "setup.json").write_text(json.dumps(state.to_dict()), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(REPO / "rapid.py"), "setup", "next", "--json"],
                cwd=project, capture_output=True, text=True, encoding="utf-8",
                env={**os.environ, "CLAUDECODE": "", "PYTHONPATH": str(REPO), "RAPID_HARNESS": "codex"},
            )
            self.assertEqual(json.loads(result.stdout)["recommended"], "codex")
            clean_env = {k: v for k, v in os.environ.items() if k not in ("RAPID_HARNESS", "CLAUDE_CODE_CHILD_SESSION")}
            clean = subprocess.run(
                [sys.executable, str(REPO / "rapid.py"), "setup", "next", "--json"],
                cwd=project, capture_output=True, text=True, encoding="utf-8",
                env={**clean_env, "CLAUDECODE": "", "PYTHONPATH": str(REPO)},
            )
            self.assertIsNone(json.loads(clean.stdout)["recommended"])

    def test_empty_folder_returns_choose_stack_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = tree_snapshot(tmp)
            result = run_rapid(tmp, "setup", "next", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["kind"], "choose_stack")
            show = run_rapid(tmp, "setup", "show", "--json")
            self.assertEqual(json.loads(show.stdout)["origin"], "empty")
            self.assertEqual(tree_snapshot(tmp), before)
            self.assertFalse((Path(tmp) / ".rapid-os").exists())

    def test_project_initialized_before_setup_derives_state_and_asks_first_doc(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "pyproject.toml").write_text("", encoding="utf-8")
            (project / "tests").mkdir()
            (project / "tests" / "test_a.py").write_text("", encoding="utf-8")
            self.assertEqual(run_rapid(project, "init", "--yes").returncode, 0)
            # A project initialized before the setup flow has no setup.json.
            (project / ".rapid-os" / "setup.json").unlink()
            before = tree_snapshot(project)

            result = run_rapid(project, "setup", "next", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            action = json.loads(result.stdout)
            self.assertEqual((action["kind"], action["doc"]), ("resolve_doc", "brief"))

            show = json.loads(run_rapid(project, "setup", "show", "--json").stdout)
            self.assertEqual(show["origin"], "derived")
            state = show["state"]
            self.assertEqual(
                state["stacks"], {c: {"id": "generic", "source": "generic"} for c in ("frontend", "backend", "baas", "docs")}
            )
            self.assertEqual(state["topology"], "fullstack-separated")
            self.assertEqual(state["archetype"], "mvp")
            self.assertEqual(state["agents"], ["cursor"])
            self.assertEqual(state["test_command"], ["python", "-m", "unittest", "discover"])
            self.assertEqual({d["status"] for d in state["docs"].values()}, {"pending"})
            self.assertFalse(state["finished"])

            self.assertEqual(tree_snapshot(project), before)
            self.assertFalse((project / ".rapid-os" / "setup.json").exists())

    def test_derived_doc_needs_rapid_doc_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "pyproject.toml").write_text("", encoding="utf-8")
            (project / "tests").mkdir()
            (project / "tests" / "test_a.py").write_text("", encoding="utf-8")
            self.assertEqual(run_rapid(project, "init", "--yes").returncode, 0)
            # A project initialized before the setup flow has no setup.json.
            (project / ".rapid-os" / "setup.json").unlink()
            docs = project / "docs"
            docs.mkdir()
            (docs / "PRODUCT_BRIEF.md").write_text("# hand written, no frontmatter\n", encoding="utf-8")
            (docs / "BUSINESS_RULES.md").write_text(
                "---\nrapid-doc: business\nsource: drafted\nstatus: draft\nsha256: abc\n---\n# b\n",
                encoding="utf-8",
            )
            state = json.loads(run_rapid(project, "setup", "show", "--json").stdout)["state"]
            self.assertEqual(state["docs"]["brief"]["status"], "pending")
            self.assertEqual(
                state["docs"]["business"],
                {"status": "drafted", "confirmed": False, "sha256": "abc"},
            )
            action = json.loads(run_rapid(project, "setup", "next", "--json").stdout)
            self.assertEqual(action["doc"], "brief")

    def test_setup_json_is_the_source_of_truth_and_is_never_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".rapid-os").mkdir()
            state = SetupState(stacks=complete_stacks("web-modern")).to_dict()
            target = project / ".rapid-os" / "setup.json"
            target.write_text(json.dumps(state), encoding="utf-8")
            before = target.read_bytes()
            action = json.loads(run_rapid(project, "setup", "next", "--json").stdout)
            self.assertEqual(action["kind"], "choose_topology")
            self.assertEqual(json.loads(run_rapid(project, "setup", "show", "--json").stdout)["origin"], "setup.json")
            self.assertEqual(target.read_bytes(), before)

    def test_corrupt_setup_json_is_rapid1406_without_traceback(self):
        for content in ("{", '{"schema_version": 9}'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp)
                (project / ".rapid-os").mkdir()
                (project / ".rapid-os" / "setup.json").write_text(content, encoding="utf-8")
                for command in ("next", "show"):
                    result = run_rapid(project, "setup", command, "--json")
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("RAPID1406", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_setup_without_subcommand_is_rapid1413(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_rapid(tmp, "setup")
            self.assertEqual(result.returncode, 1)
            self.assertIn("RAPID1413", result.stderr)
            self.assertNotIn("RAPID1401", result.stderr)

    def test_human_output_is_three_to_six_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            for command in ("next", "show"):
                lines = run_rapid(tmp, "setup", command).stdout.strip().splitlines()
                self.assertTrue(3 <= len(lines) <= 6, lines)


if __name__ == "__main__":
    unittest.main()

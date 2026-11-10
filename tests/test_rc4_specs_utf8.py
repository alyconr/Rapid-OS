"""rc.4 fixes from the rc.3 e2e on Windows with Codex: H-55 (a spec whose accents became '?' is refused),
H-54 (task progress in `rapid status`), H-56 (handing a story over for approval) and H-57 (`rapid check`
reads the command's output as UTF-8)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from rapid_os.domain.project_docs import find_lost_characters
from rapid_os.domain.specs import find_spec_lost_characters

ROOT = Path(__file__).resolve().parents[1]
SHORTCUTS = ROOT / "templates" / "shortcuts"
WORK_SHORTCUTS = ("rapid-feature", "rapid-bugfix", "rapid-refactor", "rapid-hardening", "rapid-research")
TEST_COMMAND = f'"{sys.executable}" -m unittest discover -s tests -t .'
SMOKE_TEST = "import unittest\n\nclass Smoke(unittest.TestCase):\n    def test_smoke(self):\n        self.assertTrue(True)\n"


def rapid(cwd, *argv, stdin=None, env_extra=None):
    env = {
        **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
        "PYTHONPATH": str(ROOT),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        **(env_extra or {}),
    }
    env = {name: value for name, value in env.items() if value is not None}
    return subprocess.run(
        [sys.executable, "-m", "rapid_os.cli.main", *argv],
        cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8", env=env,
    )


def git(cwd, *argv):
    subprocess.run(["git", *argv], cwd=cwd, check=True, capture_output=True)


def spec(**overrides):
    payload = {
        "title": "Reserva pública", "mode": "feature", "business_objective": "Reservar un taller",
        "problem_statement": "No se puede reservar", "scope": ["reservas"],
        "acceptance_criteria": ["La reserva queda guardada"], "tasks": ["T001: Añadir el módulo de reservas"],
    }
    payload.update(overrides)
    return payload


class Project(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir()
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "T")
        init = rapid(self.root, "init", "--yes", "--skip-docs", "--test-command", TEST_COMMAND)
        self.assertEqual(init.returncode, 0, init.stderr)
        (self.root / "app.py").write_text("x = 1\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests" / "test_smoke.py").write_text(SMOKE_TEST, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")

    def specs_dir(self):
        return self.root / ".rapid-os" / "specs"

    def stored_specs(self):
        directory = self.specs_dir()
        return sorted(p.name for p in directory.iterdir() if p.is_dir()) if directory.is_dir() else []

    def runs(self):
        directory = self.root / ".rapid-os" / "runs"
        return sorted(p.name for p in directory.iterdir() if p.is_dir()) if directory.is_dir() else []


class LostCharacterDetectionTests(unittest.TestCase):
    def test_the_word_that_lost_characters_is_named(self):
        self.assertEqual(find_lost_characters("Tarea de creaci?n at?mica"), "creaci?n")
        self.assertIsNone(find_lost_characters("¿Qué pasa? Usa `a?b` en el patrón"))

    def test_every_text_field_of_a_spec_is_checked(self):
        self.assertEqual(
            find_spec_lost_characters(spec(tasks=["T001: ok", "T002: creaci?n at?mica"])),
            ("tasks[1]", "creaci?n"),
        )
        self.assertEqual(find_spec_lost_characters(spec(title="Reserva p?blica"))[0], "title")
        self.assertEqual(
            find_spec_lost_characters(spec(findings=[{"title": "Inyecci?n", "severity": "high"}]))[0],
            "findings[0].title",
        )
        self.assertIsNone(find_spec_lost_characters(spec(business_objective="¿Qué pasa? Usa `a?b`")))


class StartRefusesLostCharactersTests(Project):
    def test_start_with_a_task_that_lost_accents_is_refused_and_writes_nothing(self):
        bad = spec(tasks=["T001: creaci?n at?mica del m?dulo"])
        result = rapid(self.root, "start", "feature", "--spec-file", "-", stdin=json.dumps(bad, ensure_ascii=False))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RAPID1415", result.stderr)
        self.assertIn("creaci?n", result.stderr)
        self.assertIn("Set-Content -Encoding utf8", result.stderr)
        self.assertIn("--spec-file", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.stored_specs(), [])
        self.assertEqual(self.runs(), [])
        self.assertFalse((self.root / ".rapid-os" / "session.json").exists())

    def test_question_marks_that_belong_to_the_text_are_accepted(self):
        good = spec(
            problem_statement="¿Qué pasa si la reserva ya existe?",
            tasks=["T001: Validar el patrón `a?b` del módulo"],
        )
        result = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(good, ensure_ascii=False))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.runs()), 1)

    def test_a_utf8_file_with_bom_keeps_the_title_and_the_slug(self):
        # What `Set-Content -Encoding utf8` writes in Windows PowerShell 5.1: UTF-8 with a BOM.
        path = Path(self._tmp.name) / "rapid-spec.json"
        path.write_bytes(b"\xef\xbb\xbf" + json.dumps(spec(), ensure_ascii=False).encode("utf-8"))
        result = rapid(self.root, "start", "feature", "--spec-file", str(path), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stored_specs(), ["reserva-publica"])
        revision = json.loads((self.specs_dir() / "reserva-publica" / "revisions" / "0001" / "revision.json").read_text("utf-8"))
        self.assertEqual(revision["title"], "Reserva pública")
        self.assertEqual(revision["implementation_tasks"], ["T001: Añadir el módulo de reservas"])


class SpecCommandsRefuseLostCharactersTests(Project):
    def test_spec_create_is_refused_without_writing(self):
        result = rapid(
            self.root, "spec", "create", "--title", "Reserva", "--objective", "Reservar",
            "--task", "T001: creaci?n at?mica",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RAPID1415", result.stderr)
        self.assertEqual(self.stored_specs(), [])

    def test_spec_revise_is_refused_and_the_current_revision_stays(self):
        created = rapid(self.root, "spec", "create", "--title", "Reserva", "--objective", "Reservar", "--task", "T001: Crear")
        self.assertEqual(created.returncode, 0, created.stderr)
        result = rapid(self.root, "spec", "revise", "reserva", "--task", "T001: creaci?n at?mica")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RAPID1415", result.stderr)
        record = json.loads((self.specs_dir() / "reserva" / "spec.json").read_text("utf-8"))
        self.assertEqual(record["current_revision"], 1)
        self.assertEqual(
            sorted(p.name for p in (self.specs_dir() / "reserva" / "revisions").iterdir()), ["0001"]
        )

    def test_spec_create_with_intact_text_is_accepted(self):
        result = rapid(
            self.root, "spec", "create", "--title", "Reserva pública", "--objective", "¿Qué pasa?",
            "--task", "T001: Añadir `a?b`",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.stored_specs(), ["reserva-publica"])


class WorkShortcutsSendSpecsByFileOnPowerShellTests(unittest.TestCase):
    def test_every_work_shortcut_has_the_powershell_rule(self):
        for name in WORK_SHORTCUTS:
            text = (SHORTCUTS / f"{name}.md").read_text("utf-8")
            with self.subTest(shortcut=name):
                self.assertIn("En Windows PowerShell no pases la spec por tubería", text)
                self.assertIn("Set-Content -Encoding utf8 $env:TEMP\\rapid-spec.json", text)
                self.assertIn("RAPID1415", text)
                self.assertIn("stdin (heredoc) sigue bien", text)


# --- H-54: task progress in `rapid status` -------------------------------------------------------------------

FOUR_TASKS = spec(
    title="Reservas", tasks=[
        "T001: Crear el modelo de reserva",
        "T002: Documentar la API",
        "T003: Validar que la fecha de la reserva no esté en el pasado y que el taller tenga plazas libres para esa fecha",
        "T004: Publicar el endpoint",
    ],
)
# What 3.2.0rc3 stored for this revision (computed with the code of main): a revision written before the
# status line keeps these digests.
LEGACY_REVISION = dict(
    spec_id="reserva-publica", revision=1, title="Reserva pública", mode="feature",
    business_objective="Reservar un taller", problem_statement="No se puede reservar",
    scope=("reservas",), acceptance_criteria=("La reserva queda guardada",),
    implementation_tasks=("T001: Añadir el módulo", "T002: Validar fechas"),
)
LEGACY_CONTENT_DIGEST = "cedb94c173f1fd8e6a93ea5570f9a6cefffd00c240b338bcf98c023dc7744ba3"
LEGACY_TASKS_DIGEST = "aa9267a8ac65df00ae6ec48cb083ef2aa725f86f2221f83e135f729861f85613"


class StatusListsTasksTests(Project):
    def setUp(self):
        super().setUp()
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(FOUR_TASKS, ensure_ascii=False))
        self.assertEqual(started.returncode, 0, started.stderr)
        self.run_id = self.runs()[0]
        for argv in (
            ("task", "start", "T001"), ("task", "done", "T001"),
            ("task", "skip", "T002", "--reason", "fuera de alcance"),
            ("task", "start", "T003"),
        ):
            result = rapid(self.root, *argv)
            self.assertEqual(result.returncode, 0, f"{argv}: {result.stderr}{result.stdout}")

    def test_text_lists_each_task_with_its_state_and_evidence(self):
        result = rapid(self.root, "status")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertIn("Tasks:         2/4 terminal", out)
        done_line = next(line for line in out.splitlines() if line.strip().startswith("T001 [done]"))
        self.assertIn("Crear el modelo de reserva", done_line)
        self.assertIn("(evidencia: E", done_line)
        self.assertNotIn("T001: Crear", done_line)  # the id is not repeated in the title
        self.assertIn("T002 [skipped] Documentar la API", out)
        long_line = next(line for line in out.splitlines() if line.strip().startswith("T003 [in_progress]"))
        self.assertTrue(long_line.rstrip().endswith("…"), long_line)
        self.assertIn("T004 [pending] Publicar el endpoint", out)
        self.assertIn("Gates:", out)
        self.assertRegex(out, r"gate\.tests \[(pending|pass|fail|unverified)\]")

    def test_json_carries_tasks_with_status_title_and_evidence_ids(self):
        result = rapid(self.root, "status", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        run = json.loads(result.stdout)["run"]
        by_id = {t["id"]: t for t in run["tasks"]}
        self.assertEqual(
            {k: v["status"] for k, v in by_id.items()},
            {"T001": "done", "T002": "skipped", "T003": "in_progress", "T004": "pending"},
        )
        self.assertTrue(by_id["T001"]["evidence_ids"])
        self.assertEqual(by_id["T004"]["evidence_ids"], [])
        self.assertEqual(by_id["T004"]["title"], "Publicar el endpoint")
        self.assertEqual(by_id["T004"]["description"], "T004: Publicar el endpoint")
        for gate in run["gates"]:
            self.assertIn("status", gate)
            self.assertIn("evidence_ids", gate)
            self.assertIn("disposition", gate)

    def test_a_pending_gate_shows_the_result_of_its_last_evidence(self):
        for argv in (("task", "done", "T003"), ("task", "start", "T004"), ("task", "done", "T004")):
            result = rapid(self.root, *argv)
            self.assertEqual(result.returncode, 0, f"{argv}: {result.stderr}{result.stdout}")
        checked = rapid(self.root, "check", "--gate", "gate.tests", "--json", "--", sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        evidence_id = json.loads(checked.stdout)["evidence_id"]

        gates = {g["id"]: g for g in json.loads(rapid(self.root, "status", "--json").stdout)["run"]["gates"]}
        self.assertEqual(gates["gate.tests"]["status"], "pending")
        self.assertEqual(gates["gate.tests"]["last_evidence_result"], "PASS")
        self.assertEqual(gates["gate.tests"]["last_evidence_id"], evidence_id)
        self.assertIsNone(gates["gate.final-verification"]["last_evidence_result"])
        self.assertNotIn("last_evidence_result", gates["gate.baseline"])  # evaluated: its status says it

        out = rapid(self.root, "status").stdout
        self.assertIn(f"gate.tests [pending · última evidencia: PASS]  (evidencia: {evidence_id})", out)
        self.assertIn("gate.final-verification [pending]\n", out)

    def test_without_an_active_run_the_last_run_is_listed(self):
        (self.root / ".rapid-os" / "session.json").unlink()
        text = rapid(self.root, "status")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertIn(f"Last Run:      {self.run_id}", text.stdout)
        self.assertIn("T001 [done]", text.stdout)
        payload = json.loads(rapid(self.root, "status", "--json").stdout)
        self.assertIsNone(payload["run"])
        self.assertEqual(payload["last_run"]["run_id"], self.run_id)
        self.assertEqual(len(payload["last_run"]["tasks"]), 4)


class TasksMarkdownStatusLineTests(Project):
    def test_a_new_revision_says_where_task_state_lives(self):
        created = rapid(self.root, "spec", "create", "--title", "Reserva", "--objective", "Reservar", "--task", "T001: Crear")
        self.assertEqual(created.returncode, 0, created.stderr)
        tasks_md = (self.specs_dir() / "reserva" / "revisions" / "0001" / "tasks.md").read_text("utf-8")
        self.assertEqual(
            tasks_md.splitlines()[:3], ["# TASKS: Reserva", "", "El estado de cada tarea vive en el run: rapid status"]
        )
        self.assertIn("- [ ] T001: Crear", tasks_md)
        revised = rapid(self.root, "spec", "revise", "reserva", "--task", "T001: Crear", "--task", "T002: Probar")
        self.assertEqual(revised.returncode, 0, revised.stderr)
        self.assertIn(
            "El estado de cada tarea vive en el run: rapid status",
            (self.specs_dir() / "reserva" / "revisions" / "0002" / "tasks.md").read_text("utf-8"),
        )

    def test_a_revision_stored_before_the_line_keeps_its_digests_and_still_runs(self):
        from dataclasses import replace

        from rapid_os.adapters.spec_registry import SpecRegistry
        from rapid_os.domain.specs import SpecRecord, SpecRevision

        registry = SpecRegistry(self.root, self.root / ".rapid-os")
        legacy = replace(SpecRevision(**LEGACY_REVISION), tasks_status_note=False)
        self.assertEqual(legacy.content_digest, LEGACY_CONTENT_DIGEST)
        spec_dir = self.specs_dir() / "reserva-publica"
        registry._write_immutable_revision_and_commit_record(
            spec_dir, legacy, SpecRecord(schema_version=1, id="reserva-publica", status="draft", current_revision=1)
        )
        stored = json.loads((spec_dir / "revisions" / "0001" / "revision.json").read_text("utf-8"))
        self.assertEqual(stored["content_digest"], LEGACY_CONTENT_DIGEST)
        self.assertEqual(stored["artifact_digests"]["tasks.md"], LEGACY_TASKS_DIGEST)
        tasks_md = (spec_dir / "revisions" / "0001" / "tasks.md").read_text("utf-8")
        self.assertNotIn("rapid status", tasks_md)

        read = SpecRegistry(self.root, self.root / ".rapid-os").get_revision("reserva-publica", 1)
        self.assertFalse(read.tasks_status_note)
        self.assertEqual(read.content_digest, LEGACY_CONTENT_DIGEST)
        self.assertEqual(rapid(self.root, "validate").returncode, 0)
        shown = rapid(self.root, "spec", "show", "reserva-publica", "--json")
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertEqual(json.loads(shown.stdout)["revision"]["content_digest"], LEGACY_CONTENT_DIGEST)
        # The run binds to the stored digest, and its tasks come from the revision, not from tasks.md.
        self.assertEqual(rapid(self.root, "spec", "status", "reserva-publica", "ready").returncode, 0)
        started = rapid(self.root, "start", "feature", "--spec", "reserva-publica", "--json")
        self.assertEqual(started.returncode, 0, started.stderr)
        contract = json.loads(next((self.root / ".rapid-os" / "runs").glob("*/contract.json")).read_text("utf-8"))
        self.assertEqual(contract["spec_content_digest"], LEGACY_CONTENT_DIGEST)
        self.assertEqual([t["id"] for t in contract["tasks"]], ["T001", "T002"])
        # And the same spec file again is still recognised as the stored one (no RAPID1322).
        again = SpecRegistry(self.root, self.root / ".rapid-os").compare_existing(
            **{k: v for k, v in LEGACY_REVISION.items() if k not in ("spec_id", "revision")}
        )
        self.assertTrue(again[1])



# --- H-56: handing a story over for approval ---------------------------------------------------------------


def drive_to_approval(case, root):
    """Follow `rapid next` like an agent until a human gate is waiting; returns the action."""
    for _ in range(25):
        action = json.loads(rapid(root, "next", "--json").stdout)["action"]
        if action["kind"] == "await_human_approval":
            return action
        for key in ("command", "after"):
            if action.get(key):
                result = rapid(root, *action[key][1:])
                case.assertEqual(result.returncode, 0, result.stderr + result.stdout)
    case.fail("the run never reached a human gate")


class NextHandsOverForApprovalTests(Project):
    CRITERIA = ["La reserva queda guardada", "Una fecha pasada se rechaza con un error claro"]

    def setUp(self):
        super().setUp()
        story = spec(title="Reservas", acceptance_criteria=self.CRITERIA, tasks=["T001: Guardar la reserva"])
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(story, ensure_ascii=False))
        self.assertEqual(started.returncode, 0, started.stderr)
        self.action = drive_to_approval(self, self.root)
        self.gate = self.action["gate_ids"][0]

    def test_json_brings_the_acceptance_criteria_and_both_commands(self):
        self.assertEqual(self.action["acceptance"], self.CRITERIA)
        commands = {item["id"]: item for item in self.action["commands"]}
        self.assertEqual(set(commands), {"approve", "reject"})
        self.assertEqual(commands["approve"]["command"], ["rapid", "approve", self.gate])
        self.assertEqual(commands["approve"]["gate_id"], self.gate)
        self.assertIn("rapid finish", commands["approve"]["consequence"])
        self.assertEqual(
            commands["reject"]["command"], ["rapid", "approve", self.gate, "--reject", "--reason", "<motivo>"]
        )
        self.assertEqual(commands["reject"]["display"], f'rapid approve {self.gate} --reject --reason "<motivo>"')
        self.assertIn("FAIL", commands["reject"]["consequence"])
        self.assertIn("rapid abort", commands["reject"]["consequence"])
        self.assertIn("run nuevo", commands["reject"]["consequence"])

    def test_text_lists_the_criteria_and_both_commands_with_their_consequence(self):
        result = rapid(self.root, "next")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        self.assertIn(f"Next: await_human_approval -> rapid approve {self.gate}", out)
        self.assertIn("Criterios de aceptación", out)
        for criterion in self.CRITERIA:
            self.assertIn(f"  - {criterion}", out)
        self.assertIn(f"Aprobar: rapid approve {self.gate}\n", out)
        self.assertIn(f'Rechazar: rapid approve {self.gate} --reject --reason "<motivo>"', out)
        self.assertIn("rapid finish", out)
        self.assertIn("rapid abort", out)


class WorkShortcutsHandOverOnlyWhatIsReadyTests(unittest.TestCase):
    def test_every_work_shortcut_reviews_criteria_before_handing_over(self):
        for name in WORK_SHORTCUTS + ("rapid-next",):
            text = (SHORTCUTS / f"{name}.md").read_text("utf-8")
            with self.subTest(shortcut=name):
                self.assertIn("revisa uno por uno los criterios de `action.acceptance` con su evidencia", text)
                self.assertIn("rapid check -- <comando>", text)
                # The person starts the services (as /rapid-init says); the agent asks and waits.
                self.assertIn("pídele a la persona `docker compose up -d` y espera", text)
                self.assertNotIn("levanta los servicios", text)
                self.assertIn("repetirá `gate.tests` y `gate.architecture` porque el árbol cambió", text)
                self.assertIn("algo depende de la persona", text)
                self.assertIn("«cumple»", text)
                self.assertIn('--reject --reason "<motivo>"', text)
                self.assertIn("Nunca entregues aconsejando no aprobar", text)
                self.assertIn("solo cuando action.kind sea await_human_approval", text)


# --- H-59: approving without typing phrases ------------------------------------------------------------------


class ApproveAsksYesNoTests(Project):
    CRITERIA = ["La reserva queda guardada"]

    def setUp(self):
        super().setUp()
        story = spec(title="Reservas", acceptance_criteria=self.CRITERIA, tasks=["T001: Guardar la reserva"])
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(story, ensure_ascii=False))
        self.assertEqual(started.returncode, 0, started.stderr)
        self.gate = drive_to_approval(self, self.root)["gate_ids"][0]

    def approve(self, *answers, gate_id=None, is_tty=True, **flags):
        from rapid_os.core.ancestry import AncestryResult
        from rapid_os.orchestration.lifecycle import execute_approve

        prompts: list[str] = []
        queue = list(answers)

        def answer(prompt):
            prompts.append(prompt)
            if not queue:
                raise EOFError
            return queue.pop(0)

        code, message = execute_approve(
            self.root, self.root / ".rapid-os", gate_id, reviewer="Ada", is_tty=is_tty, input_func=answer,
            environ={}, ancestry=AncestryResult(()), **flags,
        )
        return code, message, prompts

    def reviews(self):
        from rapid_os.adapters.evidence_registry import EvidenceRegistry

        run_id = self.runs()[0]
        return [e for e in EvidenceRegistry(self.root, self.root / ".rapid-os").list(run_id) if e.kind.value == "review"]

    def gate_disposition(self):
        gates = json.loads(rapid(self.root, "status", "--json").stdout)["run"]["gates"]
        return next(g["disposition"] for g in gates if g["id"] == self.gate)

    def test_the_only_pending_gate_is_approved_with_s_after_the_summary(self):
        code, message, prompts = self.approve("s")
        self.assertEqual(code, 0, message)
        self.assertEqual(len(prompts), 1)
        summary = prompts[0]
        self.assertIn(f"Run:   {self.runs()[0]}", summary)
        self.assertIn(f"Gate:  {self.gate}", summary)
        self.assertIn("  - La reserva queda guardada", summary)
        self.assertIn("Tareas: 1/1 terminadas", summary)
        self.assertRegex(summary, r"gate\.tests \[(pass|pending · última evidencia: PASS)\]  \(evidencia: E\d+")
        self.assertTrue(summary.endswith(f"¿Apruebas {self.gate}? [s/N] "), summary)
        self.assertNotIn("Escribe la frase", summary)
        self.assertEqual([r.payload["outcome"] for r in self.reviews()], ["approved"])
        self.assertEqual(self.reviews()[0].payload["reviewer"], "Ada")
        self.assertEqual(self.gate_disposition(), "acknowledged")

    def test_no_then_a_reason_rejects_with_that_reason(self):
        code, message, prompts = self.approve("n", "falta validar las fechas", gate_id=self.gate)
        self.assertEqual(code, 0, message)
        self.assertEqual(prompts[1], "Para rechazarlo escribe el motivo (Enter para salir sin cambios): ")
        review = self.reviews()[0]
        self.assertEqual(review.payload["outcome"], "changes_requested")
        self.assertEqual(review.payload["reason"], "falta validar las fechas")
        self.assertEqual(json.loads(rapid(self.root, "next", "--json").stdout)["action"]["command"], ["rapid", "abort"])

    def test_enter_twice_leaves_everything_unchanged(self):
        code, message, _ = self.approve("", "")
        self.assertEqual(code, 1)
        self.assertIn("Sin cambios", message)
        self.assertEqual(self.reviews(), [])
        self.assertEqual(self.gate_disposition(), "pending")

    def test_explicit_reject_and_waive_only_confirm(self):
        code, message, prompts = self.approve("N", gate_id=self.gate, reject=True, reason="no cumple")
        self.assertEqual(code, 1)
        self.assertIn("Sin cambios", message)
        self.assertEqual(len(prompts), 1)  # no second question: the reason is already given
        self.assertIn(f"¿Rechazas {self.gate} con el motivo «no cumple»? [s/N]", prompts[0])
        self.assertEqual(self.reviews(), [])
        code, message, _ = self.approve("sí", gate_id=self.gate, reject=True, reason="no cumple")
        self.assertEqual(code, 0, message)
        self.assertEqual(self.reviews()[0].payload["outcome"], "changes_requested")

    def test_without_a_terminal_it_still_only_lists(self):
        code, message, prompts = self.approve(is_tty=False)
        self.assertEqual(code, 0)
        self.assertIn("Pending human gates", message)
        self.assertIn(self.gate, message)
        self.assertEqual(prompts, [])
        self.assertEqual(self.reviews(), [])
        code, message, _ = self.approve("s", gate_id=self.gate, is_tty=False)
        self.assertEqual(code, 1)
        self.assertIn("RAPID1310", message)

    def test_yes_answers(self):
        from rapid_os.orchestration.lifecycle import is_yes

        for answer in ("s", "S", "si", "sí", "Sí", "y", "YES", " yes ", "“s”"):
            self.assertTrue(is_yes(answer), answer)
        for answer in ("", "n", "no", "N", "aprobar gate.final-verification", None):
            self.assertFalse(is_yes(answer), answer)


class ApprovalTextSaysAnswerSTests(unittest.TestCase):
    def test_shortcuts_say_run_rapid_approve_and_answer_s(self):
        for name in WORK_SHORTCUTS + ("rapid-next",):
            text = (SHORTCUTS / f"{name}.md").read_text("utf-8")
            with self.subTest(shortcut=name):
                self.assertIn("ejecute `rapid approve` en otra terminal, fuera del agente, y responda `s`", text)
        self.assertIn("responda `s`", (SHORTCUTS / "rapid-approve.md").read_text("utf-8"))


# --- H-57: `rapid check` reads the command's output as UTF-8 -----------------------------------------------

# Vitest prints ✓ (E2 9C 93), ⎯ (E2 8E AF) and ❯ (E2 9D AF); 0x9d is not a cp1252 byte, so decoding with the
# Windows code page killed the reader thread ('charmap' codec can't decode byte 0x9d).
VITEST_LIKE = (
    "import sys; sys.stdout.buffer.write("
    "' \\u2713 src/reserva.test.ts (3 tests) 4ms\\n\\u23af\\u23af\\u23af\\n \\u276f done\\n"
    "      Tests  3 passed (3)\\n'.encode('utf-8')); sys.stdout.flush()"
)


class CheckReadsUtf8OutputTests(Project):
    def test_utf8_output_is_logged_and_its_summary_counted(self):
        started = rapid(self.root, "start", "feature", "--spec-file", "-", "--json", stdin=json.dumps(spec(), ensure_ascii=False))
        self.assertEqual(started.returncode, 0, started.stderr)
        # Without PYTHONUTF8 or PYTHONIOENCODING: the code page of the machine decides, as on a real Windows.
        result = rapid(
            self.root, "check", "--json", "--gate", "gate.tests", "--", sys.executable, "-c", VITEST_LIKE,
            env_extra={"PYTHONUTF8": None, "PYTHONIOENCODING": None},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("UnicodeDecodeError", result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(json.dumps(payload, ensure_ascii=False).count('"passed": 3'), 1, payload)
        log = sorted((self.root / ".rapid-os" / "scratch" / "checks").rglob("*.log"))[-1].read_text(encoding="utf-8")
        for mark in ("\u2713", "\u23af", "\u276f", "Tests  3 passed (3)"):
            self.assertIn(mark, log)


if __name__ == "__main__":
    unittest.main()

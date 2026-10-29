"""H-29 (stdin is UTF-8, never the console code page), H-32 (executables resolved with the PATH) and H-34 (a
test command that does not exist is noticed)."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rapid_os.core import text as core_text
from rapid_os.core.text import (
    InputEncodingError,
    decode_utf8_input,
    display_command,
    find_mojibake,
    read_stdin_text,
    read_text_best_effort,
)
from rapid_os.orchestration import check as check_module
from rapid_os.orchestration.setup_conductor import COMBINED_TEST_RUNNER, combine_test_commands

ROOT = Path(__file__).resolve().parents[1]
SPEC = {
    "title": "Notificación de dueño", "mode": "feature", "business_objective": "Avisar al dueño",
    "problem_statement": "No hay notificación", "scope": ["notificación"],
    "acceptance_criteria": ["Las fechas son válidas", "El módulo avisa al dueño"], "tasks": ["T001: Crear módulo"],
}
BRIEF = "## Problema\nAgendar talleres del dueño.\n\n## Usuarios\nOrganizadores.\n\n## Historias\n- [ ] H001: Crear taller\n"


class Project(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.root = base / "project"
        self.root.mkdir()
        gitconfig = base / "gitconfig"
        gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.com\n[init]\n\tdefaultBranch = main\n", encoding="utf-8")
        # A console that reads stdin as cp1252 (Windows): what the agent's text used to go through.
        self.env = {
            **{k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION")},
            "GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_CONFIG_NOSYSTEM": "1", "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "cp1252:replace", "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.env.pop("PYTHONUTF8", None)

    def rapid(self, *argv, raw=None):
        return subprocess.run(
            [sys.executable, "-m", "rapid_os.cli.main", *argv], cwd=self.root, capture_output=True, env=self.env, input=raw
        )

    def ok(self, *argv, raw=None):
        result = self.rapid(*argv, raw=raw)
        self.assertEqual(result.returncode, 0, f"{argv}: {result.stdout.decode('utf-8', 'replace')}{result.stderr.decode('utf-8', 'replace')}")
        return result.stdout.decode("utf-8", "replace")

    def onboard(self, test_command="none", stack="python-fastapi", topology="backend-only"):
        for step in (("stack", stack), ("topology", topology), ("archetype", "mvp"), ("ai", "no"),
                     ("agents", "claude"), ("test-command", test_command), ("services", "none")):
            self.ok("setup", "set", *step)
        for doc in ("brief", "business", "data-model", "architecture", "deployment"):
            self.ok("setup", "doc", doc, "--skip")
        self.ok("setup", "finish")

    def stored_spec_titles(self):
        from rapid_os.adapters.spec_registry import SpecRegistry

        registry = SpecRegistry(self.root, self.root / ".rapid-os")
        return {r.id: registry.get_revision(r.id, revision=r.current_revision) for r in registry.list_specs()}


class DecodingTests(unittest.TestCase):
    def test_stdin_is_read_as_utf8_whatever_the_console_encoding(self):
        raw = "notificación de dueño".encode("utf-8")
        console = io.TextIOWrapper(io.BytesIO(raw), encoding="cp1252")
        self.assertEqual(console.read(), "notificaciÃ³n de dueÃ±o")  # what sys.stdin.read() used to give
        console = io.TextIOWrapper(io.BytesIO(raw), encoding="cp1252")
        with mock.patch.object(sys, "stdin", console):
            self.assertEqual(read_stdin_text(), "notificación de dueño")

    def test_a_bom_is_dropped(self):
        self.assertEqual(decode_utf8_input(b"\xef\xbb\xbfhola", "stdin"), "hola")

    def test_text_that_is_not_utf8_is_refused_with_a_code_and_never_altered(self):
        with self.assertRaises(InputEncodingError) as caught:
            decode_utf8_input("notificación".encode("cp1252"), "stdin")
        self.assertTrue(str(caught.exception).startswith("RAPID1424 "))
        self.assertIn("UTF-8", str(caught.exception))

    def test_the_fallback_of_read_text_best_effort_names_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.txt"
            path.write_bytes("dueño".encode("cp1252"))
            self.assertEqual(read_text_best_effort(path), "dueño")  # best effort for user files still works
        self.assertNotIn("read_text()", Path(core_text.__file__).read_text(encoding="utf-8").split("def read_text_best_effort")[1])


class StdinThroughTheCliTests(Project):
    def test_a_spec_from_stdin_keeps_its_characters_and_the_id_is_transliterated(self):
        self.onboard()
        self.ok("start", "feature", "--spec-file", "-", "--json", raw=json.dumps(SPEC, ensure_ascii=False).encode("utf-8"))
        ((spec_id, revision),) = self.stored_spec_titles().items()
        self.assertEqual(spec_id, "notificacion-de-dueno")
        self.assertEqual(revision.title, "Notificación de dueño")
        self.assertIn("Las fechas son válidas", revision.acceptance_criteria)
        self.assertIn("El módulo avisa al dueño", revision.acceptance_criteria)
        self.assertIsNone(find_mojibake(json.dumps(revision.to_dict(), ensure_ascii=False)))

    def test_a_spec_that_is_not_utf8_is_refused_and_nothing_is_stored(self):
        self.onboard()
        raw = json.dumps(SPEC, ensure_ascii=False).encode("cp1252")
        result = self.rapid("start", "feature", "--spec-file", "-", "--json", raw=raw)
        self.assertEqual(result.returncode, 1)
        self.assertIn("RAPID1424", result.stderr.decode("utf-8", "replace"))
        self.assertEqual(self.stored_spec_titles(), {})

    def test_a_spec_file_is_read_as_utf8_too(self):
        self.onboard()
        (self.root / "spec.json").write_bytes(json.dumps(SPEC, ensure_ascii=False).encode("utf-8-sig"))
        self.ok("start", "feature", "--spec-file", "spec.json", "--json")
        self.assertIn("notificacion-de-dueno", self.stored_spec_titles())

    def test_a_document_from_stdin_keeps_its_characters(self):
        self.onboard()
        self.ok("setup", "doc", "brief", "--source", "drafted", "--replace", "--file", "-", raw=BRIEF.encode("utf-8"))
        text = (self.root / "docs" / "PRODUCT_BRIEF.md").read_text(encoding="utf-8")
        self.assertIn("del dueño", text)
        self.assertIsNone(find_mojibake(text))

    def test_a_document_that_is_not_utf8_is_rapid1424_not_rapid1413(self):
        self.onboard()
        result = self.rapid("setup", "doc", "brief", "--source", "drafted", "--replace", "--file", "-", raw=BRIEF.encode("cp1252"))
        self.assertEqual(result.returncode, 1)
        stderr = result.stderr.decode("utf-8", "replace")
        self.assertIn("RAPID1424", stderr)
        self.assertNotIn("RAPID1413", stderr)
        (self.root / "latin.md").write_bytes(BRIEF.encode("cp1252"))
        result = self.rapid("setup", "doc", "brief", "--source", "drafted", "--replace", "--file", "latin.md")
        self.assertIn("RAPID1424", result.stderr.decode("utf-8", "replace"))


class MojibakeTests(Project):
    def test_the_typical_sequences_are_found(self):
        for text, sample in (("vÃ¡lidas", "Ã¡"), ("MÃ³dulo", "Ã³"), ("dueÃ±o", "Ã±"), ("cafÃ©", "Ã©"), ("Â¿quÃ©?", "Â¿"),
                             ("â€œhola”", "â€œ")):
            with self.subTest(text=text):
                self.assertEqual(find_mojibake(text), sample)

    def test_correct_text_is_not_flagged(self):
        for text in ("Módulo válido, dueño ¿qué?", "NÃO", "Ñandú", "Â", "naïve café", "100 % ok"):
            with self.subTest(text=text):
                self.assertIsNone(find_mojibake(text))

    def test_it_round_trips_with_what_the_console_did(self):
        original = "Notificación de dueño: ¿válida?"
        self.assertIsNotNone(find_mojibake(original.encode("utf-8").decode("cp1252", errors="ignore")))

    def test_doctor_warns_about_a_saved_spec_without_rewriting_it(self):
        self.onboard()
        broken = {**SPEC, "title": "Notificacion", "acceptance_criteria": ["Las fechas son vÃ¡lidas"]}
        self.ok("start", "feature", "--spec-file", "-", "--json", raw=json.dumps(broken, ensure_ascii=False).encode("utf-8"))
        before = (self.root / ".rapid-os" / "specs" / "notificacion" / "spec.json").read_bytes()
        out = self.ok("doctor")
        self.assertIn("RAPID1425", out)
        self.assertIn("notificacion", out)
        self.assertIn("Ã¡", out)
        self.assertIn("rapid spec revise", out)
        self.assertEqual((self.root / ".rapid-os" / "specs" / "notificacion" / "spec.json").read_bytes(), before)

    def test_doctor_warns_about_an_onboarding_document(self):
        self.onboard()
        self.ok("setup", "doc", "brief", "--source", "drafted", "--replace", "--file", "-",
                raw=BRIEF.replace("dueño", "dueÃ±o").encode("utf-8"))
        out = self.ok("doctor")
        self.assertIn("RAPID1425", out)
        self.assertIn("PRODUCT_BRIEF.md", out)

    def test_doctor_is_quiet_about_correct_text(self):
        self.onboard()
        self.ok("start", "feature", "--spec-file", "-", "--json", raw=json.dumps(SPEC, ensure_ascii=False).encode("utf-8"))
        self.assertNotIn("RAPID1425", self.ok("doctor"))


class ResolveExecutableTests(unittest.TestCase):
    def test_the_first_element_is_replaced_by_what_which_finds(self):
        with mock.patch.object(check_module.shutil, "which", return_value="C:\\tools\\pnpm.cmd"):
            self.assertEqual(check_module.resolve_executable(["pnpm", "test"]), ["C:\\tools\\pnpm.cmd", "test"])

    def test_it_is_left_as_typed_when_which_finds_nothing(self):
        with mock.patch.object(check_module.shutil, "which", return_value=None):
            self.assertEqual(check_module.resolve_executable(["nada", "x"]), ["nada", "x"])
        self.assertEqual(check_module.resolve_executable([]), [])


class RunCheckResolvesTests(Project):
    def test_run_check_runs_the_resolved_path_and_records_the_typed_argv(self):
        self.env["PYTHONIOENCODING"] = "utf-8"
        self.onboard()
        self.ok("start", "feature", "--spec-file", "-", "--json", raw=json.dumps(SPEC, ensure_ascii=False).encode("utf-8"))
        run_id = json.loads((self.root / ".rapid-os" / "session.json").read_text("utf-8"))["active_run_id"]
        seen = {}
        real_run = subprocess.run

        def fake_run(argv, **kwargs):
            if str(argv[0]).endswith("pnpm.cmd"):  # the test command; git and the rest run for real
                seen["argv"] = list(argv)
                return subprocess.CompletedProcess(argv, 0, stdout="Tests  1 passed (1)\n", stderr=None)
            return real_run(argv, **kwargs)

        with mock.patch.object(check_module.shutil, "which", return_value="C:\\tools\\pnpm.cmd"), \
                mock.patch.object(check_module.subprocess, "run", side_effect=fake_run):
            result = check_module.run_check(
                self.root, self.root / ".rapid-os", run_id, ["pnpm", "test"], gate_ids=("gate.tests",),
                test_command=["pnpm", "test"],
            )
        self.assertEqual(seen["argv"][0], "C:\\tools\\pnpm.cmd")
        self.assertEqual(result.argv, ("pnpm", "test"))  # compared with test_command and recorded as typed
        self.assertEqual(result.kind, "test_result")  # equal to test_command, so a test run
        self.assertEqual(result.evidence.payload["command"], "pnpm test")


class CombinedCommandTests(unittest.TestCase):
    def run_combined(self, codes, which=None):
        commands = [["pnpm", "test"] for _ in codes]
        argv = combine_test_commands(commands)
        namespace = {}
        calls = []

        def fake_call(cmd, *a, **k):
            calls.append(list(cmd))
            return codes[len(calls) - 1]

        with mock.patch("subprocess.call", side_effect=fake_call), mock.patch("shutil.which", return_value=which):
            with self.assertRaises(SystemExit) as caught:
                exec(argv[2], namespace)  # the code `-c` would run
        return caught.exception.code, calls

    def test_every_command_runs_and_the_result_is_zero_or_one(self):
        self.assertEqual(self.run_combined([0, 0])[0], 0)
        self.assertEqual(self.run_combined([0, 3])[0], 1)
        self.assertEqual(self.run_combined([3, 0])[0], 1)

    def test_a_process_killed_by_a_signal_fails_the_combined_run(self):
        code, calls = self.run_combined([0, -9])
        self.assertEqual(code, 1)  # max() of [0, -9] was 0: the failure disappeared
        self.assertEqual(len(calls), 2)

    def test_the_first_command_failing_does_not_skip_the_second(self):
        _code, calls = self.run_combined([1, 0])
        self.assertEqual(len(calls), 2)

    def test_each_executable_is_resolved(self):
        _code, calls = self.run_combined([0, 0], which="C:\\tools\\pnpm.cmd")
        self.assertEqual([c[0] for c in calls], ["C:\\tools\\pnpm.cmd", "C:\\tools\\pnpm.cmd"])

    def test_the_interpreter_is_one_that_exists(self):
        commands = [["a"], ["b"]]
        with mock.patch("shutil.which", side_effect=lambda name: "/x/python3" if name == "python3" else None):
            self.assertEqual(combine_test_commands(commands)[0], "python3")
        with mock.patch("shutil.which", return_value=None):
            self.assertEqual(combine_test_commands(commands)[0], sys.executable)
        with mock.patch("shutil.which", return_value="/x/python"):
            self.assertEqual(combine_test_commands(commands)[0], "python")

    def test_a_single_command_is_returned_as_is(self):
        self.assertEqual(combine_test_commands([["uv", "run", "pytest"]]), ["uv", "run", "pytest"])

    def test_the_runner_is_a_single_template(self):
        self.assertEqual(COMBINED_TEST_RUNNER.count("{commands!r}"), 1)


class DisplayCommandTests(unittest.TestCase):
    def test_posix_uses_shlex(self):
        with mock.patch.object(core_text.sys, "platform", "linux"):
            self.assertEqual(display_command(["python", "-c", "print('a b')"]), "python -c 'print('\"'\"'a b'\"'\"')'")

    def test_windows_uses_list2cmdline(self):
        with mock.patch.object(core_text.sys, "platform", "win32"):
            self.assertEqual(display_command(["python", "-c", "import os; os.x('a b')"]), 'python -c "import os; os.x(\'a b\')"')

    def test_setup_next_shows_the_combined_command_quoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}
            run = lambda *a: subprocess.run([sys.executable, "-m", "rapid_os.cli.main", *a], cwd=root, capture_output=True,  # noqa: E731
                                            text=True, encoding="utf-8", env=env)
            for step in (("stack", "python-fastapi"), ("stack", "nextjs", "--component", "frontend"),
                         ("topology", "fullstack-separated"), ("archetype", "mvp"), ("ai", "no"), ("agents", "claude")):
                self.assertEqual(run("setup", "set", *step).returncode, 0)
            out = run("setup", "next").stdout
            line = next(l for l in out.splitlines() if l.startswith("Suggested test command:"))
            self.assertIn("-c", line)
            self.assertIn("import shutil, subprocess, sys;", line)
            self.assertTrue(line.split(": ", 1)[1].startswith(("python", sys.executable)))
            self.assertRegex(line, r"[\"']")  # quoted, so it can be pasted


class MissingTestCommandTests(Project):
    def test_doctor_warns_when_the_test_command_does_not_exist_and_proposes_the_catalog_one(self):
        self.onboard(test_command="pytest-que-no-existe")
        out = self.ok("doctor")
        self.assertIn("RAPID1426", out)
        self.assertIn("pytest-que-no-existe", out)
        self.assertIn("uv run pytest", out)
        self.assertIn("rapid setup set test-command", out)
        self.assertIn("rapid setup finish", out)

    def test_doctor_is_quiet_when_the_command_exists(self):
        self.onboard(test_command=f'"{sys.executable}" -m unittest')
        self.assertNotIn("RAPID1426", self.ok("doctor"))

    def test_doctor_is_quiet_when_which_finds_a_cmd_shim(self):
        import rapid_os.cli.main as cli

        with mock.patch.object(cli.shutil, "which", return_value="C:\\tools\\pnpm.cmd"):
            self.assertTrue(cli._test_command_found(["pnpm", "test"]))
        with mock.patch.object(cli.shutil, "which", return_value=None), mock.patch.object(cli, "CURRENT_DIR", self.root):
            self.assertFalse(cli._test_command_found(["pnpm", "test"]))
            (self.root / "mvnw").write_text("#!/bin/sh\n", encoding="utf-8")
            self.assertTrue(cli._test_command_found(["./mvnw", "test"]))

    def test_start_warns_before_the_baseline(self):
        self.onboard(test_command="pytest-que-no-existe")
        subprocess.run(["git", "add", "-A"], cwd=self.root, env=self.env, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "base", "--allow-empty"], cwd=self.root, env=self.env, capture_output=True)
        result = self.rapid("start", "feature", "--spec-file", "-", "--json", raw=json.dumps(SPEC, ensure_ascii=False).encode("utf-8"))
        stderr = result.stderr.decode("utf-8", "replace")
        self.assertIn("RAPID1426", stderr)
        self.assertIn("WARNING", stderr)

    def test_setting_the_test_command_after_finishing_is_applied_and_next_is_done(self):
        self.onboard(test_command="pytest-que-no-existe")
        self.ok("setup", "set", "test-command", f'"{sys.executable}" -m unittest')
        config = json.loads((self.root / ".rapid-os" / "config.json").read_text("utf-8"))
        self.assertEqual(config["test_command"], [sys.executable, "-m", "unittest"])
        self.assertEqual(json.loads(self.ok("setup", "next", "--json"))["kind"], "done")
        self.assertNotIn("RAPID1426", self.ok("doctor"))


class HandEditedAgentFilesTests(Project):
    def test_untouched_files_regenerate_silently_and_hand_edits_are_warned_and_backed_up(self):
        self.env["PYTHONIOENCODING"] = "utf-8"
        self.onboard()
        manifest = json.loads((self.root / ".rapid-os" / "generated.json").read_text("utf-8"))
        self.assertIn("CLAUDE.md", manifest)
        first = self.rapid("setup", "set", "archetype", "corporate", "--refresh")
        self.assertNotIn("RAPID1427", first.stderr.decode("utf-8", "replace"))
        (self.root / "CLAUDE.md").write_text((self.root / "CLAUDE.md").read_text("utf-8") + "\n# nota a mano\n", encoding="utf-8")
        second = self.rapid("setup", "set", "archetype", "mvp", "--refresh")
        stderr = second.stderr.decode("utf-8", "replace")
        self.assertIn("RAPID1427 CLAUDE.md", stderr)
        self.assertIn(".rapid-os/backups", stderr)
        saved = [p.read_text("utf-8") for p in (self.root / ".rapid-os" / "backups").glob("CLAUDE.md*")]
        self.assertTrue(any("# nota a mano" in text for text in saved))
        self.assertNotIn("# nota a mano", (self.root / "CLAUDE.md").read_text("utf-8"))
        third = self.rapid("setup", "set", "archetype", "corporate", "--refresh")
        self.assertNotIn("RAPID1427", third.stderr.decode("utf-8", "replace"))

    def test_a_project_without_a_manifest_is_not_accused(self):
        self.env["PYTHONIOENCODING"] = "utf-8"
        self.onboard()
        (self.root / ".rapid-os" / "generated.json").unlink()
        (self.root / "CLAUDE.md").write_text("otro contenido\n", encoding="utf-8")
        result = self.rapid("setup", "set", "archetype", "corporate", "--refresh")
        self.assertNotIn("RAPID1427", result.stderr.decode("utf-8", "replace"))


if __name__ == "__main__":
    unittest.main()

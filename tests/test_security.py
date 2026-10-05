import argparse
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from rapid_os.cli import main as cli_main
from rapid_os.core.filesystem import (
    ensure_path_within_root,
    resolve_child_path,
    safe_rmtree_child,
)
from rapid_os.core.identifiers import (
    validate_identifier,
    validate_remote_package_reference,
)
from rapid_os.core.process import (
    build_npx_skills_add_command,
    is_npx_available,
    resolve_npx_executable,
    run_command,
    run_npx_skills_add,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=REPO_ROOT)


class SubprocessSecurityTests(unittest.TestCase):
    def test_command_injection_payloads_are_passed_as_single_literal_argument(self):
        payloads = (
            "foo && whoami",
            "foo; rm -rf .",
            "foo | echo injected",
            "$(whoami)",
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                recorded_calls = []

                def fake_runner(argv, **kwargs):
                    recorded_calls.append((argv, kwargs))
                    return MagicMock(returncode=0)

                run_npx_skills_add(
                    payload,
                    which_fn=lambda name: "/usr/bin/npx" if name == "npx" else None,
                    os_name="posix",
                    runner=fake_runner,
                )

                self.assertEqual(len(recorded_calls), 1)
                argv, kwargs = recorded_calls[0]
                self.assertEqual(argv, ["/usr/bin/npx", "skills", "add", payload])
                self.assertEqual(len(argv), 4)
                self.assertIs(kwargs.get("shell"), False)
                self.assertIs(kwargs.get("check"), True)

    def test_manage_skills_add_never_uses_shell_true_for_injection_payloads(self):
        payloads = (
            "foo && whoami",
            "foo; rm -rf .",
            "foo | echo injected",
            "$(whoami)",
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                with patch.object(
                    cli_main, "check_node_installed", return_value=True
                ), patch.object(
                    cli_main.subprocess, "run"
                ) as mock_run, contextlib.redirect_stdout(io.StringIO()):
                    cli_main.manage_skills(
                        argparse.Namespace(action="add", name=payload)
                    )

                self.assertEqual(mock_run.call_count, 1)
                called_args, called_kwargs = mock_run.call_args
                argv = called_args[0]
                self.assertIsInstance(argv, list)
                self.assertEqual(argv[1:], ["skills", "add", payload])
                self.assertIs(called_kwargs.get("shell"), False)
                self.assertIs(called_kwargs.get("check"), True)

    def test_windows_npx_resolution_prefers_npx_cmd(self):
        resolved = resolve_npx_executable(
            which_fn=lambda name: "C:\\Program Files\\nodejs\\npx.cmd"
            if name == "npx.cmd"
            else None,
            os_name="nt",
        )
        self.assertEqual(resolved, "C:\\Program Files\\nodejs\\npx.cmd")

    def test_posix_npx_resolution_uses_npx(self):
        resolved = resolve_npx_executable(
            which_fn=lambda name: "/usr/local/bin/npx" if name == "npx" else None,
            os_name="posix",
        )
        self.assertEqual(resolved, "/usr/local/bin/npx")

    def test_is_npx_available_uses_shell_false(self):
        recorded = []

        def fake_runner(argv, **kwargs):
            recorded.append((argv, kwargs))
            return MagicMock(returncode=0)

        available = is_npx_available(
            which_fn=lambda name: "/usr/bin/npx",
            os_name="posix",
            runner=fake_runner,
        )
        self.assertTrue(available)
        self.assertEqual(recorded[0][0], ["/usr/bin/npx", "--version"])
        self.assertIs(recorded[0][1]["shell"], False)

    def test_run_command_rejects_string_command_and_null_bytes(self):
        with self.assertRaises(ValueError):
            run_command("npx skills add foo")
        with self.assertRaises(ValueError):
            run_command(["npx", "skills\x00injected"])
        with self.assertRaises(ValueError):
            build_npx_skills_add_command("   ")


class PathContainmentSecurityTests(unittest.TestCase):
    def test_resolve_child_path_rejects_traversal_and_absolute_paths(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()

            unsafe_inputs = (
                "",
                "   ",
                ".",
                "..",
                "../",
                "../../foo",
                "..\\..\\foo",
                "/root/file",
                "\\Windows\\System32",
                "C:\\Windows",
                "C:Windows",
                "foo/../../../bar",
                "foo\\..\\..\\..\\bar",
                "valid\x00evil",
            )
            for value in unsafe_inputs:
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        resolve_child_path(root, value)

    def test_resolve_child_path_single_segment_rejects_nested_paths(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()

            with self.assertRaises(ValueError):
                resolve_child_path(root, "nested/skill", single_segment=True)
            with self.assertRaises(ValueError):
                resolve_child_path(root, "nested\\skill", single_segment=True)

            resolved = resolve_child_path(root, "my-skill", single_segment=True)
            self.assertEqual(resolved, (root / "my-skill").resolve())

    def test_safe_rmtree_child_refuses_to_delete_outside_root(self):
        with workspace_tempdir() as tmp:
            workspace = Path(tmp)
            target_root = workspace / ".cursor" / "skills"
            target_root.mkdir(parents=True)
            outside_dir = workspace / "important_outside_dir"
            outside_dir.mkdir()
            marker = outside_dir / "keep.txt"
            marker.write_text("do not delete", encoding="utf-8")

            with self.assertRaises(ValueError):
                safe_rmtree_child(target_root, outside_dir)
            with self.assertRaises(ValueError):
                safe_rmtree_child(target_root, target_root)

            self.assertTrue(marker.exists())

    def test_local_skill_install_blocks_traversal_and_preserves_outside_files(self):
        with workspace_tempdir() as tmp:
            workspace = Path(tmp)
            project_dir = workspace / "project"
            project_dir.mkdir()
            templates_dir = workspace / "templates"
            (templates_dir / "skills" / "safe-skill").mkdir(parents=True)
            victim_dir = workspace / "victim"
            victim_dir.mkdir()
            victim_file = victim_dir / "secret.txt"
            victim_file.write_text("keep", encoding="utf-8")

            unsafe_names = (
                "../victim",
                "..\\victim",
                "../../victim",
                "/root/file",
                "C:\\Windows",
                "foo/../../../victim",
            )

            for unsafe_name in unsafe_names:
                with self.subTest(unsafe_name=unsafe_name):
                    with patch.object(
                        cli_main, "CURRENT_DIR", project_dir
                    ), patch.object(
                        cli_main, "TEMPLATES_DIR", templates_dir
                    ), patch.object(
                        cli_main,
                        "CONFIG_FILE",
                        project_dir / ".rapid-os" / "config.json",
                    ), contextlib.redirect_stdout(io.StringIO()):
                        with self.assertRaises(SystemExit) as ctx:
                            cli_main.manage_skills(
                                argparse.Namespace(
                                    action="install",
                                    name=unsafe_name,
                                )
                            )
                        self.assertEqual(ctx.exception.code, 1)
                    self.assertTrue(victim_file.exists())

    def test_business_template_save_blocks_path_traversal(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            templates = root / "templates"
            for dirname in ("stacks", "topologies", "archetypes", "business"):
                (templates / dirname).mkdir(parents=True)
            (templates / "stacks" / "web-modern.md").write_text(
                "# web-modern\n", encoding="utf-8"
            )
            (templates / "topologies" / "front-end-only.md").write_text(
                "# front-end-only\n", encoding="utf-8"
            )
            (templates / "archetypes" / "mvp").mkdir()
            (templates / "archetypes" / "mvp" / "coding-rules.md").write_text(
                "rules", encoding="utf-8"
            )
            imported_biz = root / "rules.md"
            imported_biz.write_text("# My Business Rules\n", encoding="utf-8")

            inputs = iter(
                [
                    "1",  # topology
                    "1",  # agents
                    "",  # research tools
                    "y",  # import file
                    str(imported_biz),  # file path
                    "y",  # save as business template
                    "../../escaped_template",  # malicious template name
                ]
            )
            args = argparse.Namespace(
                stack="web-modern",
                archetype="mvp",
                no_scan=True,
            )

            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "PROJECT_RAPID_DIR", project / ".rapid-os"
            ), patch.object(
                cli_main, "CONFIG_FILE", project / ".rapid-os" / "config.json"
            ), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), patch(
                "builtins.input", lambda prompt="": next(inputs)
            ), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main.init_project(args)
                self.assertEqual(ctx.exception.code, 1)

            self.assertFalse((root / "escaped_template.md").exists())
            self.assertEqual(list((templates / "business").glob("*.md")), [])

    def test_deploy_assistant_blocks_unsafe_target_names(self):
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            templates = root / "templates"
            (templates / "deploy").mkdir(parents=True)

            with patch.object(cli_main, "CURRENT_DIR", project), patch.object(
                cli_main, "TEMPLATES_DIR", templates
            ), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    cli_main.deploy_assistant(
                        argparse.Namespace(target="../../outside")
                    )
                self.assertEqual(ctx.exception.code, 1)

            self.assertFalse((project / "DEPLOY.md").exists())


class IdentifierValidationTests(unittest.TestCase):
    def test_validate_identifier_accepts_simple_local_slugs(self):
        for valid in ("mvp", "corporate", "web-modern", "skill_1", "v2.0-template"):
            with self.subTest(valid=valid):
                self.assertEqual(validate_identifier(valid), valid)

    def test_validate_identifier_rejects_paths_and_remote_references(self):
        invalid_values = (
            "",
            "   ",
            "../foo",
            "..\\foo",
            "vercel-labs/agent-skills",
            "@scope/pkg",
            "/abs/path",
            "C:\\Windows",
            "-flag",
            ".hidden",
            "trailing.",
            "foo && bar",
        )
        for invalid in invalid_values:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_identifier(invalid)

    def test_validate_remote_package_reference_supports_owner_and_scoped_packages(self):
        valid_refs = (
            "vercel-labs/agent-skills",
            "@upstash/context7-mcp",
            "@modelcontextprotocol/server-filesystem@0.6.2",
            "firecrawl-mcp",
            "firecrawl-mcp@1.2.0-beta.1",
        )
        for ref in valid_refs:
            with self.subTest(ref=ref):
                self.assertEqual(validate_remote_package_reference(ref), ref)

    def test_validate_remote_package_reference_rejects_traversal_and_flags(self):
        invalid_refs = (
            "",
            "   ",
            "-y",
            "--help",
            "../secret",
            "owner/../secret",
            "owner/pkg/extra",
            "/etc/passwd",
            "C:\\Windows",
            "pkg with spaces",
            "pkg;whoami",
        )
        for ref in invalid_refs:
            with self.subTest(ref=ref):
                with self.assertRaises(ValueError):
                    validate_remote_package_reference(ref)


if __name__ == "__main__":
    unittest.main()

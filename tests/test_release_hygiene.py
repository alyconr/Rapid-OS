"""Release hygiene: actions pinned by SHA, SPDX license metadata, community files, Windows smoke, neutral mode templates."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

ROOT = Path(__file__).resolve().parents[1]
USES = re.compile(r"^[\s-]*uses:\s*(\S+)(.*)$", re.M)
PINNED = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
VERSION_COMMENT = re.compile(r"^\s*#\s*v?\d+(\.\d+)*\s*$")  # some projects tag without the v
# Where a `uses:` can live: real workflows, the workflows Rapid OS generates, and the examples the docs tell people to copy.
SCANNED = (".github", "templates", "docs", "website/i18n")
SUFFIXES = {".yml", ".yaml", ".md", ".mdx"}


def uses_lines():
    for folder in SCANNED:
        for path in sorted((ROOT / folder).rglob("*")):
            if path.suffix in SUFFIXES and path.is_file():
                for match in USES.finditer(path.read_text(encoding="utf-8")):
                    yield path.relative_to(ROOT).as_posix(), match.group(1), match.group(2)


class PinnedActionsTests(unittest.TestCase):
    def test_every_uses_is_pinned_to_a_full_sha_with_its_version(self):
        found = list(uses_lines())
        self.assertGreater(len(found), 10)
        for path, target, comment in found:
            if target.startswith(("./", "docker://")):
                continue
            with self.subTest(path=path, target=target):
                self.assertRegex(target, PINNED)
                self.assertRegex(comment, VERSION_COMMENT)

    def test_dependabot_keeps_the_pins_and_pip_current(self):
        text = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        self.assertIn("package-ecosystem: github-actions", text)
        self.assertIn("package-ecosystem: pip", text)


class LicenseMetadataTests(unittest.TestCase):
    @unittest.skipIf(tomllib is None, "tomllib needs Python 3.11")
    def test_pyproject_uses_the_spdx_form(self):
        config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["project"]["license"], "MIT")
        self.assertEqual(config["project"]["license-files"], ["LICENSE"])
        self.assertEqual(config["build-system"]["requires"], ["setuptools>=77.0.3"])
        # PEP 639: a license expression and a license classifier cannot go together.
        self.assertFalse([c for c in config["project"]["classifiers"] if c.startswith("License ::")])


class CommunityFilesTests(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_security_policy(self):
        text = self.read("SECURITY.md")
        for needle in ("3.2.x", "security/advisories/new", "Out of scope", ".rapid-os/"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_contributing(self):
        text = self.read("CONTRIBUTING.md")
        for needle in ("python -m unittest discover", "RAPID_UPDATE_GOLDEN=1", "website/i18n/es/", "[Unreleased]", "rapid approve"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_code_of_conduct_names_the_contact_the_maintainer_chose(self):
        text = self.read("CODE_OF_CONDUCT.md")
        self.assertIn("Contributor Covenant", text)
        self.assertIn("version 2.1", text)
        self.assertNotIn("[INSERT CONTACT METHOD]", text)
        self.assertNotIn("to be confirmed by the maintainer", text)
        self.assertIn("alyconr473@gmail.com", text)

    def test_issue_and_pull_request_templates(self):
        bug = self.read(".github/ISSUE_TEMPLATE/bug_report.yml")
        for needle in ("rapid --version", "rapid doctor", "Harness", "Shell", "Operating system"):
            with self.subTest(needle=needle):
                self.assertIn(needle, bug)
        feature = self.read(".github/ISSUE_TEMPLATE/feature_request.yml")
        for needle in ("Problem", "Proposal", "mode"):
            with self.subTest(needle=needle):
                self.assertIn(needle, feature)
        config = self.read(".github/ISSUE_TEMPLATE/config.yml")
        self.assertIn("alyconr.github.io/Rapid-OS", config)
        self.assertIn("SECURITY.md", config)
        pull_request = self.read(".github/PULL_REQUEST_TEMPLATE.md")
        for needle in ("python -m unittest discover", "website/i18n/es/", "CHANGELOG", "invariants"):
            with self.subTest(needle=needle):
                self.assertIn(needle, pull_request)


class WindowsSmokeTests(unittest.TestCase):
    def test_workflow_runs_the_smoke_within_ten_minutes(self):
        text = (ROOT / ".github" / "workflows" / "windows-smoke.yml").read_text(encoding="utf-8")
        for needle in ("windows-latest", 'python-version: "3.12"', "timeout-minutes: 10", "workflow_dispatch",
                       '"rapid_os/**"', '"templates/**"', '"pyproject.toml"', "branches: [main]", "python -m build --wheel",
                       "scripts/windows_smoke.py", "tests.test_stdin_utf8_and_resolution", "tests.test_legacy_specs",
                       "tests.test_rc4_specs_utf8.CheckReadsUtf8OutputTests"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        # PYTHONUTF8 would hide the code page bug the job exists to catch.
        self.assertNotRegex(text, r"(?m)^\s*PYTHONUTF8:")


class ReadmeTests(unittest.TestCase):
    def test_hero_promise_and_the_order_of_the_first_sections(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("Senior Engineers", readme)
        quick_start = readme.index('<a name="quick-start-shortcuts">')
        guarantees = readme.index('<a name="harness-guarantees">')
        about = readme.index('<a name="about-the-project">')
        self.assertLess(quick_start, guarantees)
        self.assertLess(guarantees, about)

    def test_the_guarantees_table_names_every_harness(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        section = readme[readme.index('<a name="harness-guarantees">'):readme.index('<a name="about-the-project">')]
        for harness in ("Claude Code", "Codex", "Cursor", "VS Code", "Antigravity"):
            with self.subTest(harness=harness):
                self.assertRegex(section, rf"(?m)^\| \*\*{harness}")


class ModeTemplatesTests(unittest.TestCase):
    def test_no_mode_template_talks_about_rapid_os_itself(self):
        for path in sorted((ROOT / "templates" / "modes").iterdir()):
            text = path.read_text(encoding="utf-8").lower()
            for word in ("rapid_os/", "conductor", "dataclasses"):
                with self.subTest(path=path.name, word=word):
                    self.assertNotIn(word, text)

    def test_the_research_shortcut_only_asks_for_rapid_check_when_code_runs(self):
        text = (ROOT / "templates" / "shortcuts" / "rapid-research.md").read_text(encoding="utf-8")
        self.assertIn("Si el experimento ejecuta código, hazlo con `rapid check -- <comando>`", text)
        self.assertNotIn("Corre los tests siempre", text)


if __name__ == "__main__":
    unittest.main()

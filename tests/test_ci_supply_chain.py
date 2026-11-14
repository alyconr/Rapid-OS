"""H-77: the security workflow failed on the first push of a project Rapid OS guided.

In the rc.3 e2e (talleres-rc2) semgrep with p/owasp-top-ten blocked frontend/pnpm-workspace.yaml with the rules
pnpm-block-exotic-sub-dependencies, pnpm-missing-minimum-release-age and pnpm-trust-policy, and bandit never ran
because it came after semgrep in the same job. Now the stack templates and security.md ask for those settings (and
the equivalents of npm, Yarn, uv and Bundler that the same ruleset checks), and every scanner has a job of its own.

Golden files live in tests/golden/supply-chain/. Regenerate them after an intentional template change with:
    RAPID_UPDATE_GOLDEN=1 python -m unittest tests.test_ci_supply_chain
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile
import unittest

from rapid_os.domain.catalog import load_catalog
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.security import package_manager_regions, render_ci_workflow, render_security_standard
from rapid_os.orchestration.setup_apply import render_tech_stack_file
from tests.test_ci_component_dirs import BACKEND_ONLY, TALLERES, state_for

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
CATALOG = load_catalog(TEMPLATES)
GOLDEN = ROOT / "tests" / "golden" / "supply-chain"
BASELINE = (TEMPLATES / "security" / "baseline.md").read_text(encoding="utf-8")
RAILS = state_for("backend-only", {"backend": "ruby-rails"})
PNPM_SETTINGS = ("minimumReleaseAge: 10080", "trustPolicy: no-downgrade", "blockExoticSubdeps: true")
SCANNERS = ("semgrep scan", "bandit -r", "go vet", "cargo clippy", "brakeman --no-pager")


def jobs(text: str) -> dict[str, str]:
    """`{job_id: body}` of a rendered workflow (jobs are the 2-space keys under `jobs:`)."""
    body = text.split("\njobs:\n", 1)[1]
    found: dict[str, str] = {}
    current = None
    for line in body.split("\n"):
        match = re.match(r"^  ([a-z][\w-]*):$", line)
        if match:
            current = match.group(1)
            found[current] = ""
        elif line.startswith("  #") or line.startswith("# "):  # the comment of the next job, or a region marker
            current = None
        elif current:
            found[current] += line + "\n"
    return found


def tech_stack(state) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / ".python-version").write_text("3.12\n", encoding="utf-8")  # not this interpreter's
        return render_tech_stack_file(
            state, CATALOG, TEMPLATES, model=ProjectModel(root=Path(tmp)), scanned=False, project_root=Path(tmp)
        )


def security(state) -> str:
    return render_security_standard(BASELINE, archetype="mvp", stack_id=state.stack_ids, ai=False)


class ScannersDoNotBlockEachOtherTests(unittest.TestCase):
    def test_each_scanner_has_a_job_of_its_own(self):
        for template in sorted((TEMPLATES / "ci").glob("*-security.yml")):
            language = template.name.removesuffix("-security.yml")
            text = render_ci_workflow(template.read_text("utf-8"), archetype="corporate", language=language, dirs=["backend"])
            with self.subTest(language=language):
                found = jobs(text)
                self.assertIn("semgrep", found)
                for job_id, body in found.items():
                    scanners = [s for s in SCANNERS if s in body]
                    self.assertLessEqual(len(scanners), 1, (job_id, scanners))
                    self.assertNotIn("needs: semgrep", body)
                    self.assertNotIn("needs: [semgrep", body)

    def test_bandit_runs_even_when_semgrep_fails(self):
        text = render_ci_workflow((TEMPLATES / "ci" / "python-security.yml").read_text("utf-8"), archetype="mvp",
                                  language="python")
        found = jobs(text)
        self.assertIn("semgrep scan --config p/owasp-top-ten --error --metrics=off", found["semgrep"])
        self.assertNotIn("bandit", found["semgrep"])
        self.assertIn("bandit -r . -ll", found["bandit"])
        self.assertNotIn("needs:", found["bandit"])

    def test_the_language_scanners_run_in_each_component_folder(self):
        for language, job_id in (("go", "go-vet"), ("rust", "clippy"), ("ruby", "brakeman")):
            text = render_ci_workflow((TEMPLATES / "ci" / f"{language}-security.yml").read_text("utf-8"),
                                      archetype="mvp", language=language, dirs=["backend"])
            with self.subTest(language=language):
                body = jobs(text)[job_id]
                self.assertIn('dir: ["backend"]', body)
                self.assertIn("working-directory: ${{ matrix.dir }}", body)
                self.assertIn("::warning title=Nada que analizar::", body)


class SupplyChainSettingsTests(unittest.TestCase):
    def test_every_pnpm_stack_asks_for_the_three_settings(self):
        for path in sorted((TEMPLATES / "stacks").rglob("*.md")):
            text = path.read_text("utf-8")
            if "**Package manager:** pnpm." not in text:
                continue
            with self.subTest(stack=path.name):
                for setting in PNPM_SETTINGS:
                    self.assertIn(setting, text)
                self.assertIn("pnpm 10.26 or later", text)
                self.assertIn("create it with these three settings when scaffolding", text)
                self.assertIn("https://pnpm.io/settings", text)

    def test_uv_and_bundler_stacks_ask_for_their_cooldown(self):
        self.assertIn('exclude-newer = "7 days"', (TEMPLATES / "stacks" / "backend" / "python-fastapi.md").read_text("utf-8"))
        self.assertIn('cooldown: 7', (TEMPLATES / "stacks" / "backend" / "ruby-rails.md").read_text("utf-8"))

    def test_security_md_carries_the_settings_of_the_project_managers(self):
        talleres = security(TALLERES)
        for setting in PNPM_SETTINGS + ("min-release-age=7", 'npmMinimalAgeGate: "7d"', 'exclude-newer = "7 days"'):
            self.assertIn(setting, talleres)
        self.assertNotIn("cooldown: 7", talleres)
        rails = security(RAILS)
        self.assertIn('source "https://rubygems.org", cooldown: 7', rails)
        self.assertNotIn("minimumReleaseAge: 10080", rails)
        self.assertNotIn('exclude-newer = "7 days"', security(state_for("backend-only", {"backend": "go"})))

    def test_the_regions(self):
        self.assertEqual(package_manager_regions(["python-fastapi", "angular"]), {"uv", "node"})
        self.assertEqual(package_manager_regions(["ruby-rails"]), {"bundler"})
        self.assertEqual(package_manager_regions(["python-django"]), set())

    def test_the_templates_match_the_golden_files(self):
        update = os.environ.get("RAPID_UPDATE_GOLDEN") == "1"
        cases = {
            "fullstack-separated/tech-stack.md": tech_stack(TALLERES),
            "fullstack-separated/security.md": security(TALLERES),
            "backend-only-python/tech-stack.md": tech_stack(BACKEND_ONLY),
            "ruby-rails/tech-stack.md": tech_stack(RAILS),
            "ruby-rails/security.md": security(RAILS),
        }
        for name, content in cases.items():
            golden = GOLDEN / name
            with self.subTest(golden=name):
                if update:
                    golden.parent.mkdir(parents=True, exist_ok=True)
                    golden.write_text(content, encoding="utf-8", newline="\n")
                self.assertEqual(content.replace("\r\n", "\n"), golden.read_text("utf-8").replace("\r\n", "\n"))


if __name__ == "__main__":
    unittest.main()

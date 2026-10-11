"""Tests for RAPID OS documentation deployment configuration, workflows, and smoke validations."""

import os
import pathlib
import unittest
import urllib.request
import urllib.error

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WEBSITE_DIR = REPO_ROOT / "website"
CONFIG_FILE = WEBSITE_DIR / "docusaurus.config.ts"
SIDEBARS_FILE = WEBSITE_DIR / "sidebars.ts"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docs-deploy.yml"
DOCS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docs.yml"
BUILD_DIR = WEBSITE_DIR / "build"


class TestDocumentationProductionConfig(unittest.TestCase):
    """Verifies that Docusaurus configuration is strictly configured for production."""

    def test_docusaurus_config_exists(self):
        self.assertTrue(CONFIG_FILE.exists(), f"Missing config file: {CONFIG_FILE}")

    def test_production_url_and_base_url(self):
        content = CONFIG_FILE.read_text(encoding="utf-8")
        self.assertIn("url: 'https://alyconr.github.io'", content)
        self.assertIn("baseUrl: '/Rapid-OS/'", content)
        self.assertIn("projectName: 'Rapid-OS'", content)
        self.assertIn("organizationName: 'alyconr'", content)

    def test_trailing_slash_configured(self):
        content = CONFIG_FILE.read_text(encoding="utf-8")
        self.assertIn("trailingSlash: false", content)

    def test_favicon_configured(self):
        content = CONFIG_FILE.read_text(encoding="utf-8")
        self.assertIn("favicon:", content)

    def test_seo_metadata_present(self):
        content = CONFIG_FILE.read_text(encoding="utf-8")
        self.assertIn("metadata:", content)
        self.assertIn("og:title", content)
        self.assertIn("twitter:card", content)

    def test_on_broken_links_throws(self):
        content = CONFIG_FILE.read_text(encoding="utf-8")
        self.assertIn("onBrokenLinks: 'throw'", content)


class TestDocumentationWorkflows(unittest.TestCase):
    """Verifies security, separation of concerns, and permissions of GitHub Actions workflows."""

    def test_docs_workflow_is_read_only(self):
        self.assertTrue(DOCS_WORKFLOW.exists(), "Missing docs.yml")
        content = DOCS_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions:", content)
        self.assertIn("contents: read", content)
        self.assertNotIn("pages: write", content)
        self.assertNotIn("id-token: write", content)

    def test_docs_workflow_runs_artifact_validation(self):
        content = DOCS_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tests.test_documentation_deployment.TestDocumentationStaticBuildIntegrity", content)

    def test_deploy_workflow_permissions_and_triggers(self):
        self.assertTrue(DEPLOY_WORKFLOW.exists(), "Missing docs-deploy.yml")
        content = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", content)
        # Ensure no automatic push trigger exists
        self.assertNotIn("push:", content, "Deployment workflow must never trigger automatically on push")
        self.assertNotIn("pull_request:", content, "Deployment workflow must never trigger on pull_request")
        self.assertNotIn("pull_request_target:", content, "Deployment workflow must never use pull_request_target")
        # Ensure build job restricted to main branch
        self.assertIn("github.ref == 'refs/heads/main'", content)
        # Ensure least-privilege job-level permissions
        self.assertIn("environment:\n      name: github-pages", content)

    def test_deploy_workflow_has_post_deploy_smoke_tests(self):
        content = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("smoke-test:", content)
        self.assertIn("needs: deploy", content)
        self.assertIn("tests.test_documentation_deployment.TestLiveDocsSmoke", content)

    def test_deploy_workflow_uses_official_actions(self):
        content = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("actions/checkout@v4", content)
        self.assertIn("actions/setup-node@v4", content)
        self.assertIn("actions/configure-pages@v5", content)
        self.assertIn("actions/upload-pages-artifact@v3", content)
        self.assertIn("actions/deploy-pages@v4", content)


class TestDocumentationOperationsRunbooks(unittest.TestCase):
    """Verifies that operational runbooks exist and are registered in sidebars."""

    def test_runbooks_exist(self):
        ops_dir = REPO_ROOT / "docs" / "operations"
        self.assertTrue((ops_dir / "documentation-deployment.md").exists())
        self.assertTrue((ops_dir / "documentation-rollback.md").exists())
        self.assertTrue((ops_dir / "documentation-maintenance.md").exists())

    def test_runbooks_registered_in_sidebar(self):
        content = SIDEBARS_FILE.read_text(encoding="utf-8")
        self.assertIn("operations/documentation-deployment", content)
        self.assertIn("operations/documentation-rollback", content)
        self.assertIn("operations/documentation-maintenance", content)

    def test_audit_sprint_5_exists_and_registered(self):
        audit_file = REPO_ROOT / "docs" / "audit" / "sprint-5-validation.md"
        self.assertTrue(audit_file.exists())
        sidebar_content = SIDEBARS_FILE.read_text(encoding="utf-8")
        self.assertIn("audit/sprint-5-validation", sidebar_content)


class TestDocumentationStaticBuildIntegrity(unittest.TestCase):
    """Verifies production static build integrity strictly without skipping."""

    def test_build_directory_exists(self):
        self.assertTrue(BUILD_DIR.exists(), f"Static build directory {BUILD_DIR} does not exist. Run 'npm run build' first.")
        self.assertTrue(BUILD_DIR.is_dir(), f"{BUILD_DIR} is not a directory.")

    def test_essential_static_files_exist(self):
        self.assertTrue(BUILD_DIR.exists(), "Build directory must exist to verify essential static files.")
        self.assertTrue((BUILD_DIR / "index.html").exists(), "Missing index.html")
        self.assertTrue((BUILD_DIR / "404.html").exists(), "Missing 404.html")
        self.assertTrue((BUILD_DIR / "sitemap.xml").exists(), "Missing sitemap.xml")

    def test_sitemap_contains_canonical_base_url(self):
        self.assertTrue(BUILD_DIR.exists(), "Build directory must exist to verify sitemap.")
        sitemap_content = (BUILD_DIR / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("https://alyconr.github.io/Rapid-OS/", sitemap_content)

    def test_no_localhost_in_index(self):
        self.assertTrue(BUILD_DIR.exists(), "Build directory must exist to verify index.html.")
        index_content = (BUILD_DIR / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("http://localhost", index_content)
        self.assertNotIn("file:///", index_content)


class TestLiveDocsSmoke(unittest.TestCase):
    """Optional live smoke tests executed when RAPID_OS_LIVE_DOCS_URL is provided."""

    def setUp(self):
        self.base_url = os.environ.get("RAPID_OS_LIVE_DOCS_URL")
        if not self.base_url:
            self.skipTest("Skipping live docs smoke tests: RAPID_OS_LIVE_DOCS_URL environment variable is not set.")
        self.base_url = self.base_url.rstrip("/")

    def _check_url(self, path: str, expected_status: int = 200) -> str:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "RAPID-OS-Smoke-Test/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                self.assertEqual(response.status, expected_status, f"Unexpected status for {url}")
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            if err.code == expected_status:
                return err.read().decode("utf-8")
            self.fail(f"HTTPError {err.code} when requesting {url} (expected {expected_status})")

    def test_live_homepage_accessible(self):
        body = self._check_url("/", expected_status=200)
        self.assertIn("Rapid OS", body)

    def test_live_cli_reference_accessible(self):
        body = self._check_url("/cli", expected_status=200)
        self.assertIn("CLI", body)

    def test_live_tutorials_accessible(self):
        body = self._check_url("/tutorials/", expected_status=200)
        self.assertIn("Laboratorios", body)

    def test_live_sitemap_accessible(self):
        body = self._check_url("/sitemap.xml", expected_status=200)
        self.assertIn("<urlset", body)

    def test_live_custom_404_page(self):
        body = self._check_url("/non-existent-smoke-test-page-404", expected_status=404)
        self.assertTrue("404" in body or "Page Not Found" in body)


if __name__ == "__main__":
    unittest.main()

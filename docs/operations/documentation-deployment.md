# Documentation Deployment Procedure

This runbook describes the formal, secure, and deterministic procedure to publish the **RAPID OS v3** documentation portal to GitHub Pages.

---

## 1. Scope and Governance

- **Portal:** Canonical RAPID OS v3.1.1 documentation.
- **Framework:** Docusaurus 3 with Node.js 20.
- **Hosting:** GitHub Pages (`alyconr.github.io/Rapid-OS/`).
- **Mechanism:** Decoupled deployment via GitHub Actions (`.github/workflows/docs-deploy.yml`).
- **Required approval:** Deploying to production requires explicit authorization from the repository owner.

---

## 2. Separation of Responsibilities

| Component | Workflow | Event | Permissions |
| :--- | :--- | :--- | :--- |
| **CI Validation** | `.github/workflows/docs.yml` | Pull Request and Push to `main` | `contents: read` |
| **Publication** | `.github/workflows/docs-deploy.yml` | `workflow_dispatch` only (manual) | `contents: read`, `pages: write`, `id-token: write` |

> **Publication is never automatic.** `docs-deploy.yml` is launched **by hand** from Actions; a merge to `main` does not publish the portal. After tagging a release, running it is a **mandatory step**: without it, the published portal keeps showing the previous version (see the [release checklist](../release-checklist.md)).

> **Security Note:** No Pull Request or fork has access to publish to GitHub Pages. Temporary OIDC tokens are only issued in the protected `github-pages` environment.

---

## 3. Technical Preconditions (Pre-flight Checklist)

Before authorizing or running a deployment, the team must verify:

1. **Unit and E2E Test Suite Green:**
   ```bash
   python -m unittest discover tests
   ```
2. **Docusaurus Typecheck and Build Successful:**
   ```bash
   cd website
   npm ci
   npm run typecheck
   npm run build
   ```
3. **Static Artifact Validation:**
   - Confirm that `website/build/index.html` exists.
   - Confirm that `website/build/404.html` exists.
   - Confirm that `website/build/sitemap.xml` contains URLs with the `/Rapid-OS/` prefix.
   - Verify there are no leaks of `localhost` or absolute development paths (`file:///`).
4. **Production Configuration in `website/docusaurus.config.ts`:**
   - `url: 'https://alyconr.github.io'`
   - `baseUrl: '/Rapid-OS/'`
   - `trailingSlash: false`
   - `onBrokenLinks: 'throw'`
5. **GitHub Pages Configuration in the Repository:**
   - Settings → Pages → Source: **GitHub Actions**.

---

## 4. Running the Controlled Manual Deployment (`workflow_dispatch`)

Deploying to production is strictly manual and requires the code to be on the `main` branch:

1. Navigate to **Actions** in the GitHub repository.
2. Select the **Deploy Documentation** workflow.
3. Click **Run workflow**.
4. Select the `main` branch.
5. Confirm the run.
6. The workflow will sequentially execute:
   - `build`: Compilation and static verification with `contents: read` permissions.
   - `deploy`: Deployment to GitHub Pages with `pages: write` and `id-token: write` permissions.
   - `smoke-test`: Automatic post-deployment validation through live HTTP tests.

---

## 5. Post-Deployment Verification (Smoke Testing)

Once the deployment workflow run has completed:

1. **Job Status in GitHub Actions:**
   - Verify that the `build` job and the `deploy` job finished with code 0.
   - Inspect the URL generated in the output of the `deploy` step.
2. **Production HTTP Smoke Test:**
   - Home access: `https://alyconr.github.io/Rapid-OS/` (HTTP 200).
   - CLI Reference access: `https://alyconr.github.io/Rapid-OS/cli` (HTTP 200).
   - Labs access: `https://alyconr.github.io/Rapid-OS/tutorials/` (HTTP 200).
   - Custom 404 page access: `https://alyconr.github.io/Rapid-OS/non-existent-page` (HTTP 404 with the Docusaurus layout).
   - `sitemap.xml` inspection: `https://alyconr.github.io/Rapid-OS/sitemap.xml` (HTTP 200).
3. **Running the Automated Smoke Tests:**
   ```bash
   RAPID_OS_LIVE_DOCS_URL=https://alyconr.github.io/Rapid-OS python -m unittest tests.test_documentation_deployment.TestLiveDocsSmoke
   ```

---

## 6. Logging and Notification

1. Note the deployed commit SHA in the release log.
2. Notify in the project channel that the documentation version is live.

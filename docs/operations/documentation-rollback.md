# Documentation Rollback Procedure

This runbook details the operational actions to follow when incidents are detected in the public documentation portal after a deployment.

---

## 1. Rollback Activation Criteria

A rollback procedure must be started if any of the following conditions occurs in the production environment:

- **P0 - Critical Breakage:** The home page (`/Rapid-OS/`) responds with an HTTP 5xx error or a persistent 404.
- **P0 - Navigation Blocked:** Global script failures (JavaScript runtime error) that prevent interacting with the navigation bar or sidebar.
- **P0 - Confidential Information Leak:** Accidental publication of credentials, secrets, internal endpoints or sensitive data in the documentation.
- **P1 - Severe Product Truth Misalignment:** Publication of wrong specifications that lead to destructive or defective behavior in the RAPID OS CLI.

---

## 2. Canonical Rollback Procedure (Controlled Git Revert)

To guarantee the immutability of Git history, authorship traceability and deterministic governance, the rollback is handled through an explicit revert in the repository:

### Step 1: Identify the Last Stable Commit

Review the history on the `main` branch or in the releases to determine the previous stable SHA:
```bash
git log --oneline -n 10
```
Assume the commit that introduced the failure is `BROKEN_COMMIT_SHA`.

### Step 2: Create a Hotfix / Revert Branch

```bash
git checkout main
git pull origin main
git checkout -b hotfix/revert-docs-incident
git revert --no-edit BROKEN_COMMIT_SHA
```

### Step 3: Local Pre-flight Validation

Run the mandatory checks to verify that the reverted tree is technically sound:
```bash
cd website
npm ci
npm run typecheck
npm run build
cd ..
python -m unittest tests.test_documentation_deployment.TestDocumentationStaticBuildIntegrity -v
```

### Step 4: Create, Review and Merge the Rollback PR

1. Push the hotfix branch:
   ```bash
   git push origin hotfix/revert-docs-incident
   ```
2. Create a Pull Request to `main` titled:
   `fix(rollback): revert commit <BROKEN_COMMIT_SHA> due to documentation incident`
3. After review and approval by the authorized reviewers and green CI verification (`docs.yml`), merge the PR into `main`.

### Step 5: Authorized Manual Deployment

Since `.github/workflows/docs-deploy.yml` does not publish automatically:

1. The authorized operator must go to the **Actions** tab in GitHub.
2. Select the **Deploy Documentation** workflow.
3. Click **Run workflow**, selecting the `main` branch (which already contains the revert).
4. The `build` job will compile the site, the `deploy` job will update GitHub Pages and the `smoke-test` job will automatically validate the live public routes.

---

## 3. Post-Rollback Verification

Once the authorized run of `.github/workflows/docs-deploy.yml` has finished:

1. **Automated Verification through Smoke Tests:**
   Run locally or verify the successful output of the `smoke-test` job:
   ```bash
   RAPID_OS_LIVE_DOCS_URL=https://alyconr.github.io/Rapid-OS python -m unittest tests.test_documentation_deployment.TestLiveDocsSmoke -v
   ```
   Critical routes checked with real assertions:
   - Homepage: HTTP 200 and presence of the title.
   - CLI Reference: HTTP 200 and presence of the CLI section.
   - Tutorials: HTTP 200 and presence of the labs index.
   - Sitemap: HTTP 200 and canonical XML format.
   - Nonexistent route: controlled HTTP 404 with the Docusaurus template.

2. **Manual Check:**
   Verify in a browser in incognito mode (clearing the browser cache) to confirm that the stable version is visible to end users.

---

## 4. Post-Mortem and Root Cause Analysis

Once the service is stabilized:

1. File a GitHub issue with the `incident-docs` label.
2. Document:
   - Root cause of the incident.
   - Why the pre-deployment tests did not detect the failure.
   - Preventive actions to add to the automated CI suite (`docs.yml` or unit tests).

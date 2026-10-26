---
title: Documentation Rollback Procedure
description: Operational runbook for rolling back the public documentation site after a deployment incident.
---

# Documentation Rollback Procedure

This runbook describes operational steps to take if an incident is found on the public documentation site after deployment.

## 1. Rollback criteria

Start a rollback if any of these conditions occur in production:

- **P0 - Critical outage:** The homepage (`/Rapid-OS/`) persistently returns HTTP 5xx or 404.
- **P0 - Navigation blocked:** Global script failures (JavaScript runtime errors) prevent use of the navbar or sidebar.
- **P0 - Confidential information exposed:** Credentials, secrets, internal endpoints, or sensitive data are accidentally published in the documentation.
- **P1 - Severe product-truth mismatch:** Published specifications could lead to destructive or faulty behavior in the Rapid OS CLI.

## 2. Canonical rollback procedure (controlled Git revert)

To preserve Git history, authorship traceability, and deterministic governance, rollbacks use an explicit repository revert.

### Step 1: Identify the last stable commit

Check the `main` branch history or releases to find the previous stable SHA:
```bash
git log --oneline -n 10
```
Assume the commit that introduced the issue is `BROKEN_COMMIT_SHA`.

### Step 2: Create a hotfix/revert branch

```bash
git checkout main
git pull origin main
git checkout -b hotfix/revert-docs-incident
git revert --no-edit BROKEN_COMMIT_SHA
```

### Step 3: Run local pre-flight validation

Run the required checks to verify that the reverted tree is technically sound:
```bash
cd website
npm ci
npm run typecheck
npm run build
cd ..
python -m unittest tests.test_documentation_deployment.TestDocumentationStaticBuildIntegrity -v
```

### Step 4: Create, review, and merge the rollback PR

1. Push the hotfix branch:
   ```bash
   git push origin hotfix/revert-docs-incident
   ```
2. Create a pull request to `main` titled `fix(rollback): revert commit <BROKEN_COMMIT_SHA> due to documentation incident`.
3. After authorized reviewers approve it and `docs.yml` CI is green, merge the PR into `main`.

### Step 5: Authorized manual deployment

Because `.github/workflows/docs-deploy.yml` does not publish automatically:

1. The authorized operator opens **Actions** in GitHub.
2. Selects **Deploy Documentation**.
3. Clicks **Run workflow**, selecting the `main` branch that contains the revert.
4. The `build` job builds the site, `deploy` updates GitHub Pages, and `smoke-test` checks the live public routes.

## 3. Post-rollback verification

After the authorized `.github/workflows/docs-deploy.yml` run:

1. **Automated smoke tests:** Run the test locally or confirm the `smoke-test` job succeeded:
   ```bash
   RAPID_OS_LIVE_DOCS_URL=https://alyconr.github.io/Rapid-OS python -m unittest tests.test_documentation_deployment.TestLiveDocsSmoke -v
   ```
   The test checks the homepage, CLI reference, tutorial index, sitemap XML, and a nonexistent route (controlled Docusaurus 404).
2. **Manual check:** Open the site in an incognito browser window (clearing browser cache) and confirm the stable version is visible to end users.

## 4. Post-mortem and root-cause analysis

After service is stable:

1. Create a GitHub issue with the `incident-docs` label.
2. Document the root cause, why pre-deployment checks missed the failure, and preventive actions for `docs.yml` CI or unit tests.

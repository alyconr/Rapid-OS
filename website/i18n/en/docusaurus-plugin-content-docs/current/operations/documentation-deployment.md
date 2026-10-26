---
title: Documentation Deployment Procedure
description: Formal, secure, deterministic runbook for publishing Rapid OS v3 documentation to GitHub Pages.
---

# Documentation Deployment Procedure

This runbook describes the formal, secure, deterministic process for publishing the **Rapid OS v3** documentation site to GitHub Pages.

## 1. Scope and governance

- **Site:** Canonical Rapid OS v3.1.1 documentation.
- **Framework:** Docusaurus 3 with Node.js 20.
- **Hosting:** GitHub Pages (`alyconr.github.io/Rapid-OS/`).
- **Mechanism:** Separate GitHub Actions deployment (`.github/workflows/docs-deploy.yml`).
- **Required approval:** Production deployment requires explicit repository-owner authorization.

## 2. Separation of responsibilities

| Component | Workflow | Event | Permissions |
|---|---|---|---|
| **CI validation** | `.github/workflows/docs.yml` | Pull request and push to `main` | `contents: read` |
| **Publishing** | `.github/workflows/docs-deploy.yml` | Manual `workflow_dispatch` only | `contents: read`, `pages: write`, `id-token: write` |

> **Publishing is never automatic.** Run `docs-deploy.yml` manually from Actions; merging into `main` does not publish the site. After tagging a release, running it is a **required step**; otherwise the published site still shows the previous version (see the [release checklist](../release-checklist.md)).

> **Security note:** Pull requests and forks cannot publish to GitHub Pages. Temporary OIDC tokens are issued only in the protected `github-pages` environment.

## 3. Technical preflight checklist

Before authorizing or running a deployment, verify:

1. **Unit and E2E tests pass:**
   ```bash
   python -m unittest discover tests
   ```
2. **Docusaurus typecheck and build succeed:**
   ```bash
   cd website
   npm ci
   npm run typecheck
   npm run build
   ```
3. **Static artifacts are valid:** `website/build/index.html`, `404.html`, and `sitemap.xml` exist; sitemap URLs include `/Rapid-OS/`; no `localhost` or development `file:///` paths are leaked.
4. **Production configuration** in `website/docusaurus.config.ts` has `url: 'https://alyconr.github.io'`, `baseUrl: '/Rapid-OS/'`, `trailingSlash: false`, and `onBrokenLinks: 'throw'`.
5. **GitHub Pages** is configured in repository Settings → Pages → Source: **GitHub Actions**.

## 4. Controlled manual deployment (`workflow_dispatch`)

Production deployment is strictly manual and requires the code to be on `main`:

1. Open **Actions** in the GitHub repository.
2. Select **Deploy Documentation**.
3. Click **Run workflow**.
4. Select the `main` branch.
5. Confirm the run.
6. The workflow runs sequentially:
   - `build`: Build and static verification with `contents: read`.
   - `deploy`: Publish to GitHub Pages with `pages: write` and `id-token: write`.
   - `smoke-test`: Run live HTTP checks after deployment.

## 5. Post-deployment verification (smoke testing)

After the deployment workflow completes:

1. **Check GitHub Actions job status:** Verify `build` and `deploy` exited with code 0, and inspect the generated URL in the `deploy` step output.
2. **Check production URLs:** Homepage, CLI reference, labs, custom 404 page, and `sitemap.xml` should respond with the expected status (200, except the missing page, which should return 404 with the Docusaurus layout).
3. **Run automated smoke tests:**
   ```bash
   RAPID_OS_LIVE_DOCS_URL=https://alyconr.github.io/Rapid-OS python -m unittest tests.test_documentation_deployment.TestLiveDocsSmoke
   ```

## 6. Record and notify

1. Record the deployed commit SHA in the release log.
2. Notify the project channel that the documentation version is live.

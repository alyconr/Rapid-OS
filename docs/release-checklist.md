# Rapid OS v3.1.0 Release Checklist

This checklist documents the exact verification and release procedure for cutting the `v3.1.0` release once the release-readiness Pull Request is merged into `main`.

---

## 1. Mandatory Pre-Tag Verification Gates on `main`

All of the following gates MUST be checked before creating tag `v3.1.0`:

- [ ] `python -m build` succeeds
- [ ] wheel exists (`dist/rapid_os-3.1.0-py3-none-any.whl`)
- [ ] sdist exists (`dist/rapid_os-3.1.0.tar.gz`)
- [ ] clean wheel installation succeeds outside repository checkout
- [ ] declared Python versions (`3.10`, `3.11`, `3.12`, `3.13`) are green in CI
- [ ] stable installer resolves exact `v3.1.0` tag (`install.sh` and `install.ps1`)
- [ ] stable installation docs do not track `main`

### Step-by-Step Verification Commands

1. Checkout `main` and pull the merged release-readiness commit:
   ```bash
   git checkout main
   git pull --ff-only origin main
   git status
   ```
2. Verify clean working tree (`nothing to commit, working tree clean`).
3. Verify version output:
   ```bash
   python rapid.py --version
   # Expected: Rapid OS 3.1.0
   ```
4. Verify bytecode compilation and full test suite:
   ```bash
   python -m compileall -q rapid.py rapid_os tests
   python -m unittest discover -v
   ```
5. Build distribution artifacts (`wheel` + `sdist`) and verify both exist:
   ```bash
   python -m pip install --upgrade pip build
   python -m build
   test -f dist/rapid_os-3.1.0-py3-none-any.whl
   test -f dist/rapid_os-3.1.0.tar.gz
   ```
6. Verify clean wheel installation in an isolated virtual environment outside the checkout:
   ```bash
   python -m venv /tmp/rapid-wheel-check
   /tmp/rapid-wheel-check/bin/pip install dist/rapid_os-3.1.0-py3-none-any.whl
   (cd /tmp && /tmp/rapid-wheel-check/bin/rapid --version)
   (cd /tmp && /tmp/rapid-wheel-check/bin/rapid --help)
   (cd /tmp && /tmp/rapid-wheel-check/bin/rapid guide)
   (cd /tmp && /tmp/rapid-wheel-check/bin/rapid doctor)
   ```
7. Smoke test with the wheel installed outside the checkout, in a temporary git project:
   ```bash
   python -m venv /tmp/rapid-smoke-venv
   /tmp/rapid-smoke-venv/bin/pip install dist/rapid_os-3.1.0-py3-none-any.whl
   mkdir /tmp/rapid-smoke && cd /tmp/rapid-smoke && git init -q
   echo "print('hello')" > app.py
   /tmp/rapid-smoke-venv/bin/rapid init --yes --test-command "python -m unittest discover"
   /tmp/rapid-smoke-venv/bin/rapid shortcuts install --harness claude --dry-run --json
   # Expected: 8 files, no RAPID1315 in "warnings"
   echo '{"title":"Smoke","business_objective":"Smoke test","problem_statement":"None","acceptance_criteria":["It runs"],"tasks":["T001: Smoke task"]}' \
     | /tmp/rapid-smoke-venv/bin/rapid start feature --spec-file - --json
   # Expected: exit code 0
   ```
8. Confirm GitHub Actions CI (`Tests` workflow across Python `3.10`, `3.11`, `3.12`, and `3.13`) is green on `main`.

---

## 2. Tagging `v3.1.0`

Once `main` is verified and green:

```bash
git checkout main
git pull --ff-only origin main
git tag -a v3.1.0 -m "Rapid OS v3.1.0"
git push origin v3.1.0
```

---

## 3. Publishing the GitHub Release

Create the GitHub Release for tag `v3.1.0` using `docs/release-v3.1.0.md`:

```bash
gh release create v3.1.0 \
  --title "Rapid OS v3.1.0" \
  --notes-file docs/release-v3.1.0.md
```

---

## 4. Publishing the documentation portal (mandatory after the tag)

The portal is **not** published automatically: `.github/workflows/docs-deploy.yml` only runs on `workflow_dispatch`, so merging to `main` or pushing the tag does not update https://alyconr.github.io/Rapid-OS/. After tagging, a person must run it:

```bash
gh workflow run docs-deploy.yml --ref main
gh run list --workflow docs-deploy.yml --limit 1
```

- [ ] `Deploy Documentation` finished with `build`, `deploy` and `smoke-test` green
- [ ] the live portal shows the new release page (see [documentation deployment](./operations/documentation-deployment.md))

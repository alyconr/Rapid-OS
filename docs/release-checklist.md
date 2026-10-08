# Rapid OS v3.0.0 Release Checklist

This checklist documents the exact verification and release procedure for cutting the `v3.0.0` release once the release-readiness Pull Request is merged into `main`.

---

## 1. Pre-Tag Verification on `main`

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
   # Expected: Rapid OS 3.0.0
   ```
4. Verify bytecode compilation:
   ```bash
   python -m compileall -q rapid.py rapid_os tests
   ```
5. Run the complete unit and E2E test suite:
   ```bash
   python -m unittest discover -v
   ```
6. Run project validation and diagnostics:
   ```bash
   python rapid.py doctor
   python rapid.py validate
   ```
7. Verify clean virtual environment installation and `rapid` console script:
   ```bash
   python -m venv /tmp/rapid-release-check
   /tmp/rapid-release-check/bin/pip install .
   /tmp/rapid-release-check/bin/rapid --version
   /tmp/rapid-release-check/bin/rapid guide
   ```
8. Confirm GitHub Actions CI (`Tests` workflow on Python 3.10 and Python 3.12) is green on `main`.

---

## 2. Tagging `v3.0.0`

Once `main` is verified and green:

```bash
git checkout main
git pull --ff-only origin main
git tag -a v3.0.0 -m "Rapid OS v3.0.0"
git push origin v3.0.0
```

---

## 3. Publishing the GitHub Release

Create the GitHub Release for tag `v3.0.0` using `docs/release-v3.0.0.md`:

```bash
gh release create v3.0.0 \
  --title "Rapid OS v3.0.0" \
  --notes-file docs/release-v3.0.0.md
```

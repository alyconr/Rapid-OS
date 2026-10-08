# Rapid OS v3.0.0 Release Checklist

This checklist documents the exact verification and release procedure for cutting the `v3.0.0` release once the release-readiness Pull Request is merged into `main`.

---

## 1. Mandatory Pre-Tag Verification Gates on `main`

All of the following gates MUST be checked before creating tag `v3.0.0`:

- [ ] `python -m build` succeeds
- [ ] wheel exists (`dist/rapid_os-3.0.0-py3-none-any.whl`)
- [ ] sdist exists (`dist/rapid_os-3.0.0.tar.gz`)
- [ ] clean wheel installation succeeds outside repository checkout
- [ ] declared Python versions (`3.10`, `3.11`, `3.12`, `3.13`) are green in CI
- [ ] stable installer resolves exact `v3.0.0` tag (`install.sh` and `install.ps1`)
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
   # Expected: Rapid OS 3.0.0
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
   test -f dist/rapid_os-3.0.0-py3-none-any.whl
   test -f dist/rapid_os-3.0.0.tar.gz
   ```
6. Verify clean wheel installation in an isolated virtual environment outside the checkout:
   ```bash
   python -m venv /tmp/rapid-wheel-check
   /tmp/rapid-wheel-check/bin/pip install dist/rapid_os-3.0.0-py3-none-any.whl
   (cd /tmp && /tmp/rapid-wheel-check/bin/rapid --version)
   (cd /tmp && /tmp/rapid-wheel-check/bin/rapid --help)
   (cd /tmp && /tmp/rapid-wheel-check/bin/rapid guide)
   (cd /tmp && /tmp/rapid-wheel-check/bin/rapid doctor)
   ```
7. Confirm GitHub Actions CI (`Tests` workflow across Python `3.10`, `3.11`, `3.12`, and `3.13`) is green on `main`.

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


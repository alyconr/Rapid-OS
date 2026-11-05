# Contributing to Rapid OS

Thanks for helping. This page covers what you need to get a pull request merged. By taking part you accept the [Code of Conduct](CODE_OF_CONDUCT.md). To report a vulnerability, follow [SECURITY.md](SECURITY.md) instead of opening an issue.

## Development environment

You need Python 3.10 or newer, Git, and Node.js 20 if you touch the documentation site. Node.js and Go are also used by some end-to-end tests.

```bash
git clone https://github.com/alyconr/Rapid-OS.git
cd Rapid-OS
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
rapid --version
```

Rapid OS has no runtime dependencies (`dependencies = []` in `pyproject.toml`): the product code uses the standard library only. Keep it that way.

Create your branch from `main`.

## Tests

**Run the full suite locally before opening a pull request:**

```bash
python -m unittest discover      # the whole suite, serially
python scripts/test.py --all     # the same suite, in parallel
```

Do not rely on CI for this. Since [#107](https://github.com/alyconr/Rapid-OS/pull/107), a pull request runs only the fast suite on Python 3.12. The full suite on Python 3.10 to 3.13 runs after the merge to `main`, on `v*` tags, or by hand with `gh workflow run tests.yml --ref <branch>`. `python scripts/test.py` runs the fast suite, and `python scripts/test.py test_hooks` runs only the modules you name.

Write tests along with the change. If a test module starts driving the CLI end to end, add it to `SLOW_MODULES` in `scripts/test.py`.

### Goldens

The generated shortcuts are compared with `tests/golden/shortcuts/`. After an intentional change to `templates/shortcuts/`, regenerate them and review the diff:

```bash
RAPID_UPDATE_GOLDEN=1 python -m unittest tests.test_shortcuts
```

In PowerShell: `$env:RAPID_UPDATE_GOLDEN = "1"; python -m unittest tests.test_shortcuts`.

## Documentation

- A change in behavior carries its documentation in the same pull request.
- The English documentation lives in `docs/`, and its Spanish translation in `website/i18n/es/docusaurus-plugin-content-docs/current/`, at the same relative path. Update both, and write the Spanish with its accents (tildes).
- Document only what you can verify in the code, the parser or the tests. See [Maintaining the Documentation](docs/contributing/documentation.md).
- New commands and flags go in `docs/cli.md`, new `RAPIDxxxx` codes in `docs/troubleshooting/diagnostics.md`, and new pages in `website/sidebars.ts`.
- Check the site if you touched it: `cd website && npm ci && npm run build`. A broken link fails the build.

## Changelog

Add your change to the `[Unreleased]` section of `CHANGELOG.md`. Version numbers and released sections change only in the version pull request.

## Rapid OS invariants

These are the promises the product makes. A change that weakens one of them will not be merged, however useful it is. The full list is in [Product Limits and Boundaries](docs/concepts/product-boundaries.md).

- **It never records evidence of something it did not run.** Test gates count only evidence produced by `rapid check`; `rapid evidence add` refuses the producers reserved to Rapid OS (`rapid:*`).
- **The person approves.** Human gates move only with `rapid approve`, run by a person in their own terminal. Rapid OS, a shortcut, a hook or a harness never approves, waives or rejects one.
- **It never confirms on the person's behalf.** A document drafted by the agent stays a draft until `rapid setup doc <id> --confirm`.
- **It does not commit.** `rapid finish` leaves the commit to the person, except for `--merge` with their written confirmation.
- **Plumbing runs nothing from the repository.** The porcelain runs only `test_command`, the argv of `rapid check`, and the git commands it documents.
- **Evaluation is deterministic.** No LLM acts as a judge; Rapid OS does not launch agents or call model APIs.
- **Records are immutable and append-only.** Spec revisions, contracts, evidence and evaluation reports are not rewritten, and reports written with older rulesets still replay under their own rules.
- **Limits are stated.** When something is best-effort or is not guaranteed, the documentation says so.
- **Existing commands keep working.** Do not break existing commands, generated file locations or digests without a migration path.

## Pull requests

Keep each pull request to one purpose, with few commits, and fill in the [template](.github/PULL_REQUEST_TEMPLATE.md).

Workflow actions are pinned to a full commit SHA with a `# vX.Y.Z` comment, and `tests/test_release_hygiene.py` enforces it. Dependabot keeps the pins current.

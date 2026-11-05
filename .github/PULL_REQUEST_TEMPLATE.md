## What and why

<!-- What changes, and what problem it solves. Link the issue if there is one. -->

## Verification

<!-- The commands you ran and what they printed. -->

## Checklist

- [ ] Full suite green locally: `python -m unittest discover` or `python scripts/test.py --all` (CI on a pull request runs only the fast suite)
- [ ] Docs updated in English (`docs/`) and Spanish (`website/i18n/es/docusaurus-plugin-content-docs/current/`), or not needed
- [ ] `cd website && npm run build` passes, if the docs or the site changed
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Goldens regenerated with `RAPID_UPDATE_GOLDEN=1` and the diff reviewed, if a shortcut template changed
- [ ] Rapid OS invariants respected (see `CONTRIBUTING.md`): it never records evidence of something it did not run, the person approves, it does not confirm or commit on the person's behalf

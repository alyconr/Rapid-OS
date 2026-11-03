# Project written before hardening findings

A real `.rapid-os/` written by Rapid OS at main `5f1a0d89` (before #104 added `findings` to specs): one ready
spec per mode (`legacy-feature`, `legacy-bugfix`, `legacy-refactor`, `legacy-hardening`, `legacy-research`),
whose `revision.json` has no `findings` key and a `content_digest` computed without it, and a finished
hardening run (`legacy-hardening-r1-run-001`) with its evaluation report (ruleset 2). Do not regenerate it with
a newer Rapid OS: `tests/test_legacy_specs.py` checks that a project upgraded from 3.1 or 3.2.0rc1 still reads.

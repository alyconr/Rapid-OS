---
title: RAPIDxxx Diagnostics Catalog
description: Reference for Rapid OS diagnostic codes, common causes, and remediation.
---

# RAPIDxxx Diagnostics Catalog

`rapid validate`, `rapid scan`, and governance commands emit deterministic diagnostics with unique codes. Use the message and the guidance below to resolve them.

## Project configuration and templates (`RAPID100–RAPID110`)

| Code | Severity | Cause | Remediation |
| --- | --- | --- | --- |
| `RAPID100` | INFO | Valid project configuration loaded. | Informational. |
| `RAPID101` | ERROR | `.rapid-os/config.json` missing. | Run `rapid init`. |
| `RAPID102` | ERROR | Invalid JSON syntax. | Fix the JSON or restore its `.bak` backup. |
| `RAPID103` | ERROR | Unsupported or invalid schema version. | Use a supported `schema_version`. |
| `RAPID104` | ERROR | Required configuration fields missing. | Regenerate with `rapid init`. |
| `RAPID105` | ERROR | Required stack or topology templates missing. | Reinstall Rapid OS or restore `templates/`. |
| `RAPID106` | ERROR | Template is not valid UTF-8. | Save as UTF-8 or restore the original. |
| `RAPID107` | ERROR | Template could not be read. | Check permissions or reinstall. |
| `RAPID108` | WARNING | Empty template. | Restore or remove it. |
| `RAPID109` | ERROR | Invalid JSON template. | Fix the reported syntax or restore it. |
| `RAPID110` | WARNING | Unresolved template placeholders. | Replace placeholders if you edited templates. |

## Project Intelligence (`RAPID600–RAPID604`)

| Code | Severity | Cause | Remediation |
| --- | --- | --- | --- |
| `RAPID600` | INFO | Valid `.rapid-os/project.json` snapshot. | Informational. |
| `RAPID601` | ERROR | Corrupt JSON. | Regenerate with `rapid scan --write`. |
| `RAPID602` | ERROR | Insufficient read permissions. | Adjust file permissions. |
| `RAPID603` | ERROR | Unsupported snapshot schema. | Regenerate with `rapid scan --write`. |
| `RAPID604` | ERROR | Corrupt `ProjectFact` or evidence. | Regenerate the snapshot. |

## Context Compiler (`RAPID700–RAPID705`)

| Code | Severity | Cause | Remediation |
| --- | --- | --- | --- |
| `RAPID700` | INFO | Context compilation succeeded. | Informational. |
| `RAPID701` | ERROR | Required context source missing. | Check or initialize `.rapid-os/standards/`. |
| `RAPID702` | ERROR | Required sources exceed token/character budget. | Increase `--max-chars <n>` or reduce required sources in config. |
| `RAPID703` | WARNING | Selected context sources conflict. | Inspect `rapid context --manifest` and resolve contradictions. |
| `RAPID704` | ERROR | Invalid snapshot or compiler source. | Run `rapid scan --write` and check file integrity. |

For other diagnostic families, consult the matching CLI command and its emitted code; remediation should follow the precise cause in that command's report.

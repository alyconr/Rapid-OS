---
title: Project Documents and Provenance
description: How onboarding documents reach the agent with visible provenance, whether confirmed, assumed, or skipped.
---

# Project Documents and Provenance

Onboarding can produce up to four documents: a brief, business rules, data model, and architecture. Rapid OS distinguishes what a person wrote, what an agent drafted, and what was skipped; the agent receives each item **marked for what it is**.

> Rapid OS never marks something confirmed unless a person confirmed it.

## Which documents count

| Document | File | Context source |
|---|---|---|
| `brief` | `docs/PRODUCT_BRIEF.md` | `doc.brief` |
| `business` | `docs/BUSINESS_RULES.md` | `doc.business` |
| `data-model` | `docs/DATA_MODEL.md` | `doc.data-model` |
| `architecture` | `docs/ARCHITECTURE.md` | `doc.architecture` |

A file counts only if its frontmatter includes `rapid-doc: <id>` and `source: provided` or `source: drafted`. A manually written `docs/README.md` or `docs/ARCHITECTURE.md` without that frontmatter is not included in context. Frontmatter is never injected; the agent sees only the body.

```markdown
---
rapid-doc: brief
source: drafted
status: draft
sha256: <body hash>
---
## Problem
...
```

## Three provenance states

| State | How it is identified | What the agent sees |
|---|---|---|
| Confirmed | `source: provided`, or `source: drafted` with `status: confirmed` | The body without a banner; it is a rule. |
| Assumed | `source: drafted` with `status: draft` | The body under a note that the agent drafted it and the person has not confirmed it. |
| Skipped | `docs.<id>.status` is `skipped` in `.rapid-os/setup.json` | A single line: `<title>: not defined. Ask; do not invent.` |

The same rule applies in `rapid context` and agent files (`CLAUDE.md`, `.cursorrules`, and others). A draft remains an assumption until a person explicitly confirms it.

## How documents are written

Rapid OS, not the agent, writes the documents. The agent sends only the **body**; `rapid setup doc` adds frontmatter, calculates a SHA-256 hash of the body, and saves a `.bak` copy of the previous file.

```bash
# Agent draft: status remains draft until a person confirms it.
printf '%s' "$BODY" | rapid setup doc business --source drafted --file -
# Person-provided content: stored as-is with status confirmed.
rapid setup doc business --source provided --file notes.md
# Person reviewed a draft: only the status changes, not the body.
rapid setup doc business --confirm
```

- A draft (`drafted`) must contain every required section and fit within `max_chars`; otherwise, `rapid setup doc` rejects it with `RAPID1403`/`RAPID1404` (exit 1, nothing written). Person-provided content is not validated.
- A draft cannot replace a person-provided or manually written document without `--replace` (`RAPID1405`).
- `--skip` and `--reopen` record that a document is not needed or return it to pending. `--confirm` and `--reopen` also regenerate `CLAUDE.md`, `.cursorrules`, and other agent files when project standards exist.
- Import a legacy `standards/business.md` with `rapid setup doc business --from-legacy` (as `provided`; the original is not deleted).
- `rapid init` follows the same logic: each document can be imported, entered in the terminal, left pending for the agent (`/rapid-init`), or skipped. With `--yes`, they remain pending.

## Confirm or leave as an assumption

Before onboarding closes, Rapid OS does not accept agent drafts as fact. After all documents are resolved and before `finish`, `rapid setup next` returns `review_drafts` listing unconfirmed drafts. The person decides **for each document**:

| Decision | Result |
|---|---|
| **Confirm** (`rapid setup doc <id> --confirm`) | Becomes a project rule the agent follows in each run without questioning. Reopen it with `rapid setup doc <id> --reopen`. |
| **Leave as an assumption** (do not confirm) | Agent sees a warning, may question it, and each run reminds you it is unconfirmed (`RAPID1408`). Confirm later with `rapid setup doc <id> --confirm`. |

The agent summarizes each draft and asks about it. Run `--confirm` only for drafts you explicitly confirm, never based on a generic "ok" or "continue." To change a draft, rewrite it with `rapid setup doc <id> --source drafted --replace` and ask again. `rapid setup review --done` closes the review; unconfirmed documents remain drafts. Confirming a document does not close the review. If a new draft appears after review (the agent rewrites one, or you reopen it), review becomes pending again until `rapid setup review --done`. A completed onboarding does not reopen.

## Coexistence with `standards/business.md`

If both `standards/business.md` and `doc.business` exist, `doc.business` takes precedence. The `rapid context` manifest lists `standard.business` as skipped with reason `superseded by doc.business`; `rapid validate` reports `RAPID1410` if their bodies differ (compared without frontmatter and with whitespace normalized). If only `standards/business.md` exists, nothing changes. If the business document was skipped but the standard exists, the standard still supplies business rules and Rapid OS does not add the "ask; do not invent" line.

## `rapid validate` checks

| Code | Level | Condition |
|---|---|---|
| `RAPID1400` | INFO | `.rapid-os/setup.json` exists and is valid. |
| `RAPID1406` | ERROR | `.rapid-os/setup.json` exists and is invalid. |
| `RAPID1408` | WARNING | An agent-drafted document is unconfirmed (one per document). |
| `RAPID1403` | WARNING | A draft is missing a required `##` section; `rapid setup doc` rejects it instead. |
| `RAPID1404` | WARNING | A draft exceeds its `max_chars`; `rapid setup doc` rejects it instead. |
| `RAPID1410` | WARNING | `standards/business.md` differs from `docs/BUSINESS_RULES.md`. |

`RAPID1403` and `RAPID1404` are evaluated only for drafted documents; person-provided content is not validated. See [Diagnostics](../troubleshooting/diagnostics.md).

## The only later edit: marking a story complete

Rapid OS does not edit the brief again except in a narrow case. When `rapid finish` returns PASS and the run spec has a `story:<ID>` tag (for example, `story:H001`), it changes only the matching unchecked line in `## Stories` (or its alias) from `- [ ] H001:` to `- [x] H001:`. Before editing, it copies the brief to `.rapid-os/backups/`, updates the frontmatter hash, and regenerates agent files. `source` and `status` do not change, so a draft remains an assumption. A brief without `rapid-doc` frontmatter, an already completed or nonexistent story, any verdict other than PASS, or `rapid finish --no-tick` leaves the brief unchanged.

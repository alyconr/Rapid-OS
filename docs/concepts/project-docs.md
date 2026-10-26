---
title: Project documents and their provenance
description: How onboarding documents reach the agent with their provenance visible, whether confirmed, assumed or skipped.
---

# Project documents and their provenance

Onboarding produces up to four documents (brief, business rules, data model and architecture). Rapid OS does not treat what a person wrote, what the agent drafted and what was skipped the same way: the agent receives each thing **marked as what it is**.

> Rapid OS never marks as confirmed what the person did not confirm.

## Which document counts

| Document | File | Context source |
| :--- | :--- | :--- |
| `brief` | `docs/PRODUCT_BRIEF.md` | `doc.brief` |
| `business` | `docs/BUSINESS_RULES.md` | `doc.business` |
| `data-model` | `docs/DATA_MODEL.md` | `doc.data-model` |
| `architecture` | `docs/ARCHITECTURE.md` | `doc.architecture` |

A file counts only if its frontmatter includes `rapid-doc: <id>` and `source: provided` or `source: drafted`. A hand-written `docs/README.md` or `docs/ARCHITECTURE.md` without that frontmatter does not enter the context. The frontmatter is never injected: the agent sees only the body.

```markdown
---
rapid-doc: brief
source: drafted
status: draft
sha256: <hash of the body>
---
## Problem
...
```

## Three provenance states

| State | How it is recognized | What the agent sees |
| :--- | :--- | :--- |
| Confirmed | `source: provided`, or `source: drafted` with `status: confirmed` | The body, without a banner: it is a rule. |
| Assumed | `source: drafted` with `status: draft` | The body under the line `> Assumptions drafted by the agent, not confirmed by the person.` |
| Skipped | `docs.<id>.status` is `skipped` in `.rapid-os/setup.json` | A single line: `<title>: undefined. Ask, do not invent.` |

The same rule applies in `rapid context` and in the agent files (`CLAUDE.md`, `.cursorrules`, ...). A draft stops being an assumption only when a person explicitly confirms it.

## How they are written

The documents are written by Rapid OS, not by the agent: the agent sends only the **body** and `rapid setup doc` adds the frontmatter, computes the body's `sha256` and saves a `.bak` of the previous file.

```bash
# Drafted by the agent: status: draft until a person confirms it.
printf '%s' "$BODY" | rapid setup doc business --source drafted --file -
# Provided by the person: saved as is, status: confirmed.
rapid setup doc business --source provided --file notes.md
# The person reviewed the draft: only the status changes, the body is untouched.
rapid setup doc business --confirm
```

- A draft (`drafted`) must include all required sections and fit within `max_chars`; otherwise `rapid setup doc` rejects it with `RAPID1403`/`RAPID1404` (exit 1, nothing is written). What the person provides (`provided`) is not validated.
- A draft does not replace a document provided by a person (or a hand-written file) without `--replace` (`RAPID1405`).
- `--skip` and `--reopen` record that a document is not needed, or return it to pending; `--confirm` and `--reopen` also regenerate `CLAUDE.md`, `.cursorrules`, ... when the project already has standards.
- A previous project with `standards/business.md` imports it with `rapid setup doc business --from-legacy` (as `provided`; the original is not deleted).
- `rapid init` uses the same logic: each document is imported, written in the terminal, left pending for the agent (`/rapid-init`) or skipped. With `--yes` they are left pending.

## Confirm or leave as an assumption

Before closing onboarding, Rapid OS does not take the agent's drafts as good: `rapid setup next` returns `review_drafts` (after resolving all documents and before `finish`) with the list of unconfirmed drafts, and the person decides **document by document**. Each option has a different consequence:

| Decision | What happens |
| :--- | :--- |
| **Confirm** (`rapid setup doc <id> --confirm`) | It becomes a project rule: the agent follows it in every run without questioning it. You can return it to draft with `rapid setup doc <id> --reopen`. |
| **Leave as an assumption** (do not confirm) | The agent receives it under the notice "Assumptions drafted by the agent, not confirmed by the person", may question it and ask you, and each run reminds you that it is unconfirmed (`RAPID1408`). You confirm it whenever you want with `rapid setup doc <id> --confirm`. |

The agent summarizes each draft for you in a few lines and asks you about each one; it runs `--confirm` only for those you explicitly confirm, never from a generic "ok" or "continue". If you want to change something first, rewrite the draft (`rapid setup doc <id> --source drafted --replace`) and ask again. When you are done, `rapid setup review --done` closes the review: what you did not confirm stays as a draft. Confirming a document does not close the review (you can confirm several and then close it; if you confirm them all, `rapid setup review --done` finishes successfully without changing anything and the next step is `finish`), and `rapid setup finish` with the review pending fails with `RAPID1407` and tells you the next command.

If a new draft appears after the review is closed (the agent rewrites one, or you return one to draft with `--reopen`), the review becomes pending again until the next `rapid setup review --done`. An onboarding that is already finished is not reopened.

## Coexistence with `standards/business.md`

If both `standards/business.md` and `doc.business` exist, `doc.business` wins: the `rapid context` manifest lists `standard.business` as skipped with the reason `superseded by doc.business`, and `rapid validate` warns with `RAPID1410` when the bodies differ (they are compared without frontmatter and with whitespace normalized). If only `standards/business.md` exists, nothing changes. If the business document was skipped but `standards/business.md` exists, the standard keeps speaking for the business and the "ask, do not invent" line is not added.

## What `rapid validate` checks

| Code | Level | When |
| :--- | :--- | :--- |
| `RAPID1400` | INFO | `.rapid-os/setup.json` exists and is valid. |
| `RAPID1406` | ERROR | `.rapid-os/setup.json` exists and is not valid. |
| `RAPID1408` | WARNING | A document drafted by the agent is still unconfirmed (one per document). |
| `RAPID1403` | WARNING | A document drafted by the agent lacks a required section (a `## ` heading with any of its titles, case-insensitive). In `rapid setup doc` it is a rejection, not a warning. |
| `RAPID1404` | WARNING | A document drafted by the agent exceeds `max_chars` of its bank. In `rapid setup doc` it is a rejection, not a warning. |
| `RAPID1410` | WARNING | `standards/business.md` and `docs/BUSINESS_RULES.md` differ. |

`RAPID1403` and `RAPID1404` are only evaluated on `drafted` documents: what the person pasted is not validated. Details in [Diagnostics](../troubleshooting/diagnostics.md).

## The only later edit: ticking off a story

Rapid OS does not edit the brief again, with one narrow exception: when `rapid finish` ends in PASS and the run's spec carries the tag `story:<ID>` (for example `story:H001`), it changes, in the `## Stories` section (or its alias), only the line `- [ ] H001:` to `- [x] H001:`. Beforehand it copies the brief to `.rapid-os/backups/`, updates the frontmatter's `sha256` and regenerates the agent files; `source` and `status` do not change, so a draft is still a draft and still enters the context as an assumption. A brief without `rapid-doc` frontmatter, a story already ticked or nonexistent, a verdict other than PASS and `rapid finish --no-tick` change nothing.

---
title: What the agent knows about your project
description: Where the agent gets your project's rules from (documents, standards, spec), what happens to drafts, and how to change them; compiling by hand with rapid context remains an advanced mode.
---

# What the agent knows about your project

An agent without context improvises: it invents business rules, mixes architecture styles, and forgets earlier decisions. Rapid OS gives it, on every job, only what it needs to know.

## With shortcuts

You don't have to do anything: the agent receives the context on every job. It comes from three places:

| What | Where it comes from | Where it lives |
| :--- | :--- | :--- |
| **Project documents**: brief, business rules, data model, architecture | You decided them in `/rapid-init` (pasted, drafted by the agent, or skipped) | `docs/` |
| **Standards**: stack, architecture, security, code style | Rapid OS generates them from your onboarding decisions | `.rapid-os/standards/` and your agent's file (`CLAUDE.md`, `AGENTS.md`…) |
| **The current job's spec** | The agent drafts it from your request | `.rapid-os/specs/` |

### Drafts and confirmed documents

What you **confirmed** the agent treats as a project rule and follows without arguing. What remained a **draft** (the agent drafted it and you did not confirm it) it treats as an assumption: it can question it and ask you, and every job reminds you of it. To confirm a draft later:

```bash
rapid setup doc business --confirm
```

Replace `business` with `brief`, `data-model`, or `architecture`.

### Changing a document

The documents in `docs/` are written by Rapid OS (`rapid setup doc`); they are not edited by hand. If you skipped one and now want it, reopen it:

```bash
rapid setup doc business --reopen
```

Then type `/rapid-init` in the agent: it offers it to you again so you can paste it, draft it, or skip it. To replace a document that already has content, see [Project documents](../concepts/project-docs.md).

<details>
<summary>What the agent does under the hood</summary>

When you run `rapid start <mode> --spec-file -`, Rapid OS creates the run's contract with the spec and the project's standards, and the shortcut tells the agent to work only on the task returned by `rapid next --json` (`implement_task`). To see exactly what context a harness would receive (for example, to debug a response or for CI), use `rapid context`, described in the advanced mode.

</details>

## Advanced mode

You don't need it with shortcuts. It explains the context compiler (`rapid context`): budget, relevance, manifest, and provenance, useful for debugging and for CI.

<details>
<summary>See the context compiler</summary>

---

## Why not dump the whole repository

```mermaid
flowchart LR
    subgraph Without Rapid OS
        A[Entire Repository] -->|Massive unfiltered dump| B[AI Agent]
        B --> C[Noise, hallucinations, and token limit exceeded]
    end

    subgraph With Rapid OS Context Compiler
        D[Standards + ProjectModel + Spec] -->|rapid context (Mode + Budget)| E[Synthesized Context]
        E --> F[AI Agent]
        F --> G[Precise, focused implementation]
    end
```

---

## Main `rapid context` options

| Flag | Type | Description |
| :--- | :--- | :--- |
| `--mode` | string | Task mode: `feature`, `bugfix`, `refactor`, `hardening`, `research`, or `general`. |
| `--spec` | string | Identifier of a specification in `ready` state to include. |
| `--harness` | string | Identifier of the target harness (e.g. `codex`, `claude`, `cursor`, `vscode`, `antigravity`). |
| `--objective` | string | Explicit objective for relevance refinement. |
| `--max-chars` | integer | Maximum character budget for the resulting Markdown. |
| `--manifest` | flag | Prints a readable provenance summary (`ContextManifest`). |
| `--json` | flag | Emits the structured `CompiledContext` object in JSON format. |

---

## Example: Compile context for a Feature

Suppose a spec `api-rate-limiting` in `ready` state (see [How the spec is written](./first-spec.md)):

```bash
rapid context --spec api-rate-limiting --manifest
```

With `--mode`, `--harness`, or `--max-chars` (see the table above) you adjust the mode, the target agent, and the budget.

### What does the output contain?
The command emits to `stdout` a structured Markdown document ready to be pasted into the prompt or injected by an automation tool:
1. **General project directives:** Key architecture and coding standards extracted from `.rapid-os/standards/`.
2. **Relevant scan facts:** Language, testing frameworks, and libraries relevant to the mode.
3. **Active specification:** The objectives, scope, acceptance criteria, and tasks of the spec's frozen revision.
4. **Manifest summary (`--manifest`):**
   ```text
   Rapid OS Context Manifest

   Mode: general
   Harness: cursor
   Budget: 17550 / 24000 chars

   SELECTED
     standard.security      critical  9450 chars   relevant to general mode
     standard.architecture  high      5159 chars   relevant to general mode
     standard.tech-stack    high      445 chars    relevant to general mode
     spec.api-rate-limiting.requirements high      467 chars    relevant to general mode; selected spec 'api-rate-limiting'
   ```

---

## The Context Manifest (`ContextManifest`)

Every compilation generates a cryptographic hash of its content (`content_digest`). When a run is later created with `rapid run create`, this digest is recorded immutably in the execution contract (`ExecutionContract.context_digest`).

This guarantees a **perfect audit**: months after a change was implemented, the team can reproduce with mathematical certainty exactly what information and directives the agent saw at the time of execution.

</details>

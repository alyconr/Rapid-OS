---
title: What is Rapid OS
description: Purpose, scope, users, and mental model of Rapid OS v3.
---

# What is Rapid OS

Rapid OS is an **engineering governance** layer for **AI-assisted development**. It is installed as a CLI and keeps versionable artifacts inside the repository so that a coding harness's work has context, scope, rules, traceability, and verifiable evidence.

## Purpose

The main goal is for a task executed with AI to be able to answer these questions in a verifiable way:

1. **What do we know about the repository?**
2. **What must be built?**
3. **What context does the agent need for that task?**
4. **What risk level and which controls apply?**
5. **Does the harness declare the necessary capabilities?**
6. **What happened during execution?**
7. **What evidence supports that the task and its gates were satisfied?**
8. **Does the complete state of the project remain intact?**

## Who it is for

Rapid OS is aimed at:

- developers who use Codex, Claude, Cursor, VS Code, or other coding harnesses;
- teams that need to standardize how context is delivered to AI agents;
- architects who want to separate human decisions from automatic inferences;
- teams with quality, security, review, or migration controls;
- organizations that need traceability between specification, execution, and evidence.

## Mental model

Rapid OS works as a **control layer**, not as the builder.

```text
User / team
    ↓ defines intent and constraints
Rapid OS
    ↓ produces context, contracts, gates, and records
External coding harness
    ↓ implements or modifies the software
Rapid OS
    ↓ ingests evidence and evaluates deterministic rules
Governed result
```

## What it does

Rapid OS can:

- detect languages, frameworks, databases, testing, Docker, monorepos, and deploy signals;
- maintain specifications with immutable revisions;
- compile task-specific context;
- classify risk and require gates;
- model a harness's capabilities;
- maintain an append-only ledger of run states;
- copy and verify evidence artifacts with SHA-256;
- produce deterministic, reproducible evaluations;
- validate cross-integrity between specs, runs, evidence, and evals;
- drive a governed run with the porcelain (`rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`) and generate each harness's `/rapid-<mode>` shortcuts.

## What it does not do

Rapid OS:

- does not automatically invoke LLMs or coding agents;
- the plumbing (`rapid scan`, `rapid context`, `rapid spec`, `rapid policy`, `rapid run`, `rapid harness`, `rapid evidence`, `rapid eval`, `rapid validate`) does not execute anything from the repository: it operates on files and records;
- the porcelain runs only the `test_command` from `.rapid-os/config.json` or the argv passed to `rapid check -- <command>`, without a shell, plus read-only `git` commands to record the run's changes; it does not execute any other project command;
- does not create branches or worktrees on its own: only `rapid start --worktree` creates, on explicit request, the isolated worktree (`../<repo>-<run-id>`, branch `rapid/<run-id>`) of a run whose contract requires an isolated workspace;
- writes the architecture rule (`.rapid-os/standards/architecture.md` and `architecture.json`) for the catalog's backend and frontend stacks (with the idiomatic names of their language) when `rapid setup finish` or `rapid init` is executed; `rapid arch check` only reads the imports of the code under `modules_root` and `shared_root` (with `ast` and regular expressions, without executing it) and never modifies the code; `rapid check -- rapid ...` runs the Rapid OS currently in use;
- writes `compose.yaml` and `.env.example` with the infrastructure services the person decided on for now (`@now`), only in an empty repository or by adding the missing ones without modifying the existing ones; it never runs Docker or starts containers (the person runs `docker compose up -d`) and never deploys: `rapid deploy --target <platform>` only prints a template;
- writes the security baseline (`.rapid-os/standards/security.md`, at the archetype's level) when onboarding is closed and, only in an empty repository and without overwriting an existing one, a per-language CI workflow, `.github/workflows/rapid-security-<language>.yml`, with the security scans (the agent never writes it); it does not run those scans, your CI does;
- only creates a git repository when `rapid setup finish` or `rapid init` run in a folder that is not inside one (`git init` and `git symbolic-ref HEAD` to `main`, always): it needs it to observe the runs' changes, it never nests a repository inside another, and it never makes commits; without git installed it only warns, and `rapid start` fails with `RAPID1416` in a folder without a repository;
- does not invoke agents with the Claude Code hooks: `rapid hook stop|pre-tool` are executed by Claude Code and only respond with a tool denial or a stop block (`rapid shortcuts install --hooks` is the only way that writes them to `.claude/settings.json`);
- does not write `/rapid-<mode>` shortcuts into the harness folders (`.claude/skills`, `.agents/skills`, `.cursor/skills`, `.github/prompts`) except when `rapid shortcuts install` or `rapid init --shortcuts` is executed, and only with `rapid shortcuts install --global` does it write outside the project, in your user's skills folder (the `install.sh` and `install.ps1` installers only offer it, never by default);
- does not write `docs/PRODUCT_BRIEF.md`, `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md`, or `docs/ARCHITECTURE.md` except when `rapid setup doc` or `rapid init` is executed, nor does it copy the standards from `.rapid-os/standards/` except `rapid setup finish` or `rapid init`; `rapid init` no longer creates the `TODO` scaffolding of `docs/` (`SPECS.md` and similar);
- only marks as done the brief story that the run closed: with a PASS verdict and the `story:<ID>` tag in the spec, `rapid finish` changes that single line of `docs/PRODUCT_BRIEF.md` (`- [ ] H002:` becomes `- [x] H002:`, with a copy in `.rapid-os/backups/`) and touches nothing else; with another verdict, with `--no-tick`, or with a brief without `rapid-doc` frontmatter it only suggests `Mark H002 as done in docs/PRODUCT_BRIEF.md`. Nor does it leave `.bak` copies of the agent files it regenerates (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`...) in the project root: they go to `.rapid-os/backups/`, only if the content changed and keeping the 5 most recent per file;
- never marks as confirmed what the person did not confirm: a document drafted by the agent stays as `source: drafted` and `status: draft` until an explicit `rapid setup doc <id> --confirm`, and it reaches the context marked as an assumption;
- never invokes agents and never approves human gates: `rapid approve` is executed by a person in their terminal (it requires a TTY and fails with `RAPID1310` under an agent);
- does not treat an `acknowledged` gate as evidence;
- does not treat a declared capability as proof that it was used;
- does not guarantee that a `PASS` means a total absence of bugs or perfect security.

## Compatibility

Rapid OS v3 keeps the legacy v2 flows, including `rapid init`, `rapid scope`, `rapid skill`, `rapid mcp`, `rapid vision`, `rapid deploy`, `rapid refine`, `rapid inspect-context`, `rapid validate`, and `rapid doctor`, while adding the v3 governance cycle.

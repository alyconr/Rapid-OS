---
title: Product Boundaries
description: What Rapid OS v3 does and does not do, with a strict separation of responsibilities.
---

# Product Boundaries

Understanding Rapid OS's technical boundaries is essential to using it successfully. Rapid OS is a **governance, specification, audit, and quality-control layer**. It is not a model executor or autonomous agent.

## Keep concepts separate

A common source of errors in AI tools is confusing human declarations with physical facts or logical conclusions. Rapid OS keeps them distinct:

```text
Declaration != Capability != Evidence != Evaluation
```

1. **Gate acknowledged:** A human operator or script declares that a control was satisfied (`ACKNOWLEDGED`). This is a declaration, **not evidence** that the code works.
2. **Harness compatible:** A harness declares support for `tests.execute`. This means the tool says it can run tests; it does **not** prove that it did.
3. **Run evidence:** The test executor's output with exit code `0` and a SHA-256 hash is stored. This is **physical evidence**.
4. **Evaluation PASS:** The evaluator checks recorded evidence under deterministic rules and returns a verdict. This is a **formal evaluation**.

## What Rapid OS does not do

:::warning Explicit boundaries
Rapid OS has a strict deterministic-engineering scope. The following operations are outside its design:
:::

- **It does not call LLMs or model APIs automatically:** Rapid OS does not call OpenAI, Anthropic, Google, or other providers in the background. Language-model interaction happens in the coding harness chosen by the developer.
- **It does not orchestrate autonomous background agents:** It is not a continuous-execution daemon or recursive agent runtime.
- **It does not use an LLM as a judge:** `rapid eval` uses deterministic rules implemented with the Python standard library.
- **Plumbing does not run repository code; porcelain runs only requested commands:** `rapid scan`, `context`, `spec`, `policy`, `run`, `harness`, `evidence`, `eval`, and `validate` operate statically on files and records. Porcelain runs only `test_command` from `.rapid-os/config.json` (for the `rapid start` baseline and `rapid task done`) or argv passed to `rapid check -- <command>`, without a shell, plus read-only Git commands (`rev-parse`, `diff`, `ls-files`, `config user.name`) to record run changes. `rapid start --worktree` also runs `git worktree add`. It runs no other project commands.
- **It never approves human gates:** A person runs `rapid approve` in their terminal. Rapid OS, shortcuts, hooks, and harness-produced evidence cannot approve, waive, or reject a human gate.
- **It does not automatically create Git branches or worktrees:** If policy requires `workspace.isolated`, Rapid OS records that in the contract and `rapid start` stops as `blocked`. Only `rapid start --worktree`, run by the operator or harness, creates the isolated worktree (`../<repo>-<run-id>`, branch `rapid/<run-id>`); `rapid abort` never removes it. The operator or harness creates other isolated environments or branches.
- **All Git commands use one entry point:** `rapid_os/orchestration/git.py` runs Git with `-c safe.directory=<project root>` (only that directory, never `*`) and `-c core.fsmonitor=false`. This avoids ownership issues such as the Codex Windows sandbox and prevents a foreign repository from executing programs when read. If the person's own Git needs an exception, Rapid OS reports it in `person_actions`; it never changes the person's Git configuration.
- **It initializes Git only so it can observe runs:** `rapid setup finish` and `rapid init` run `git init` (and set the initial branch to `main`) only outside an existing repository. They never nest repositories or commit; if Git is absent, they only warn. `rapid start` outside a repository returns `RAPID1416` without writing anything.
- **Architecture is checked by reading imports, not running application code:** `rapid arch check` reads files under `modules_root` and `shared_root` and reports violations; it never edits code or migrates an existing project. It writes `architecture.md` and `architecture.json` for catalog backend and frontend stacks, and never overwrites an existing file. See [Reference Architecture](./architecture.md).
- **It writes local service configuration but does not start services or deploy:** `rapid setup finish` writes `compose.yaml` and `.env.example` for services selected as `@now`, and adds `.env` to `.gitignore`. If `compose.yaml` exists, it adds missing services without changing existing ones. It does not run Docker; a person runs `docker compose up -d`. `rapid deploy --target <platform>` prints a template without writing files; a person performs deployment. See [Infrastructure Services](./infrastructure-services.md) and the [deployment guide](../guides/deployment.md).
- **It writes the security baseline and CI configuration but does not run scans:** `rapid setup finish` writes `standards/security.md` and, only for an empty repository, a language-specific `.github/workflows/rapid-security-<language>.yml` workflow. It never overwrites an existing workflow or manually written `security.md`. CI runs the scans. See the [Security Baseline](./security-baseline.md).
- **Hooks can deny tools to an agent, but Rapid OS does not invoke agents:** Claude Code runs `rapid hook stop|pre-tool` when the agent tries to stop or use a tool. Hooks return a stop block or denial (reserving `rapid approve`, `rapid abort`, and `.rapid-os/` writes for a person); they never launch an agent. `rapid shortcuts install --hooks` or `rapid init --hooks` writes them to `.claude/settings.json` without changing user hooks. Command detection is best effort.
- **It does not install harness shortcuts on its own:** `rapid shortcuts install` (or `rapid init --shortcuts`) writes `/rapid-<mode>` and `/rapid-init` files into supported harness directories. `rapid shortcuts install --global` writes to documented user skill directories only when explicitly requested. `rapid shortcuts remove` deletes only files marked `generated by rapid shortcuts`. Shortcuts never approve human gates.
- **It does not confirm project documents for a person or create them autonomously:** Only `rapid setup doc` and `rapid init` write `docs/PRODUCT_BRIEF.md`, `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md`, and `docs/ARCHITECTURE.md`, with provenance frontmatter and a backup. A draft is saved as `source: drafted`, `status: draft` and remains an assumption in context until a person runs `rapid setup doc <id> --confirm`. `rapid init` no longer creates `TODO` scaffolding in `docs/`.
- **It marks only the story closed by a run and keeps backups out of the project root:** If `rapid finish` returns PASS and the spec has `story:<ID>`, it changes that one unchecked story to checked, keeping a prior copy under `.rapid-os/backups/`. Otherwise it only suggests the story. Regenerated agent files also keep up to five changed backups there.
- **It is not an operating-system sandbox:** Rapid OS "capabilities" are software capability declarations, not kernel-enforced isolation or containers.
- **It does not mathematically guarantee defect-free software:** `PASS` certifies that contract rules were satisfied by recorded evidence; it is not a formal proof that the software has no bugs and does not replace engineering judgment.

## What Rapid OS does

- Guides a governed run with porcelain commands and generates harness shortcuts.
- Deterministically scans repositories and extracts facts with provenance (`rapid scan`).
- Maintains software specs with immutable revisions (`rapid spec`).
- Compiles structured context under strict character budgets (`rapid context`).
- Models risk policies and control gates (`rapid policy`).
- Issues immutable execution contracts bound by SHA-256 digests (`rapid run`).
- Models and validates capabilities declared by coding tools (`rapid harness`).
- Records and protects execution evidence artifacts (`rapid evidence`).
- Evaluates physical evidence offline with reproducible rules (`rapid eval`).
- Audits cross-project integrity (`rapid validate`).

## Human gates and layered defenses

Human review gates are **never acknowledged automatically**.

- `rapid approve` requires an interactive terminal (TTY), asks for explicit text confirmation (`approve <gate-id>`), and rejects child-agent session markers (`CLAUDE_CODE_CHILD_SESSION == "1"`).
- It also checks the parent process chain and returns `RAPID1310` if an ancestor is an agent harness. Currently, only Claude Code is recognized, based on documented or observed process names. Codex and Cursor are not recognized because their process names are unconfirmed. Ancestor detection is **best effort**: detached processes, renamed executables, reused PIDs, or unreadable process trees are known limits. If the tree cannot be read, `rapid approve` does not reject for that reason; `rapid doctor` records `RAPID1319`. A person using their own terminal, including an IDE terminal, has no `claude` ancestor; Claude Code's `!` mode does and cannot approve.
- TTY confirmation can be emulated externally (for example with `script` or a PTY emulator). It is a **layered defense** and deliberate friction, not a cryptographic or infallible guarantee. Rapid OS does not cryptographically attest who approves; reviewer identity is declared through `--reviewer` or `git config user.name`.

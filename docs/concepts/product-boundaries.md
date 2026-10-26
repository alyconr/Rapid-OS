---
title: Product Limits and Boundaries
description: What Rapid OS v3 does and does NOT do. Strict separation of responsibilities.
---

# Product Limits and Boundaries

To use Rapid OS successfully you need to understand its technical boundaries. Rapid OS is a layer of **governance, specification, auditing, and quality control**. It is not a model runner or an autonomous agent.

---

## Strict separation of concepts

One of the most common sources of error in AI tooling is confusing human statements with physical facts or logical conclusions. Rapid OS draws rigorous distinctions:

```text
Declaration != Capability != Evidence != Evaluation
```

1. **Gate Acknowledged:** A human operator or script declares that a control was satisfied (`ACKNOWLEDGED`). This is a declaration, **not evidence** that the code works.
2. **Harness Compatible:** A harness declares that it supports `tests.execute`. This means the tool *says it can run tests*; it **does not prove** that it ran them.
3. **Run Evidence:** The output file with the test runner's exit code `0` and its SHA-256 hash is stored. This is **physical evidence**.
4. **Evaluation PASS:** The evaluator analyzes the recorded evidence under deterministic rules and issues a verdict. This is a **formal evaluation**.

---

## What Rapid OS does NOT do

:::warning Explicit boundaries
Rapid OS keeps a strict scope of deterministic engineering. The following operations are outside its design:
:::

- **It does not automatically invoke LLMs or model APIs:** Rapid OS does not call OpenAI, Anthropic, Google, or other providers in the background. Interaction with the language model happens in the coding harness the developer chooses to use (Codex, Claude, Cursor, Antigravity, etc.).
- **It does not orchestrate background autonomous agents:** It is not a continuously running daemon or a recursive-agent runtime.
- **It does not use LLM-as-a-judge:** Behavioral evaluations (`rapid eval`) are 100% deterministic, executed by standard-library Python code against logical rules.
- **Plumbing executes nothing from the repository; porcelain executes only what it is asked to:** `rapid scan`, `rapid context`, `rapid spec`, `rapid policy`, `rapid run`, `rapid harness`, `rapid evidence`, `rapid eval`, and `rapid validate` operate statically on files and records. The porcelain runs only the `test_command` from `.rapid-os/config.json` (in the `rapid start` baseline and in `rapid task done`) or the argv passed to `rapid check -- <command>`, without a shell, plus read-only `git` commands (`rev-parse`, `diff`, `ls-files`, `config user.name`) to record the run's changes; with `rapid start --worktree` it adds `git worktree add`. It runs no other project command.
- **It never approves human gates:** `rapid approve` is run by a person in their terminal. Rapid OS never approves, waives, or rejects a human gate on its own, and neither does a shortcut, a hook, or evidence produced by a harness.
- **It does not automatically create Git branches or worktrees:** When a policy requires `workspace.isolated`, Rapid OS declares the need in the contract and `rapid start` stops at `blocked`. Only `rapid start --worktree`, run by the operator or their harness, creates the isolated worktree (`../<repo>-<run-id>`, branch `rapid/<run-id>`); `rapid abort` never removes it. In every other case, actually creating the isolated environment or branch is up to the operator or the harness.
- **All its git commands go through a single gate:** `rapid_os/orchestration/git.py` runs git with `-c safe.directory=<project root>` (only that folder, never `*`) and `-c core.fsmonitor=false`, so it does not depend on who owns the folder (Codex sandbox on Windows) and so a foreign repository cannot run programs just by being read. The exception for the person's own git, which only they can grant, is handed to them as `person_actions`; Rapid OS never modifies the person's git configuration.
- **It only creates a git repository so it can observe runs:** `rapid setup finish` and `rapid init` run `git init` (and set the initial branch with `git symbolic-ref HEAD`, always `main`) only when the folder is not inside a repository. It never nests repositories, never makes commits, and without git installed it only warns. `rapid start` in a folder with no repository fails with `RAPID1416` without writing anything.
- **Architecture is verified by reading imports, not by running code:** `rapid arch check` reads the text of the files under `modules_root` and `shared_root` (Python with `ast`; TypeScript, JavaScript, and the script blocks of `.vue`, `.svelte`, and `.astro`, Go, Java, Kotlin, C#, Rust, and PHP with regular expressions; Ruby on Rails delegates to `bin/packwerk check`) and only reports; it never edits code or migrates an existing project. Rapid OS writes the rule (`architecture.md` and `architecture.json`) for the backend and frontend stacks in the catalog (using the idiomatic names of their language), and it does not overwrite an existing file. See [Reference architecture](./architecture.md).
- **It writes the local services environment, but does not start it or deploy:** `rapid setup finish` writes `compose.yaml` and `.env.example` for the services decided `@now` (and adds `.env` to `.gitignore`); if `compose.yaml` already exists it only adds the missing services and does not modify what is there. It does not run Docker: the person runs `docker compose up -d`. `rapid deploy --target <platform>` prints a template and writes nothing; the person does the deployment. See [Infrastructure services](./infrastructure-services.md) and the [deployment guide](../guides/deployment.md).
- **It writes the security baseline and its CI, but does not run the scans:** `rapid setup finish` writes `standards/security.md` and, only in an empty repository, one workflow per language `.github/workflows/rapid-security-<language>.yml` (gitleaks, semgrep, bandit or `pip-audit`/`npm audit`, and SBOM and provenance in Corporate, all pinned by full SHA). It never overwrites an existing workflow or a hand-written `security.md`. The scans are run by your CI, not by Rapid OS. See [Security baseline](./security-baseline.md).
- **Hooks deny tools to the agent, but Rapid OS does not invoke agents:** `rapid hook stop|pre-tool` are run by Claude Code when the agent tries to stop or to use a tool; they only return a stop block or a denial (they reserve `rapid approve`, `rapid abort`, and writes to `.rapid-os/` for the person) and never launch the agent. Only `rapid shortcuts install --hooks` or `rapid init --hooks` write them to `.claude/settings.json`, without touching the user's hooks, and command detection is best-effort.
- **It does not install harness shortcuts on its own:** `rapid shortcuts install` (or `rapid init --shortcuts`) is the only way to write the `/rapid-<mode>` commands (and `/rapid-init`) into `.claude/skills`, `.agents/skills`, `.cursor/skills`, or `.github/prompts`, and `rapid shortcuts install --global` is the only way to write them outside the project, in your user's skills folder (only for harnesses with a documented folder; `install.sh` and `install.ps1` offer it as an option and never by default); `rapid shortcuts remove` deletes only the files that carry the `generated by rapid shortcuts` marker. Shortcuts never approve human gates.
- **It does not confirm on the person's behalf or create documentation on its own:** `rapid setup doc` and `rapid init` are the only commands that write `docs/PRODUCT_BRIEF.md`, `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md`, and `docs/ARCHITECTURE.md` (with `rapid-doc`, `source`, `status`, and `sha256` frontmatter, and a `.bak` of the previous file); `rapid setup finish` and `rapid init` are the only ones that copy stack, topology, archetype, and security into `.rapid-os/standards/`. A document drafted by the agent is saved as `source: drafted` and `status: draft`, enters the context as an assumption, and only `rapid setup doc <id> --confirm` confirms it. `rapid init` no longer creates the `TODO` scaffolding in `docs/`.
- **It only ticks the story the run closed, and does not fill the root with backups:** when `rapid finish` ends in PASS and the spec carries the `story:<ID>` tag, it changes that single `- [ ] <ID>:` line to `- [x] <ID>:` in `docs/PRODUCT_BRIEF.md` (previous copy in `.rapid-os/backups/`, `source` and `status` unchanged: a draft stays a draft); if the verdict is not PASS, if you pass `--no-tick`, or if the brief is not a Rapid OS document, it only suggests the story. A run covers one story. The agent files that Rapid OS regenerates keep their previous copy in `.rapid-os/backups/` (only if the content changed, 5 per file), not in the project root.
- **It is not an operating-system sandbox:** "Capabilities" in Rapid OS are declarations of software capabilities, not kernel security cages or enforced containers.
- **It does not mathematically guarantee the absence of defects:** A `PASS` verdict certifies that the contract rules and the recorded evidence were satisfied. It is not a formal proof of mathematical correctness of all the software, and it does not replace the judgment of engineers.

---

## What Rapid OS DOES do

- Drives a governed run from start to finish with the porcelain (`rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`) and generates each harness's `/rapid-<mode>` shortcuts (`rapid shortcuts`).
- Analyzes repositories deterministically and extracts facts with provenance (`rapid scan`).
- Maintains software specifications with immutable revisions (`rapid spec`).
- Compiles structured context within strict character budgets (`rapid context`).
- Models risk policies and control gates (`rapid policy`).
- Issues immutable execution contracts bound by SHA-256 digests (`rapid run`).
- Models and validates the capabilities declared by coding tools (`rapid harness`).
- Records and safeguards execution evidence artifacts (`rapid evidence`).
- Evaluates physical evidence offline using reproducible rules (`rapid eval`).
- Audits the full cross-integrity of the project (`rapid validate`).

---

## Boundaries on human gates and defense in depth

A core governance principle in Rapid OS is that **human review gates are never acknowledged automatically**.

To prevent agents or subprocesses from self-approving human gates:
- `rapid approve` requires an interactive terminal (TTY), asks for explicit textual confirmation (`aprobar <gate-id>`), and refuses to run if it detects child-agent session markers (`CLAUDE_CODE_CHILD_SESSION == "1"`).
- It also walks the parent process chain and refuses to run (`RAPID1310`) if any ancestor is an agent harness. Today only Claude Code is recognized (the `claude`/`claude.exe` binary, the `@anthropic-ai/claude-code` npm package, and the native installer's `~/.local/share/claude/versions/` directory), because those are the only names confirmed in its official documentation or in a real installation; Codex and Cursor are not recognized because their process name is not confirmed. Ancestry detection is **best-effort**: a process that detaches from its parent (double fork, `setsid`, `nohup … &`) ends up hanging from `init` and no longer has `claude` as an ancestor. Along with a renamed `claude.exe` and the reused pid of a dead parent, this is a known limit. The rule remains that a person approves in their own terminal. If ancestry cannot be read (Linux: `/proc`; macOS: `ps`; Windows: `CreateToolhelp32Snapshot`), `rapid approve` does **not** refuse because of it and `rapid doctor` records the reason (`RAPID1319`). A person using their own terminal, even an IDE's integrated one, has no `claude` process among their ancestors; they also cannot approve from Claude Code's `!` mode, because there `claude` is the ancestor.
- It is important to note that TTY confirmation can be emulated externally (with commands such as `script` or `pty` emulators), so it acts as **defense in depth** and deliberate friction, not as a cryptographic or foolproof guarantee. Rapid OS does not cryptographically attest who approves: the reviewer's identity is the one declared (`--reviewer` or `git config user.name`).

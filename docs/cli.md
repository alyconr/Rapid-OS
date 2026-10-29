# Rapid OS CLI Reference

Rapid OS provides a deterministic, standard-library-only command-line interface (`rapid` or `python rapid.py`) for project intelligence, task-aware context compilation, spec authoring, execution policy & runs, harness capability resolution, immutable run evidence ingestion, and deterministic behavioral evaluations.

All commands operate on the **current working directory** as the target project root.

## Global Options

- `--version`: Print `Rapid OS 3.1.1` and exit (`0`).
- `-h`, `--help`: Show command help and exit (`0`).

```bash
rapid --version
rapid --help
```

---

## Global Contracts

### JSON Output Contract (`--json`)
For every command supporting `--json`:
- `stdout` emits **exactly one** valid UTF-8 JSON document (no banners, emojis, or decorative text).
- `stderr` receives any human-readable error or diagnostic messages when a command fails.
- Process exit code reflects the command outcome (`0` on success, non-zero on error or gate failure).

### Exit Code Matrix

| Scenario | Exit Code |
| :--- | :--- |
| Successful informational or state-writing command | `0` |
| `rapid validate` / `rapid doctor` with warnings only (without `--strict`) | `0` |
| `rapid validate --strict` when any warning or error is present | `1` |
| `rapid harness resolve` without `--require-compatible` (`compatible`, `incompatible`, or `unresolved`) | `0` |
| `rapid harness resolve --require-compatible` when status is `incompatible` or `unresolved` (`RAPID1110`) | `1` |
| `rapid eval run` without `--require-pass` (`pass`, `pass_with_waivers`, `unverified`, or `fail`) | `0` |
| `rapid eval run --require-pass` when verdict is `unverified` (`RAPID1225`) or `fail` (`RAPID1226`) | `1` |
| Domain validation error (`RAPIDxxx`) or missing required resource | `1` |
| Invalid CLI flag / argument (`argparse` usage error) | `2` |

---

## Core Project & Legacy Workflow Commands

### `rapid init`
Initialize `.rapid-os/` standards, `.rapid-os/config.json`, and AI harness rule files (`.cursorrules`, `CLAUDE.md`, `.agent/rules/constitution.md`, `INSTRUCTIONS.md`, `AGENTS.md`). Writes project configuration and context files with `.bak` backup protection.

```bash
rapid init
rapid init --stack nextjs
rapid init --archetype corporate
rapid init --archetype mvp
rapid init --no-scan
```

Options:
- `--stack <name>`: Select the stack directly (`templates/stacks/<component>/<name>.md`; `generic` and `docs-modern` live in `templates/stacks/`). A stack that covers several components fills all of them; a stack id of before the component catalog (`python-api`, `python-ai`, `nodejs-ai`, `web-modern`, `frontend-creative`) is accepted and maps to the stack that replaced it. `init` takes one stack: a component of the topology that it does not cover is chosen afterwards with `rapid setup next`.
- `--archetype {mvp,corporate}`: Select archetype directly without interactive prompt.
- `--topology <id>`: Select topology template directly (`templates/topologies/<id>.md`). With `--yes` and no `--topology`, the topology is chosen to match the stack (`doc-site` only with `docs-modern`; `fullstack-separated` for the backend stacks and the frameworks that cover both components; `front-end-only` for the frontend stacks).
- `rapid init` also creates `.rapid-os/standards/security.md` (from the `corporate` archetype or, if there is none, a minimal template) when it does not exist; `rapid start hardening` requires it.
- `--agents <lista>`: Comma-separated list of agent IDs or numbers (e.g. `cursor,claude`).
- `-y`, `--yes`: Non-interactive mode accepting defaults. It asks nothing about the project documents: they stay `pending` (not skipped), and `init` ends with `Complete the documentation with /rapid-init or rapid setup next`. With `--yes --no-scan`, no `test_command` is suggested, so pass `--test-command`.
- `--business-file <ruta>`: Import that file as `docs/BUSINESS_RULES.md`, provided by a person (`source: provided`, `status: confirmed`) and stored as is, without checking sections or size. A path that is empty, a directory or unreadable is `RAPID1413` (exit 1, nothing written). The other documents follow the usual rules (asked, or `pending` with `--yes`).
- `--skip-docs`: Mark the four project documents (`brief`, `business`, `data-model`, `architecture`) as `skipped` without asking. Combined with `--business-file`, the business document is still imported.
- `--test-command <cmd>`: Explicit test command string to store in `.rapid-os/config.json`.
- `--no-scan`: Skip automatic project intelligence scan suggestions during initialization.
- `--shortcuts`: Install the `/rapid-<mode>` shortcuts for the selected agents at the end of `init` without asking (see `rapid shortcuts`). Without it, `init` only offers them on an interactive terminal. It does not install hooks.
- `--hooks`: Also install the Claude Code hooks (see `rapid hook`) in `.claude/settings.json`. Independent of `--shortcuts`; it needs `claude` among the selected agents (otherwise a `RAPID1337` warning is printed and `init` continues).

`init` shares the state and the writes of `rapid setup`: it builds the same `.rapid-os/setup.json`, copies the same standards and saves the same config. The interactive terminal offers, for each of the four documents (`docs/PRODUCT_BRIEF.md`, `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md`, `docs/ARCHITECTURE.md`): 1) import a file (`.md`, `.txt`; an empty path or a directory asks again, `0` goes back), 2) write it there (it ends with two empty lines or EOF), 3) leave it for your agent (`/rapid-init`, the default) or 4) skip it. A document that is already resolved (`provided`, `drafted` or `skipped`) is kept when `init` runs again. `init` no longer offers the `TODO` scaffold of `docs/` (`SPECS.md` and the other templates) nor saves business templates; it does not write `.rapid-os/standards/business.md` any more (an existing one keeps working, see `rapid setup doc business --from-legacy`).
- When documents are left `pending`, `init` ends suggesting `/rapid-init` (`$rapid-init` in Codex) or `rapid setup next`; `rapid shortcuts install --only rapid-init` creates the shortcut.
- When `init` installs shortcuts or hooks and `rapid` is not on the `PATH`, it prints the warning `RAPID1414` and still exits 0: the shortcuts and the hooks run `rapid` from the agent's shell. `rapid doctor` reports the same.

### `rapid guide`
Display the Rapid OS v3 8-step governance workflow and command reference (`Read-only` vs `Writes`). Read-only.

```bash
rapid guide
```

### `rapid scan`
Scan the repository and emit normalized `ProjectFact` records (`ProjectModel`, `schema_version = 1`). Read-only unless `--write` is passed.

```bash
rapid scan
rapid scan --verbose
rapid scan --json
rapid scan --write
rapid scan --json --write
```

Options:
- `--verbose`: Show per-fact `Evidence` provenance (`path`, `reason`, `source_type`).
- `--json`: Emit pure `ProjectModel` JSON to `stdout`.
- `--write`: Persist `.rapid-os/project.json` snapshot (`schema_version = 1`) with backup protection.

### `rapid validate`
Validate templates, `.rapid-os/` configuration, standards, project intelligence snapshot (`RAPID600–RAPID604`), context compilation (`RAPID700–RAPID705`), spec registry (`RAPID800–RAPID809`), execution policy & run registry (`RAPID1000–RAPID1014`), harness capability registry & lock (`RAPID1100–RAPID1112`), evidence registry (`RAPID1200–RAPID1211`), and behavioral evaluation registry (`RAPID1220–RAPID1229`). Read-only.

```bash
rapid validate
rapid validate --strict
rapid validate --json
rapid validate --strict --json
```

### `rapid doctor`
Inspect local Rapid OS installation paths, bundled/repo template availability, optional `node`/`npx` availability, and current project health. Read-only.

```bash
rapid doctor
rapid doctor --json
```

`doctor` also warns with `RAPID1421` when `standards/security.md` exists and does not mention OWASP ASVS (the project was initialized before the security baseline), with the hint `rapid setup set archetype <current> --refresh`.

When the folder is a git repository that Git refuses for the person's own terminal ("dubious ownership") but accepts for Rapid OS, `doctor` adds the optional `person_actions` list (see `rapid setup`): `[{"id": "git-safe-directory", "why": ..., "command": ...}]` in `--json`; otherwise, it prints `To use Git yourself in this folder, run this in your terminal: <command>` plus the reason. Nothing is added for a repository the person owns.

### `rapid inspect-context`
Assemble and preview the legacy v2 composed project context without writing agent files. Read-only.

```bash
rapid inspect-context
rapid inspect-context --summary
rapid inspect-context --json
```

### `rapid scope`
Interactive Spec-Driven Development wizard that generates root `SPECS.md`, `TASKS.md`, and `ACCEPTANCE.md` (with optional registration in `.rapid-os/specs/`). Writes files.

```bash
rapid scope
rapid scope --register
rapid scope --register --spec-id checkout-flow --status ready
```

### `rapid skill`
Manage agent skills from local templates or remote packages (`npx skills add`).

```bash
rapid skill
rapid skill list
rapid skill install <template-name>
rapid skill add <package-ref>
```

### `rapid mcp`
Generate Model Context Protocol (MCP) server configuration for supported editors (`cursor`, `claude`, `vscode`, `antigravity`, `codex`) at `project` or `global` scope. Writes files.

```bash
rapid mcp
rapid mcp --ide claude --scope project
rapid mcp --ide codex --scope project
rapid mcp --ide cursor --scope project
rapid mcp --ide vscode --scope project
rapid mcp --ide antigravity --scope global
```

### `rapid vision`
Copy a UI reference image into `references/`, record its description in `references/VISION_CONTEXT.md`, and regenerate active agent context files. Writes files.

```bash
rapid vision
rapid vision path/to/mockup.png
```

### `rapid deploy`
Print the deployment template of a platform (`aws`, `azure`, `vercel`, `render`, `railway` or `dokploy`, from `templates/deploy/<target>.md`) and the command that reopens the project document, `rapid setup doc deployment --reopen`. Read-only: it no longer writes `DEPLOY.md`; the project document is `docs/DEPLOYMENT.md`, the optional last document of the onboarding. An unknown platform is `RAPID1413`. See the [deployment guide](guides/deployment.md).

```bash
rapid deploy --target railway
```

### `rapid refine` & `rapid prompt`
Generate structured prompts for refining rule files (`rapid refine <file>`) or assembling a quick context prompt (`rapid prompt`, legacy alias). Read-only output to terminal.

```bash
rapid refine .rapid-os/standards/business.md
rapid prompt
```

---

## Context Compiler (`rapid context`)

Compile task-relevant, budgeted context (`CompiledContext`, `schema_version = 1`) in read-only mode. Both `rapid context` and `rapid context compile` are supported.

```bash
rapid context
rapid context compile --mode feature --harness codex --objective "Implement billing webhook"
rapid context --spec billing-webhook --harness my-company-agent
rapid context --mode hardening --manifest
rapid context --mode general --json
```

Options:
- `[compile]`: Optional positional action alias.
- `--mode {feature,bugfix,refactor,hardening,research,general}`
- `--harness <harness-id>`: Any valid harness ID (`^[a-z0-9][a-z0-9-]{0,62}$`, e.g. `codex`, `claude`, `cursor`, `vscode`, `antigravity`, or custom IDs).
- `--objective <text>`
- `--spec <spec-id>` / `--spec-revision <n>`: Load a `ready` spec from `.rapid-os/specs/<spec-id>/` (suppresses root `SPECS.md`/`TASKS.md`/`ACCEPTANCE.md`).
- `--path <relative-path>` (repeatable)
- `--tag <tag>` (repeatable)
- `--constraint <constraint>` (repeatable)
- `--max-chars <n>`
- `--manifest`: Render human-readable selection/skip/conflict manifest.
- `--json`: Emit pure `CompiledContext` JSON (`schema_version = 1`) on `stdout`.

---

## Spec Registry (`rapid spec`)

Manage immutable, multi-spec revisions in `.rapid-os/specs/<spec-id>/`.

- **Read-only subcommands**: `list`, `show`
- **State-writing subcommands**: `create`, `revise`, `status`, `export-legacy`

```bash
rapid spec create --title "Checkout Flow" --mode feature --objective "Enable Stripe checkout" --scope "API" --acceptance "Webhook verified" --task "Add endpoint" --status ready [--json]
rapid spec list [--status {draft,ready,archived}] [--json]
rapid spec show <spec-id> [--revision <n>] [--json]
rapid spec revise <spec-id> --task "Add idempotency key" [--json]
rapid spec status <spec-id> {draft,ready,archived} [--json]
rapid spec export-legacy <spec-id> [--revision <n>]
```

Authoring flags of `create` and `revise` (list fields can be repeated): `--title`, `--mode`, `--objective` (`--business-objective`), `--problem` (`--problem-statement`), `--scope`, `--out-of-scope`, `--actor` (`--actors-users`), `--main-flow` (`--flow`), `--edge-case`, `--business-rule` (`--rule`), `--technical-constraint` (`--constraint`), `--affected-path`, `--data-impact`, `--acceptance` (`--acceptance-criteria`), `--testing` (`--testing-strategy`), `--task` (`--implementation-task`) and `--tag`. `create` also takes `--id`, `--status` and `--export-legacy`.

---

## Execution Policy & Run Registry (`rapid policy` & `rapid run`)

Evaluate execution contracts (`ExecutionContract`, `schema_version = 1`) and track append-only run states in `.rapid-os/runs/<run-id>/`.

### `rapid policy`
- `rapid policy show [--json]`: Display active execution policy (`default` or `.rapid-os/policy.json`). Read-only.
- `rapid policy init [--json]`: Write default `.rapid-os/policy.json` (fails with `RAPID1005` if it already exists). Writes files.

### `rapid run`
- **Read-only subcommands**: `list`, `show`
- **State-writing subcommands**: `create`, `status`, `task`, `gate`

```bash
rapid run create --spec <spec-id> [--spec-revision <n>] [--id <run-id>] [--harness <harness-id>] [--classification {spike,bounded,architectural}] [--risk {low,medium,high,critical}] [--json]
rapid run list [--status {prepared,active,blocked,finished,failed,cancelled}] [--json]
rapid run show <run-id> [--state-revision <n>] [--json]
rapid run status <run-id> {active,blocked,finished,failed,cancelled} [--reason "..."] [--json]
rapid run task <run-id> <task-id> {in_progress,done,blocked,skipped} [--reason "..."] [--json]
rapid run gate <run-id> <gate-id> {acknowledged,waived,acknowledge,waive} [--reason "..."] [--json]
```

> **CLI Flag Conventions (`run_id` vs `--run`)**: Within `rapid run`, `<run-id>` is a positional argument (`rapid run show <run-id>`) because `Run` is the primary resource of that command group. In cross-domain commands that evaluate or attach records to a run (`rapid harness resolve --run <run-id>`, `rapid evidence ... --run <run-id>`, `rapid eval ... --run <run-id>`), `--run <run-id>` is passed as a named flag.

---

## Harness Capability Registry (`rapid harness`)

Inspect declarative harness capability profiles (`HarnessProfile`, `schema_version = 1`), initialize project profile overrides in `.rapid-os/harnesses/<id>.json`, lock active profiles in `.rapid-os/capabilities.lock`, and resolve run contracts against harness capabilities (`CapabilityResolution`, `schema_version = 1`).

- **Read-only subcommands**: `list`, `show`, `resolve`
- **State-writing subcommands**: `init`, `lock`

> **Product Truth**: A capability declaration states what a harness is expected to support; it does not execute the harness or prove that the capability was exercised at runtime.

```bash
rapid harness list [--json]
rapid harness show <harness-id> [--json]
rapid harness init <harness-id> [--json]
rapid harness lock [--json]
rapid harness resolve --run <run-id> [--locked] [--require <capability-id>] [--require-compatible] [--json]
```

Options for `rapid harness resolve`:
- `--run <run-id>`: Required run identifier whose `ExecutionContract` is evaluated (`profile.id == contract.harness`).
- `--locked`: Resolve against `.rapid-os/capabilities.lock` instead of live profiles (`RAPID1111` if missing or invalid).
- `--require <capability-id>`: Repeatable extra canonical capability requirement (`source="cli.require"`, additive only).
- `--require-compatible`: Gate mode — exits `0` only when `status == "compatible"`, and exits `1` with `RAPID1110` when `status` is `incompatible` or `unresolved`.
- `--json`: Emit pure `CapabilityResolution` JSON (`schema_version = 1`) on `stdout`.

---

## Evidence Engine (`rapid evidence`)

Ingest, inspect, and verify append-only, immutable execution evidence (`RunEvidence`, `schema_version = 1`: `id`, `run_id`, `contract_digest`, `state_revision`, `state_digest`, `kind`, `producer`, `summary`, `task_ids`, `gate_ids`, `capability_ids`, `payload`, `artifacts`, `content_digest` — contains no wall-clock timestamps) and copied SHA-256-verified artifacts (`EvidenceArtifact`: `path`, `sha256`, `size_bytes`) under `.rapid-os/evidence/<run-id>/`.

- **Read-only subcommands**: `list`, `show`, `verify`
- **State-writing subcommand**: `add`

> **Product Truth**: Evidence authenticity is local integrity verification (`content_digest`, artifact `sha256` and `size_bytes`, sequence continuity `E001..E00N`, and Run/Contract/`RunState` binding), not cryptographic external attestation. Adding evidence never mutates `.rapid-os/runs/<run-id>/`.

```bash
rapid evidence list --run <run-id> [--json]
rapid evidence show --run <run-id> <evidence-id> [--json]
rapid evidence add --run <run-id> --input <file> [--json]
rapid evidence verify --run <run-id> [--json]
```

---

## Behavioral Evals (`rapid eval`)

Run deterministic, offline behavioral evaluations (`BehavioralEvaluator` → `EvaluationReport`, `schema_version = 1`, `EvaluationVerdict`: `pass`, `pass_with_waivers`, `fail`, `unverified`) over an `ExecutionContract`, `RunState`, `RunEvidence[]`, `BehavioralRuleset` (`version = 1`), and `extra_capability_ids`, and inspect append-only evaluation reports under `.rapid-os/evals/<run-id>/reports/`.

- **Read-only by default**: `list`, `show`, and `run` (unless `--write` is passed)
- **State-writing**: `run --write`

> **Product Truth**: `GateDisposition.ACKNOWLEDGED` is a declaration, not proof (`UNVERIFIED` without qualifying evidence). `EvaluationVerdict.PASS` means the configured Phase 6 evidence rules are satisfied by the exact recorded evidence set; it does not mathematically prove the software has zero bugs or that requirements are complete. Every persisted `EvaluationReport` undergoes mandatory semantic replay via `BehavioralEvaluator` when loaded or validated (`RAPID1223` on any discrepancy).

```bash
rapid eval run --run <run-id> [--ruleset {1,2}] [--require <capability-id>] [--write] [--require-pass] [--json]
rapid eval list --run <run-id> [--json]
rapid eval show --run <run-id> [--revision <n>] [--json]
```

Options for `run`:
- `--ruleset {1,2}`: Behavioral ruleset version to evaluate against (defaults to `2`).
- `--require <capability-id>`: Extra additive canonical capability ID to evaluate (repeatable).
- `--write`: Persist append-only EvaluationReport snapshot.
- `--require-pass`: Exit non-zero unless verdict is `pass` or `pass_with_waivers`.
- `--json`: Emit pure EvaluationReport JSON.

---

## Check & Verification (`rapid check`)

Execute direct argv commands without shell, capture combined output into `.rapid-os/scratch/checks/<run-id>/<n>.log`, parse test outcomes (unittest/pytest), and register append-only `RunEvidence` on success (`exit_code == 0` for `expect=pass`, or failing exit/counts for `expect=fail`).

```bash
rapid check [--task <task-id>] [--gate <gate-id>] [--kind {test,command}] [--expect {pass,fail}] [--json] -- <argv...>
```

Options:
- `--task <task-id>`: Bind recorded evidence to a task (e.g. `T001`).
- `--gate <gate-id>`: Bind recorded evidence to a gate (e.g. `gate.baseline`, `gate.tests`).
- `--kind {test,command}`: Explicitly choose `test_result` or `command_result` evidence kind (inferred from argv if omitted).
- `--expect {pass,fail}`: Expected outcome of the check (defaults to `pass`). If `fail`, evidence with `expectation="fail"` is registered only when the check fails (e.g. reproducing a defect before a fix).
- A check bound to `gate.baseline` or `gate.tests`, or to a task of a mode that needs tests (every mode but `research`), is recorded as `test_result` with its count when the output has a summary of pytest, unittest, vitest, jest, `cargo test` or `go test -v`, **even if its argv is not exactly `test_command`** (`pytest -q` run through `uv run` is still `pytest`). `--kind command` keeps it a plain `command_result`. `rapid check` always prints `Tests: N passed, M failed, K skipped` for a test run, and when a check that should be a test run has no readable summary it says so (`No se pudo leer un conteo de tests...`): its evidence has no count. `go test` without `-v` prints no per-test counts.
- Each test run keeps its `command` in the evidence payload (optional), and every check keeps `tree`: the digest of the working tree when it ended (the files that differ from `HEAD`, tracked or not, with their hashes; `.rapid-os/` and tool artifacts left out; the map is in `.rapid-os/scratch/trees/`). `rapid next` before asking for approval, `rapid approve` and `rapid finish` compare the tree with the one the last `gate.tests` check saw: if it changed (a test deleted, a file edited), `rapid next` returns `verify` with the new check, `approve` and `finish` refuse with `RAPID1423`, and all of them name the changed files. Rejecting a gate does not need a new check. A check that predates the fingerprint, no `gate.tests` check, or a folder git cannot read are not judged.
- `--json`: Output execution and recorded evidence details as JSON.
- The executable of the argv is resolved with the `PATH` and `PATHEXT` before it runs (`pnpm`, `npm`, `yarn` are `.cmd` shims on Windows and `subprocess` does not find them without a shell); the argv compared with `test_command` and recorded in the evidence is the one that was typed.
- `-- <argv...>`: Vector of command arguments to run directly without shell.

---

## Task Lifecycle Management (`rapid task`)

Manage and transition tasks for the active run session (`.rapid-os/session.json`).

```bash
rapid task start [<task-id>] [--reason <text>] [--json]
rapid task done [<task-id>] [--reason <text>] [--no-check] [--json]
rapid task skip <task-id> --reason <text> [--json]
```

Subcommands:
- `start`: Mark a task as `in_progress`. If `<task-id>` is omitted, transitions the first `pending` task.
- `done`: Mark a task as `done`. Runs verification tests (`test_command`) and records evidence unless `--no-check` is provided. If `<task-id>` is omitted, resolves the current `in_progress` task (`RAPID1306` if none or ambiguous).
- `skip`: Skip a task with a mandatory `--reason` (`RAPID1306` if reason omitted).

---

## Intent & Workflow Layer (`rapid start`, `rapid next`, `rapid finish`, `rapid approve`, `rapid attach`, `rapid hook`, `rapid status`, `rapid abort`)

Manage end-to-end intent porcelain sessions (`.rapid-os/session.json`).

### `rapid start`
Initialize or resume a governed intent workflow session. Mode is mandatory when creating a new run, and optional when `--resume` is passed (loaded from `.rapid-os/session.json`).

```bash
rapid start [{feature,bugfix,refactor,hardening,research}] [<objective>] [--spec-file <path>|-] [--spec <id>] [--harness <harness-id>] [--resume] [--worktree] [--json]
```

A new run needs a git repository, because Rapid OS observes the run's changes with git: in a folder that is not a work tree (or without git installed) `rapid start` fails first with `RAPID1416` (before the empty-repository refusal) and writes nothing to `.rapid-os/runs` or `session.json`. `rapid setup finish` and `rapid init` create the repository, so this only happens in a folder where it was removed.

Each mode has its own playbook in `templates/modes/` (`spec_template` and per-action instructions):

| Mode | Behavior |
| :--- | :--- |
| `feature` | Default loop: baseline, tasks, verification, human gate. |
| `bugfix` | The baseline is taken at `start`, before the reproduction test exists. While `T001` ("Reproducir con un test en rojo") is `in_progress` without a passing `reproduction.T001` assertion, `rapid next` proposes `rapid check --expect fail --task T001 -- <test_command>`; once the failure is recorded it proposes `rapid task done T001 --no-check` (the suite is red by design). |
| `refactor` | The baseline is mandatory. Once all tasks are terminal, if the latest `test_result` has fewer passed tests than the baseline, `rapid next` returns `blocked` with the difference (a Conductor rule, not an evaluator rule). |
| `hardening` | Risk is `high`, so the contract requires an isolated workspace (see `--worktree`) and a `gate.review`. |
| `research` | Spike: low risk, no baseline and no mandatory tests. Findings are recorded with `rapid attach`. |

A **brand-new repository** (no source code outside `docs/` and hidden folders, and no tests: `pyproject.toml` or `package.json` alone are configuration, not code) changes `rapid start`:

- With no commit in the repository (so no worktree can be created), a run that the policy would isolate (`RAPID1334`) goes in the current workspace instead: the contract records `isolation_waived: "no_commits"` (omitted from every other contract), the human gates (`gate.migration-review`, `gate.security-review`...) stay, `rapid start` notes it and `rapid status --json` shows it. A repository with commits is never waived.
- `feature` adds the scaffold as the first task, `T001: Minimal scaffold with a passing test` (your tasks move down one number so the text matches the contract IDs). If the project has no `test_command`, the task ends with `Configure the command with rapid setup set test-command <cmd> before closing it`, and the contract has **no `gate.baseline`** because there is no baseline to capture. The run starts `active`; `rapid start` reports changes in the optional top-level `notes[]` output (`Note: ...` in text mode), including renumbering (`T001→T002, T002→T003`). `rapid next` always provides the run's IDs. Close the scaffold task with a passing `rapid check`; the contract records the reason in the optional `baseline_waived: "empty_repository"` field (also in `rapid status --json` under `run`). This field is omitted from other contracts, so projects with code or tests are unchanged. `rapid status` and `rapid finish` print `No baseline: new project` (to stderr with `finish --json`). With `--spec <id>`, the waiver applies only if that spec already begins with the scaffold task.
- `bugfix`, `refactor`, and `hardening` fail with `RAPID1413` without writing anything: `There is no code to <fix|refactor|harden>; use /rapid-feature`. `research` is unaffected.
- A repository with code but no tests keeps `gate.baseline`; the `run_baseline` instruction suggests creating a passing test in a task, or using the `research` mode.

Options:
- `--worktree`: When the contract requires `isolated_required`, create a git worktree at `../<repo>-<run-id>` on branch `rapid/<run-id>` from `HEAD`. The ledger (`.rapid-os/`, `session.json`) stays in the main repository; `session.json` stores `workspace_path`, `rapid check`/`rapid task done` run the commands in that directory, `rapid finish` collects the changes from it, and the run records `workspace` evidence with `mode: isolated` (which acknowledges `gate.workspace-isolation`). Without the flag the run stops at `blocked` and `rapid next` proposes `rapid start --resume --worktree`. The flag has no effect when the contract does not require isolation. Uncommitted changes of the main checkout are not part of the worktree (it starts from `HEAD`). `rapid abort` keeps the worktree on disk.
- `--spec-file`: if a spec with the same identity (`id` or title) and the same content already exists (a previous `rapid start` created it and then failed, e.g. `RAPID1004`), it is reused; if the content differs, `rapid start` exits with `RAPID1322` and suggests `rapid start <mode> --spec <id>`.
  - **Input encoding.** Text handed over as data is read as bytes and decoded as UTF-8 (a BOM is accepted), whatever the console code page is: `rapid start <mode> --spec-file -`, `--spec-file <path>`, and `--file -` / `--file <path>` of `rapid setup doc` and `rapid setup stack --custom`. On Windows `sys.stdin` would otherwise read with cp1252 and store `Ã³` for `ó`. Text that is not valid UTF-8 is refused with `RAPID1424` and nothing is stored. `rapid doctor` warns with `RAPID1425` when a saved spec or onboarding document already holds UTF-8 read as cp1252 (`Ã¡`, `Ã©`, `Ã³`, `Ã±`...); saved specs are never rewritten (the registry has digests): create a new revision with `rapid spec revise`. `rapid start` (and `rapid doctor`) warn with `RAPID1426` when `test_command` cannot be run — its first element is not on the `PATH` (Windows tries `.cmd` and `.exe` too) nor a file of the project — and propose the stack catalog's command, listing the command of each component and offering `rapid setup set test-command --recommended` (with the onboarding finished it already writes `config.json`).
- `session.json` also records `start_untracked`: the untracked files that existed before `rapid start`, which `rapid finish` does not attribute to the run.

### `rapid next`
Query the deterministic next workflow action without mutating state. When a human review was rejected (`rapid approve --reject`) it returns `blocked` with the command `rapid abort`: the gate stays `FAIL` for that run and a new run is needed. Agents must not run `rapid abort` on their own in that case. That action carries `rejection`: `{gate_ids[], reviewer, reason}`, the text the person wrote with `--reason` (`reviewer` and `reason` are `null` for a review recorded before the reason was kept), and the same text is in `instructions`. `/rapid-next` and the mode shortcuts tell the agent to use it when it opens the new run.

After `rapid finish` the session still points at the closed run, but `rapid next` does not stop at `done` while the brief has open stories: it returns `author_spec` with the `seed` of the next unchecked story (and a `notes[]` line saying the previous run ended). It returns `done` when there is no brief or no open story.

```bash
rapid next [--json]
```

With no active run, `rapid next` (and `rapid start feature` without a spec) returns `author_spec`. When the project has a product brief written by `rapid setup doc brief` (`docs/PRODUCT_BRIEF.md`, with `rapid-doc` frontmatter) that still has open stories, the `feature` action carries an optional `seed` object, omitted otherwise, so the output without a brief is exactly the same as before:

- `seed.source`: the brief (`docs/PRODUCT_BRIEF.md`).
- `seed.confirmed`: `false` while the brief is an unconfirmed draft (an assumption), `true` when a person provided or confirmed it.
- `seed.stories[]`: `{id, text}` for every unchecked story (`- [ ] H001: ...`) of the stories section, in order. They are all listed, not only the first, so the agent can pick the one that makes sense to start with (for dependencies).
- `seed.business_doc`, `seed.data_model_doc`: `docs/BUSINESS_RULES.md` and `docs/DATA_MODEL.md` when those documents exist, otherwise `null`.

### `rapid finish`
Collect repository changes, evaluate machine gates, and close the run.

```bash
rapid finish [--json] [--no-tick]
```

The `file_change` evidence it records (capability `repository.write`) lists the files the run changed in the project: tracked changes since the run started plus new untracked files, without `.rapid-os/` and without tool artifacts (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`, `.nox`, `node_modules`, `.venv`, `venv`, `*.pyc`, `*.pyo`, `.coverage*`), even in a project with no `.gitignore`; with no real change no `file_change` is recorded and the verdict is not `pass`.

`rapid finish` ends with `Rapid OS no hace commit: revisa los cambios y haz commit tú` (to stderr with `--json`): Rapid OS never commits, and neither do the shortcuts.

In text mode it prints the report revision and verdict (`Evaluation report 0001 for run '<run-id>': verdict PASS`). When the verdict is `unverified` and `capability.repository.write.observed` did not pass, it adds one line explaining why: `No file changes were observed: the folder is not a Git repository` or `... Git works but the run did not change project files (outside .rapid-os/ and tool artifacts)`. With `--json`, the same text is the optional report field `unverified_reason` (also sent to stderr). When the run spec cites a story with the tag `story:<ID>` (for example, `story:H002`; the `/rapid-feature` shortcut asks the agent to add it), `finish` also updates the story in `docs/PRODUCT_BRIEF.md`:

- Verdict `pass`: it ticks the story. Inside the `## Historias` section (or its alias) only the line `- [ ] H002:` becomes `- [x] H002:`; the previous file is copied to `.rapid-os/backups/`, the frontmatter `sha256` follows the new body, `source` and `status` stay (a draft stays a draft) and the agent files are regenerated. It prints `H002 marcada como hecha en docs/PRODUCT_BRIEF.md`. A story that is already ticked or does not exist changes nothing and says so; a brief without `rapid-doc` frontmatter is not touched (`Marca H002 ...` is suggested instead).
- Any other verdict: the brief is not changed and `finish` prints `H002 will be marked when the run passes`. `pass_with_waivers` only suggests `Mark H002 complete in docs/PRODUCT_BRIEF.md`.
- `--no-tick`: the previous behavior, it only suggests `Marca H002 como hecha en docs/PRODUCT_BRIEF.md` on a passing verdict.

These lines go to stderr with `--json`, so stdout stays the report. Finishing a run that already ended is idempotent and records no new evidence or report: it prints the stored verdict (the latest report) and exits 0 only if that verdict is `pass` or `pass_with_waivers`, otherwise 1; a run that ended without a report (for example `cancelled` or `failed`) prints `already ended (<outcome>)` on stderr and exits 1.

### `rapid approve`
Review a human gate. Without arguments it lists the pending human gates of the active run (read-only; no TTY needed). With a gate id it approves it, or with `--waive` / `--reject` waives or rejects it. Changing a gate requires an interactive terminal (TTY) and cannot be executed inside agent child sessions (`CLAUDE_CODE_CHILD_SESSION == 1`) nor under an agent harness: if any ancestor process is Claude Code (`claude`/`claude.exe`), it fails with `RAPID1310` even with a TTY and without the session variables (unreadable ancestry never rejects; `rapid doctor` reports it with `RAPID1319`). Without a TTY every case fails with `RAPID1310` (a stdin closed during the confirmation, EOF, is reported the same way).

```bash
rapid approve
rapid approve <gate-id> [--reviewer <name>]
rapid approve <gate-id> --waive --reason <text> [--reviewer <name>]
rapid approve <gate-id> --reject --reason <text> [--reviewer <name>]
```

Options:
- `--reviewer <name>`: Reviewer recorded in the evidence. Defaults to `git config user.name`; if it is not set, the name is asked on the terminal (`RAPID1331` if left empty).
- `--waive`: Waive a gate instead of approving it. Only gates that the contract marks as waivable (for example `gate.review`) can be waived, and `--reason` is mandatory. Confirm by typing `dispensar <gate-id>`.
- `--reject`: Record a `review` evidence with outcome `changes_requested`. This leaves the gate in `FAIL` for the rest of that run: `rapid next` returns `blocked` with the command `rapid abort`, and a new run is needed. `--reason` is mandatory. Confirm by typing `rechazar <gate-id>` (typing `aprobar <gate-id>` does not reject).
- `--reason <text>`: Reason for `--waive` or `--reject` (`RAPID1333` if missing). A rejection keeps it in the evidence (`payload.reason`) and `rapid next` hands it to the agent (see `action.rejection`).

After the last pending human gate is approved, `rapid approve` prints `Siguiente: rapid finish (o /rapid-next en tu agente). Tras finish el run ya no se puede cancelar.` Approving, waiving or rejecting a gate that is already decided is `RAPID1332`, and the message says how to take it back: `rapid abort` before `rapid finish`; after `rapid finish`, `git revert` and a new run. The full procedure is in [Undo an approval](./guides/undo-approval.md).

### `rapid attach`
Record a file of the project (or of the run workspace) as `artifact` evidence with producer `rapid:attach`. The evidence is linked to `--task` or, if omitted, to the only `in_progress` task, so it backs the task assertion; research spikes use it instead of tests. Files under `.rapid-os/` cannot be attached.

```bash
rapid attach <path> --label <text> [--task <task-id>]
```

### `rapid hook`
Entry points for the Claude Code hooks. They read the hook JSON that Claude Code writes on stdin (`session_id`, `cwd`, `tool_name`, `tool_input`, `stop_hook_active`) and are meant to be wired in `.claude/settings.json` (see `rapid shortcuts install --hooks`), not typed by hand. They never fail the agent: invalid stdin, a missing project or a corrupt `.rapid-os/` produce no output and exit 0, and the cause is appended to `.rapid-os/scratch/hooks.log`.

```bash
rapid hook stop
rapid hook pre-tool
```

- `stop`: blocks the stop (`{"decision": "block", "reason": ...}`) only while `rapid next` proposes `run_baseline`, `activate`, `implement_task`, `verify` or `finish`; the reason is the instructions plus the exact command. It never blocks on `author_spec`, `await_human_approval`, `blocked` (including the `rapid abort` proposed after a rejected review), `done` or when there is no session. After `hooks.max_stop_blocks` consecutive blocks for the same action (default `3`, set in `.rapid-os/config.json` as `{"hooks": {"max_stop_blocks": 3}}`; `0` disables blocking) the agent is allowed to stop; the count lives per `session_id` in `.rapid-os/scratch/hooks.json` and restarts when the action (`kind` + `task_id` + `gate_ids`) changes.
- `pre-tool`: denies (`permissionDecision: "deny"`) shell commands (`Bash`, `PowerShell`) that run `rapid approve`, `rapid run gate`, `rapid run status`, `rapid evidence add`, `rapid spec status` or `rapid abort` (also through `python -m rapid_os`, `python rapid.py`, absolute paths, environment prefixes, `;`, `&&`, `||`, `|`, `$(...)`, backticks, shells with `-c`, `script -c`/`su -c` and `find -exec`; `rapid approve --help` is allowed), any command that removes or redefines `CLAUDE_CODE_CHILD_SESSION` or `CLAUDECODE` (`env -u`, `env -i`, `unset`, `VAR=`/`VAR=0` prefixes or `export`, `Remove-Item Env:`), which would lift the guard that makes `rapid approve` refuse to run inside an agent session, and any write inside `.rapid-os/` (`Write`, `Edit`, `MultiEdit`, `NotebookEdit`, or a shell command using `>`, `>>`, `tee`, `cp`, `mv`, `rm`, `sed -i`, ...). `rapid status`, `next`, `check`, `task`, `attach`, `finish` and `start` stay allowed. The detection of shell commands is best-effort: it cannot stop an agent determined to hide a command.
- Project resolution: from `cwd` upward to the first `.rapid-os/`; inside a worktree created by `rapid start --worktree` the ledger of the main repository is used.
- Input: the payload is decoded as UTF-8 (a BOM is accepted). When it is not valid JSON the hook ignores it, exits `0` and writes to `.rapid-os/scratch/hooks.log` how many bytes arrived and how they start (`stdin is not valid JSON (57 bytes, starting with b'\xff\xfe{\x00...' (hex ff fe 7b 00 ...)); ignored`).
- Manual test: do not pipe the payload from Windows PowerShell 5.1: its pipeline re-encodes the text (UTF-16 or with a BOM) before `rapid` reads it, so it arrives invalid. Redirect a file instead, from `cmd`: `cmd /c "rapid hook pre-tool < payload.json"` (PowerShell 7 and POSIX shells can pipe: `cat payload.json | rapid hook pre-tool`).

### `rapid status`
Display active session, run state, tasks, gates, and last evaluation verdict.

```bash
rapid status [--json]
```

### `rapid abort`
Cancel the active run and remove the session file.

```bash
rapid abort [--reason <text>]
```

---

## Architecture (`rapid arch`)

Verify the project's modular-monolith architecture rule. Read-only.

```bash
rapid arch check [--json] [--new-only]
```

- `check`: reads `.rapid-os/standards/architecture.json` and the imports of the files under its `modules_root` and `shared_root` (Python with `ast`; TypeScript/JavaScript, including the script of `.vue`, `.svelte` and `.astro` files, Go, Java, Kotlin, C#, Rust and PHP with regular expressions; no code is executed; Ruby on Rails delegates to `bin/packwerk check`) and reports one `RAPID1420` per violation, with file, line, import and rule: a layer importing a layer it may not (`layer`), a module importing anything but another module's public entry (`cross_module`), `shared` importing a module (`shared`), the `__init__.py` at the root of a Python module importing anything but the module's own `public.py` (`init_reexport`, which closes the back door of `from app.modules.pagos import Repo` reaching an inner layer through the package), or `domain` importing a forbidden library (`domain_forbidden_import`). Relative imports are resolved, and imports written from the component's root (`app.modules...`, `@/...`, `src/...`) are resolved inside its `root` when the component lives in a subfolder (`backend/`, `frontend/`). A Python file that does not parse (syntax newer than the Python running Rapid OS, for example `except A, B:` on 3.14) is read line by line, with a `WARNING <file>: leído sin AST: sintaxis más nueva que el Python de Rapid OS (3.x)`, and is never skipped as invalid. Only directories under `modules_root` count as modules: a file directly in it (its `__init__.py`) is not one. Exit `1` with violations (also an unreadable `architecture.json`, reported as `RAPID1420`); exit `0` without violations, without modules yet, or, with a warning, when there is no `architecture.json`.
- `--new-only`: fail only for the violations the active run added. `rapid start` photographs the violations the project already has (file, rule and import; stored as `start_architecture` in `session.json`), and with `--new-only` those are listed as `(previa)` debt, counted in `N violaciones previas; no bloquean este run` and left out of the exit code, so a run does not fail for code it did not write. `rapid next` proposes the gate with this flag and `rapid finish` re-checks the same way. In a `refactor` run a previous violation in a file the run touched counts as new. The photo counts occurrences (a second identical import in a file that had one is new), and outside refactor a violation whose file was moved stays previous (matched by rule and import). With no active run, a closed run or a run without a photo every violation is previous. Without the flag, `check` lists and fails on all of them.
- When the entry layer (`api/`, `web/`, `Http/`, `ui/`...) imports `infrastructure/` (or `data-access/`), the `layer` message ends with where the stack puts the composition (`composition` in `architecture.json`; for `python-fastapi`: `app/main.py` or the module's `public.py`). A rule written before the field still loads.
- `--json`: `{schema_version, ok, language, modules[], checked_files, violations[{code, rule, file, line, import, message, status}], new_only, counts{new, previous}, baseline, skipped[], warnings[]}` (`status` is `new` or `previous`, see `--new-only`; `baseline` is the active run's id or `null`); without `architecture.json` it carries a `warning` instead.
- In a run's worktree (which has no `.rapid-os/`), when the current directory has no `architecture.json` and there is an active session whose contract includes `gate.architecture`, the rule is read from the session's main project and the code judged is the current directory's. If the run demands the gate and no rule is found, it exits `1` with `RAPID1420 el run exige gate.architecture y no hay architecture.json` (`error` in `--json`); outside a run a missing rule stays a warning with exit `0`.
- An existing project with global layers is only judged inside `modules_root`: the rule applies to new code, and the migration is done with `/rapid-refactor`.
- `rapid setup finish` (and `rapid init`) write `architecture.md` (the rule, for the agent, with the names of each stack's language and a table that maps them to the canonical responsibilities) and `architecture.json` (the rule, for Rapid OS) to `.rapid-os/standards/` for every backend and frontend stack of the catalog; `generic`, `custom` and `docs-modern` get neither. A project with a separate frontend and backend gets two rules (`backend/` and `frontend/`, key `rules`). An existing file is not overwritten. See `docs/concepts/architecture.md`.
- **Gate:** when `architecture.json` exists, the contract of a `feature`, `bugfix` or `refactor` run includes the machine gate `gate.architecture` (kind `architecture_check`, post-execution, required, not waivable). `rapid next` proposes it like `gate.tests`: `rapid check --gate gate.architecture -- rapid arch check --new-only`, and `rapid finish` is not `PASS` until it is satisfied by a passing `command_result`. `rapid finish` also runs the check again on the final state of the code before the verdict: if it fails (a violation added after the gate passed), it prints `RAPID1422` with every violation, exits `1` and leaves the run open with no verdict, so the code can be fixed and `rapid finish` run again. (`rapid check` runs a leading `rapid` as the Rapid OS that is running, not as whichever is on `PATH`.)

---

## Harness Shortcuts (`rapid shortcuts`)

Generate the `/rapid-<mode>` commands of each coding harness from a single source (`templates/shortcuts/`). The shortcuts teach the agent only the loop (`rapid next --json` → `rapid start <mode> --spec-file -` → `rapid check -- <cmd>` → `rapid approve` by a person); they do not list plumbing commands, and they never run `rapid approve`, `rapid run gate` or `rapid evidence add`.

```bash
rapid shortcuts install [--harness <id> ...] [--only <shortcut> ...] [--global] [--dry-run] [--json]
rapid shortcuts list    [--harness <id> ...] [--only <shortcut> ...] [--global] [--json]
rapid shortcuts remove  [--harness <id> ...] [--only <shortcut> ...] [--global] [--dry-run] [--json]
```

Options:
- `--harness <id>`: Harness to target (`claude`, `codex`, `antigravity`, `cursor`, `vscode`). Repeatable. Without it, the supported entries of `tools` in `.rapid-os/config.json` are used; a project without that file must pass `--harness` (`RAPID1312`).
- `--only <shortcut>`: Restrict the command to this shortcut (repeatable), e.g. `--only rapid-init`. An unknown name is `RAPID1413`.
- `--global`: Use the user-level skills folder of each harness, under your home directory, instead of the project. It needs `--harness` (no project config is read). With `--hooks` (Claude Code) inside a project it installs the skills for the user and the hooks in the project's `.claude/settings.json` without copying the skills there; outside a project (no `.rapid-os/`) it is `RAPID1413` with that indication. Only harnesses whose official documentation names a user-level folder support it: `claude` (`~/.claude/skills`), `codex` (`~/.agents/skills`), `cursor` (`~/.cursor/skills`) and `antigravity` (`~/.gemini/config/skills`, the App and IDE folder). `vscode` has no documented folder: `--global` for it is `RAPID1413` and nothing is written. With `--json`, `install` adds `"scope": "global"`.
- `--dry-run`: Show what would be written or deleted without touching the filesystem (`install`, `remove`).
- `--hooks`: With `install`, also merge the Rapid OS hooks (`Stop` and `PreToolUse`, command `rapid` with arguments `hook stop` / `hook pre-tool`) into the project's `.claude/settings.json`; with `remove`, also remove them. Requires the `claude` harness (`RAPID1337`). Other keys and hooks of the file are left untouched, an existing file is backed up as `.bak`, installing twice writes nothing, and `remove` only deletes the handlers it owns (and the file itself when nothing else is left in it). An unreadable `settings.json` is reported with `RAPID1338` and never overwritten. The handlers use Claude Code's exec form, so `rapid` must be on the `PATH` of the machine running Claude Code; `rapid doctor` warns (`RAPID1339`) when hooks are installed and `rapid` is not found.
- `--json`: Emit `schema_version`, `command`, `harnesses`, `files[]` (`path`, `shortcut`, `harnesses`, `action`) and, for `install` and `list`, `skipped[]`.
- `warnings` (`install` and `list`): always a list of objects `{code, message, ...}` (`RAPID1315` and `RAPID1316` carry `shortcut`/`mode` or `path`; `RAPID1321` is described below). In `install` it is always present (empty when there is nothing to warn about); in `list` it is optional and omitted when empty. When the selection leaves the same `/rapid-*` in two folders that one tool reads (`cursor` or `vscode` together with `claude`, `codex` or `antigravity`), each overlap prints `WARNING RAPID1321` on stderr (also in `rapid init --shortcuts`) and, with `--json`, adds an object `{code, message, reader, harnesses, folders}` to `warnings`. In `install` the object is appended to the `warnings` list that already holds the text warnings; in `list` the field is optional and omitted when empty. It never changes the exit code or what is written. See [Si combinas harnesses](guides/shortcuts.md#if-you-combine-harnesses).

Generated files:

| Harness | Path | Invocation | Official documentation |
| :--- | :--- | :--- | :--- |
| Claude Code | `.claude/skills/<name>/SKILL.md` | `/<name>` | https://code.claude.com/docs/en/skills |
| Codex | `.agents/skills/<name>/SKILL.md` | `$<name>` or `/skills` | https://developers.openai.com/codex/skills |
| Antigravity | `.agents/skills/<name>/SKILL.md` | `/<name>` | https://antigravity.google/docs/skills |
| Cursor | `.cursor/skills/<name>/SKILL.md` | `/<name>` | https://cursor.com/docs/context/skills |
| VS Code / Copilot | `.github/prompts/<name>.prompt.md` | `/<name>` | https://code.visualstudio.com/docs/copilot/customization/prompt-files |

Behavior:
- Shortcuts: `rapid-feature`, `rapid-bugfix`, `rapid-refactor`, `rapid-hardening`, `rapid-research`, `rapid-next`, `rapid-status`, `rapid-approve`. `rapid-approve` sets `disable-model-invocation` where the harness supports it (Claude Code, Cursor); it shows pending human gates and the exact `rapid approve <gate>` command for the person's own terminal.
- Only Claude Code runs the `` !`rapid next --json` `` line before the prompt is sent (a failing command aborts the skill); the other harnesses get the instruction "run `rapid next --json`" as plain text.
- Mode shortcuts are generated only for modes with a playbook in `templates/modes/`. `list` and `install` report the omitted ones with `RAPID1315`; running `rapid shortcuts install` again after a playbook is added creates the missing ones.
- Codex and Antigravity share `.agents/skills`; when both are selected each file is written once.
- Every file carries the marker `<!-- generated by rapid shortcuts -->` right after the frontmatter. `install` is idempotent: identical content is not rewritten; different content is first backed up as `.bak`. `remove` deletes only files that carry the marker (`RAPID1317` for those left untouched) and the then-empty `<name>/` folder. Because `.agents/skills` is shared, removing for one of Codex/Antigravity removes the files for both.
- `rapid init` offers to install the shortcuts at the end (interactive terminals only, default no). `rapid init --shortcuts` installs them for the selected agents without asking.

## Onboarding (`rapid setup`)

Completes the onboarding with commands only, the way `rapid start`/`rapid next` drive a run: every command returns the next decision, so a harness can loop on `rapid setup next --json` until it gets `done`. `next` and `show` are **read-only**: they never write, not even `.rapid-os/setup.json`. `set`, `stack`, `doc` and `finish` write.

```bash
rapid setup next [--json]
rapid setup show [--json]
rapid setup set stack|topology|archetype|ai|services|agents|test-command <value> [--refresh] [--json]
rapid setup set test-command --recommended [--json]
rapid setup stack --custom --file <path|-> [--json]
rapid setup doc <id> --source provided|drafted --file <path|-> [--replace] [--json]
rapid setup doc <id> --skip | --confirm | --reopen | --from-legacy [--replace] [--json]
rapid setup review --done [--json]
rapid setup story <ID> --reopen [--json]
rapid setup finish [--json]
```

- `story <ID> --reopen`: untick one story of the product brief (`- [x] H002: ...` becomes `- [ ] H002: ...`), the inverse of the tick `rapid finish` does. Only that line changes (the id is matched without regard to case, the frontmatter `sha256` follows the body, `source` and `status` stay, the previous file goes to `.rapid-os/backups/`). Use it after a `git revert` of the story's code so `rapid next` offers it again. Already open: success, nothing changes. Unknown story, a brief without `rapid-doc` frontmatter or no `--reopen`: `RAPID1413`. See [Undo an approval](./guides/undo-approval.md).
- `set test-command --recommended`: apply the command the stack catalog proposes for the decided stacks (the one `set_test_command` shows as `recommended`), without typing it; with two components it is the combined command. `RAPID1413` if the catalog has none, or if a value or another key is given.
- `next`: the next decision, in this order: `choose_stack` (once per component of the topology, in the topology's order; with no topology yet the first one can be of any component), `choose_topology`, `choose_archetype`, `choose_ai`, `choose_agents`, `set_test_command`, `resolve_doc` (`brief`, `business`), `choose_services`, `resolve_doc` (`data-model`, `architecture`, `deployment`), `review_drafts`, `finish`, `done`. `--json` emits one object with `schema_version`, `kind` and the fields of that decision:
  - `choose_stack`: `facts[]` from the scanner, `component` (`frontend`, `backend`, `docs`...; absent while the topology is undecided), `components[]` and `decided` (the stacks already chosen), `options[]` (`id`, `source`, `summary`, `language`, `score`, `fits[]`, `avoid_if[]`, `compatible_topologies[]` and, for a stack of the catalog, `component`, `covers[]`, `monolith`, `factors`, `factor_sources`, `package_manager`, `default_test_command[]` and `supported_services[]`) sorted by a deterministic score (language and framework match), `recommended` (what the scanner detected for that component, or `null`), `questions[]` from `templates/setup/stack-questions.json` (always: the brief may not answer them), `instruction` (how the agent recommends: ask what the brief does not answer, recommend one option and an alternative with the `factors`, claim nothing the catalog does not say, and let the person decide) and `command` (`rapid setup set stack <id> --component <component>`). `alt_command` is the invocation for a stack outside the catalog (`rapid setup stack --custom --file -`). A topology's `baas` component asks for no stack. A finished onboarding is not reopened because its topology asks for a component it never had to decide.
  - `choose_topology`: only the topologies compatible with every stack already chosen, plus `recommended`.
  - `set_test_command`: `recommended` is what the repository already has (a `package.json` with a test script, pytest) or, in an empty repository, the command of the decided stacks from the catalog (`test_commands` in each stack sidecar: `root` and `subdir`, with `{root}` for the component's folder), run from the project root and pointed at the component's folder (`uv run` for a Python backend in `backend/`, `pnpm` for a frontend in `frontend/`). With two components in their own folders `recommended` is one argv (`python -c ...`) that runs both and fails if either fails, and `components[]` (`component`, `stack`, `root`, `command`) lists each command.
  - `resolve_doc` for `architecture` carries `standard[]` and `standard_instruction`: per component, the structure `standards/architecture.md` will state when the onboarding ends (`modules_root`, `shared_root`, `module_pattern`, `public_entry`, `public_contract`, `layers[]` with `dirs` and `may_import`, and `dependency_rules[]`), taken from the same catalog. The draft cites it instead of inventing a public entry point that the standard then contradicts.
  - `choose_agents`: `recommended` is the harness detected from `RAPID_HARNESS`, the Claude Code marker, `default_harness` or a single supported harness in `tools` of the config, or `null` (the `cursor` fallback is not a detection). `set_test_command`: `recommended` is `["npm", "test"]` when `package.json` has `scripts.test`, pytest when detected, or the unittest discovery command for a Python project with a tests directory; otherwise `null`.
  - `choose_services`: `roles[]`, `catalog[]` (`id`, `role`, `image`, `ports[]`, `connection_env`), `suggested_services[]` (the stack's minimum, not a decision), `when_values` (`now`, `later`), `instruction` and `command` (`rapid setup set services <role>:<engine>[@now|@later],...`; `none` is valid). `rapid setup set services` rejects an unknown role or engine, or a pair that does not fit, with `RAPID1413`, and an engine the stack does not support with `RAPID1402`. For `data-model`, `architecture` and `deployment`, `resolve_doc` also carries `services[]` (only the decided ones) and, when the document has them, `conditional_sections[]` (required while their condition holds: `Base de datos local` in `data-model` with a database service). `setup finish` writes `compose.yaml`, `.env.example` and `.env` in `.gitignore` for the `@now` services of an empty repository (or adds the missing ones to an existing compose file, never modifying what is there; an unreadable YAML is left untouched with a warning) and announces them in `added_files`/`planned_files`. While `compose.yaml` exists with a `@now` service, `rapid setup finish`, `rapid status` and `rapid validate` list the person action `local-services` (`docker compose up -d`). See [Infrastructure services](concepts/infrastructure-services.md).
  - `review_drafts`: only when some document is an unconfirmed draft and the review is not closed (it is skipped when every document is `provided`, confirmed or skipped, and it never reopens a finished setup). `drafts[]` (`doc`, `file`, `title`), `consequences` (`confirm` and `keep_draft`: what each decision means, the texts the shortcut reads to the person), `commands` (`confirm`: `rapid setup doc <id> --confirm`, `done`: `rapid setup review --done`) and `command` (the `done` one).
  - `resolve_doc`: `doc`, `target` (`docs/<FILE>.md`), `choices` (`provided`, `drafted`, `skip`), `questions[]`, `required_sections[]` (`id`, `titles[]`), `max_chars` and `command` (the invocation that writes the document), all read from `templates/setup/docs/<id>.json`. For `business` it also carries `legacy_source` (`.rapid-os/standards/business.md`) when that file has content and `docs/BUSINESS_RULES.md` does not exist.
  - Every action except `done` carries `command`, the argv that resolves it; `finish` and `done` list `unconfirmed_docs[]`: drafted documents nobody has confirmed.
- `set` after `finish`: when the onboarding is already finished and no decision is left open, `rapid setup set <key> <value>` applies the change right away (`config.json` or the standards, like `finish` would) and leaves `finished: true`; it does not reopen the onboarding. `rapid setup set test-command <cmd>` is how a project that accepted `none` gets its test command: `rapid task done` needs it (`RAPID1301` suggests this command), and the scaffold task of an empty repository says so when there is none.
- `doc <id> --source drafted` rejects a body where a `?` sits between two letters or opens a word (`vac?os`, `Decisi?n`, `?xito`), which is what a pipe that is not UTF-8 leaves of the accents (`RAPID1415`; code blocks, inline code and URLs are ignored). Send the text with `--file <path>` from a UTF-8 file; in Windows PowerShell 5.1 do not pipe the text, write it with `Set-Content -Encoding utf8 $env:TEMP\rapid-<id>.md` first. With `--source provided` the same pattern is only a `WARNING RAPID1415`: what a person pastes is stored as is.
- `person_actions`: when the next action is `done` (so after `finish`, and in `next --json`), the payload carries `person_actions[]` (`id`, `why`, `command`) only if the person needs something that Rapid OS cannot do for them: today `git-safe-directory`, the per-user command that lets their own git read this folder (the harness runs commands as another Windows user and git requires the same owner). It is omitted otherwise. The shortcuts show it as is and ask the person to run it in their own terminal. Rapid OS runs every git command with `safe.directory` set to the project root only, and with the fsmonitor off.
- `show`: the state and its `origin`: `setup.json`, `derived` or `empty`. `--json` emits `{origin, state}`.

State resolution: `.rapid-os/setup.json` when it exists (invalid: `RAPID1406`, exit 1); otherwise, if `.rapid-os/` exists (a project initialized before the setup flow), the state is derived from disk (`tech-stack.md`, `topology.md`, `coding-rules.md`, `config.json`, and the documents that carry `rapid-doc` frontmatter), without writing anything; without `.rapid-os/` the state is empty and `next` returns `choose_stack`. A broken catalog sidecar or question bank is `RAPID1401`; an invalid `rapid setup` subcommand, key or value (including a missing subcommand) is `RAPID1413`.

### Commands that write

They create `.rapid-os/` and `setup.json` when they do not exist, write atomically, and print the next action: with `--json` stdout carries the action object alone (progress goes to stderr); without it, a summary line and the same lines as `next`. An expected failure prints a `RAPIDxxxx` code on stderr and exits 1 without a traceback and without writing.

- `set <key> <value>`: records one decision in `setup.json`; the standards are written by `finish`.
  - `stack <id> [--component frontend|backend|baas|docs]`: a stack of the catalog or a template without sidecar. A stack that covers several components (`nextjs`, `nuxt`, `sveltekit`, `ruby-rails`, `python-django`, `php-laravel`) fills all the ones the topology asks for; `--component` limits it to one (`RAPID1413` when the stack cannot fill it). The ids of before the component catalog are accepted (`python-api` fills `backend` with `python-fastapi`; `python-ai` and `nodejs-ai` also set `ai` to `yes`; `web-modern` fills `frontend` and `backend` with `nextjs`; `frontend-creative` fills `frontend` with `react-vite` and its creative profile) and the output says so in `notes[]`. Unknown or `custom` is `RAPID1413`. If the topology already chosen does not fit the new stack, it is left undecided again and `next` asks for it; the note `Topology '<id>' does not fit stack '<id>'; it is undecided again.` goes to stderr and, with `--json`, to an optional `notes[]` field of the output (omitted when there are no notes).
  - `topology <id>`: `RAPID1413` when unknown; `RAPID1402` when it is incompatible with the stack already chosen.
  - `ai <yes|no>`: Does the product use models or agents? The `choose_ai` action (after archetype selection) includes a question such as *Will the product use AI models or agents (for example, an assistant that replies over WhatsApp)?*, `options`, and `command`. With `yes`, `standards/security.md` includes the AI section. Legacy IDs `python-ai` and `nodejs-ai` set this to `yes` automatically (a later `no` only prints a note). A `setup.json` without this field is undecided until setup finishes, then treated as `no`. After setup is complete, `set ai` applies immediately and keeps a `.bak` of `security.md`. Anything other than yes or no returns `RAPID1413`.
  - `archetype <mvp|corporate>`, `agents <id,id>` (ids of `rapid shortcuts`: `cursor`, `claude`, `antigravity`, `vscode`, `codex`) and `test-command '<cmd>'` (`none` records that the project has no test command). Any other key or value is `RAPID1413`.
- `stack --custom --file <path|->`: for a stack outside the catalog, the agent writes the `tech-stack.md` and sends it here. It must have a `Runtime`, a `Framework` and a `Testing` section (a `## ` heading or a `- **Name:**` line; `RAPID1409` otherwise). It is written to `.rapid-os/standards/tech-stack.md` (previous file kept as `.bak`) and records `custom` for every component under `stacks`; `finish` does not overwrite it.
- `doc <id> --source provided|drafted --file <path|->`: the harness sends only the **body** (read as UTF-8, `RAPID1424` if it is not); Rapid OS writes `docs/<FILE>.md` with the frontmatter (`rapid-doc`, `source`, `status`, `sha256` of the body) and keeps a `.bak` of the previous file. `provided` (the person wrote or pasted it) is stored as is, with `status: confirmed`, without checking sections or size. `drafted` (the agent wrote it) must carry every required section and fit `max_chars` (`RAPID1403`/`RAPID1404` are a rejection here: exit 1, nothing written) and is saved with `status: draft` until a person confirms it. A draft over a document a person provided, or over a file written by hand, needs `--replace` (`RAPID1405`). The body is stored with `\n` newlines and a final newline; nothing else changes.
- `review --done`: records `drafts_reviewed` in `.rapid-os/setup.json` (an optional field, omitted while false; older files without it read as false) and returns `finish` as the next action. It confirms nothing: any document not explicitly confirmed with `doc <id> --confirm` remains a draft and reaches the agent as an assumption. Confirming a document does not close the review, so several may be confirmed first. If no unconfirmed drafts remain, the command succeeds, changes nothing, and prints `All drafts are confirmed; nothing remains to review` followed by the next action. `review` without `--done` returns `RAPID1413`. A new draft (`doc --source drafted`) or `--reopen` makes review pending again. `rapid setup finish` with pending review returns `RAPID1407`, like any unresolved decision.
- `doc <id> --skip | --confirm | --reopen`: `--skip` records that the document is not needed (`RAPID1413` if the file is already written: Rapid OS never deletes it). `--confirm` is the person's confirmation of a draft: it changes only `status` in the frontmatter, never the body. `--reopen` returns a skipped document to `pending`, or a confirmed draft to `draft`.
- `doc business --from-legacy`: imports `.rapid-os/standards/business.md` as `docs/BUSINESS_RULES.md` with `source: provided` (backup of any existing file; the original is not deleted). `--replace` allows importing over an existing file.
- The frontmatter of the document is the source of truth for `status`/`confirmed`; `setup.json` is updated in the same operation and never contradicts it. Every `doc` write (`provided`, `drafted`, `--confirm`, `--skip`, `--reopen`, `--from-legacy`) regenerates the agent files (`CLAUDE.md`, `.cursorrules`, ...) when the project already has standards and agents in its config; otherwise `finish` does it.
- `finish` also gives the project a git repository when it is not inside one (a parent repository counts: it never nests): `git init` plus `git symbolic-ref HEAD refs/heads/<branch>` before the first commit, where `<branch>` is always `main` (any `init.defaultBranch` of the machine, such as Git for Windows' `master`, is ignored). It makes no commit and prints `Repositorio git creado en la rama main (Rapid OS observa los cambios con git)`. Without git installed it only warns (`Instala git: ...`) and the onboarding finishes. When git refuses the folder (`detected dubious ownership`) it does not run `git init`: it warns with the `git config` command that adds the folder to git's `safe.directory` list (the exact command is in `docs/troubleshooting/diagnostics.md`), using the path git prints; `rapid start` fails with `RAPID1416` and the same command, and `rapid finish` names the cause in `unverified_reason`. `rapid init` does the same, before updating `.gitignore`. The check runs on every `rapid setup finish`, not only the first one, so it is also the repair for a project whose `.git` was removed afterwards (`RAPID1416` suggests it). Decisions worth knowing: a `init.defaultBranch` that is not a valid branch name falls back to `main`; the creation note goes to stdout (stderr with `--json`) and is printed once, because later runs find the repository already there; and `rapid start --resume` does not repeat the git check, since the run already exists and `rapid finish` explains an UNVERIFIED caused by missing git.
- `set archetype <id> --refresh`: regenerates `standards/security.md` (the security baseline at the archetype's level: MVP is OWASP ASVS 5.0.0 L1, Corporate is L2 plus SLSA Build L2) and `standards/coding-rules.md` from the current templates, keeps the previous copies as `.bak` in `.rapid-os/backups/` (the 5 most recent per file) and rebuilds the agent files. It is how a project initialized before the baseline gets it (`rapid doctor` suggests it with `RAPID1421`). `--refresh` goes only with `archetype` (`RAPID1413` otherwise). Without `--refresh`, a `security.md` that Rapid OS did not write is never rewritten.
- `finish` also writes one workflow per language, `.github/workflows/rapid-security-<language>.yml` named `rapid-security (<language>)` (from `templates/ci/<python|typescript>-security.yml`: gitleaks, semgrep with OWASP Top 10 rules, bandit or `pip-audit`/`npm audit`, and Corporate SBOM and signed provenance; all actions pinned by full SHA) when the repository is empty and has no such workflow. It never overwrites an existing one. It prints `Rapid OS added this workflow; review it before the first commit: <path>`; with `--json`, the payload includes `added_files[]` (`file`, `note`), and `review_drafts` reports `planned_files[]` beforehand. See `docs/concepts/security-baseline.md`.
- `finish` writes a `.gitignore` entry for what each decided stack generates or installs (`stacks[].gitignore` in the sidecar: `node_modules/`, `.next/`, `.venv/`...) on top of the session and scratch entries; it only appends what is missing to an existing `.gitignore` and never creates one (the services of an empty repository do write one for `.env`, and the stack entries are added to it). A Python stack's `tech-stack.md` states the Python version (`.python-version`, `requires-python` or, failing both, the interpreter that runs Rapid OS) and where it came from. A frontend next to a separate backend declares no database, and with `ai` on the orchestration library is left as a decision. When `claude` is among the agents it also installs the Claude Code hooks in the project's `.claude/settings.json` (and says so) without copying the `/rapid-*` skills, which are installed once for the user with `rapid shortcuts install --global --harness claude`.
- `show` prints each drafted document as `drafted (draft)` or `drafted (confirmed)`. `rapid setup doc <id> --confirm` and `--reopen` change only the status: the previous file goes to `.rapid-os/backups/`, never to `docs/<name>.md.<n>.bak` (writing new content with `--replace` still keeps its copy beside the document, since it can be what a person wrote).
- `finish`: `RAPID1407` while a decision is still open. Otherwise it copies the stack, topology, archetype and security standards to `.rapid-os/standards/` (a standard that already expresses the decision on disk is left untouched), saves `.rapid-os/config.json` (`tools` and `test_command`, other keys kept), rebuilds the agent files, adds the missing lines (`.rapid-os/session.json`, `.rapid-os/scratch/`, `.rapid-os/backups/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`) to an existing `.gitignore` (it never creates one), marks `finished` and returns `done`. Unconfirmed drafts do not block it; they are listed in `unconfirmed_docs[]`. Running it again changes nothing. A later `set` reopens it.

`rapid validate` keeps reporting the documents: `RAPID1403`/`RAPID1404` stay warnings there (a document edited by hand) and each unconfirmed draft gives one `RAPID1408`.

---

## Complete Diagnostic Code Reference (`RAPIDxxx`)

| Code Range | Domain | Summary |
| :--- | :--- | :--- |
| `TEMPLATE001–003`, `CONFIG001–004`, `STD001–004`, `TOOL001–002`, `ARCH001`, `CTX001–002`, `ENV001`, `MCP001–013` | Legacy / Core Project & MCP | Templates, `.rapid-os/config.json`, `.rapid-os/standards/`, stack/topology consistency, optional `npx` check, and MCP server configuration warnings/errors. |
| `RAPID600–RAPID604` | Phase 1 — Project Intelligence | `.rapid-os/project.json` snapshot validity (`RAPID600` INFO, `RAPID601` invalid JSON, `RAPID602` unreadable, `RAPID603` schema version, `RAPID604` corrupt fact/evidence). |
| `RAPID700–RAPID705` | Phase 2 — Context Compiler | Context compilation (`RAPID700` INFO, `RAPID701` missing required source, `RAPID702` budget exceeded by required sources, `RAPID703` conflict warning, `RAPID704` invalid source/snapshot, `RAPID705` invalid request). |
| `RAPID800–RAPID809` | Phase 3 — Spec Registry | `.rapid-os/specs/` integrity (`RAPID800` INFO, `RAPID801` invalid `spec.json`, `RAPID802` missing revision history, `RAPID803` invalid `revision.json`, `RAPID804` markdown artifact drift, `RAPID805` lifecycle error, `RAPID806` identity error, `RAPID807` not found, `RAPID808` unsafe path, `RAPID809` unreferenced revision warning). |
| `RAPID1000–RAPID1014` | Phase 4 — Execution Policy & Runs | `.rapid-os/policy.json` and `.rapid-os/runs/` (`RAPID1000` INFO, `RAPID1001` invalid `run.json`, `RAPID1002` invalid `contract.json`, `RAPID1003` spec binding mismatch, `RAPID1004` context snapshot mismatch, `RAPID1005` invalid policy, `RAPID1006` policy violation/downgrade, `RAPID1007` run identity/not found, `RAPID1008` unsafe path, `RAPID1009` invalid run transition, `RAPID1010` invalid task transition, `RAPID1011` state history gap/warning, `RAPID1012` invalid `RunState` or transition history, `RAPID1013` invalid gate transition/waiver, `RAPID1014` phase boundary precondition failure). |
| `RAPID1100–RAPID1112` | Phase 5 — Harness Capability Registry | `.rapid-os/harnesses/` and `.rapid-os/capabilities.lock` (`RAPID1100` INFO, `RAPID1101` invalid capability ID, `RAPID1102` invalid `HarnessProfile`, `RAPID1103` profile not found, `RAPID1104` invalid harness ID, `RAPID1105` unsafe path, `RAPID1106` invalid capability support, `RAPID1107` invalid requirement, `RAPID1108` invalid resolution, `RAPID1109` resolution digest mismatch, `RAPID1110` incompatible/unresolved harness under `--require-compatible`, `RAPID1111` invalid/missing lock, `RAPID1112` stale lock warning). |
| `RAPID1200–RAPID1211` | Phase 6 — Evidence Engine | `.rapid-os/evidence/` (`RAPID1200` INFO, `RAPID1201` invalid evidence ID, `RAPID1202` invalid `RunEvidence` schema/digest, `RAPID1203` Run/Contract/State/producer binding mismatch, `RAPID1204` unsafe path, `RAPID1205` copied artifact missing/SHA-256/size mismatch, `RAPID1206` invalid payload, `RAPID1207` invalid task/gate/capability reference, `RAPID1208` sequence gap/duplicate, `RAPID1209` trailing crash-orphan artifact directory warning, `RAPID1210` evidence not found, `RAPID1211` append-only overwrite or unresolved crash-orphan block). |
| `RAPID1220–RAPID1229` | Phase 6 — Behavioral Evals | `.rapid-os/evals/` (`RAPID1220` INFO, `RAPID1221` invalid `EvaluationReport` schema, `RAPID1222` report digest mismatch, `RAPID1223` binding or semantic replay mismatch, `RAPID1224` unsafe path, `RAPID1225` `UNVERIFIED` under `--require-pass`, `RAPID1226` `FAIL` under `--require-pass`, `RAPID1227` stale report warning, `RAPID1228` report not found, `RAPID1229` append-only overwrite violation). |
| `RAPID1300–RAPID1339` | Intent layer (porcelain), shortcuts and hooks | Session and run (`RAPID1300` harness fallback, `RAPID1301` missing `test_command`, `RAPID1302` interactive input required, `RAPID1303` playbook, `RAPID1304`–`RAPID1309` session, tasks and project state), approval guard (`RAPID1310`, `RAPID1330`–`RAPID1336`), shortcuts (`RAPID1311`–`RAPID1319`, `RAPID1321`), `rapid check --expect fail` (`RAPID1320`) and Claude Code hooks (`RAPID1337`–`RAPID1339`). See the [diagnostics catalog](troubleshooting/diagnostics.md) for every code. |
| `RAPID1400–RAPID1429` | Catalog, onboarding and architecture | Stack/topology sidecars and setup state (`RAPID1400` informational "valid setup" of `rapid validate`, `RAPID1401` invalid catalog sidecar or question bank, `RAPID1402` stack and topology incompatible, `RAPID1403`/`RAPID1404` drafted document missing a section or over its size (a warning in `validate`, a rejection in `rapid setup doc`), `RAPID1405` a draft over a document a person provided, `RAPID1406` invalid `.rapid-os/setup.json`, `RAPID1407` `rapid setup finish` with decisions left, `RAPID1408` unconfirmed draft, `RAPID1409` custom stack without Runtime/Framework/Testing, `RAPID1410` `standards/business.md` differs from `docs/BUSINESS_RULES.md`, `RAPID1412` template without a sidecar, `RAPID1413` invalid `rapid setup` subcommand, key or value (also `rapid shortcuts` with an unsupported `--global` or an unknown `--only`), `RAPID1414` `rapid` not on the `PATH` while shortcuts or hooks are installed, `RAPID1415` text that lost its accents or `ñ` (`?` between letters) in `rapid setup doc`, `RAPID1416` `rapid start` in a folder that is not a git repository). See `docs/troubleshooting/diagnostics.md`., `RAPID1420` a violation of the architecture rule found by `rapid arch check` (or an unreadable `architecture.json`)), `RAPID1421` `security.md` without OWASP ASVS (warning of `rapid doctor`), `RAPID1417` a command that writes state run from the home folder, where `.rapid-os` is the Rapid OS installation and not a project (nothing is written; `rapid doctor` says "No estás en un proyecto" instead), `RAPID1424` text from `--file`/`--spec-file`/stdin that is not valid UTF-8 (nothing is stored), `RAPID1425` a saved spec or onboarding document with UTF-8 read as cp1252 (warning of `rapid doctor`), `RAPID1426` `test_command` that cannot be run (warning of `rapid doctor` and `rapid start`), `RAPID1427` an agent file edited by hand that `rapid setup` regenerates (warning; the copy goes to `.rapid-os/backups/`), `RAPID1423` the code changed after the last `gate.tests` check (`rapid approve` / `rapid finish` refuse, `rapid next` asks for a new check), `RAPID1422` `rapid finish` found, on the final state of the code, a violation of the architecture rule that `gate.architecture` had not seen (no `PASS`, exit 1, the run stays open)) |

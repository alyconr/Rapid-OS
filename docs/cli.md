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
rapid init --stack web-modern
rapid init --archetype corporate
rapid init --archetype mvp
rapid init --no-scan
```

Options:
- `--stack <name>`: Select stack template directly (`templates/stacks/<name>.md`).
- `--archetype {mvp,corporate}`: Select archetype directly without interactive prompt.
- `--topology <id>`: Select topology template directly (`templates/topologies/<id>.md`). With `--yes` and no `--topology`, the topology is chosen to match the stack (`doc-site` only with `docs-modern`; `fullstack-separated` for `web-modern`, `python-ai` and `nodejs-ai`; `front-end-only` for `frontend-creative`).
- `rapid init` also creates `.rapid-os/standards/security.md` (from the `corporate` archetype or, if there is none, a minimal template) when it does not exist; `rapid start hardening` requires it.
- `--agents <lista>`: Comma-separated list of agent IDs or numbers (e.g. `cursor,claude`).
- `-y`, `--yes`: Non-interactive mode accepting defaults. It asks nothing about the project documents: they stay `pending` (not skipped) and `init` ends with `Completa la documentación con /rapid-init o rapid setup next`. Con `--yes --no-scan` no se propone `test_command` y hay que pasar `--test-command`.
- `--business-file <ruta>`: Import that file as `docs/BUSINESS_RULES.md`, provided by a person (`source: provided`, `status: confirmed`) and stored as is, without checking sections or size. A path that is empty, a directory or unreadable is `RAPID1413` (exit 1, nothing written). The other documents follow the usual rules (asked, or `pending` with `--yes`).
- `--skip-docs`: Mark the four project documents (`brief`, `business`, `data-model`, `architecture`) as `skipped` without asking. Combined with `--business-file`, the business document is still imported.
- `--test-command <cmd>`: Explicit test command string to store in `.rapid-os/config.json`.
- `--no-scan`: Skip automatic project intelligence scan suggestions during initialization.
- `--shortcuts`: Install the `/rapid-<mode>` shortcuts for the selected agents at the end of `init` without asking (see `rapid shortcuts`). Without it, `init` only offers them on an interactive terminal. It does not install hooks.
- `--hooks`: Also install the Claude Code hooks (see `rapid hook`) in `.claude/settings.json`. Independent of `--shortcuts`; it needs `claude` among the selected agents (otherwise a `RAPID1337` warning is printed and `init` continues).

`init` shares the state and the writes of `rapid setup`: it builds the same `.rapid-os/setup.json`, copies the same standards and saves the same config. The interactive terminal offers, for each of the four documents (`docs/PRODUCT_BRIEF.md`, `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md`, `docs/ARCHITECTURE.md`): 1) import a file (`.md`, `.txt`; an empty path or a directory asks again, `0` goes back), 2) write it there (it ends with two empty lines or EOF), 3) leave it for your agent (`/rapid-init`, the default) or 4) skip it. A document that is already resolved (`provided`, `drafted` or `skipped`) is kept when `init` runs again. `init` no longer offers the `TODO` scaffold of `docs/` (`SPECS.md` and the other templates) nor saves business templates; it does not write `.rapid-os/standards/business.md` any more (an existing one keeps working, see `rapid setup doc business --from-legacy`).
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
Generate `DEPLOY.md` from `templates/deploy/<target>.md` (or a generic deployment checklist fallback). Writes files.

```bash
rapid deploy aws
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
- `--json`: Output execution and recorded evidence details as JSON.
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

Each mode has its own playbook in `templates/modes/` (`spec_template` and per-action instructions):

| Mode | Behavior |
| :--- | :--- |
| `feature` | Default loop: baseline, tasks, verification, human gate. |
| `bugfix` | The baseline is taken at `start`, before the reproduction test exists. While `T001` ("Reproducir con un test en rojo") is `in_progress` without a passing `reproduction.T001` assertion, `rapid next` proposes `rapid check --expect fail --task T001 -- <test_command>`; once the failure is recorded it proposes `rapid task done T001 --no-check` (the suite is red by design). |
| `refactor` | The baseline is mandatory. Once all tasks are terminal, if the latest `test_result` has fewer passed tests than the baseline, `rapid next` returns `blocked` with the difference (a Conductor rule, not an evaluator rule). |
| `hardening` | Risk is `high`, so the contract requires an isolated workspace (see `--worktree`) and a `gate.review`. |
| `research` | Spike: low risk, no baseline and no mandatory tests. Findings are recorded with `rapid attach`. |

Options:
- `--worktree`: When the contract requires `isolated_required`, create a git worktree at `../<repo>-<run-id>` on branch `rapid/<run-id>` from `HEAD`. The ledger (`.rapid-os/`, `session.json`) stays in the main repository; `session.json` stores `workspace_path`, `rapid check`/`rapid task done` run the commands in that directory, `rapid finish` collects the changes from it, and the run records `workspace` evidence with `mode: isolated` (which acknowledges `gate.workspace-isolation`). Without the flag the run stops at `blocked` and `rapid next` proposes `rapid start --resume --worktree`. The flag has no effect when the contract does not require isolation. Uncommitted changes of the main checkout are not part of the worktree (it starts from `HEAD`). `rapid abort` keeps the worktree on disk.
- `--spec-file`: if a spec with the same identity (`id` or title) and the same content already exists (a previous `rapid start` created it and then failed, e.g. `RAPID1004`), it is reused; if the content differs, `rapid start` exits with `RAPID1322` and suggests `rapid start <mode> --spec <id>`.
- `session.json` also records `start_untracked`: the untracked files that existed before `rapid start`, which `rapid finish` does not attribute to the run.

### `rapid next`
Query the deterministic next workflow action without mutating state. When a human review was rejected (`rapid approve --reject`) it returns `blocked` with the command `rapid abort`: the gate stays `FAIL` for that run and a new run is needed. Agents must not run `rapid abort` on their own in that case.

```bash
rapid next [--json]
```

### `rapid finish`
Collect repository changes, evaluate machine gates, and close the run.

```bash
rapid finish [--json]
```

In text mode it prints the report revision and the verdict (`Evaluation report 0001 for run '<run-id>': verdict PASS`). Finishing a run that already ended is idempotent and records no new evidence or report: it prints the stored verdict (the latest report) and exits 0 only if that verdict is `pass` or `pass_with_waivers`, otherwise 1; a run that ended without a report (for example `cancelled` or `failed`) prints `already ended (<outcome>)` on stderr and exits 1.

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
- `--reject`: Record a `review` evidence with outcome `changes_requested`. This leaves the gate in `FAIL` for the rest of that run: `rapid next` returns `blocked` with the command `rapid abort`, and a new run is needed. `--reason` is mandatory.
- `--reason <text>`: Reason for `--waive` or `--reject` (`RAPID1333` if missing).

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

## Harness Shortcuts (`rapid shortcuts`)

Generate the `/rapid-<mode>` commands of each coding harness from a single source (`templates/shortcuts/`). The shortcuts teach the agent only the loop (`rapid next --json` → `rapid start <mode> --spec-file -` → `rapid check -- <cmd>` → `rapid approve` by a person); they do not list plumbing commands, and they never run `rapid approve`, `rapid run gate` or `rapid evidence add`.

```bash
rapid shortcuts install [--harness <id> ...] [--dry-run] [--json]
rapid shortcuts list    [--harness <id> ...] [--json]
rapid shortcuts remove  [--harness <id> ...] [--dry-run] [--json]
```

Options:
- `--harness <id>`: Harness to target (`claude`, `codex`, `antigravity`, `cursor`, `vscode`). Repeatable. Without it, the supported entries of `tools` in `.rapid-os/config.json` are used; a project without that file must pass `--harness` (`RAPID1312`).
- `--dry-run`: Show what would be written or deleted without touching the filesystem (`install`, `remove`).
- `--hooks`: With `install`, also merge the Rapid OS hooks (`Stop` and `PreToolUse`, command `rapid` with arguments `hook stop` / `hook pre-tool`) into the project's `.claude/settings.json`; with `remove`, also remove them. Requires the `claude` harness (`RAPID1337`). Other keys and hooks of the file are left untouched, an existing file is backed up as `.bak`, installing twice writes nothing, and `remove` only deletes the handlers it owns (and the file itself when nothing else is left in it). An unreadable `settings.json` is reported with `RAPID1338` and never overwritten. The handlers use Claude Code's exec form, so `rapid` must be on the `PATH` of the machine running Claude Code; `rapid doctor` warns (`RAPID1339`) when hooks are installed and `rapid` is not found.
- `--json`: Emit `schema_version`, `command`, `harnesses`, `files[]` (`path`, `shortcut`, `harnesses`, `action`) and, for `install` and `list`, `skipped[]`.
- `warnings` (`install` and `list`): always a list of objects `{code, message, ...}` (`RAPID1315` and `RAPID1316` carry `shortcut`/`mode` or `path`; `RAPID1321` is described below). In `install` it is always present (empty when there is nothing to warn about); in `list` it is optional and omitted when empty. When the selection leaves the same `/rapid-*` in two folders that one tool reads (`cursor` or `vscode` together with `claude`, `codex` or `antigravity`), each overlap prints `WARNING RAPID1321` on stderr (also in `rapid init --shortcuts`) and, with `--json`, adds an object `{code, message, reader, harnesses, folders}` to `warnings`. In `install` the object is appended to the `warnings` list that already holds the text warnings; in `list` the field is optional and omitted when empty. It never changes the exit code or what is written. See [Si combinas harnesses](guides/shortcuts.md#si-combinas-harnesses).

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
- Only Claude Code runs the `` !`rapid next --json` `` line before the prompt is sent (a failing command aborts the skill); the other harnesses get the instruction "ejecuta `rapid next --json`" as plain text.
- Mode shortcuts are generated only for modes with a playbook in `templates/modes/`. `list` and `install` report the omitted ones with `RAPID1315`; running `rapid shortcuts install` again after a playbook is added creates the missing ones.
- Codex and Antigravity share `.agents/skills`; when both are selected each file is written once.
- Every file carries the marker `<!-- generated by rapid shortcuts -->` right after the frontmatter. `install` is idempotent: identical content is not rewritten; different content is first backed up as `.bak`. `remove` deletes only files that carry the marker (`RAPID1317` for those left untouched) and the then-empty `<name>/` folder. Because `.agents/skills` is shared, removing for one of Codex/Antigravity removes the files for both.
- `rapid init` offers to install the shortcuts at the end (interactive terminals only, default no). `rapid init --shortcuts` installs them for the selected agents without asking.

## Onboarding (`rapid setup`)

Completes the onboarding with commands only, the way `rapid start`/`rapid next` drive a run: every command returns the next decision, so a harness can loop on `rapid setup next --json` until it gets `done`. `next` and `show` are **read-only**: they never write, not even `.rapid-os/setup.json`. `set`, `stack`, `doc` and `finish` write.

```bash
rapid setup next [--json]
rapid setup show [--json]
rapid setup set stack|topology|archetype|agents|test-command <value> [--json]
rapid setup stack --custom --file <path|-> [--json]
rapid setup doc <id> --source provided|drafted --file <path|-> [--replace] [--json]
rapid setup doc <id> --skip | --confirm | --reopen | --from-legacy [--replace] [--json]
rapid setup finish [--json]
```

- `next`: the next decision, in this order: `choose_stack`, `choose_topology`, `choose_archetype`, `choose_agents`, `set_test_command`, `resolve_doc` (`brief`, `business`, `data-model`, `architecture`), `finish`, `done`. `--json` emits one object with `schema_version`, `kind` and the fields of that decision:
  - `choose_stack`: `facts[]` from the scanner, `options[]` (`id`, `source`, `summary`, `language`, `score`, `fits[]`, `avoid_if[]`, `compatible_topologies[]`; the lists are empty for a stack without a sidecar) sorted by a deterministic score (language and framework match), `recommended` (the scanner suggestion or `null`) and, only when `recommended` is `null`, `questions[]` from `templates/setup/stack-questions.json`. `alt_command` is the invocation for a stack outside the catalog (`rapid setup stack --custom --file -`).
  - `choose_topology`: only the topologies compatible with the chosen stack, plus `recommended`.
  - `choose_agents`: `recommended` is the harness detected from `RAPID_HARNESS`, the Claude Code marker or `default_harness` in the config, or `null` (the `cursor` fallback is not a detection). `set_test_command`: `recommended` is `["npm", "test"]` when `package.json` has `scripts.test`, pytest when detected, or the unittest discovery command for a Python project with a tests directory; otherwise `null`.
  - `resolve_doc`: `doc`, `target` (`docs/<FILE>.md`), `choices` (`provided`, `drafted`, `skip`), `questions[]`, `required_sections[]` (`id`, `titles[]`), `max_chars` and `command` (the invocation that writes the document), all read from `templates/setup/docs/<id>.json`. For `business` it also carries `legacy_source` (`.rapid-os/standards/business.md`) when that file has content and `docs/BUSINESS_RULES.md` does not exist.
  - Every action except `done` carries `command`, the argv that resolves it; `finish` and `done` list `unconfirmed_docs[]`: drafted documents nobody has confirmed.
- `show`: the state and its `origin`: `setup.json`, `derived` or `empty`. `--json` emits `{origin, state}`.

State resolution: `.rapid-os/setup.json` when it exists (invalid: `RAPID1406`, exit 1); otherwise, if `.rapid-os/` exists (a project initialized before the setup flow), the state is derived from disk (`tech-stack.md`, `topology.md`, `coding-rules.md`, `config.json`, and the documents that carry `rapid-doc` frontmatter), without writing anything; without `.rapid-os/` the state is empty and `next` returns `choose_stack`. A broken catalog sidecar or question bank is `RAPID1401`; an invalid `rapid setup` subcommand, key or value (including a missing subcommand) is `RAPID1413`.

### Commands that write

They create `.rapid-os/` and `setup.json` when they do not exist, write atomically, and print the next action: with `--json` stdout carries the action object alone (progress goes to stderr); without it, a summary line and the same lines as `next`. An expected failure prints a `RAPIDxxxx` code on stderr and exits 1 without a traceback and without writing.

- `set <key> <value>`: records one decision in `setup.json`; the standards are written by `finish`.
  - `stack <id>`: a stack of the catalog or a template without sidecar. Unknown or `custom` is `RAPID1413`. If the topology already chosen does not fit the new stack, it is left undecided again (a note on stderr) and `next` asks for it.
  - `topology <id>`: `RAPID1413` when unknown; `RAPID1402` when it is incompatible with the stack already chosen.
  - `archetype <mvp|corporate>`, `agents <id,id>` (ids of `rapid shortcuts`: `cursor`, `claude`, `antigravity`, `vscode`, `codex`) and `test-command '<cmd>'` (`none` records that the project has no test command). Any other key or value is `RAPID1413`.
- `stack --custom --file <path|->`: for a stack outside the catalog, the agent writes the `tech-stack.md` and sends it here. It must have a `Runtime`, a `Framework` and a `Testing` section (a `## ` heading or a `- **Name:**` line; `RAPID1409` otherwise). It is written to `.rapid-os/standards/tech-stack.md` (previous file kept as `.bak`) and records `stack = {id: custom, source: custom}`; `finish` does not overwrite it.
- `doc <id> --source provided|drafted --file <path|->`: the harness sends only the **body**; Rapid OS writes `docs/<FILE>.md` with the frontmatter (`rapid-doc`, `source`, `status`, `sha256` of the body) and keeps a `.bak` of the previous file. `provided` (the person wrote or pasted it) is stored as is, with `status: confirmed`, without checking sections or size. `drafted` (the agent wrote it) must carry every required section and fit `max_chars` (`RAPID1403`/`RAPID1404` are a rejection here: exit 1, nothing written) and is saved with `status: draft` until a person confirms it. A draft over a document a person provided, or over a file written by hand, needs `--replace` (`RAPID1405`). The body is stored with `\n` newlines and a final newline; nothing else changes.
- `doc <id> --skip | --confirm | --reopen`: `--skip` records that the document is not needed (`RAPID1413` if the file is already written: Rapid OS never deletes it). `--confirm` is the person's confirmation of a draft: it changes only `status` in the frontmatter, never the body. `--reopen` returns a skipped document to `pending`, or a confirmed draft to `draft`.
- `doc business --from-legacy`: imports `.rapid-os/standards/business.md` as `docs/BUSINESS_RULES.md` with `source: provided` (backup of any existing file; the original is not deleted). `--replace` allows importing over an existing file.
- The frontmatter of the document is the source of truth for `status`/`confirmed`; `setup.json` is updated in the same operation and never contradicts it. Every `doc` write (`provided`, `drafted`, `--confirm`, `--skip`, `--reopen`, `--from-legacy`) regenerates the agent files (`CLAUDE.md`, `.cursorrules`, ...) when the project already has standards and agents in its config; otherwise `finish` does it.
- `finish`: `RAPID1407` while a decision is still open. Otherwise it copies the stack, topology, archetype and security standards to `.rapid-os/standards/` (a standard that already expresses the decision on disk is left untouched), saves `.rapid-os/config.json` (`tools` and `test_command`, other keys kept), rebuilds the agent files, adds `.rapid-os/session.json` and `.rapid-os/scratch/` to an existing `.gitignore`, marks `finished` and returns `done`. Unconfirmed drafts do not block it; they are listed in `unconfirmed_docs[]`. Running it again changes nothing. A later `set` reopens it.

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
| `RAPID1400–RAPID1419` | Catalog and onboarding | Stack/topology sidecars and setup state (`RAPID1400` informational "valid setup" of `rapid validate`, `RAPID1401` invalid catalog sidecar or question bank, `RAPID1402` stack and topology incompatible, `RAPID1403`/`RAPID1404` drafted document missing a section or over its size (a warning in `validate`, a rejection in `rapid setup doc`), `RAPID1405` a draft over a document a person provided, `RAPID1406` invalid `.rapid-os/setup.json`, `RAPID1407` `rapid setup finish` with decisions left, `RAPID1408` unconfirmed draft, `RAPID1409` custom stack without Runtime/Framework/Testing, `RAPID1410` `standards/business.md` differs from `docs/BUSINESS_RULES.md`, `RAPID1412` template without a sidecar, `RAPID1413` invalid `rapid setup` subcommand, key or value, `RAPID1414` `rapid` not on the `PATH` while shortcuts or hooks are installed). See `docs/troubleshooting/diagnostics.md`. |

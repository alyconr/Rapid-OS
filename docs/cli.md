# Rapid OS CLI Reference

Rapid OS provides a deterministic, standard-library-only command-line interface (`rapid` or `python rapid.py`) for project intelligence, task-aware context compilation, spec authoring, execution policy & runs, and harness capability resolution.

## Global Options

- `--root <path>`: Target project root directory (defaults to current working directory).
- `--version`: Print the Rapid OS version and exit.
- `-h`, `--help`: Show command help and exit.

---

## Core Project & Legacy Workflow Commands

### `rapid init`
Initialize `.rapid-os/` standards, configuration, and AI harness rule files (`CLAUDE.md`, `AGENTS.md`, `.cursor/rules/`, `.github/copilot-instructions.md`).

```bash
rapid init
rapid init --stack python-ai --topology fullstack-separated --design minimal-saas --security high-compliance --ide cursor,claude,codex --no-interactive
```

### `rapid update`
Regenerate AI harness rule files from `.rapid-os/config.json` and `.rapid-os/standards/`.

```bash
rapid update
rapid update --ide cursor,claude --dry-run
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

### `rapid validate` & `rapid doctor`
Validate `.rapid-os/` configuration, standards, project intelligence snapshot (`RAPID6xx`), spec registry (`RAPID8xx`), execution policy & run registry (`RAPID1000–RAPID1019`), and harness capability registry & lock (`RAPID1100–RAPID1119`).

```bash
rapid validate
rapid validate --strict
rapid validate --json
rapid doctor
```

---

## Context Compiler (`rapid context`)

Compile task-relevant, budgeted context (`CompiledContext`, `schema_version = 1`) in read-only mode.

```bash
rapid context --mode feature --harness codex --objective "Implement billing webhook"
rapid context --spec billing-webhook --harness my-company-agent
rapid context --mode hardening --manifest
rapid context --mode general --json
```

Options:
- `--mode {feature,bugfix,refactor,hardening,research,general}`
- `--harness <harness-id>`: Any valid harness ID (`^[a-z0-9][a-z0-9-]{0,62}$`, e.g. `codex`, `claude`, `cursor`, `vscode`, `antigravity`, or custom IDs).
- `--objective <text>`
- `--spec <spec-id>` / `--spec-revision <n>`
- `--path <relative-path>` (repeatable)
- `--tag <tag>` (repeatable)
- `--constraint <constraint>` (repeatable)
- `--max-chars <n>`
- `--manifest`
- `--json`

---

## Spec Registry (`rapid spec`)

Manage immutable, multi-spec revisions in `.rapid-os/specs/<spec-id>/`.

```bash
rapid spec create --title "Checkout Flow" --mode feature --objective "Enable Stripe checkout" --scope "API" --acceptance "Webhook verified" --task "Add endpoint" --status ready
rapid spec list [--status {draft,ready,archived}] [--json]
rapid spec show <spec-id> [--revision <n>] [--json]
rapid spec revise <spec-id> --task "Add idempotency key" [--json]
rapid spec status <spec-id> {draft,ready,archived} [--json]
rapid spec export-legacy <spec-id> [--revision <n>]
```

---

## Execution Policy & Run Registry (`rapid policy` & `rapid run`)

Evaluate execution contracts (`ExecutionContract`, `schema_version = 1`) and track append-only run states in `.rapid-os/runs/<run-id>/`.

```bash
rapid policy show [--json]
rapid policy init [--json]

rapid run create --spec <spec-id> [--spec-revision <n>] [--id <run-id>] [--harness <harness-id>] [--classification {spike,bounded,architectural}] [--risk {low,medium,high,critical}] [--json]
rapid run list [--status {prepared,active,blocked,finished,failed,cancelled}] [--json]
rapid run show <run-id> [--state-revision <n>] [--json]
rapid run status <run-id> {active,blocked,finished,failed,cancelled} [--reason "..."] [--json]
rapid run task <run-id> <task-id> {in_progress,done,blocked,skipped} [--reason "..."] [--json]
rapid run gate <run-id> <gate-id> {acknowledged,waived} [--reason "..."] [--json]
```

---

## Harness Capability Registry (`rapid harness`)

Inspect declarative harness capability profiles (`HarnessProfile`, `schema_version = 1`), initialize project profile overrides in `.rapid-os/harnesses/<id>.json`, lock active profiles in `.rapid-os/capabilities.lock`, and resolve run contracts against harness capabilities (`CapabilityResolution`, `schema_version = 1`).

> **Product Truth**: A capability declaration states what a harness is expected to support; it does not execute the harness or prove that the capability was exercised at runtime.

### `rapid harness list`
List active harness profiles (`builtin:<id>` and `.rapid-os/harnesses/<id>.json` overrides) in deterministic `harness_id` order. Read-only.

```bash
rapid harness list
rapid harness list --json
```

### `rapid harness show <harness-id>`
Show a resolved harness profile, provenance (`source`), `content_digest`, and capability statuses (`supported`, `unsupported`, `unknown`). Read-only.

```bash
rapid harness show codex
rapid harness show codex --json
```

### `rapid harness init <harness-id>`
Copy a built-in harness profile to `.rapid-os/harnesses/<harness-id>.json` for project-specific customization. Never overwrites an existing file (`RAPID1104`). For custom harness IDs without a built-in profile, fails with `RAPID1103` and explains how to author `.rapid-os/harnesses/<harness-id>.json`.

```bash
rapid harness init codex
rapid harness init codex --json
```

### `rapid harness resolve --run <run-id>`
Resolve an immutable run's `ExecutionContract` against a harness profile in read-only mode (never modifies `.rapid-os/runs/<run-id>/`).

```bash
rapid harness resolve --run checkout-r1-run-001
rapid harness resolve --run checkout-r1-run-001 --harness claude
rapid harness resolve --run checkout-r1-run-001 --locked
rapid harness resolve --run checkout-r1-run-001 --require mcp.invoke
rapid harness resolve --run checkout-r1-run-001 --require-compatible
rapid harness resolve --run checkout-r1-run-001 --json
```

Options:
- `--run <run-id>`: Required run identifier whose `ExecutionContract` is evaluated.
- `--harness <harness-id>`: Optional harness override (defaults to `contract.harness`).
- `--locked`: Resolve against the exact `HarnessProfile` snapshot stored in `.rapid-os/capabilities.lock` instead of live profiles on disk.
- `--require <capability-id>`:Repeatable extra canonical capability requirement (`source="cli.require"`).
- `--require-compatible`: Gate mode — exits `0` only when `compatibility == "compatible"`, and exits `1` with `RAPID1110` (`incompatible`) or `RAPID1111` (`unresolved`). Without `--require-compatible`, resolution is informational and exits `0` for `compatible`, `incompatible`, and `unresolved`.
- `--json`: Emit pure `CapabilityResolution` JSON (`schema_version = 1`) on `stdout`.

### `rapid harness lock`
Write a deterministic `.rapid-os/capabilities.lock` snapshot (`schema_version = 1`) pinning all active harness profiles and their digests.

```bash
rapid harness lock
rapid harness lock --json
```

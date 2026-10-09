# Rapid OS CLI Reference

Rapid OS provides a deterministic, standard-library-only command-line interface (`rapid` or `python rapid.py`) for project intelligence, task-aware context compilation, spec authoring, execution policy & runs, harness capability resolution, immutable run evidence ingestion, and deterministic behavioral evaluations.

All commands operate on the **current working directory** as the target project root.

## Global Options

- `--version`: Print `Rapid OS 3.0.0` and exit (`0`).
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
- `--no-scan`: Skip automatic project intelligence scan suggestions during initialization.

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
rapid eval run --run <run-id> [--require <capability-id>] [--write] [--require-pass] [--json]
rapid eval list --run <run-id> [--json]
rapid eval show --run <run-id> [--revision <n>] [--json]
```

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

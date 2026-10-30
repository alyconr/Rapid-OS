---
title: RAPIDxxx Diagnostics Catalog
description: Exhaustive reference of RAPID OS diagnostic codes, common causes, and remediation actions.
---

# RAPIDxxx Diagnostics Catalog

When you run `rapid validate`, `rapid scan`, or governance commands, RAPID OS emits deterministic diagnostics identified by unique codes. This guide documents the meaning of each code and how to resolve it.

---

## 1. Project Configuration and Templates (`RAPID100–RAPID110`)

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID100` | INFO | Project configuration valid and loaded. | Informational. |
| `RAPID101` | ERROR | File `.rapid-os/config.json` not found. | Run `rapid init` to initialize the project. |
| `RAPID102` | ERROR | JSON syntax error in `.rapid-os/config.json`. | Fix the JSON syntax or restore from the `.bak` backup file. |
| `RAPID103` | ERROR | Incompatible or invalid schema version. | Verify that `schema_version` matches the supported version. |
| `RAPID104` | ERROR | Required fields missing from `config.json`. | Regenerate the configuration with `rapid init`. |
| `RAPID105` | ERROR | A mandatory templates folder (`stacks` or `topologies`) has no Markdown template. | Reinstall Rapid OS or restore the `templates/` folder. |
| `RAPID106` | ERROR | A template file is not valid UTF-8. | Save it as UTF-8 or restore the original template. |
| `RAPID107` | ERROR | A template file could not be read (permissions or disk error). | Check the permissions of `templates/` or reinstall Rapid OS. |
| `RAPID108` | WARNING | A template file is empty. | Restore the template or delete the file. |
| `RAPID109` | ERROR | A `.json` template is not valid JSON. | Fix the syntax indicated in the message or restore the template. |
| `RAPID110` | WARNING | A template contains unresolved markers (`{{...}}`, `TODO`, `REPLACE_ME`...). | Replace the markers; it only matters if you edited the templates. |

---

## 2. Phase 1 — Project Intelligence (`RAPID600–RAPID604`)

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID600` | INFO | Valid `.rapid-os/project.json` snapshot. | Informational. |
| `RAPID601` | ERROR | Corrupt JSON syntax in `project.json`. | Run `rapid scan --write` to regenerate the snapshot. |
| `RAPID602` | ERROR | Insufficient read permissions on `project.json`. | Adjust the file system permissions. |
| `RAPID603` | ERROR | Unsupported snapshot schema version. | Run `rapid scan --write` to update to schema version 1. |
| `RAPID604` | ERROR | Fact (`ProjectFact`) or evidence corrupt in the snapshot. | Regenerate the snapshot with `rapid scan --write`. |

---

## 3. Phase 2 — Context Compiler (`RAPID700–RAPID705`)

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID700` | INFO | Context compilation succeeded. | Informational. |
| `RAPID701` | ERROR | Required context source not found. | Check that the standards (`.rapid-os/standards/`) exist or initialize them with `rapid init`. |
| `RAPID702` | ERROR | The token/character budget was exceeded by mandatory sources. | Raise the limit with `--max-chars <n>` or reduce the required sources in `.rapid-os/config.json`. |
| `RAPID703` | WARNING | Conflict detected among the selected context sources. | Review the manifest with `rapid context --manifest` and resolve contradictory rules. |
| `RAPID704` | ERROR | Invalid snapshot or source for the compiler. | Run `rapid scan --write` and verify file integrity. |
| `RAPID705` | ERROR | Invalid context request (unrecognized harness or mode). | Verify that the mode is `{feature,bugfix,refactor,hardening,research,general}` and the harness ID is valid. |

---

## 4. Phase 3 — Spec Registry (`RAPID800–RAPID809`)

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID800` | INFO | Specification registry intact. | Informational. |
| `RAPID801` | ERROR | `spec.json` file with invalid schema or content. | Review the structure in `.rapid-os/specs/<id>/spec.json`. |
| `RAPID802` | ERROR | Revision history missing or discontinuous. | Verify that the `rev_0001`, `rev_0002` folders exist sequentially. |
| `RAPID803` | ERROR | Corrupt `revision.json` file. | Restore or regenerate the spec revision with `rapid spec revise`. |
| `RAPID804` | WARNING | Drift detected between the spec markdown and the JSON metadata. | Synchronize the content or re-export with `rapid spec export-legacy`. |
| `RAPID805` | ERROR | Invalid lifecycle transition in a spec. | Specs can only transition between `draft`, `ready`, and `archived`. |
| `RAPID806` | ERROR | Conflict or invalid format in a spec identifier. | Use alphanumeric IDs with hyphens (`^[a-z0-9][a-z0-9-]{0,62}$`). |
| `RAPID807` | ERROR | Referenced spec not found in the registry. | Verify with `rapid spec list` that the spec exists before creating a run. |
| `RAPID808` | ERROR | Unsafe path detected (path traversal attempted). | Keep all operations inside the project's working tree. |
| `RAPID809` | WARNING | Orphan revision not linked in the history. | Verify the `revisions` array in `spec.json`. |

---

## 5. Phase 4 — Execution Policy and Runs (`RAPID1000–RAPID1014`)

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID1000` | INFO | Run and contract registry intact. | Informational. |
| `RAPID1001` | ERROR | `run.json` file corrupt or with invalid schema. | Review `.rapid-os/runs/<id>/run.json`. |
| `RAPID1002` | ERROR | `contract.json` file corrupt or digest altered. | Do not modify `contract.json` manually; it is immutable. |
| `RAPID1003` | ERROR | Mismatch between the contract's spec and the registered spec. | Regenerate the run, making sure the spec is in `ready` state. |
| `RAPID1004` | ERROR | Mismatch in the context snapshot digest. | Recompile a consistent context before starting the run. |
| `RAPID1005` | ERROR | Invalid `.rapid-os/policy.json` file, or duplicate on `policy init`. | Fix the policy syntax or remove the file before initializing a new one. |
| `RAPID1006` | ERROR | Policy violation or unauthorized attempt to downgrade risk. | Respect the evaluation computed by the policy according to the paths and tags. |
| `RAPID1007` | ERROR | Run identifier not found or duplicate. | Use unique identifiers with `rapid run list`. |
| `RAPID1008` | ERROR | Unsafe run path outside the root directory. | Fix relative paths. |
| `RAPID1009` | ERROR | Invalid run state transition. | Respect the lifecycle: `prepared` → `active` → `finished` / `failed` / `cancelled`. |
| `RAPID1010` | ERROR | Invalid contract task transition. | Tasks only support: `in_progress`, `done`, `blocked`, `skipped`. |
| `RAPID1011` | WARNING | Gap in the sequential run state history. | Check that the `state_0001.json` files follow a continuous numeric sequence. |
| `RAPID1012` | ERROR | `RunState` file corrupt or digest mismatch. | Verify the integrity of the states in `.rapid-os/runs/<id>/states/`. |
| `RAPID1013` | ERROR | Attempt to waive (`waive`) a gate that is not in `waivable_gates`. | Modify the policy in `policy.json` or satisfy the gate with evidence. |
| `RAPID1014` | ERROR | Phase-boundary precondition failure when transitioning the run. | Complete the required tasks before marking the run as `finished`. |

---

## 6. Phase 5 — Harness Capability Registry (`RAPID1100–RAPID1112`)

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID1100` | INFO | Harness profiles and lock intact. | Informational. |
| `RAPID1101` | ERROR | Non-canonical or invalid capability identifier. | Use canonical IDs (e.g. `shell.execute`, `repository.write`). |
| `RAPID1102` | ERROR | Invalid harness profile (`HarnessProfile`). | Fix `.rapid-os/harnesses/<id>.json` according to schema v1. |
| `RAPID1103` | ERROR | Harness profile not found. | Initialize the profile with `rapid harness init <id>` or use a built-in one. |
| `RAPID1104` | ERROR | Invalid harness ID format. | Use lowercase alphanumeric names with hyphens. |
| `RAPID1105` | ERROR | Unsafe or unreadable path in the harness registry or in `.rapid-os/capabilities.lock`: it is a symlink, escapes the project root, or is not a regular directory or file. | Replace it with a real directory or file inside the project (`.rapid-os/harnesses/`, `.rapid-os/capabilities.lock`); `rapid harness lock` regenerates the lock. |
| `RAPID1106` | ERROR | Invalid support level in a profile. | Use `supported`, `unsupported`, or `unknown`. |
| `RAPID1107` | ERROR | Malformed capability requirement in the contract. | Verify the contract's capability specification. |
| `RAPID1108` | ERROR | Invalid `CapabilityResolution` object. | Run `rapid harness resolve --run <id>` again. |
| `RAPID1109` | ERROR | Mismatch in the resolution digest. | Make sure the profile and the contract have not changed. |
| `RAPID1110` | ERROR | Incompatible or unresolved harness under `--require-compatible`. | Select a compatible harness or adjust the contract's requirements. |
| `RAPID1111` | ERROR | `.rapid-os/capabilities.lock` file missing or corrupt under `--locked`. | Run `rapid harness lock` to generate the lock file. |
| `RAPID1112` | WARNING | The lock file is out of date with respect to the current profiles. | Regenerate the lock with `rapid harness lock`. |

---

## 7. Phase 6 — Evidence Engine (`RAPID1200–RAPID1211`)

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID1200` | INFO | Evidence records intact and continuous. | Informational. |
| `RAPID1201` | ERROR | Invalid evidence ID. | The Evidence Engine manages canonical IDs such as `E001`, `E002`. |
| `RAPID1202` | ERROR | Invalid `RunEvidence` schema or `content_digest`. | Do not alter the evidence JSON files manually. |
| `RAPID1203` | ERROR | Misalignment in the contract, state, or producer binding. | Make sure the evidence corresponds to the active run and state. |
| `RAPID1204` | ERROR | Unsafe evidence path outside `.rapid-os/evidence/`. | Keep the canonical structure. |
| `RAPID1205` | ERROR | Copied artifact missing or with a mismatched SHA-256 hash / size. | Verify that the artifact was not modified after being recorded. |
| `RAPID1206` | ERROR | JSON payload does not satisfy the minimum fields for the `EvidenceKind`. | See the [Evidence Cookbook](../cookbooks/evidence-engine.md) for the required schema. |
| `RAPID1207` | ERROR | The evidence references a nonexistent task, gate, or capability. | Verify that the `task_id` or `gate_id` is in the contract. |
| `RAPID1208` | ERROR | Gap in the numeric sequence of evidence (e.g. `E002` is missing between `E001` and `E003`). | Restore the immutable sequence. |
| `RAPID1209` | WARNING | Orphan artifacts directory detected after an interruption. | Run `rapid evidence verify` to audit inconsistencies. |
| `RAPID1210` | ERROR | Referenced evidence file not found on disk. | Verify that the files exist in `.rapid-os/evidence/<run-id>/`. |
| `RAPID1211` | ERROR | Attempt to overwrite an existing evidence file. | Evidence is append-only; new records must use the next ordinal. |

---

## 8. Phase 6 — Behavioral Evals (`RAPID1220–RAPID1229`)

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID1220` | INFO | Behavioral evaluation reports intact. | Informational. |
| `RAPID1221` | ERROR | Invalid `EvaluationReport` schema. | Regenerate the report with `rapid eval run --write`. |
| `RAPID1222` | ERROR | Mismatch in the evaluation report's SHA-256 hash. | Do not edit the files in `.rapid-os/evals/` manually. |
| `RAPID1223` | ERROR | Semantic replay failure (replay mismatch). | The stored report differs from the deterministic computation over the real evidence. |
| `RAPID1224` | ERROR | Unsafe report path. | Keep the reports in `.rapid-os/evals/<run-id>/reports/`. |
| `RAPID1225` | ERROR | `UNVERIFIED` verdict under the `--require-pass` flag. | Record observable evidence for all acknowledged gates. |
| `RAPID1226` | ERROR | `FAIL` verdict under the `--require-pass` flag. | Fix the failed tests or requirements before evaluating. |
| `RAPID1227` | WARNING | The stored report predates the most recent state or evidence. | Run `rapid eval run --write` to generate a new report revision. |
| `RAPID1228` | ERROR | Referenced evaluation report not found. | Run `rapid eval run --write` to create it. |
| `RAPID1229` | ERROR | Attempt to overwrite an existing report revision. | Revisions are append-only (`eval_report_0001.json`, `eval_report_0002.json`). |

---

## 9. Intent Layer and Configuration (`RAPID1300–RAPID1339`)

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID1300` | WARNING | No harness was specified or detected in the environment/configuration. A fallback to `cursor` was applied. | Specify `--harness <id>`, set `RAPID_HARNESS=<id>`, configure `"default_harness"`, or leave a single supported harness in `"tools"` of `.rapid-os/config.json` (with several, the warning lists them). |
| `RAPID1301` | WARNING | Test command (`test_command`) missing or empty in `.rapid-os/config.json`. | Configure `"test_command": ["python", "-m", "pytest"]` (as an argv list) in `.rapid-os/config.json` or initialize with `rapid init --test-command "<cmd>"`. |
| `RAPID1302` | ERROR | Interactive input required in `rapid init` but stdin is not a terminal (or ended with EOF). | Run with the `-y` / `--yes` flag (unattended mode with defaults) or provide complementary flags (`--stack`, `--topology`, `--agents`, `--test-command`). |
| `RAPID1303` | ERROR | Mode playbook or template not found, corrupt, or lacking instructions for the required action. | Verify that the `.json` template file under `templates/modes/<mode>.json` exists and is syntactically valid. |
| `RAPID1304` | ERROR | Active session (`.rapid-os/session.json`) invalid or references a `run_id` that does not exist in `RunRegistry`. | Verify the referenced run or restart the session by creating a new run with `rapid run create`. |
| `RAPID1305` | WARNING | The active run in `.rapid-os/session.json` reached a terminal state without an evaluation verdict. | Start a new specification run or clear the session. A finished run with a verdict is valid. |
| `RAPID1306` | ERROR | Invalid or ambiguous task transition (several in progress without an explicit ID) or no pending tasks. | Explicitly specify the `task_id` (e.g. `T001`) or the mandatory reason for `skip`. |
| `RAPID1307` | ERROR | There is no active session (`.rapid-os/session.json`) to run commands that depend on the current run. | Create or activate a run first with `rapid run create --spec <spec-id>` or `rapid start`. |
| `RAPID1308` | ERROR | Attempt to start a new run (`rapid start`) when a non-terminal active run already exists in the session. | Continue with `rapid next`, abort the existing run with `rapid abort`, or use the `--resume` flag. |
| `RAPID1309` | ERROR | Project not initialized (`.rapid-os/standards/` directory missing when running `rapid start`). | Run `rapid init` to initialize the project standards and configuration. |
| `RAPID1310` | ERROR | Human gate approval (`rapid approve`) invoked without an interactive terminal (TTY) or from an agent session (`CLAUDE_CODE_CHILD_SESSION == 1`), or under an ancestor process that is an agent harness (today `claude`). TTY confirmation can be emulated (script/pty) and acts as defense in depth, not an absolute guarantee (reinforced in PRs 2.1 and 3.2). | Run `rapid approve <gate-id>` directly, by a person in their own interactive terminal, confirming the approval by typing `aprobar <gate-id>`. |
| `RAPID1311` | ERROR | Harness not supported for shortcuts (`rapid shortcuts --harness <id>`). | Use one of `claude`, `codex`, `antigravity`, `cursor`, or `vscode`. |
| `RAPID1312` | ERROR | No harness selected: `--harness` is missing and `.rapid-os/config.json` does not exist or lists no supported harness in `tools`. | Pass `--harness <id>` or run `rapid init --agents <list>`. |
| `RAPID1313` | ERROR | Shortcut template missing or invalid under `templates/shortcuts/<name>.md` (frontmatter, description, or body). | Restore the template from the Rapid OS installation or reinstall the package. |
| `RAPID1314` | ERROR | A shortcut file could not be read, written, or deleted: unsafe path, symbolic link, file system error, or different content rendered by two harnesses for the same path. | Check permissions and that the path is not a symbolic link; retry. |
| `RAPID1315` | WARNING | Mode shortcut skipped: the `templates/modes/<mode>.json` playbook does not exist. | Expected until the mode has a playbook; when you add it, run `rapid shortcuts install` again. |
| `RAPID1316` | WARNING | An existing shortcut file does not carry the `generated by rapid shortcuts` marker and will be replaced. | The previous version is kept as `.bak`; review it before continuing or use another name for your own skill. |
| `RAPID1317` | WARNING | `rapid shortcuts remove` skipped a file without the `generated by rapid shortcuts` marker. | Delete it manually if you really want to; Rapid OS only deletes files it generated. |
| `RAPID1318` | ERROR | `rapid shortcuts` was invoked without a subcommand. | Use `install`, `list`, or `remove`. |
| `RAPID1319` | WARNING / INFO | `rapid doctor`: the parent process chain could not be read (WARNING; `rapid approve` cannot look for an agent harness among its ancestors and applies only the TTY and `CLAUDE_CODE_CHILD_SESSION` checks), or `doctor` runs under an agent harness (INFO; there `rapid approve` is rejected with `RAPID1310`). | In the WARNING case, check the permissions of `/proc`, the availability of `ps`, or platform support; in the INFO case, run `rapid approve` in your own terminal. |
| `RAPID1320` | ERROR | `rapid check --expect fail` tied to a gate (`--gate`) or invoked without a valid task (requires `--task <id>` or exactly one `in_progress` task). | Specify `--task <task_id>` or verify that there is exactly one `in_progress` task in the active session. Tying expected failures to gates is not allowed. |
| `RAPID1321` | WARNING | `rapid shortcuts install`, `list`, and `rapid init --shortcuts`: the harness selection leaves the same `/rapid-*` in two folders that a single tool reads (`cursor` or `vscode` together with `claude`, `codex`, or `antigravity`). It is only a warning: it changes neither the exit code nor what is written, and the official Cursor and VS Code documentation does not specify how they display same-named skills in different folders. | Install only the combination recommended in the warning (the tool already reads those folders); see "If you combine harnesses" in the [shortcuts guide](../guides/shortcuts.md#if-you-combine-harnesses). |
| `RAPID1322` | ERROR | `rapid start <mode> --spec-file`: a spec with the same identity (id or title) and **different content** already exists (or is archived). With the same content it is reused without error. | Reuse the existing spec with `rapid start <mode> --spec <id>`, or change the title/`id` of the spec file. |
| `RAPID1330` | ERROR | `rapid approve` with incompatible options: `--reject` and `--waive` together, or either one without `<gate-id>`. | Use a single action and pass the gate (`rapid approve` lists the pending ones). |
| `RAPID1331` | ERROR | The reviewer could not be determined: `--reviewer` was not passed, `git config user.name` is not set, and no name was entered in the terminal. | Pass `--reviewer <name>` or run `git config user.name "<name>"`. |
| `RAPID1332` | ERROR | The gate does not exist, is not a human gate, is no longer pending, or was rejected (`changes_requested`) and stays FAIL for the rest of the run. | Verify the id with `rapid approve`; if it was rejected, run `rapid abort` and start a new run. To take back a decision: `rapid abort` before `rapid finish`; after `rapid finish`, `git revert` and a new run ([Undo an approval](../guides/undo-approval.md)). |
| `RAPID1333` | ERROR | `--reason` is missing on `--reject`/`--waive`, the gate is not waivable according to the contract, or the run is not in a state that allows modifying the gate (it must be `active` with all tasks terminal). | Provide `--reason`, waive only waivable gates (e.g. `gate.review`), and complete the tasks before approving. |
| `RAPID1334` | ERROR | The isolated worktree of `rapid start --worktree` could not be created (not a git repository, no commits, the path `../<repo>-<run-id>` already exists, or `git worktree add` failed; on Windows it may say `Filename too long`). | Confirm a git repository with at least one commit, free the path, and retry `rapid start --resume --worktree`. For `Filename too long`, run `git config core.longpaths true` in this repository. Rapid uses `-c core.longpaths=true` for worktree git commands. |
| `RAPID1335` | ERROR | The worktree recorded in `workspace_path` of `session.json` no longer exists. | Restore it with `git worktree add` at that path or cancel the run with `rapid abort`. |
| `RAPID1340` | WARNING | On Windows, an evidence artifact path exceeds 200 characters from the repository root and `core.longpaths` is disabled. | Run `git config core.longpaths true` in this repository before creating or removing worktrees. |
| `RAPID1341` | ERROR | `rapid finish --merge` needs written confirmation or could not complete the commit and merge. | Type `integrar <run-id>` exactly; resolve source checkout changes or merge conflicts before retrying. |
| `RAPID1342` | ERROR | `rapid check` was invoked for a terminal run still referenced by the session. | Start a new run with `rapid start`. |
| `RAPID1343` | ERROR | `rapid start hardening`: a finding is missing, malformed, has an invalid CWE/CVSS vector or severity, or cites a standard absent from `security.md`. The message names the finding. | Correct the reported `findings[]` entry using a CWE, complete CVSS v4.0 vector and a `standard_ref` cited in `.rapid-os/standards/security.md`. |
| `RAPID1336` | ERROR | `rapid attach` failed: no `--label`, nonexistent file, outside the project and the workspace, under `.rapid-os/`, or nonexistent task. | Fix the path, provide `--label` and, if applicable, a valid `--task`. |
| `RAPID1337` | ERROR | `rapid shortcuts install --hooks` / `remove --hooks` (or `rapid init --hooks`, where it is reported as a warning) without the `claude` harness selected. | Select `claude` (`--harness claude` or `tools` in `.rapid-os/config.json`) or remove `--hooks`. |
| `RAPID1338` | ERROR | `.claude/settings.json` cannot be merged: invalid JSON, a root that is not an object, `hooks` or `hooks.<Event>` with an unexpected type, or an error writing it. The file is not modified. | Fix the file by hand (or restore the `.bak`) and repeat the command. |
| `RAPID1339` | WARNING | `rapid doctor`: Claude Code hooks are installed but `rapid` does not resolve on the `PATH`; Claude Code treats the failure as a non-blocking error and the run stops being enforced. | Install Rapid OS where Claude Code can see it (e.g. `pipx install git+https://github.com/alyconr/Rapid-OS.git`) or add its scripts directory to the `PATH`. |

## 10. Stack catalog, onboarding, architecture, and security (`RAPID1400–RAPID1429`)

| Code | Level | Meaning | Action |
|---|---|---|---|
| `RAPID1400` | INFO | `.rapid-os/setup.json` exists and is valid ("Setup válido"). Emitted by `rapid validate`. | None. |
| `RAPID1401` | ERROR | Invalid catalog sidecar under `templates/stacks/`, `templates/topologies/`, or `templates/setup/`: unreadable JSON, `schema_version` other than 1, missing or empty field, `id` different from the file name, unknown topology in `compatible_topologies`, `default_topology` outside `compatible_topologies`, or a malformed question bank. In a stack under `templates/stacks/<component>/`: component different from its folder, `covers` without its component, incomplete `factors` or `sources` (all eleven factors and at least one https URL for each), `hosting_fit` outside `serverless`, `containers`, and `PaaS`, `supported_services` with an engine that is not in `templates/services/`, or a repeated id. A topology without `components`. `rapid init` aborts with this code instead of a traceback. | Fix or restore the indicated file from the Rapid OS installation, or reinstall the package. |
| `RAPID1402` | ERROR | `rapid setup set topology <id>` with a topology incompatible with the stack already chosen (according to the catalog's `compatible_topologies`; a stack outside the catalog accepts all but `doc-site`), or `rapid setup set services` with an engine the stack does not support (the stack's `service_roles`). Nothing is written. When changing the stack with `set stack`, a topology that no longer fits is not an error: it is left undecided. | Choose a topology from the list shown by the message or `rapid setup next`. Also applies to a topology that does not fit one of the stacks already chosen (one per component), and to `rapid setup set services` with an engine that the backend stack does not declare in `supported_services` (the message lists the ones it does). |
| `RAPID1406` | ERROR | `.rapid-os/setup.json` is invalid: unreadable JSON, `schema_version` other than 1, or a field with a disallowed type or value (`stack`, `docs.<id>.status`, etc.). `rapid setup next` and `show` exit with 1 without a traceback and do not modify the file. | Fix the file according to the message, or move it so the state is derived from disk. |
| `RAPID1403` | WARNING / ERROR | An onboarding document drafted by the agent (`source: drafted`) lacks a section required by its bank: there is no `## ` heading matching any of its titles (es/en, case-insensitive). Not evaluated for `source: provided`. **Dual use:** in `rapid validate` it is a WARNING about an already-written document; in `rapid setup doc <id> --source drafted` it is a rejection (ERROR, exit 1) and nothing is written. | Add the section or redo the document. Conditional sections (`Base de datos local` in `DATA_MODEL.md` with a `database` service) count while their condition holds. |
| `RAPID1404` | WARNING / ERROR | An onboarding document drafted by the agent exceeds its bank's `max_chars`. Not evaluated for `source: provided`. Same dual use as `RAPID1403`: WARNING in `rapid validate`, rejection (exit 1, nothing written) in `rapid setup doc ... --source drafted`. | Shorten the document. |
| `RAPID1405` | ERROR | `rapid setup doc <id> --source drafted` on a document that a person supplied (`source: provided`) or on a hand-written file: the draft would replace it. Nothing is written. | Repeat with `--replace` if you want to replace it (a `.bak` is kept), or leave the document as it is. |
| `RAPID1407` | ERROR | `rapid setup finish` while a decision remains open (stack, topology, archetype, agents, test command, a `pending` document, or the draft review, `review_drafts`, not closed). Nothing is written. | Run the command indicated by the message (the `command` of `rapid setup next`) and repeat `finish`. |
| `RAPID1408` | WARNING | An onboarding document drafted by the agent is still unconfirmed by a person; it reaches the agent as an assumption. | Have a person review and confirm it. |
| `RAPID1409` | ERROR | `rapid setup stack --custom` received a `tech-stack.md` missing one of the `Runtime`, `Framework`, or `Testing` sections (a `## ` heading or a `- **Name:**` line). Nothing is written. | Add the sections the message names and repeat the command. |
| `RAPID1410` | WARNING | `standards/business.md` and `docs/BUSINESS_RULES.md` exist and their bodies differ (ignoring frontmatter and normalizing whitespace). `docs/BUSINESS_RULES.md` wins; the standard is left out of the context. | Unify the content or delete `standards/business.md`. |
| `RAPID1412` | WARNING | A stack or topology template (`.md`) has no `.json` sidecar. The template remains usable and is treated as compatible with all topologies except `doc-site`. | Add `templates/<stacks\|topologies>/<id>.json` to declare `compatible_topologies` and `default_topology`; it is not mandatory. |
| `RAPID1413` | ERROR | Invalid `rapid setup` subcommand, key, or value: unknown `set` key, nonexistent stack/topology/archetype/agent, unreadable or empty `--file`, unknown document, unknown `services` role or engine or an incompatible role-engine pair (`rapid setup set services <role>:<engine>`, with optional `@now` or `@later`), unknown platform in `rapid deploy --target` (`Plataforma desconocida`), `--component` with a key that is not `stack`, an unknown component or one the stack cannot fill (`rapid setup set stack go --component frontend`), a combination of `doc` modes (`--skip`, `--confirm`, `--reopen`, `--from-legacy`, `--source`), nothing to confirm or import, `--skip` of an already-written document, or `rapid setup` without a subcommand, `rapid setup review` without `--done`; also `rapid init --business-file` with an empty path, a directory, or an unreadable file, and `rapid start bugfix\|refactor\|hardening` in a new repository, with no code or tests (`No hay código que arreglar\|refactorizar\|endurecer; usa /rapid-feature`), and `rapid shortcuts install\|list\|remove` with `--global` for a harness without a documented user folder (`vscode`), without `--harness` or with `--hooks`, or with an `--only` that is not a shortcut. | Use `next`, `show`, `set`, `stack`, `doc`, or `finish` with values from `rapid setup next`. |
| `RAPID1414` | WARNING | `rapid init` installed shortcuts or hooks, or `rapid doctor` found them, and `rapid` does not resolve on the `PATH`: they run from the agent's shell. It does not change the exit code (0). | Install Rapid OS with the installer or with `pipx install git+https://github.com/alyconr/Rapid-OS.git`, or add its scripts directory to the `PATH`. |
| `RAPID1415` | ERROR / WARNING | The body of an onboarding document has a `?` between two letters or at the start of a word (`vac?os`, `Decisi?n`, `?xito`): what a non-UTF-8 pipe (the one from Windows PowerShell 5.1 to native programs uses ASCII) leaves in place of accents and `ñ`. Code blocks, inline code, and URLs are ignored. In `rapid setup doc <id> --source drafted` it is a rejection (exit 1, nothing is written); with `--source provided` it is a WARNING and the text is saved as is, because Rapid OS does not rewrite what the person pastes. | Write the document to a UTF-8 file and send it with `--file <path>`. In Windows PowerShell: `Set-Content -Encoding utf8 $env:TEMP\rapid-<id>.md` and `rapid setup doc <id> --source drafted --file $env:TEMP\rapid-<id>.md`. |
| `RAPID1416` | ERROR | `rapid start` in a folder that is not a git repository, without git installed, or in a repository git does not trust. Rapid OS observes the run's changes with git and the run could never pass. It is checked before the run is created and before the empty-repository rejection (`RAPID1413`): nothing is written to `.rapid-os/runs` or `session.json`. | Run `git init`, or `rapid setup finish`, which creates the repository (with no commits) if it is missing; install git if it is not installed. **Folder git does not trust** (`detected dubious ownership`, common on Windows on another drive or in folders created by another user): same code, different text (`RAPID1416 git no confía en esta carpeta (dubious ownership) ...`); `git init` does not fix it, you must run `git config --global --add safe.directory <path>` with the path the message prints. `rapid setup finish` does not run `git init` in that case: it warns with the same command. Rapid OS runs all its git commands with `-c safe.directory=<project root>`, so `untrusted` only happens if git does not honor that setting (versions before 2.38) or if the repository is in a folder above the project root. The usual case of the Codex sandbox on Windows (another user) no longer blocks Rapid OS: the only thing pending is the exception for the person's own git, which arrives as `person_actions` (`git-safe-directory`) in `rapid setup finish`, `rapid setup next --json`, and `rapid doctor`. See [Windows: sandbox and git](../integrations/codex.md#windows-sandbox-and-git). |
| `RAPID1417` | ERROR | A command that writes state (`rapid setup set`, `init`, `start`, `finish`, `check`...) was run from the home folder, where `.rapid-os` is the Rapid OS installation (`~/.rapid-os`), not a project. Nothing was written. | `cd` into your project and run it again. `rapid doctor` there says "No estás en un proyecto" instead of reporting false errors. |
| `RAPID1420` | ERROR | `rapid arch check` found an import that breaks the architecture rule in `.rapid-os/standards/architecture.json`; one is emitted per violation, with file, line, import, and rule: `layer` (a layer imports a layer it is not allowed to), `cross_module` (a module imports from another something other than its public entry point), `shared` (`shared` imports a module), `init_reexport` (the `__init__.py` of a Python module imports something other than its own `public.py`), or `domain_forbidden_import` (`domain` imports `fastapi`, `sqlalchemy`, `react`, `@prisma/client`... depending on the stack). It is also used for an unreadable or invalid `architecture.json` and for a run whose contract includes `gate.architecture` when there is no `architecture.json` in the current directory or in the session's main project (`el run exige gate.architecture y no hay architecture.json`). In a run, it makes `rapid check --gate gate.architecture` fail and `rapid finish` does not give `PASS`. | Change the code to respect the rule (import only the other module's public entry point, move the logic to the layer where it belongs, remove the library from `domain`). Never disable or edit `architecture.json` to make it pass: ask the person to change the rule. In a Ruby on Rails project the rule delegates to `bin/packwerk check`: if packwerk is not there (`RAPID1420 packwerk no está disponible...`) the check ends with 1 and the gate is not considered satisfied; install it with `bundle add packwerk --group development && bundle binstub packwerk`. With an `architecture.json` of several rules (`rules`), each is judged in its own folder. |
| `RAPID1421` | WARNING | `rapid doctor` found `.rapid-os/standards/security.md` and it does not mention OWASP ASVS: the project was initialized before the security baseline (OWASP Top 10:2025, ASVS 5.0.0, SSDF, SLSA). It does not change the exit code. | Run `rapid setup set archetype <the current one> --refresh` (the warning writes it out with the project's archetype): it regenerates `security.md` and `coding-rules.md` and leaves the previous copies in `.rapid-os/backups/`. |
| `RAPID1422` | ERROR | `rapid finish` ran `gate.architecture` again on the final state of the code and found a violation that was not there when the gate passed (or the rule is gone). It prints the violations (`RAPID1420`), exits 1 and leaves the run open with no verdict. Fix the code and run `rapid finish` again. |
| `RAPID1423` | ERROR | `rapid approve` or `rapid finish` found the working tree different from the one the last `gate.tests` check saw (a file edited, a test deleted); `rapid next` returns `verify` with the same message. Nothing verified those changes. | Run `rapid check --gate gate.tests -- <test command>` again and repeat the command; the message names the changed files. |
| `RAPID1424` | ERROR | Text handed to `rapid start --spec-file`, `rapid setup doc --file` or `rapid setup stack --custom --file` (from stdin or a file) is not valid UTF-8. Nothing was stored. | Save the content as UTF-8 and send it again. Rapid OS reads input as bytes and decodes UTF-8 (a BOM is fine), so the console code page does not matter. |
| `RAPID1425` | WARNING | `rapid doctor` found `Ã¡`, `Ã©`, `Ã³`, `Ã±`... in a saved spec or onboarding document: UTF-8 text that was read as cp1252 (older versions on Windows). Saved specs are not rewritten (the registry has digests). A revision fixes the text but not the id: if the id came out altered too, a new spec is needed. | Create a new revision of the spec with the right text (`rapid spec revise`); rewrite a document with `rapid setup doc <id> --source drafted --replace --file <path>`. |
| `RAPID1426` | WARNING | `test_command` in `.rapid-os/config.json` cannot be run: its first element is not on the `PATH` (on Windows `.cmd` and `.exe` count) nor a file of the project. `rapid doctor` and `rapid start` say so before the baseline fails with "command not found". | Run `rapid setup set test-command --recommended`: it applies the command the stack catalog proposes for the decided stacks (the message lists the command of each component to read). With the onboarding finished it already writes `config.json`. Without a catalog proposal, `rapid setup set test-command '<cmd>'`. |
| `RAPID1427` | WARNING | `rapid setup` is about to regenerate an agent file (`CLAUDE.md`, `AGENTS.md`, `INSTRUCTIONS.md`...) that differs from what Rapid OS wrote last time: it was edited by hand. The file is rewritten and the previous copy goes to `.rapid-os/backups/`. A change of line endings alone (CRLF/LF) is not an edit. | Move what you want to keep into `.rapid-os/standards/` (the source of those files) and regenerate; or recover it from the backup. |

---

## 11. Project validation: standards, configuration, stack, and context (`RAPID200–RAPID502`)

Emitted by `rapid validate` and `rapid doctor` over `.rapid-os/`.

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID200` | ERROR | The project's `.rapid-os/` folder is missing. | Run `rapid init` (or `rapid setup next`) at the project root. |
| `RAPID201` | ERROR | `.rapid-os/standards/` is missing. | Run `rapid init` to regenerate the standards. |
| `RAPID202` | ERROR | A mandatory standard is missing (`tech-stack.md` or `topology.md`). | Run `rapid setup finish` or `rapid init` to generate it. |
| `RAPID203` | WARNING | An optional standard is missing (`security.md`, `business.md`, or `coding-rules.md`). | Informational; `rapid setup finish` writes `security.md` and `coding-rules.md`. |
| `RAPID204` | ERROR | A standard is not valid UTF-8. | Save it as UTF-8 or regenerate it. |
| `RAPID205` | ERROR | A standard could not be read. | Check the permissions and existence of the file. |
| `RAPID206` | ERROR | A mandatory standard is empty. | Regenerate it with `rapid init` or `rapid setup finish`. |
| `RAPID207` | WARNING | An optional standard is empty. | Complete it or delete it. |
| `RAPID208` | WARNING | A standard contains unresolved markers (`{{...}}`, `TODO`, `REPLACE_ME`...). | Replace them with the real content. |
| `RAPID300` | WARNING | `.rapid-os/config.json` is missing; the default tools are used. | Run `rapid init` or `rapid setup set agents <ids>`. |
| `RAPID301` | ERROR | `config.json` is not valid JSON. | Fix the syntax or restore the file from `.rapid-os/backups/` or its `.bak`. |
| `RAPID302` | ERROR | `config.json` could not be read. | Check the file permissions. |
| `RAPID303` | ERROR | The `config.json` schema is invalid (for example `tools` is not a list). | Fix the field indicated by the message. |
| `RAPID304` | WARNING | No tools are selected in `config.json`. | Choose them with `rapid setup set agents <ids>`. |
| `RAPID305` | ERROR | The `tools` ids in `config.json` must be strings. | Leave only text ids in `tools`. |
| `RAPID306` | INFO | A known research tool was selected (`context7`, `firecrawl`). | Informational. |
| `RAPID307` | ERROR | Reference to an unknown tool in `config.json`. | Use a registered agent or a known research tool (the warning lists them). |
| `RAPID308` | ERROR | The selected agent has no registered adapter. | Choose an agent from the supported list. |
| `RAPID309` | ERROR | The adapter failed to render the validation context. | Reinstall Rapid OS; if it persists, open an issue with the message. |
| `RAPID310` | ERROR | The adapter did not render one of the outputs it declares. | Reinstall Rapid OS; it is an adapter defect. |
| `RAPID311` | ERROR | The adapter declares an unsafe output path (absolute or with `..`). | Reinstall Rapid OS; it is an adapter defect. |
| `RAPID400` | INFO | Stack detected in `tech-stack.md`. | Informational. |
| `RAPID401` | INFO | Topology detected in `topology.md`. | Informational. |
| `RAPID402` | ERROR | The stack only supports the `doc-site` topology. | Change the topology with `rapid setup set topology doc-site` or choose another stack. |
| `RAPID403` | ERROR | The `doc-site` topology must use the `docs-modern` stack. | `rapid setup set stack docs-modern` or change topology. |
| `RAPID404` | ERROR | The stack is not compatible with the chosen topology (the message lists the compatible ones). | Choose a compatible topology or change the stack. |
| `RAPID405` | WARNING | `fullstack-baas` with `python-ai`: the topology is designed for integrated web applications. | Confirm that the combination is intentional. |
| `RAPID500` | ERROR | The project's assembled context is empty. | Regenerate the standards with `rapid init` or `rapid setup finish`. |
| `RAPID501` | INFO | Length of the assembled context. | Informational. |
| `RAPID502` | WARNING | The assembled context contains unresolved markers. | Replace the markers in the standards that contain them. |

---

## 12. `rapid validate` environment (`RAPID900–RAPID909`)

`rapid validate` opens its report with the environment it used; they are informational except `RAPID906`.

| Code | Severity | Common cause | Remediation action |
| :--- | :--- | :--- | :--- |
| `RAPID900` | INFO | Current directory. | Informational. |
| `RAPID901` | INFO | Rapid OS directory (`RAPID_HOME`). | Informational. |
| `RAPID902` | INFO | Script directory. | Informational. |
| `RAPID903` | INFO | Templates directory in use. | Informational. |
| `RAPID904` | INFO | The project's `.rapid-os/` directory. | Informational. |
| `RAPID905` | INFO | Configuration file in use. | Informational. |
| `RAPID906` | WARNING | Node.js/npx is not available: remote skills and some MCP flows will not work. | Install Node.js if you use those flows. |
| `RAPID907` | INFO | There is no Rapid OS project in the current directory. | Run `rapid init` or enter the project root. |
| `RAPID908` | INFO | Default harness from `config.json`. | Informational. |
| `RAPID909` | INFO | Test command from `config.json`. | Informational; change it with `rapid setup set test-command <cmd>`. |


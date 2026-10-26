# Rapid OS v3.1.0 Release Notes

**Release Version**: `3.1.0`  
**Artifact Schema Version**: `1` (`BehavioralRuleset` versions `1` and `2`; `2` is the default)  
**Python Requirement**: Python `>=3.10` (`3.10`, `3.11`, `3.12`, and `3.13` verified in CI)

---

## 1. Overview

**Rapid OS v3.1.0** adds the **intent layer ("porcelain")** on top of the v3 governance engine ("plumbing"). The plumbing (`rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) is unchanged; the porcelain verbs (`rapid start`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`, `rapid approve`, `rapid status`, `rapid abort`) drive a governed run on top of it, and `/rapid-<mode>` **shortcuts** teach each coding harness to follow that loop.

What does not change: Rapid OS does not invoke agents, does not use an LLM as a judge, and never approves a human gate. The plumbing runs nothing; the porcelain runs only the `test_command` of `.rapid-os/config.json` or the argv given to `rapid check`, creates a worktree only with `rapid start --worktree`, and uses read-only `git` commands to record the run's changes.

---

## 2. What's Included in v3.1.0

### Porcelain layer
- `rapid start <mode>`, `rapid next`, `rapid check`, `rapid task`, `rapid attach`, `rapid finish`, `rapid approve`, `rapid status` and `rapid abort`.
- A pure Conductor (`next_action`) that asks the `BehavioralEvaluator` what is missing and returns a `NextAction`; `.rapid-os/session.json` remembers the active run.
- Evidence producers `rapid:check`, `rapid:start`, `rapid:finish` and `rapid:attach`. See [orchestration architecture](./architecture/orchestration.md).

### Five engineering modes
- Playbooks in `templates/modes/` for `feature`, `bugfix`, `refactor`, `hardening` and `research`.
- `bugfix`: baseline before the red test and `rapid check --expect fail` on `T001`. `refactor`: blocked when passing tests drop below the baseline. `hardening`: isolated git worktree with `rapid start --worktree`. `research`: `rapid attach`, no mandatory tests.

### Behavioral ruleset v2
- `expectation: "fail"` evidence produces a `reproduction.<task>` assertion and does not count as a failing task or as gate evidence (`RAPID1320`).
- Review evidence produced by a `harness:*` producer cannot close a human gate.

### Shortcuts
- `rapid shortcuts install|list|remove` and `rapid init --shortcuts` generate eight shortcuts (`rapid-feature`, `rapid-bugfix`, `rapid-refactor`, `rapid-hardening`, `rapid-research`, `rapid-next`, `rapid-status`, `rapid-approve`) for Claude Code, Codex, Antigravity, Cursor and VS Code from `templates/shortcuts/`. Idempotent, with `.bak` backups (`RAPID1311`–`RAPID1318`).
- A `RAPID1321` warning flags harness selections that leave the same shortcut in two folders one tool reads. In `--json`, `warnings` is a list of `{code, message, ...}` objects. See the [shortcuts guide](./guides/shortcuts.md).

### Claude Code hooks
- `rapid hook stop|pre-tool`, installed with `rapid shortcuts install --hooks` or `rapid init --hooks`: keep the agent working until a person is needed and deny reserved commands (`rapid approve`, `rapid abort`, `rapid run gate`, `rapid evidence add`) and edits inside `.rapid-os/` (`RAPID1337`–`RAPID1339`).

### Hardened human approval
- `rapid approve` requires a TTY, refuses `CLAUDE_CODE_CHILD_SESSION=1` and refuses when any ancestor process is Claude Code (`RAPID1310`; `RAPID1319` in `rapid doctor` when the ancestry cannot be read). Without arguments it lists pending human gates; `--waive` (waivable gates only) and `--reject` take a mandatory `--reason` (`RAPID1330`–`RAPID1336`).

### Fixes
- `rapid finish` no longer fails in text mode, no longer attributes pre-existing untracked files to the run, and exits by verdict on a run that already ended.
- Runs without a baseline gate and isolated runs can leave `prepared`; expected failures at `rapid start` and `rapid approve` are reported with a RAPID code instead of a traceback.

### Documentation and portal
- Shortcuts are the main flow; the v3 commands are the advanced mode. New pages: shortcuts guide and orchestration architecture. Product boundaries state exactly what is executed. The unused default Docusaurus template `site/` was removed.

---

## 3. New CLI Surface

```text
rapid start      (<mode> [--spec-file <path>|-] [--spec <id>] [--harness <id>] [--resume] [--worktree] [--json])
rapid next       ([--json])
rapid check      ([--task <id>] [--gate <id>] [--expect fail] [--json] -- <command>)
rapid task       (start | done | skip)
rapid attach     (<path> --label <text> [--task <id>])
rapid finish     ([--json])
rapid approve    ([<gate>] [--reviewer <name>] [--waive | --reject] [--reason <text>])
rapid status     ([--json])
rapid abort      ([--reason <text>])
rapid shortcuts  (install | list | remove) [--harness <id>] [--dry-run] [--hooks] [--json]
rapid hook       (stop | pre-tool)
rapid init       (... [--shortcuts] [--hooks])
```

---

## 4. Compatibility & Upgrade Notes

- **v3 commands and flags are unchanged.** Existing scripts that call `rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`, `rapid validate` and the legacy v2 commands keep working without modification.
- **JSON output only gains optional fields.** New fields (`workspace_path`, `start_untracked`, `action.spec_template`, `warnings` in `rapid shortcuts --json`) are omitted when unused.
- **Ruleset v2 is the default** for `rapid eval run`; `--ruleset 1` remains available.
- **v1 reports stay valid.** A persisted `EvaluationReport` is replayed with the ruleset it was written with.
- **No schema or digest changes.** Specs, contracts, `RunState`, `RunEvidence` and `EvaluationReport` keep `schema_version = 1` and their digests; there is nothing to migrate in specs, runs, evidence or evals.
- **Package version is `3.1.0`**; all v3 JSON schemas remain at `schema_version = 1`. The governance core still uses only the Python standard library; optional integrations such as remote skills use Node.js/`npx` and need network access.

---

## 5. Known Limits

- **Human approval is best-effort, not cryptographic.** The ancestry check does not see a process that detaches from its parent (double fork, `setsid`, `nohup … &`), a renamed `claude.exe` or a reused pid; a TTY can be emulated; and the reviewer identity is the one declared (`--reviewer` or `git config user.name`). The rule is unchanged: a person approves, in their own terminal.
- **Ancestry detection covers Claude Code only.** Codex and Cursor are not detected because their process names are not confirmed.
- **Hooks exist only for Claude Code**, and the command analysis they perform is best-effort: it cannot stop a command built at runtime.
- **Duplicate shortcuts across tools.** Cursor and VS Code also read `.claude/skills` and `.agents/skills`; their documentation does not say how same-named skills in different folders are shown, hence the `RAPID1321` warning.

---

## 6. How to Upgrade

See [De 3.0 a 3.1](./installation/upgrade.md#5-from-30-to-31). In short:

```bash
rapid --version                      # Rapid OS 3.1.0
rapid shortcuts install              # regenerate the shortcuts in your project (add --hooks for Claude Code)
```

Add `.rapid-os/session.json` and `.rapid-os/scratch/` to `.gitignore`, and set `test_command` in `.rapid-os/config.json`.

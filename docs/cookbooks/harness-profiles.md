---
title: Harness Profiles and Capabilities
description: Cookbook for configuring coding harness profiles, resolving capability compatibility, and generating locks in RAPID OS.
---

# Harness Profiles and Capabilities

In the agent-assisted engineering ecosystem, different editors and assistants (Cursor, Claude Code, GitHub Copilot, Codex, Antigravity) offer different sets of tools and integrations.

RAPID OS does not assume that all environments can perform the same actions. Through the **Harness Capability Registry**, it declares, versions, and audits which capabilities each assistant declares it supports.

---

## Product Truth: What a Capability Represents

> **Product Truth Principle**:
> 1. A declared capability (e.g. `repository.write`, `shell.execute`) expresses the **support the harness declares it offers**.
> 2. RAPID OS does **not** directly invoke the harness or control the operating system's processes or permissions.
> 3. A harness declaring a capability is **not evidence** that it was exercised or that the result is free of defects.

---

## Canonical Capabilities Catalog

The RAPID OS catalog defines exactly the following 11 canonical capabilities:

| Identifier | Category | Description |
| :--- | :--- | :--- |
| `context.consume` | `context` | Ability to read and consume the compiled context and execution contracts. |
| `git.inspect` | `git` | Ability to inspect git state, history, and diffs. |
| `git.modify` | `git` | Ability to create branches, commits, or worktrees in git. |
| `mcp.invoke` | `integration` | Ability to invoke Model Context Protocol (MCP) tools and resources. |
| `repository.read` | `repository` | Ability to read repository files and structure. |
| `repository.write` | `repository` | Ability to create or modify repository files during the task. |
| `shell.execute` | `execution` | Ability to run terminal or local shell commands. |
| `subagents.delegate` | `delegation` | Ability to delegate subtasks to specialized subagents. |
| `tests.execute` | `testing` | Ability to run automated test suites for verification. |
| `workspace.current` | `workspace` | Ability to operate in the current working tree when policy allows it. |
| `workspace.isolated` | `workspace` | Ability to operate in an isolated workspace or worktree when policy requires it. |

---

## 1. Built-in Profiles

RAPID OS ships with default canonical profiles:

```bash
# List all available profiles
rapid harness list

# View the detailed capabilities of a built-in profile
rapid harness show codex
rapid harness show claude
rapid harness show cursor
rapid harness show antigravity
```

---

## 2. Customize or create a local profile

You can override a default profile or register your team's proprietary harness in `.rapid-os/harnesses/<id>.json`:

```bash
# Initialize the template of an existing or new profile
rapid harness init my-internal-agent
```

### Canonical Structure of `.rapid-os/harnesses/<id>.json`

The profile file follows schema version 1 (`HarnessProfile`):

```json
{
  "schema_version": 1,
  "id": "my-internal-agent",
  "capabilities": [
    {
      "capability_id": "context.consume",
      "status": "supported",
      "reason": "Reads the compiled context directly from .rapid-os/context"
    },
    {
      "capability_id": "repository.read",
      "status": "supported",
      "reason": "Full read access to the entire repository tree"
    },
    {
      "capability_id": "repository.write",
      "status": "supported",
      "reason": "Write access restricted to code and test files"
    },
    {
      "capability_id": "shell.execute",
      "status": "supported",
      "reason": "Runs linter tools and local commands"
    },
    {
      "capability_id": "tests.execute",
      "status": "supported",
      "reason": "Runs pytest suites in the terminal"
    },
    {
      "capability_id": "git.inspect",
      "status": "supported",
      "reason": "Inspects git diffs and status"
    },
    {
      "capability_id": "git.modify",
      "status": "unsupported",
      "reason": "Commits and branch changes are handled by the developer"
    },
    {
      "capability_id": "subagents.delegate",
      "status": "unknown",
      "reason": "Subagent support pending validation in the corporate environment"
    }
  ]
}
```

### Allowed support levels (`CapabilitySupportStatus`)

The only three canonical states allowed for `status` are:

- **`supported`**: The capability is available and declared as supported by the environment.
- **`unsupported`**: The capability is neither available nor supported in this working environment.
- **`unknown`**: The support status is undetermined or has not been explicitly declared.

> **Important**: RAPID OS does **not** support states such as `conditional`. If a capability has operational restrictions, declare it as `supported` or `unsupported` and detail the specific conditions in the `reason` field.

---

## 3. Deterministic Locking (`rapid harness lock`)

To guarantee that CI pipelines or developers use exactly the same profile definitions and capability hashes, you can generate the `.rapid-os/capabilities.lock` file:

```bash
rapid harness lock
```

This command inspects all active profiles, computes their canonical SHA-256 digest, and freezes them in an immutable file versioned in git.

---

## 4. Compatibility Resolution Against a Run

When an `ExecutionContract` is created, it defines which capabilities the task requires. You can deterministically verify whether the assigned harness satisfies those requirements:

```bash
# Basic resolution
rapid harness resolve --run feature-payment-r1-run-001

# Strict resolution against the lock file (.rapid-os/capabilities.lock)
rapid harness resolve --run feature-payment-r1-run-001 --locked

# CI gate mode resolution (exit code 1 if incompatible or unresolved)
rapid harness resolve --run feature-payment-r1-run-001 --require-compatible
```

### Resolution states (`CapabilityResolutionStatus`):
1. **`compatible`**: The harness declares support (`supported`) for all mandatory capabilities required by the contract. (Exit code `0`).
2. **`incompatible`**: The harness marks at least one capability required by the contract as unsupported (`unsupported`). (Exit code `1` with diagnostic `RAPID1110` under `--require-compatible`).
3. **`unresolved`**: One or more required capabilities are in the `unknown` state or have not been declared. (Exit code `1` under `--require-compatible`).

---

## 5. Requiring Additional Capabilities in the CLI

If a particular run requires a capability not originally required by the spec, you can force its evaluation at resolution time:

```bash
rapid harness resolve \
  --run feature-payment-r1-run-001 \
  --require "shell.execute" \
  --require-compatible
```

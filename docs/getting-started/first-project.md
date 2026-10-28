---
title: Your First Project
description: From an empty folder to your first approved feature with /rapid-init and /rapid-feature.
---

# Your First Project

Go from an empty folder to a completed and approved feature. You enter three things in your agent and one in your terminal.

- **You need:** Rapid OS installed (`rapid --version` responds) and a coding agent (Claude Code, Codex, Cursor, Antigravity, or VS Code).
- **Time:** about 15 minutes.

## Main workflow: `/rapid-init`

### 1. Make shortcuts available

If you selected an agent when installing Rapid OS, shortcuts are ready. Otherwise, install them once:

```bash
rapid shortcuts install --global --harness claude
```

Replace `claude` with `codex`, `cursor`, or `antigravity`. In VS Code, or to keep shortcuts in the repository, run `rapid init --shortcuts` from the project directory.

### 2. Create a folder and describe the project

```bash
mkdir hello-rapid && cd hello-rapid
```

Open your agent in that folder and enter (in Codex, use `$rapid-init`):

```text
/rapid-init a Python API for validating usernames
```

### 3. Respond to its proposals

The agent asks you to decide on the stack, topology, archetype (MVP or Corporate), test command, and four project documents (brief, business rules, data model, and architecture). For each decision it recommends an option and an alternative. If your product is an API or a service without an interface, choose the `backend-only` topology (a single backend component, no frontend). The test command it proposes for an empty repository comes from the stack catalog and runs from the project root (pointed at the `backend/` or `frontend/` folder when the components live in their own). For each document, you can provide your own, have the agent draft it (you review the complete draft before it is saved), or skip it.

Agent-written content remains a **draft**. Before finishing, the agent summarizes each document and asks you to confirm it. Only explicit confirmation makes it a project rule; otherwise it remains an assumption the agent can question.

<details>
<summary>Commands run by the agent behind the scenes</summary>

```bash
rapid setup next --json
rapid setup set stack python-fastapi
rapid setup set archetype mvp
rapid setup set test-command "python -m unittest discover"
rapid setup doc business --source drafted --file -
rapid setup doc brief --skip
rapid setup review --done
rapid setup finish
```

See the [`rapid setup` CLI reference](/cli#onboarding-rapid-setup).

</details>

### 4. Request your first feature

```text
/rapid-feature add a validate_username function to app.py
```

Without arguments, `/rapid-feature` suggests the first unchecked brief story (`- [ ] H001: ...`) and waits for your confirmation. The agent writes the spec, implements it task by task, and runs the tests.

### 5. Approve from your terminal

When finished, the agent stops and gives you the exact command. Run it in **another terminal**, outside the agent:

```bash
rapid approve gate.final-verification
```

Return to the agent and enter `/rapid-next`; the run closes with its verdict. Your first feature is implemented, tested, and approved by you. To reject, check progress, or cancel, see [When the agent stops](/getting-started/when-the-agent-stops).

:::note Without an agent: `rapid init`
`rapid init` runs interactive onboarding from the terminal. It is an alternative if you do not use an agent; anything left unresolved can be completed later with `/rapid-init`.
:::

## Next steps

- Try one lab for each mode: [Hands-on labs](/tutorials/).
- Adopt Rapid OS in an existing repository: [An existing project](/getting-started/existing-project).

## Advanced mode (v3 commands)

You do not need this for normal use. For the same workflow using v3 commands (for CI or auditing), follow the [manual walkthrough (Under the hood)](../tutorials/first-governed-project.md) and the [v3 governance loop](../governance-loop.md).

---
title: An Existing Project
description: Adopt Rapid OS in an existing code repository without risking business code.
---

# An Existing Project

Adopting Rapid OS in a repository already in production or active development is safe and non-invasive. Rapid OS is designed to **inspect and govern without modifying your business code**.

## With shortcuts

1. **Open your agent at the repository root** and enter:

   ```text
   /rapid-init
   ```

   The agent reads what it detects (language, framework, test directory) and proposes a starting point: stack, test command, and project documents. You confirm or change them. If the folder is not yet a Git repository, setup initializes one on branch `main`, without commits.

2. **Request the work:**

   ```text
   /rapid-bugfix the 10% discount returns a negative total
   ```

3. **Approve in your terminal** when prompted (the agent gives the exact command, such as `rapid approve gate.final-verification`), then enter `/rapid-next` to close. See [When the Agent Stops](./when-the-agent-stops.md) for other options.

Rapid OS does not touch your business code. It writes configuration to `.rapid-os/`, documents to `docs/`, and agent instructions (`CLAUDE.md`, `AGENTS.md`, and others). If it adds anything else (for example, a security workflow), it tells you when onboarding finishes. Each run starts with a test *baseline*: if your suite is already failing, the run cannot proceed until you fix it or cancel with `rapid abort`.

No shortcuts yet? Install them once with `rapid shortcuts install --global --harness claude` (replace `claude` with your agent), or run `rapid init --shortcuts` inside the repository. See the [shortcuts guide](../guides/shortcuts.md).

## Advanced mode

You do not need this to use Rapid OS. The v3 command path (`rapid doctor`, `rapid scan`, and others) is useful to inspect what Rapid OS detects in your repository, or for CI and auditing.

<details>
<summary>View the steps with v3 commands</summary>

### 1. Go to the repository root

Rapid OS CLI operates on the current working directory. Go to the project root (where `.git` or the main configuration files are):

```bash
cd /path/to/your/existing-project
```

### 2. Check the environment with `rapid doctor`

```bash
rapid doctor
```

If Rapid OS is not initialized in this project, it is expected for `.rapid-os/config.json` to be missing.

### 3. Run the read-only scanner

Before creating files, scan the project:

```bash
rapid scan
rapid scan --verbose  # show evidence for each detected fact
```

The scanner looks for standard ecosystem markers: language and packaging files (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`), frameworks, test tools, containers and orchestration files, and monorepo structure. It does **not** inspect secret files such as `.env` or private keys, and it does not modify source code.

### 4. Persist project intelligence

After reviewing detected facts, save the snapshot:

```bash
rapid scan --write
```

This creates only `.rapid-os/project.json` so later steps can reuse the information without rescanning the tree.

### 5. Initialize governance with `rapid init`

```bash
rapid init
```

`rapid init` also asks about the four project documents (`docs/PRODUCT_BRIEF.md`, `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md`, and `docs/ARCHITECTURE.md`); it preserves them if already resolved in a previous setup. A legacy `.rapid-os/standards/business.md` is offered as `legacy_source`; `rapid setup doc business --from-legacy` imports it as person-provided content without deleting the original. In an existing project, `rapid setup finish` writes only standards that changed.

If files such as `.cursorrules`, `CLAUDE.md`, `INSTRUCTIONS.md`, or `.rapid-os/config.json` already exist, Rapid OS does not silently delete them. Before updating content, it creates a `.bak` backup (for example, `.cursorrules.bak`) so you can inspect or merge your previous rules into `.rapid-os/standards/`.

### 6. Validate integrity

```bash
rapid validate
rapid validate --strict  # any warning produces a nonzero exit code
```

Common warnings include missing recommended `STD001–STD004` standards, minor `CONFIG001–CONFIG004` inconsistencies, and `RAPID600–RAPID604` differences in the Project Intelligence snapshot.

</details>

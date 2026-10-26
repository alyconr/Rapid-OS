---
id: index
slug: /
title: Rapid OS
description: Official documentation for Rapid OS v3, a Contract-Driven Engineering OS for governing the work of coding harnesses and AI agents.
---

# Rapid OS

<div className="hero--rapid">

**Rapid OS v3** is a **Contract-Driven Engineering OS** for teams that build software with coding harnesses and AI assistants.

Its goal is not to replace the agent that writes code. Its goal is to turn AI-assisted work into an **explicit, traceable, reproducible, and verifiable** process: understand the repository, define what must be built, compile the right context, set execution rules, declare capabilities, record evidence, and evaluate the result.

</div>

## What problem it solves

Coding agents can work fast, but they tend to suffer from three recurring problems:

- **Loss of context**: they don't always know the business rules, architecture, security requirements, or prior decisions.
- **Ambiguous instructions**: a prompt is not the same as a versioned, verifiable specification.
- **Lack of evidence**: an agent saying "done" does not prove that tests, reviews, or checks were run.

Rapid OS introduces deterministic contracts and records around that workflow.

<div className="rapid-grid">
  <div className="rapid-card">
    <h3>What exists</h3>
    <p><code>rapid scan</code> builds project intelligence with evidence and provenance.</p>
  </div>
  <div className="rapid-card">
    <h3>What must be built</h3>
    <p><code>rapid spec</code> manages specifications and immutable revisions.</p>
  </div>
  <div className="rapid-card">
    <h3>What the agent needs to know</h3>
    <p><code>rapid context</code> compiles relevant, prioritized context limited by a budget.</p>
  </div>
  <div className="rapid-card">
    <h3>Under which rules it can work</h3>
    <p><code>rapid policy</code> and <code>rapid run</code> set risk, workspace, gates, and tasks.</p>
  </div>
  <div className="rapid-card">
    <h3>What the harness can do</h3>
    <p><code>rapid harness</code> resolves declared capabilities against the run's contract.</p>
  </div>
  <div className="rapid-card">
    <h3>What actually happened</h3>
    <p><code>rapid evidence</code> and <code>rapid eval</code> record verifiable proof and produce a deterministic verdict.</p>
  </div>
</div>

## Get started in 3 steps

You don't need to learn commands: you work with **shortcuts** (`/rapid-…`) inside your coding agent, and in your terminal you only install and approve.

**1. Install Rapid OS** ([Installation](./installation/index.md)). At the end, the installer asks which agents to install the shortcuts for: type yours (for example `claude`). If you skipped it, run this once:

```bash
rapid shortcuts install --global --harness claude
```

**2. Describe your project in the agent.** It proposes the stack, the test command, and the documents; you decide:

```text
/rapid-init a Python API to validate usernames
```

**3. Ask for the work:**

```text
/rapid-feature add CSV export to the monthly report
```

When it finishes, the agent stops and gives you the command to approve in **your** terminal (for example `rapid approve gate.final-verification`). Then type `/rapid-next` to close out.

| You want to… | Type in your agent |
| :--- | :--- |
| Set up the project | `/rapid-init <description>` |
| A new feature | `/rapid-feature <goal>` |
| Fix a bug | `/rapid-bugfix <what fails>` |
| Refactor without breaking tests | `/rapid-refactor <scope>` |
| Harden security | `/rapid-hardening <area>` |
| Research an option | `/rapid-research <question>` |
| See where things stand or continue | `/rapid-status` · `/rapid-next` |

In Codex they are typed with `$` (`$rapid-init`). In VS Code, and if you prefer to version the shortcuts with the repository, install them in the project with `rapid init --shortcuts`. Per-agent details are in the [shortcuts guide](./guides/shortcuts.md).

## Advanced mode: the v3 governance loop

The v3 commands (`rapid scan`, `rapid spec`, `rapid run`, `rapid evidence`, `rapid eval`…) remain available for CI, debugging, and auditing. The v3 governance loop follows eight steps:

```text
1. scan
2. spec
3. context
4. policy / run
5. harness
6. external execution + run update
7. evidence
8. eval + validate
```

Rapid OS **does not autonomously run an LLM**, does not approve human gates, only creates a worktree with `rapid start --worktree`, runs only the configured `test_command` or the argv of `rapid check` (the plumbing runs nothing), and does not use an LLM as a judge. The external coding harness does the work; Rapid OS governs and verifies the artifacts around that work.

## Start here

- [What Rapid OS is and who it is for](./concepts/what-is-rapid-os.md)
- [Why Rapid OS and the problems it solves](./concepts/why-rapid-os.md)
- [Requirements and installation](./installation/index.md)
- [Shortcuts per harness (`/rapid-<mode>`)](./guides/shortcuts.md)
- [Your first project (Quickstart)](./getting-started/first-project.md)
- [A project that already exists](./getting-started/existing-project.md)
- [When the agent stops](./getting-started/when-the-agent-stops.md)
- [Engineering modes](./guides/modes/index.md)
- [Governance and Evidence Cookbooks](./cookbooks/policies-and-contracts.md)
- [RAPIDxxx Diagnostics Catalog](./troubleshooting/diagnostics.md)
- [CI/CD integration](./guides/ci-cd-integration.md)
- [v3 governance loop](./governance-loop.md)
- [Capabilities and permissions](./guides/permissions-capabilities.md)
- [File structure](./guides/project-layout.md)
- [Full CLI reference](./cli.md)
- [v3 technical architecture](./architecture/rapid-os-v3.md)
- [Orchestration architecture (porcelain over plumbing)](./architecture/orchestration.md)

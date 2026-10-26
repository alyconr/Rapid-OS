---
id: index
slug: /
title: Rapid OS
description: "Official Rapid OS v3 documentation: a contract-driven engineering OS for governing work by coding harnesses and AI agents."
---

# Rapid OS

<div className="hero--rapid">

**Rapid OS v3** is a **Contract-Driven Engineering OS** for teams building software with coding harnesses and AI assistants.

It does not replace the agent that writes code. It turns AI-assisted work into an **explicit, traceable, reproducible, and verifiable** process: understand the repository, define what to build, compile the right context, set execution rules, declare capabilities, record evidence, and evaluate the result.

</div>

## The problem it solves

Coding agents can work quickly, but commonly face three problems:

- **Context loss**: they may not know business rules, architecture, security requirements, or prior decisions.
- **Ambiguous instructions**: a prompt is not a versioned, verifiable specification.
- **Lack of evidence**: an agent saying “done” does not prove that tests, reviews, or controls ran.

Rapid OS adds deterministic contracts and records around that workflow.

## Start in three steps

Work with **shortcuts** (`/rapid-…`) in your coding agent; use the terminal to install and approve actions.

**1. Install Rapid OS.** Follow the [installation guide](/installation/).

**2. Describe your project to the agent:**

```text
/rapid-init a Python API for validating usernames
```

**3. Ask for work:**

```text
/rapid-feature add CSV export to the monthly report
```

When work is done, the agent stops and gives you the command to approve in **your** terminal (for example, `rapid approve gate.final-verification`). Then use `/rapid-next` to close the task.

| Goal | Shortcut |
| --- | --- |
| Configure a project | `/rapid-init <description>` |
| Build a feature | `/rapid-feature <goal>` |
| Fix a bug | `/rapid-bugfix <problem>` |
| Refactor safely | `/rapid-refactor <scope>` |
| Improve security | `/rapid-hardening <area>` |
| Investigate an option | `/rapid-research <question>` |
| Check status or continue | `/rapid-status` · `/rapid-next` |

## The governance loop

The v3 workflow follows eight steps: scan, spec, context, policy/run, harness, external execution and run update, evidence, then evaluation and validation. The external coding harness performs the work; Rapid OS governs and verifies the surrounding artifacts. Rapid OS does not autonomously run an LLM, approve human gates, or use an LLM as a judge.

## Explore the documentation

- [What is Rapid OS?](/concepts/what-is-rapid-os)
- [Installation](/installation/)
- [Shortcuts guide](/guides/shortcuts)
- [Your first project](/getting-started/first-project)
- [Engineering modes](/guides/modes/)
- [Governance loop](/governance-loop)
- [CLI reference](/cli)

The English documentation includes the full set of pages. Switch to Español from the language selector to read the original Spanish versions.

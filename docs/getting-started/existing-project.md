---
title: An Existing Project
description: How to adopt Rapid OS in repositories with preexisting code without risk to the business code.
---

# An Existing Project

Adopting Rapid OS in a repository that is already in production or active development is a safe, non-invasive process. Rapid OS is designed to **analyze and govern without modifying your business code**.

## With shortcuts

1. **Open your agent at the repository root** and type:

   ```text
   /rapid-init
   ```

   The agent reads what it detects in your repository (language, framework, tests folder) and proposes it as a starting point: stack, test command, and documents. You confirm or change it. If the folder is not yet a git repository, it creates one on the `main` branch, with no commits.

2. **Ask for the work:**

   ```text
   /rapid-bugfix the 10% discount returns a negative total
   ```

3. **Approve in your terminal** when the agent asks you to (it gives you the exact command, for example `rapid approve gate.final-verification`) and type `/rapid-next` to close. More options in [When the agent stops](./when-the-agent-stops.md).

Rapid OS does not touch your business code: it writes its configuration to `.rapid-os/`, the documents to `docs/`, and your agent's instructions (`CLAUDE.md`, `AGENTS.md`…); if it adds anything else (for example a security workflow), it tells you when it closes the onboarding. The first step of every run is a *baseline* of your tests: if your suite is already red, the run does not advance until you fix it (or abandon the run with `rapid abort`).

Don't have the shortcuts yet? One time only: `rapid shortcuts install --global --harness claude` (replace `claude` with your agent), or inside the repository `rapid init --shortcuts`. Details in the [shortcuts guide](../guides/shortcuts.md).

## Advanced mode

You don't need it to use Rapid OS. It is the path with v3 commands (`rapid doctor`, `rapid scan`…): useful to see what Rapid OS discovers in your repository, for CI, and for auditing.

<details>
<summary>See the steps with v3 commands</summary>

---

## 1. Locate the repository root

The Rapid OS CLI always operates on the current working directory. Move to the repository root (where the `.git` folder or the project's main configuration files live):

```bash
cd /path/to/your-existing-project
```

---

## 2. Pre-check with `rapid doctor`

Run an initial check to verify the state of the environment in that directory:

```bash
rapid doctor
```

If the project does not have Rapid OS yet, it will report that `.rapid-os/config.json` does not exist. This is expected.

---

## 3. Read-only scan (`rapid scan`)

Before creating any file, run the project scanner:

```bash
rapid scan
```

Or to see the detailed evidence for each detected fact:

```bash
rapid scan --verbose
```

### What does the scanner analyze?
Rapid OS looks for standard markers of the software ecosystem:
- **Languages and packagers:** `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`, etc.
- **Frameworks:** Django, FastAPI, Flask, React, Next.js, Vue, Spring, etc.
- **Testing:** `pytest`, `unittest`, `jest`, `vitest`, `mocha`, etc.
- **Containers and orchestration:** `Dockerfile`, `docker-compose.yml`.
- **Structure:** Monorepo detection (`pnpm-workspace.yaml`, `lerna.json`, app folders).

### What does the scanner NOT read (secrets safety)?
- **It does not analyze secrets files:** It automatically ignores `.env`, files with private keys (`.pem`, `.key`), tokens, and ignored directories such as `.git`, `node_modules`, `venv`, `__pycache__`, or `.docusaurus`.
- **It does not modify source code:** `rapid scan` is **100% read-only**.

---

## 4. Persist the project intelligence

Once you have reviewed the discovered facts, persist the intelligence snapshot:

```bash
rapid scan --write
```

This creates only `.rapid-os/project.json`, letting later stages reuse the information without walking the file tree again.

---

## 5. Initialize governance with `rapid init`

To establish the project standards and the context files for coding agents, run:

```bash
rapid init
```

### Project documentation and prior business rules

`rapid init` also asks about the four project documents (`docs/PRODUCT_BRIEF.md`, `docs/BUSINESS_RULES.md`, `docs/DATA_MODEL.md`, `docs/ARCHITECTURE.md`); if you already resolved them in a previous run, it keeps them. If your project came from an earlier version with `.rapid-os/standards/business.md`, `rapid setup next` offers it as `legacy_source` and `rapid setup doc business --from-legacy` imports it as a person-supplied document, without deleting the original. For a project that already exists, `rapid setup finish` writes only the standards that changed: it does not overwrite those that already express your decision.

### Protection of existing files with `.bak`
If your project already has files such as `.cursorrules`, `CLAUDE.md`, `INSTRUCTIONS.md`, or `.rapid-os/config.json`:
- Rapid OS **does not delete them without warning**.
- It automatically creates a backup with a `.bak` extension (for example, `.cursorrules.bak`) before updating the content.
- You can inspect the difference or merge your previous rules into the new standards files in `.rapid-os/standards/`.

---

## 6. Integrity validation (`rapid validate`)

Verify that the project's configuration and standards are consistent:

```bash
rapid validate
```

To enable strict checking, where any warning produces a non-zero exit code:

```bash
rapid validate --strict
```

### How to interpret common warnings
- `STD001–STD004`: A recommended standards file is missing from `.rapid-os/standards/` (e.g. `tech-stack.md` or `topology.md`).
- `CONFIG001–CONFIG004`: Minor inconsistencies in the project configuration.
- `RAPID600–RAPID604`: Discrepancies in the Project Intelligence snapshot.

Once `rapid validate` returns code `0`, your repository has a verified governance baseline and is ready to receive specifications and context compilations.

</details>

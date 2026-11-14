---
title: Security Baseline
description: Security rules for every project, the standards behind them, MVP and Corporate levels, CI scans created by Rapid OS, and AI security.
---

# Security Baseline

Every project starts with concrete security rules, each traceable to a standard, and CI scans that run from the first PR. MVP and Corporate share the baseline but use different levels. Rules live in `.rapid-os/standards/security.md`, are provided to the agent as a standard, and are used by `rapid start hardening` to classify findings.

## Which standards cover which rules

| Standard | Coverage in `security.md` |
|---|---|
| [OWASP ASVS 5.0.0](https://github.com/OWASP/ASVS) | Project verification level: L1 (MVP) or L2 (Corporate). |
| [OWASP Top 10:2025](https://top10.owasp.org/2025) | One to three rules per category, from A01 Broken Access Control to A10 Mishandling of Exceptional Conditions. |
| [OWASP API Security Top 10:2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) | One rule per API1–API10 item, for API stacks (backend catalog stacks and `nextjs`, `nuxt`, and `sveltekit`). |
| [NIST SSDF SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final) | PO, PS, PW, and RV families applied to Rapid OS: a brief threat model for specs touching authentication, payments, or personal data; human review at the final gate; and vulnerability handling by CVSS severity. |
| [SLSA 1.2](https://slsa.dev/spec/v1.2/) | Versioned lockfile, pinned dependencies, and CI actions pinned by full SHA. Corporate adds Build L2 and Source L2. |
| [CWE](https://cwe.mitre.org/) and [CVSS v4.0](https://www.first.org/cvss/v4-0/specification-document) | Report each finding with its CWE and `CVSS:4.0/...` vector. |
| [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/) and [Top 10 for Agentic Applications for 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) | AI section when the product uses models or agents. |

Each rule cites its supporting standard in brackets. Category names match the official source, and source URLs are included in a comment at the end of `security.md`.

## Levels

| | MVP | Corporate |
|---|---|---|
| OWASP ASVS 5.0.0 | Level L1 | Level L2 |
| SLSA 1.2 | Pinned lockfile, dependencies, and actions | Also Build L2 (signed artifact provenance) and Source L2 |
| CI | Secrets, static analysis, dependencies | Also SBOM and provenance |

MVP speed never lowers the baseline: MVP `coding-rules.md` says "Speed never lowers the security baseline or modular architecture" and no longer permits loose typing with `any`.

SLSA 1.2 Source L2 covers *history and provenance*: `main` history is continuous and immutable, and the code platform emits provenance for each revision. Requiring all changes to go through reviewed PRs is an additional project practice, not an L2 requirement. Complete this part when configuring the repository.

## Projects on a BaaS provider

With `supabase` or `firebase` as the `baas` stack, `security.md` adds a section for the provider, with the same bracketed citations as the rest: Supabase (RLS on every table of an exposed schema, revoked default privileges, policies tested by `supabase test db`, the publishable key public and the secret key never in the client) or Firebase (deny-by-default Firestore and Storage rules tested in the emulator with `@firebase/rules-unit-testing`, App Check, the web `apiKey` as an identifier and not a secret, service-account credentials only on the server). The API Security Top 10 applies, and the CI workflow adds the job that runs those tests.

A document database, Firestore or the service `database:mongodb`, adds a section on NoSQL injection [OWASP A05:2025, CWE-943, OWASP ASVS V1]: never pass an object, an operator (`$where`, `$gt`, `$ne`...) or a field name taken from the input to a query, check the type of each value first, and validate the shape of each document when it is written. With MongoDB, a section requires authentication in every environment (also locally) and the port on `127.0.0.1` only, as the `compose.yaml` Rapid OS writes. Changing the provider or the database engine rewrites a `security.md` that Rapid OS wrote.

## Does the product use AI?

After archetype selection, onboarding asks `rapid setup set ai yes|no`: *Will the product use AI models or agents (for example, an assistant that replies over WhatsApp)?* With `yes`, `security.md` includes **AI Security** rules: treat model output as untrusted input; defend against prompt injection; allow-list tools with least privilege; require human approval for irreversible actions (payments, deletions, customer messages); keep secrets out of prompts and memory; and set cost and iteration limits. Each rule cites the relevant OWASP LLM 2025 and OWASP Agentic 2026 item.

Legacy IDs `python-ai` and `nodejs-ai` automatically set `ai: yes`. A `setup.json` without `ai` is treated as undecided until onboarding finishes, then as `no` in a completed project.

## Rapid OS creates the security CI workflow

When onboarding finishes for an **empty repository**, `rapid setup finish` writes a language-specific workflow `.github/workflows/rapid-security-<language>.yml` from `templates/ci/<language>-security.yml`. Each appears in Actions under the same name as its file, `rapid-security-<language>` (for example `rapid-security-python` and `rapid-security-typescript`). A project that already has `rapid-security.yml` is left unchanged and receives no additional workflow. Workflows run on pull requests and pushes to `main`:

- **Secrets:** gitleaks, downloaded with a pinned checksum.
- **Static analysis:** semgrep with `p/owasp-top-ten` rules; Python also adds bandit.
- **Dependencies:** the audit of the language's package manager, in the folder of each component (below).
- **Corporate:** SBOM (`anchore/sbom-action`) and signed provenance (`actions/attest-build-provenance`).

Actions are pinned by full commit SHA, with the version in a comment. Rapid OS never overwrites an existing workflow and does not write this workflow into a repository that already has code. `setup finish` reports the new file (also in `added_files` with `--json`) and asks you to review it before the first commit. Draft review announces it earlier in `planned_files`.

### What the dependencies job audits, per component

The manifest and the lockfile live in the folder of each component. With topology `fullstack-separated` (a backend and a frontend with different stacks) that is `backend/` and `frontend/`; any other topology keeps the whole project in the root. The dependencies job runs once per folder of its language (a matrix over `dir`, named `Dependencias (...) · <folder>`), with that folder as the working directory:

| Language | What it reads in the folder | Command |
| --- | --- | --- |
| Python | `uv.lock` | `uv export --frozen --format requirements.txt --no-emit-project -o <file>`, then `pip-audit --disable-pip -r <file>` (the exported requirements are pinned with hashes, so pip-audit does not resolve again). `uv audit` exists but uv marks it experimental. |
| Python | `requirements.txt` | `pip-audit -r requirements.txt` |
| Python | `pyproject.toml` without a lock | `pip install .`, then `pip-audit --skip-editable` |
| TypeScript | `pnpm-lock.yaml`, `package-lock.json` or `yarn.lock` | `pnpm audit --audit-level high`, `npm audit --audit-level=high` or `yarn npm audit --all --recursive --severity high`, after installing with the lockfile. The pnpm version comes from `packageManager` in that folder's `package.json` (pnpm 10 without it). |
| Go, Rust, Ruby, .NET, PHP | `go.mod`, `Cargo.lock`, `Gemfile.lock`, a `.sln`/`.slnx`/`.csproj`, `composer.lock` | `govulncheck`, `cargo audit`, `bundle-audit`, `dotnet package list --vulnerable`, `composer audit` |

Java and Kotlin use GitHub's dependency review on pull requests, which covers the whole repository.

What happens in each folder:

- **The folder has code and its manifest or lockfile:** the audit runs and fails on a vulnerability.
- **The folder has code but no manifest or lockfile:** the job fails and says what is missing and where, for example `frontend tiene package.json pero ningún lockfile (pnpm-lock.yaml, package-lock.json o yarn.lock)`.
- **The folder does not exist or has no code of that language yet** (a repository just created): the job passes and writes a warning (`::warning::`) that also appears in the job summary: `Nada que auditar: backend no existe o no tiene código Python todavía`. A green job with that warning audited nothing.

Each workflow starts with a line `# rapid-os-ci: <language> sha256=<digest>`: the SHA-256 of the rest of the file as Rapid OS wrote it. It tells a later version whether the workflow was edited.

### Bringing the workflows of an existing project up to date

`rapid doctor` compares each `rapid-security-<language>.yml` with what the current version writes for the project's stacks and topology (`.rapid-os/setup.json`):

- **Written by an earlier version and not edited** (its stamp still matches, or, for workflows of 3.2.0rc1 to rc3, which have no stamp, its content is one of the workflows those versions wrote): warning `RAPID1443`.
- **Edited by the person:** info `RAPID1443`.

```bash
rapid setup ci                # state of each workflow: current, outdated, edited or missing
rapid setup ci --regenerate   # write what this version generates
```

`--regenerate` replaces a workflow nobody edited (the previous copy goes to `.rapid-os/backups/`) and writes a missing one. It never overwrites an edited workflow: the new one is written beside it as `rapid-security-<language>.yml.new` (GitHub does not run it). Compare the two, carry your changes to the new one and rename it to the workflow's name. `rapid setup ci` reads only; `--json` gives `workflows[]` with `file`, `language`, `status` and, with `--regenerate`, `action` (`unchanged`, `replaced`, `written`, `new`) and `written`.

## Existing projects

Only a person's decision changes `security.md`. To refresh an older project's generated baseline:

```bash
rapid setup set archetype mvp --refresh
```

This regenerates `security.md` and `coding-rules.md` from the current archetype templates and saves previous versions in `.rapid-os/backups/` (the five most recent per file). `rapid doctor` suggests this with warning `RAPID1421` when `security.md` does not mention ASVS. A manually written security file is never rewritten without `--refresh`.

## Hardening mode

The `rapid start hardening` spec stores a structured `findings[]` list (`id`, `title`, `cwe`, `cvss_v4_vector`, `severity`, `standard_ref`) in each revision. Start validates each CWE and complete CVSS v4.0 base vector, requires the severity to be the rating of the vector's CVSS v4.0 base score, and requires `standard_ref` to match, ignoring case, one full citation in `security.md` (one comma-separated item inside the square brackets, not a substring). Each finding also needs an acceptance criterion naming its id or CWE and task evidence.

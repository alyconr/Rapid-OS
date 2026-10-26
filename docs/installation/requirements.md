---
title: System Requirements
description: Software prerequisites, Python versions, and optional dependencies for Rapid OS.
---

# System Requirements

Rapid OS is designed to keep its technical overhead low: the governance core has no mandatory third-party runtime dependencies and runs on the Python standard library.

## Required prerequisites

To run the Rapid OS CLI on any operating system, you need:

| Requirement | Minimum version | Notes |
| :--- | :--- | :--- |
| **Python** | `3.10` or later | Extensively tested in CI with Python `3.10`, `3.11`, `3.12`, and `3.13`. |
| **Git** | `2.20` or later | Used for version control operations and repository inspection. |
| **Terminal** | Standard console | PowerShell 5.1+ or 7+ on Windows; Bash or Zsh on Linux/macOS. |

### Check the prerequisites

Before installing, check your tools in a terminal:

```bash
python --version   # or python3 --version
git --version
```

Both commands should return successfully with compatible versions.

## Optional dependencies

:::note Not required for the main CLI
The v3 governance loop (`scan`, `spec`, `context`, `policy`, `run`, `harness`, `evidence`, `eval`, `validate`) **does not** require Node.js or npm.
:::

Additional tools are needed only in these two cases:

1. **Remote skill management (`rapid skill add`):** If you use the legacy feature for adding third-party skills through npx, `node` (Node.js 18+) and `npx` must be available on your PATH.
2. **Documentation site development and build (Docusaurus):** To clone and build the documentation site locally from `website/`, you need Node.js 20+ and `npm`.

## Connectivity and permissions

- **Internet access:** Needed only to initially download the repository or package. The rest of the governance loop runs **fully offline**, without calling cloud APIs.
- **User permissions:** Administrator (`root` or `Administrator`) privileges are not required to install or use Rapid OS. It installs in the user directory (`$HOME/.rapid-os`).

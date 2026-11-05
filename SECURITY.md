# Security Policy

## Supported versions

| Version | Supported |
| :-- | :-- |
| 3.2.x (including its release candidates) | Yes |
| Earlier versions | No: please upgrade first and check whether the problem is still there |

## Reporting a vulnerability

Report it privately through GitHub: open the [Security Advisories page](https://github.com/alyconr/Rapid-OS/security/advisories/new) of the repository ("Report a vulnerability"). Please do not open a public issue, pull request or discussion for a vulnerability.

A useful report includes the output of `rapid --version`, your operating system and shell, the harness involved, the steps to reproduce and what an attacker gains.

## What to expect

Rapid OS is maintained by a small team, so these times are goals, not contractual deadlines:

| Step | Goal |
| :-- | :-- |
| Acknowledge the report | Within 5 business days |
| First assessment (accepted, needs more information, or out of scope) | Within 15 business days |
| Fix or mitigation for an accepted report | Depends on severity; we keep you informed in the advisory at least every 30 days |

We coordinate the publication date with you and credit you in the advisory unless you prefer otherwise.

## In scope

Bugs where Rapid OS breaks a promise it makes, for example:

- `rapid evidence add` accepting a producer or a review field reserved to Rapid OS.
- A run reaching `PASS` without the real test run or the human approval its contract requires, using only Rapid OS commands.
- `rapid approve` working from a Claude Code agent session, where it documents the refusal.
- A malicious repository making Rapid OS run a program just by being read.
- Rapid OS writing outside the project when it says it does not, or path traversal through its inputs.

## Out of scope

**The honest limit: an agent with a shell can write files under `.rapid-os/` directly.** Rapid OS runs on the same machine and with the same permissions as the agent, and its records are not signed, so it cannot stop that on its own. In Claude Code, the `PreToolUse` hook blocks those writes on a best-effort basis (a command built at runtime can get past its analysis); the other harnesses have no equivalent. Closing this fully needs a channel outside the agent's reach. The [README](README.md#harness-guarantees) lists what is and is not guaranteed for each harness.

Also out of scope:

- Rapid OS is not an operating-system sandbox: a harness capability is a declaration, not an enforced restriction.
- The commands you ask it to run: `test_command` and the argv of `rapid check` run with your permissions.
- The behavior or the security of the harnesses, the models and the MCP servers themselves.
- Vulnerabilities in the code an agent writes. A `PASS` verdict certifies that the contract and the recorded evidence were satisfied, not that the software is free of defects.
- Versions that are no longer supported.

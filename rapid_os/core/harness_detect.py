from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from rapid_os.domain.harnesses import validate_harness_id

FALLBACK_HARNESS_ID = "cursor"
WARNING_RAPID1300 = (
    "WARNING [RAPID1300]: No harness explicitly provided or detected from environment/config. "
    "Falling back to 'cursor'. Set RAPID_HARNESS=<id>, use --harness <id>, or configure "
    "'default_harness' in .rapid-os/config.json."
)


@dataclass(frozen=True)
class HarnessDetection:
    """Result of harness resolution with provenance and diagnostic warning if fallback."""

    harness_id: str
    source: str
    warning: str | None = None


def detect_harness(
    explicit: str | None,
    env: Mapping[str, str],
    config: Mapping,
) -> HarnessDetection:
    """Detect the target coding harness using strict precedence:

    1. Explicit CLI argument (--harness <id>)
    2. Environment variable RAPID_HARNESS
    3. Official harness environment markers:
       - CLAUDE_CODE_CHILD_SESSION == "1" -> 'claude' (Claude Code official documentation:
         exported to Bash tool commands and hooks; see https://code.claude.com/docs/en/env-vars)
    4. Project config 'default_harness' from .rapid-os/config.json
    4b. Project config 'tools' naming exactly one supported harness (source 'config_tools')
    5. Fallback 'cursor' with WARNING RAPID1300 (it lists the harnesses of 'tools', if any)

    Codex has no marker here: its documentation (https://developers.openai.com/codex/environment-variables)
    lists only variables for Codex itself (CODEX_HOME, CODEX_API_KEY); CODEX_THREAD_ID, which it adds
    to the commands it runs, appears only in a GitHub discussion
    (https://github.com/openai/codex/discussions/26901), so it is not relied on.
    """
    # 1. Explicit flag
    if explicit is not None and str(explicit).strip():
        resolved_id = validate_harness_id(str(explicit).strip())
        return HarnessDetection(harness_id=resolved_id, source="flag")

    # 2. RAPID_HARNESS env var
    env_harness = env.get("RAPID_HARNESS")
    if env_harness is not None and str(env_harness).strip():
        resolved_id = validate_harness_id(str(env_harness).strip())
        return HarnessDetection(harness_id=resolved_id, source="env")

    # 3. Environment markers
    # Marker: Claude Code (CLAUDE_CODE_CHILD_SESSION == "1")
    # Reference: https://code.claude.com/docs/en/env-vars
    # Claude Code exports CLAUDE_CODE_CHILD_SESSION="1" to Bash tool commands and hooks.
    if env.get("CLAUDE_CODE_CHILD_SESSION") == "1":
        return HarnessDetection(
            harness_id=validate_harness_id("claude"),
            source="marker",
        )

    # 4. Config default_harness
    default_harness = config.get("default_harness")
    if default_harness is not None and str(default_harness).strip():
        resolved_id = validate_harness_id(str(default_harness).strip())
        return HarnessDetection(harness_id=resolved_id, source="config")

    # 4b. A project that lists one supported harness in 'tools' works with that one.
    listed = _supported_tools(config.get("tools"))
    if len(listed) == 1:
        return HarnessDetection(harness_id=listed[0], source="config_tools")

    # 5. Fallback to cursor with warning
    warning = WARNING_RAPID1300
    if listed:
        warning += (
            f" The project's 'tools' lists {', '.join(listed)}: "
            "pick the one you are working in."
        )
    return HarnessDetection(
        harness_id=FALLBACK_HARNESS_ID,
        source="fallback",
        warning=warning,
    )


def _supported_tools(tools: object) -> list[str]:
    """The supported harness ids named by config 'tools', in order and without repeats."""
    if not isinstance(tools, (list, tuple)):
        return []
    from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY

    supported = DEFAULT_AGENT_REGISTRY.ids()
    listed: list[str] = []
    for tool in tools:
        if isinstance(tool, str) and tool in supported and tool not in listed:
            listed.append(tool)
    return listed

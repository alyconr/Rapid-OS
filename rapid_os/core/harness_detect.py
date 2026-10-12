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
       - CLAUDE_PROJECT_DIR -> 'claude' (Claude Code official documentation: set to project root)
         URL: https://docs.anthropic.com/en/docs/agents-and-tools/claude-code
       - CURSOR_AGENT -> 'cursor' (Cursor official documentation: set by Cursor in agent/terminal sessions)
         URL: https://docs.cursor.com/
       - TERM_PROGRAM == 'vscode' -> 'vscode' (VS Code official documentation: integrated terminal identity)
         URL: https://code.visualstudio.com/docs/terminal/basics
       - CODEX_THREAD_ID -> 'codex' (OpenAI Codex official documentation: thread execution session id)
         URL: https://github.com/openai/codex
    4. Project config 'default_harness' from .rapid-os/config.json
    5. Fallback 'cursor' with WARNING RAPID1300
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
    # Marker 1: Claude Code (CLAUDE_PROJECT_DIR)
    # Ref: Claude Code docs define CLAUDE_PROJECT_DIR as the active project directory in tool executions.
    if env.get("CLAUDE_PROJECT_DIR"):
        return HarnessDetection(
            harness_id=validate_harness_id("claude"),
            source="marker",
        )

    # Marker 2: Cursor (CURSOR_AGENT)
    # Ref: Cursor docs define CURSOR_AGENT in terminal/shell sessions executed by Cursor.
    if env.get("CURSOR_AGENT"):
        return HarnessDetection(
            harness_id=validate_harness_id("cursor"),
            source="marker",
        )

    # Marker 3: VS Code (TERM_PROGRAM == 'vscode')
    # Ref: VS Code sets TERM_PROGRAM=vscode in its integrated terminal.
    if env.get("TERM_PROGRAM") == "vscode":
        return HarnessDetection(
            harness_id=validate_harness_id("vscode"),
            source="marker",
        )

    # Marker 4: Codex (CODEX_THREAD_ID)
    # Ref: OpenAI Codex injects CODEX_THREAD_ID during active thread execution.
    if env.get("CODEX_THREAD_ID"):
        return HarnessDetection(
            harness_id=validate_harness_id("codex"),
            source="marker",
        )

    # 4. Config default_harness
    default_harness = config.get("default_harness")
    if default_harness is not None and str(default_harness).strip():
        resolved_id = validate_harness_id(str(default_harness).strip())
        return HarnessDetection(harness_id=resolved_id, source="config")

    # 5. Fallback to cursor with warning
    return HarnessDetection(
        harness_id=FALLBACK_HARNESS_ID,
        source="fallback",
        warning=WARNING_RAPID1300,
    )

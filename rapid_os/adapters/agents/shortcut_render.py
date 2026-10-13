"""Shared rendering helpers for harness shortcut files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from rapid_os.domain.shortcuts import GENERATED_MARKER, ShortcutTemplate


def yaml_string(value: str) -> str:
    """Quote a scalar so values such as `[objetivo]` stay plain strings in YAML."""
    return json.dumps(value, ensure_ascii=False)


def context_step(template: ShortcutTemplate, *, inline: bool) -> str:
    """Return the harness-specific "read the current state first" block.

    Only Claude Code runs `!`command`` before the prompt is sent; every other harness
    gets the same instruction as plain text.
    """
    command = template.context_command
    if command is None:
        return ""
    if inline:
        return (
            f"## Estado actual\n\n!`{command}`\n\n"
            f"La salida anterior es el resultado de `{command}`."
        )
    return f"Antes de nada, ejecuta `{command}` y lee su salida."


def document(frontmatter: Sequence[tuple[str, str]], body: str) -> str:
    """Compose frontmatter, the generated marker (right after it) and the body."""
    lines = ["---"]
    lines.extend(f"{key}: {value}" for key, value in frontmatter)
    lines.append("---")
    return "\n".join(lines) + f"\n{GENERATED_MARKER}\n\n{body}"


def skill_frontmatter(template: ShortcutTemplate) -> list[tuple[str, str]]:
    return [
        ("name", template.name),
        ("description", yaml_string(template.description)),
    ]


def simple_skill_outputs(
    shortcuts: Iterable[ShortcutTemplate],
    root_parts: tuple[str, ...],
    *,
    with_disable_model_invocation: bool,
) -> Mapping[Path, str]:
    """Render `<root>/<name>/SKILL.md` documents (Codex, Antigravity, Cursor)."""
    outputs = {}
    for template in shortcuts:
        frontmatter = skill_frontmatter(template)
        if with_disable_model_invocation and template.disable_model_invocation:
            frontmatter.append(("disable-model-invocation", "true"))
        body = template.render_body(context_step(template, inline=False))
        outputs[Path(*root_parts, template.name, "SKILL.md")] = document(frontmatter, body)
    return outputs

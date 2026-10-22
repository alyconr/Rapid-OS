"""Security baseline of a project: which parts apply and how the template is rendered. Pure: no I/O.

The baseline (`templates/security/baseline.md`) and the CI workflow (`templates/ci/*.yml`) have
conditional regions, marked on their own lines with `<!-- if NAME -->` / `<!-- endif -->` in
Markdown and `# if NAME` / `# endif` in YAML. A region is kept when every enclosing condition holds.
"""

from __future__ import annotations

import re
from typing import Collection, Mapping

# Stacks whose product is built around models or agents: no question, the AI section applies.
AI_STACKS = frozenset({"python-ai", "nodejs-ai"})
# Stacks that expose an API: the API Security Top 10 applies.
API_STACKS = frozenset({"python-api", "python-ai", "nodejs-ai", "web-modern"})
# OWASP ASVS 5.0.0 level each archetype verifies.
ASVS_LEVELS: Mapping[str, str] = {"mvp": "L1", "corporate": "L2"}
# The language of the CI workflow for each stack (`generic` depends on what the scanner finds).
CI_LANGUAGE_BY_STACK: Mapping[str, str] = {
    "python-api": "python",
    "python-ai": "python",
    "nodejs-ai": "typescript",
    "web-modern": "typescript",
    "docs-modern": "typescript",
    "frontend-creative": "typescript",
}
CI_WORKFLOW_PATH = ".github/workflows/rapid-security.yml"
CI_ADDED_NOTE = "Rapid OS añadió este workflow; revísalo antes del primer commit"
CI_PLANNED_NOTE = "Rapid OS añadirá este workflow al cerrar el onboarding; revísalo antes del primer commit"

AI_SECTION_HEADING = "## Seguridad de IA"
ASVS_LEVEL_TOKEN = "{ASVS_LEVEL}"

_MARKER = re.compile(r"^\s*(?:<!--\s*(?P<md>if\s+\w+|endif)\s*-->|#\s*(?P<yml>if\s+\w+|endif))\s*$")


def is_ai_stack(stack_id: str | None) -> bool:
    return stack_id in AI_STACKS


def has_api(stack_id: str | None) -> bool:
    return stack_id in API_STACKS


def effective_ai(stack_id: str | None, decision: bool | None) -> bool:
    """AI stacks are always `yes`; the others follow the person's answer (`None` reads as no)."""
    return is_ai_stack(stack_id) or bool(decision)


def render_conditionals(text: str, active: Collection[str]) -> str:
    """Keep the regions whose condition is in `active`; drop the marker lines."""
    kept: list[str] = []
    stack: list[bool] = []
    for line in text.splitlines(keepends=True):
        marker = _MARKER.match(line.rstrip("\r\n"))
        if marker is not None:
            directive = (marker.group("md") or marker.group("yml")).split()
            if directive[0] == "if":
                stack.append(directive[1] in active)
            elif stack:
                stack.pop()
            continue
        if all(stack):
            kept.append(line)
    return "".join(kept)


def render_security_standard(
    template: str, *, archetype: str, stack_id: str | None, ai: bool | None
) -> str:
    """`standards/security.md`: the baseline at the archetype's level, with the API and AI parts
    only where they apply."""
    active = {archetype}
    if has_api(stack_id):
        active.add("api")
    if effective_ai(stack_id, ai):
        active.add("ai")
    body = render_conditionals(template, active)
    return body.replace(ASVS_LEVEL_TOKEN, ASVS_LEVELS.get(archetype, "L1"))


def render_ci_workflow(template: str, *, archetype: str) -> str:
    """The CI workflow: Corporate adds the SBOM and the provenance."""
    return render_conditionals(template, {archetype})


def ci_language(stack_id: str | None, scanned_languages: Collection[str] = ()) -> str | None:
    """`python` or `typescript` for the CI template, or None when there is no template."""
    if stack_id in CI_LANGUAGE_BY_STACK:
        return CI_LANGUAGE_BY_STACK[stack_id]
    if stack_id == "generic":
        lowered = {value.lower() for value in scanned_languages}
        if "python" in lowered:
            return "python"
        if lowered & {"typescript", "javascript"}:
            return "typescript"
    return None


def security_mentions_asvs(text: str | None) -> bool:
    return bool(text) and "ASVS" in text


def security_has_ai_section(text: str | None) -> bool:
    return bool(text) and AI_SECTION_HEADING in text

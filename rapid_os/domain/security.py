"""Security baseline of a project: which parts apply and how the template is rendered. Pure: no I/O.

The baseline (`templates/security/baseline.md`) and the CI workflow (`templates/ci/*.yml`) have
conditional regions, marked on their own lines with `<!-- if NAME -->` / `<!-- endif -->` in
Markdown and `# if NAME` / `# endif` in YAML. A region is kept when every enclosing condition holds.
"""

from __future__ import annotations

import re
from typing import Collection, Iterable, Mapping

# Stacks whose product is built around models or agents: no question, the AI section applies.
# (Only the ids of before the component catalog: now a project answers `ai`.)
AI_STACKS = frozenset({"python-ai", "nodejs-ai"})
# Stacks that expose an API: the API Security Top 10 applies.
API_STACKS = frozenset(
    {
        "python-api", "python-ai", "nodejs-ai", "web-modern",
        "python-fastapi", "python-django", "node-nestjs", "node-fastify", "go", "rust-axum", "ruby-rails",
        "dotnet-aspnetcore", "java-spring-boot", "kotlin-spring-boot", "php-laravel",
        "nextjs", "nuxt", "sveltekit",
    }
)
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
    "python-fastapi": "python",
    "python-django": "python",
    "node-nestjs": "typescript",
    "node-fastify": "typescript",
    "nextjs": "typescript",
    "nuxt": "typescript",
    "sveltekit": "typescript",
    "react-vite": "typescript",
    "angular": "typescript",
    "vue-vite": "typescript",
    "svelte-vite": "typescript",
    "astro": "typescript",
    "go": "go",
    "rust-axum": "rust",
    "ruby-rails": "ruby",
    "dotnet-aspnetcore": "dotnet",
    "java-spring-boot": "java",
    "kotlin-spring-boot": "kotlin",
    "php-laravel": "php",
}
_SCANNED_CI_LANGUAGES: Mapping[str, str] = {
    "python": "python",
    "typescript": "typescript",
    "javascript": "typescript",
    "go": "go",
    "rust": "rust",
    "ruby": "ruby",
    "csharp": "dotnet",
    "c#": "dotnet",
    "java": "java",
    "kotlin": "kotlin",
    "php": "php",
}
CI_WORKFLOW_PATH = ".github/workflows/rapid-security.yml"
CI_ADDED_NOTE = "Rapid OS añadió este workflow; revísalo antes del primer commit"
CI_PLANNED_NOTE = "Rapid OS añadirá este workflow al cerrar el onboarding; revísalo antes del primer commit"

AI_SECTION_HEADING = "## Seguridad de IA"
ASVS_LEVEL_TOKEN = "{ASVS_LEVEL}"

_MARKER = re.compile(r"^\s*(?:<!--\s*(?P<md>if\s+\w+|endif)\s*-->|#\s*(?P<yml>if\s+\w+|endif))\s*$")


def is_ai_stack(stack_id: "str | Iterable[str] | None") -> bool:
    if stack_id is None:
        return False
    ids = [stack_id] if isinstance(stack_id, str) else list(stack_id)
    return any(item in AI_STACKS for item in ids)


def has_api(stack_id: "str | Iterable[str] | None") -> bool:
    """True when the stack, or any of the stacks of the project, exposes an API."""
    if stack_id is None:
        return False
    ids = [stack_id] if isinstance(stack_id, str) else list(stack_id)
    return any(item in API_STACKS for item in ids)


def effective_ai(stack_id: "str | Iterable[str] | None", decision: bool | None) -> bool:
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
    template: str, *, archetype: str, stack_id: "str | Iterable[str] | None", ai: bool | None
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


def render_ci_workflow(template: str, *, archetype: str, primary: bool = True) -> str:
    """The CI workflow: Corporate adds the SBOM and the provenance, and only the first workflow of a
    project scans the secrets (a second language would repeat the same scan)."""
    return render_conditionals(template, {archetype, "primary"} if primary else {archetype})


def ci_language(stack_id: str | None, scanned_languages: Collection[str] = ()) -> str | None:
    """The language of the CI template (`templates/ci/<language>-security.yml`), or None when there is none."""
    if stack_id in CI_LANGUAGE_BY_STACK:
        return CI_LANGUAGE_BY_STACK[stack_id]
    if stack_id == "generic":
        lowered = {value.lower() for value in scanned_languages}
        for scanned in ("python", "typescript", "javascript", "go", "rust", "ruby", "csharp", "c#", "java", "kotlin", "php"):
            if scanned in lowered:
                return _SCANNED_CI_LANGUAGES[scanned]
    return None


def ci_languages(stack_ids: Iterable[str], scanned_languages: Collection[str] = ()) -> list[str]:
    """The distinct CI languages of a project, in the order of its stacks (the backend's first)."""
    found: list[str] = []
    for stack_id in stack_ids:
        language = ci_language(stack_id, scanned_languages)
        if language and language not in found:
            found.append(language)
    return found


def ci_workflow_path(language: str, index: int) -> str:
    """The first workflow keeps the well-known path; another language gets its own file."""
    return CI_WORKFLOW_PATH if index == 0 else f".github/workflows/rapid-security-{language}.yml"


def security_mentions_asvs(text: str | None) -> bool:
    return bool(text) and "ASVS" in text


def security_has_ai_section(text: str | None) -> bool:
    return bool(text) and AI_SECTION_HEADING in text

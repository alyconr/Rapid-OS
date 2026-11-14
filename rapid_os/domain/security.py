"""Security baseline of a project: which parts apply and how the template is rendered. Pure: no I/O.

The baseline (`templates/security/baseline.md`) and the CI workflow (`templates/ci/*.yml`) have
conditional regions, marked on their own lines with `<!-- if NAME -->` / `<!-- endif -->` in
Markdown and `# if NAME` / `# endif` in YAML. A region is kept when every enclosing condition holds.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Collection, Iterable, Mapping, Sequence

# Stacks whose product is built around models or agents: no question, the AI section applies.
# (Only the ids of before the component catalog: now a project answers `ai`.)
AI_STACKS = frozenset({"python-ai", "nodejs-ai"})
# Stacks that expose an API: the API Security Top 10 applies.
API_STACKS = frozenset(
    {
        "python-api", "python-ai", "nodejs-ai", "web-modern",
        "python-fastapi", "python-django", "node-nestjs", "node-fastify", "hono", "go", "rust-axum", "ruby-rails",
        "dotnet-aspnetcore", "java-spring-boot", "kotlin-spring-boot", "php-laravel",
        "nextjs", "nuxt", "sveltekit",
        # A BaaS exposes its data API to the browser: the API Security Top 10 applies.
        "supabase", "firebase",
    }
)
# BaaS providers: the baseline and the CI workflow have a region for each.
BAAS_PROVIDERS = ("supabase", "firebase")
# Document databases (NoSQL injection, CWE-943): a BaaS stack, or a decided service engine.
DOCUMENT_STACKS = frozenset({"firebase"})
DOCUMENT_ENGINES = frozenset({"mongodb"})
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
    "hono": "typescript",
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
    # The language of the provider's functions and of the tests of its rules.
    "supabase": "typescript",
    "firebase": "typescript",
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
# A workflow per language: `rapid-security-<language>.yml`, named `rapid-security (<language>)`.
CI_WORKFLOW_PREFIX = ".github/workflows/rapid-security"
# The path of before the language was part of it: a project that has it is left as it is.
CI_WORKFLOW_PATH = f"{CI_WORKFLOW_PREFIX}.yml"
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


def security_regions(stack_id: "str | Iterable[str] | None", engines: Iterable[str] = ()) -> frozenset[str]:
    """The regions of the baseline that depend on the data store: the BaaS provider, `documents` for a
    document database (Firestore, or the service `database:mongodb`) and `mongodb` for that engine."""
    ids = {stack_id} if isinstance(stack_id, str) else set(stack_id or ())
    engine_ids = set(engines)
    regions = {provider for provider in BAAS_PROVIDERS if provider in ids}
    if ids & DOCUMENT_STACKS or engine_ids & DOCUMENT_ENGINES:
        regions.add("documents")
    regions.update(engine_ids & DOCUMENT_ENGINES)
    return frozenset(regions)


def render_security_standard(
    template: str,
    *,
    archetype: str,
    stack_id: "str | Iterable[str] | None",
    ai: bool | None,
    engines: Iterable[str] = (),
) -> str:
    """`standards/security.md`: the baseline at the archetype's level, with the API and AI parts
    only where they apply, and the parts of the data store decided (`engines`: the service engines)."""
    active = {archetype}
    active.update(security_regions(stack_id, engines))
    if has_api(stack_id):
        active.add("api")
    if effective_ai(stack_id, ai):
        active.add("ai")
    body = render_conditionals(template, active)
    return body.replace(ASVS_LEVEL_TOKEN, ASVS_LEVELS.get(archetype, "L1"))


def render_ci_workflow(
    template: str,
    *,
    archetype: str,
    primary: bool = True,
    language: str | None = None,
    stack_ids: Iterable[str] = (),
    dirs: Sequence[str] = (".",),
) -> str:
    """The CI workflow: Corporate adds the SBOM and the provenance, and only the first workflow of a
    project scans the secrets (a second language would repeat the same scan). With a `language`,
    the workflow is named after it (`rapid-security-<language>`, like its file) so the workflows of a
    project do not look alike on GitHub. `dirs` are the folders of the components of that language
    (`backend`, `frontend`, or `.` for a project in one folder): the jobs that read a manifest or a
    lockfile run once in each (H-78)."""
    active = {archetype, "primary"} if primary else {archetype}
    # The tests of a BaaS provider's rules run in the workflow of its language (the frontend's).
    active.update(provider for provider in BAAS_PROVIDERS if provider in set(stack_ids))
    body = render_conditionals(template, active)
    if language:
        body = re.sub(r"^name: rapid-security[ \t]*$", f"name: rapid-security-{language}", body, count=1, flags=re.MULTILINE)
    return body.replace(COMPONENT_DIRS_TOKEN, json.dumps(list(dirs) or ["."]))


# The matrix of folders of the jobs that read a manifest or a lockfile.
COMPONENT_DIRS_TOKEN = "{RAPID_COMPONENT_DIRS}"
# Components that can live in a folder of their own (fullstack-separated: backend/ and frontend/).
_FOLDER_COMPONENTS = ("backend", "frontend")


def ci_component_dirs(
    component_stacks: Mapping[str, str], scanned_languages: Collection[str] = ()
) -> dict[str, list[str]]:
    """The folders of each CI language, from the components of the topology (setup.json).

    A backend and a frontend with different stacks live in `backend/` and `frontend/`, the same rule as
    the test command of each component; any other project lives in the root (`.`)."""
    chosen = {c: s for c, s in component_stacks.items() if c in _FOLDER_COMPONENTS}
    separate = len(chosen) == 2 and len(set(chosen.values())) == 2
    found: dict[str, list[str]] = {}
    ordered = [c for c in ("backend", "frontend") if c in component_stacks] + [
        c for c in component_stacks if c not in ("backend", "frontend")
    ]
    for component in ordered:
        language = ci_language(component_stacks[component], scanned_languages)
        if not language:
            continue
        folder = component if separate and component in chosen else "."
        dirs = found.setdefault(language, [])
        if folder not in dirs:
            dirs.append(folder)
    for language, dirs in found.items():
        if "." in dirs and len(dirs) > 1:  # a BaaS beside a separate frontend: its folder is the frontend's
            found[language] = [d for d in dirs if d != "."]
    return found


# The first line of a workflow Rapid OS writes: what it is and the SHA-256 of the rest of the file, so a
# later version can tell a workflow nobody edited (it is replaced) from one the person changed (`.new`).
CI_STAMP_PREFIX = "# rapid-os-ci:"
_STAMP = re.compile(r"^# rapid-os-ci: (?P<language>[a-z]+) sha256=(?P<digest>[0-9a-f]{64})\n")


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n")


def ci_body_digest(body: str) -> str:
    return hashlib.sha256(_lf(body).encode("utf-8")).hexdigest()


def stamp_ci_workflow(body: str, language: str) -> str:
    """The workflow with its first line: language and digest of the body."""
    return f"{CI_STAMP_PREFIX} {language} sha256={ci_body_digest(body)}\n{body}"


def ci_workflow_state(text: str, expected: str, legacy_digests: Collection[str] = ()) -> str:
    """`current` (it is what this version writes), `outdated` (written by Rapid OS and not edited since:
    it can be replaced), or `edited` (the person changed it, or it was not written by Rapid OS)."""
    normalized = _lf(text)
    if normalized == _lf(expected):
        return "current"
    stamp = _STAMP.match(normalized)
    if stamp is not None:
        body = normalized[stamp.end():]
        return "outdated" if ci_body_digest(body) == stamp.group("digest") else "edited"
    return "outdated" if ci_body_digest(normalized) in legacy_digests else "edited"


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


def ci_workflow_path(language: str) -> str:
    """The workflow of a language, also when the project has just one."""
    return f"{CI_WORKFLOW_PREFIX}-{language}.yml"


def security_mentions_asvs(text: str | None) -> bool:
    return bool(text) and "ASVS" in text


def security_has_ai_section(text: str | None) -> bool:
    return bool(text) and AI_SECTION_HEADING in text

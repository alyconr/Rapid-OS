from dataclasses import dataclass
from pathlib import Path
from re import split

from rapid_os.core.filesystem import create_backup


NOT_SPECIFIED = "_Not specified._"
SUPPORTED_MODES = ("new feature", "refactor", "bugfix", "legacy hardening")
MODE_ALIASES = {
    "1": "new feature",
    "feature": "new feature",
    "new": "new feature",
    "new feature": "new feature",
    "2": "refactor",
    "refactor": "refactor",
    "refactoring": "refactor",
    "3": "bugfix",
    "bug": "bugfix",
    "bugfix": "bugfix",
    "fix": "bugfix",
    "4": "legacy hardening",
    "hardening": "legacy hardening",
    "legacy": "legacy hardening",
    "legacy hardening": "legacy hardening",
}


@dataclass(frozen=True)
class ScopeSpec:
    initiative_name: str
    mode: str
    business_objective: str
    problem_statement: str
    scope: list[str]
    out_of_scope: list[str]
    actors_users: list[str]
    main_flow: list[str]
    edge_cases: list[str]
    business_rules: list[str]
    technical_constraints: list[str]
    affected_files_modules: list[str]
    data_impact: str
    acceptance_criteria: list[str]
    testing_strategy: list[str]
    implementation_tasks: list[str]


def normalize_mode(mode):
    normalized = (mode or "").strip().lower()
    return MODE_ALIASES.get(normalized, "new feature")


def normalize_text(value):
    normalized = (value or "").strip()
    return normalized if normalized else NOT_SPECIFIED


def parse_list(value):
    if not value or not value.strip():
        return []
    return [item.strip() for item in split(r"[;,]", value) if item.strip()]


def render_text(value):
    return normalize_text(value)


def render_bullets(items):
    normalized_items = [item.strip() for item in items if item and item.strip()]
    if not normalized_items:
        return NOT_SPECIFIED
    return "\n".join(f"- {item}" for item in normalized_items)


def render_checklist(items):
    normalized_items = [item.strip() for item in items if item and item.strip()]
    if not normalized_items:
        return NOT_SPECIFIED
    return "\n".join(f"- [ ] {item}" for item in normalized_items)


def render_specs(spec):
    return (
        f"# SPEC: {render_text(spec.initiative_name)}\n\n"
        f"## Mode\n{render_text(spec.mode)}\n\n"
        f"## Business Objective\n{render_text(spec.business_objective)}\n\n"
        f"## Problem Statement\n{render_text(spec.problem_statement)}\n\n"
        f"## Scope\n{render_bullets(spec.scope)}\n\n"
        f"## Out of Scope\n{render_bullets(spec.out_of_scope)}\n\n"
        f"## Actors / Users\n{render_bullets(spec.actors_users)}\n\n"
        f"## Main Flow\n{render_bullets(spec.main_flow)}\n\n"
        f"## Edge Cases\n{render_bullets(spec.edge_cases)}\n\n"
        f"## Business Rules\n{render_bullets(spec.business_rules)}\n\n"
        f"## Technical Constraints\n{render_bullets(spec.technical_constraints)}\n\n"
        f"## Affected Files / Modules\n{render_bullets(spec.affected_files_modules)}\n\n"
        f"## Data Impact\n{render_text(spec.data_impact)}"
    )


def render_tasks(spec):
    return (
        f"# TASKS: {render_text(spec.initiative_name)}\n\n"
        f"## Implementation Tasks\n{render_checklist(spec.implementation_tasks)}\n\n"
        "## Execution Notes\n"
        "- Work from `SPECS.md` as the source of scope.\n"
        "- Validate each task against `ACCEPTANCE.md`.\n"
        "- Keep implementation changes inside the documented scope."
    )


def render_acceptance(spec):
    return (
        f"# ACCEPTANCE: {render_text(spec.initiative_name)}\n\n"
        f"## Acceptance Criteria\n{render_checklist(spec.acceptance_criteria)}\n\n"
        f"## Testing Strategy\n{render_bullets(spec.testing_strategy)}\n\n"
        "## Definition of Done\n"
        "- [ ] Acceptance criteria reviewed\n"
        "- [ ] Testing strategy completed or explicitly deferred\n"
        "- [ ] Implementation matches `SPECS.md`\n"
        "- [ ] Tasks in `TASKS.md` are complete or intentionally deferred"
    )


def render_scope_artifacts(spec):
    return {
        "SPECS.md": render_specs(spec),
        "TASKS.md": render_tasks(spec),
        "ACCEPTANCE.md": render_acceptance(spec),
    }


def write_scope_artifacts(spec, current_dir):
    written = []
    for filename, content in render_scope_artifacts(spec).items():
        target = Path(current_dir) / filename
        create_backup(target)
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written

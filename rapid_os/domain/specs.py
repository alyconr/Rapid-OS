import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping

from rapid_os.domain.project import normalize_evidence_path
from rapid_os.domain.scope import (
    NOT_SPECIFIED,
    ScopeSpec,
    render_bullets,
    render_checklist,
    render_text,
)


SPEC_SCHEMA_VERSION = 1
SPEC_REVISION_SCHEMA_VERSION = 1

SPEC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
SPEC_SLUG_TOKEN_RE = re.compile(r"[^a-z0-9]+")

SPEC_ARTIFACT_FILENAMES = (
    "requirements.md",
    "tasks.md",
    "acceptance.md",
)

CANONICAL_SPEC_REVISION_KEYS = frozenset(
    {
        "schema_version",
        "spec_id",
        "revision",
        "title",
        "mode",
        "business_objective",
        "problem_statement",
        "scope",
        "out_of_scope",
        "actors_users",
        "main_flow",
        "edge_cases",
        "business_rules",
        "technical_constraints",
        "affected_paths",
        "data_impact",
        "acceptance_criteria",
        "testing_strategy",
        "implementation_tasks",
        "tags",
        "artifact_digests",
        "content_digest",
    }
)


def is_canonical_revision_dir_name(name: str) -> bool:
    """Return True if `name` is the canonical directory name for a positive integer revision (`0001`..`9999`, `10000`, ...)."""
    if not isinstance(name, str) or not name.isdigit() or not name.isascii():
        return False
    revision = int(name)
    if revision < 1:
        return False
    return name == f"{revision:04d}"


def format_revision_dir_name(revision: int) -> str:
    """Return the canonical directory name (`0001`..`9999`, `10000`, ...) for a positive integer revision."""
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise InvalidRevisionManifestError(
            f"Invalid revision number '{revision}': must be a positive integer."
        )
    return f"{revision:04d}"


class SpecRegistryError(ValueError):
    """Base domain error for Spec Registry operations with an associated RAPID8xx diagnostic code."""

    default_code = "RAPID801"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        path: Path | str | None = None,
    ):
        super().__init__(message)
        self.code = code or self.default_code
        self.path = path


class InvalidSpecRecordError(SpecRegistryError):
    default_code = "RAPID801"


class CurrentRevisionMissingError(SpecRegistryError):
    default_code = "RAPID802"


class InvalidRevisionManifestError(SpecRegistryError):
    default_code = "RAPID803"


class SpecArtifactDriftError(SpecRegistryError):
    default_code = "RAPID804"


class SpecLifecycleError(SpecRegistryError):
    default_code = "RAPID805"


class DuplicateSpecIdentityError(SpecRegistryError):
    default_code = "RAPID806"


class SpecNotFoundError(SpecRegistryError):
    default_code = "RAPID807"


class UnsafeSpecPathError(SpecRegistryError):
    default_code = "RAPID808"


class SpecStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    ARCHIVED = "archived"

    @classmethod
    def coerce(cls, value: object) -> "SpecStatus":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise ValueError(
            f"Invalid SpecStatus '{value}': expected one of {[m.value for m in cls]}."
        )


ALLOWED_SPEC_TRANSITIONS: Mapping[SpecStatus, frozenset[SpecStatus]] = {
    SpecStatus.DRAFT: frozenset(
        {SpecStatus.DRAFT, SpecStatus.READY, SpecStatus.ARCHIVED}
    ),
    SpecStatus.READY: frozenset(
        {SpecStatus.DRAFT, SpecStatus.READY, SpecStatus.ARCHIVED}
    ),
    SpecStatus.ARCHIVED: frozenset(),
}


def validate_status_transition(
    current: SpecStatus | str,
    target: SpecStatus | str,
) -> SpecStatus:
    """Validate and return `target` status if `current -> target` is allowed in Phase 3."""
    try:
        current_status = SpecStatus.coerce(current)
        target_status = SpecStatus.coerce(target)
    except ValueError as exc:
        raise SpecLifecycleError(str(exc)) from exc

    allowed = ALLOWED_SPEC_TRANSITIONS.get(current_status, frozenset())
    if target_status not in allowed:
        raise SpecLifecycleError(
            f"Invalid spec status transition '{current_status.value}' -> '{target_status.value}'."
        )
    return target_status


class SpecMode(str, Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    HARDENING = "hardening"
    RESEARCH = "research"

    @classmethod
    def coerce(cls, value: object) -> "SpecMode":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = (
                value.strip().lower().replace("_", " ").replace("-", " ")
            )
            aliases = {
                "1": cls.FEATURE,
                "feature": cls.FEATURE,
                "new": cls.FEATURE,
                "new feature": cls.FEATURE,
                "2": cls.REFACTOR,
                "refactor": cls.REFACTOR,
                "refactoring": cls.REFACTOR,
                "3": cls.BUGFIX,
                "bug": cls.BUGFIX,
                "bugfix": cls.BUGFIX,
                "bug fix": cls.BUGFIX,
                "fix": cls.BUGFIX,
                "4": cls.HARDENING,
                "hardening": cls.HARDENING,
                "legacy": cls.HARDENING,
                "legacy hardening": cls.HARDENING,
                "5": cls.RESEARCH,
                "research": cls.RESEARCH,
            }
            if normalized in aliases:
                return aliases[normalized]
        raise ValueError(
            f"Invalid SpecMode '{value}': expected one of {[m.value for m in cls]}."
        )


LEGACY_SCOPE_MODE_BY_SPEC_MODE: Mapping[SpecMode, str] = {
    SpecMode.FEATURE: "new feature",
    SpecMode.REFACTOR: "refactor",
    SpecMode.BUGFIX: "bugfix",
    SpecMode.HARDENING: "legacy hardening",
    SpecMode.RESEARCH: "new feature",
}


def validate_spec_id(raw_id: object, label: str = "spec id") -> str:
    """Validate that `raw_id` is a canonical, path-safe, lowercase spec identifier."""
    if not isinstance(raw_id, str):
        raise DuplicateSpecIdentityError(
            f"Invalid {label}: expected a string."
        )
    if "\x00" in raw_id:
        raise DuplicateSpecIdentityError(
            f"Invalid {label}: null bytes are not allowed."
        )
    if not raw_id or raw_id != raw_id.strip():
        raise DuplicateSpecIdentityError(
            f"Invalid {label} '{raw_id}': leading or trailing whitespace is not allowed."
        )
    if not SPEC_ID_RE.match(raw_id):
        raise DuplicateSpecIdentityError(
            f"Invalid {label} '{raw_id}': must match {SPEC_ID_RE.pattern}."
        )
    return raw_id


def derive_spec_id(title: str) -> str:
    """Deterministically derive a valid spec ID slug from an initiative title."""
    if not isinstance(title, str) or "\x00" in title:
        raise DuplicateSpecIdentityError(
            "Cannot derive spec ID from an invalid title."
        )
    lowered = title.strip().lower()
    slug = SPEC_SLUG_TOKEN_RE.sub("-", lowered).strip("-")
    if len(slug) > 63:
        slug = slug[:63].rstrip("-")
    if not slug:
        raise DuplicateSpecIdentityError(
            f"Cannot derive a valid spec ID from title '{title}'."
        )
    return validate_spec_id(slug)


def sha256_text(content: str) -> str:
    """Compute SHA-256 hex digest over exact UTF-8 bytes of `content`."""
    if not isinstance(content, str):
        raise TypeError("Expected string content for SHA-256 digest calculation.")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _clean_free_text(value: object, field_name: str, *, allow_empty: bool = True) -> str:
    if value is None:
        cleaned = ""
    elif not isinstance(value, str):
        raise ValueError(f"SpecRevision '{field_name}' must be a string.")
    else:
        if "\x00" in value:
            raise ValueError(
                f"SpecRevision '{field_name}' cannot contain null bytes."
            )
        cleaned = value.strip()
        if cleaned == NOT_SPECIFIED:
            cleaned = ""

    if not allow_empty and not cleaned:
        raise ValueError(f"SpecRevision '{field_name}' must be a non-empty string.")
    return cleaned


def _clean_ordered_items(
    items: Iterable[object] | None,
    field_name: str,
) -> tuple[str, ...]:
    if items is None:
        return ()
    if isinstance(items, (str, bytes)):
        raise ValueError(
            f"SpecRevision '{field_name}' must be a sequence of strings, not a single string."
        )
    cleaned: list[str] = []
    for raw in items:
        if raw is None:
            continue
        if not isinstance(raw, str):
            raise ValueError(
                f"SpecRevision '{field_name}' items must be strings."
            )
        if "\x00" in raw:
            raise ValueError(
                f"SpecRevision '{field_name}' items cannot contain null bytes."
            )
        stripped = raw.strip()
        if stripped and stripped != NOT_SPECIFIED:
            cleaned.append(stripped)
    return tuple(cleaned)


def _clean_tags(tags: Iterable[object] | None) -> tuple[str, ...]:
    if tags is None:
        return ()
    if isinstance(tags, (str, bytes)):
        raise ValueError(
            "SpecRevision 'tags' must be a sequence of strings, not a single string."
        )
    unique_tags: set[str] = set()
    for raw in tags:
        if raw is None:
            continue
        if not isinstance(raw, str):
            raise ValueError("SpecRevision 'tags' items must be strings.")
        if "\x00" in raw:
            raise ValueError("SpecRevision 'tags' cannot contain null bytes.")
        stripped = raw.strip().lower()
        if stripped and stripped != NOT_SPECIFIED.lower():
            unique_tags.add(stripped)
    return tuple(sorted(unique_tags))


def _clean_affected_paths(
    paths: Iterable[object] | None,
    root: Path | None = None,
) -> tuple[str, ...]:
    if paths is None:
        return ()
    if isinstance(paths, (str, bytes)):
        raise ValueError(
            "SpecRevision 'affected_paths' must be a sequence of path strings."
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        if raw is None:
            continue
        if not isinstance(raw, (str, Path)):
            raise ValueError(
                "SpecRevision 'affected_paths' items must be strings or Paths."
            )
        raw_str = str(raw).strip()
        if not raw_str or raw_str == NOT_SPECIFIED:
            continue
        portable = normalize_evidence_path(raw_str, root)
        if portable not in seen:
            seen.add(portable)
            normalized.append(portable)
    return tuple(normalized)


@dataclass(frozen=True)
class SpecRecord:
    schema_version: int = SPEC_SCHEMA_VERSION
    id: str = ""
    status: SpecStatus = SpecStatus.DRAFT
    current_revision: int = 1

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != SPEC_SCHEMA_VERSION
        ):
            raise InvalidSpecRecordError(
                f"Unsupported SpecRecord schema_version '{self.schema_version}': expected {SPEC_SCHEMA_VERSION}."
            )
        validated_id = validate_spec_id(self.id, "SpecRecord.id")
        object.__setattr__(self, "id", validated_id)

        try:
            coerced_status = SpecStatus.coerce(self.status)
        except ValueError as exc:
            raise InvalidSpecRecordError(str(exc)) from exc
        object.__setattr__(self, "status", coerced_status)

        if (
            isinstance(self.current_revision, bool)
            or not isinstance(self.current_revision, int)
            or self.current_revision < 1
        ):
            raise InvalidSpecRecordError(
                f"Invalid SpecRecord current_revision '{self.current_revision}': must be a positive integer."
            )

    @property
    def revision(self) -> int:
        return self.current_revision

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "status": self.status.value,
            "current_revision": self.current_revision,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "SpecRecord":
        if not isinstance(payload, Mapping):
            raise InvalidSpecRecordError("SpecRecord payload must be a JSON object.")
        allowed_keys = {"schema_version", "id", "status", "current_revision"}
        unknown_keys = set(payload.keys()) - allowed_keys
        if unknown_keys:
            raise InvalidSpecRecordError(
                f"SpecRecord contains unexpected fields: {sorted(unknown_keys)}."
            )
        for req_key in ("schema_version", "id", "status", "current_revision"):
            if req_key not in payload:
                raise InvalidSpecRecordError(
                    f"SpecRecord missing required field '{req_key}'."
                )
        return cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            id=payload["id"],  # type: ignore[arg-type]
            status=payload["status"],  # type: ignore[arg-type]
            current_revision=payload["current_revision"],  # type: ignore[arg-type]
        )

    @classmethod
    def from_json(cls, raw_json: str) -> "SpecRecord":
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise InvalidSpecRecordError(
                f"SpecRecord is invalid JSON: {exc.msg}"
            ) from exc
        return cls.from_dict(payload)


@dataclass(frozen=True)
class SpecRevision:
    schema_version: int = SPEC_REVISION_SCHEMA_VERSION
    spec_id: str = ""
    revision: int = 1

    title: str = ""
    mode: SpecMode = SpecMode.FEATURE

    business_objective: str = ""
    problem_statement: str = ""

    scope: tuple[str, ...] = ()
    out_of_scope: tuple[str, ...] = ()

    actors_users: tuple[str, ...] = ()
    main_flow: tuple[str, ...] = ()
    edge_cases: tuple[str, ...] = ()

    business_rules: tuple[str, ...] = ()
    technical_constraints: tuple[str, ...] = ()

    affected_paths: tuple[str, ...] = ()

    data_impact: str = ""

    acceptance_criteria: tuple[str, ...] = ()
    testing_strategy: tuple[str, ...] = ()
    implementation_tasks: tuple[str, ...] = ()

    tags: tuple[str, ...] = ()

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != SPEC_REVISION_SCHEMA_VERSION
        ):
            raise InvalidRevisionManifestError(
                f"Unsupported SpecRevision schema_version '{self.schema_version}': expected {SPEC_REVISION_SCHEMA_VERSION}."
            )
        try:
            validated_spec_id = validate_spec_id(self.spec_id, "SpecRevision.spec_id")
        except DuplicateSpecIdentityError as exc:
            raise InvalidRevisionManifestError(str(exc)) from exc
        object.__setattr__(self, "spec_id", validated_spec_id)

        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 1
        ):
            raise InvalidRevisionManifestError(
                f"Invalid SpecRevision revision '{self.revision}': must be a positive integer."
            )

        try:
            cleaned_title = _clean_free_text(self.title, "title", allow_empty=False)
            coerced_mode = SpecMode.coerce(self.mode)
            cleaned_objective = _clean_free_text(
                self.business_objective, "business_objective"
            )
            cleaned_problem = _clean_free_text(
                self.problem_statement, "problem_statement"
            )
            cleaned_scope = _clean_ordered_items(self.scope, "scope")
            cleaned_out_of_scope = _clean_ordered_items(
                self.out_of_scope, "out_of_scope"
            )
            cleaned_actors = _clean_ordered_items(
                self.actors_users, "actors_users"
            )
            cleaned_main_flow = _clean_ordered_items(self.main_flow, "main_flow")
            cleaned_edge_cases = _clean_ordered_items(self.edge_cases, "edge_cases")
            cleaned_business_rules = _clean_ordered_items(
                self.business_rules, "business_rules"
            )
            cleaned_tech_constraints = _clean_ordered_items(
                self.technical_constraints, "technical_constraints"
            )
            cleaned_paths = _clean_affected_paths(self.affected_paths)
            cleaned_data_impact = _clean_free_text(self.data_impact, "data_impact")
            cleaned_acceptance = _clean_ordered_items(
                self.acceptance_criteria, "acceptance_criteria"
            )
            cleaned_testing = _clean_ordered_items(
                self.testing_strategy, "testing_strategy"
            )
            cleaned_tasks = _clean_ordered_items(
                self.implementation_tasks, "implementation_tasks"
            )
            cleaned_tags = _clean_tags(self.tags)
        except ValueError as exc:
            raise InvalidRevisionManifestError(str(exc)) from exc

        object.__setattr__(self, "title", cleaned_title)
        object.__setattr__(self, "mode", coerced_mode)
        object.__setattr__(self, "business_objective", cleaned_objective)
        object.__setattr__(self, "problem_statement", cleaned_problem)
        object.__setattr__(self, "scope", cleaned_scope)
        object.__setattr__(self, "out_of_scope", cleaned_out_of_scope)
        object.__setattr__(self, "actors_users", cleaned_actors)
        object.__setattr__(self, "main_flow", cleaned_main_flow)
        object.__setattr__(self, "edge_cases", cleaned_edge_cases)
        object.__setattr__(self, "business_rules", cleaned_business_rules)
        object.__setattr__(self, "technical_constraints", cleaned_tech_constraints)
        object.__setattr__(self, "affected_paths", cleaned_paths)
        object.__setattr__(self, "data_impact", cleaned_data_impact)
        object.__setattr__(self, "acceptance_criteria", cleaned_acceptance)
        object.__setattr__(self, "testing_strategy", cleaned_testing)
        object.__setattr__(self, "implementation_tasks", cleaned_tasks)
        object.__setattr__(self, "tags", cleaned_tags)

    @property
    def actors(self) -> tuple[str, ...]:
        return self.actors_users

    @property
    def revision_dir_name(self) -> str:
        return format_revision_dir_name(self.revision)

    def render_requirements(self) -> str:
        return render_requirements_artifact(self)

    def render_tasks(self) -> str:
        return render_tasks_artifact(self)

    def render_acceptance(self) -> str:
        return render_acceptance_artifact(self)

    def render_artifacts(self) -> dict[str, str]:
        return {
            "requirements.md": self.render_requirements(),
            "tasks.md": self.render_tasks(),
            "acceptance.md": self.render_acceptance(),
        }

    @property
    def artifact_digests(self) -> dict[str, str]:
        return {
            filename: sha256_text(content)
            for filename, content in self.render_artifacts().items()
        }

    def _canonical_content_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "spec_id": self.spec_id,
            "revision": self.revision,
            "title": self.title,
            "mode": self.mode.value,
            "business_objective": self.business_objective,
            "problem_statement": self.problem_statement,
            "scope": list(self.scope),
            "out_of_scope": list(self.out_of_scope),
            "actors_users": list(self.actors_users),
            "main_flow": list(self.main_flow),
            "edge_cases": list(self.edge_cases),
            "business_rules": list(self.business_rules),
            "technical_constraints": list(self.technical_constraints),
            "affected_paths": list(self.affected_paths),
            "data_impact": self.data_impact,
            "acceptance_criteria": list(self.acceptance_criteria),
            "testing_strategy": list(self.testing_strategy),
            "implementation_tasks": list(self.implementation_tasks),
            "tags": list(self.tags),
            "artifact_digests": self.artifact_digests,
        }

    @property
    def content_digest(self) -> str:
        canonical_json = json.dumps(
            self._canonical_content_payload(),
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256_text(canonical_json)

    def to_dict(self) -> dict[str, object]:
        payload = self._canonical_content_payload()
        payload["content_digest"] = self.content_digest
        return payload

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        *,
        verify_digests: bool = True,
    ) -> "SpecRevision":
        if not isinstance(payload, Mapping):
            raise InvalidRevisionManifestError(
                "SpecRevision payload must be a JSON object."
            )
        unknown_keys = set(payload.keys()) - CANONICAL_SPEC_REVISION_KEYS
        if unknown_keys:
            raise InvalidRevisionManifestError(
                f"SpecRevision contains unexpected fields: {sorted(unknown_keys)}."
            )
        required_keys = (
            "schema_version",
            "spec_id",
            "revision",
            "title",
            "mode",
        )
        for req_key in required_keys:
            if req_key not in payload:
                raise InvalidRevisionManifestError(
                    f"SpecRevision missing required field '{req_key}'."
                )

        if verify_digests:
            if "artifact_digests" not in payload or not isinstance(
                payload.get("artifact_digests"), Mapping
            ):
                raise InvalidRevisionManifestError(
                    "SpecRevision missing required 'artifact_digests' object."
                )
            if (
                "content_digest" not in payload
                or not isinstance(payload.get("content_digest"), str)
                or not str(payload.get("content_digest")).strip()
            ):
                raise InvalidRevisionManifestError(
                    "SpecRevision missing required 'content_digest' string."
                )

        instance = cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            spec_id=payload["spec_id"],  # type: ignore[arg-type]
            revision=payload["revision"],  # type: ignore[arg-type]
            title=payload["title"],  # type: ignore[arg-type]
            mode=payload["mode"],  # type: ignore[arg-type]
            business_objective=payload.get("business_objective", ""),  # type: ignore[arg-type]
            problem_statement=payload.get("problem_statement", ""),  # type: ignore[arg-type]
            scope=payload.get("scope", ()),  # type: ignore[arg-type]
            out_of_scope=payload.get("out_of_scope", ()),  # type: ignore[arg-type]
            actors_users=payload.get("actors_users", ()),  # type: ignore[arg-type]
            main_flow=payload.get("main_flow", ()),  # type: ignore[arg-type]
            edge_cases=payload.get("edge_cases", ()),  # type: ignore[arg-type]
            business_rules=payload.get("business_rules", ()),  # type: ignore[arg-type]
            technical_constraints=payload.get("technical_constraints", ()),  # type: ignore[arg-type]
            affected_paths=payload.get("affected_paths", ()),  # type: ignore[arg-type]
            data_impact=payload.get("data_impact", ""),  # type: ignore[arg-type]
            acceptance_criteria=payload.get("acceptance_criteria", ()),  # type: ignore[arg-type]
            testing_strategy=payload.get("testing_strategy", ()),  # type: ignore[arg-type]
            implementation_tasks=payload.get("implementation_tasks", ()),  # type: ignore[arg-type]
            tags=payload.get("tags", ()),  # type: ignore[arg-type]
        )

        if verify_digests:
            raw_digests = dict(payload["artifact_digests"])  # type: ignore[arg-type]
            if set(raw_digests.keys()) != set(SPEC_ARTIFACT_FILENAMES):
                raise InvalidRevisionManifestError(
                    f"SpecRevision 'artifact_digests' must contain exactly {list(SPEC_ARTIFACT_FILENAMES)}."
                )
            expected_digests = instance.artifact_digests
            if raw_digests != expected_digests:
                raise SpecArtifactDriftError(
                    f"SpecRevision artifact_digests in revision.json do not match canonical derived artifacts for '{instance.spec_id}' r{instance.revision}."
                )
            raw_content_digest = str(payload["content_digest"])
            if raw_content_digest != instance.content_digest:
                raise SpecArtifactDriftError(
                    f"SpecRevision content_digest mismatch for '{instance.spec_id}' r{instance.revision}."
                )

        return instance

    @classmethod
    def from_json(
        cls,
        raw_json: str,
        *,
        verify_digests: bool = True,
    ) -> "SpecRevision":
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise InvalidRevisionManifestError(
                f"SpecRevision is invalid JSON: {exc.msg}"
            ) from exc
        return cls.from_dict(payload, verify_digests=verify_digests)


def render_requirements_artifact(revision: SpecRevision) -> str:
    """Deterministically render `requirements.md` from a canonical `SpecRevision`."""
    return (
        f"# SPEC: {render_text(revision.title)}\n\n"
        f"## Title\n{render_text(revision.title)}\n\n"
        f"## Mode\n{render_text(revision.mode.value)}\n\n"
        f"## Business Objective\n{render_text(revision.business_objective)}\n\n"
        f"## Problem Statement\n{render_text(revision.problem_statement)}\n\n"
        f"## Scope\n{render_bullets(revision.scope)}\n\n"
        f"## Out of Scope\n{render_bullets(revision.out_of_scope)}\n\n"
        f"## Actors / Users\n{render_bullets(revision.actors_users)}\n\n"
        f"## Main Flow\n{render_bullets(revision.main_flow)}\n\n"
        f"## Edge Cases\n{render_bullets(revision.edge_cases)}\n\n"
        f"## Business Rules\n{render_bullets(revision.business_rules)}\n\n"
        f"## Technical Constraints\n{render_bullets(revision.technical_constraints)}\n\n"
        f"## Affected Files / Modules\n{render_bullets(revision.affected_paths)}\n\n"
        f"## Data Impact\n{render_text(revision.data_impact)}\n"
    )


def render_tasks_artifact(revision: SpecRevision) -> str:
    """Deterministically render `tasks.md` from a canonical `SpecRevision`."""
    return (
        f"# TASKS: {render_text(revision.title)}\n\n"
        f"## Implementation Tasks\n{render_checklist(revision.implementation_tasks)}\n\n"
        "## Planning Notes\n"
        "- Work from `requirements.md` as the source of scope.\n"
        "- Validate each task against `acceptance.md`.\n"
        "- Keep implementation changes inside the documented scope.\n"
    )


def render_acceptance_artifact(revision: SpecRevision) -> str:
    """Deterministically render `acceptance.md` from a canonical `SpecRevision`."""
    return (
        f"# ACCEPTANCE: {render_text(revision.title)}\n\n"
        f"## Acceptance Criteria\n{render_checklist(revision.acceptance_criteria)}\n\n"
        f"## Testing Strategy\n{render_bullets(revision.testing_strategy)}\n\n"
        "## Definition of Done\n"
        "- [ ] Acceptance criteria reviewed\n"
        "- [ ] Testing strategy completed or explicitly deferred\n"
        "- [ ] Implementation matches `requirements.md`\n"
        "- [ ] Tasks in `tasks.md` are complete or intentionally deferred\n"
    )


def spec_revision_from_scope(
    scope_spec: ScopeSpec,
    *,
    spec_id: str | None = None,
    revision: int = 1,
    tags: Iterable[str] = (),
) -> SpecRevision:
    """Explicit conversion from legacy `ScopeSpec` authoring DTO to canonical `SpecRevision`."""
    if not isinstance(scope_spec, ScopeSpec):
        raise TypeError("Expected a ScopeSpec instance.")

    raw_title = (scope_spec.initiative_name or "").strip()
    resolved_id = (
        validate_spec_id(spec_id)
        if spec_id is not None and str(spec_id).strip()
        else derive_spec_id(raw_title)
    )
    resolved_title = raw_title if raw_title else resolved_id

    return SpecRevision(
        schema_version=SPEC_REVISION_SCHEMA_VERSION,
        spec_id=resolved_id,
        revision=revision,
        title=resolved_title,
        mode=SpecMode.coerce(scope_spec.mode),
        business_objective=scope_spec.business_objective,
        problem_statement=scope_spec.problem_statement,
        scope=tuple(scope_spec.scope),
        out_of_scope=tuple(scope_spec.out_of_scope),
        actors_users=tuple(scope_spec.actors_users),
        main_flow=tuple(scope_spec.main_flow),
        edge_cases=tuple(scope_spec.edge_cases),
        business_rules=tuple(scope_spec.business_rules),
        technical_constraints=tuple(scope_spec.technical_constraints),
        affected_paths=tuple(scope_spec.affected_files_modules),
        data_impact=scope_spec.data_impact,
        acceptance_criteria=tuple(scope_spec.acceptance_criteria),
        testing_strategy=tuple(scope_spec.testing_strategy),
        implementation_tasks=tuple(scope_spec.implementation_tasks),
        tags=tuple(tags),
    )


def scope_spec_from_revision(revision: SpecRevision) -> ScopeSpec:
    """Convert a canonical `SpecRevision` into a legacy `ScopeSpec` DTO for legacy projection."""
    if not isinstance(revision, SpecRevision):
        raise TypeError("Expected a SpecRevision instance.")

    legacy_mode = LEGACY_SCOPE_MODE_BY_SPEC_MODE.get(
        revision.mode,
        "new feature",
    )
    return ScopeSpec(
        initiative_name=revision.title,
        mode=legacy_mode,
        business_objective=revision.business_objective,
        problem_statement=revision.problem_statement,
        scope=list(revision.scope),
        out_of_scope=list(revision.out_of_scope),
        actors_users=list(revision.actors_users),
        main_flow=list(revision.main_flow),
        edge_cases=list(revision.edge_cases),
        business_rules=list(revision.business_rules),
        technical_constraints=list(revision.technical_constraints),
        affected_files_modules=list(revision.affected_paths),
        data_impact=revision.data_impact,
        acceptance_criteria=list(revision.acceptance_criteria),
        testing_strategy=list(revision.testing_strategy),
        implementation_tasks=list(revision.implementation_tasks),
    )

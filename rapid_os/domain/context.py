import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from enum import Enum, IntEnum
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from rapid_os.domain.harnesses import validate_harness_id
from rapid_os.domain.project import (
    FACT_CATEGORIES,
    ProjectFact,
    ProjectModel,
    normalize_evidence_path,
)


CONTEXT_MANIFEST_SCHEMA_VERSION = 1
DEFAULT_MAX_CHARS = 24000

CONTEXT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._#-]*$")

SUPPORTED_HARNESSES = (
    "codex",
    "claude",
    "cursor",
    "vscode",
    "antigravity",
)


class ContextBudgetExceededError(ValueError):
    """Raised when required context fragments exceed the configured character budget."""

    def __init__(
        self,
        message: str,
        *,
        max_chars: int,
        required_chars: int,
        required_sources: tuple[str, ...] = (),
    ):
        super().__init__(message)
        self.max_chars = max_chars
        self.required_chars = required_chars
        self.required_sources = required_sources


class ContextRequiredSourceMissingError(ValueError):
    """Raised when one or more required context sources or kinds are missing."""

    def __init__(
        self,
        message: str,
        *,
        missing_kinds: tuple[str, ...] = (),
        missing_source_ids: tuple[str, ...] = (),
        manifest: "ContextManifest | None" = None,
    ):
        super().__init__(message)
        self.missing_kinds = tuple(missing_kinds)
        self.missing_source_ids = tuple(missing_source_ids)
        self.manifest = manifest


class ContextSourceKind(str, Enum):
    TASK_CONSTRAINTS = "task_constraints"
    SECURITY = "security"
    BUSINESS = "business"
    ARCHITECTURE = "architecture"
    TOPOLOGY = "topology"
    TECH_STACK = "tech_stack"
    CODING_RULES = "coding_rules"
    SPEC = "spec"
    TASKS = "tasks"
    ACCEPTANCE = "acceptance"
    DESIGN = "design"
    REFERENCE = "reference"
    CUSTOM = "custom"
    PROJECT_INTELLIGENCE = "project_intelligence"

    @classmethod
    def coerce(cls, value: object) -> "ContextSourceKind":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower().replace("-", "_")
            for member in cls:
                if member.value == normalized:
                    return member
        raise ValueError(
            f"Invalid ContextSourceKind '{value}': expected one of {[m.value for m in cls]}."
        )


class ContextPriority(IntEnum):
    LOW = 10
    MEDIUM = 50
    HIGH = 80
    CRITICAL = 100

    @classmethod
    def coerce(cls, value: object) -> "ContextPriority":
        if isinstance(value, cls):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            for member in cls:
                if int(member) == value:
                    return member
            if value >= cls.CRITICAL:
                return cls.CRITICAL
            if value >= cls.HIGH:
                return cls.HIGH
            if value >= cls.MEDIUM:
                return cls.MEDIUM
            if value > 0:
                return cls.LOW
        if isinstance(value, str):
            normalized = value.strip().upper()
            if normalized in cls.__members__:
                return cls[normalized]
            if normalized.isdigit():
                return cls.coerce(int(normalized))
        raise ValueError(
            f"Invalid ContextPriority '{value}': expected LOW(10), MEDIUM(50), HIGH(80), or CRITICAL(100)."
        )

    @property
    def label(self) -> str:
        return self.name.lower()


class ContextMode(str, Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    HARDENING = "hardening"
    RESEARCH = "research"
    GENERAL = "general"

    @classmethod
    def coerce(cls, value: object) -> "ContextMode":
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.GENERAL
        if isinstance(value, str):
            normalized = value.strip().lower().replace("_", " ").replace("-", " ")
            aliases = {
                "": cls.GENERAL,
                "general": cls.GENERAL,
                "feature": cls.FEATURE,
                "new feature": cls.FEATURE,
                "bugfix": cls.BUGFIX,
                "bug fix": cls.BUGFIX,
                "fix": cls.BUGFIX,
                "refactor": cls.REFACTOR,
                "refactoring": cls.REFACTOR,
                "hardening": cls.HARDENING,
                "legacy hardening": cls.HARDENING,
                "security": cls.HARDENING,
                "research": cls.RESEARCH,
            }
            if normalized in aliases:
                return aliases[normalized]
        raise ValueError(
            f"Invalid ContextMode '{value}': expected one of {[m.value for m in cls]}."
        )


DEFAULT_PRECEDENCE_ORDER: tuple[ContextSourceKind, ...] = (
    ContextSourceKind.TASK_CONSTRAINTS,
    ContextSourceKind.SECURITY,
    ContextSourceKind.BUSINESS,
    ContextSourceKind.ARCHITECTURE,
    ContextSourceKind.TOPOLOGY,
    ContextSourceKind.TECH_STACK,
    ContextSourceKind.CODING_RULES,
    ContextSourceKind.SPEC,
    ContextSourceKind.TASKS,
    ContextSourceKind.ACCEPTANCE,
    ContextSourceKind.DESIGN,
    ContextSourceKind.REFERENCE,
    ContextSourceKind.CUSTOM,
    ContextSourceKind.PROJECT_INTELLIGENCE,
)

DEFAULT_KIND_PRIORITIES: Mapping[ContextSourceKind, ContextPriority] = {
    ContextSourceKind.TASK_CONSTRAINTS: ContextPriority.CRITICAL,
    ContextSourceKind.SECURITY: ContextPriority.CRITICAL,
    ContextSourceKind.BUSINESS: ContextPriority.HIGH,
    ContextSourceKind.ARCHITECTURE: ContextPriority.HIGH,
    ContextSourceKind.TOPOLOGY: ContextPriority.HIGH,
    ContextSourceKind.TECH_STACK: ContextPriority.HIGH,
    ContextSourceKind.CODING_RULES: ContextPriority.MEDIUM,
    ContextSourceKind.SPEC: ContextPriority.HIGH,
    ContextSourceKind.TASKS: ContextPriority.MEDIUM,
    ContextSourceKind.ACCEPTANCE: ContextPriority.MEDIUM,
    ContextSourceKind.PROJECT_INTELLIGENCE: ContextPriority.MEDIUM,
    ContextSourceKind.DESIGN: ContextPriority.LOW,
    ContextSourceKind.REFERENCE: ContextPriority.LOW,
    ContextSourceKind.CUSTOM: ContextPriority.LOW,
}

DEFAULT_MODE_REQUIRED_KINDS: Mapping[ContextMode, tuple[ContextSourceKind, ...]] = {
    ContextMode.FEATURE: (),
    ContextMode.BUGFIX: (),
    ContextMode.REFACTOR: (),
    # Hardening cannot proceed without the security rules; a missing source is reported, never invented.
    ContextMode.HARDENING: (ContextSourceKind.SECURITY,),
    ContextMode.RESEARCH: (),
    ContextMode.GENERAL: (),
}

DEFAULT_MODE_PREFERRED_KINDS: Mapping[ContextMode, tuple[ContextSourceKind, ...]] = {
    ContextMode.BUGFIX: (
        ContextSourceKind.TASK_CONSTRAINTS,
        ContextSourceKind.ARCHITECTURE,
        ContextSourceKind.TOPOLOGY,
        ContextSourceKind.TECH_STACK,
        ContextSourceKind.CODING_RULES,
        ContextSourceKind.SECURITY,
        ContextSourceKind.SPEC,
        ContextSourceKind.ACCEPTANCE,
        ContextSourceKind.PROJECT_INTELLIGENCE,
    ),
    ContextMode.FEATURE: (
        ContextSourceKind.TASK_CONSTRAINTS,
        ContextSourceKind.BUSINESS,
        ContextSourceKind.SPEC,
        ContextSourceKind.TASKS,
        ContextSourceKind.ACCEPTANCE,
        ContextSourceKind.ARCHITECTURE,
        ContextSourceKind.TOPOLOGY,
        ContextSourceKind.TECH_STACK,
        ContextSourceKind.CODING_RULES,
        ContextSourceKind.SECURITY,
        ContextSourceKind.DESIGN,
        ContextSourceKind.REFERENCE,
        ContextSourceKind.PROJECT_INTELLIGENCE,
    ),
    ContextMode.HARDENING: (
        ContextSourceKind.TASK_CONSTRAINTS,
        ContextSourceKind.SECURITY,
        ContextSourceKind.ARCHITECTURE,
        ContextSourceKind.TOPOLOGY,
        ContextSourceKind.CODING_RULES,
        ContextSourceKind.TECH_STACK,
        ContextSourceKind.ACCEPTANCE,
        ContextSourceKind.PROJECT_INTELLIGENCE,
    ),
    ContextMode.REFACTOR: (
        ContextSourceKind.TASK_CONSTRAINTS,
        ContextSourceKind.ARCHITECTURE,
        ContextSourceKind.TOPOLOGY,
        ContextSourceKind.CODING_RULES,
        ContextSourceKind.TECH_STACK,
        ContextSourceKind.SECURITY,
        ContextSourceKind.SPEC,
        ContextSourceKind.TASKS,
        ContextSourceKind.ACCEPTANCE,
        ContextSourceKind.PROJECT_INTELLIGENCE,
    ),
    ContextMode.RESEARCH: (
        ContextSourceKind.TASK_CONSTRAINTS,
        ContextSourceKind.BUSINESS,
        ContextSourceKind.ARCHITECTURE,
        ContextSourceKind.TOPOLOGY,
        ContextSourceKind.TECH_STACK,
        ContextSourceKind.SPEC,
        ContextSourceKind.REFERENCE,
        ContextSourceKind.PROJECT_INTELLIGENCE,
    ),
    ContextMode.GENERAL: (
        ContextSourceKind.TASK_CONSTRAINTS,
        ContextSourceKind.SECURITY,
        ContextSourceKind.BUSINESS,
        ContextSourceKind.ARCHITECTURE,
        ContextSourceKind.TOPOLOGY,
        ContextSourceKind.TECH_STACK,
        ContextSourceKind.CODING_RULES,
        ContextSourceKind.SPEC,
        ContextSourceKind.TASKS,
        ContextSourceKind.ACCEPTANCE,
        ContextSourceKind.PROJECT_INTELLIGENCE,
        ContextSourceKind.DESIGN,
        ContextSourceKind.REFERENCE,
        ContextSourceKind.CUSTOM,
    ),
}


def validate_context_id(raw_id: str, label: str = "context identifier") -> str:
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise ValueError(f"{label} must be a non-empty string.")
    cleaned = raw_id.strip()
    if cleaned.startswith("_") or ".." in cleaned or not CONTEXT_ID_RE.match(cleaned):
        raise ValueError(
            f"Invalid {label} '{cleaned}': must be a stable public identifier."
        )
    return cleaned


def _normalize_tags(tags: Iterable[str] | None) -> tuple[str, ...]:
    if not tags:
        return ()
    if isinstance(tags, (str, bytes)):
        raise ValueError("Tags must be an iterable of strings, not a single string.")
    cleaned = {
        str(tag).strip().lower()
        for tag in tags
        if tag is not None and str(tag).strip()
    }
    return tuple(sorted(cleaned))


_WINDOWS_DRIVE_PROVENANCE_RE = re.compile(
    r"^(?:[A-Za-z0-9_.-]+:)?[A-Za-z]:(?:[\\/]|$)"
)


def normalize_context_provenance(
    provenance: str | None,
    fallback: str = "",
) -> str:
    raw = str(provenance).strip() if provenance is not None else ""
    if not raw:
        raw = str(fallback).strip() if fallback else ""
    if not raw:
        return ""
    if "\x00" in raw:
        raise ValueError("Context provenance cannot contain null bytes.")
    if _WINDOWS_DRIVE_PROVENANCE_RE.match(raw):
        raise ValueError(
            f"Context provenance '{raw}' must not contain an absolute drive path."
        )
    normalized = raw.replace("\\", "/")
    target_part = normalized.split(":", 1)[1] if ":" in normalized else normalized
    if normalized.startswith("/") or target_part.startswith("/"):
        raise ValueError(
            f"Context provenance '{raw}' must not be an absolute path."
        )
    segments = [seg for seg in target_part.split("/") if seg]
    if ".." in segments:
        raise ValueError(
            f"Context provenance '{raw}' must not contain '..' traversal segments."
        )
    return normalized


@dataclass(frozen=True)
class ContextFragment:
    id: str
    source_id: str
    kind: ContextSourceKind
    content: str
    priority: ContextPriority = ContextPriority.MEDIUM
    required: bool = False
    reason: str = ""
    path: str | None = None
    tags: tuple[str, ...] = ()
    provenance: str = ""

    def __post_init__(self):
        object.__setattr__(
            self, "id", validate_context_id(self.id, "ContextFragment.id")
        )
        object.__setattr__(
            self,
            "source_id",
            validate_context_id(self.source_id, "ContextFragment.source_id"),
        )
        object.__setattr__(self, "kind", ContextSourceKind.coerce(self.kind))
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("ContextFragment content must be a non-empty string.")
        object.__setattr__(self, "content", self.content.strip())
        object.__setattr__(self, "priority", ContextPriority.coerce(self.priority))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(
            self,
            "reason",
            str(self.reason).strip() if self.reason is not None else "",
        )
        if self.path is not None:
            object.__setattr__(self, "path", normalize_evidence_path(self.path, None))
        object.__setattr__(self, "tags", _normalize_tags(self.tags))
        object.__setattr__(
            self,
            "provenance",
            normalize_context_provenance(self.provenance, fallback=self.path or ""),
        )

    @property
    def chars(self) -> int:
        return len(self.content)


@dataclass(frozen=True)
class ContextSource:
    id: str
    kind: ContextSourceKind
    content: str
    path: str | None = None
    priority: ContextPriority | int = ContextPriority.MEDIUM
    required: bool = False
    tags: tuple[str, ...] = ()
    provenance: str = ""
    fragments: tuple[ContextFragment, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "id", validate_context_id(self.id, "ContextSource.id"))
        object.__setattr__(self, "kind", ContextSourceKind.coerce(self.kind))
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError(
                f"ContextSource '{self.id}' content must be a non-empty string."
            )
        object.__setattr__(self, "content", self.content.strip())
        if self.path is not None:
            object.__setattr__(self, "path", normalize_evidence_path(self.path, None))
        object.__setattr__(self, "priority", ContextPriority.coerce(self.priority))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "tags", _normalize_tags(self.tags))
        resolved_provenance = normalize_context_provenance(
            self.provenance,
            fallback=self.path or self.id,
        )
        object.__setattr__(self, "provenance", resolved_provenance)
        if self.fragments:
            normalized_frags: list[ContextFragment] = []
            for item in self.fragments:
                if not isinstance(item, ContextFragment):
                    raise ValueError(
                        "ContextSource fragments must be ContextFragment instances."
                    )
                if not item.provenance:
                    item = replace(item, provenance=resolved_provenance)
                normalized_frags.append(item)
            object.__setattr__(self, "fragments", tuple(normalized_frags))
        else:
            object.__setattr__(self, "fragments", ())

    def to_fragments(self) -> tuple[ContextFragment, ...]:
        if self.fragments:
            return tuple(
                item if item.provenance else replace(item, provenance=self.provenance)
                for item in self.fragments
            )
        return (
            ContextFragment(
                id=self.id,
                source_id=self.id,
                kind=self.kind,
                content=self.content,
                priority=self.priority,
                required=self.required,
                path=self.path,
                tags=self.tags,
                provenance=self.provenance,
            ),
        )


@dataclass(frozen=True)
class ContextRequest:
    objective: str = ""
    mode: ContextMode | str = ContextMode.GENERAL
    harness: str = "cursor"
    affected_paths: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    max_chars: int | None = None
    constraints: tuple[str, ...] = ()
    spec_id: str | None = None
    spec_revision: int | None = None

    def __post_init__(self):
        if self.objective is None:
            cleaned_objective = ""
        elif not isinstance(self.objective, str):
            raise ValueError("ContextRequest objective must be a string.")
        else:
            cleaned_objective = self.objective.strip()
        object.__setattr__(self, "objective", cleaned_objective)

        object.__setattr__(self, "mode", ContextMode.coerce(self.mode))

        if self.harness is None:
            cleaned_harness = "cursor"
        else:
            try:
                cleaned_harness = validate_harness_id(
                    self.harness,
                    "ContextRequest.harness",
                )
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
        object.__setattr__(self, "harness", cleaned_harness)

        if self.affected_paths is None:
            raw_paths: tuple[str, ...] = ()
        elif isinstance(self.affected_paths, (str, bytes)):
            raise ValueError(
                "ContextRequest affected_paths must be a sequence of path strings."
            )
        else:
            raw_paths = tuple(
                normalize_evidence_path(p, None)
                for p in self.affected_paths
                if p is not None and str(p).strip()
            )
        object.__setattr__(self, "affected_paths", tuple(sorted(set(raw_paths))))

        object.__setattr__(self, "tags", _normalize_tags(self.tags))

        if self.max_chars is not None:
            if (
                isinstance(self.max_chars, bool)
                or not isinstance(self.max_chars, int)
                or self.max_chars <= 0
            ):
                raise ValueError(
                    "ContextRequest max_chars must be a positive integer."
                )

        if self.constraints is None:
            cleaned_constraints: tuple[str, ...] = ()
        elif isinstance(self.constraints, (str, bytes)):
            raise ValueError("ContextRequest constraints must be a sequence of strings.")
        else:
            cleaned_constraints = tuple(
                dict.fromkeys(
                    str(item).strip()
                    for item in self.constraints
                    if item is not None and str(item).strip()
                )
            )
        object.__setattr__(self, "constraints", cleaned_constraints)

        if self.spec_id is not None:
            from rapid_os.domain.specs import validate_spec_id

            object.__setattr__(
                self,
                "spec_id",
                validate_spec_id(self.spec_id, "ContextRequest.spec_id"),
            )

        if self.spec_revision is not None:
            if (
                isinstance(self.spec_revision, bool)
                or not isinstance(self.spec_revision, int)
                or self.spec_revision <= 0
            ):
                raise ValueError(
                    "ContextRequest spec_revision must be a positive integer."
                )
            if self.spec_id is None:
                raise ValueError(
                    "ContextRequest spec_revision requires spec_id to be specified."
                )


@dataclass(frozen=True)
class ContextPolicy:
    max_chars: int = DEFAULT_MAX_CHARS
    required_kinds: tuple[ContextSourceKind, ...] = ()
    mode_required_kinds: Mapping[ContextMode, tuple[ContextSourceKind, ...]] = field(
        default_factory=lambda: dict(DEFAULT_MODE_REQUIRED_KINDS)
    )
    mode_preferred_kinds: Mapping[ContextMode, tuple[ContextSourceKind, ...]] = field(
        default_factory=lambda: dict(DEFAULT_MODE_PREFERRED_KINDS)
    )
    kind_priorities: Mapping[ContextSourceKind, ContextPriority] = field(
        default_factory=lambda: dict(DEFAULT_KIND_PRIORITIES)
    )
    precedence_order: tuple[ContextSourceKind, ...] = DEFAULT_PRECEDENCE_ORDER

    def __post_init__(self):
        if (
            isinstance(self.max_chars, bool)
            or not isinstance(self.max_chars, int)
            or self.max_chars <= 0
        ):
            raise ValueError("ContextPolicy max_chars must be a positive integer.")
        object.__setattr__(
            self,
            "required_kinds",
            tuple(ContextSourceKind.coerce(k) for k in self.required_kinds),
        )
        object.__setattr__(
            self,
            "precedence_order",
            tuple(ContextSourceKind.coerce(k) for k in self.precedence_order),
        )

    def precedence_rank(self, kind: ContextSourceKind) -> int:
        coerced = ContextSourceKind.coerce(kind)
        try:
            return self.precedence_order.index(coerced)
        except ValueError:
            return len(self.precedence_order)

    def priority_for_kind(self, kind: ContextSourceKind) -> ContextPriority:
        coerced = ContextSourceKind.coerce(kind)
        return self.kind_priorities.get(coerced, ContextPriority.MEDIUM)

    def is_kind_required(self, kind: ContextSourceKind, mode: ContextMode) -> bool:
        coerced_kind = ContextSourceKind.coerce(kind)
        coerced_mode = ContextMode.coerce(mode)
        if coerced_kind in self.required_kinds:
            return True
        mode_req = self.mode_required_kinds.get(coerced_mode, ())
        return coerced_kind in mode_req

    def preferred_kinds_for_mode(
        self, mode: ContextMode
    ) -> tuple[ContextSourceKind, ...]:
        coerced_mode = ContextMode.coerce(mode)
        return tuple(
            self.mode_preferred_kinds.get(
                coerced_mode,
                DEFAULT_MODE_PREFERRED_KINDS[ContextMode.GENERAL],
            )
        )


DEFAULT_CONTEXT_POLICY = ContextPolicy()


@dataclass(frozen=True)
class ContextConflict:
    key: str
    sources: tuple[str, ...]
    values: tuple[str, ...]
    winning_source: str | None = None
    resolution: str = ""

    def __post_init__(self):
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("ContextConflict key must be a non-empty string.")
        object.__setattr__(self, "key", self.key.strip())
        sources_tuple = tuple(
            validate_context_id(s, "ContextConflict.source") for s in self.sources
        )
        if len(sources_tuple) < 2:
            raise ValueError("ContextConflict must reference at least two sources.")
        object.__setattr__(self, "sources", sources_tuple)
        values_tuple = tuple(
            str(v).strip() for v in self.values if str(v).strip()
        )
        if len(values_tuple) < 2:
            raise ValueError("ContextConflict must contain at least two values.")
        object.__setattr__(self, "values", values_tuple)
        if self.winning_source is not None:
            object.__setattr__(
                self,
                "winning_source",
                validate_context_id(self.winning_source, "ContextConflict.winning_source"),
            )
        object.__setattr__(self, "resolution", str(self.resolution or "").strip())

    @property
    def category(self) -> str:
        return self.key

    @property
    def winner(self) -> str | None:
        return self.winning_source

    @property
    def reason(self) -> str:
        return self.resolution

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "key": self.key,
            "sources": list(self.sources),
            "values": list(self.values),
        }
        if self.winning_source is not None:
            payload["winning_source"] = self.winning_source
        if self.resolution:
            payload["resolution"] = self.resolution
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContextConflict":
        if not isinstance(payload, Mapping):
            raise ValueError("ContextConflict payload must be an object.")
        raw_sources = payload.get("sources")
        raw_values = payload.get("values")
        if not isinstance(raw_sources, list) or not isinstance(raw_values, list):
            raise ValueError("ContextConflict 'sources' and 'values' must be lists.")
        winning = payload.get("winning_source")
        return cls(
            key=str(payload.get("key", "")),
            sources=tuple(str(s) for s in raw_sources),
            values=tuple(str(v) for v in raw_values),
            winning_source=str(winning) if winning is not None else None,
            resolution=str(payload.get("resolution", "")),
        )


@dataclass(frozen=True)
class ManifestEntry:
    source_id: str
    kind: str
    selected: bool
    reason: str
    priority: int
    required: bool = False
    path: str | None = None
    chars: int = 0
    precedence: int = 0
    provenance: str = ""

    def __post_init__(self):
        object.__setattr__(
            self,
            "source_id",
            validate_context_id(self.source_id, "ManifestEntry.source_id"),
        )
        coerced_kind = ContextSourceKind.coerce(self.kind)
        object.__setattr__(self, "kind", coerced_kind.value)
        object.__setattr__(self, "selected", bool(self.selected))
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("ManifestEntry reason must be a non-empty string.")
        object.__setattr__(self, "reason", self.reason.strip())
        object.__setattr__(self, "priority", int(ContextPriority.coerce(self.priority)))
        object.__setattr__(self, "required", bool(self.required))
        if self.path is not None:
            object.__setattr__(self, "path", normalize_evidence_path(self.path, None))
        object.__setattr__(self, "chars", int(self.chars))
        object.__setattr__(self, "precedence", int(self.precedence))
        object.__setattr__(
            self,
            "provenance",
            normalize_context_provenance(self.provenance, fallback=self.path or ""),
        )

    @property
    def priority_label(self) -> str:
        return ContextPriority.coerce(self.priority).label

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "source_id": self.source_id,
            "kind": self.kind,
            "selected": self.selected,
            "reason": self.reason,
            "priority": self.priority,
            "required": self.required,
            "chars": self.chars,
            "precedence": self.precedence,
            "provenance": self.provenance,
        }
        if self.path is not None:
            payload["path"] = self.path
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ManifestEntry":
        if not isinstance(payload, Mapping):
            raise ValueError("ManifestEntry payload must be an object.")
        raw_path = payload.get("path")
        raw_prov = payload.get("provenance")
        return cls(
            source_id=str(payload.get("source_id") or payload.get("id") or ""),
            kind=str(payload.get("kind", "")),
            selected=bool(payload.get("selected", True)),
            reason=str(payload.get("reason", "")),
            priority=int(payload.get("priority", int(ContextPriority.MEDIUM))),  # type: ignore[arg-type]
            required=bool(payload.get("required", False)),
            path=str(raw_path) if raw_path is not None else None,
            chars=int(payload.get("chars", 0)),  # type: ignore[arg-type]
            precedence=int(payload.get("precedence", 0)),  # type: ignore[arg-type]
            provenance=str(raw_prov) if raw_prov is not None else "",
        )


@dataclass(frozen=True)
class ContextManifest:
    schema_version: int = CONTEXT_MANIFEST_SCHEMA_VERSION
    mode: str = ContextMode.GENERAL.value
    harness: str = "cursor"
    objective: str = ""
    max_chars: int = DEFAULT_MAX_CHARS
    compiled_chars: int = 0
    content_digest: str = ""
    selected: tuple[ManifestEntry, ...] = ()
    skipped: tuple[ManifestEntry, ...] = ()
    conflicts: tuple[ContextConflict, ...] = ()

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != CONTEXT_MANIFEST_SCHEMA_VERSION
        ):
            raise ValueError(
                f"Unsupported ContextManifest schema_version '{self.schema_version}': expected {CONTEXT_MANIFEST_SCHEMA_VERSION}."
            )
        coerced_mode = ContextMode.coerce(self.mode)
        object.__setattr__(self, "mode", coerced_mode.value)
        try:
            cleaned_harness = validate_harness_id(
                self.harness,
                "ContextManifest.harness",
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        object.__setattr__(self, "harness", cleaned_harness)
        object.__setattr__(self, "objective", str(self.objective or "").strip())
        if isinstance(self.max_chars, bool) or int(self.max_chars) <= 0:
            raise ValueError("ContextManifest max_chars must be a positive integer.")
        object.__setattr__(self, "max_chars", int(self.max_chars))
        object.__setattr__(self, "compiled_chars", int(self.compiled_chars))
        object.__setattr__(self, "content_digest", str(self.content_digest or "").strip())
        object.__setattr__(self, "selected", tuple(self.selected))
        object.__setattr__(self, "skipped", tuple(self.skipped))
        object.__setattr__(self, "conflicts", tuple(self.conflicts))

    @property
    def sources(self) -> tuple[ManifestEntry, ...]:
        return self.selected + self.skipped

    @property
    def budget_max_chars(self) -> int:
        return self.max_chars

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode,
            "harness": self.harness,
            "objective": self.objective,
            "max_chars": self.max_chars,
            "compiled_chars": self.compiled_chars,
            "content_digest": self.content_digest,
            "selected": [item.to_dict() for item in self.selected],
            "skipped": [item.to_dict() for item in self.skipped],
            "conflicts": [item.to_dict() for item in self.conflicts],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ContextManifest":
        if not isinstance(payload, Mapping):
            raise ValueError("ContextManifest payload must be a JSON object.")
        raw_selected = payload.get("selected", [])
        raw_skipped = payload.get("skipped", [])
        raw_conflicts = payload.get("conflicts", [])
        if (
            not isinstance(raw_selected, list)
            or not isinstance(raw_skipped, list)
            or not isinstance(raw_conflicts, list)
        ):
            raise ValueError(
                "ContextManifest 'selected', 'skipped', and 'conflicts' must be lists."
            )
        return cls(
            schema_version=payload.get("schema_version"),  # type: ignore[arg-type]
            mode=str(payload.get("mode", ContextMode.GENERAL.value)),
            harness=str(payload.get("harness", "cursor")),
            objective=str(payload.get("objective", "")),
            max_chars=int(payload.get("max_chars", DEFAULT_MAX_CHARS)),  # type: ignore[arg-type]
            compiled_chars=int(payload.get("compiled_chars", 0)),  # type: ignore[arg-type]
            content_digest=str(payload.get("content_digest", "")),
            selected=tuple(ManifestEntry.from_dict(item) for item in raw_selected),
            skipped=tuple(ManifestEntry.from_dict(item) for item in raw_skipped),
            conflicts=tuple(ContextConflict.from_dict(item) for item in raw_conflicts),
        )

    @classmethod
    def from_json(cls, raw_json: str) -> "ContextManifest":
        return cls.from_dict(json.loads(raw_json))


@dataclass(frozen=True)
class ContextSelection:
    request: ContextRequest
    effective_max_chars: int
    selected_fragments: tuple[ContextFragment, ...]
    skipped_entries: tuple[ManifestEntry, ...]
    conflicts: tuple[ContextConflict, ...]
    missing_required_kinds: tuple[ContextSourceKind, ...] = ()

    @property
    def skipped(self) -> tuple[ManifestEntry, ...]:
        return self.skipped_entries


@dataclass(frozen=True)
class CompiledContext:
    schema_version: int = CONTEXT_MANIFEST_SCHEMA_VERSION
    content: str = ""
    manifest: ContextManifest = field(default_factory=ContextManifest)

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != CONTEXT_MANIFEST_SCHEMA_VERSION
        ):
            raise ValueError(
                f"Unsupported CompiledContext schema_version '{self.schema_version}': expected {CONTEXT_MANIFEST_SCHEMA_VERSION}."
            )
        if not isinstance(self.content, str):
            raise ValueError("CompiledContext content must be a string.")
        if not isinstance(self.manifest, ContextManifest):
            raise ValueError("CompiledContext manifest must be a ContextManifest.")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "content": self.content,
            "manifest": self.manifest.to_dict(),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "CompiledContext":
        if not isinstance(payload, Mapping):
            raise ValueError("CompiledContext payload must be a JSON object.")
        raw_manifest = payload.get("manifest")
        if not isinstance(raw_manifest, Mapping):
            raise ValueError("CompiledContext 'manifest' must be an object.")
        return cls(
            schema_version=payload.get("schema_version"),  # type: ignore[arg-type]
            content=str(payload.get("content", "")),
            manifest=ContextManifest.from_dict(raw_manifest),
        )

    @classmethod
    def from_json(cls, raw_json: str) -> "CompiledContext":
        return cls.from_dict(json.loads(raw_json))


PROJECT_FACT_CATEGORY_TITLES = {
    "language": "Languages",
    "framework": "Frameworks",
    "package_manager": "Package Managers",
    "database": "Database",
    "testing": "Testing",
    "monorepo": "Monorepo",
    "docker": "Docker",
    "deploy_provider": "Deployment",
}

PROJECT_FACT_CATEGORY_TAGS = {
    "language": {"backend", "frontend", "code", "language"},
    "framework": {"backend", "frontend", "api", "web", "framework"},
    "package_manager": {"dependencies", "build", "package"},
    "database": {"database", "db", "sql", "storage", "backend", "data"},
    "testing": {"testing", "tests", "qa", "verification"},
    "monorepo": {"monorepo", "workspace", "architecture"},
    "docker": {"docker", "container", "deployment", "infra"},
    "deploy_provider": {"deployment", "deploy", "ci", "infra"},
}


def select_relevant_project_facts(
    project_model: ProjectModel,
    request: ContextRequest | None = None,
) -> tuple[ProjectFact, ...]:
    """Filter `ProjectModel` facts to those relevant for `request` without dumping raw evidence."""
    if not project_model.facts:
        return ()

    if request is None:
        return project_model.facts

    mode = request.mode
    req_tags = set(request.tags)
    objective_lower = request.objective.lower()

    if req_tags:
        matched_categories = {
            category
            for category, cat_tags in PROJECT_FACT_CATEGORY_TAGS.items()
            if req_tags & cat_tags or category in req_tags
        }
        # Always include core language/framework/testing context alongside tagged categories
        allowed_categories = matched_categories | {"language", "framework", "testing"}
    elif mode == ContextMode.BUGFIX:
        allowed_categories = {
            "language",
            "framework",
            "database",
            "testing",
            "monorepo",
        }
        if any(word in objective_lower for word in ("deploy", "docker", "ci", "build")):
            allowed_categories |= {"docker", "deploy_provider", "package_manager"}
    elif mode == ContextMode.HARDENING:
        allowed_categories = {
            "language",
            "framework",
            "database",
            "testing",
            "docker",
            "deploy_provider",
        }
    elif mode == ContextMode.REFACTOR:
        allowed_categories = {
            "language",
            "framework",
            "database",
            "testing",
            "monorepo",
            "package_manager",
        }
    else:
        allowed_categories = set(FACT_CATEGORIES)

    selected = tuple(
        fact
        for fact in project_model.facts
        if fact.category in allowed_categories
    )
    return selected if selected else project_model.facts


def format_compact_project_intelligence(
    project_model: ProjectModel,
    request: ContextRequest | None = None,
) -> str:
    """Render a compact, agent-optimized summary of relevant `ProjectFact` items."""
    selected_facts = select_relevant_project_facts(project_model, request)
    if not selected_facts:
        return ""

    blocks: list[str] = []
    rendered_categories: set[str] = set()

    for category in FACT_CATEGORIES:
        cat_facts = [fact for fact in selected_facts if fact.category == category]
        if not cat_facts:
            continue
        rendered_categories.add(category)
        title = PROJECT_FACT_CATEGORY_TITLES.get(
            category, category.replace("_", " ").title()
        )
        lines = [f"{title}:"]
        for fact in cat_facts:
            lines.append(f"- {fact.value}")
        blocks.append("\n".join(lines))

    for fact in selected_facts:
        if fact.category in rendered_categories:
            continue
        rendered_categories.add(fact.category)
        cat_facts = [item for item in selected_facts if item.category == fact.category]
        title = fact.category.replace("_", " ").title()
        lines = [f"{title}:"]
        for item in cat_facts:
            lines.append(f"- {item.value}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def build_project_intelligence_source(
    project_model: ProjectModel,
    request: ContextRequest | None = None,
    *,
    priority: ContextPriority = ContextPriority.MEDIUM,
    required: bool = False,
    provenance: str = "scan:live",
) -> ContextSource | None:
    """Create a native `ContextSource` from a `ProjectModel` if relevant facts exist."""
    compact_text = format_compact_project_intelligence(project_model, request)
    if not compact_text:
        return None

    fact_tags: set[str] = {"project-intelligence"}
    for fact in select_relevant_project_facts(project_model, request):
        fact_tags.add(fact.category)
        fact_tags.add(fact.value)
        fact_tags.update(PROJECT_FACT_CATEGORY_TAGS.get(fact.category, ()))

    return ContextSource(
        id="project.intelligence",
        kind=ContextSourceKind.PROJECT_INTELLIGENCE,
        content=compact_text,
        path=None,
        priority=priority,
        required=required,
        tags=tuple(sorted(fact_tags)),
        provenance=provenance,
    )


def build_task_constraints_source(
    request: ContextRequest | None,
) -> ContextSource | None:
    """Create a canonical first-class `ContextSource` from `ContextRequest.constraints`."""
    if request is None or not request.constraints:
        return None

    content = "\n".join(f"- {item}" for item in request.constraints)
    return ContextSource(
        id="task.constraints",
        kind=ContextSourceKind.TASK_CONSTRAINTS,
        content=content,
        path=None,
        priority=ContextPriority.CRITICAL,
        required=True,
        tags=request.tags,
        provenance="ContextRequest.constraints",
    )


_DATABASE_TOKEN_MAP = (
    ("postgres", re.compile(r"\b(?:postgres|postgresql)\b", re.IGNORECASE)),
    ("mysql", re.compile(r"\b(?:mysql|mariadb)\b", re.IGNORECASE)),
    ("mongodb", re.compile(r"\b(?:mongodb|mongo)\b", re.IGNORECASE)),
    ("sqlite", re.compile(r"\bsqlite\b", re.IGNORECASE)),
)

_TOPOLOGY_TOKEN_MAP = (
    (
        "front-end-only",
        re.compile(
            r"(?:\bfront-end-only\b|\bfrontend only\b|\bbackend:\s*none\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "fullstack-separated",
        re.compile(
            r"(?:\bfullstack-separated\b|\bfullstack separated\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "fullstack-baas",
        re.compile(
            r"(?:\bfullstack-baas\b|\bfullstack baas\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "doc-site",
        re.compile(
            r"(?:\bdoc-site\b|\bmodern docs\b)",
            re.IGNORECASE,
        ),
    ),
)


def _extract_exclusive_claims(content: str, token_map) -> tuple[str, ...]:
    found: list[str] = []
    for canonical_value, pattern in token_map:
        if pattern.search(content):
            found.append(canonical_value)
    return tuple(found)


def detect_context_conflicts(
    sources: Sequence[ContextFragment | ContextSource],
    project_model: ProjectModel | None = None,
    policy: ContextPolicy = DEFAULT_CONTEXT_POLICY,
) -> tuple[ContextConflict, ...]:
    """Detect structural conflicts across effectively selected fragments/sources and ProjectModel facts."""
    grouped_by_source: dict[str, tuple[ContextSourceKind, list[str]]] = {}
    for item in sources:
        source_id = getattr(item, "source_id", item.id)
        kind = ContextSourceKind.coerce(item.kind)
        if source_id not in grouped_by_source:
            grouped_by_source[source_id] = (kind, [item.content])
        else:
            grouped_by_source[source_id][1].append(item.content)

    ordered_sources: list[tuple[str, ContextSourceKind, str]] = [
        (source_id, kind, "\n".join(chunks))
        for source_id, (kind, chunks) in grouped_by_source.items()
    ]
    ordered_sources.sort(
        key=lambda entry: (policy.precedence_rank(entry[1]), entry[0])
    )

    conflicts: list[ContextConflict] = []

    # 1. Database conflicts across structured rules and ProjectModel
    db_claims: list[tuple[str, str, int]] = []
    for source_id, kind, content in ordered_sources:
        if kind not in {
            ContextSourceKind.TASK_CONSTRAINTS,
            ContextSourceKind.SECURITY,
            ContextSourceKind.BUSINESS,
            ContextSourceKind.ARCHITECTURE,
            ContextSourceKind.TOPOLOGY,
            ContextSourceKind.TECH_STACK,
            ContextSourceKind.PROJECT_INTELLIGENCE,
        }:
            continue
        matched_dbs = _extract_exclusive_claims(content, _DATABASE_TOKEN_MAP)
        if len(matched_dbs) == 1:
            db_claims.append(
                (source_id, matched_dbs[0], policy.precedence_rank(kind))
            )

    if project_model is not None and not any(
        src_id == "project.intelligence" for src_id, _, _ in db_claims
    ):
        model_dbs = [
            db
            for db in project_model.values("database")
            if db in {"postgres", "mysql", "mongodb", "sqlite"}
        ]
        if len(model_dbs) == 1:
            db_claims.append(
                (
                    "project.intelligence",
                    model_dbs[0],
                    policy.precedence_rank(ContextSourceKind.PROJECT_INTELLIGENCE),
                )
            )

    db_claims.sort(key=lambda item: (item[2], item[0]))

    distinct_db_values = []
    for _, value, _ in db_claims:
        if value not in distinct_db_values:
            distinct_db_values.append(value)

    if len(distinct_db_values) > 1:
        winning_source = db_claims[0][0]
        conflicts.append(
            ContextConflict(
                key="database",
                sources=tuple(item[0] for item in db_claims),
                values=tuple(distinct_db_values),
                winning_source=winning_source,
                resolution=(
                    f"Source '{winning_source}' takes precedence by policy "
                    "(user-declared rules override lower-precedence sources and detected facts)."
                ),
            )
        )

    # 2. Topology conflicts across structured rules
    topo_claims: list[tuple[str, str, int]] = []
    for source_id, kind, content in ordered_sources:
        if kind not in {
            ContextSourceKind.TASK_CONSTRAINTS,
            ContextSourceKind.BUSINESS,
            ContextSourceKind.ARCHITECTURE,
            ContextSourceKind.TOPOLOGY,
            ContextSourceKind.TECH_STACK,
        }:
            continue
        matched_topos = _extract_exclusive_claims(content, _TOPOLOGY_TOKEN_MAP)
        if len(matched_topos) == 1:
            topo_claims.append(
                (source_id, matched_topos[0], policy.precedence_rank(kind))
            )

    topo_claims.sort(key=lambda item: (item[2], item[0]))

    distinct_topo_values = []
    for _, value, _ in topo_claims:
        if value not in distinct_topo_values:
            distinct_topo_values.append(value)

    if len(distinct_topo_values) > 1:
        winning_source = topo_claims[0][0]
        conflicts.append(
            ContextConflict(
                key="topology",
                sources=tuple(item[0] for item in topo_claims),
                values=tuple(distinct_topo_values),
                winning_source=winning_source,
                resolution=f"Source '{winning_source}' takes precedence by policy.",
            )
        )

    return tuple(conflicts)


SECTION_TITLES_BY_KIND: Mapping[ContextSourceKind, str] = {
    ContextSourceKind.TASK_CONSTRAINTS: "Task Constraints",
    ContextSourceKind.SECURITY: "Security Rules",
    ContextSourceKind.BUSINESS: "Business Rules",
    ContextSourceKind.ARCHITECTURE: "Architecture",
    ContextSourceKind.TOPOLOGY: "Topology",
    ContextSourceKind.TECH_STACK: "Technical Stack",
    ContextSourceKind.CODING_RULES: "Coding Rules",
    ContextSourceKind.SPEC: "Task Specifications",
    ContextSourceKind.TASKS: "Implementation Tasks",
    ContextSourceKind.ACCEPTANCE: "Acceptance Criteria",
    ContextSourceKind.DESIGN: "Design Standards",
    ContextSourceKind.REFERENCE: "Visual & Reference Context",
    ContextSourceKind.CUSTOM: "Additional Context",
    ContextSourceKind.PROJECT_INTELLIGENCE: "Project Intelligence",
}


def render_compiled_markdown(
    request: ContextRequest,
    fragments: Sequence[ContextFragment],
    policy: ContextPolicy = DEFAULT_CONTEXT_POLICY,
) -> str:
    """Render selected `ContextFragment` items in deterministic precedence order."""
    lines: list[str] = [
        "# Rapid OS Compiled Context",
        "",
        "## Task",
        "",
        f"Mode: {request.mode.value}",
        f"Harness: {request.harness}",
    ]
    if request.objective:
        lines.append(f"Objective: {request.objective}")
    if request.affected_paths:
        lines.append(f"Affected Paths: {', '.join(request.affected_paths)}")
    if request.tags:
        lines.append(f"Tags: {', '.join(request.tags)}")

    ordered_fragments = sorted(
        fragments,
        key=lambda frag: (
            policy.precedence_rank(frag.kind),
            -int(frag.priority),
            frag.source_id,
            frag.id,
        ),
    )

    grouped_by_kind: dict[ContextSourceKind, list[ContextFragment]] = {}
    for frag in ordered_fragments:
        grouped_by_kind.setdefault(frag.kind, []).append(frag)

    rendered_kinds: set[ContextSourceKind] = set()
    for kind in list(policy.precedence_order) + list(ContextSourceKind):
        if kind in rendered_kinds or kind not in grouped_by_kind:
            continue
        rendered_kinds.add(kind)
        heading = SECTION_TITLES_BY_KIND.get(
            kind, kind.value.replace("_", " ").title()
        )
        lines.append("")
        lines.append(f"## {heading}")
        for frag in grouped_by_kind[kind]:
            lines.append("")
            lines.append(frag.content)

    return "\n".join(lines).strip() + "\n"


def _evaluate_fragment_relevance(
    fragment: ContextFragment,
    request: ContextRequest,
    project_model: ProjectModel | None,
    policy: ContextPolicy,
) -> tuple[bool, int, str]:
    """Return `(is_relevant, relevance_score, reason)` deterministically."""
    mode = request.mode
    req_tags = set(request.tags)
    frag_tags = set(fragment.tags)
    preferred_kinds = policy.preferred_kinds_for_mode(mode)

    is_required = fragment.required or policy.is_kind_required(fragment.kind, mode)
    reasons: list[str] = []
    score = 0

    if is_required:
        score += 1000
        if fragment.required:
            reasons.append(f"required {fragment.kind.value} source")
        else:
            reasons.append(f"required for {mode.value} mode by policy")

    if fragment.kind in preferred_kinds:
        rank_bonus = max(10, 100 - (preferred_kinds.index(fragment.kind) * 5))
        score += rank_bonus
        if not is_required:
            reasons.append(f"relevant to {mode.value} mode")

    if request.spec_id and fragment.source_id.startswith(f"spec.{request.spec_id}."):
        score += 90
        reasons.append(f"selected spec '{request.spec_id}'")

    matched_tags = sorted(req_tags & frag_tags)
    if matched_tags:
        score += 50 * len(matched_tags)
        reasons.append(f"matches request tags ({', '.join(matched_tags)})")

    if request.affected_paths and fragment.path:
        if fragment.path in request.affected_paths:
            score += 80
            reasons.append(f"matches affected path ({fragment.path})")

    if request.affected_paths:
        # Boost backend/architecture/testing rules when domain/core/adapter paths are affected
        affected_str = " ".join(request.affected_paths).lower()
        if "test" in affected_str and "testing" in frag_tags:
            score += 30
            reasons.append("matches affected test paths")
        elif (
            any(part in affected_str for part in ("domain/", "core/", "adapters/"))
            and fragment.kind
            in {
                ContextSourceKind.ARCHITECTURE,
                ContextSourceKind.CODING_RULES,
                ContextSourceKind.SECURITY,
            }
        ):
            score += 25
            reasons.append("matches affected backend/domain paths")

    if (
        fragment.kind == ContextSourceKind.PROJECT_INTELLIGENCE
        and project_model is not None
        and project_model.facts
    ):
        fact_Preview = ", ".join(
            f"{f.category}={f.value}"
            for f in select_relevant_project_facts(project_model, request)[:3]
        )
        if fact_Preview:
            reasons.append(f"selected ProjectModel facts ({fact_Preview})")

    is_relevant = is_required or score > 0
    if not is_relevant:
        return False, 0, f"skipped: not relevant for {mode.value} mode"

    combined_reason = "; ".join(reasons) if reasons else f"selected for {mode.value} mode"
    return True, score, combined_reason


class ContextResolver:
    """Harness-neutral, deterministic resolver that selects context fragments within budget.

    `ContextResolver.resolve()` returns `ContextSelection` (including `missing_required_kinds`)
    for low-level inspection; operational failure on missing required sources is enforced by
    `ContextCompiler.compile()`.
    """

    def __init__(self, policy: ContextPolicy = DEFAULT_CONTEXT_POLICY):
        self.policy = policy

    def resolve(
        self,
        request: ContextRequest,
        sources: Sequence[ContextSource],
        project_model: ProjectModel | None = None,
        policy: ContextPolicy | None = None,
    ) -> ContextSelection:
        policy = policy or self.policy
        effective_max_chars = (
            request.max_chars if request.max_chars is not None else policy.max_chars
        )

        all_sources: list[ContextSource] = list(sources)

        has_explicit_task_constraints = any(
            src.id == "task.constraints"
            or src.kind == ContextSourceKind.TASK_CONSTRAINTS
            for src in all_sources
        )
        if request.constraints and not has_explicit_task_constraints:
            tc_source = build_task_constraints_source(request)
            if tc_source is not None:
                all_sources.append(tc_source)

        has_explicit_pi_source = any(
            src.id == "project.intelligence"
            or src.kind == ContextSourceKind.PROJECT_INTELLIGENCE
            for src in all_sources
        )
        if project_model is not None and not has_explicit_pi_source:
            pi_source = build_project_intelligence_source(
                project_model,
                request,
                priority=policy.priority_for_kind(
                    ContextSourceKind.PROJECT_INTELLIGENCE
                ),
                required=policy.is_kind_required(
                    ContextSourceKind.PROJECT_INTELLIGENCE, request.mode
                ),
                provenance="scan:live",
            )
            if pi_source is not None:
                all_sources.append(pi_source)

        seen_source_ids: set[str] = set()
        for src in all_sources:
            if not isinstance(src, ContextSource):
                raise ValueError("All context sources must be ContextSource instances.")
            if src.id in seen_source_ids:
                raise ValueError(
                    f"Duplicate ContextSource id '{src.id}': source IDs must be unique."
                )
            seen_source_ids.add(src.id)

        # Sort sources deterministically so input order never affects output
        canonical_sources = sorted(
            all_sources,
            key=lambda src: (
                policy.precedence_rank(src.kind),
                -int(src.priority),
                src.id,
            ),
        )

        required_candidates: list[tuple[ContextFragment, int, str]] = []
        optional_candidates: list[tuple[ContextFragment, int, str]] = []
        skipped_entries: list[ManifestEntry] = []

        seen_fragment_ids: set[str] = set()
        for src in canonical_sources:
            for raw_frag in src.to_fragments():
                if raw_frag.id in seen_fragment_ids:
                    raise ValueError(
                        f"Duplicate ContextFragment id '{raw_frag.id}'."
                    )
                seen_fragment_ids.add(raw_frag.id)

                effective_priority = ContextPriority.coerce(
                    max(
                        int(raw_frag.priority),
                        int(policy.priority_for_kind(raw_frag.kind)),
                    )
                    if raw_frag.priority == ContextPriority.MEDIUM
                    else int(raw_frag.priority)
                )
                is_req = raw_frag.required or policy.is_kind_required(
                    raw_frag.kind, request.mode
                )
                is_relevant, relevance_score, reason = _evaluate_fragment_relevance(
                    raw_frag, request, project_model, policy
                )
                effective_provenance = raw_frag.provenance or src.provenance
                normalized_frag = ContextFragment(
                    id=raw_frag.id,
                    source_id=raw_frag.source_id,
                    kind=raw_frag.kind,
                    content=raw_frag.content,
                    priority=effective_priority,
                    required=is_req,
                    reason=raw_frag.reason or reason,
                    path=raw_frag.path,
                    tags=raw_frag.tags,
                    provenance=effective_provenance,
                )

                if not is_relevant:
                    skipped_entries.append(
                        ManifestEntry(
                            source_id=normalized_frag.source_id,
                            kind=normalized_frag.kind.value,
                            selected=False,
                            reason=reason,
                            priority=int(normalized_frag.priority),
                            required=False,
                            path=normalized_frag.path,
                            chars=len(normalized_frag.content),
                            precedence=policy.precedence_rank(normalized_frag.kind),
                            provenance=normalized_frag.provenance,
                        )
                    )
                elif is_req:
                    required_candidates.append(
                        (normalized_frag, relevance_score, normalized_frag.reason)
                    )
                else:
                    optional_candidates.append(
                        (normalized_frag, relevance_score, normalized_frag.reason)
                    )

        # Deterministic ordering of required fragments
        required_candidates.sort(
            key=lambda item: (
                policy.precedence_rank(item[0].kind),
                -int(item[0].priority),
                -item[1],
                item[0].source_id,
                item[0].id,
            )
        )
        selected_fragments: list[ContextFragment] = [
            item[0] for item in required_candidates
        ]

        # Verify required fragments fit within budget (or empty base fits within budget)
        required_rendered = render_compiled_markdown(
            request, selected_fragments, policy
        )
        if len(required_rendered) > effective_max_chars:
            # Covers both required fragments over budget and a budget too small for the document itself:
            # nothing is ever truncated silently.
            raise ContextBudgetExceededError(
                f"Required context ({len(required_rendered)} chars) exceeds max_chars budget ({effective_max_chars}).",
                max_chars=effective_max_chars,
                required_chars=len(required_rendered),
                required_sources=tuple(frag.source_id for frag in selected_fragments),
            )

        # Deterministic ranking for optional fragments:
        # priority desc -> relevance score desc -> precedence asc -> source_id asc -> fragment_id asc
        optional_candidates.sort(
            key=lambda item: (
                -int(item[0].priority),
                -item[1],
                policy.precedence_rank(item[0].kind),
                item[0].source_id,
                item[0].id,
            )
        )

        for frag, _score, _reason in optional_candidates:
            trial_fragments = selected_fragments + [frag]
            trial_rendered = render_compiled_markdown(request, trial_fragments, policy)
            if len(trial_rendered) <= effective_max_chars:
                selected_fragments.append(frag)
            else:
                skipped_entries.append(
                    ManifestEntry(
                        source_id=frag.source_id,
                        kind=frag.kind.value,
                        selected=False,
                        reason="skipped: source exceeds remaining budget",
                        priority=int(frag.priority),
                        required=False,
                        path=frag.path,
                        chars=len(frag.content),
                        precedence=policy.precedence_rank(frag.kind),
                        provenance=frag.provenance,
                    )
                )

        # Final deterministic ordering of selected fragments by precedence
        selected_fragments.sort(
            key=lambda frag: (
                policy.precedence_rank(frag.kind),
                -int(frag.priority),
                frag.source_id,
                frag.id,
            )
        )

        present_kinds = {frag.kind for frag in selected_fragments}
        missing_required: list[ContextSourceKind] = []
        for kind in list(policy.precedence_order) + list(ContextSourceKind):
            if (
                kind not in missing_required
                and policy.is_kind_required(kind, request.mode)
                and kind not in present_kinds
            ):
                missing_required.append(kind)
                skipped_entries.append(
                    ManifestEntry(
                        source_id=f"missing.{kind.value}",
                        kind=kind.value,
                        selected=False,
                        reason=f"skipped: required {kind.value} source missing",
                        priority=int(policy.priority_for_kind(kind)),
                        required=True,
                        path=None,
                        chars=0,
                        precedence=policy.precedence_rank(kind),
                        provenance="",
                    )
                )

        # Deterministic ordering of skipped entries
        skipped_entries.sort(
            key=lambda entry: (
                entry.precedence,
                -entry.priority,
                entry.source_id,
            )
        )

        pi_was_skipped = any(
            entry.source_id == "project.intelligence"
            or entry.kind == ContextSourceKind.PROJECT_INTELLIGENCE.value
            for entry in skipped_entries
        )
        effective_project_model = None if pi_was_skipped else project_model

        conflicts = detect_context_conflicts(
            selected_fragments,
            project_model=effective_project_model,
            policy=policy,
        )

        return ContextSelection(
            request=request,
            effective_max_chars=effective_max_chars,
            selected_fragments=tuple(selected_fragments),
            skipped_entries=tuple(skipped_entries),
            conflicts=conflicts,
            missing_required_kinds=tuple(missing_required),
        )


class ContextCompiler:
    """Deterministic Context Compiler producing `CompiledContext` and `ContextManifest`."""

    def __init__(
        self,
        resolver: ContextResolver | None = None,
        policy: ContextPolicy = DEFAULT_CONTEXT_POLICY,
    ):
        self.policy = policy
        self.resolver = resolver or ContextResolver(policy=policy)

    def compile(
        self,
        request: ContextRequest,
        sources: Sequence[ContextSource] = (),
        project_model: ProjectModel | None = None,
        policy: ContextPolicy | None = None,
    ) -> CompiledContext:
        policy = policy or self.policy
        selection = self.resolver.resolve(
            request=request,
            sources=sources,
            project_model=project_model,
            policy=policy,
        )
        compiled_text = render_compiled_markdown(
            request=selection.request,
            fragments=selection.selected_fragments,
            policy=policy,
        )
        digest = hashlib.sha256(compiled_text.encode("utf-8")).hexdigest()

        selected_entries = tuple(
            ManifestEntry(
                source_id=frag.source_id,
                kind=frag.kind.value,
                selected=True,
                reason=frag.reason,
                priority=int(frag.priority),
                required=frag.required,
                path=frag.path,
                chars=len(frag.content),
                precedence=policy.precedence_rank(frag.kind),
                provenance=frag.provenance,
            )
            for frag in selection.selected_fragments
        )

        manifest = ContextManifest(
            schema_version=CONTEXT_MANIFEST_SCHEMA_VERSION,
            mode=selection.request.mode.value,
            harness=selection.request.harness,
            objective=selection.request.objective,
            max_chars=selection.effective_max_chars,
            compiled_chars=len(compiled_text),
            content_digest=digest,
            selected=selected_entries,
            skipped=selection.skipped_entries,
            conflicts=selection.conflicts,
        )

        missing_kinds_tuple = tuple(
            kind.value for kind in selection.missing_required_kinds
        )
        missing_ids_tuple = tuple(
            entry.source_id for entry in selection.skipped_entries if entry.required
        )
        if missing_kinds_tuple or missing_ids_tuple:
            missing_desc = ", ".join(missing_kinds_tuple or missing_ids_tuple)
            raise ContextRequiredSourceMissingError(
                f"Required context source missing for mode '{selection.request.mode.value}': {missing_desc}.",
                missing_kinds=missing_kinds_tuple,
                missing_source_ids=missing_ids_tuple,
                manifest=manifest,
            )

        return CompiledContext(
            schema_version=CONTEXT_MANIFEST_SCHEMA_VERSION,
            content=compiled_text,
            manifest=manifest,
        )


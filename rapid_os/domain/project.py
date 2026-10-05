import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping


PROJECT_MODEL_SCHEMA_VERSION = 1

FACT_CATEGORIES = (
    "language",
    "framework",
    "package_manager",
    "docker",
    "testing",
    "monorepo",
    "database",
    "deploy_provider",
)

CATEGORY_ORDER_INDEX = {
    category: index for index, category in enumerate(FACT_CATEGORIES)
}

DETECTOR_NAMESPACE_BY_CATEGORY = {
    "language": "language",
    "framework": "framework",
    "package_manager": "package_manager",
    "docker": "docker",
    "testing": "testing",
    "monorepo": "monorepo",
    "database": "database",
    "deploy_provider": "deploy",
}

WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
DETECTOR_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        if self is Confidence.HIGH:
            return 2
        if self is Confidence.MEDIUM:
            return 1
        return 0

    @classmethod
    def coerce(cls, value: object) -> "Confidence":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise ValueError(
            f"Invalid confidence '{value}': expected one of 'high', 'medium', 'low'."
        )


class SourceType(str, Enum):
    FILE = "file"
    MANIFEST = "manifest"
    CONFIG = "config"
    DIRECTORY = "directory"
    ENVIRONMENT_KEY = "environment-key"
    DEPENDENCY = "dependency"
    WORKFLOW = "workflow"

    @classmethod
    def coerce(cls, value: object) -> "SourceType":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise ValueError(
            f"Invalid source_type '{value}': expected one of {[m.value for m in cls]}."
        )


def canonical_detector_id(category: str, value: str) -> str:
    """Return a stable conceptual detector ID for `(category, value)`."""
    cleaned_category = (category or "").strip()
    cleaned_value = (value or "").strip()
    namespace = DETECTOR_NAMESPACE_BY_CATEGORY.get(
        cleaned_category,
        cleaned_category,
    )
    if not namespace or not cleaned_value:
        raise ValueError("Cannot build detector ID from empty category or value.")
    return f"{namespace}.{cleaned_value}"


def _posix_relpath_if_under(path_str: str, root_str: str) -> str | None:
    """Compute a POSIX relative path when `path_str` is inside `root_str` using normalized slashes."""
    norm_path = path_str.replace("\\", "/").rstrip("/")
    norm_root = root_str.replace("\\", "/").rstrip("/")
    if not norm_root:
        return None
    if norm_path == norm_root:
        return "."
    prefix = norm_root + "/"
    if norm_path.startswith(prefix):
        return norm_path[len(prefix) :]
    if os_case_insensitive := (
        WINDOWS_DRIVE_RE.match(norm_path) and WINDOWS_DRIVE_RE.match(norm_root)
    ):
        if norm_path.lower() == norm_root.lower():
            return "."
        if norm_path.lower().startswith(prefix.lower()):
            return norm_path[len(prefix) :]
    return None


def normalize_evidence_path(path: Path | str, root: Path | None = None) -> str:
    """Normalize an evidence path to a portable, repository-relative POSIX path string."""
    if path is None:
        raise ValueError("Evidence path cannot be None.")

    raw_str = str(path).strip()
    if not raw_str:
        raise ValueError("Evidence path cannot be empty.")
    if "\x00" in raw_str:
        raise ValueError("Evidence path cannot contain null bytes.")

    candidate_str = raw_str
    if root is not None:
        root_path = Path(root)
        matched = _posix_relpath_if_under(raw_str, str(root_path))
        if matched is not None:
            candidate_str = matched
        else:
            try:
                candidate_str = Path(path).relative_to(root_path).as_posix()
            except ValueError:
                try:
                    candidate_str = (
                        Path(path).resolve().relative_to(root_path.resolve()).as_posix()
                    )
                except (ValueError, OSError):
                    candidate_str = raw_str

    posix_str = candidate_str.replace("\\", "/").strip()
    while posix_str.startswith("./"):
        posix_str = posix_str[2:]

    if not posix_str or posix_str == ".":
        return "."

    if (
        posix_str.startswith("/")
        or WINDOWS_DRIVE_RE.match(posix_str)
        or Path(candidate_str).is_absolute()
    ):
        raise ValueError(
            f"Evidence path '{raw_str}' must be relative to the project root."
        )

    parts = [part for part in PurePosixPath(posix_str).parts if part not in {"", "."}]
    if not parts:
        return "."
    if any(part == ".." for part in parts):
        raise ValueError(
            f"Evidence path '{raw_str}' cannot escape the project root with '..'."
        )

    return "/".join(parts)


@dataclass(frozen=True)
class Evidence:
    path: Path
    reason: str
    source_type: SourceType = SourceType.FILE
    detector: str | None = None

    def __post_init__(self):
        if self.path is None or not str(self.path).strip():
            raise ValueError("Evidence path cannot be empty.")
        if "\x00" in str(self.path):
            raise ValueError("Evidence path cannot contain null bytes.")
        object.__setattr__(self, "path", Path(str(self.path).strip()))

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("Evidence reason must be a non-empty string.")
        object.__setattr__(self, "reason", self.reason.strip())

        object.__setattr__(self, "source_type", SourceType.coerce(self.source_type))

        if self.detector is not None:
            if not isinstance(self.detector, str) or not self.detector.strip():
                raise ValueError("Evidence detector must be a non-empty string when provided.")
            cleaned_detector = self.detector.strip()
            if cleaned_detector.startswith("_") or not DETECTOR_ID_RE.match(cleaned_detector):
                raise ValueError(f"Invalid detector identifier '{cleaned_detector}'.")
            object.__setattr__(self, "detector", cleaned_detector)

    def portable_path(self, root: Path | None = None) -> str:
        return normalize_evidence_path(self.path, root)

    def normalize(self, root: Path | None = None) -> "Evidence":
        portable = normalize_evidence_path(self.path, root)
        return Evidence(
            path=Path(portable),
            reason=self.reason,
            source_type=self.source_type,
            detector=self.detector,
        )

    def to_dict(self, root: Path | None = None) -> dict[str, object]:
        payload: dict[str, object] = {
            "path": normalize_evidence_path(self.path, root),
            "reason": self.reason,
            "source_type": self.source_type.value,
        }
        if self.detector is not None:
            payload["detector"] = self.detector
        return payload

    @classmethod
    def from_source(
        cls,
        path: Path | str,
        reason: str,
        *,
        root: Path | None = None,
        source_type: SourceType = SourceType.FILE,
        detector: str | None = None,
    ) -> "Evidence":
        portable = normalize_evidence_path(path, root)
        return cls(
            path=Path(portable),
            reason=reason,
            source_type=source_type,
            detector=detector,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "Evidence":
        if not isinstance(payload, Mapping):
            raise ValueError("Evidence payload must be an object.")
        raw_path = payload.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("Evidence 'path' must be a non-empty relative path string.")
        portable_path = normalize_evidence_path(raw_path, None)
        reason = payload.get("reason")
        source_type = payload.get("source_type", SourceType.FILE.value)
        detector = payload.get("detector")
        return cls(
            path=Path(portable_path),
            reason=str(reason) if isinstance(reason, str) else "",
            source_type=SourceType.coerce(source_type),
            detector=str(detector) if detector is not None else None,
        )


@dataclass(frozen=True)
class ProjectFact:
    category: str
    value: str
    confidence: Confidence
    evidence: tuple[Evidence, ...] = ()
    detector: str = ""

    def __post_init__(self):
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("ProjectFact category must be a non-empty string.")
        cleaned_category = self.category.strip()
        object.__setattr__(self, "category", cleaned_category)

        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("ProjectFact value must be a non-empty string.")
        cleaned_value = self.value.strip()
        object.__setattr__(self, "value", cleaned_value)

        object.__setattr__(self, "confidence", Confidence.coerce(self.confidence))

        if self.detector is None:
            raise ValueError("ProjectFact detector cannot be None.")
        if not isinstance(self.detector, str):
            raise ValueError("ProjectFact detector must be a string.")
        if self.detector == "":
            resolved_detector = canonical_detector_id(cleaned_category, cleaned_value)
        else:
            resolved_detector = self.detector.strip()
            if not resolved_detector:
                raise ValueError("ProjectFact detector cannot be blank.")
        if resolved_detector.startswith("_") or not DETECTOR_ID_RE.match(resolved_detector):
            raise ValueError(
                f"Invalid ProjectFact detector '{resolved_detector}': must be a stable public identifier."
            )
        object.__setattr__(self, "detector", resolved_detector)

        if self.evidence is None or isinstance(self.evidence, (str, bytes)):
            raise ValueError("ProjectFact evidence must be a non-empty sequence of Evidence items.")
        evidence_tuple = tuple(self.evidence)
        if not evidence_tuple:
            raise ValueError("ProjectFact must include at least one Evidence item.")
        for item in evidence_tuple:
            if not isinstance(item, Evidence):
                raise ValueError("All ProjectFact evidence items must be Evidence instances.")
        object.__setattr__(self, "evidence", evidence_tuple)

    def normalize(self, root: Path | None = None) -> "ProjectFact":
        normalized_items = [item.normalize(root) for item in self.evidence]
        deduped = _dedupe_and_sort_evidence(normalized_items, root=None)
        return ProjectFact(
            category=self.category,
            value=self.value,
            confidence=self.confidence,
            evidence=deduped,
            detector=self.detector,
        )

    def to_dict(self, root: Path | None = None) -> dict[str, object]:
        normalized = self.normalize(root)
        return {
            "category": normalized.category,
            "value": normalized.value,
            "confidence": normalized.confidence.value,
            "detector": normalized.detector,
            "evidence": [item.to_dict(root=None) for item in normalized.evidence],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ProjectFact":
        if not isinstance(payload, Mapping):
            raise ValueError("ProjectFact payload must be an object.")
        raw_evidence = payload.get("evidence")
        if not isinstance(raw_evidence, list) or not raw_evidence:
            raise ValueError("ProjectFact 'evidence' must be a non-empty list.")
        evidence_items = tuple(Evidence.from_dict(item) for item in raw_evidence)
        detector = payload.get("detector")
        if not isinstance(detector, str) or not detector.strip():
            raise ValueError("ProjectFact 'detector' must be a non-empty string.")
        return cls(
            category=str(payload.get("category", "")),
            value=str(payload.get("value", "")),
            confidence=Confidence.coerce(payload.get("confidence")),
            evidence=evidence_items,
            detector=detector,
        )


def _dedupe_and_sort_evidence(
    evidence_items: Iterable[Evidence],
    root: Path | None = None,
) -> tuple[Evidence, ...]:
    by_key: dict[tuple[str, str, str, str], Evidence] = {}
    for item in evidence_items:
        normalized_item = item.normalize(root)
        key = (
            normalized_item.portable_path(None),
            normalized_item.reason,
            normalized_item.source_type.value,
            normalized_item.detector or "",
        )
        if key not in by_key:
            by_key[key] = normalized_item
    sorted_keys = sorted(by_key.keys())
    return tuple(by_key[key] for key in sorted_keys)


def normalize_facts(
    facts: Iterable[ProjectFact],
    root: Path | None = None,
) -> tuple[ProjectFact, ...]:
    """Normalize, deduplicate, and deterministically order a collection of `ProjectFact` items."""
    grouped: dict[tuple[str, str], ProjectFact] = {}

    for raw_fact in facts:
        if not isinstance(raw_fact, ProjectFact):
            raise ValueError("Expected ProjectFact instance during normalization.")
        fact = raw_fact.normalize(root)
        key = (fact.category, fact.value)
        canonical_detector = canonical_detector_id(fact.category, fact.value)
        if key not in grouped:
            grouped[key] = ProjectFact(
                category=fact.category,
                value=fact.value,
                confidence=fact.confidence,
                evidence=fact.evidence,
                detector=canonical_detector,
            )
            continue

        existing = grouped[key]
        strongest_confidence = (
            fact.confidence
            if fact.confidence.rank > existing.confidence.rank
            else existing.confidence
        )

        merged_evidence = _dedupe_and_sort_evidence(
            existing.evidence + fact.evidence,
            root=None,
        )
        grouped[key] = ProjectFact(
            category=existing.category,
            value=existing.value,
            confidence=strongest_confidence,
            evidence=merged_evidence,
            detector=canonical_detector,
        )

    sorted_keys = sorted(
        grouped.keys(),
        key=lambda item: (
            CATEGORY_ORDER_INDEX.get(item[0], 999),
            item[0],
            item[1],
        ),
    )
    return tuple(grouped[key] for key in sorted_keys)


@dataclass(frozen=True)
class ProjectModel:
    schema_version: int = PROJECT_MODEL_SCHEMA_VERSION
    root: Path = Path(".")
    facts: tuple[ProjectFact, ...] = ()

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != PROJECT_MODEL_SCHEMA_VERSION
        ):
            raise ValueError(
                f"Unsupported ProjectModel schema_version '{self.schema_version}': expected {PROJECT_MODEL_SCHEMA_VERSION}."
            )
        if self.root is None:
            raise ValueError("ProjectModel root cannot be None.")
        root_path = Path(self.root)
        object.__setattr__(self, "root", root_path)

        if self.facts is None or isinstance(self.facts, (str, bytes)):
            raise ValueError("ProjectModel facts must be a sequence of ProjectFact instances.")
        normalized_facts = normalize_facts(self.facts, root=root_path)
        object.__setattr__(self, "facts", normalized_facts)

    def facts_for(self, category: str) -> tuple[ProjectFact, ...]:
        return tuple(fact for fact in self.facts if fact.category == category)

    def by_category(self, category: str) -> tuple[ProjectFact, ...]:
        return self.facts_for(category)

    def values(self, category: str) -> tuple[str, ...]:
        return tuple(fact.value for fact in self.facts_for(category))

    def has(
        self,
        category: str,
        value: str | None = None,
    ) -> bool:
        if value is None:
            return any(fact.category == category for fact in self.facts)
        return any(
            fact.category == category and fact.value == value for fact in self.facts
        )

    def fact(self, category: str, value: str) -> ProjectFact | None:
        for item in self.facts:
            if item.category == category and item.value == value:
                return item
        return None

    def categories(self) -> tuple[str, ...]:
        seen = []
        for fact in self.facts:
            if fact.category not in seen:
                seen.append(fact.category)
        return tuple(seen)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "facts": [fact.to_dict(root=self.root) for fact in self.facts],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        root: Path = Path("."),
    ) -> "ProjectModel":
        if not isinstance(payload, Mapping):
            raise ValueError("ProjectModel payload must be a JSON object.")
        schema_version = payload.get("schema_version")
        raw_facts = payload.get("facts")
        if not isinstance(raw_facts, list):
            raise ValueError("ProjectModel 'facts' must be a list.")
        facts = tuple(ProjectFact.from_dict(item) for item in raw_facts)
        return cls(
            schema_version=schema_version,  # type: ignore[arg-type]
            root=root,
            facts=facts,
        )

    @classmethod
    def from_json(cls, raw_json: str, root: Path = Path(".")) -> "ProjectModel":
        payload = json.loads(raw_json)
        return cls.from_dict(payload, root=root)

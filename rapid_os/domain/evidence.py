from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Iterable, Mapping

from rapid_os.domain.capabilities import (
    CANONICAL_CAPABILITY_IDS,
    validate_capability_id,
)
from rapid_os.domain.execution import (
    GATE_ID_RE,
    ExecutionContract,
    ExecutionError,
    RunState,
    validate_run_id,
    validate_task_id,
)
from rapid_os.domain.harnesses import (
    HarnessCapabilityError,
    validate_harness_id,
)
from rapid_os.domain.policy import sha256_canonical_json


RUN_EVIDENCE_SCHEMA_VERSION = 1

EVIDENCE_ID_RE = re.compile(r"^E\d{3,}$")
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class EvidenceError(ValueError):
    """Base domain error for Phase 6 Evidence Engine operations (RAPID1201-RAPID1219)."""

    default_code = "RAPID1202"

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


class InvalidEvidenceIdError(EvidenceError):
    default_code = "RAPID1201"


class InvalidRunEvidenceError(EvidenceError):
    default_code = "RAPID1202"


class EvidenceBindingMismatchError(EvidenceError):
    default_code = "RAPID1203"


class UnsafeEvidencePathError(EvidenceError):
    default_code = "RAPID1204"


class EvidenceArtifactIntegrityError(EvidenceError):
    default_code = "RAPID1205"


class InvalidEvidencePayloadError(EvidenceError):
    default_code = "RAPID1206"


class InvalidEvidenceReferenceError(EvidenceError):
    default_code = "RAPID1207"


class EvidenceSequenceGapError(EvidenceError):
    default_code = "RAPID1208"


class EvidenceNotFoundError(EvidenceError):
    default_code = "RAPID1210"


class EvidenceOverwriteError(EvidenceError):
    default_code = "RAPID1211"


def sha256_bytes(data: bytes) -> str:
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("sha256_bytes requires bytes.")
    return hashlib.sha256(bytes(data)).hexdigest()


def _validate_sha256(
    value: object,
    label: str,
    error_cls=InvalidRunEvidenceError,
) -> str:
    if not isinstance(value, str) or not SHA256_HEX_RE.match(value):
        raise error_cls(
            f"Invalid {label} '{value}': must be a 64-character lowercase hex SHA-256 digest."
        )
    return value


def format_evidence_id(index: int) -> str:
    """Format 1-based evidence ordinal as `E001`, `E002`, ..., `E1000`."""
    if isinstance(index, bool) or not isinstance(index, int) or index < 1:
        raise InvalidEvidenceIdError(
            f"Invalid evidence index '{index}': must be a positive integer."
        )
    return f"E{index:03d}"


def parse_evidence_ordinal(raw_id: object, label: str = "evidence id") -> int:
    validated = validate_evidence_id(raw_id, label)
    return int(validated[1:])


def validate_evidence_id(raw_id: object, label: str = "evidence id") -> str:
    """Validate that `raw_id` is a canonical evidence identifier (`E001`..`E999`, `E1000`, ...)."""
    if not isinstance(raw_id, str):
        raise InvalidEvidenceIdError(
            f"Invalid {label}: expected a string."
        )
    if "\x00" in raw_id or not raw_id or raw_id != raw_id.strip():
        raise InvalidEvidenceIdError(
            f"Invalid {label} '{raw_id}': whitespace and null bytes are not allowed."
        )
    if not EVIDENCE_ID_RE.match(raw_id):
        raise InvalidEvidenceIdError(
            f"Invalid {label} '{raw_id}': must match {EVIDENCE_ID_RE.pattern}."
        )
    num = int(raw_id[1:])
    if num < 1 or raw_id != f"E{num:03d}":
        raise InvalidEvidenceIdError(
            f"Invalid {label} '{raw_id}': must use canonical E001..E999 format."
        )
    return raw_id


def is_canonical_evidence_file_name(name: str) -> bool:
    """Return True if `name` is `<canonical_evidence_id>.json` (`E001.json`, ...)."""
    if not isinstance(name, str) or not name.endswith(".json"):
        return False
    stem = name[:-5]
    try:
        validate_evidence_id(stem)
        return True
    except InvalidEvidenceIdError:
        return False


def format_evidence_file_name(evidence_id: str | int) -> str:
    if isinstance(evidence_id, int) and not isinstance(evidence_id, bool):
        validated = format_evidence_id(evidence_id)
    else:
        validated = validate_evidence_id(evidence_id)
    return f"{validated}.json"


def _validate_portable_text(
    value: object,
    label: str,
    *,
    error_cls=InvalidRunEvidenceError,
    forbid_slashes: bool = False,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error_cls(f"{label} must be a non-empty string.")
    if "\x00" in value:
        raise error_cls(f"{label} cannot contain null bytes.")
    cleaned = value.strip()
    if "\\" in cleaned or _WINDOWS_DRIVE_RE.match(cleaned) or cleaned.startswith("/"):
        raise error_cls(
            f"{label} '{cleaned}' must be portable and cannot be a host path."
        )
    if forbid_slashes and "/" in cleaned:
        raise error_cls(f"{label} '{cleaned}' cannot contain path separators.")
    segments = [seg for seg in cleaned.split("/") if seg]
    if ".." in segments:
        raise error_cls(f"{label} '{cleaned}' cannot contain '..' segments.")
    return cleaned


def validate_relative_posix_path(
    raw_path: object,
    label: str = "relative path",
    *,
    error_cls=UnsafeEvidencePathError,
) -> str:
    """Validate that `raw_path` is a portable, normalized, project-relative POSIX path."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise error_cls(f"{label} must be a non-empty string.")
    if "\x00" in raw_path:
        raise error_cls(f"{label} cannot contain null bytes.")
    if raw_path != raw_path.strip():
        raise error_cls(
            f"{label} '{raw_path}' cannot have leading or trailing whitespace."
        )
    if (
        raw_path.startswith(("/", "\\"))
        or "\\" in raw_path
        or _WINDOWS_DRIVE_RE.match(raw_path)
    ):
        raise error_cls(
            f"{label} '{raw_path}' must be a project-relative POSIX path without drive letters or backslashes."
        )
    win_p = PureWindowsPath(raw_path)
    posix_p = PurePosixPath(raw_path)
    if win_p.is_absolute() or posix_p.is_absolute() or win_p.drive or win_p.root or posix_p.root:
        raise error_cls(f"{label} '{raw_path}' cannot be an absolute path.")

    raw_segments = raw_path.split("/")
    if any(seg in {"", ".", ".."} for seg in raw_segments):
        raise error_cls(
            f"{label} '{raw_path}' cannot contain empty, '.', or '..' path segments."
        )
    return "/".join(raw_segments)


def validate_evidence_producer(raw_producer: object) -> str:
    """Validate declared evidence producer (`harness:<id>`, `ci:...`, `user`, `external:...`)."""
    producer = _validate_portable_text(
        raw_producer,
        "RunEvidence.producer",
        error_cls=InvalidRunEvidenceError,
        forbid_slashes=True,
    )
    if any(ch.isspace() for ch in producer):
        raise InvalidRunEvidenceError(
            f"RunEvidence.producer '{producer}' cannot contain whitespace."
        )
    if producer.startswith("harness:"):
        harness_part = producer[len("harness:") :]
        try:
            validate_harness_id(harness_part, "producer harness id")
        except HarnessCapabilityError as exc:
            raise InvalidRunEvidenceError(
                f"Invalid harness producer '{producer}': {exc}"
            ) from exc
    return producer


class EvidenceKind(str, Enum):
    COMMAND_RESULT = "command_result"
    TEST_RESULT = "test_result"
    FILE_CHANGE = "file_change"
    GIT_RESULT = "git_result"
    WORKSPACE = "workspace"
    REVIEW = "review"
    TOOL_INVOCATION = "tool_invocation"
    DELEGATION = "delegation"
    ARTIFACT = "artifact"

    @classmethod
    def coerce(cls, value: object) -> "EvidenceKind":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidEvidencePayloadError(
            f"Invalid EvidenceKind '{value}': expected one of {[m.value for m in cls]}."
        )


ALLOWED_GIT_OPERATIONS = frozenset({"inspect", "modify"})
ALLOWED_WORKSPACE_MODES = frozenset({"current", "isolated"})
ALLOWED_REVIEW_TYPES = frozenset({"peer", "security", "migration", "manual", "final"})
ALLOWED_REVIEW_OUTCOMES = frozenset({"approved", "changes_requested", "rejected"})
ALLOWED_INVOCATION_OUTCOMES = frozenset({"success", "failure"})

PAYLOAD_REQUIRED_KEYS: Mapping[EvidenceKind, frozenset[str]] = {
    EvidenceKind.COMMAND_RESULT: frozenset({"label", "exit_code"}),
    EvidenceKind.TEST_RESULT: frozenset(
        {"suite", "exit_code", "passed", "failed", "skipped"}
    ),
    EvidenceKind.FILE_CHANGE: frozenset({"paths"}),
    EvidenceKind.GIT_RESULT: frozenset({"operation"}),
    EvidenceKind.WORKSPACE: frozenset({"mode"}),
    EvidenceKind.REVIEW: frozenset({"review_type", "outcome", "reviewer"}),
    EvidenceKind.TOOL_INVOCATION: frozenset({"tool_id", "outcome"}),
    EvidenceKind.DELEGATION: frozenset({"target", "outcome"}),
    EvidenceKind.ARTIFACT: frozenset({"label"}),
}


def _validate_int_field(
    value: object,
    label: str,
    *,
    minimum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidEvidencePayloadError(
            f"Payload field '{label}' must be an integer."
        )
    if minimum is not None and value < minimum:
        raise InvalidEvidencePayloadError(
            f"Payload field '{label}' must be >= {minimum}, got {value}."
        )
    return value


def validate_evidence_payload(
    kind: EvidenceKind | str,
    payload: object,
) -> dict[str, object]:
    """Validate and normalize `payload` strictly against the canonical schema for `kind`."""
    coerced_kind = EvidenceKind.coerce(kind)
    if not isinstance(payload, Mapping):
        raise InvalidEvidencePayloadError(
            f"Evidence payload for '{coerced_kind.value}' must be a JSON object."
        )

    expected_keys = PAYLOAD_REQUIRED_KEYS[coerced_kind]
    actual_keys = set(payload.keys())
    unknown = actual_keys - expected_keys
    if unknown:
        raise InvalidEvidencePayloadError(
            f"Unexpected fields in '{coerced_kind.value}' payload: {sorted(unknown)}."
        )
    missing = expected_keys - actual_keys
    if missing:
        raise InvalidEvidencePayloadError(
            f"Missing required fields in '{coerced_kind.value}' payload: {sorted(missing)}."
        )

    if coerced_kind == EvidenceKind.COMMAND_RESULT:
        label = _validate_portable_text(
            payload["label"],
            "command_result.label",
            error_cls=InvalidEvidencePayloadError,
        )
        exit_code = _validate_int_field(
            payload["exit_code"],
            "command_result.exit_code",
        )
        return {
            "label": label,
            "exit_code": exit_code,
        }

    if coerced_kind == EvidenceKind.TEST_RESULT:
        suite = _validate_portable_text(
            payload["suite"],
            "test_result.suite",
            error_cls=InvalidEvidencePayloadError,
        )
        exit_code = _validate_int_field(
            payload["exit_code"],
            "test_result.exit_code",
        )
        passed = _validate_int_field(
            payload["passed"],
            "test_result.passed",
            minimum=0,
        )
        failed = _validate_int_field(
            payload["failed"],
            "test_result.failed",
            minimum=0,
        )
        skipped = _validate_int_field(
            payload["skipped"],
            "test_result.skipped",
            minimum=0,
        )
        return {
            "suite": suite,
            "exit_code": exit_code,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        }

    if coerced_kind == EvidenceKind.FILE_CHANGE:
        raw_paths = payload["paths"]
        if (
            isinstance(raw_paths, (str, bytes))
            or not isinstance(raw_paths, Iterable)
        ):
            raise InvalidEvidencePayloadError(
                "file_change.paths must be a non-empty list of relative POSIX paths."
            )
        normalized_paths: list[str] = []
        seen_paths: set[str] = set()
        for item in raw_paths:
            norm_path = validate_relative_posix_path(
                item,
                "file_change.paths entry",
                error_cls=InvalidEvidencePayloadError,
            )
            if norm_path not in seen_paths:
                seen_paths.add(norm_path)
                normalized_paths.append(norm_path)
        if not normalized_paths:
            raise InvalidEvidencePayloadError(
                "file_change.paths must contain at least one path."
            )
        normalized_paths.sort()
        return {
            "paths": normalized_paths,
        }

    if coerced_kind == EvidenceKind.GIT_RESULT:
        raw_op = payload["operation"]
        if not isinstance(raw_op, str) or raw_op.strip() not in ALLOWED_GIT_OPERATIONS:
            raise InvalidEvidencePayloadError(
                f"git_result.operation must be one of {sorted(ALLOWED_GIT_OPERATIONS)}, got '{raw_op}'."
            )
        return {
            "operation": raw_op.strip(),
        }

    if coerced_kind == EvidenceKind.WORKSPACE:
        raw_mode = payload["mode"]
        if (
            not isinstance(raw_mode, str)
            or raw_mode.strip() not in ALLOWED_WORKSPACE_MODES
        ):
            raise InvalidEvidencePayloadError(
                f"workspace.mode must be one of {sorted(ALLOWED_WORKSPACE_MODES)}, got '{raw_mode}'."
            )
        return {
            "mode": raw_mode.strip(),
        }

    if coerced_kind == EvidenceKind.REVIEW:
        raw_type = payload["review_type"]
        raw_outcome = payload["outcome"]
        if (
            not isinstance(raw_type, str)
            or raw_type.strip() not in ALLOWED_REVIEW_TYPES
        ):
            raise InvalidEvidencePayloadError(
                f"review.review_type must be one of {sorted(ALLOWED_REVIEW_TYPES)}, got '{raw_type}'."
            )
        if (
            not isinstance(raw_outcome, str)
            or raw_outcome.strip() not in ALLOWED_REVIEW_OUTCOMES
        ):
            raise InvalidEvidencePayloadError(
                f"review.outcome must be one of {sorted(ALLOWED_REVIEW_OUTCOMES)}, got '{raw_outcome}'."
            )
        reviewer = _validate_portable_text(
            payload["reviewer"],
            "review.reviewer",
            error_cls=InvalidEvidencePayloadError,
            forbid_slashes=True,
        )
        return {
            "review_type": raw_type.strip(),
            "outcome": raw_outcome.strip(),
            "reviewer": reviewer,
        }

    if coerced_kind == EvidenceKind.TOOL_INVOCATION:
        tool_id = _validate_portable_text(
            payload["tool_id"],
            "tool_invocation.tool_id",
            error_cls=InvalidEvidencePayloadError,
            forbid_slashes=True,
        )
        raw_outcome = payload["outcome"]
        if (
            not isinstance(raw_outcome, str)
            or raw_outcome.strip() not in ALLOWED_INVOCATION_OUTCOMES
        ):
            raise InvalidEvidencePayloadError(
                f"tool_invocation.outcome must be one of {sorted(ALLOWED_INVOCATION_OUTCOMES)}, got '{raw_outcome}'."
            )
        return {
            "tool_id": tool_id,
            "outcome": raw_outcome.strip(),
        }

    if coerced_kind == EvidenceKind.DELEGATION:
        target = _validate_portable_text(
            payload["target"],
            "delegation.target",
            error_cls=InvalidEvidencePayloadError,
            forbid_slashes=True,
        )
        raw_outcome = payload["outcome"]
        if (
            not isinstance(raw_outcome, str)
            or raw_outcome.strip() not in ALLOWED_INVOCATION_OUTCOMES
        ):
            raise InvalidEvidencePayloadError(
                f"delegation.outcome must be one of {sorted(ALLOWED_INVOCATION_OUTCOMES)}, got '{raw_outcome}'."
            )
        return {
            "target": target,
            "outcome": raw_outcome.strip(),
        }

    if coerced_kind == EvidenceKind.ARTIFACT:
        label = _validate_portable_text(
            payload["label"],
            "artifact.label",
            error_cls=InvalidEvidencePayloadError,
        )
        return {
            "label": label,
        }

    raise InvalidEvidencePayloadError(
        f"Unsupported EvidenceKind '{coerced_kind}'."
    )


CANONICAL_EVIDENCE_ARTIFACT_KEYS = frozenset({"path", "sha256", "size_bytes"})


def validate_evidence_artifact_path(
    raw_path: object,
    *,
    expected_run_id: str | None = None,
    expected_evidence_id: str | None = None,
) -> str:
    """Validate that `raw_path` is `.rapid-os/evidence/<run-id>/artifacts/<evidence-id>/<relpath>`."""
    normalized = validate_relative_posix_path(
        raw_path,
        "EvidenceArtifact.path",
        error_cls=UnsafeEvidencePathError,
    )
    parts = normalized.split("/")
    if (
        len(parts) < 6
        or parts[0] != ".rapid-os"
        or parts[1] != "evidence"
        or parts[3] != "artifacts"
    ):
        raise UnsafeEvidencePathError(
            f"EvidenceArtifact.path '{normalized}' must reside under '.rapid-os/evidence/<run-id>/artifacts/<evidence-id>/'."
        )
    path_run_id = parts[2]
    path_evidence_id = parts[4]
    try:
        validate_run_id(path_run_id, "artifact path run_id")
    except ExecutionError as exc:
        raise UnsafeEvidencePathError(str(exc)) from exc
    try:
        validate_evidence_id(path_evidence_id, "artifact path evidence_id")
    except InvalidEvidenceIdError as exc:
        raise UnsafeEvidencePathError(str(exc)) from exc

    if expected_run_id is not None and path_run_id != expected_run_id:
        raise UnsafeEvidencePathError(
            f"EvidenceArtifact.path '{normalized}' run_id '{path_run_id}' does not match RunEvidence.run_id '{expected_run_id}'."
        )
    if (
        expected_evidence_id is not None
        and path_evidence_id != expected_evidence_id
    ):
        raise UnsafeEvidencePathError(
            f"EvidenceArtifact.path '{normalized}' evidence_id '{path_evidence_id}' does not match RunEvidence.id '{expected_evidence_id}'."
        )
    return normalized


@dataclass(frozen=True)
class EvidenceArtifact:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        object.__setattr__(
            self,
            "path",
            validate_evidence_artifact_path(self.path),
        )
        object.__setattr__(
            self,
            "sha256",
            _validate_sha256(
                self.sha256,
                "EvidenceArtifact.sha256",
                EvidenceArtifactIntegrityError,
            ),
        )
        if (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes < 0
        ):
            raise EvidenceArtifactIntegrityError(
                f"Invalid EvidenceArtifact.size_bytes '{self.size_bytes}': must be a non-negative integer."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "EvidenceArtifact":
        if not isinstance(payload, Mapping):
            raise InvalidRunEvidenceError(
                "EvidenceArtifact payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_EVIDENCE_ARTIFACT_KEYS
        if unknown:
            raise InvalidRunEvidenceError(
                f"Unexpected fields in EvidenceArtifact: {sorted(unknown)}."
            )
        missing = CANONICAL_EVIDENCE_ARTIFACT_KEYS - set(payload.keys())
        if missing:
            raise InvalidRunEvidenceError(
                f"Missing required fields in EvidenceArtifact: {sorted(missing)}."
            )
        return cls(
            path=payload["path"],  # type: ignore[arg-type]
            sha256=payload["sha256"],  # type: ignore[arg-type]
            size_bytes=payload["size_bytes"],  # type: ignore[arg-type]
        )


def _normalize_task_ids(values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise InvalidEvidenceReferenceError(
            "RunEvidence.task_ids must be a sequence of task IDs."
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        try:
            validated = validate_task_id(raw, "RunEvidence.task_ids entry")
        except ExecutionError as exc:
            raise InvalidEvidenceReferenceError(str(exc)) from exc
        if validated not in seen:
            seen.add(validated)
            normalized.append(validated)
    normalized.sort(key=lambda item: int(item[1:]))
    return tuple(normalized)


def _normalize_gate_ids(values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise InvalidEvidenceReferenceError(
            "RunEvidence.gate_ids must be a sequence of gate IDs."
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        if (
            not isinstance(raw, str)
            or not raw.strip()
            or raw != raw.strip()
            or not GATE_ID_RE.match(raw)
        ):
            raise InvalidEvidenceReferenceError(
                f"Invalid gate reference '{raw}' in RunEvidence.gate_ids."
            )
        if raw not in seen:
            seen.add(raw)
            normalized.append(raw)
    normalized.sort()
    return tuple(normalized)


def _normalize_capability_ids(values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise InvalidEvidenceReferenceError(
            "RunEvidence.capability_ids must be a sequence of capability IDs."
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        try:
            validated = validate_capability_id(
                raw,
                "RunEvidence.capability_ids entry",
            )
        except HarnessCapabilityError as exc:
            raise InvalidEvidenceReferenceError(str(exc)) from exc
        if validated not in seen:
            seen.add(validated)
            normalized.append(validated)
    normalized.sort()
    return tuple(normalized)


CANONICAL_RUN_EVIDENCE_KEYS = frozenset(
    {
        "schema_version",
        "id",
        "run_id",
        "contract_digest",
        "state_revision",
        "state_digest",
        "kind",
        "producer",
        "summary",
        "task_ids",
        "gate_ids",
        "capability_ids",
        "payload",
        "artifacts",
        "content_digest",
    }
)


@dataclass(frozen=True)
class RunEvidence:
    schema_version: int
    id: str
    run_id: str
    contract_digest: str
    state_revision: int
    state_digest: str
    kind: EvidenceKind
    producer: str
    summary: str
    task_ids: tuple[str, ...]
    gate_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    payload: Mapping[str, object]
    artifacts: tuple[EvidenceArtifact, ...] = ()
    content_digest: str = ""

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != RUN_EVIDENCE_SCHEMA_VERSION
        ):
            raise InvalidRunEvidenceError(
                f"Unsupported RunEvidence schema_version '{self.schema_version}': expected {RUN_EVIDENCE_SCHEMA_VERSION}."
            )

        object.__setattr__(
            self,
            "id",
            validate_evidence_id(self.id, "RunEvidence.id"),
        )
        try:
            validated_run_id = validate_run_id(self.run_id, "RunEvidence.run_id")
        except ExecutionError as exc:
            raise InvalidRunEvidenceError(str(exc)) from exc
        object.__setattr__(self, "run_id", validated_run_id)

        object.__setattr__(
            self,
            "contract_digest",
            _validate_sha256(
                self.contract_digest,
                "RunEvidence.contract_digest",
                InvalidRunEvidenceError,
            ),
        )
        if (
            isinstance(self.state_revision, bool)
            or not isinstance(self.state_revision, int)
            or self.state_revision < 1
        ):
            raise InvalidRunEvidenceError(
                f"Invalid RunEvidence.state_revision '{self.state_revision}': must be a positive integer."
            )
        object.__setattr__(
            self,
            "state_digest",
            _validate_sha256(
                self.state_digest,
                "RunEvidence.state_digest",
                InvalidRunEvidenceError,
            ),
        )

        coerced_kind = EvidenceKind.coerce(self.kind)
        object.__setattr__(self, "kind", coerced_kind)

        object.__setattr__(
            self,
            "producer",
            validate_evidence_producer(self.producer),
        )
        object.__setattr__(
            self,
            "summary",
            _validate_portable_text(
                self.summary,
                "RunEvidence.summary",
                error_cls=InvalidRunEvidenceError,
            ),
        )

        object.__setattr__(
            self,
            "task_ids",
            _normalize_task_ids(self.task_ids),
        )
        object.__setattr__(
            self,
            "gate_ids",
            _normalize_gate_ids(self.gate_ids),
        )
        object.__setattr__(
            self,
            "capability_ids",
            _normalize_capability_ids(self.capability_ids),
        )

        normalized_payload = validate_evidence_payload(coerced_kind, self.payload)
        object.__setattr__(self, "payload", normalized_payload)

        if isinstance(self.artifacts, (str, bytes)) or not isinstance(
            self.artifacts, Iterable
        ):
            raise InvalidRunEvidenceError(
                "RunEvidence.artifacts must be a sequence of EvidenceArtifact items."
            )
        normalized_artifacts: list[EvidenceArtifact] = []
        seen_paths: set[str] = set()
        for item in self.artifacts:
            art_obj = (
                item
                if isinstance(item, EvidenceArtifact)
                else EvidenceArtifact.from_dict(item)  # type: ignore[arg-type]
            )
            validate_evidence_artifact_path(
                art_obj.path,
                expected_run_id=self.run_id,
                expected_evidence_id=self.id,
            )
            if art_obj.path in seen_paths:
                raise InvalidRunEvidenceError(
                    f"Duplicate artifact path '{art_obj.path}' in RunEvidence '{self.id}'."
                )
            seen_paths.add(art_obj.path)
            normalized_artifacts.append(art_obj)

        normalized_artifacts.sort(key=lambda a: a.path)
        object.__setattr__(self, "artifacts", tuple(normalized_artifacts))

        if coerced_kind == EvidenceKind.ARTIFACT and not self.artifacts:
            raise InvalidEvidencePayloadError(
                "RunEvidence of kind 'artifact' must include at least one EvidenceArtifact."
            )

        computed_digest = self._compute_content_digest()
        if self.content_digest:
            validated_digest = _validate_sha256(
                self.content_digest,
                "RunEvidence.content_digest",
                InvalidRunEvidenceError,
            )
            if validated_digest != computed_digest:
                raise InvalidRunEvidenceError(
                    f"RunEvidence 'content_digest' mismatch for '{self.id}'."
                )
        object.__setattr__(self, "content_digest", computed_digest)

    def _canonical_digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "run_id": self.run_id,
            "contract_digest": self.contract_digest,
            "state_revision": self.state_revision,
            "state_digest": self.state_digest,
            "kind": self.kind.value,
            "producer": self.producer,
            "summary": self.summary,
            "task_ids": list(self.task_ids),
            "gate_ids": list(self.gate_ids),
            "capability_ids": list(self.capability_ids),
            "payload": dict(self.payload),
            "artifacts": [a.to_dict() for a in self.artifacts],
        }

    def _compute_content_digest(self) -> str:
        return sha256_canonical_json(self._canonical_digest_payload())

    def to_dict(self) -> dict[str, object]:
        return {
            **self._canonical_digest_payload(),
            "content_digest": self.content_digest,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        *,
        verify_digest: bool = True,
    ) -> "RunEvidence":
        if not isinstance(payload, Mapping):
            raise InvalidRunEvidenceError(
                "RunEvidence payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_RUN_EVIDENCE_KEYS
        if unknown:
            raise InvalidRunEvidenceError(
                f"Unexpected fields in RunEvidence: {sorted(unknown)}."
            )
        missing = CANONICAL_RUN_EVIDENCE_KEYS - set(payload.keys())
        if missing:
            raise InvalidRunEvidenceError(
                f"Missing required fields in RunEvidence: {sorted(missing)}."
            )
        raw_artifacts = payload["artifacts"]
        if not isinstance(raw_artifacts, list):
            raise InvalidRunEvidenceError(
                "RunEvidence 'artifacts' must be a JSON list."
            )
        raw_digest = str(payload["content_digest"]) if verify_digest else ""
        return cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            id=payload["id"],  # type: ignore[arg-type]
            run_id=payload["run_id"],  # type: ignore[arg-type]
            contract_digest=payload["contract_digest"],  # type: ignore[arg-type]
            state_revision=payload["state_revision"],  # type: ignore[arg-type]
            state_digest=payload["state_digest"],  # type: ignore[arg-type]
            kind=EvidenceKind.coerce(payload["kind"]),
            producer=payload["producer"],  # type: ignore[arg-type]
            summary=payload["summary"],  # type: ignore[arg-type]
            task_ids=payload["task_ids"],  # type: ignore[arg-type]
            gate_ids=payload["gate_ids"],  # type: ignore[arg-type]
            capability_ids=payload["capability_ids"],  # type: ignore[arg-type]
            payload=payload["payload"],  # type: ignore[arg-type]
            artifacts=tuple(
                EvidenceArtifact.from_dict(item) for item in raw_artifacts
            ),
            content_digest=raw_digest,
        )

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        verify_digest: bool = True,
    ) -> "RunEvidence":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidRunEvidenceError(
                f"Invalid RunEvidence JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise InvalidRunEvidenceError(
                "RunEvidence JSON root must be an object."
            )
        return cls.from_dict(payload, verify_digest=verify_digest)


def verify_evidence_against_run(
    evidence: RunEvidence,
    contract: ExecutionContract,
    state: RunState,
    *,
    current_state_revision: int | None = None,
) -> None:
    """Verify that `evidence` is strictly bound to `contract` and `state` and references valid tasks/gates/capabilities."""
    if not isinstance(evidence, RunEvidence):
        raise InvalidRunEvidenceError(
            "verify_evidence_against_run requires a RunEvidence instance."
        )
    if not isinstance(contract, ExecutionContract):
        raise EvidenceBindingMismatchError(
            "verify_evidence_against_run requires an ExecutionContract instance."
        )
    if not isinstance(state, RunState):
        raise EvidenceBindingMismatchError(
            "verify_evidence_against_run requires a RunState instance."
        )

    if evidence.run_id != contract.run_id or evidence.run_id != state.run_id:
        raise EvidenceBindingMismatchError(
            f"Evidence '{evidence.id}' run_id '{evidence.run_id}' does not match run '{contract.run_id}'."
        )
    if evidence.contract_digest != contract.contract_digest:
        raise EvidenceBindingMismatchError(
            f"Evidence '{evidence.id}' contract_digest '{evidence.contract_digest}' does not match contract digest '{contract.contract_digest}'."
        )
    if (
        current_state_revision is not None
        and evidence.state_revision > current_state_revision
    ):
        raise EvidenceBindingMismatchError(
            f"Evidence '{evidence.id}' references state_revision s{evidence.state_revision}, which exceeds current_state_revision s{current_state_revision}."
        )
    if evidence.state_revision != state.revision:
        raise EvidenceBindingMismatchError(
            f"Evidence '{evidence.id}' state_revision s{evidence.state_revision} does not match loaded RunState s{state.revision}."
        )
    if evidence.state_digest != state.content_digest:
        raise EvidenceBindingMismatchError(
            f"Evidence '{evidence.id}' state_digest '{evidence.state_digest}' does not match persisted RunState s{state.revision} digest '{state.content_digest}'."
        )

    if evidence.producer.startswith("harness:"):
        declared_harness = evidence.producer[len("harness:") :]
        if declared_harness != contract.harness:
            raise EvidenceBindingMismatchError(
                f"Evidence '{evidence.id}' producer '{evidence.producer}' does not match contract harness '{contract.harness}'."
            )

    valid_task_ids = {t.id for t in contract.tasks}
    for task_id in evidence.task_ids:
        if task_id not in valid_task_ids:
            raise InvalidEvidenceReferenceError(
                f"Evidence '{evidence.id}' references unknown task '{task_id}' not present in ExecutionContract."
            )

    valid_gate_ids = {g.id for g in contract.gates}
    for gate_id in evidence.gate_ids:
        if gate_id not in valid_gate_ids:
            raise InvalidEvidenceReferenceError(
                f"Evidence '{evidence.id}' references unknown gate '{gate_id}' not present in ExecutionContract."
            )

    for cap_id in evidence.capability_ids:
        if cap_id not in CANONICAL_CAPABILITY_IDS:
            raise InvalidEvidenceReferenceError(
                f"Evidence '{evidence.id}' references unknown capability '{cap_id}'."
            )


def compute_evidence_set_digest(
    records_or_run_id: Iterable[RunEvidence] | str,
    records: Iterable[RunEvidence] | None = None,
    *,
    run_id: str | None = None,
) -> str:
    """Compute canonical SHA-256 digest of a run's ordered `RunEvidence` set."""
    if isinstance(records_or_run_id, str):
        resolved_run_id = records_or_run_id
        resolved_records = tuple(records or ())
    else:
        resolved_records = tuple(records_or_run_id)
        resolved_run_id = run_id or (
            resolved_records[0].run_id if resolved_records else ""
        )

    if not resolved_run_id:
        raise InvalidRunEvidenceError(
            "compute_evidence_set_digest requires run_id when records is empty."
        )
    try:
        validated_run_id = validate_run_id(resolved_run_id, "evidence set run_id")
    except ExecutionError as exc:
        raise InvalidRunEvidenceError(str(exc)) from exc

    seen_ids: set[str] = set()
    ordered_list: list[RunEvidence] = []
    for rec in resolved_records:
        if not isinstance(rec, RunEvidence):
            raise InvalidRunEvidenceError(
                "compute_evidence_set_digest requires RunEvidence instances."
            )
        if rec.run_id != validated_run_id:
            raise EvidenceBindingMismatchError(
                f"RunEvidence '{rec.id}' belongs to run '{rec.run_id}', expected '{validated_run_id}'."
            )
        if rec.id in seen_ids:
            raise EvidenceSequenceGapError(
                f"Duplicate evidence ID '{rec.id}' in evidence set for run '{validated_run_id}'."
            )
        seen_ids.add(rec.id)
        ordered_list.append(rec)

    ordered_list.sort(key=lambda item: parse_evidence_ordinal(item.id))
    canonical_payload = {
        "run_id": validated_run_id,
        "records": [
            {
                "id": item.id,
                "content_digest": item.content_digest,
            }
            for item in ordered_list
        ],
    }
    return sha256_canonical_json(canonical_payload)

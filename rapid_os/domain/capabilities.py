from dataclasses import dataclass
from enum import Enum
import json
import re
from typing import Iterable, Mapping

from rapid_os.domain.execution import (
    ExecutionContract,
    GateKind,
    WorkspaceRequirement,
)
from rapid_os.domain.harnesses import (
    BUILTIN_HARNESS_IDS,
    HARNESS_ID_RE,
    CapabilityResolutionDigestMismatchError,
    HarnessCapabilityError,
    HarnessIdentityError,
    HarnessProfileNotFoundError,
    IncompatibleHarnessError,
    InvalidCapabilityIdError,
    InvalidCapabilityLockError,
    InvalidCapabilityRequirementError,
    InvalidCapabilityResolutionError,
    InvalidCapabilitySupportError,
    InvalidHarnessProfileError,
    UnsafeHarnessPathError,
    validate_harness_id,
    validate_harness_profile_source,
)
from rapid_os.domain.policy import sha256_canonical_json


HARNESS_PROFILE_SCHEMA_VERSION = 1
CAPABILITY_RESOLUTION_SCHEMA_VERSION = 1
CAPABILITY_LOCK_SCHEMA_VERSION = 1

CAPABILITY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,95}$")
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _validate_sha256(
    value: object,
    label: str,
    error_cls=InvalidHarnessProfileError,
) -> str:
    if not isinstance(value, str) or not SHA256_HEX_RE.match(value):
        raise error_cls(
            f"Invalid {label} '{value}': must be a 64-character lowercase hex SHA-256 digest."
        )
    return value


def _validate_portable_token(
    value: object,
    label: str,
    error_cls=InvalidCapabilityRequirementError,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error_cls(f"{label} must be a non-empty string.")
    if "\x00" in value:
        raise error_cls(f"{label} cannot contain null bytes.")
    cleaned = value.strip()
    if "\\" in cleaned or _WINDOWS_DRIVE_RE.match(cleaned) or cleaned.startswith("/"):
        raise error_cls(
            f"{label} '{cleaned}' must be portable and cannot be an absolute host path."
        )
    segments = [seg for seg in cleaned.split("/") if seg]
    if ".." in segments:
        raise error_cls(f"{label} '{cleaned}' cannot contain '..' segments.")
    return cleaned


class CapabilityCategory(str, Enum):
    CONTEXT = "context"
    REPOSITORY = "repository"
    WORKSPACE = "workspace"
    EXECUTION = "execution"
    TESTING = "testing"
    GIT = "git"
    INTEGRATION = "integration"
    DELEGATION = "delegation"

    @classmethod
    def coerce(cls, value: object) -> "CapabilityCategory":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidCapabilityIdError(
            f"Invalid CapabilityCategory '{value}': expected one of {[m.value for m in cls]}."
        )


@dataclass(frozen=True)
class CapabilityDefinition:
    id: str
    category: CapabilityCategory
    description: str

    def __post_init__(self):
        if (
            not isinstance(self.id, str)
            or "\x00" in self.id
            or self.id != self.id.strip()
            or ".." in self.id
            or self.id.endswith((".", "-"))
            or not CAPABILITY_ID_RE.match(self.id)
        ):
            raise InvalidCapabilityIdError(
                f"Invalid CapabilityDefinition.id '{self.id}': must match {CAPABILITY_ID_RE.pattern}."
            )
        object.__setattr__(
            self,
            "category",
            CapabilityCategory.coerce(self.category),
        )
        if not isinstance(self.description, str) or not self.description.strip():
            raise InvalidCapabilityIdError(
                "CapabilityDefinition.description must be a non-empty string."
            )
        object.__setattr__(self, "description", self.description.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "category": self.category.value,
            "description": self.description,
        }


CANONICAL_CAPABILITY_DEFINITIONS: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        id="context.consume",
        category=CapabilityCategory.CONTEXT,
        description="Consume compiled Rapid OS context and execution contracts.",
    ),
    CapabilityDefinition(
        id="git.inspect",
        category=CapabilityCategory.GIT,
        description="Inspect repository git status, history, and diffs.",
    ),
    CapabilityDefinition(
        id="git.modify",
        category=CapabilityCategory.GIT,
        description="Create branches, commits, or worktrees in git.",
    ),
    CapabilityDefinition(
        id="mcp.invoke",
        category=CapabilityCategory.INTEGRATION,
        description="Invoke configured Model Context Protocol (MCP) tools and resources.",
    ),
    CapabilityDefinition(
        id="repository.read",
        category=CapabilityCategory.REPOSITORY,
        description="Read repository files and project structure.",
    ),
    CapabilityDefinition(
        id="repository.write",
        category=CapabilityCategory.REPOSITORY,
        description="Create or modify repository files during task implementation.",
    ),
    CapabilityDefinition(
        id="shell.execute",
        category=CapabilityCategory.EXECUTION,
        description="Execute local shell or terminal commands.",
    ),
    CapabilityDefinition(
        id="subagents.delegate",
        category=CapabilityCategory.DELEGATION,
        description="Delegate subtasks to specialized subagents.",
    ),
    CapabilityDefinition(
        id="tests.execute",
        category=CapabilityCategory.TESTING,
        description="Execute automated test suites for implementation verification.",
    ),
    CapabilityDefinition(
        id="workspace.current",
        category=CapabilityCategory.WORKSPACE,
        description="Operate within the current working tree when allowed by policy.",
    ),
    CapabilityDefinition(
        id="workspace.isolated",
        category=CapabilityCategory.WORKSPACE,
        description="Operate within an isolated workspace or worktree when required by policy.",
    ),
)

CANONICAL_CAPABILITY_CATALOG: Mapping[str, CapabilityDefinition] = {
    defn.id: defn for defn in CANONICAL_CAPABILITY_DEFINITIONS
}

CANONICAL_CAPABILITY_IDS: tuple[str, ...] = tuple(
    sorted(CANONICAL_CAPABILITY_CATALOG.keys())
)


def validate_capability_id(
    raw_id: object,
    label: str = "capability id",
) -> str:
    """Validate that `raw_id` is a syntactically valid capability ID registered in the canonical catalog."""
    if not isinstance(raw_id, str):
        raise InvalidCapabilityIdError(
            f"Invalid {label}: expected a string."
        )
    if "\x00" in raw_id or not raw_id or raw_id != raw_id.strip():
        raise InvalidCapabilityIdError(
            f"Invalid {label} '{raw_id}': whitespace and null bytes are not allowed."
        )
    if (
        ".." in raw_id
        or raw_id.endswith((".", "-"))
        or not CAPABILITY_ID_RE.match(raw_id)
    ):
        raise InvalidCapabilityIdError(
            f"Invalid {label} '{raw_id}': must match {CAPABILITY_ID_RE.pattern}."
        )
    if raw_id not in CANONICAL_CAPABILITY_CATALOG:
        raise InvalidCapabilityIdError(
            f"Unknown capability ID '{raw_id}': expected one of {list(CANONICAL_CAPABILITY_IDS)}."
        )
    return raw_id


def get_capability_definition(capability_id: str) -> CapabilityDefinition:
    """Return the canonical `CapabilityDefinition` for `capability_id`."""
    validated_id = validate_capability_id(capability_id)
    return CANONICAL_CAPABILITY_CATALOG[validated_id]


class CapabilitySupportStatus(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"

    @classmethod
    def coerce(cls, value: object) -> "CapabilitySupportStatus":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidCapabilitySupportError(
            f"Invalid CapabilitySupportStatus '{value}': expected one of {[m.value for m in cls]}."
        )


CANONICAL_CAPABILITY_SUPPORT_KEYS = frozenset(
    {"capability_id", "status", "reason"}
)


@dataclass(frozen=True)
class CapabilitySupport:
    capability_id: str
    status: CapabilitySupportStatus
    reason: str

    def __post_init__(self):
        object.__setattr__(
            self,
            "capability_id",
            validate_capability_id(
                self.capability_id,
                "CapabilitySupport.capability_id",
            ),
        )
        object.__setattr__(
            self,
            "status",
            CapabilitySupportStatus.coerce(self.status),
        )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidCapabilitySupportError(
                "CapabilitySupport.reason must be a non-empty string."
            )
        object.__setattr__(self, "reason", self.reason.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "status": self.status.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "CapabilitySupport":
        if not isinstance(payload, Mapping):
            raise InvalidCapabilitySupportError(
                "CapabilitySupport payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_CAPABILITY_SUPPORT_KEYS
        if unknown:
            raise InvalidCapabilitySupportError(
                f"Unexpected fields in CapabilitySupport: {sorted(unknown)}."
            )
        missing = CANONICAL_CAPABILITY_SUPPORT_KEYS - set(payload.keys())
        if missing:
            raise InvalidCapabilitySupportError(
                f"Missing required fields in CapabilitySupport: {sorted(missing)}."
            )
        raw_cap_id = payload["capability_id"]
        raw_status = payload["status"]
        raw_reason = payload["reason"]
        if not isinstance(raw_cap_id, str):
            raise InvalidCapabilityIdError(
                "CapabilitySupport 'capability_id' must be a string."
            )
        if not isinstance(raw_status, str):
            raise InvalidCapabilitySupportError(
                "CapabilitySupport 'status' must be a string."
            )
        if not isinstance(raw_reason, str):
            raise InvalidCapabilitySupportError(
                "CapabilitySupport 'reason' must be a string."
            )
        return cls(
            capability_id=raw_cap_id,
            status=CapabilitySupportStatus.coerce(raw_status),
            reason=raw_reason,
        )


CANONICAL_HARNESS_PROFILE_KEYS = frozenset(
    {"schema_version", "id", "capabilities", "content_digest"}
)
REQUIRED_HARNESS_PROFILE_INPUT_KEYS = frozenset(
    {"schema_version", "id", "capabilities"}
)


@dataclass(frozen=True)
class HarnessProfile:
    schema_version: int
    id: str
    capabilities: tuple[CapabilitySupport, ...]
    content_digest: str = ""

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != HARNESS_PROFILE_SCHEMA_VERSION
        ):
            raise InvalidHarnessProfileError(
                f"Unsupported HarnessProfile schema_version '{self.schema_version}': expected {HARNESS_PROFILE_SCHEMA_VERSION}."
            )
        object.__setattr__(
            self,
            "id",
            validate_harness_id(self.id, "HarnessProfile.id"),
        )

        if isinstance(self.capabilities, (str, bytes)) or not isinstance(
            self.capabilities, Iterable
        ):
            raise InvalidHarnessProfileError(
                "HarnessProfile.capabilities must be a sequence of CapabilitySupport items."
            )

        normalized_caps: list[CapabilitySupport] = []
        seen_cap_ids: set[str] = set()
        for item in self.capabilities:
            support_obj = (
                item
                if isinstance(item, CapabilitySupport)
                else CapabilitySupport.from_dict(item)  # type: ignore[arg-type]
            )
            if support_obj.capability_id in seen_cap_ids:
                raise InvalidCapabilitySupportError(
                    f"Duplicate capability support declaration '{support_obj.capability_id}' in HarnessProfile '{self.id}'."
                )
            seen_cap_ids.add(support_obj.capability_id)
            normalized_caps.append(support_obj)

        normalized_caps.sort(key=lambda c: c.capability_id)
        object.__setattr__(self, "capabilities", tuple(normalized_caps))

        computed_digest = self._compute_content_digest()
        if self.content_digest:
            validated_digest = _validate_sha256(
                self.content_digest,
                "HarnessProfile.content_digest",
                InvalidHarnessProfileError,
            )
            if validated_digest != computed_digest:
                raise InvalidHarnessProfileError(
                    f"HarnessProfile 'content_digest' mismatch for '{self.id}'."
                )
        object.__setattr__(self, "content_digest", computed_digest)

    def _canonical_digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "capabilities": [c.to_dict() for c in self.capabilities],
        }

    def _compute_content_digest(self) -> str:
        return sha256_canonical_json(self._canonical_digest_payload())

    @property
    def digest(self) -> str:
        return self.content_digest

    def support_map(self) -> dict[str, CapabilitySupport]:
        return {item.capability_id: item for item in self.capabilities}

    def get_support(self, capability_id: str) -> CapabilitySupport | None:
        validated_id = validate_capability_id(capability_id)
        for item in self.capabilities:
            if item.capability_id == validated_id:
                return item
        return None

    def support_for(self, capability_id: str) -> CapabilitySupport:
        """Return explicit `CapabilitySupport` for `capability_id`, or conservative `UNKNOWN` if omitted from profile."""
        validated_id = validate_capability_id(capability_id)
        for item in self.capabilities:
            if item.capability_id == validated_id:
                return item
        return CapabilitySupport(
            capability_id=validated_id,
            status=CapabilitySupportStatus.UNKNOWN,
            reason=f"Capability '{validated_id}' is not declared in harness profile '{self.id}'.",
        )

    def status_for(self, capability_id: str) -> CapabilitySupportStatus:
        return self.support_for(capability_id).status

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "capabilities": [c.to_dict() for c in self.capabilities],
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
        require_digest: bool = False,
    ) -> "HarnessProfile":
        if not isinstance(payload, Mapping):
            raise InvalidHarnessProfileError(
                "HarnessProfile payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_HARNESS_PROFILE_KEYS
        if unknown:
            raise InvalidHarnessProfileError(
                f"Unexpected fields in HarnessProfile: {sorted(unknown)}."
            )
        missing = REQUIRED_HARNESS_PROFILE_INPUT_KEYS - set(payload.keys())
        if missing:
            raise InvalidHarnessProfileError(
                f"Missing required fields in HarnessProfile: {sorted(missing)}."
            )
        if require_digest and "content_digest" not in payload:
            raise InvalidHarnessProfileError(
                "Missing required field 'content_digest' in HarnessProfile."
            )

        raw_caps = payload["capabilities"]
        if not isinstance(raw_caps, list):
            raise InvalidHarnessProfileError(
                "HarnessProfile 'capabilities' must be a list."
            )
        supports = tuple(CapabilitySupport.from_dict(item) for item in raw_caps)

        raw_digest = ""
        if "content_digest" in payload:
            raw_digest_val = payload["content_digest"]
            if not isinstance(raw_digest_val, str) or not raw_digest_val.strip():
                raise InvalidHarnessProfileError(
                    "HarnessProfile 'content_digest' must be a non-empty SHA-256 hex string when present."
                )
            if verify_digest:
                raw_digest = _validate_sha256(
                    raw_digest_val,
                    "HarnessProfile.content_digest",
                    InvalidHarnessProfileError,
                )

        return cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            id=payload["id"],  # type: ignore[arg-type]
            capabilities=supports,
            content_digest=raw_digest,
        )

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        verify_digest: bool = True,
        require_digest: bool = False,
    ) -> "HarnessProfile":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidHarnessProfileError(
                f"Invalid HarnessProfile JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise InvalidHarnessProfileError(
                "HarnessProfile JSON root must be an object."
            )
        return cls.from_dict(
            payload,
            verify_digest=verify_digest,
            require_digest=require_digest,
        )


CANONICAL_CAPABILITY_REQUIREMENT_KEYS = frozenset(
    {"capability_id", "required", "source", "reason"}
)


@dataclass(frozen=True)
class CapabilityRequirement:
    capability_id: str
    required: bool
    source: str
    reason: str

    def __post_init__(self):
        object.__setattr__(
            self,
            "capability_id",
            validate_capability_id(
                self.capability_id,
                "CapabilityRequirement.capability_id",
            ),
        )
        if not isinstance(self.required, bool):
            raise InvalidCapabilityRequirementError(
                "CapabilityRequirement.required must be a boolean."
            )
        object.__setattr__(
            self,
            "source",
            _validate_portable_token(
                self.source,
                "CapabilityRequirement.source",
                InvalidCapabilityRequirementError,
            ),
        )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidCapabilityRequirementError(
                "CapabilityRequirement.reason must be a non-empty string."
            )
        object.__setattr__(self, "reason", self.reason.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "required": self.required,
            "source": self.source,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "CapabilityRequirement":
        if not isinstance(payload, Mapping):
            raise InvalidCapabilityRequirementError(
                "CapabilityRequirement payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_CAPABILITY_REQUIREMENT_KEYS
        if unknown:
            raise InvalidCapabilityRequirementError(
                f"Unexpected fields in CapabilityRequirement: {sorted(unknown)}."
            )
        missing = CANONICAL_CAPABILITY_REQUIREMENT_KEYS - set(payload.keys())
        if missing:
            raise InvalidCapabilityRequirementError(
                f"Missing required fields in CapabilityRequirement: {sorted(missing)}."
            )
        return cls(
            capability_id=payload["capability_id"],  # type: ignore[arg-type]
            required=payload["required"],  # type: ignore[arg-type]
            source=payload["source"],  # type: ignore[arg-type]
            reason=payload["reason"],  # type: ignore[arg-type]
        )


class CapabilityRequirementResolver:
    """Pure domain service that deterministically derives `CapabilityRequirement` items from an `ExecutionContract`."""

    @staticmethod
    def derive(
        contract: ExecutionContract,
        *,
        extra_requirements: Iterable[CapabilityRequirement | Mapping[str, object] | str] = (),
    ) -> tuple[CapabilityRequirement, ...]:
        if not isinstance(contract, ExecutionContract):
            raise InvalidCapabilityRequirementError(
                "CapabilityRequirementResolver.derive requires an ExecutionContract instance."
            )

        by_id: dict[str, CapabilityRequirement] = {}

        def _add_derived(
            capability_id: str,
            source: str,
            reason: str,
        ) -> None:
            req = CapabilityRequirement(
                capability_id=capability_id,
                required=True,
                source=source,
                reason=reason,
            )
            by_id[req.capability_id] = req

        # 1. Always required
        _add_derived(
            "context.consume",
            "contract",
            "Execution contract requires consuming the compiled context snapshot.",
        )
        _add_derived(
            "repository.read",
            "contract",
            "Execution contract requires reading repository files.",
        )

        # 2. Tasks -> repository.write
        if contract.tasks:
            _add_derived(
                "repository.write",
                "contract.tasks",
                f"Execution contract defines {len(contract.tasks)} implementation task(s) requiring repository writes.",
            )

        # 3. Workspace requirement -> workspace.current or workspace.isolated
        if contract.workspace == WorkspaceRequirement.CURRENT_ALLOWED:
            _add_derived(
                "workspace.current",
                "contract.workspace",
                "Execution contract allows operating in the current workspace.",
            )
        elif contract.workspace == WorkspaceRequirement.ISOLATED_REQUIRED:
            _add_derived(
                "workspace.isolated",
                "contract.workspace",
                "Execution contract requires an isolated workspace.",
            )

        # 4. Required implementation_tests gate -> tests.execute
        if any(
            gate.required and gate.kind == GateKind.IMPLEMENTATION_TESTS
            for gate in contract.gates
        ):
            _add_derived(
                "tests.execute",
                "contract.gates",
                "Execution contract requires implementation test verification (gate.tests).",
            )

        # 5. Extra requirements (additive only; never remove or downgrade derived requirements)
        if extra_requirements is not None:
            if isinstance(extra_requirements, (str, bytes)) or not isinstance(
                extra_requirements, Iterable
            ):
                raise InvalidCapabilityRequirementError(
                    "extra_requirements must be an iterable of capability IDs or CapabilityRequirement items."
                )
            for item in extra_requirements:
                if isinstance(item, str):
                    validated_id = validate_capability_id(
                        item,
                        "extra capability requirement",
                    )
                    extra_req = CapabilityRequirement(
                        capability_id=validated_id,
                        required=True,
                        source="extra",
                        reason=f"Explicitly required capability '{validated_id}'.",
                    )
                elif isinstance(item, CapabilityRequirement):
                    extra_req = item
                elif isinstance(item, Mapping):
                    extra_req = CapabilityRequirement.from_dict(item)
                else:
                    raise InvalidCapabilityRequirementError(
                        f"Invalid extra requirement '{item}': expected capability ID string or CapabilityRequirement."
                    )

                if not extra_req.required:
                    raise InvalidCapabilityRequirementError(
                        f"Extra capability requirement '{extra_req.capability_id}' cannot set required=False or remove contract requirements."
                    )
                if extra_req.capability_id not in by_id:
                    by_id[extra_req.capability_id] = extra_req

        return tuple(by_id[cap_id] for cap_id in sorted(by_id.keys()))


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNRESOLVED = "unresolved"

    @classmethod
    def coerce(cls, value: object) -> "CompatibilityStatus":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidCapabilityResolutionError(
            f"Invalid CompatibilityStatus '{value}': expected one of {[m.value for m in cls]}."
        )


CANONICAL_CAPABILITY_RESOLUTION_KEYS = frozenset(
    {
        "schema_version",
        "harness_id",
        "contract_digest",
        "profile_source",
        "profile_digest",
        "requirements",
        "satisfied",
        "missing",
        "unknown",
        "status",
        "reasons",
        "resolution_digest",
    }
)


def _normalize_capability_id_tuple(
    values: object,
    label: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise InvalidCapabilityResolutionError(
            f"{label} must be a sequence of capability IDs."
        )
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        validated = validate_capability_id(raw, label)
        if validated in seen:
            raise InvalidCapabilityResolutionError(
                f"Duplicate capability ID '{validated}' in {label}."
            )
        seen.add(validated)
        result.append(validated)
    return tuple(sorted(result))


@dataclass(frozen=True)
class CapabilityResolution:
    schema_version: int
    harness_id: str
    contract_digest: str
    profile_source: str
    profile_digest: str
    requirements: tuple[CapabilityRequirement, ...]
    satisfied: tuple[str, ...]
    missing: tuple[str, ...]
    unknown: tuple[str, ...]
    status: CompatibilityStatus
    reasons: tuple[str, ...]
    resolution_digest: str = ""

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != CAPABILITY_RESOLUTION_SCHEMA_VERSION
        ):
            raise InvalidCapabilityResolutionError(
                f"Unsupported CapabilityResolution schema_version '{self.schema_version}': expected {CAPABILITY_RESOLUTION_SCHEMA_VERSION}."
            )
        object.__setattr__(
            self,
            "harness_id",
            validate_harness_id(self.harness_id, "CapabilityResolution.harness_id"),
        )
        object.__setattr__(
            self,
            "contract_digest",
            _validate_sha256(
                self.contract_digest,
                "CapabilityResolution.contract_digest",
                InvalidCapabilityResolutionError,
            ),
        )
        object.__setattr__(
            self,
            "profile_source",
            validate_harness_profile_source(
                self.profile_source,
                expected_harness_id=self.harness_id,
                error_cls=InvalidCapabilityResolutionError,
            ),
        )
        object.__setattr__(
            self,
            "profile_digest",
            _validate_sha256(
                self.profile_digest,
                "CapabilityResolution.profile_digest",
                InvalidCapabilityResolutionError,
            ),
        )

        if isinstance(self.requirements, (str, bytes)) or not isinstance(
            self.requirements, Iterable
        ):
            raise InvalidCapabilityResolutionError(
                "CapabilityResolution.requirements must be a sequence of CapabilityRequirement items."
            )
        normalized_reqs: list[CapabilityRequirement] = []
        seen_req_ids: set[str] = set()
        for item in self.requirements:
            req_obj = (
                item
                if isinstance(item, CapabilityRequirement)
                else CapabilityRequirement.from_dict(item)  # type: ignore[arg-type]
            )
            if req_obj.capability_id in seen_req_ids:
                raise InvalidCapabilityRequirementError(
                    f"Duplicate capability requirement '{req_obj.capability_id}' in CapabilityResolution."
                )
            seen_req_ids.add(req_obj.capability_id)
            normalized_reqs.append(req_obj)
        normalized_reqs.sort(key=lambda r: r.capability_id)
        object.__setattr__(self, "requirements", tuple(normalized_reqs))

        satisfied_tuple = _normalize_capability_id_tuple(
            self.satisfied,
            "CapabilityResolution.satisfied",
        )
        missing_tuple = _normalize_capability_id_tuple(
            self.missing,
            "CapabilityResolution.missing",
        )
        unknown_tuple = _normalize_capability_id_tuple(
            self.unknown,
            "CapabilityResolution.unknown",
        )
        object.__setattr__(self, "satisfied", satisfied_tuple)
        object.__setattr__(self, "missing", missing_tuple)
        object.__setattr__(self, "unknown", unknown_tuple)

        sat_set = set(satisfied_tuple)
        mis_set = set(missing_tuple)
        unk_set = set(unknown_tuple)
        if (sat_set & mis_set) or (sat_set & unk_set) or (mis_set & unk_set):
            raise InvalidCapabilityResolutionError(
                "CapabilityResolution satisfied, missing, and unknown sets must be mutually disjoint."
            )
        required_set = {r.capability_id for r in normalized_reqs if r.required}
        if (sat_set | mis_set | unk_set) != required_set:
            raise InvalidCapabilityResolutionError(
                "CapabilityResolution partition (satisfied | missing | unknown) does not match required capabilities."
            )

        status_obj = CompatibilityStatus.coerce(self.status)
        if missing_tuple:
            expected_status = CompatibilityStatus.INCOMPATIBLE
        elif unknown_tuple:
            expected_status = CompatibilityStatus.UNRESOLVED
        else:
            expected_status = CompatibilityStatus.COMPATIBLE
        if status_obj != expected_status:
            raise InvalidCapabilityResolutionError(
                f"CapabilityResolution status '{status_obj.value}' is inconsistent with missing={list(missing_tuple)} and unknown={list(unknown_tuple)} (expected '{expected_status.value}')."
            )
        object.__setattr__(self, "status", status_obj)

        if isinstance(self.reasons, (str, bytes)) or not isinstance(
            self.reasons, Iterable
        ):
            raise InvalidCapabilityResolutionError(
                "CapabilityResolution.reasons must be a sequence of strings."
            )
        normalized_reasons: list[str] = []
        for reason in self.reasons:
            if not isinstance(reason, str) or not reason.strip():
                raise InvalidCapabilityResolutionError(
                    "CapabilityResolution.reasons entries must be non-empty strings."
                )
            cleaned = reason.strip()
            if cleaned not in normalized_reasons:
                normalized_reasons.append(cleaned)
        object.__setattr__(self, "reasons", tuple(normalized_reasons))

        computed_digest = self._compute_resolution_digest()
        if self.resolution_digest:
            validated_digest = _validate_sha256(
                self.resolution_digest,
                "CapabilityResolution.resolution_digest",
                CapabilityResolutionDigestMismatchError,
            )
            if validated_digest != computed_digest:
                raise CapabilityResolutionDigestMismatchError(
                    "CapabilityResolution 'resolution_digest' does not match canonical resolution content."
                )
        object.__setattr__(self, "resolution_digest", computed_digest)

    def _canonical_digest_payload(self) -> dict[str, object]:
        return {
            "harness_id": self.harness_id,
            "contract_digest": self.contract_digest,
            "profile_source": self.profile_source,
            "profile_digest": self.profile_digest,
            "requirements": [r.to_dict() for r in self.requirements],
            "satisfied": list(self.satisfied),
            "missing": list(self.missing),
            "unknown": list(self.unknown),
            "status": self.status.value,
            "reasons": list(self.reasons),
        }

    def _compute_resolution_digest(self) -> str:
        return sha256_canonical_json(self._canonical_digest_payload())

    @property
    def is_compatible(self) -> bool:
        return self.status == CompatibilityStatus.COMPATIBLE

    @property
    def required(self) -> tuple[CapabilityRequirement, ...]:
        return self.requirements

    @property
    def supported(self) -> tuple[str, ...]:
        return self.satisfied

    @property
    def unsupported(self) -> tuple[str, ...]:
        return self.missing

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "harness_id": self.harness_id,
            "contract_digest": self.contract_digest,
            "profile_source": self.profile_source,
            "profile_digest": self.profile_digest,
            "requirements": [r.to_dict() for r in self.requirements],
            "satisfied": list(self.satisfied),
            "missing": list(self.missing),
            "unknown": list(self.unknown),
            "status": self.status.value,
            "reasons": list(self.reasons),
            "resolution_digest": self.resolution_digest,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        *,
        verify_digest: bool = True,
    ) -> "CapabilityResolution":
        if not isinstance(payload, Mapping):
            raise InvalidCapabilityResolutionError(
                "CapabilityResolution payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_CAPABILITY_RESOLUTION_KEYS
        if unknown:
            raise InvalidCapabilityResolutionError(
                f"Unexpected fields in CapabilityResolution: {sorted(unknown)}."
            )
        missing = CANONICAL_CAPABILITY_RESOLUTION_KEYS - set(payload.keys())
        if missing:
            raise InvalidCapabilityResolutionError(
                f"Missing required fields in CapabilityResolution: {sorted(missing)}."
            )
        raw_reqs = payload["requirements"]
        raw_satisfied = payload["satisfied"]
        raw_missing = payload["missing"]
        raw_unknown = payload["unknown"]
        raw_reasons = payload["reasons"]
        if (
            not isinstance(raw_reqs, list)
            or not isinstance(raw_satisfied, list)
            or not isinstance(raw_missing, list)
            or not isinstance(raw_unknown, list)
            or not isinstance(raw_reasons, list)
        ):
            raise InvalidCapabilityResolutionError(
                "CapabilityResolution list fields ('requirements', 'satisfied', 'missing', 'unknown', 'reasons') must be JSON lists."
            )
        raw_digest = str(payload["resolution_digest"]) if verify_digest else ""
        return cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            harness_id=payload["harness_id"],  # type: ignore[arg-type]
            contract_digest=payload["contract_digest"],  # type: ignore[arg-type]
            profile_source=payload["profile_source"],  # type: ignore[arg-type]
            profile_digest=payload["profile_digest"],  # type: ignore[arg-type]
            requirements=tuple(
                CapabilityRequirement.from_dict(r) for r in raw_reqs
            ),
            satisfied=tuple(raw_satisfied),
            missing=tuple(raw_missing),
            unknown=tuple(raw_unknown),
            status=CompatibilityStatus.coerce(payload["status"]),
            reasons=tuple(raw_reasons),
            resolution_digest=raw_digest,
        )

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        verify_digest: bool = True,
    ) -> "CapabilityResolution":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidCapabilityResolutionError(
                f"Invalid CapabilityResolution JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise InvalidCapabilityResolutionError(
                "CapabilityResolution JSON root must be an object."
            )
        return cls.from_dict(payload, verify_digest=verify_digest)


class _DualResolveDescriptor:
    def __init__(self, func):
        self._func = func

    def __get__(self, instance, owner=None):
        def _bound(*args, **kwargs):
            return self._func(instance, *args, **kwargs)

        return _bound


class CapabilityResolver:
    """Pure domain resolver evaluating `ExecutionContract` capability requirements against a `HarnessProfile`."""

    def __init__(
        self,
        requirement_resolver: CapabilityRequirementResolver | None = None,
    ):
        self._requirement_resolver = (
            requirement_resolver or CapabilityRequirementResolver()
        )

    @_DualResolveDescriptor
    def resolve(
        self_or_none,
        contract: ExecutionContract,
        profile: HarnessProfile,
        *,
        profile_source: str,
        extra_requirements: Iterable[CapabilityRequirement | Mapping[str, object] | str] = (),
        run_id: str | None = None,
    ) -> CapabilityResolution:
        del run_id
        req_resolver = (
            self_or_none._requirement_resolver
            if isinstance(self_or_none, CapabilityResolver)
            else CapabilityRequirementResolver()
        )
        if not isinstance(contract, ExecutionContract):
            raise InvalidCapabilityResolutionError(
                "CapabilityResolver.resolve requires an ExecutionContract instance."
            )
        if not isinstance(profile, HarnessProfile):
            raise InvalidCapabilityResolutionError(
                "CapabilityResolver.resolve requires a HarnessProfile instance."
            )
        if profile.id != contract.harness:
            raise InvalidCapabilityResolutionError(
                f"HarnessProfile.id '{profile.id}' does not match ExecutionContract.harness '{contract.harness}'."
            )
        validated_source = validate_harness_profile_source(
            profile_source,
            expected_harness_id=profile.id,
            error_cls=InvalidCapabilityResolutionError,
        )

        requirements = req_resolver.derive(
            contract,
            extra_requirements=extra_requirements,
        )

        satisfied: list[str] = []
        missing: list[str] = []
        unknown: list[str] = []
        reasons: list[str] = []

        for req in requirements:
            if not req.required:
                continue
            support = profile.support_for(req.capability_id)
            if support.status == CapabilitySupportStatus.SUPPORTED:
                satisfied.append(req.capability_id)
            elif support.status == CapabilitySupportStatus.UNSUPPORTED:
                missing.append(req.capability_id)
                reasons.append(
                    f"{req.capability_id}: unsupported by harness '{profile.id}' ({support.reason})"
                )
            else:
                unknown.append(req.capability_id)
                reasons.append(
                    f"{req.capability_id}: support is unknown for harness '{profile.id}' ({support.reason})"
                )

        if missing:
            status = CompatibilityStatus.INCOMPATIBLE
        elif unknown:
            status = CompatibilityStatus.UNRESOLVED
        else:
            status = CompatibilityStatus.COMPATIBLE
            reasons.append(
                f"All {len(satisfied)} required capabilities are declared supported by harness '{profile.id}'."
            )

        return CapabilityResolution(
            schema_version=CAPABILITY_RESOLUTION_SCHEMA_VERSION,
            harness_id=profile.id,
            contract_digest=contract.contract_digest,
            profile_source=validated_source,
            profile_digest=profile.content_digest,
            requirements=requirements,
            satisfied=tuple(satisfied),
            missing=tuple(missing),
            unknown=tuple(unknown),
            status=status,
            reasons=tuple(reasons),
        )


CANONICAL_LOCKED_HARNESS_PROFILE_KEYS = frozenset(
    {"id", "source", "profile_digest", "profile"}
)
CANONICAL_CAPABILITY_LOCK_KEYS = frozenset(
    {"schema_version", "profiles", "content_digest"}
)


@dataclass(frozen=True)
class LockedHarnessProfile:
    id: str
    source: str
    profile_digest: str
    profile: HarnessProfile

    def __post_init__(self):
        try:
            validated_id = validate_harness_id(
                self.id,
                "LockedHarnessProfile.id",
            )
        except HarnessCapabilityError as exc:
            raise InvalidCapabilityLockError(str(exc)) from exc
        object.__setattr__(self, "id", validated_id)

        validated_source = validate_harness_profile_source(
            self.source,
            expected_harness_id=validated_id,
            error_cls=InvalidCapabilityLockError,
        )
        object.__setattr__(self, "source", validated_source)

        validated_digest = _validate_sha256(
            self.profile_digest,
            "LockedHarnessProfile.profile_digest",
            InvalidCapabilityLockError,
        )
        object.__setattr__(self, "profile_digest", validated_digest)

        try:
            profile_obj = (
                self.profile
                if isinstance(self.profile, HarnessProfile)
                else HarnessProfile.from_dict(
                    self.profile,  # type: ignore[arg-type]
                    verify_digest=True,
                    require_digest=True,
                )
            )
        except HarnessCapabilityError as exc:
            raise InvalidCapabilityLockError(
                f"Invalid embedded HarnessProfile in lock for '{validated_id}': {exc}"
            ) from exc

        if profile_obj.id != validated_id:
            raise InvalidCapabilityLockError(
                f"LockedHarnessProfile.id '{validated_id}' does not match embedded profile.id '{profile_obj.id}'."
            )
        if profile_obj.content_digest != validated_digest:
            raise InvalidCapabilityLockError(
                f"LockedHarnessProfile.profile_digest '{validated_digest}' does not match embedded profile content_digest '{profile_obj.content_digest}'."
            )
        object.__setattr__(self, "profile", profile_obj)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "source": self.source,
            "profile_digest": self.profile_digest,
            "profile": self.profile.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "LockedHarnessProfile":
        if not isinstance(payload, Mapping):
            raise InvalidCapabilityLockError(
                "LockedHarnessProfile payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_LOCKED_HARNESS_PROFILE_KEYS
        if unknown:
            raise InvalidCapabilityLockError(
                f"Unexpected fields in LockedHarnessProfile: {sorted(unknown)}."
            )
        missing = CANONICAL_LOCKED_HARNESS_PROFILE_KEYS - set(payload.keys())
        if missing:
            raise InvalidCapabilityLockError(
                f"Missing required fields in LockedHarnessProfile: {sorted(missing)}."
            )
        try:
            profile_obj = HarnessProfile.from_dict(
                payload["profile"],  # type: ignore[arg-type]
                verify_digest=True,
                require_digest=True,
            )
        except HarnessCapabilityError as exc:
            raise InvalidCapabilityLockError(
                f"Invalid embedded HarnessProfile in capabilities.lock: {exc}"
            ) from exc
        return cls(
            id=payload["id"],  # type: ignore[arg-type]
            source=payload["source"],  # type: ignore[arg-type]
            profile_digest=payload["profile_digest"],  # type: ignore[arg-type]
            profile=profile_obj,
        )


@dataclass(frozen=True)
class CapabilityLock:
    schema_version: int
    profiles: tuple[LockedHarnessProfile, ...]
    content_digest: str = ""

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != CAPABILITY_LOCK_SCHEMA_VERSION
        ):
            raise InvalidCapabilityLockError(
                f"Unsupported CapabilityLock schema_version '{self.schema_version}': expected {CAPABILITY_LOCK_SCHEMA_VERSION}."
            )
        if isinstance(self.profiles, (str, bytes)) or not isinstance(
            self.profiles, Iterable
        ):
            raise InvalidCapabilityLockError(
                "CapabilityLock.profiles must be a sequence of LockedHarnessProfile items."
            )

        normalized_profiles: list[LockedHarnessProfile] = []
        seen_ids: set[str] = set()
        for item in self.profiles:
            locked_obj = (
                item
                if isinstance(item, LockedHarnessProfile)
                else LockedHarnessProfile.from_dict(item)  # type: ignore[arg-type]
            )
            if locked_obj.id in seen_ids:
                raise InvalidCapabilityLockError(
                    f"Duplicate harness profile '{locked_obj.id}' in CapabilityLock."
                )
            seen_ids.add(locked_obj.id)
            normalized_profiles.append(locked_obj)

        normalized_profiles.sort(key=lambda p: p.id)
        object.__setattr__(self, "profiles", tuple(normalized_profiles))

        computed_digest = self._compute_content_digest()
        if self.content_digest:
            validated_digest = _validate_sha256(
                self.content_digest,
                "CapabilityLock.content_digest",
                InvalidCapabilityLockError,
            )
            if validated_digest != computed_digest:
                raise InvalidCapabilityLockError(
                    "CapabilityLock 'content_digest' does not match canonical lock content."
                )
        object.__setattr__(self, "content_digest", computed_digest)

    def _canonical_digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profiles": [p.to_dict() for p in self.profiles],
        }

    def _compute_content_digest(self) -> str:
        return sha256_canonical_json(self._canonical_digest_payload())

    def get_profile(self, harness_id: str) -> LockedHarnessProfile:
        validated_id = validate_harness_id(harness_id)
        for item in self.profiles:
            if item.id == validated_id:
                return item
        raise HarnessProfileNotFoundError(
            f"Harness '{validated_id}' is not present in capabilities.lock."
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profiles": [p.to_dict() for p in self.profiles],
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
    ) -> "CapabilityLock":
        if not isinstance(payload, Mapping):
            raise InvalidCapabilityLockError(
                "CapabilityLock payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_CAPABILITY_LOCK_KEYS
        if unknown:
            raise InvalidCapabilityLockError(
                f"Unexpected fields in CapabilityLock: {sorted(unknown)}."
            )
        missing = CANONICAL_CAPABILITY_LOCK_KEYS - set(payload.keys())
        if missing:
            raise InvalidCapabilityLockError(
                f"Missing required fields in CapabilityLock: {sorted(missing)}."
            )
        raw_profiles = payload["profiles"]
        if not isinstance(raw_profiles, list):
            raise InvalidCapabilityLockError(
                "CapabilityLock 'profiles' must be a list."
            )
        locked_items = [
            LockedHarnessProfile.from_dict(item) for item in raw_profiles
        ]
        if [item.id for item in locked_items] != sorted(
            item.id for item in locked_items
        ):
            raise InvalidCapabilityLockError(
                "CapabilityLock 'profiles' must be ordered by harness id ASC."
            )
        raw_digest_val = payload["content_digest"]
        if not isinstance(raw_digest_val, str) or not raw_digest_val.strip():
            raise InvalidCapabilityLockError(
                "CapabilityLock 'content_digest' must be a non-empty SHA-256 hex string."
            )
        raw_digest = str(raw_digest_val) if verify_digest else ""
        return cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            profiles=tuple(locked_items),
            content_digest=raw_digest,
        )

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        verify_digest: bool = True,
    ) -> "CapabilityLock":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidCapabilityLockError(
                f"Invalid CapabilityLock JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise InvalidCapabilityLockError(
                "CapabilityLock JSON root must be an object."
            )
        return cls.from_dict(payload, verify_digest=verify_digest)

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Iterable, Mapping


EXECUTION_POLICY_SCHEMA_VERSION = 1

GATE_ID_RE = re.compile(r"^gate\.[a-z0-9][a-z0-9-]{0,62}$")
RISK_SIGNAL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")


def sha256_canonical_json(payload: Mapping[str, object]) -> str:
    """Compute a deterministic SHA-256 hex digest over canonical JSON serialization."""
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def sha256_utf8(text: str) -> str:
    """Compute a deterministic SHA-256 hex digest over UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ExecutionError(ValueError):
    """Base domain error for Phase 4 Execution Policy and Run Registry operations (RAPID1001-RAPID1014)."""

    default_code = "RAPID1001"

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


class InvalidRunRecordError(ExecutionError):
    default_code = "RAPID1001"


class InvalidExecutionContractError(ExecutionError):
    default_code = "RAPID1002"


class InvalidSpecBindingError(ExecutionError):
    default_code = "RAPID1003"


class ContextSnapshotMismatchError(ExecutionError):
    default_code = "RAPID1004"


class InvalidExecutionPolicyError(ExecutionError):
    default_code = "RAPID1005"


class PolicyViolationError(ExecutionError):
    default_code = "RAPID1006"


class RunIdentityError(ExecutionError):
    default_code = "RAPID1007"


class RunNotFoundError(RunIdentityError):
    default_code = "RAPID1007"


class DuplicateRunIdentityError(RunIdentityError):
    default_code = "RAPID1007"


class UnsafeRunPathError(ExecutionError):
    default_code = "RAPID1008"


class InvalidRunTransitionError(ExecutionError):
    default_code = "RAPID1009"


class InvalidTaskTransitionError(ExecutionError):
    default_code = "RAPID1010"


class RunStateHistoryGapError(ExecutionError):
    default_code = "RAPID1011"


class InvalidRunStateError(ExecutionError):
    default_code = "RAPID1012"


class InvalidGateTransitionError(ExecutionError):
    default_code = "RAPID1013"


class ExecutionPreconditionError(ExecutionError):
    default_code = "RAPID1014"


class ExecutionClass(str, Enum):
    SPIKE = "spike"
    BOUNDED = "bounded"
    ARCHITECTURAL = "architectural"

    @classmethod
    def coerce(cls, value: object) -> "ExecutionClass":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidExecutionPolicyError(
            f"Invalid ExecutionClass '{value}': expected one of {[m.value for m in cls]}."
        )

    @property
    def rank(self) -> int:
        ranks = {
            ExecutionClass.SPIKE: 1,
            ExecutionClass.BOUNDED: 2,
            ExecutionClass.ARCHITECTURAL: 3,
        }
        return ranks[self]


class RiskLevel(IntEnum):
    LOW = 10
    MEDIUM = 50
    HIGH = 80
    CRITICAL = 100

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def coerce(cls, value: object) -> "RiskLevel":
        if isinstance(value, cls):
            return value
        if not isinstance(value, bool) and isinstance(value, int):
            for member in cls:
                if int(member) == value:
                    return member
        if isinstance(value, str):
            normalized = value.strip().lower()
            by_label = {
                "low": cls.LOW,
                "medium": cls.MEDIUM,
                "high": cls.HIGH,
                "critical": cls.CRITICAL,
                "10": cls.LOW,
                "50": cls.MEDIUM,
                "80": cls.HIGH,
                "100": cls.CRITICAL,
            }
            if normalized in by_label:
                return by_label[normalized]
        raise InvalidExecutionPolicyError(
            f"Invalid RiskLevel '{value}': expected one of ['low', 'medium', 'high', 'critical']."
        )


class WorkspaceRequirement(str, Enum):
    CURRENT_ALLOWED = "current_allowed"
    ISOLATED_REQUIRED = "isolated_required"

    @classmethod
    def coerce(cls, value: object) -> "WorkspaceRequirement":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidExecutionPolicyError(
            f"Invalid WorkspaceRequirement '{value}': expected one of {[m.value for m in cls]}."
        )

    @property
    def rank(self) -> int:
        return 2 if self == WorkspaceRequirement.ISOLATED_REQUIRED else 1


class GateKind(str, Enum):
    BASELINE_CHECK = "baseline_check"
    IMPLEMENTATION_TESTS = "implementation_tests"
    PEER_REVIEW = "peer_review"
    SECURITY_REVIEW = "security_review"
    MIGRATION_REVIEW = "migration_review"
    MANUAL_APPROVAL = "manual_approval"
    FINAL_VERIFICATION = "final_verification"
    WORKSPACE_ISOLATION = "workspace_isolation"

    @classmethod
    def coerce(cls, value: object) -> "GateKind":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidExecutionPolicyError(
            f"Invalid GateKind '{value}': expected one of {[m.value for m in cls]}."
        )


class GatePhase(str, Enum):
    PRE_EXECUTION = "pre_execution"
    POST_EXECUTION = "post_execution"

    @classmethod
    def coerce(cls, value: object) -> "GatePhase":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidExecutionPolicyError(
            f"Invalid GatePhase '{value}': expected one of {[m.value for m in cls]}."
        )


CANONICAL_RISK_SIGNAL_KEYS = frozenset({"id", "level", "reason", "source"})
CANONICAL_GATE_REQUIREMENT_KEYS = frozenset(
    {"id", "kind", "phase", "required", "waivable", "reason"}
)
CANONICAL_POLICY_DECISION_KEYS = frozenset(
    {
        "classification",
        "risk",
        "risk_signals",
        "workspace",
        "gates",
        "reasons",
    }
)
CANONICAL_EXECUTION_POLICY_KEYS = frozenset(
    {
        "schema_version",
        "minimum_classification",
        "minimum_risk",
        "architectural_tags",
        "architectural_path_prefixes",
        "high_risk_tags",
        "critical_risk_tags",
        "workspace_by_risk",
        "waivable_gate_ids",
        "extra_required_gate_ids",
    }
)


@dataclass(frozen=True)
class RiskSignal:
    id: str
    level: RiskLevel
    reason: str
    source: str

    def __post_init__(self):
        if not isinstance(self.id, str) or not RISK_SIGNAL_ID_RE.match(self.id.strip()):
            raise InvalidExecutionPolicyError(
                f"Invalid RiskSignal.id '{self.id}'."
            )
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "level", RiskLevel.coerce(self.level))
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidExecutionPolicyError(
                "RiskSignal.reason must be a non-empty string."
            )
        object.__setattr__(self, "reason", self.reason.strip())
        if not isinstance(self.source, str) or not self.source.strip():
            raise InvalidExecutionPolicyError(
                "RiskSignal.source must be a non-empty string."
            )
        object.__setattr__(self, "source", self.source.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "level": self.level.label,
            "reason": self.reason,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "RiskSignal":
        if not isinstance(payload, Mapping):
            raise InvalidExecutionPolicyError("RiskSignal payload must be a JSON object.")
        unknown = set(payload.keys()) - CANONICAL_RISK_SIGNAL_KEYS
        if unknown:
            raise InvalidExecutionPolicyError(
                f"Unexpected fields in RiskSignal: {sorted(unknown)}."
            )
        missing = CANONICAL_RISK_SIGNAL_KEYS - set(payload.keys())
        if missing:
            raise InvalidExecutionPolicyError(
                f"Missing required fields in RiskSignal: {sorted(missing)}."
            )
        return cls(
            id=str(payload["id"]),
            level=RiskLevel.coerce(payload["level"]),
            reason=str(payload["reason"]),
            source=str(payload["source"]),
        )


@dataclass(frozen=True)
class GateRequirement:
    id: str
    kind: GateKind
    phase: GatePhase
    required: bool
    waivable: bool
    reason: str

    def __post_init__(self):
        if not isinstance(self.id, str) or not GATE_ID_RE.match(self.id.strip()):
            raise InvalidExecutionPolicyError(
                f"Invalid GateRequirement.id '{self.id}': must match {GATE_ID_RE.pattern}."
            )
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "kind", GateKind.coerce(self.kind))
        object.__setattr__(self, "phase", GatePhase.coerce(self.phase))
        if not isinstance(self.required, bool):
            raise InvalidExecutionPolicyError("GateRequirement.required must be a boolean.")
        if not isinstance(self.waivable, bool):
            raise InvalidExecutionPolicyError("GateRequirement.waivable must be a boolean.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidExecutionPolicyError(
                "GateRequirement.reason must be a non-empty string."
            )
        object.__setattr__(self, "reason", self.reason.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "phase": self.phase.value,
            "required": self.required,
            "waivable": self.waivable,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "GateRequirement":
        if not isinstance(payload, Mapping):
            raise InvalidExecutionPolicyError(
                "GateRequirement payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_GATE_REQUIREMENT_KEYS
        if unknown:
            raise InvalidExecutionPolicyError(
                f"Unexpected fields in GateRequirement: {sorted(unknown)}."
            )
        missing = CANONICAL_GATE_REQUIREMENT_KEYS - set(payload.keys())
        if missing:
            raise InvalidExecutionPolicyError(
                f"Missing required fields in GateRequirement: {sorted(missing)}."
            )
        return cls(
            id=str(payload["id"]),
            kind=GateKind.coerce(payload["kind"]),
            phase=GatePhase.coerce(payload["phase"]),
            required=payload["required"],  # type: ignore[arg-type]
            waivable=payload["waivable"],  # type: ignore[arg-type]
            reason=str(payload["reason"]),
        )


@dataclass(frozen=True)
class PolicyDecision:
    classification: ExecutionClass
    risk: RiskLevel
    risk_signals: tuple[RiskSignal, ...]
    workspace: WorkspaceRequirement
    gates: tuple[GateRequirement, ...]
    reasons: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(
            self,
            "classification",
            ExecutionClass.coerce(self.classification),
        )
        object.__setattr__(self, "risk", RiskLevel.coerce(self.risk))
        if isinstance(self.risk_signals, (str, bytes)) or not isinstance(
            self.risk_signals, Iterable
        ):
            raise InvalidExecutionPolicyError(
                "PolicyDecision.risk_signals must be a sequence of RiskSignal items."
            )
        normalized_signals = tuple(
            s if isinstance(s, RiskSignal) else RiskSignal.from_dict(s)  # type: ignore[arg-type]
            for s in self.risk_signals
        )
        object.__setattr__(self, "risk_signals", normalized_signals)
        object.__setattr__(
            self,
            "workspace",
            WorkspaceRequirement.coerce(self.workspace),
        )
        if isinstance(self.gates, (str, bytes)) or not isinstance(
            self.gates, Iterable
        ):
            raise InvalidExecutionPolicyError(
                "PolicyDecision.gates must be a sequence of GateRequirement items."
            )
        normalized_gates = tuple(
            g if isinstance(g, GateRequirement) else GateRequirement.from_dict(g)  # type: ignore[arg-type]
            for g in self.gates
        )
        seen_gate_ids: set[str] = set()
        for gate in normalized_gates:
            if gate.id in seen_gate_ids:
                raise InvalidExecutionPolicyError(
                    f"Duplicate gate requirement '{gate.id}' in PolicyDecision."
                )
            seen_gate_ids.add(gate.id)
        object.__setattr__(self, "gates", normalized_gates)

        if isinstance(self.reasons, (str, bytes)) or not isinstance(
            self.reasons, Iterable
        ):
            raise InvalidExecutionPolicyError(
                "PolicyDecision.reasons must be a sequence of strings."
            )
        normalized_reasons: list[str] = []
        for item in self.reasons:
            if not isinstance(item, str) or not item.strip():
                raise InvalidExecutionPolicyError(
                    "PolicyDecision.reasons entries must be non-empty strings."
                )
            cleaned = item.strip()
            if cleaned not in normalized_reasons:
                normalized_reasons.append(cleaned)
        object.__setattr__(self, "reasons", tuple(normalized_reasons))

    def to_dict(self) -> dict[str, object]:
        return {
            "classification": self.classification.value,
            "risk": self.risk.label,
            "risk_signals": [s.to_dict() for s in self.risk_signals],
            "workspace": self.workspace.value,
            "gates": [g.to_dict() for g in self.gates],
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "PolicyDecision":
        if not isinstance(payload, Mapping):
            raise InvalidExecutionPolicyError(
                "PolicyDecision payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_POLICY_DECISION_KEYS
        if unknown:
            raise InvalidExecutionPolicyError(
                f"Unexpected fields in PolicyDecision: {sorted(unknown)}."
            )
        missing = CANONICAL_POLICY_DECISION_KEYS - set(payload.keys())
        if missing:
            raise InvalidExecutionPolicyError(
                f"Missing required fields in PolicyDecision: {sorted(missing)}."
            )
        raw_signals = payload["risk_signals"]
        raw_gates = payload["gates"]
        raw_reasons = payload["reasons"]
        if not isinstance(raw_signals, list):
            raise InvalidExecutionPolicyError(
                "PolicyDecision 'risk_signals' must be a list."
            )
        if not isinstance(raw_gates, list):
            raise InvalidExecutionPolicyError(
                "PolicyDecision 'gates' must be a list."
            )
        if not isinstance(raw_reasons, list):
            raise InvalidExecutionPolicyError(
                "PolicyDecision 'reasons' must be a list."
            )
        return cls(
            classification=ExecutionClass.coerce(payload["classification"]),
            risk=RiskLevel.coerce(payload["risk"]),
            risk_signals=tuple(RiskSignal.from_dict(s) for s in raw_signals),
            workspace=WorkspaceRequirement.coerce(payload["workspace"]),
            gates=tuple(GateRequirement.from_dict(g) for g in raw_gates),
            reasons=tuple(raw_reasons),
        )


DEFAULT_ARCHITECTURAL_TAGS: tuple[str, ...] = (
    "architecture",
    "architectural",
    "auth",
    "authentication",
    "authorization",
    "ci",
    "database-migration",
    "database-schema",
    "deployment",
    "infra",
    "infrastructure",
    "migration",
    "migrations",
    "schema",
    "security",
)

DEFAULT_ARCHITECTURAL_PATH_PREFIXES: tuple[str, ...] = (
    ".github/workflows/",
    "alembic/",
    "auth/",
    "deploy/",
    "infra/",
    "migrations/",
    "prisma/",
    "security/",
    "supabase/migrations/",
    "terraform/",
)

DEFAULT_HIGH_RISK_TAGS: tuple[str, ...] = (
    "architecture",
    "auth",
    "authentication",
    "ci",
    "database-migration",
    "database-schema",
    "deployment",
    "infra",
    "infrastructure",
    "migration",
    "migrations",
    "security",
)

DEFAULT_CRITICAL_RISK_TAGS: tuple[str, ...] = (
    "auth-migration",
    "breaking-change",
    "critical",
    "destructive-migration",
    "production-auth",
    "production-migration",
    "security-critical",
)

DEFAULT_WORKSPACE_BY_RISK: Mapping[str, str] = {
    "low": WorkspaceRequirement.CURRENT_ALLOWED.value,
    "medium": WorkspaceRequirement.CURRENT_ALLOWED.value,
    "high": WorkspaceRequirement.ISOLATED_REQUIRED.value,
    "critical": WorkspaceRequirement.ISOLATED_REQUIRED.value,
}

DEFAULT_WAIVABLE_GATE_IDS: tuple[str, ...] = (
    "gate.review",
    "gate.tests",
)

CANONICAL_GATE_CATALOG: Mapping[str, tuple[GateKind, GatePhase, str]] = {
    "gate.workspace-isolation": (
        GateKind.WORKSPACE_ISOLATION,
        GatePhase.PRE_EXECUTION,
        "High or critical risk work requires an isolated workspace declaration.",
    ),
    "gate.baseline": (
        GateKind.BASELINE_CHECK,
        GatePhase.PRE_EXECUTION,
        "Verify repository baseline health before executing changes.",
    ),
    "gate.manual-approval": (
        GateKind.MANUAL_APPROVAL,
        GatePhase.PRE_EXECUTION,
        "Critical risk execution requires explicit pre-execution manual approval.",
    ),
    "gate.tests": (
        GateKind.IMPLEMENTATION_TESTS,
        GatePhase.POST_EXECUTION,
        "Implementation changes require test verification before completion.",
    ),
    "gate.review": (
        GateKind.PEER_REVIEW,
        GatePhase.POST_EXECUTION,
        "High or critical risk execution requires architectural/peer review.",
    ),
    "gate.security-review": (
        GateKind.SECURITY_REVIEW,
        GatePhase.POST_EXECUTION,
        "Security or authentication changes require dedicated security review.",
    ),
    "gate.migration-review": (
        GateKind.MIGRATION_REVIEW,
        GatePhase.POST_EXECUTION,
        "Database or schema migration changes require migration review.",
    ),
    "gate.final-verification": (
        GateKind.FINAL_VERIFICATION,
        GatePhase.POST_EXECUTION,
        "All executions require final contractual verification.",
    ),
}

CANONICAL_GATE_ORDER: tuple[str, ...] = (
    "gate.workspace-isolation",
    "gate.baseline",
    "gate.manual-approval",
    "gate.tests",
    "gate.review",
    "gate.security-review",
    "gate.migration-review",
    "gate.final-verification",
)

DEFAULT_GATES_BY_RISK: Mapping[RiskLevel, tuple[str, ...]] = {
    RiskLevel.LOW: ("gate.final-verification",),
    RiskLevel.MEDIUM: (
        "gate.baseline",
        "gate.tests",
        "gate.final-verification",
    ),
    RiskLevel.HIGH: (
        "gate.workspace-isolation",
        "gate.baseline",
        "gate.tests",
        "gate.review",
        "gate.final-verification",
    ),
    RiskLevel.CRITICAL: (
        "gate.workspace-isolation",
        "gate.baseline",
        "gate.manual-approval",
        "gate.tests",
        "gate.review",
        "gate.final-verification",
    ),
}


def _normalize_token_tuple(
    values: Iterable[object],
    label: str,
    *,
    require_Minimum: Iterable[str] = (),
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise InvalidExecutionPolicyError(f"{label} must be a list of strings.")
    cleaned: set[str] = set()
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise InvalidExecutionPolicyError(
                f"{label} entries must be non-empty strings."
            )
        cleaned.add(item.strip().lower())
    missing_defaults = set(require_Minimum) - cleaned
    if missing_defaults:
        raise PolicyViolationError(
            f"Policy cannot remove built-in {label} entries: {sorted(missing_defaults)}.",
            code="RAPID1006",
        )
    return tuple(sorted(cleaned))


@dataclass(frozen=True)
class ExecutionPolicy:
    schema_version: int = EXECUTION_POLICY_SCHEMA_VERSION
    minimum_classification: ExecutionClass = ExecutionClass.SPIKE
    minimum_risk: RiskLevel = RiskLevel.LOW
    architectural_tags: tuple[str, ...] = DEFAULT_ARCHITECTURAL_TAGS
    architectural_path_prefixes: tuple[str, ...] = DEFAULT_ARCHITECTURAL_PATH_PREFIXES
    high_risk_tags: tuple[str, ...] = DEFAULT_HIGH_RISK_TAGS
    critical_risk_tags: tuple[str, ...] = DEFAULT_CRITICAL_RISK_TAGS
    workspace_by_risk: Mapping[str, str] = field(
        default_factory=lambda: dict(DEFAULT_WORKSPACE_BY_RISK)
    )
    waivable_gate_ids: tuple[str, ...] = DEFAULT_WAIVABLE_GATE_IDS
    extra_required_gate_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != EXECUTION_POLICY_SCHEMA_VERSION
        ):
            raise InvalidExecutionPolicyError(
                f"Unsupported ExecutionPolicy schema_version '{self.schema_version}': expected {EXECUTION_POLICY_SCHEMA_VERSION}."
            )
        object.__setattr__(
            self,
            "minimum_classification",
            ExecutionClass.coerce(self.minimum_classification),
        )
        object.__setattr__(
            self,
            "minimum_risk",
            RiskLevel.coerce(self.minimum_risk),
        )
        object.__setattr__(
            self,
            "architectural_tags",
            _normalize_token_tuple(
                self.architectural_tags,
                "architectural_tags",
                require_Minimum=DEFAULT_ARCHITECTURAL_TAGS,
            ),
        )
        object.__setattr__(
            self,
            "architectural_path_prefixes",
            _normalize_token_tuple(
                self.architectural_path_prefixes,
                "architectural_path_prefixes",
                require_Minimum=DEFAULT_ARCHITECTURAL_PATH_PREFIXES,
            ),
        )
        object.__setattr__(
            self,
            "high_risk_tags",
            _normalize_token_tuple(
                self.high_risk_tags,
                "high_risk_tags",
                require_Minimum=DEFAULT_HIGH_RISK_TAGS,
            ),
        )
        object.__setattr__(
            self,
            "critical_risk_tags",
            _normalize_token_tuple(
                self.critical_risk_tags,
                "critical_risk_tags",
                require_Minimum=DEFAULT_CRITICAL_RISK_TAGS,
            ),
        )

        if not isinstance(self.workspace_by_risk, Mapping):
            raise InvalidExecutionPolicyError(
                "ExecutionPolicy.workspace_by_risk must be a JSON object."
            )
        expected_risk_keys = {"low", "medium", "high", "critical"}
        if set(self.workspace_by_risk.keys()) != expected_risk_keys:
            raise InvalidExecutionPolicyError(
                f"ExecutionPolicy.workspace_by_risk must contain exactly keys {sorted(expected_risk_keys)}."
            )
        normalized_workspace: dict[str, str] = {}
        for risk_key in ("low", "medium", "high", "critical"):
            req = WorkspaceRequirement.coerce(self.workspace_by_risk[risk_key])
            default_req = WorkspaceRequirement.coerce(
                DEFAULT_WORKSPACE_BY_RISK[risk_key]
            )
            if req.rank < default_req.rank:
                raise PolicyViolationError(
                    f"Policy cannot downgrade workspace requirement for risk '{risk_key}' below '{default_req.value}'.",
                    code="RAPID1006",
                )
            normalized_workspace[risk_key] = req.value
        object.__setattr__(self, "workspace_by_risk", normalized_workspace)

        if isinstance(self.waivable_gate_ids, (str, bytes)) or not isinstance(
            self.waivable_gate_ids, Iterable
        ):
            raise InvalidExecutionPolicyError(
                "ExecutionPolicy.waivable_gate_ids must be a list of gate IDs."
            )
        waivable_set: set[str] = set()
        for gate_id in self.waivable_gate_ids:
            if not isinstance(gate_id, str) or gate_id not in CANONICAL_GATE_CATALOG:
                raise InvalidExecutionPolicyError(
                    f"Unknown gate ID '{gate_id}' in waivable_gate_ids."
                )
            if gate_id not in DEFAULT_WAIVABLE_GATE_IDS:
                raise PolicyViolationError(
                    f"Policy cannot mark non-waivable gate '{gate_id}' as waivable.",
                    code="RAPID1006",
                )
            waivable_set.add(gate_id)
        object.__setattr__(
            self,
            "waivable_gate_ids",
            tuple(sorted(waivable_set)),
        )

        if isinstance(self.extra_required_gate_ids, (str, bytes)) or not isinstance(
            self.extra_required_gate_ids, Iterable
        ):
            raise InvalidExecutionPolicyError(
                "ExecutionPolicy.extra_required_gate_ids must be a list of gate IDs."
            )
        extra_gates: set[str] = set()
        for gate_id in self.extra_required_gate_ids:
            if not isinstance(gate_id, str) or gate_id not in CANONICAL_GATE_CATALOG:
                raise InvalidExecutionPolicyError(
                    f"Unknown gate ID '{gate_id}' in extra_required_gate_ids."
                )
            extra_gates.add(gate_id)
        object.__setattr__(
            self,
            "extra_required_gate_ids",
            tuple(sorted(extra_gates)),
        )

    def workspace_for_risk(self, risk: RiskLevel) -> WorkspaceRequirement:
        coerced = RiskLevel.coerce(risk)
        return WorkspaceRequirement.coerce(self.workspace_by_risk[coerced.label])

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "minimum_classification": self.minimum_classification.value,
            "minimum_risk": self.minimum_risk.label,
            "architectural_tags": list(self.architectural_tags),
            "architectural_path_prefixes": list(self.architectural_path_prefixes),
            "high_risk_tags": list(self.high_risk_tags),
            "critical_risk_tags": list(self.critical_risk_tags),
            "workspace_by_risk": dict(self.workspace_by_risk),
            "waivable_gate_ids": list(self.waivable_gate_ids),
            "extra_required_gate_ids": list(self.extra_required_gate_ids),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @property
    def digest(self) -> str:
        return sha256_canonical_json(self.to_dict())

    def content_digest(self) -> str:
        return self.digest

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ExecutionPolicy":
        if not isinstance(payload, Mapping):
            raise InvalidExecutionPolicyError(
                "ExecutionPolicy payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_EXECUTION_POLICY_KEYS
        if unknown:
            raise InvalidExecutionPolicyError(
                f"Unexpected fields in ExecutionPolicy: {sorted(unknown)}."
            )
        if "schema_version" not in payload:
            raise InvalidExecutionPolicyError(
                "ExecutionPolicy is missing required field 'schema_version'."
            )
        return cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            minimum_classification=ExecutionClass.coerce(
                payload.get("minimum_classification", ExecutionClass.SPIKE.value)
            ),
            minimum_risk=RiskLevel.coerce(
                payload.get("minimum_risk", RiskLevel.LOW.label)
            ),
            architectural_tags=payload.get(
                "architectural_tags", DEFAULT_ARCHITECTURAL_TAGS
            ),  # type: ignore[arg-type]
            architectural_path_prefixes=payload.get(
                "architectural_path_prefixes", DEFAULT_ARCHITECTURAL_PATH_PREFIXES
            ),  # type: ignore[arg-type]
            high_risk_tags=payload.get("high_risk_tags", DEFAULT_HIGH_RISK_TAGS),  # type: ignore[arg-type]
            critical_risk_tags=payload.get(
                "critical_risk_tags", DEFAULT_CRITICAL_RISK_TAGS
            ),  # type: ignore[arg-type]
            workspace_by_risk=payload.get(
                "workspace_by_risk", DEFAULT_WORKSPACE_BY_RISK
            ),  # type: ignore[arg-type]
            waivable_gate_ids=payload.get(
                "waivable_gate_ids", DEFAULT_WAIVABLE_GATE_IDS
            ),  # type: ignore[arg-type]
            extra_required_gate_ids=payload.get("extra_required_gate_ids", ()),  # type: ignore[arg-type]
        )

    @classmethod
    def from_json(cls, raw: str) -> "ExecutionPolicy":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidExecutionPolicyError(
                f"Invalid ExecutionPolicy JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise InvalidExecutionPolicyError(
                "ExecutionPolicy JSON root must be an object."
            )
        return cls.from_dict(payload)


DEFAULT_EXECUTION_POLICY = ExecutionPolicy()


_MIGRATION_TAG_SET = frozenset(
    {
        "migration",
        "migrations",
        "database-migration",
        "database-schema",
        "schema",
        "db-migration",
    }
)
_MIGRATION_PATH_PREFIXES = (
    "migrations/",
    "alembic/",
    "prisma/",
    "supabase/migrations/",
)

_INFRA_TAG_SET = frozenset(
    {
        "infra",
        "infrastructure",
        "deployment",
        "terraform",
        "docker",
        "k8s",
        "kubernetes",
    }
)
_INFRA_PATH_PREFIXES = (
    "infra/",
    "terraform/",
    "deploy/",
)

_SECURITY_TAG_SET = frozenset(
    {
        "security",
        "owasp",
        "encryption",
        "secrets",
        "vulnerability",
    }
)
_SECURITY_PATH_PREFIXES = ("security/",)

_AUTH_TAG_SET = frozenset(
    {
        "auth",
        "authentication",
        "authorization",
        "oauth",
        "jwt",
        "rbac",
        "sso",
    }
)
_AUTH_PATH_PREFIXES = ("auth/",)

_CI_TAG_SET = frozenset(
    {
        "ci",
        "cd",
        "ci-cd",
        "github-actions",
        "pipeline",
    }
)
_CI_PATH_PREFIXES = (".github/workflows/",)

_ARCH_TAG_SET = frozenset(
    {
        "architecture",
        "architectural",
        "core-architecture",
    }
)

_EMPTY_DATA_IMPACT_TOKENS = frozenset(
    {
        "",
        "none",
        "n/a",
        "no",
        "nil",
        "sin impacto",
        "no especificado",
    }
)


class ExecutionPolicyEvaluator:
    """Pure, deterministic evaluator transforming `(SpecRevision, ExecutionPolicy)` into a `PolicyDecision`."""

    def evaluate(
        self,
        spec,
        policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
        *,
        requested_classification: ExecutionClass | str | None = None,
        requested_risk: RiskLevel | str | int | None = None,
    ) -> PolicyDecision:
        from rapid_os.domain.specs import SpecMode, SpecRevision

        if not isinstance(spec, SpecRevision):
            raise InvalidExecutionPolicyError(
                "ExecutionPolicyEvaluator.evaluate requires a SpecRevision instance."
            )
        if not isinstance(policy, ExecutionPolicy):
            raise InvalidExecutionPolicyError(
                "ExecutionPolicyEvaluator.evaluate requires an ExecutionPolicy instance."
            )

        signals: list[RiskSignal] = []
        reasons: list[str] = []

        # 1. Base classification and mode signal
        if spec.mode == SpecMode.RESEARCH:
            base_class = ExecutionClass.SPIKE
            signals.append(
                RiskSignal(
                    id="mode.research",
                    level=RiskLevel.LOW,
                    reason="Spec mode is 'research' (spike exploration).",
                    source="spec.mode",
                )
            )
            reasons.append("mode.research")
        elif spec.mode == SpecMode.HARDENING:
            base_class = ExecutionClass.ARCHITECTURAL
            signals.append(
                RiskSignal(
                    id="mode.hardening",
                    level=RiskLevel.HIGH,
                    reason="Spec mode is 'hardening' (architectural/security scope).",
                    source="spec.mode",
                )
            )
            reasons.append("mode.hardening")
        else:
            base_class = ExecutionClass.BOUNDED
            reasons.append(f"mode.{spec.mode.value}")

        tags = set(spec.tags)
        paths = tuple(p.lower() for p in spec.affected_paths)

        # 2. Structured domain signals from tags and affected_paths
        has_migration_tag = bool(tags & _MIGRATION_TAG_SET)
        has_migration_path = any(
            p.startswith(_MIGRATION_PATH_PREFIXES) or "/migrations/" in p
            for p in paths
        )
        if has_migration_tag or has_migration_path:
            src = "spec.tags" if has_migration_tag else "spec.affected_paths"
            signals.append(
                RiskSignal(
                    id="scope.database-migration",
                    level=RiskLevel.HIGH,
                    reason="Database schema or migration scope detected.",
                    source=src,
                )
            )
            reasons.append(
                "path.database-migration"
                if has_migration_path and not has_migration_tag
                else "scope.database-migration"
            )

        has_infra_tag = bool(tags & _INFRA_TAG_SET)
        has_infra_path = any(p.startswith(_INFRA_PATH_PREFIXES) for p in paths)
        if has_infra_tag or has_infra_path:
            src = "spec.tags" if has_infra_tag else "spec.affected_paths"
            signals.append(
                RiskSignal(
                    id="scope.infrastructure",
                    level=RiskLevel.HIGH,
                    reason="Infrastructure or deployment scope detected.",
                    source=src,
                )
            )
            reasons.append("scope.infrastructure")

        has_sec_tag = bool(tags & _SECURITY_TAG_SET)
        has_sec_path = any(p.startswith(_SECURITY_PATH_PREFIXES) for p in paths)
        if has_sec_tag or has_sec_path:
            src = "spec.tags" if has_sec_tag else "spec.affected_paths"
            signals.append(
                RiskSignal(
                    id="scope.security",
                    level=RiskLevel.HIGH,
                    reason="Security-sensitive scope detected.",
                    source=src,
                )
            )
            reasons.append("scope.security")

        has_auth_tag = bool(tags & _AUTH_TAG_SET)
        has_auth_path = any(p.startswith(_AUTH_PATH_PREFIXES) for p in paths)
        if has_auth_tag or has_auth_path:
            src = "spec.tags" if has_auth_tag else "spec.affected_paths"
            signals.append(
                RiskSignal(
                    id="scope.authentication",
                    level=RiskLevel.HIGH,
                    reason="Authentication or authorization scope detected.",
                    source=src,
                )
            )
            reasons.append("scope.authentication")

        has_ci_tag = bool(tags & _CI_TAG_SET)
        has_ci_path = any(p.startswith(_CI_PATH_PREFIXES) for p in paths)
        if has_ci_tag or has_ci_path:
            src = "spec.tags" if has_ci_tag else "spec.affected_paths"
            signals.append(
                RiskSignal(
                    id="scope.ci",
                    level=RiskLevel.HIGH,
                    reason="CI/CD workflow scope detected.",
                    source=src,
                )
            )
            reasons.append("scope.ci")

        has_arch_tag = bool(tags & _ARCH_TAG_SET)
        custom_arch_tag = bool(
            tags
            & (
                set(policy.architectural_tags)
                - _MIGRATION_TAG_SET
                - _INFRA_TAG_SET
                - _SECURITY_TAG_SET
                - _AUTH_TAG_SET
                - _CI_TAG_SET
            )
        )
        custom_arch_path = any(
            p.startswith(tuple(policy.architectural_path_prefixes))
            and not p.startswith(
                _MIGRATION_PATH_PREFIXES
                + _INFRA_PATH_PREFIXES
                + _SECURITY_PATH_PREFIXES
                + _AUTH_PATH_PREFIXES
                + _CI_PATH_PREFIXES
            )
            for p in paths
        )
        if has_arch_tag or custom_arch_tag or custom_arch_path:
            src = (
                "spec.tags"
                if (has_arch_tag or custom_arch_tag)
                else "spec.affected_paths"
            )
            signals.append(
                RiskSignal(
                    id="scope.architecture",
                    level=RiskLevel.HIGH,
                    reason="Explicit architectural tag or path scope detected.",
                    source=src,
                )
            )
            reasons.append("scope.architecture")

        cleaned_data_impact = (spec.data_impact or "").strip()
        if cleaned_data_impact.lower() not in _EMPTY_DATA_IMPACT_TOKENS:
            signals.append(
                RiskSignal(
                    id="data.impact",
                    level=RiskLevel.MEDIUM,
                    reason="Spec declares non-empty data impact.",
                    source="spec.data_impact",
                )
            )
            reasons.append("data.impact")

        # Critical tags
        matched_critical_tags = sorted(tags & set(policy.critical_risk_tags))
        if matched_critical_tags:
            signals.append(
                RiskSignal(
                    id="scope.critical-impact",
                    level=RiskLevel.CRITICAL,
                    reason=f"Critical risk tag(s) present: {', '.join(matched_critical_tags)}.",
                    source="spec.tags",
                )
            )
            reasons.append("scope.critical-impact")

        # Custom high risk tags from project policy
        matched_custom_high = sorted(
            tags
            & (
                set(policy.high_risk_tags)
                - _MIGRATION_TAG_SET
                - _INFRA_TAG_SET
                - _SECURITY_TAG_SET
                - _AUTH_TAG_SET
                - _CI_TAG_SET
                - _ARCH_TAG_SET
            )
        )
        if matched_custom_high:
            signals.append(
                RiskSignal(
                    id="policy.high-risk-tag",
                    level=RiskLevel.HIGH,
                    reason=f"Policy high-risk tag(s) present: {', '.join(matched_custom_high)}.",
                    source="policy.high_risk_tags",
                )
            )
            reasons.append("policy.high-risk-tag")

        # 3. Determine calculated ExecutionClass
        elevating_signal_ids = {
            "mode.hardening",
            "scope.database-migration",
            "scope.infrastructure",
            "scope.security",
            "scope.authentication",
            "scope.ci",
            "scope.architecture",
            "scope.critical-impact",
            "policy.high-risk-tag",
            "data.impact",
        }
        has_architectural_signal = any(
            s.id in elevating_signal_ids for s in signals
        )
        calculated_class = base_class
        if has_architectural_signal and calculated_class != ExecutionClass.ARCHITECTURAL:
            calculated_class = ExecutionClass.ARCHITECTURAL

        if policy.minimum_classification.rank > calculated_class.rank:
            calculated_class = policy.minimum_classification
            reasons.append(
                f"policy.minimum_classification:{policy.minimum_classification.value}"
            )

        if requested_classification is not None:
            coerced_req_class = ExecutionClass.coerce(requested_classification)
            if coerced_req_class.rank < calculated_class.rank:
                raise PolicyViolationError(
                    f"Policy violation: requested classification '{coerced_req_class.value}' cannot downgrade calculated classification '{calculated_class.value}'.",
                    code="RAPID1006",
                )
            if coerced_req_class.rank > calculated_class.rank:
                calculated_class = coerced_req_class
                reasons.append(
                    f"override.classification:{coerced_req_class.value}"
                )

        if calculated_class == ExecutionClass.ARCHITECTURAL and not any(
            s.id == "classification.architectural" for s in signals
        ):
            signals.append(
                RiskSignal(
                    id="classification.architectural",
                    level=RiskLevel.HIGH,
                    reason="Execution classification is architectural.",
                    source="policy.classification",
                )
            )
            if "classification.architectural" not in reasons:
                reasons.append("classification.architectural")

        # 4. Determine calculated RiskLevel
        base_risk_by_class = {
            ExecutionClass.SPIKE: RiskLevel.LOW,
            ExecutionClass.BOUNDED: RiskLevel.MEDIUM,
            ExecutionClass.ARCHITECTURAL: RiskLevel.HIGH,
        }
        calculated_risk = base_risk_by_class[calculated_class]
        for sig in signals:
            if sig.level > calculated_risk:
                calculated_risk = sig.level
        if policy.minimum_risk > calculated_risk:
            calculated_risk = policy.minimum_risk
            signals.append(
                RiskSignal(
                    id="policy.minimum-risk",
                    level=policy.minimum_risk,
                    reason=f"Project policy enforces minimum risk '{policy.minimum_risk.label}'.",
                    source="policy.minimum_risk",
                )
            )
            reasons.append(f"policy.minimum_risk:{policy.minimum_risk.label}")

        if requested_risk is not None:
            coerced_req_risk = RiskLevel.coerce(requested_risk)
            if coerced_req_risk < calculated_risk:
                raise PolicyViolationError(
                    f"Policy violation: requested risk '{coerced_req_risk.label}' cannot downgrade calculated risk '{calculated_risk.label}'.",
                    code="RAPID1006",
                )
            if coerced_req_risk > calculated_risk:
                calculated_risk = coerced_req_risk
                signals.append(
                    RiskSignal(
                        id="override.risk",
                        level=coerced_req_risk,
                        reason=f"Explicit user escalation to '{coerced_req_risk.label}' risk.",
                        source="cli.override",
                    )
                )
                reasons.append(f"override.risk:{coerced_req_risk.label}")

        # 5. Determine WorkspaceRequirement
        workspace = policy.workspace_for_risk(calculated_risk)

        # 6. Determine required Gates in canonical order without duplicates
        selected_gate_ids: set[str] = set(DEFAULT_GATES_BY_RISK[calculated_risk])
        if workspace == WorkspaceRequirement.ISOLATED_REQUIRED:
            selected_gate_ids.add("gate.workspace-isolation")

        signal_ids = {s.id for s in signals}
        if signal_ids & {"scope.security", "scope.authentication"}:
            selected_gate_ids.add("gate.security-review")
        if "scope.database-migration" in signal_ids:
            selected_gate_ids.add("gate.migration-review")

        selected_gate_ids.update(policy.extra_required_gate_ids)

        waivable_set = set(policy.waivable_gate_ids)
        ordered_gates: list[GateRequirement] = []
        for gate_id in CANONICAL_GATE_ORDER:
            if gate_id not in selected_gate_ids:
                continue
            kind, phase, gate_reason = CANONICAL_GATE_CATALOG[gate_id]
            ordered_gates.append(
                GateRequirement(
                    id=gate_id,
                    kind=kind,
                    phase=phase,
                    required=True,
                    waivable=(
                        gate_id in waivable_set
                        and calculated_risk < RiskLevel.CRITICAL
                    ),
                    reason=gate_reason,
                )
            )

        return PolicyDecision(
            classification=calculated_class,
            risk=calculated_risk,
            risk_signals=tuple(signals),
            workspace=workspace,
            gates=tuple(ordered_gates),
            reasons=tuple(reasons),
        )

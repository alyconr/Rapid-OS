from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import re
from typing import Iterable, Mapping

from rapid_os.domain.capabilities import (
    CANONICAL_CAPABILITY_IDS,
    CapabilityRequirement,
    CapabilityRequirementResolver,
)
from rapid_os.domain.evidence import (
    EvidenceError,
    EvidenceKind,
    InvalidEvidenceReferenceError,
    RunEvidence,
    compute_evidence_set_digest,
    parse_evidence_ordinal,
    validate_evidence_id,
)
from rapid_os.domain.execution import (
    ExecutionContract,
    ExecutionError,
    GateDisposition,
    GateKind,
    GateRequirement,
    GateState,
    RunState,
    RunStatus,
    TaskState,
    TaskStatus,
    validate_run_id,
    verify_run_state_against_contract,
)
from rapid_os.domain.harnesses import HarnessCapabilityError
from rapid_os.domain.policy import sha256_canonical_json


EVALUATION_REPORT_SCHEMA_VERSION = 1
BEHAVIORAL_RULESET_VERSION = 1

SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
ASSERTION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
EVAL_REPORT_FILE_RE = re.compile(r"^(?P<num>\d{4,})\.json$")

ASSERTION_CATEGORIES = frozenset(
    {
        "lifecycle",
        "task",
        "gate",
        "capability",
    }
)

NON_OBSERVABLE_CAPABILITY_IDS = frozenset(
    {
        "context.consume",
        "repository.read",
    }
)

TASK_EVIDENCE_KINDS = frozenset(
    {
        EvidenceKind.COMMAND_RESULT,
        EvidenceKind.TEST_RESULT,
        EvidenceKind.FILE_CHANGE,
        EvidenceKind.GIT_RESULT,
        EvidenceKind.TOOL_INVOCATION,
        EvidenceKind.DELEGATION,
        EvidenceKind.ARTIFACT,
    }
)

REVIEW_GATE_KIND_TO_REVIEW_TYPE: Mapping[GateKind, str] = {
    GateKind.PEER_REVIEW: "peer",
    GateKind.SECURITY_REVIEW: "security",
    GateKind.MIGRATION_REVIEW: "migration",
    GateKind.MANUAL_APPROVAL: "manual",
    GateKind.FINAL_VERIFICATION: "final",
}


class EvaluationError(ValueError):
    """Base domain error for Phase 6 Behavioral Evaluation operations (RAPID1221-RAPID1239)."""

    default_code = "RAPID1221"

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


class InvalidEvaluationReportError(EvaluationError):
    default_code = "RAPID1221"


class EvaluationReportDigestMismatchError(EvaluationError):
    default_code = "RAPID1222"


class EvaluationBindingMismatchError(EvaluationError):
    default_code = "RAPID1223"


class UnsafeEvaluationPathError(EvaluationError):
    default_code = "RAPID1224"


class EvaluationUnverifiedError(EvaluationError):
    default_code = "RAPID1225"


class EvaluationFailedError(EvaluationError):
    default_code = "RAPID1226"


class EvaluationReportNotFoundError(EvaluationError):
    default_code = "RAPID1228"


class EvaluationOverwriteError(EvaluationError):
    default_code = "RAPID1229"


def _validate_sha256(
    value: object,
    label: str,
    error_cls=InvalidEvaluationReportError,
) -> str:
    if not isinstance(value, str) or not SHA256_HEX_RE.match(value):
        raise error_cls(
            f"Invalid {label} '{value}': must be a 64-character lowercase hex SHA-256 digest."
        )
    return value


def format_eval_report_file_name(revision: int) -> str:
    """Format 1-based evaluation report revision as `0001.json`, `0002.json`, ..."""
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise InvalidEvaluationReportError(
            f"Invalid evaluation report revision '{revision}': must be a positive integer."
        )
    return f"{revision:04d}.json"


def is_canonical_eval_report_file_name(name: str) -> bool:
    """Return True if `name` is a canonical evaluation report filename (`0001.json`, ...)."""
    if not isinstance(name, str):
        return False
    match = EVAL_REPORT_FILE_RE.match(name)
    if not match:
        return False
    raw = match.group("num")
    num = int(raw)
    return num >= 1 and raw == f"{num:04d}"


def parse_eval_report_revision(name_or_rev: object) -> int:
    if isinstance(name_or_rev, int) and not isinstance(name_or_rev, bool):
        if name_or_rev < 1:
            raise InvalidEvaluationReportError(
                f"Invalid evaluation report revision '{name_or_rev}': must be >= 1."
            )
        return name_or_rev
    if isinstance(name_or_rev, str):
        cleaned = name_or_rev.strip()
        if cleaned.endswith(".json"):
            if not is_canonical_eval_report_file_name(cleaned):
                raise InvalidEvaluationReportError(
                    f"Invalid evaluation report filename '{name_or_rev}'."
                )
            return int(cleaned[:-5])
        if cleaned.isdigit():
            rev = int(cleaned)
            if rev >= 1:
                return rev
    raise InvalidEvaluationReportError(
        f"Invalid evaluation report revision '{name_or_rev}'."
    )


@dataclass(frozen=True)
class BehavioralRule:
    id: str
    category: str
    version: int
    description: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "category": self.category,
            "version": self.version,
            "description": self.description,
        }


DEFAULT_BEHAVIORAL_RULESET: tuple[BehavioralRule, ...] = (
    BehavioralRule(
        id="rule.run.lifecycle.v1",
        category="lifecycle",
        version=1,
        description="Run status FINISHED is PASS; FAILED or CANCELLED is FAIL; PREPARED, ACTIVE, or BLOCKED is UNVERIFIED.",
    ),
    BehavioralRule(
        id="rule.task.evidence.v1",
        category="task",
        version=1,
        description="Tasks in DONE require at least one non-failing execution evidence item linked via task_ids; SKIPPED tasks are NOT_APPLICABLE; incomplete tasks are UNVERIFIED.",
    ),
    BehavioralRule(
        id="rule.gate.disposition.v1",
        category="gate",
        version=1,
        description="Pending gates are always UNVERIFIED; waived gates are WAIVED; acknowledged gates require valid gate-specific evidence to PASS and remain UNVERIFIED without evidence.",
    ),
    BehavioralRule(
        id="rule.gate.implementation_tests.v1",
        category="gate",
        version=1,
        description="IMPLEMENTATION_TESTS gates require ACKNOWLEDGED disposition plus artifact-backed TEST_RESULT evidence with exit_code == 0 and failed == 0.",
    ),
    BehavioralRule(
        id="rule.gate.baseline_check.v1",
        category="gate",
        version=1,
        description="BASELINE_CHECK gates require ACKNOWLEDGED disposition plus artifact-backed COMMAND_RESULT or TEST_RESULT evidence with exit_code == 0 (and failed == 0 for TEST_RESULT).",
    ),
    BehavioralRule(
        id="rule.gate.workspace_isolation.v1",
        category="gate",
        version=1,
        description="WORKSPACE_ISOLATION gates require ACKNOWLEDGED disposition plus WORKSPACE evidence with mode == 'isolated'.",
    ),
    BehavioralRule(
        id="rule.gate.review.v1",
        category="gate",
        version=1,
        description="Review gates require ACKNOWLEDGED disposition plus REVIEW evidence matching review_type with outcome == 'approved' (changes_requested or rejected produces FAIL).",
    ),
    BehavioralRule(
        id="rule.gate.multi_evidence_conservative.v1",
        category="gate",
        version=1,
        description="When multiple evidence items apply to a gate, any explicit failure dominates passing evidence (any FAIL -> FAIL, else any PASS -> PASS, else UNVERIFIED).",
    ),
    BehavioralRule(
        id="rule.capability.observation.v1",
        category="capability",
        version=1,
        description="Observable required capabilities must be backed by matching non-failing evidence; context.consume and repository.read are NOT_APPLICABLE in Evidence Engine v1.",
    ),
    BehavioralRule(
        id="rule.verdict.precedence.v1",
        category="verdict",
        version=1,
        description="Overall verdict precedence: lifecycle FAIL or any required FAIL -> FAIL; else any required UNVERIFIED -> UNVERIFIED; else any required WAIVED -> PASS_WITH_WAIVERS; else PASS.",
    ),
)


def compute_ruleset_digest(
    rules: Iterable[BehavioralRule] = DEFAULT_BEHAVIORAL_RULESET,
    *,
    version: int = BEHAVIORAL_RULESET_VERSION,
) -> str:
    """Compute canonical SHA-256 digest of the active behavioral evaluation ruleset."""
    ordered = sorted(rules, key=lambda r: r.id)
    payload = {
        "ruleset_version": version,
        "rules": [r.to_dict() for r in ordered],
    }
    return sha256_canonical_json(payload)


DEFAULT_BEHAVIORAL_RULESET_DIGEST = compute_ruleset_digest()


class EvalAssertionStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNVERIFIED = "unverified"
    WAIVED = "waived"
    NOT_APPLICABLE = "not_applicable"

    @classmethod
    def coerce(cls, value: object) -> "EvalAssertionStatus":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidEvaluationReportError(
            f"Invalid EvalAssertionStatus '{value}': expected one of {[m.value for m in cls]}."
        )


class EvaluationVerdict(str, Enum):
    PASS = "pass"
    PASS_WITH_WAIVERS = "pass_with_waivers"
    FAIL = "fail"
    UNVERIFIED = "unverified"

    @classmethod
    def coerce(cls, value: object) -> "EvaluationVerdict":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidEvaluationReportError(
            f"Invalid EvaluationVerdict '{value}': expected one of {[m.value for m in cls]}."
        )


CANONICAL_EVAL_ASSERTION_KEYS = frozenset(
    {
        "id",
        "category",
        "subject_id",
        "required",
        "status",
        "reason",
        "evidence_ids",
    }
)


@dataclass(frozen=True)
class EvalAssertion:
    id: str
    category: str
    subject_id: str
    required: bool
    status: EvalAssertionStatus
    reason: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if (
            not isinstance(self.id, str)
            or not self.id.strip()
            or self.id != self.id.strip()
            or not ASSERTION_ID_RE.match(self.id)
        ):
            raise InvalidEvaluationReportError(
                f"Invalid EvalAssertion.id '{self.id}'."
            )
        if (
            not isinstance(self.category, str)
            or self.category not in ASSERTION_CATEGORIES
        ):
            raise InvalidEvaluationReportError(
                f"Invalid EvalAssertion.category '{self.category}': expected one of {sorted(ASSERTION_CATEGORIES)}."
            )
        if (
            not isinstance(self.subject_id, str)
            or not self.subject_id.strip()
            or self.subject_id != self.subject_id.strip()
        ):
            raise InvalidEvaluationReportError(
                f"Invalid EvalAssertion.subject_id '{self.subject_id}'."
            )
        if not isinstance(self.required, bool):
            raise InvalidEvaluationReportError(
                "EvalAssertion.required must be a boolean."
            )
        object.__setattr__(
            self,
            "status",
            EvalAssertionStatus.coerce(self.status),
        )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidEvaluationReportError(
                f"EvalAssertion.reason for '{self.id}' must be a non-empty string."
            )
        object.__setattr__(self, "reason", self.reason.strip())

        if isinstance(self.evidence_ids, (str, bytes)) or not isinstance(
            self.evidence_ids, Iterable
        ):
            raise InvalidEvaluationReportError(
                f"EvalAssertion.evidence_ids for '{self.id}' must be a sequence of evidence IDs."
            )
        normalized_ev_ids: list[str] = []
        seen_ev_ids: set[str] = set()
        for raw_ev in self.evidence_ids:
            try:
                validated_ev = validate_evidence_id(
                    raw_ev,
                    f"EvalAssertion '{self.id}' evidence_id",
                )
            except EvidenceError as exc:
                raise InvalidEvaluationReportError(str(exc)) from exc
            if validated_ev not in seen_ev_ids:
                seen_ev_ids.add(validated_ev)
                normalized_ev_ids.append(validated_ev)
        normalized_ev_ids.sort(key=parse_evidence_ordinal)
        object.__setattr__(self, "evidence_ids", tuple(normalized_ev_ids))

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "category": self.category,
            "subject_id": self.subject_id,
            "required": self.required,
            "status": self.status.value,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "EvalAssertion":
        if not isinstance(payload, Mapping):
            raise InvalidEvaluationReportError(
                "EvalAssertion payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_EVAL_ASSERTION_KEYS
        if unknown:
            raise InvalidEvaluationReportError(
                f"Unexpected fields in EvalAssertion: {sorted(unknown)}."
            )
        missing = CANONICAL_EVAL_ASSERTION_KEYS - set(payload.keys())
        if missing:
            raise InvalidEvaluationReportError(
                f"Missing required fields in EvalAssertion: {sorted(missing)}."
            )
        return cls(
            id=payload["id"],  # type: ignore[arg-type]
            category=payload["category"],  # type: ignore[arg-type]
            subject_id=payload["subject_id"],  # type: ignore[arg-type]
            required=payload["required"],  # type: ignore[arg-type]
            status=EvalAssertionStatus.coerce(payload["status"]),
            reason=payload["reason"],  # type: ignore[arg-type]
            evidence_ids=payload["evidence_ids"],  # type: ignore[arg-type]
        )


def compute_evaluation_verdict(
    assertions: Iterable[EvalAssertion],
) -> EvaluationVerdict:
    """Compute overall `EvaluationVerdict` from `assertions` according to Phase 6 precedence rules."""
    assertion_tuple = tuple(assertions)
    if not assertion_tuple:
        raise InvalidEvaluationReportError(
            "EvaluationReport must contain at least one assertion."
        )

    for item in assertion_tuple:
        if (
            item.id == "run.lifecycle"
            and item.status == EvalAssertionStatus.FAIL
        ):
            return EvaluationVerdict.FAIL

    if any(
        item.required and item.status == EvalAssertionStatus.FAIL
        for item in assertion_tuple
    ):
        return EvaluationVerdict.FAIL

    if any(
        item.required and item.status == EvalAssertionStatus.UNVERIFIED
        for item in assertion_tuple
    ):
        return EvaluationVerdict.UNVERIFIED

    if any(
        item.required and item.status == EvalAssertionStatus.WAIVED
        for item in assertion_tuple
    ):
        return EvaluationVerdict.PASS_WITH_WAIVERS

    return EvaluationVerdict.PASS


CANONICAL_EVALUATION_REPORT_KEYS = frozenset(
    {
        "schema_version",
        "run_id",
        "contract_digest",
        "state_revision",
        "state_digest",
        "evidence_set_digest",
        "ruleset_version",
        "ruleset_digest",
        "assertions",
        "verdict",
        "report_digest",
    }
)


@dataclass(frozen=True)
class EvaluationReport:
    schema_version: int
    run_id: str
    contract_digest: str
    state_revision: int
    state_digest: str
    evidence_set_digest: str
    ruleset_version: int
    ruleset_digest: str
    assertions: tuple[EvalAssertion, ...]
    verdict: EvaluationVerdict
    report_digest: str = ""

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != EVALUATION_REPORT_SCHEMA_VERSION
        ):
            raise InvalidEvaluationReportError(
                f"Unsupported EvaluationReport schema_version '{self.schema_version}': expected {EVALUATION_REPORT_SCHEMA_VERSION}."
            )
        try:
            validated_run_id = validate_run_id(
                self.run_id,
                "EvaluationReport.run_id",
            )
        except ExecutionError as exc:
            raise InvalidEvaluationReportError(str(exc)) from exc
        object.__setattr__(self, "run_id", validated_run_id)

        object.__setattr__(
            self,
            "contract_digest",
            _validate_sha256(
                self.contract_digest,
                "EvaluationReport.contract_digest",
                InvalidEvaluationReportError,
            ),
        )
        if (
            isinstance(self.state_revision, bool)
            or not isinstance(self.state_revision, int)
            or self.state_revision < 1
        ):
            raise InvalidEvaluationReportError(
                f"Invalid EvaluationReport.state_revision '{self.state_revision}': must be a positive integer."
            )
        object.__setattr__(
            self,
            "state_digest",
            _validate_sha256(
                self.state_digest,
                "EvaluationReport.state_digest",
                InvalidEvaluationReportError,
            ),
        )
        object.__setattr__(
            self,
            "evidence_set_digest",
            _validate_sha256(
                self.evidence_set_digest,
                "EvaluationReport.evidence_set_digest",
                InvalidEvaluationReportError,
            ),
        )
        if (
            isinstance(self.ruleset_version, bool)
            or not isinstance(self.ruleset_version, int)
            or self.ruleset_version != BEHAVIORAL_RULESET_VERSION
        ):
            raise InvalidEvaluationReportError(
                f"Unsupported EvaluationReport ruleset_version '{self.ruleset_version}': expected {BEHAVIORAL_RULESET_VERSION}."
            )
        object.__setattr__(
            self,
            "ruleset_digest",
            _validate_sha256(
                self.ruleset_digest,
                "EvaluationReport.ruleset_digest",
                InvalidEvaluationReportError,
            ),
        )

        if isinstance(self.assertions, (str, bytes)) or not isinstance(
            self.assertions, Iterable
        ):
            raise InvalidEvaluationReportError(
                "EvaluationReport.assertions must be a non-empty sequence of EvalAssertion items."
            )
        normalized_assertions: list[EvalAssertion] = []
        seen_assertion_ids: set[str] = set()
        for item in self.assertions:
            assertion_obj = (
                item
                if isinstance(item, EvalAssertion)
                else EvalAssertion.from_dict(item)  # type: ignore[arg-type]
            )
            if assertion_obj.id in seen_assertion_ids:
                raise InvalidEvaluationReportError(
                    f"Duplicate assertion ID '{assertion_obj.id}' in EvaluationReport."
                )
            seen_assertion_ids.add(assertion_obj.id)
            normalized_assertions.append(assertion_obj)

        if not normalized_assertions:
            raise InvalidEvaluationReportError(
                "EvaluationReport.assertions must contain at least one assertion."
            )
        if not any(a.id == "run.lifecycle" for a in normalized_assertions):
            raise InvalidEvaluationReportError(
                "EvaluationReport.assertions must include 'run.lifecycle'."
            )
        object.__setattr__(self, "assertions", tuple(normalized_assertions))

        coerced_verdict = EvaluationVerdict.coerce(self.verdict)
        expected_verdict = compute_evaluation_verdict(self.assertions)
        if coerced_verdict != expected_verdict:
            raise InvalidEvaluationReportError(
                f"EvaluationReport.verdict '{coerced_verdict.value}' is inconsistent with assertions (expected '{expected_verdict.value}')."
            )
        object.__setattr__(self, "verdict", coerced_verdict)

        computed_digest = self._compute_report_digest()
        if self.report_digest:
            validated_digest = _validate_sha256(
                self.report_digest,
                "EvaluationReport.report_digest",
                EvaluationReportDigestMismatchError,
            )
            if validated_digest != computed_digest:
                raise EvaluationReportDigestMismatchError(
                    f"EvaluationReport 'report_digest' mismatch for run '{self.run_id}'."
                )
        object.__setattr__(self, "report_digest", computed_digest)

    def _canonical_digest_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "contract_digest": self.contract_digest,
            "state_revision": self.state_revision,
            "state_digest": self.state_digest,
            "evidence_set_digest": self.evidence_set_digest,
            "ruleset_version": self.ruleset_version,
            "ruleset_digest": self.ruleset_digest,
            "assertions": [a.to_dict() for a in self.assertions],
            "verdict": self.verdict.value,
        }

    def _compute_report_digest(self) -> str:
        return sha256_canonical_json(self._canonical_digest_payload())

    def to_dict(self) -> dict[str, object]:
        return {
            **self._canonical_digest_payload(),
            "report_digest": self.report_digest,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        *,
        verify_digest: bool = True,
    ) -> "EvaluationReport":
        if not isinstance(payload, Mapping):
            raise InvalidEvaluationReportError(
                "EvaluationReport payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_EVALUATION_REPORT_KEYS
        if unknown:
            raise InvalidEvaluationReportError(
                f"Unexpected fields in EvaluationReport: {sorted(unknown)}."
            )
        missing = CANONICAL_EVALUATION_REPORT_KEYS - set(payload.keys())
        if missing:
            raise InvalidEvaluationReportError(
                f"Missing required fields in EvaluationReport: {sorted(missing)}."
            )
        raw_assertions = payload["assertions"]
        if not isinstance(raw_assertions, list):
            raise InvalidEvaluationReportError(
                "EvaluationReport 'assertions' must be a JSON list."
            )
        raw_digest = str(payload["report_digest"]) if verify_digest else ""
        return cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            run_id=payload["run_id"],  # type: ignore[arg-type]
            contract_digest=payload["contract_digest"],  # type: ignore[arg-type]
            state_revision=payload["state_revision"],  # type: ignore[arg-type]
            state_digest=payload["state_digest"],  # type: ignore[arg-type]
            evidence_set_digest=payload["evidence_set_digest"],  # type: ignore[arg-type]
            ruleset_version=payload["ruleset_version"],  # type: ignore[arg-type]
            ruleset_digest=payload["ruleset_digest"],  # type: ignore[arg-type]
            assertions=tuple(
                EvalAssertion.from_dict(item) for item in raw_assertions
            ),
            verdict=EvaluationVerdict.coerce(payload["verdict"]),
            report_digest=raw_digest,
        )

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        verify_digest: bool = True,
    ) -> "EvaluationReport":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidEvaluationReportError(
                f"Invalid EvaluationReport JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise InvalidEvaluationReportError(
                "EvaluationReport JSON root must be an object."
            )
        return cls.from_dict(payload, verify_digest=verify_digest)


def _is_evidence_item_failure(evidence: RunEvidence) -> bool:
    """Return True if `evidence` records an explicit execution or verification failure."""
    if evidence.kind == EvidenceKind.COMMAND_RESULT:
        return int(evidence.payload["exit_code"]) != 0  # type: ignore[arg-type]
    if evidence.kind == EvidenceKind.TEST_RESULT:
        return (
            int(evidence.payload["exit_code"]) != 0  # type: ignore[arg-type]
            or int(evidence.payload["failed"]) > 0  # type: ignore[arg-type]
        )
    if evidence.kind == EvidenceKind.REVIEW:
        return str(evidence.payload["outcome"]) in {
            "changes_requested",
            "rejected",
        }
    if evidence.kind in {
        EvidenceKind.TOOL_INVOCATION,
        EvidenceKind.DELEGATION,
    }:
        return str(evidence.payload["outcome"]) == "failure"
    return False


class BehavioralEvaluator:
    """Pure, deterministic domain evaluator over `ExecutionContract`, `RunState`, and `RunEvidence`."""

    def __init__(
        self,
        *,
        ruleset: tuple[BehavioralRule, ...] = DEFAULT_BEHAVIORAL_RULESET,
        ruleset_version: int = BEHAVIORAL_RULESET_VERSION,
        requirement_resolver: CapabilityRequirementResolver | None = None,
    ):
        self.ruleset = tuple(ruleset)
        self.ruleset_version = ruleset_version
        self.ruleset_digest = compute_ruleset_digest(
            self.ruleset,
            version=self.ruleset_version,
        )
        self.requirement_resolver = (
            requirement_resolver or CapabilityRequirementResolver()
        )

    def evaluate(
        self,
        contract: ExecutionContract,
        state: RunState,
        evidence: Iterable[RunEvidence] = (),
        *,
        extra_capability_requirements: Iterable[CapabilityRequirement | str] = (),
    ) -> EvaluationReport:
        if not isinstance(contract, ExecutionContract):
            raise EvaluationBindingMismatchError(
                "BehavioralEvaluator.evaluate requires an ExecutionContract instance."
            )
        if not isinstance(state, RunState):
            raise EvaluationBindingMismatchError(
                "BehavioralEvaluator.evaluate requires a RunState instance."
            )
        if contract.run_id != state.run_id:
            raise EvaluationBindingMismatchError(
                f"RunState run_id '{state.run_id}' does not match ExecutionContract run_id '{contract.run_id}'."
            )
        try:
            verify_run_state_against_contract(state, contract)
        except ExecutionError as exc:
            raise EvaluationBindingMismatchError(str(exc)) from exc

        raw_evidence = tuple(evidence)
        valid_task_ids = {t.id for t in contract.tasks}
        valid_gate_ids = {g.id for g in contract.gates}

        for ev in raw_evidence:
            if not isinstance(ev, RunEvidence):
                raise EvaluationBindingMismatchError(
                    "BehavioralEvaluator.evaluate requires RunEvidence instances."
                )
            if ev.run_id != contract.run_id:
                raise EvaluationBindingMismatchError(
                    f"Evidence '{ev.id}' belongs to run '{ev.run_id}', expected '{contract.run_id}'."
                )
            if ev.contract_digest != contract.contract_digest:
                raise EvaluationBindingMismatchError(
                    f"Evidence '{ev.id}' contract_digest '{ev.contract_digest}' does not match ExecutionContract digest '{contract.contract_digest}'."
                )
            if ev.state_revision > state.revision:
                raise EvaluationBindingMismatchError(
                    f"Evidence '{ev.id}' references state_revision s{ev.state_revision} > evaluated RunState s{state.revision}."
                )
            if ev.producer.startswith("harness:"):
                declared_harness = ev.producer[len("harness:") :]
                if declared_harness != contract.harness:
                    raise EvaluationBindingMismatchError(
                        f"Evidence '{ev.id}' producer '{ev.producer}' does not match contract harness '{contract.harness}'."
                    )
            for tid in ev.task_ids:
                if tid not in valid_task_ids:
                    raise InvalidEvidenceReferenceError(
                        f"Evidence '{ev.id}' references unknown task '{tid}'."
                    )
            for gid in ev.gate_ids:
                if gid not in valid_gate_ids:
                    raise InvalidEvidenceReferenceError(
                        f"Evidence '{ev.id}' references unknown gate '{gid}'."
                    )
            for cid in ev.capability_ids:
                if cid not in CANONICAL_CAPABILITY_IDS:
                    raise InvalidEvidenceReferenceError(
                        f"Evidence '{ev.id}' references unknown capability '{cid}'."
                    )

        ordered_evidence = tuple(
            sorted(raw_evidence, key=lambda item: parse_evidence_ordinal(item.id))
        )
        evidence_set_digest = compute_evidence_set_digest(
            contract.run_id,
            ordered_evidence,
        )

        assertions: list[EvalAssertion] = []

        # 1. Run Lifecycle Assertion
        assertions.append(self._evaluate_lifecycle(contract, state))

        # 2. Task Evidence Assertions (in contract task order)
        task_state_by_id: dict[str, TaskState] = {
            t.id: t for t in state.tasks
        }
        for contract_task in contract.tasks:
            task_state = task_state_by_id.get(contract_task.id)
            if task_state is None:
                raise EvaluationBindingMismatchError(
                    f"RunState s{state.revision} is missing contract task '{contract_task.id}'."
                )
            assertions.append(
                self._evaluate_task(task_state, ordered_evidence)
            )

        # 3. Required Gate Evidence Assertions (in contract gate order)
        gate_state_by_id: dict[str, GateState] = {
            g.id: g for g in state.gates
        }
        for contract_gate in contract.gates:
            if not contract_gate.required:
                continue
            gate_state = gate_state_by_id.get(contract_gate.id)
            if gate_state is None:
                raise EvaluationBindingMismatchError(
                    f"RunState s{state.revision} is missing required contract gate '{contract_gate.id}'."
                )
            assertions.append(
                self._evaluate_gate(
                    contract_gate,
                    gate_state,
                    ordered_evidence,
                )
            )

        # 4. Capability Observation Assertions (derived via Phase 5 CapabilityRequirementResolver)
        try:
            capability_requirements = self.requirement_resolver.derive(
                contract,
                extra_requirements=extra_capability_requirements,
            )
        except HarnessCapabilityError as exc:
            raise InvalidEvidenceReferenceError(str(exc)) from exc

        for cap_req in capability_requirements:
            assertions.append(
                self._evaluate_capability(cap_req, ordered_evidence)
            )

        verdict = compute_evaluation_verdict(assertions)

        return EvaluationReport(
            schema_version=EVALUATION_REPORT_SCHEMA_VERSION,
            run_id=contract.run_id,
            contract_digest=contract.contract_digest,
            state_revision=state.revision,
            state_digest=state.content_digest,
            evidence_set_digest=evidence_set_digest,
            ruleset_version=self.ruleset_version,
            ruleset_digest=self.ruleset_digest,
            assertions=tuple(assertions),
            verdict=verdict,
        )

    def _evaluate_lifecycle(
        self,
        contract: ExecutionContract,
        state: RunState,
    ) -> EvalAssertion:
        if state.status == RunStatus.FINISHED:
            return EvalAssertion(
                id="run.lifecycle",
                category="lifecycle",
                subject_id=contract.run_id,
                required=True,
                status=EvalAssertionStatus.PASS,
                reason="Run reached terminal status 'finished'.",
                evidence_ids=(),
            )
        if state.status in {RunStatus.FAILED, RunStatus.CANCELLED}:
            return EvalAssertion(
                id="run.lifecycle",
                category="lifecycle",
                subject_id=contract.run_id,
                required=True,
                status=EvalAssertionStatus.FAIL,
                reason=f"Run is in terminal failure status '{state.status.value}'.",
                evidence_ids=(),
            )
        return EvalAssertion(
            id="run.lifecycle",
            category="lifecycle",
            subject_id=contract.run_id,
            required=True,
            status=EvalAssertionStatus.UNVERIFIED,
            reason=f"Run is in non-terminal status '{state.status.value}'.",
            evidence_ids=(),
        )

    def _evaluate_task(
        self,
        task_state: TaskState,
        ordered_evidence: tuple[RunEvidence, ...],
    ) -> EvalAssertion:
        assertion_id = f"task.{task_state.id}.evidence"
        linked = [
            ev
            for ev in ordered_evidence
            if task_state.id in ev.task_ids and ev.kind in TASK_EVIDENCE_KINDS
        ]
        ev_ids = tuple(ev.id for ev in linked)

        if task_state.status == TaskStatus.SKIPPED:
            return EvalAssertion(
                id=assertion_id,
                category="task",
                subject_id=task_state.id,
                required=False,
                status=EvalAssertionStatus.NOT_APPLICABLE,
                reason=f"Task '{task_state.id}' was skipped.",
                evidence_ids=ev_ids,
            )

        if task_state.status == TaskStatus.DONE:
            if not linked:
                return EvalAssertion(
                    id=assertion_id,
                    category="task",
                    subject_id=task_state.id,
                    required=True,
                    status=EvalAssertionStatus.UNVERIFIED,
                    reason=f"Task '{task_state.id}' is marked done without linked execution evidence.",
                    evidence_ids=(),
                )
            failing = [ev for ev in linked if _is_evidence_item_failure(ev)]
            if failing:
                return EvalAssertion(
                    id=assertion_id,
                    category="task",
                    subject_id=task_state.id,
                    required=True,
                    status=EvalAssertionStatus.FAIL,
                    reason=f"Task '{task_state.id}' has failing linked execution evidence ({', '.join(ev.id for ev in failing)}).",
                    evidence_ids=ev_ids,
                )
            return EvalAssertion(
                id=assertion_id,
                category="task",
                subject_id=task_state.id,
                required=True,
                status=EvalAssertionStatus.PASS,
                reason=f"Task '{task_state.id}' completion is backed by execution evidence ({', '.join(ev_ids)}).",
                evidence_ids=ev_ids,
            )

        return EvalAssertion(
            id=assertion_id,
            category="task",
            subject_id=task_state.id,
            required=True,
            status=EvalAssertionStatus.UNVERIFIED,
            reason=f"Task '{task_state.id}' is in status '{task_state.status.value}' and not yet completed.",
            evidence_ids=ev_ids,
        )

    def _evaluate_gate(
        self,
        contract_gate: GateRequirement,
        gate_state: GateState,
        ordered_evidence: tuple[RunEvidence, ...],
    ) -> EvalAssertion:
        assertion_id = f"gate.{contract_gate.id}.evidence"
        linked = [
            ev for ev in ordered_evidence if contract_gate.id in ev.gate_ids
        ]
        all_linked_ids = tuple(ev.id for ev in linked)

        if gate_state.disposition == GateDisposition.WAIVED:
            return EvalAssertion(
                id=assertion_id,
                category="gate",
                subject_id=contract_gate.id,
                required=contract_gate.required,
                status=EvalAssertionStatus.WAIVED,
                reason=f"Gate '{contract_gate.id}' was explicitly waived.",
                evidence_ids=all_linked_ids,
            )

        if gate_state.disposition == GateDisposition.PENDING:
            return EvalAssertion(
                id=assertion_id,
                category="gate",
                subject_id=contract_gate.id,
                required=contract_gate.required,
                status=EvalAssertionStatus.UNVERIFIED,
                reason=f"Gate '{contract_gate.id}' disposition is 'pending' (not yet acknowledged).",
                evidence_ids=all_linked_ids,
            )

        # GateDisposition.ACKNOWLEDGED — declaration alone is never PASS
        relevant_ids: list[str] = []
        fail_ids: list[str] = []
        pass_ids: list[str] = []

        for ev in linked:
            item_status = self._classify_gate_evidence_item(contract_gate.kind, ev)
            if item_status is None:
                continue
            relevant_ids.append(ev.id)
            if item_status == EvalAssertionStatus.FAIL:
                fail_ids.append(ev.id)
            elif item_status == EvalAssertionStatus.PASS:
                pass_ids.append(ev.id)

        evidence_ids = tuple(relevant_ids) if relevant_ids else all_linked_ids

        if fail_ids:
            return EvalAssertion(
                id=assertion_id,
                category="gate",
                subject_id=contract_gate.id,
                required=contract_gate.required,
                status=EvalAssertionStatus.FAIL,
                reason=f"Gate '{contract_gate.id}' has failing evidence ({', '.join(fail_ids)}).",
                evidence_ids=evidence_ids,
            )

        if pass_ids:
            return EvalAssertion(
                id=assertion_id,
                category="gate",
                subject_id=contract_gate.id,
                required=contract_gate.required,
                status=EvalAssertionStatus.PASS,
                reason=f"Gate '{contract_gate.id}' is acknowledged and verified by evidence ({', '.join(pass_ids)}).",
                evidence_ids=evidence_ids,
            )

        return EvalAssertion(
            id=assertion_id,
            category="gate",
            subject_id=contract_gate.id,
            required=contract_gate.required,
            status=EvalAssertionStatus.UNVERIFIED,
            reason=f"Gate '{contract_gate.id}' is acknowledged in RunState but lacks qualifying verification evidence.",
            evidence_ids=evidence_ids,
        )

    def _classify_gate_evidence_item(
        self,
        gate_kind: GateKind,
        evidence: RunEvidence,
    ) -> EvalAssertionStatus | None:
        if gate_kind == GateKind.IMPLEMENTATION_TESTS:
            if evidence.kind != EvidenceKind.TEST_RESULT:
                return None
            exit_code = int(evidence.payload["exit_code"])  # type: ignore[arg-type]
            failed = int(evidence.payload["failed"])  # type: ignore[arg-type]
            if exit_code != 0 or failed > 0:
                return EvalAssertionStatus.FAIL
            if len(evidence.artifacts) >= 1:
                return EvalAssertionStatus.PASS
            return EvalAssertionStatus.UNVERIFIED

        if gate_kind == GateKind.BASELINE_CHECK:
            if evidence.kind == EvidenceKind.COMMAND_RESULT:
                exit_code = int(evidence.payload["exit_code"])  # type: ignore[arg-type]
                if exit_code != 0:
                    return EvalAssertionStatus.FAIL
                if len(evidence.artifacts) >= 1:
                    return EvalAssertionStatus.PASS
                return EvalAssertionStatus.UNVERIFIED
            if evidence.kind == EvidenceKind.TEST_RESULT:
                exit_code = int(evidence.payload["exit_code"])  # type: ignore[arg-type]
                failed = int(evidence.payload["failed"])  # type: ignore[arg-type]
                if exit_code != 0 or failed > 0:
                    return EvalAssertionStatus.FAIL
                if len(evidence.artifacts) >= 1:
                    return EvalAssertionStatus.PASS
                return EvalAssertionStatus.UNVERIFIED
            return None

        if gate_kind == GateKind.WORKSPACE_ISOLATION:
            if evidence.kind != EvidenceKind.WORKSPACE:
                return None
            mode = str(evidence.payload["mode"])
            if mode == "isolated":
                return EvalAssertionStatus.PASS
            return EvalAssertionStatus.FAIL

        expected_review_type = REVIEW_GATE_KIND_TO_REVIEW_TYPE.get(gate_kind)
        if expected_review_type is not None:
            if evidence.kind != EvidenceKind.REVIEW:
                return None
            if str(evidence.payload["review_type"]) != expected_review_type:
                return None
            outcome = str(evidence.payload["outcome"])
            if outcome == "approved":
                return EvalAssertionStatus.PASS
            if outcome in {"changes_requested", "rejected"}:
                return EvalAssertionStatus.FAIL
            return EvalAssertionStatus.UNVERIFIED

        return None

    def _evaluate_capability(
        self,
        requirement: CapabilityRequirement,
        ordered_evidence: tuple[RunEvidence, ...],
    ) -> EvalAssertion:
        cap_id = requirement.capability_id
        assertion_id = f"capability.{cap_id}.observed"

        if cap_id in NON_OBSERVABLE_CAPABILITY_IDS:
            return EvalAssertion(
                id=assertion_id,
                category="capability",
                subject_id=cap_id,
                required=False,
                status=EvalAssertionStatus.NOT_APPLICABLE,
                reason=f"Capability '{cap_id}' is not objectively observable by Evidence Engine v1.",
                evidence_ids=(),
            )

        relevant_ids: list[str] = []
        fail_ids: list[str] = []
        pass_ids: list[str] = []

        for ev in ordered_evidence:
            item_status = self._classify_capability_evidence_item(cap_id, ev)
            if item_status is None:
                continue
            relevant_ids.append(ev.id)
            if item_status == EvalAssertionStatus.FAIL:
                fail_ids.append(ev.id)
            elif item_status == EvalAssertionStatus.PASS:
                pass_ids.append(ev.id)

        evidence_ids = tuple(relevant_ids)
        if fail_ids:
            return EvalAssertion(
                id=assertion_id,
                category="capability",
                subject_id=cap_id,
                required=True,
                status=EvalAssertionStatus.FAIL,
                reason=f"Required capability '{cap_id}' ({requirement.source}) observed failing evidence ({', '.join(fail_ids)}).",
                evidence_ids=evidence_ids,
            )

        if pass_ids:
            return EvalAssertion(
                id=assertion_id,
                category="capability",
                subject_id=cap_id,
                required=True,
                status=EvalAssertionStatus.PASS,
                reason=f"Required capability '{cap_id}' ({requirement.source}) observed in evidence ({', '.join(pass_ids)}).",
                evidence_ids=evidence_ids,
            )

        return EvalAssertion(
            id=assertion_id,
            category="capability",
            subject_id=cap_id,
            required=True,
            status=EvalAssertionStatus.UNVERIFIED,
            reason=f"Required capability '{cap_id}' ({requirement.source}) has no qualifying observation evidence.",
            evidence_ids=evidence_ids,
        )

    def _classify_capability_evidence_item(
        self,
        capability_id: str,
        evidence: RunEvidence,
    ) -> EvalAssertionStatus | None:
        if capability_id == "repository.write":
            if evidence.kind == EvidenceKind.FILE_CHANGE:
                return EvalAssertionStatus.PASS
            return None

        if capability_id == "workspace.current":
            if evidence.kind != EvidenceKind.WORKSPACE:
                return None
            if str(evidence.payload["mode"]) == "current":
                return EvalAssertionStatus.PASS
            if "workspace.current" in evidence.capability_ids:
                return EvalAssertionStatus.FAIL
            return None

        if capability_id == "workspace.isolated":
            if evidence.kind != EvidenceKind.WORKSPACE:
                return None
            if str(evidence.payload["mode"]) == "isolated":
                return EvalAssertionStatus.PASS
            if "workspace.isolated" in evidence.capability_ids:
                return EvalAssertionStatus.FAIL
            return None

        if capability_id == "tests.execute":
            if evidence.kind != EvidenceKind.TEST_RESULT:
                return None
            exit_code = int(evidence.payload["exit_code"])  # type: ignore[arg-type]
            failed = int(evidence.payload["failed"])  # type: ignore[arg-type]
            if exit_code == 0 and failed == 0:
                return EvalAssertionStatus.PASS
            return EvalAssertionStatus.FAIL

        if capability_id == "shell.execute":
            if evidence.kind != EvidenceKind.COMMAND_RESULT:
                return None
            exit_code = int(evidence.payload["exit_code"])  # type: ignore[arg-type]
            if exit_code == 0:
                return EvalAssertionStatus.PASS
            return EvalAssertionStatus.FAIL

        if capability_id == "git.inspect":
            if (
                evidence.kind == EvidenceKind.GIT_RESULT
                and str(evidence.payload["operation"]) == "inspect"
            ):
                return EvalAssertionStatus.PASS
            return None

        if capability_id == "git.modify":
            if (
                evidence.kind == EvidenceKind.GIT_RESULT
                and str(evidence.payload["operation"]) == "modify"
            ):
                return EvalAssertionStatus.PASS
            return None

        if capability_id == "mcp.invoke":
            if evidence.kind != EvidenceKind.TOOL_INVOCATION:
                return None
            if str(evidence.payload["outcome"]) == "success":
                return EvalAssertionStatus.PASS
            return EvalAssertionStatus.FAIL

        if capability_id == "subagents.delegate":
            if evidence.kind != EvidenceKind.DELEGATION:
                return None
            if str(evidence.payload["outcome"]) == "success":
                return EvalAssertionStatus.PASS
            return EvalAssertionStatus.FAIL

        return None

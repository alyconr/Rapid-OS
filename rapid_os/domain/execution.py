import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from rapid_os.domain.context import SUPPORTED_HARNESSES, CompiledContext
from rapid_os.domain.harnesses import validate_harness_id
from rapid_os.domain.policy import (
    DEFAULT_EXECUTION_POLICY,
    EXECUTION_POLICY_SCHEMA_VERSION,
    GATE_ID_RE,
    ContextSnapshotMismatchError,
    DuplicateRunIdentityError,
    ExecutionClass,
    ExecutionError,
    ExecutionPolicy,
    ExecutionPolicyEvaluator,
    ExecutionPreconditionError,
    GateKind,
    GatePhase,
    GateRequirement,
    InvalidExecutionContractError,
    InvalidExecutionPolicyError,
    InvalidGateTransitionError,
    InvalidRunRecordError,
    InvalidRunStateError,
    InvalidRunTransitionError,
    InvalidSpecBindingError,
    InvalidTaskTransitionError,
    PolicyDecision,
    PolicyViolationError,
    RiskLevel,
    RiskSignal,
    RunIdentityError,
    RunNotFoundError,
    RunStateHistoryGapError,
    UnsafeRunPathError,
    WorkspaceRequirement,
    sha256_canonical_json,
    sha256_utf8,
)
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.specs import (
    SpecRevision,
    is_canonical_revision_dir_name,
    validate_spec_id,
)


EXECUTION_CONTRACT_SCHEMA_VERSION = 1
RUN_SCHEMA_VERSION = 1
RUN_STATE_SCHEMA_VERSION = 1

RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
TASK_ID_RE = re.compile(r"^T\d{3,}$")
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_run_id(raw_id: object, label: str = "run id") -> str:
    """Validate that `raw_id` is a canonical, path-safe, lowercase run identifier."""
    if not isinstance(raw_id, str):
        raise InvalidRunRecordError(
            f"Invalid {label}: expected a string."
        )
    if "\x00" in raw_id:
        raise InvalidRunRecordError(
            f"Invalid {label}: null bytes are not allowed."
        )
    if not raw_id or raw_id != raw_id.strip():
        raise InvalidRunRecordError(
            f"Invalid {label} '{raw_id}': leading or trailing whitespace is not allowed."
        )
    if not RUN_ID_RE.match(raw_id):
        raise InvalidRunRecordError(
            f"Invalid {label} '{raw_id}': must match {RUN_ID_RE.pattern}."
        )
    return raw_id


def derive_run_id(spec_id: str, spec_revision: int, ordinal: int = 1) -> str:
    """Deterministically derive `<spec-id>-r<revision>-run-<ordinal:03d>` within the 63-char slug budget."""
    validated_spec = validate_spec_id(spec_id, "spec_id")
    if isinstance(spec_revision, bool) or not isinstance(spec_revision, int) or spec_revision < 1:
        raise InvalidExecutionContractError(
            f"Invalid spec_revision '{spec_revision}': must be a positive integer."
        )
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
        raise DuplicateRunIdentityError(
            f"Invalid run ordinal '{ordinal}': must be a positive integer."
        )
    suffix = f"-r{spec_revision}-run-{ordinal:03d}"
    max_prefix_len = 63 - len(suffix)
    prefix = validated_spec[:max_prefix_len].rstrip("-")
    if not prefix:
        prefix = "spec"
    return validate_run_id(f"{prefix}{suffix}")


def format_task_id(index: int) -> str:
    """Format 1-based task ordinal as `T001`, `T002`, ..., `T1000`."""
    if isinstance(index, bool) or not isinstance(index, int) or index < 1:
        raise InvalidTaskTransitionError(
            f"Invalid task index '{index}': must be a positive integer."
        )
    return f"T{index:03d}"


def validate_task_id(raw_id: object, label: str = "task id") -> str:
    if not isinstance(raw_id, str) or not TASK_ID_RE.match(raw_id.strip()):
        raise InvalidTaskTransitionError(
            f"Invalid {label} '{raw_id}': must match {TASK_ID_RE.pattern}."
        )
    value = raw_id.strip()
    num = int(value[1:])
    if num < 1 or value != f"T{num:03d}":
        raise InvalidTaskTransitionError(
            f"Invalid {label} '{raw_id}': must use canonical T001..T999 format."
        )
    return value


def is_canonical_state_file_name(name: str) -> bool:
    """Return True if `name` is `<canonical_revision>.json` (`0001.json`, ..., `10000.json`)."""
    if not isinstance(name, str) or not name.endswith(".json"):
        return False
    stem = name[:-5]
    return is_canonical_revision_dir_name(stem)


def format_state_file_name(revision: int) -> str:
    """Return `<revision:04d>.json` for a positive integer state revision."""
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise InvalidRunStateError(
            f"Invalid state revision '{revision}': must be a positive integer."
        )
    return f"{revision:04d}.json"


CANONICAL_TASK_CONTRACT_KEYS = frozenset({"id", "description"})


@dataclass(frozen=True)
class TaskContract:
    id: str
    description: str

    def __post_init__(self):
        object.__setattr__(self, "id", validate_task_id(self.id, "TaskContract.id"))
        if not isinstance(self.description, str) or not self.description.strip():
            raise InvalidExecutionContractError(
                "TaskContract.description must be a non-empty string."
            )
        object.__setattr__(self, "description", self.description.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "TaskContract":
        if not isinstance(payload, Mapping):
            raise InvalidExecutionContractError(
                "TaskContract payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_TASK_CONTRACT_KEYS
        if unknown:
            raise InvalidExecutionContractError(
                f"Unexpected fields in TaskContract: {sorted(unknown)}."
            )
        missing = CANONICAL_TASK_CONTRACT_KEYS - set(payload.keys())
        if missing:
            raise InvalidExecutionContractError(
                f"Missing required fields in TaskContract: {sorted(missing)}."
            )
        try:
            return cls(
                id=str(payload["id"]),
                description=str(payload["description"]),
            )
        except InvalidTaskTransitionError as exc:
            raise InvalidExecutionContractError(str(exc)) from exc


def derive_task_contracts(spec: SpecRevision) -> tuple[TaskContract, ...]:
    """Derive ordered `TaskContract` items (`T001`, `T002`, ...) from `SpecRevision.implementation_tasks`."""
    if not isinstance(spec, SpecRevision):
        raise InvalidExecutionContractError(
            "derive_task_contracts requires a SpecRevision instance."
        )
    return tuple(
        TaskContract(id=format_task_id(idx), description=desc)
        for idx, desc in enumerate(spec.implementation_tasks, start=1)
    )


CANONICAL_EXECUTION_CONTRACT_KEYS = frozenset(
    {
        "schema_version",
        "run_id",
        "spec_id",
        "spec_revision",
        "spec_content_digest",
        "harness",
        "context_digest",
        "context_manifest_digest",
        "project_model_digest",
        "policy_source",
        "policy_digest",
        "decision",
        "classification",
        "risk",
        "risk_signals",
        "workspace",
        "gates",
        "tasks",
        "contract_digest",
    }
)


ALLOWED_POLICY_SOURCES = frozenset(
    {
        "default",
        ".rapid-os/policy.json",
        "injected",
    }
)


def _validate_sha256(value: object, label: str, error_cls=InvalidExecutionContractError) -> str:
    if not isinstance(value, str) or not SHA256_HEX_RE.match(value):
        raise error_cls(
            f"Invalid {label} '{value}': must be a 64-character lowercase hex SHA-256 digest."
        )
    return value


@dataclass(frozen=True)
class ExecutionContract:
    schema_version: int
    run_id: str
    spec_id: str
    spec_revision: int
    spec_content_digest: str
    harness: str
    context_digest: str
    context_manifest_digest: str
    project_model_digest: str
    policy_source: str
    policy_digest: str
    decision: PolicyDecision
    classification: ExecutionClass
    risk: RiskLevel
    risk_signals: tuple[RiskSignal, ...]
    workspace: WorkspaceRequirement
    gates: tuple[GateRequirement, ...]
    tasks: tuple[TaskContract, ...]
    contract_digest: str = ""

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != EXECUTION_CONTRACT_SCHEMA_VERSION
        ):
            raise InvalidExecutionContractError(
                f"Unsupported ExecutionContract schema_version '{self.schema_version}': expected {EXECUTION_CONTRACT_SCHEMA_VERSION}."
            )
        try:
            validated_run_id = validate_run_id(self.run_id, "ExecutionContract.run_id")
        except ExecutionError as exc:
            raise InvalidExecutionContractError(str(exc)) from exc
        object.__setattr__(self, "run_id", validated_run_id)

        try:
            validated_spec_id = validate_spec_id(
                self.spec_id, "ExecutionContract.spec_id"
            )
        except Exception as exc:
            raise InvalidSpecBindingError(str(exc)) from exc
        object.__setattr__(self, "spec_id", validated_spec_id)

        if (
            isinstance(self.spec_revision, bool)
            or not isinstance(self.spec_revision, int)
            or self.spec_revision < 1
        ):
            raise InvalidSpecBindingError(
                f"Invalid ExecutionContract.spec_revision '{self.spec_revision}': must be a positive integer."
            )
        object.__setattr__(
            self,
            "spec_content_digest",
            _validate_sha256(
                self.spec_content_digest,
                "ExecutionContract.spec_content_digest",
                InvalidSpecBindingError,
            ),
        )

        try:
            validated_harness = validate_harness_id(
                self.harness,
                "ExecutionContract.harness",
            )
        except ValueError as exc:
            raise InvalidExecutionContractError(str(exc)) from exc
        object.__setattr__(self, "harness", validated_harness)

        object.__setattr__(
            self,
            "context_digest",
            _validate_sha256(self.context_digest, "ExecutionContract.context_digest"),
        )
        object.__setattr__(
            self,
            "context_manifest_digest",
            _validate_sha256(
                self.context_manifest_digest,
                "ExecutionContract.context_manifest_digest",
            ),
        )
        object.__setattr__(
            self,
            "project_model_digest",
            _validate_sha256(
                self.project_model_digest,
                "ExecutionContract.project_model_digest",
            ),
        )

        if (
            not isinstance(self.policy_source, str)
            or self.policy_source not in ALLOWED_POLICY_SOURCES
        ):
            raise InvalidExecutionContractError(
                f"Invalid ExecutionContract.policy_source '{self.policy_source}': expected one of {sorted(ALLOWED_POLICY_SOURCES)}."
            )
        object.__setattr__(
            self,
            "policy_digest",
            _validate_sha256(self.policy_digest, "ExecutionContract.policy_digest"),
        )

        decision_obj = (
            self.decision
            if isinstance(self.decision, PolicyDecision)
            else PolicyDecision.from_dict(self.decision)  # type: ignore[arg-type]
        )
        object.__setattr__(self, "decision", decision_obj)

        try:
            class_obj = ExecutionClass.coerce(self.classification)
            risk_obj = RiskLevel.coerce(self.risk)
            workspace_obj = WorkspaceRequirement.coerce(self.workspace)
        except ExecutionError as exc:
            raise InvalidExecutionContractError(str(exc)) from exc
        object.__setattr__(self, "classification", class_obj)
        object.__setattr__(self, "risk", risk_obj)
        object.__setattr__(self, "workspace", workspace_obj)

        if isinstance(self.risk_signals, (str, bytes)) or not isinstance(
            self.risk_signals, Iterable
        ):
            raise InvalidExecutionContractError(
                "ExecutionContract.risk_signals must be a sequence."
            )
        try:
            signals_tuple = tuple(
                s if isinstance(s, RiskSignal) else RiskSignal.from_dict(s)  # type: ignore[arg-type]
                for s in self.risk_signals
            )
        except ExecutionError as exc:
            raise InvalidExecutionContractError(str(exc)) from exc
        object.__setattr__(self, "risk_signals", signals_tuple)

        if isinstance(self.gates, (str, bytes)) or not isinstance(
            self.gates, Iterable
        ):
            raise InvalidExecutionContractError(
                "ExecutionContract.gates must be a sequence."
            )
        try:
            gates_tuple = tuple(
                g if isinstance(g, GateRequirement) else GateRequirement.from_dict(g)  # type: ignore[arg-type]
                for g in self.gates
            )
        except ExecutionError as exc:
            raise InvalidExecutionContractError(str(exc)) from exc
        seen_gates: set[str] = set()
        for gate in gates_tuple:
            if gate.id in seen_gates:
                raise InvalidExecutionContractError(
                    f"Duplicate gate '{gate.id}' in ExecutionContract."
                )
            seen_gates.add(gate.id)
        object.__setattr__(self, "gates", gates_tuple)

        if (
            decision_obj.classification != class_obj
            or decision_obj.risk != risk_obj
            or decision_obj.workspace != workspace_obj
            or decision_obj.risk_signals != signals_tuple
            or decision_obj.gates != gates_tuple
        ):
            raise InvalidExecutionContractError(
                "ExecutionContract top-level policy fields do not match embedded PolicyDecision."
            )

        if isinstance(self.tasks, (str, bytes)) or not isinstance(
            self.tasks, Iterable
        ):
            raise InvalidExecutionContractError(
                "ExecutionContract.tasks must be a sequence."
            )
        tasks_tuple = tuple(
            t if isinstance(t, TaskContract) else TaskContract.from_dict(t)  # type: ignore[arg-type]
            for t in self.tasks
        )
        for idx, task in enumerate(tasks_tuple, start=1):
            expected_id = format_task_id(idx)
            if task.id != expected_id:
                raise InvalidExecutionContractError(
                    f"ExecutionContract task sequence must be contiguous starting at T001: expected '{expected_id}', got '{task.id}'."
                )
        object.__setattr__(self, "tasks", tasks_tuple)

        computed_digest = self._compute_contract_digest()
        if self.contract_digest:
            validated_digest = _validate_sha256(
                self.contract_digest,
                "ExecutionContract.contract_digest",
            )
            if validated_digest != computed_digest:
                raise InvalidExecutionContractError(
                    "ExecutionContract 'contract_digest' does not match canonical contract content."
                )
        object.__setattr__(self, "contract_digest", computed_digest)

    def _canonical_digest_payload(self) -> dict[str, object]:
        """Return canonical contract payload (excluding `run_id` and `contract_digest`) so identical inputs yield the same contract digest."""
        return {
            "schema_version": self.schema_version,
            "spec_id": self.spec_id,
            "spec_revision": self.spec_revision,
            "spec_content_digest": self.spec_content_digest,
            "harness": self.harness,
            "context_digest": self.context_digest,
            "context_manifest_digest": self.context_manifest_digest,
            "project_model_digest": self.project_model_digest,
            "policy_source": self.policy_source,
            "policy_digest": self.policy_digest,
            "decision": self.decision.to_dict(),
            "classification": self.classification.value,
            "risk": self.risk.label,
            "risk_signals": [s.to_dict() for s in self.risk_signals],
            "workspace": self.workspace.value,
            "gates": [g.to_dict() for g in self.gates],
            "tasks": [t.to_dict() for t in self.tasks],
        }

    def _compute_contract_digest(self) -> str:
        return sha256_canonical_json(self._canonical_digest_payload())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "spec_id": self.spec_id,
            "spec_revision": self.spec_revision,
            "spec_content_digest": self.spec_content_digest,
            "harness": self.harness,
            "context_digest": self.context_digest,
            "context_manifest_digest": self.context_manifest_digest,
            "project_model_digest": self.project_model_digest,
            "policy_source": self.policy_source,
            "policy_digest": self.policy_digest,
            "decision": self.decision.to_dict(),
            "classification": self.classification.value,
            "risk": self.risk.label,
            "risk_signals": [s.to_dict() for s in self.risk_signals],
            "workspace": self.workspace.value,
            "gates": [g.to_dict() for g in self.gates],
            "tasks": [t.to_dict() for t in self.tasks],
            "contract_digest": self.contract_digest,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
        *,
        verify_digest: bool = True,
    ) -> "ExecutionContract":
        if not isinstance(payload, Mapping):
            raise InvalidExecutionContractError(
                "ExecutionContract payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_EXECUTION_CONTRACT_KEYS
        if unknown:
            raise InvalidExecutionContractError(
                f"Unexpected fields in ExecutionContract: {sorted(unknown)}."
            )
        missing = CANONICAL_EXECUTION_CONTRACT_KEYS - set(payload.keys())
        if missing:
            raise InvalidExecutionContractError(
                f"Missing required fields in ExecutionContract: {sorted(missing)}."
            )
        raw_signals = payload["risk_signals"]
        raw_gates = payload["gates"]
        raw_tasks = payload["tasks"]
        if (
            not isinstance(raw_signals, list)
            or not isinstance(raw_gates, list)
            or not isinstance(raw_tasks, list)
        ):
            raise InvalidExecutionContractError(
                "ExecutionContract 'risk_signals', 'gates', and 'tasks' must be lists."
            )
        try:
            decision = PolicyDecision.from_dict(payload["decision"])  # type: ignore[arg-type]
            signals = tuple(RiskSignal.from_dict(s) for s in raw_signals)
            gates = tuple(GateRequirement.from_dict(g) for g in raw_gates)
            tasks = tuple(TaskContract.from_dict(t) for t in raw_tasks)
        except ExecutionError as exc:
            raise InvalidExecutionContractError(str(exc)) from exc

        raw_contract_digest = str(payload["contract_digest"]) if verify_digest else ""
        return cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            run_id=str(payload["run_id"]),
            spec_id=str(payload["spec_id"]),
            spec_revision=payload["spec_revision"],  # type: ignore[arg-type]
            spec_content_digest=str(payload["spec_content_digest"]),
            harness=str(payload["harness"]),
            context_digest=str(payload["context_digest"]),
            context_manifest_digest=str(payload["context_manifest_digest"]),
            project_model_digest=str(payload["project_model_digest"]),
            policy_source=str(payload["policy_source"]),
            policy_digest=str(payload["policy_digest"]),
            decision=decision,
            classification=ExecutionClass.coerce(payload["classification"]),
            risk=RiskLevel.coerce(payload["risk"]),
            risk_signals=signals,
            workspace=WorkspaceRequirement.coerce(payload["workspace"]),
            gates=gates,
            tasks=tasks,
            contract_digest=raw_contract_digest,
        )

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        verify_digest: bool = True,
    ) -> "ExecutionContract":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidExecutionContractError(
                f"Invalid ExecutionContract JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise InvalidExecutionContractError(
                "ExecutionContract JSON root must be an object."
            )
        return cls.from_dict(payload, verify_digest=verify_digest)


def build_execution_contract(
    *,
    run_id: str,
    spec: SpecRevision,
    compiled_context: CompiledContext,
    project_model: ProjectModel | None,
    policy: ExecutionPolicy = DEFAULT_EXECUTION_POLICY,
    policy_source: str = "default",
    decision: PolicyDecision | None = None,
    harness: str = "cursor",
) -> ExecutionContract:
    """Deterministically build an `ExecutionContract` from a `SpecRevision`, `CompiledContext`, `ProjectModel`, and `ExecutionPolicy`."""
    if not isinstance(spec, SpecRevision):
        raise InvalidExecutionContractError(
            "build_execution_contract requires a SpecRevision instance."
        )
    if not isinstance(compiled_context, CompiledContext):
        raise InvalidExecutionContractError(
            "build_execution_contract requires a CompiledContext instance."
        )
    if not isinstance(policy, ExecutionPolicy):
        raise InvalidExecutionContractError(
            "build_execution_contract requires an ExecutionPolicy instance."
        )
    if policy != DEFAULT_EXECUTION_POLICY and policy_source == "default":
        raise InvalidExecutionContractError(
            "Custom ExecutionPolicy cannot claim policy_source='default'."
        )

    resolved_decision = (
        decision
        if decision is not None
        else ExecutionPolicyEvaluator().evaluate(spec, policy)
    )
    resolved_model = (
        project_model
        if project_model is not None
        else ProjectModel(facts=())
    )
    context_text = compiled_context.content
    if not context_text.endswith("\n"):
        context_text = context_text + "\n"
    manifest_json = json.dumps(
        compiled_context.manifest.to_dict(),
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    return ExecutionContract(
        schema_version=EXECUTION_CONTRACT_SCHEMA_VERSION,
        run_id=run_id,
        spec_id=spec.spec_id,
        spec_revision=spec.revision,
        spec_content_digest=spec.content_digest,
        harness=harness or compiled_context.manifest.harness or "cursor",
        context_digest=sha256_utf8(context_text),
        context_manifest_digest=sha256_utf8(manifest_json),
        project_model_digest=sha256_canonical_json(resolved_model.to_dict()),
        policy_source=policy_source,
        policy_digest=policy.digest,
        decision=resolved_decision,
        classification=resolved_decision.classification,
        risk=resolved_decision.risk,
        risk_signals=resolved_decision.risk_signals,
        workspace=resolved_decision.workspace,
        gates=resolved_decision.gates,
        tasks=derive_task_contracts(spec),
    )


class RunStatus(str, Enum):
    PREPARED = "prepared"
    ACTIVE = "active"
    BLOCKED = "blocked"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def coerce(cls, value: object) -> "RunStatus":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidRunTransitionError(
            f"Invalid RunStatus '{value}': expected one of {[m.value for m in cls]}."
        )

    @property
    def is_terminal(self) -> bool:
        return self in (
            RunStatus.FINISHED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        )


ALLOWED_RUN_TRANSITIONS: Mapping[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PREPARED: frozenset({RunStatus.ACTIVE, RunStatus.CANCELLED}),
    RunStatus.ACTIVE: frozenset(
        {
            RunStatus.BLOCKED,
            RunStatus.FINISHED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.BLOCKED: frozenset(
        {
            RunStatus.ACTIVE,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.FINISHED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}


def validate_run_status_transition(
    current: RunStatus | str,
    target: RunStatus | str,
) -> RunStatus:
    current_status = RunStatus.coerce(current)
    target_status = RunStatus.coerce(target)
    allowed = ALLOWED_RUN_TRANSITIONS.get(current_status, frozenset())
    if target_status not in allowed:
        raise InvalidRunTransitionError(
            f"Invalid RunStatus transition '{current_status.value}' -> '{target_status.value}'."
        )
    return target_status


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    SKIPPED = "skipped"

    @classmethod
    def coerce(cls, value: object) -> "TaskStatus":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        raise InvalidTaskTransitionError(
            f"Invalid TaskStatus '{value}': expected one of {[m.value for m in cls]}."
        )

    @property
    def is_terminal(self) -> bool:
        return self in (TaskStatus.DONE, TaskStatus.SKIPPED)


ALLOWED_TASK_TRANSITIONS: Mapping[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.SKIPPED}),
    TaskStatus.IN_PROGRESS: frozenset(
        {TaskStatus.BLOCKED, TaskStatus.DONE, TaskStatus.SKIPPED}
    ),
    TaskStatus.BLOCKED: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.SKIPPED}),
    TaskStatus.DONE: frozenset(),
    TaskStatus.SKIPPED: frozenset(),
}


def validate_task_status_transition(
    current: TaskStatus | str,
    target: TaskStatus | str,
) -> TaskStatus:
    current_status = TaskStatus.coerce(current)
    target_status = TaskStatus.coerce(target)
    allowed = ALLOWED_TASK_TRANSITIONS.get(current_status, frozenset())
    if target_status not in allowed:
        raise InvalidTaskTransitionError(
            f"Invalid TaskStatus transition '{current_status.value}' -> '{target_status.value}'."
        )
    return target_status


class GateDisposition(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    WAIVED = "waived"

    @classmethod
    def coerce(cls, value: object) -> "GateDisposition":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            aliases = {
                "pending": cls.PENDING,
                "ack": cls.ACKNOWLEDGED,
                "acknowledge": cls.ACKNOWLEDGED,
                "acknowledged": cls.ACKNOWLEDGED,
                "waive": cls.WAIVED,
                "waived": cls.WAIVED,
            }
            if normalized in aliases:
                return aliases[normalized]
        raise InvalidGateTransitionError(
            f"Invalid GateDisposition '{value}': expected 'acknowledge'/'acknowledged' or 'waive'/'waived'."
        )

    @property
    def is_addressed(self) -> bool:
        return self in (GateDisposition.ACKNOWLEDGED, GateDisposition.WAIVED)


ALLOWED_GATE_TRANSITIONS: Mapping[GateDisposition, frozenset[GateDisposition]] = {
    GateDisposition.PENDING: frozenset(
        {GateDisposition.ACKNOWLEDGED, GateDisposition.WAIVED}
    ),
    GateDisposition.ACKNOWLEDGED: frozenset(),
    GateDisposition.WAIVED: frozenset(),
}


def validate_gate_transition(
    current: GateDisposition | str,
    target: GateDisposition | str,
    *,
    waivable: bool,
    reason: str = "",
) -> GateDisposition:
    current_disp = GateDisposition.coerce(current)
    target_disp = GateDisposition.coerce(target)
    allowed = ALLOWED_GATE_TRANSITIONS.get(current_disp, frozenset())
    if target_disp not in allowed:
        raise InvalidGateTransitionError(
            f"Invalid GateDisposition transition '{current_disp.value}' -> '{target_disp.value}'."
        )
    if target_disp == GateDisposition.WAIVED:
        if not waivable:
            raise InvalidGateTransitionError(
                "Gate is not waivable under the active ExecutionContract."
            )
        if not isinstance(reason, str) or not reason.strip():
            raise InvalidGateTransitionError(
                "A non-empty '--reason' is required when waiving a gate."
            )
    return target_disp


CANONICAL_TASK_STATE_KEYS = frozenset({"id", "description", "status", "reason"})
CANONICAL_GATE_STATE_KEYS = frozenset(
    {
        "id",
        "kind",
        "phase",
        "required",
        "waivable",
        "disposition",
        "reason",
    }
)
CANONICAL_RUN_STATE_KEYS = frozenset(
    {
        "schema_version",
        "run_id",
        "revision",
        "status",
        "tasks",
        "gates",
        "change_kind",
        "reason",
        "content_digest",
    }
)
CANONICAL_RUN_RECORD_KEYS = frozenset(
    {
        "schema_version",
        "id",
        "spec_id",
        "spec_revision",
        "contract_digest",
        "current_state_revision",
    }
)


@dataclass(frozen=True)
class TaskState:
    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    reason: str = ""

    def __post_init__(self):
        object.__setattr__(self, "id", validate_task_id(self.id, "TaskState.id"))
        if not isinstance(self.description, str) or not self.description.strip():
            raise InvalidRunStateError(
                "TaskState.description must be a non-empty string."
            )
        object.__setattr__(self, "description", self.description.strip())
        try:
            object.__setattr__(self, "status", TaskStatus.coerce(self.status))
        except InvalidTaskTransitionError as exc:
            raise InvalidRunStateError(str(exc)) from exc
        if not isinstance(self.reason, str):
            raise InvalidRunStateError("TaskState.reason must be a string.")
        object.__setattr__(self, "reason", self.reason.strip())

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "TaskState":
        if not isinstance(payload, Mapping):
            raise InvalidRunStateError("TaskState payload must be a JSON object.")
        unknown = set(payload.keys()) - CANONICAL_TASK_STATE_KEYS
        if unknown:
            raise InvalidRunStateError(
                f"Unexpected fields in TaskState: {sorted(unknown)}."
            )
        missing = CANONICAL_TASK_STATE_KEYS - set(payload.keys())
        if missing:
            raise InvalidRunStateError(
                f"Missing required fields in TaskState: {sorted(missing)}."
            )
        try:
            return cls(
                id=str(payload["id"]),
                description=str(payload["description"]),
                status=TaskStatus.coerce(payload["status"]),
                reason=str(payload["reason"]),
            )
        except ExecutionError as exc:
            raise InvalidRunStateError(str(exc)) from exc


@dataclass(frozen=True)
class GateState:
    id: str
    kind: GateKind
    phase: GatePhase
    required: bool
    waivable: bool
    disposition: GateDisposition = GateDisposition.PENDING
    reason: str = ""

    def __post_init__(self):
        if not isinstance(self.id, str) or not GATE_ID_RE.match(self.id.strip()):
            raise InvalidRunStateError(
                f"Invalid GateState.id '{self.id}': must match {GATE_ID_RE.pattern}."
            )
        object.__setattr__(self, "id", self.id.strip())
        try:
            object.__setattr__(self, "kind", GateKind.coerce(self.kind))
            object.__setattr__(self, "phase", GatePhase.coerce(self.phase))
        except ExecutionError as exc:
            raise InvalidRunStateError(str(exc)) from exc
        if not isinstance(self.required, bool) or not isinstance(self.waivable, bool):
            raise InvalidRunStateError(
                "GateState 'required' and 'waivable' must be booleans."
            )
        if not isinstance(self.disposition, GateDisposition):
            if (
                isinstance(self.disposition, str)
                and self.disposition.strip().lower()
                in {"pending", "acknowledged", "waived"}
            ):
                object.__setattr__(
                    self,
                    "disposition",
                    GateDisposition(self.disposition.strip().lower()),
                )
            else:
                raise InvalidRunStateError(
                    f"Invalid GateState.disposition '{self.disposition}'."
                )
        if not isinstance(self.reason, str):
            raise InvalidRunStateError("GateState.reason must be a string.")
        cleaned_reason = self.reason.strip()
        if self.disposition == GateDisposition.WAIVED:
            if not self.waivable:
                raise InvalidRunStateError(
                    f"Gate '{self.id}' is marked waived in state snapshot but is not waivable."
                )
            if not cleaned_reason:
                raise InvalidRunStateError(
                    f"Gate '{self.id}' is marked waived in state snapshot without a reason."
                )
        object.__setattr__(self, "reason", cleaned_reason)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "phase": self.phase.value,
            "required": self.required,
            "waivable": self.waivable,
            "disposition": self.disposition.value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "GateState":
        if not isinstance(payload, Mapping):
            raise InvalidRunStateError("GateState payload must be a JSON object.")
        unknown = set(payload.keys()) - CANONICAL_GATE_STATE_KEYS
        if unknown:
            raise InvalidRunStateError(
                f"Unexpected fields in GateState: {sorted(unknown)}."
            )
        missing = CANONICAL_GATE_STATE_KEYS - set(payload.keys())
        if missing:
            raise InvalidRunStateError(
                f"Missing required fields in GateState: {sorted(missing)}."
            )
        raw_disp = payload["disposition"]
        if not isinstance(raw_disp, str) or raw_disp not in {
            "pending",
            "acknowledged",
            "waived",
        }:
            raise InvalidRunStateError(
                f"Invalid GateState.disposition '{raw_disp}'."
            )
        return cls(
            id=str(payload["id"]),
            kind=GateKind.coerce(payload["kind"]),
            phase=GatePhase.coerce(payload["phase"]),
            required=payload["required"],  # type: ignore[arg-type]
            waivable=payload["waivable"],  # type: ignore[arg-type]
            disposition=GateDisposition(raw_disp),
            reason=str(payload["reason"]),
        )


@dataclass(frozen=True)
class RunState:
    schema_version: int
    run_id: str
    revision: int
    status: RunStatus
    tasks: tuple[TaskState, ...]
    gates: tuple[GateState, ...]
    change_kind: str
    reason: str
    content_digest: str = ""

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != RUN_STATE_SCHEMA_VERSION
        ):
            raise InvalidRunStateError(
                f"Unsupported RunState schema_version '{self.schema_version}': expected {RUN_STATE_SCHEMA_VERSION}."
            )
        try:
            validated_run_id = validate_run_id(self.run_id, "RunState.run_id")
        except ExecutionError as exc:
            raise InvalidRunStateError(str(exc)) from exc
        object.__setattr__(self, "run_id", validated_run_id)

        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 1
        ):
            raise InvalidRunStateError(
                f"Invalid RunState.revision '{self.revision}': must be a positive integer."
            )

        try:
            object.__setattr__(self, "status", RunStatus.coerce(self.status))
        except InvalidRunTransitionError as exc:
            raise InvalidRunStateError(str(exc)) from exc

        if isinstance(self.tasks, (str, bytes)) or not isinstance(
            self.tasks, Iterable
        ):
            raise InvalidRunStateError("RunState.tasks must be a list.")
        tasks_tuple = tuple(
            t if isinstance(t, TaskState) else TaskState.from_dict(t)  # type: ignore[arg-type]
            for t in self.tasks
        )
        for idx, task in enumerate(tasks_tuple, start=1):
            expected_id = format_task_id(idx)
            if task.id != expected_id:
                raise InvalidRunStateError(
                    f"RunState tasks must be contiguous starting at T001: expected '{expected_id}', got '{task.id}'."
                )
        object.__setattr__(self, "tasks", tasks_tuple)

        if isinstance(self.gates, (str, bytes)) or not isinstance(
            self.gates, Iterable
        ):
            raise InvalidRunStateError("RunState.gates must be a list.")
        gates_tuple = tuple(
            g if isinstance(g, GateState) else GateState.from_dict(g)  # type: ignore[arg-type]
            for g in self.gates
        )
        seen_gates: set[str] = set()
        for gate in gates_tuple:
            if gate.id in seen_gates:
                raise InvalidRunStateError(
                    f"Duplicate gate '{gate.id}' in RunState."
                )
            seen_gates.add(gate.id)
        object.__setattr__(self, "gates", gates_tuple)

        if not isinstance(self.change_kind, str) or not self.change_kind.strip():
            raise InvalidRunStateError(
                "RunState.change_kind must be a non-empty string."
            )
        object.__setattr__(self, "change_kind", self.change_kind.strip())

        if not isinstance(self.reason, str):
            raise InvalidRunStateError("RunState.reason must be a string.")
        object.__setattr__(self, "reason", self.reason.strip())

        computed_digest = self._compute_content_digest()
        if self.content_digest:
            validated_digest = _validate_sha256(
                self.content_digest,
                "RunState.content_digest",
                InvalidRunStateError,
            )
            if validated_digest != computed_digest:
                raise InvalidRunStateError(
                    "RunState 'content_digest' does not match canonical state content."
                )
        object.__setattr__(self, "content_digest", computed_digest)

    def _canonical_content_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "revision": self.revision,
            "status": self.status.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "gates": [g.to_dict() for g in self.gates],
            "change_kind": self.change_kind,
            "reason": self.reason,
        }

    def _compute_content_digest(self) -> str:
        return sha256_canonical_json(self._canonical_content_payload())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "revision": self.revision,
            "status": self.status.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "gates": [g.to_dict() for g in self.gates],
            "change_kind": self.change_kind,
            "reason": self.reason,
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
    ) -> "RunState":
        if not isinstance(payload, Mapping):
            raise InvalidRunStateError("RunState payload must be a JSON object.")
        unknown = set(payload.keys()) - CANONICAL_RUN_STATE_KEYS
        if unknown:
            raise InvalidRunStateError(
                f"Unexpected fields in RunState: {sorted(unknown)}."
            )
        missing = CANONICAL_RUN_STATE_KEYS - set(payload.keys())
        if missing:
            raise InvalidRunStateError(
                f"Missing required fields in RunState: {sorted(missing)}."
            )
        raw_tasks = payload["tasks"]
        raw_gates = payload["gates"]
        if not isinstance(raw_tasks, list) or not isinstance(raw_gates, list):
            raise InvalidRunStateError(
                "RunState 'tasks' and 'gates' must be lists."
            )
        tasks = tuple(TaskState.from_dict(t) for t in raw_tasks)
        gates = tuple(GateState.from_dict(g) for g in raw_gates)
        try:
            status = RunStatus.coerce(payload["status"])
        except InvalidRunTransitionError as exc:
            raise InvalidRunStateError(str(exc)) from exc
        raw_digest = str(payload["content_digest"]) if verify_digest else ""
        return cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            run_id=str(payload["run_id"]),
            revision=payload["revision"],  # type: ignore[arg-type]
            status=status,
            tasks=tasks,
            gates=gates,
            change_kind=str(payload["change_kind"]),
            reason=str(payload["reason"]),
            content_digest=raw_digest,
        )

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        verify_digest: bool = True,
    ) -> "RunState":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidRunStateError(
                f"Invalid RunState JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise InvalidRunStateError("RunState JSON root must be an object.")
        return cls.from_dict(payload, verify_digest=verify_digest)


def build_initial_run_state(contract: ExecutionContract) -> RunState:
    """Create state revision 1 (`PREPARED`) from an `ExecutionContract`."""
    if not isinstance(contract, ExecutionContract):
        raise InvalidRunStateError(
            "build_initial_run_state requires an ExecutionContract instance."
        )
    tasks = tuple(
        TaskState(
            id=t.id,
            description=t.description,
            status=TaskStatus.PENDING,
            reason="",
        )
        for t in contract.tasks
    )
    gates = tuple(
        GateState(
            id=g.id,
            kind=g.kind,
            phase=g.phase,
            required=g.required,
            waivable=g.waivable,
            disposition=GateDisposition.PENDING,
            reason="",
        )
        for g in contract.gates
    )
    return RunState(
        schema_version=RUN_STATE_SCHEMA_VERSION,
        run_id=contract.run_id,
        revision=1,
        status=RunStatus.PREPARED,
        tasks=tasks,
        gates=gates,
        change_kind="run.prepared",
        reason="Initial run state prepared from execution contract.",
    )


def verify_run_state_against_contract(
    state: RunState,
    contract: ExecutionContract,
) -> None:
    """Verify that `state` matches `contract` run_id, task IDs/descriptions, and gate IDs/metadata."""
    if state.run_id != contract.run_id:
        raise InvalidRunStateError(
            f"RunState run_id '{state.run_id}' does not match contract run_id '{contract.run_id}'."
        )
    if len(state.tasks) != len(contract.tasks):
        raise InvalidRunStateError(
            f"RunState r{state.revision} task count ({len(state.tasks)}) does not match contract task count ({len(contract.tasks)})."
        )
    for st_task, ct_task in zip(state.tasks, contract.tasks):
        if st_task.id != ct_task.id or st_task.description != ct_task.description:
            raise InvalidRunStateError(
                f"RunState r{state.revision} task '{st_task.id}' diverges from contract task '{ct_task.id}'."
            )
    if len(state.gates) != len(contract.gates):
        raise InvalidRunStateError(
            f"RunState r{state.revision} gate count ({len(state.gates)}) does not match contract gate count ({len(contract.gates)})."
        )
    for st_gate, ct_gate in zip(state.gates, contract.gates):
        if (
            st_gate.id != ct_gate.id
            or st_gate.kind != ct_gate.kind
            or st_gate.phase != ct_gate.phase
            or st_gate.required != ct_gate.required
            or st_gate.waivable != ct_gate.waivable
        ):
            raise InvalidRunStateError(
                f"RunState r{state.revision} gate '{st_gate.id}' diverges from contract gate '{ct_gate.id}'."
            )


def enforce_run_transition_preconditions(
    state: RunState,
    target_status: RunStatus,
) -> None:
    """Enforce contractual gate and task preconditions for `ACTIVE` and `FINISHED`."""
    if target_status in (RunStatus.ACTIVE, RunStatus.FINISHED):
        pending_pre_gates = [
            g.id
            for g in state.gates
            if g.phase == GatePhase.PRE_EXECUTION
            and g.required
            and not g.disposition.is_addressed
        ]
        if pending_pre_gates:
            raise ExecutionPreconditionError(
                f"Cannot transition run '{state.run_id}' to '{target_status.value}': required PRE_EXECUTION gate(s) still pending: {', '.join(pending_pre_gates)}."
            )

    if target_status == RunStatus.FINISHED:
        incomplete_tasks = [
            f"{t.id} ({t.status.value})"
            for t in state.tasks
            if not t.status.is_terminal
        ]
        if incomplete_tasks:
            raise ExecutionPreconditionError(
                f"Cannot transition run '{state.run_id}' to 'finished': incomplete task(s): {', '.join(incomplete_tasks)}."
            )
        pending_post_gates = [
            g.id
            for g in state.gates
            if g.phase == GatePhase.POST_EXECUTION
            and g.required
            and not g.disposition.is_addressed
        ]
        if pending_post_gates:
            raise ExecutionPreconditionError(
                f"Cannot transition run '{state.run_id}' to 'finished': required POST_EXECUTION gate(s) still pending: {', '.join(pending_post_gates)}."
            )


def enforce_task_transition_preconditions(
    state: RunState,
    task_id: str,
) -> None:
    """Tasks may only transition while the run is in `RunStatus.ACTIVE`."""
    if state.status != RunStatus.ACTIVE:
        raise ExecutionPreconditionError(
            f"Cannot transition task '{task_id}' for run '{state.run_id}' while status is '{state.status.value}'; run must be 'active'."
        )


def enforce_gate_transition_preconditions(
    state: RunState,
    gate: GateState,
) -> None:
    """Enforce lifecycle phase boundaries for `PRE_EXECUTION` and `POST_EXECUTION` gates."""
    if gate.phase == GatePhase.PRE_EXECUTION:
        if state.status != RunStatus.PREPARED:
            raise ExecutionPreconditionError(
                f"Cannot modify PRE_EXECUTION gate '{gate.id}' for run '{state.run_id}' while status is '{state.status.value}'; PRE_EXECUTION gates may only be modified while 'prepared'."
            )
    elif gate.phase == GatePhase.POST_EXECUTION:
        if state.status != RunStatus.ACTIVE:
            raise ExecutionPreconditionError(
                f"Cannot modify POST_EXECUTION gate '{gate.id}' for run '{state.run_id}' while status is '{state.status.value}'; POST_EXECUTION gates may only be modified while 'active'."
            )
        incomplete_tasks = [
            f"{t.id} ({t.status.value})"
            for t in state.tasks
            if not t.status.is_terminal
        ]
        if incomplete_tasks:
            raise ExecutionPreconditionError(
                f"Cannot modify POST_EXECUTION gate '{gate.id}' for run '{state.run_id}' while task(s) are incomplete: {', '.join(incomplete_tasks)}."
            )


def verify_initial_run_state(state: RunState) -> None:
    """Verify that initial snapshot `s1` (`0001.json`) strictly obeys initial state invariants."""
    if not isinstance(state, RunState):
        raise InvalidRunStateError("Expected a RunState instance for initial state verification.")
    if state.revision != 1:
        raise InvalidRunStateError(
            f"Initial RunState must have revision 1, got {state.revision}."
        )
    if state.status != RunStatus.PREPARED:
        raise InvalidRunStateError(
            f"Initial RunState s1 for run '{state.run_id}' must have status 'prepared', got '{state.status.value}'."
        )
    if state.change_kind != "run.prepared":
        raise InvalidRunStateError(
            f"Initial RunState s1 for run '{state.run_id}' must have change_kind 'run.prepared', got '{state.change_kind}'."
        )
    non_pending_tasks = [
        t.id for t in state.tasks if t.status != TaskStatus.PENDING or t.reason != ""
    ]
    if non_pending_tasks:
        raise InvalidRunStateError(
            f"Initial RunState s1 for run '{state.run_id}' must have all tasks in 'pending' status with empty reason; invalid task(s): {', '.join(non_pending_tasks)}."
        )
    non_pending_gates = [
        g.id
        for g in state.gates
        if g.disposition != GateDisposition.PENDING or g.reason != ""
    ]
    if non_pending_gates:
        raise InvalidRunStateError(
            f"Initial RunState s1 for run '{state.run_id}' must have all gates in 'pending' disposition with empty reason; invalid gate(s): {', '.join(non_pending_gates)}."
        )


def verify_run_state_transition(
    previous: RunState,
    current: RunState,
) -> None:
    """Pure semantic verification proving `previous` (sN) -> `current` (sN+1) is a single legal transition."""
    if not isinstance(previous, RunState) or not isinstance(current, RunState):
        raise InvalidRunStateError(
            "verify_run_state_transition requires two RunState instances."
        )
    if current.run_id != previous.run_id:
        raise InvalidRunStateError(
            f"State transition run_id mismatch: s{previous.revision} has '{previous.run_id}', s{current.revision} has '{current.run_id}'."
        )
    if current.revision != previous.revision + 1:
        raise InvalidRunStateError(
            f"State transition revision mismatch: expected revision {previous.revision + 1} after s{previous.revision}, got {current.revision}."
        )

    if len(current.tasks) != len(previous.tasks):
        raise InvalidRunStateError(
            f"State s{current.revision} task count ({len(current.tasks)}) differs from s{previous.revision} ({len(previous.tasks)})."
        )
    for prev_t, curr_t in zip(previous.tasks, current.tasks):
        if prev_t.id != curr_t.id or prev_t.description != curr_t.description:
            raise InvalidRunStateError(
                f"State s{current.revision} task definition '{curr_t.id}' diverges from s{previous.revision} '{prev_t.id}'."
            )

    if len(current.gates) != len(previous.gates):
        raise InvalidRunStateError(
            f"State s{current.revision} gate count ({len(current.gates)}) differs from s{previous.revision} ({len(previous.gates)})."
        )
    for prev_g, curr_g in zip(previous.gates, current.gates):
        if (
            prev_g.id != curr_g.id
            or prev_g.kind != curr_g.kind
            or prev_g.phase != curr_g.phase
            or prev_g.required != curr_g.required
            or prev_g.waivable != curr_g.waivable
        ):
            raise InvalidRunStateError(
                f"State s{current.revision} gate definition '{curr_g.id}' diverges from s{previous.revision} '{prev_g.id}'."
            )

    status_changed = current.status != previous.status
    changed_tasks = [
        (prev_t, curr_t)
        for prev_t, curr_t in zip(previous.tasks, current.tasks)
        if prev_t != curr_t
    ]
    changed_gates = [
        (prev_g, curr_g)
        for prev_g, curr_g in zip(previous.gates, current.gates)
        if prev_g != curr_g
    ]

    mutation_categories = (
        (1 if status_changed else 0)
        + (1 if changed_tasks else 0)
        + (1 if changed_gates else 0)
    )
    if (
        mutation_categories != 1
        or len(changed_tasks) > 1
        or len(changed_gates) > 1
    ):
        raise InvalidRunStateError(
            f"Invalid state transition s{previous.revision} -> s{current.revision} for run '{current.run_id}': each snapshot must mutate exactly one of run status, one task, or one gate."
        )

    try:
        if status_changed:
            validate_run_status_transition(previous.status, current.status)
            enforce_run_transition_preconditions(previous, current.status)
            expected_kind = f"run.status.{current.status.value}"
            if current.change_kind != expected_kind:
                raise InvalidRunStateError(
                    f"State s{current.revision} change_kind '{current.change_kind}' does not match status transition '{expected_kind}'."
                )
        elif changed_tasks:
            prev_t, curr_t = changed_tasks[0]
            if prev_t.status == curr_t.status:
                raise InvalidRunStateError(
                    f"State s{current.revision} mutates task '{curr_t.id}' without changing status."
                )
            enforce_task_transition_preconditions(previous, curr_t.id)
            validate_task_status_transition(prev_t.status, curr_t.status)
            expected_kind = f"task.{curr_t.id}.{curr_t.status.value}"
            if current.change_kind != expected_kind:
                raise InvalidRunStateError(
                    f"State s{current.revision} change_kind '{current.change_kind}' does not match task transition '{expected_kind}'."
                )
        else:
            prev_g, curr_g = changed_gates[0]
            if prev_g.disposition == curr_g.disposition:
                raise InvalidRunStateError(
                    f"State s{current.revision} mutates gate '{curr_g.id}' without changing disposition."
                )
            validate_gate_transition(
                prev_g.disposition,
                curr_g.disposition,
                waivable=curr_g.waivable,
                reason=curr_g.reason,
            )
            enforce_gate_transition_preconditions(previous, curr_g)
            expected_kind = f"gate.{curr_g.id}.{curr_g.disposition.value}"
            if current.change_kind != expected_kind:
                raise InvalidRunStateError(
                    f"State s{current.revision} change_kind '{current.change_kind}' does not match gate transition '{expected_kind}'."
                )
    except ExecutionError as exc:
        if isinstance(exc, InvalidRunStateError):
            raise
        raise InvalidRunStateError(str(exc), path=exc.path) from exc


@dataclass(frozen=True)
class RunRecord:
    schema_version: int
    id: str
    spec_id: str
    spec_revision: int
    contract_digest: str
    current_state_revision: int

    def __post_init__(self):
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != RUN_SCHEMA_VERSION
        ):
            raise InvalidRunRecordError(
                f"Unsupported RunRecord schema_version '{self.schema_version}': expected {RUN_SCHEMA_VERSION}."
            )
        object.__setattr__(self, "id", validate_run_id(self.id, "RunRecord.id"))
        try:
            validated_spec_id = validate_spec_id(self.spec_id, "RunRecord.spec_id")
        except Exception as exc:
            raise InvalidRunRecordError(str(exc)) from exc
        object.__setattr__(self, "spec_id", validated_spec_id)

        if (
            isinstance(self.spec_revision, bool)
            or not isinstance(self.spec_revision, int)
            or self.spec_revision < 1
        ):
            raise InvalidRunRecordError(
                f"Invalid RunRecord.spec_revision '{self.spec_revision}': must be a positive integer."
            )
        object.__setattr__(
            self,
            "contract_digest",
            _validate_sha256(
                self.contract_digest,
                "RunRecord.contract_digest",
                InvalidRunRecordError,
            ),
        )
        if (
            isinstance(self.current_state_revision, bool)
            or not isinstance(self.current_state_revision, int)
            or self.current_state_revision < 1
        ):
            raise InvalidRunRecordError(
                f"Invalid RunRecord.current_state_revision '{self.current_state_revision}': must be a positive integer."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "spec_id": self.spec_id,
            "spec_revision": self.spec_revision,
            "contract_digest": self.contract_digest,
            "current_state_revision": self.current_state_revision,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "RunRecord":
        if not isinstance(payload, Mapping):
            raise InvalidRunRecordError(
                "RunRecord payload must be a JSON object."
            )
        unknown = set(payload.keys()) - CANONICAL_RUN_RECORD_KEYS
        if unknown:
            raise InvalidRunRecordError(
                f"Unexpected fields in RunRecord: {sorted(unknown)}."
            )
        missing = CANONICAL_RUN_RECORD_KEYS - set(payload.keys())
        if missing:
            raise InvalidRunRecordError(
                f"Missing required fields in RunRecord: {sorted(missing)}."
            )
        return cls(
            schema_version=payload["schema_version"],  # type: ignore[arg-type]
            id=str(payload["id"]),
            spec_id=str(payload["spec_id"]),
            spec_revision=payload["spec_revision"],  # type: ignore[arg-type]
            contract_digest=str(payload["contract_digest"]),
            current_state_revision=payload["current_state_revision"],  # type: ignore[arg-type]
        )

    @classmethod
    def from_json(cls, raw: str) -> "RunRecord":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InvalidRunRecordError(
                f"Invalid RunRecord JSON: {exc.msg}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise InvalidRunRecordError("RunRecord JSON root must be an object.")
        return cls.from_dict(payload)

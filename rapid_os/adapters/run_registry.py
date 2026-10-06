import json
from pathlib import Path

from rapid_os.adapters.context_sources import ContextSourceLoader
from rapid_os.adapters.execution_policy import load_execution_policy
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.core.filesystem import (
    ensure_path_within_root,
    resolve_child_path,
    safe_write_text,
)
from rapid_os.domain.context import (
    ContextCompiler,
    ContextManifest,
    ContextRequest,
)
from rapid_os.domain.execution import (
    RUN_SCHEMA_VERSION,
    RUN_STATE_SCHEMA_VERSION,
    ContextSnapshotMismatchError,
    DuplicateRunIdentityError,
    ExecutionClass,
    ExecutionContract,
    ExecutionError,
    ExecutionPolicy,
    ExecutionPolicyEvaluator,
    GateDisposition,
    GateState,
    InvalidExecutionContractError,
    InvalidGateTransitionError,
    InvalidRunRecordError,
    InvalidRunStateError,
    InvalidRunTransitionError,
    InvalidSpecBindingError,
    InvalidTaskTransitionError,
    RiskLevel,
    RunNotFoundError,
    RunRecord,
    RunState,
    RunStateHistoryGapError,
    RunStatus,
    TaskState,
    TaskStatus,
    UnsafeRunPathError,
    build_execution_contract,
    build_initial_run_state,
    derive_run_id,
    enforce_run_transition_preconditions,
    format_state_file_name,
    sha256_utf8,
    validate_gate_transition,
    validate_run_id,
    validate_run_status_transition,
    validate_task_id,
    validate_task_status_transition,
    verify_run_state_against_contract,
)
from rapid_os.domain.specs import SpecRegistryError, SpecStatus


RUNS_DIRNAME = "runs"
RUN_RECORD_FILENAME = "run.json"
CONTRACT_FILENAME = "contract.json"
CONTEXT_SNAPSHOT_FILENAME = "context.md"
CONTEXT_MANIFEST_FILENAME = "context-manifest.json"
STATES_DIRNAME = "states"


def resolve_runs_root_dir(
    project_root: Path,
    project_rapid_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Return `(root, rapid_dir, runs_dir)` with containment verification."""
    raw_first = Path(project_root)
    if project_rapid_dir is None and raw_first.name == ".rapid-os":
        rapid_dir = raw_first
        root = rapid_dir.parent
    else:
        root = raw_first
        rapid_dir = (
            Path(project_rapid_dir)
            if project_rapid_dir is not None
            else (root / ".rapid-os")
        )

    try:
        contained_rapid = ensure_path_within_root(root, rapid_dir)
        runs_dir = resolve_child_path(
            contained_rapid,
            RUNS_DIRNAME,
            single_segment=True,
        )
        ensure_path_within_root(root, runs_dir)
    except ValueError as exc:
        raise UnsafeRunPathError(
            str(exc),
            path=rapid_dir / RUNS_DIRNAME,
        ) from exc

    return root, contained_rapid, runs_dir


class RunRegistry:
    """Filesystem-backed canonical Run Registry under `.rapid-os/runs/`."""

    def __init__(
        self,
        project_root: Path = Path("."),
        project_rapid_dir: Path | None = None,
    ):
        root, rapid_dir, runs_dir = resolve_runs_root_dir(
            project_root,
            project_rapid_dir,
        )
        self.root = root
        self.rapid_dir = rapid_dir
        self.runs_dir = runs_dir

    def _resolve_run_dir(self, run_id: str) -> Path:
        validated_id = validate_run_id(run_id)
        if self.runs_dir.is_symlink():
            raise UnsafeRunPathError(
                f"Runs registry root '{self.runs_dir}' cannot be a symlink.",
                path=self.runs_dir,
            )
        try:
            run_dir = resolve_child_path(
                self.runs_dir,
                validated_id,
                single_segment=True,
            )
            ensure_path_within_root(self.root, run_dir)
        except ValueError as exc:
            raise UnsafeRunPathError(str(exc), path=run_id) from exc
        if run_dir.is_symlink():
            raise UnsafeRunPathError(
                f"Run directory '{run_id}' cannot be a symlink.",
                path=run_dir,
            )
        return run_dir

    def _resolve_states_dir(self, run_dir: Path) -> Path:
        try:
            states_dir = resolve_child_path(
                run_dir,
                STATES_DIRNAME,
                single_segment=True,
            )
            ensure_path_within_root(self.root, states_dir)
        except ValueError as exc:
            raise UnsafeRunPathError(str(exc), path=run_dir) from exc
        if states_dir.is_symlink():
            raise UnsafeRunPathError(
                f"Run states directory '{states_dir}' cannot be a symlink.",
                path=states_dir,
            )
        return states_dir

    def _resolve_state_file(self, run_dir: Path, revision: int) -> Path:
        states_dir = self._resolve_states_dir(run_dir)
        filename = format_state_file_name(revision)
        try:
            state_file = resolve_child_path(
                states_dir,
                filename,
                single_segment=True,
            )
            ensure_path_within_root(self.root, state_file)
        except ValueError as exc:
            raise UnsafeRunPathError(str(exc), path=states_dir) from exc
        if state_file.is_symlink():
            raise UnsafeRunPathError(
                f"Run state file '{filename}' cannot be a symlink.",
                path=state_file,
            )
        return state_file

    def _read_run_record_from_dir(
        self,
        run_dir: Path,
        expected_id: str,
    ) -> RunRecord:
        try:
            record_file = resolve_child_path(
                run_dir,
                RUN_RECORD_FILENAME,
                single_segment=True,
            )
            ensure_path_within_root(self.root, record_file)
        except ValueError as exc:
            raise UnsafeRunPathError(str(exc), path=run_dir) from exc

        if record_file.is_symlink():
            raise UnsafeRunPathError(
                f"Run record '{record_file}' cannot be a symlink.",
                path=record_file,
            )
        if not record_file.exists():
            raise InvalidRunRecordError(
                f"Run record '{RUN_RECORD_FILENAME}' is missing for '{expected_id}'.",
                path=record_file,
            )
        if not record_file.is_file():
            raise UnsafeRunPathError(
                f"Run record '{record_file}' is not a regular file.",
                path=record_file,
            )

        try:
            raw = record_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnsafeRunPathError(
                f"Run record '{record_file}' could not be read as UTF-8: {exc}",
                path=record_file,
            ) from exc

        try:
            record = RunRecord.from_json(raw)
        except ExecutionError as exc:
            raise type(exc)(str(exc), code=exc.code, path=record_file) from exc

        if record.id != expected_id:
            raise DuplicateRunIdentityError(
                f"RunRecord.id '{record.id}' does not match directory '{expected_id}'.",
                path=record_file,
            )
        return record

    def _read_and_verify_contract_from_dir(
        self,
        run_dir: Path,
        record: RunRecord,
    ) -> ExecutionContract:
        try:
            contract_file = resolve_child_path(
                run_dir,
                CONTRACT_FILENAME,
                single_segment=True,
            )
            context_file = resolve_child_path(
                run_dir,
                CONTEXT_SNAPSHOT_FILENAME,
                single_segment=True,
            )
            manifest_file = resolve_child_path(
                run_dir,
                CONTEXT_MANIFEST_FILENAME,
                single_segment=True,
            )
            ensure_path_within_root(self.root, contract_file)
            ensure_path_within_root(self.root, context_file)
            ensure_path_within_root(self.root, manifest_file)
        except ValueError as exc:
            raise UnsafeRunPathError(str(exc), path=run_dir) from exc

        if contract_file.is_symlink():
            raise UnsafeRunPathError(
                f"Execution contract '{contract_file}' cannot be a symlink.",
                path=contract_file,
            )
        if not contract_file.exists():
            raise InvalidExecutionContractError(
                f"Execution contract '{CONTRACT_FILENAME}' is missing for run '{record.id}'.",
                path=contract_file,
            )
        if not contract_file.is_file():
            raise UnsafeRunPathError(
                f"Execution contract '{contract_file}' is not a regular file.",
                path=contract_file,
            )

        try:
            raw_contract = contract_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnsafeRunPathError(
                f"Execution contract '{contract_file}' could not be read as UTF-8: {exc}",
                path=contract_file,
            ) from exc

        try:
            contract = ExecutionContract.from_json(raw_contract, verify_digest=True)
        except ExecutionError as exc:
            raise type(exc)(str(exc), code=exc.code, path=contract_file) from exc

        if contract.run_id != record.id:
            raise InvalidExecutionContractError(
                f"ExecutionContract.run_id '{contract.run_id}' does not match RunRecord.id '{record.id}'.",
                path=contract_file,
            )
        if (
            contract.spec_id != record.spec_id
            or contract.spec_revision != record.spec_revision
        ):
            raise InvalidSpecBindingError(
                f"ExecutionContract spec binding ({contract.spec_id}@r{contract.spec_revision}) does not match RunRecord ({record.spec_id}@r{record.spec_revision}).",
                path=contract_file,
            )
        if contract.contract_digest != record.contract_digest:
            raise InvalidExecutionContractError(
                f"ExecutionContract digest '{contract.contract_digest}' does not match RunRecord.contract_digest '{record.contract_digest}'.",
                path=contract_file,
            )

        # Verify persisted context snapshot and context-manifest snapshot
        for snap_file, label in (
            (context_file, CONTEXT_SNAPSHOT_FILENAME),
            (manifest_file, CONTEXT_MANIFEST_FILENAME),
        ):
            if snap_file.is_symlink():
                raise UnsafeRunPathError(
                    f"Run context snapshot '{snap_file}' cannot be a symlink.",
                    path=snap_file,
                )
            if not snap_file.exists():
                raise ContextSnapshotMismatchError(
                    f"Run context snapshot '{label}' is missing for run '{record.id}'.",
                    path=snap_file,
                )
            if not snap_file.is_file():
                raise UnsafeRunPathError(
                    f"Run context snapshot '{snap_file}' is not a regular file.",
                    path=snap_file,
                )

        try:
            raw_context = context_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnsafeRunPathError(
                f"Context snapshot '{context_file}' could not be read as UTF-8: {exc}",
                path=context_file,
            ) from exc

        try:
            raw_manifest = manifest_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnsafeRunPathError(
                f"Context manifest '{manifest_file}' could not be read as UTF-8: {exc}",
                path=manifest_file,
            ) from exc

        if sha256_utf8(raw_context) != contract.context_digest:
            raise ContextSnapshotMismatchError(
                f"Context snapshot '{CONTEXT_SNAPSHOT_FILENAME}' digest mismatch for run '{record.id}'.",
                path=context_file,
            )
        if sha256_utf8(raw_manifest) != contract.context_manifest_digest:
            raise ContextSnapshotMismatchError(
                f"Context manifest '{CONTEXT_MANIFEST_FILENAME}' digest mismatch for run '{record.id}'.",
                path=manifest_file,
            )

        try:
            manifest_payload = json.loads(raw_manifest)
            if not isinstance(manifest_payload, dict):
                raise ValueError("Context manifest JSON must be an object.")
            ContextManifest.from_dict(manifest_payload)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ContextSnapshotMismatchError(
                f"Context manifest '{CONTEXT_MANIFEST_FILENAME}' is invalid for run '{record.id}': {exc}",
                path=manifest_file,
            ) from exc

        return contract

    def _read_and_verify_state_file(
        self,
        run_id: str,
        revision: int,
        state_file: Path,
        contract: ExecutionContract | None = None,
    ) -> RunState:
        if state_file.is_symlink():
            raise UnsafeRunPathError(
                f"Run state file '{state_file}' cannot be a symlink.",
                path=state_file,
            )
        if not state_file.exists():
            raise InvalidRunStateError(
                f"Run state snapshot '{state_file.name}' is missing for run '{run_id}'.",
                path=state_file,
            )
        if not state_file.is_file():
            raise UnsafeRunPathError(
                f"Run state snapshot '{state_file}' is not a regular file.",
                path=state_file,
            )

        try:
            raw_state = state_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnsafeRunPathError(
                f"Run state snapshot '{state_file}' could not be read as UTF-8: {exc}",
                path=state_file,
            ) from exc

        try:
            state = RunState.from_json(raw_state, verify_digest=True)
        except ExecutionError as exc:
            raise type(exc)(str(exc), code=exc.code, path=state_file) from exc

        if state.run_id != run_id:
            raise InvalidRunStateError(
                f"RunState.run_id '{state.run_id}' does not match '{run_id}'.",
                path=state_file,
            )
        if state.revision != revision:
            raise InvalidRunStateError(
                f"RunState.revision '{state.revision}' does not match file '{state_file.name}'.",
                path=state_file,
            )
        if contract is not None:
            try:
                verify_run_state_against_contract(state, contract)
            except ExecutionError as exc:
                raise type(exc)(str(exc), code=exc.code, path=state_file) from exc

        return state

    def _verify_state_history(
        self,
        run_id: str,
        record: RunRecord,
        contract: ExecutionContract | None = None,
    ) -> dict[int, RunState]:
        """Verify that every state snapshot in `1..record.current_state_revision` exists and is valid without gaps."""
        run_dir = self._resolve_run_dir(run_id)
        states_dir = self._resolve_states_dir(run_dir)
        if not states_dir.exists() or not states_dir.is_dir():
            raise RunStateHistoryGapError(
                f"Run states directory is missing for run '{run_id}' (current_state_revision={record.current_state_revision}).",
                path=states_dir,
            )

        verified: dict[int, RunState] = {}
        for rev_num in range(1, record.current_state_revision + 1):
            state_file = self._resolve_state_file(run_dir, rev_num)
            if not state_file.exists() or not state_file.is_file():
                raise RunStateHistoryGapError(
                    f"Required state snapshot s{rev_num} ({state_file.name}) is missing for run '{run_id}' (current_state_revision={record.current_state_revision}).",
                    path=state_file,
                )
            verified[rev_num] = self._read_and_verify_state_file(
                run_id,
                rev_num,
                state_file,
                contract=contract,
            )
        return verified

    def exists(self, run_id: str) -> bool:
        run_dir = self._resolve_run_dir(run_id)
        if not run_dir.exists() or not run_dir.is_dir():
            return False
        record_file = run_dir / RUN_RECORD_FILENAME
        return record_file.exists() and record_file.is_file()

    def list_runs(
        self,
        status: RunStatus | str | None = None,
    ) -> tuple[RunRecord, ...]:
        """Deterministically discover all runs in `.rapid-os/runs/*/run.json` ordered by `id` ASC."""
        if not self.runs_dir.exists():
            return ()
        if self.runs_dir.is_symlink() or not self.runs_dir.is_dir():
            raise UnsafeRunPathError(
                f"Runs registry root '{self.runs_dir}' is not a valid directory.",
                path=self.runs_dir,
            )

        status_filter = (
            RunStatus.coerce(status) if status is not None else None
        )
        records: list[RunRecord] = []
        for entry in sorted(self.runs_dir.iterdir(), key=lambda p: p.name):
            if entry.is_symlink():
                raise UnsafeRunPathError(
                    f"Run entry '{entry}' cannot be a symlink.",
                    path=entry,
                )
            if not entry.is_dir():
                raise InvalidRunRecordError(
                    f"Unexpected non-directory entry '{entry.name}' in run registry.",
                    path=entry,
                )
            validate_run_id(entry.name)
            record = self._read_run_record_from_dir(entry, entry.name)
            if status_filter is not None:
                state = self.get_state(record.id)
                if state.status != status_filter:
                    continue
            records.append(record)

        records.sort(key=lambda r: r.id)
        return tuple(records)

    def get(self, run_id: str) -> RunRecord:
        """Load and validate `RunRecord` for `run_id`, verifying current state file exists."""
        run_dir = self._resolve_run_dir(run_id)
        if not run_dir.exists():
            raise RunNotFoundError(
                f"Run '{run_id}' was not found in registry.",
                path=run_dir,
            )
        if not run_dir.is_dir():
            raise UnsafeRunPathError(
                f"Run path '{run_dir}' is not a directory.",
                path=run_dir,
            )
        record = self._read_run_record_from_dir(run_dir, run_id)
        current_state_file = self._resolve_state_file(
            run_dir,
            record.current_state_revision,
        )
        if not current_state_file.exists() or not current_state_file.is_file():
            raise RunStateHistoryGapError(
                f"Current state snapshot s{record.current_state_revision} ({current_state_file.name}) is missing for run '{run_id}'.",
                path=current_state_file,
            )
        return record

    def get_contract(self, run_id: str) -> ExecutionContract:
        """Load and validate `ExecutionContract` and context snapshot digests for `run_id`."""
        record = self.get(run_id)
        run_dir = self._resolve_run_dir(run_id)
        return self._read_and_verify_contract_from_dir(run_dir, record)

    def get_state(
        self,
        run_id: str,
        revision: int | None = None,
    ) -> RunState:
        """Load and validate a specific or current `RunState` after verifying full `1..current_state_revision` history without fallback."""
        record = self.get(run_id)
        contract = self.get_contract(run_id)
        target_rev = (
            record.current_state_revision if revision is None else revision
        )
        if (
            isinstance(target_rev, bool)
            or not isinstance(target_rev, int)
            or target_rev < 1
        ):
            raise InvalidRunStateError(
                f"Invalid state revision '{target_rev}': must be a positive integer."
            )

        verified_history = self._verify_state_history(
            run_id,
            record,
            contract=contract,
        )
        if target_rev in verified_history:
            return verified_history[target_rev]

        run_dir = self._resolve_run_dir(run_id)
        state_file = self._resolve_state_file(run_dir, target_rev)
        if not state_file.exists() or not state_file.is_file():
            raise RunNotFoundError(
                f"State revision s{target_rev} was not found for run '{run_id}'.",
                path=state_file,
            )
        return self._read_and_verify_state_file(
            run_id,
            target_rev,
            state_file,
            contract=contract,
        )

    def get_artifact_paths(
        self,
        run_id: str,
        state_revision: int | None = None,
    ) -> dict[str, str]:
        """Return portable project-relative paths for all run artifacts."""
        record = self.get(run_id)
        target_rev = (
            record.current_state_revision
            if state_revision is None
            else state_revision
        )
        run_dir = self._resolve_run_dir(record.id)
        state_file = self._resolve_state_file(run_dir, target_rev)
        return {
            "run.json": (run_dir / RUN_RECORD_FILENAME)
            .relative_to(self.root)
            .as_posix(),
            "contract.json": (run_dir / CONTRACT_FILENAME)
            .relative_to(self.root)
            .as_posix(),
            "context.md": (run_dir / CONTEXT_SNAPSHOT_FILENAME)
            .relative_to(self.root)
            .as_posix(),
            "context-manifest.json": (run_dir / CONTEXT_MANIFEST_FILENAME)
            .relative_to(self.root)
            .as_posix(),
            "state.json": state_file.relative_to(self.root).as_posix(),
        }

    def _next_run_id_for_spec(self, spec_id: str, spec_revision: int) -> str:
        ordinal = 1
        while True:
            candidate = derive_run_id(spec_id, spec_revision, ordinal)
            candidate_dir = self._resolve_run_dir(candidate)
            if not candidate_dir.exists() and not candidate_dir.is_symlink():
                return candidate
            ordinal += 1

    def _write_state_snapshot(self, run_dir: Path, state: RunState) -> Path:
        state_file = self._resolve_state_file(run_dir, state.revision)
        safe_write_text(
            state_file,
            state.to_json(indent=2) + "\n",
            encoding="utf-8",
            backup=False,
            create_parents=True,
        )
        return state_file

    def _write_run_record(self, run_dir: Path, record: RunRecord) -> Path:
        record_file = resolve_child_path(
            run_dir,
            RUN_RECORD_FILENAME,
            single_segment=True,
        )
        ensure_path_within_root(self.root, record_file)
        safe_write_text(
            record_file,
            record.to_json(indent=2) + "\n",
            encoding="utf-8",
            backup=False,
            create_parents=True,
        )
        return record_file

    def create(
        self,
        *,
        spec_id: str,
        spec_revision: int | None = None,
        run_id: str | None = None,
        harness: str = "cursor",
        classification: ExecutionClass | str | None = None,
        risk: RiskLevel | str | int | None = None,
        policy: ExecutionPolicy | None = None,
    ) -> RunRecord:
        """Create a new Run bound to an exact `ready` SpecRevision, compiled context snapshot, project model, and policy decision."""
        # 1. Load and validate ready spec + full spec revision history
        try:
            spec_registry = SpecRegistry(self.root, self.rapid_dir)
            spec_record = spec_registry.get(spec_id)
        except SpecRegistryError as exc:
            raise InvalidSpecBindingError(
                f"Cannot bind run to spec '{spec_id}': {exc}",
                path=exc.path,
            ) from exc

        if spec_record.status != SpecStatus.READY:
            raise InvalidSpecBindingError(
                f"Spec '{spec_id}' has status '{spec_record.status.value}'; only 'ready' specs can be used to create a run.",
                path=self.rapid_dir / "specs" / spec_id / "spec.json",
            )

        try:
            resolved_spec_rev = spec_registry.get_revision(
                spec_id,
                revision=spec_revision,
            )
        except SpecRegistryError as exc:
            raise InvalidSpecBindingError(
                f"Cannot load revision for spec '{spec_id}': {exc}",
                path=exc.path,
            ) from exc

        # 2. Load ExecutionPolicy
        if policy is not None:
            resolved_policy = policy
            policy_source = "default"
        else:
            resolved_policy, policy_source = load_execution_policy(
                self.root,
                self.rapid_dir,
            )

        # 3. Compile Context Snapshot for exact SpecRevision
        try:
            context_request = ContextRequest(
                objective=resolved_spec_rev.business_objective,
                mode=resolved_spec_rev.mode.value,
                harness=harness or "cursor",
                affected_paths=resolved_spec_rev.affected_paths,
                tags=resolved_spec_rev.tags,
                spec_id=resolved_spec_rev.spec_id,
                spec_revision=resolved_spec_rev.revision,
            )
        except ValueError as exc:
            raise InvalidExecutionContractError(
                f"Invalid context request for run creation: {exc}"
            ) from exc

        discovery = ContextSourceLoader().load(
            self.root,
            self.rapid_dir,
            request=context_request,
        )
        if discovery.load_errors:
            first_err = discovery.load_errors[0]
            raise ContextSnapshotMismatchError(
                f"Context source load failed for '{first_err.source_id}': {first_err.message}",
                path=first_err.path,
            )

        try:
            compiled_context = ContextCompiler().compile(
                request=context_request,
                sources=discovery.sources,
                project_model=discovery.project_model,
            )
        except ValueError as exc:
            raise ContextSnapshotMismatchError(
                f"Context compilation failed for run creation: {exc}"
            ) from exc

        # 4. Evaluate ExecutionPolicy
        decision = ExecutionPolicyEvaluator().evaluate(
            resolved_spec_rev,
            resolved_policy,
            requested_classification=classification,
            requested_risk=risk,
        )

        # 5. Resolve deterministic Run ID
        if run_id is not None:
            resolved_run_id = validate_run_id(run_id)
            run_dir = self._resolve_run_dir(resolved_run_id)
            if run_dir.exists():
                raise DuplicateRunIdentityError(
                    f"Run '{resolved_run_id}' already exists.",
                    path=run_dir,
                )
        else:
            resolved_run_id = self._next_run_id_for_spec(
                resolved_spec_rev.spec_id,
                resolved_spec_rev.revision,
            )
            run_dir = self._resolve_run_dir(resolved_run_id)

        # 6. Build ExecutionContract and initial RunState (0001)
        contract = build_execution_contract(
            run_id=resolved_run_id,
            spec=resolved_spec_rev,
            compiled_context=compiled_context,
            project_model=discovery.project_model,
            policy=resolved_policy,
            policy_source=policy_source,
            decision=decision,
            harness=context_request.harness,
        )
        initial_state = build_initial_run_state(contract)
        record = RunRecord(
            schema_version=RUN_SCHEMA_VERSION,
            id=resolved_run_id,
            spec_id=contract.spec_id,
            spec_revision=contract.spec_revision,
            contract_digest=contract.contract_digest,
            current_state_revision=1,
        )

        # 7. Persist in commit-point order: context snapshots -> contract.json -> states/0001.json -> verify -> run.json last
        context_text = compiled_context.content
        if not context_text.endswith("\n"):
            context_text = context_text + "\n"
        manifest_text = (
            json.dumps(
                compiled_context.manifest.to_dict(),
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )

        context_file = resolve_child_path(
            run_dir,
            CONTEXT_SNAPSHOT_FILENAME,
            single_segment=True,
        )
        manifest_file = resolve_child_path(
            run_dir,
            CONTEXT_MANIFEST_FILENAME,
            single_segment=True,
        )
        contract_file = resolve_child_path(
            run_dir,
            CONTRACT_FILENAME,
            single_segment=True,
        )
        ensure_path_within_root(self.root, context_file)
        ensure_path_within_root(self.root, manifest_file)
        ensure_path_within_root(self.root, contract_file)

        safe_write_text(
            context_file,
            context_text,
            encoding="utf-8",
            backup=False,
            create_parents=True,
        )
        safe_write_text(
            manifest_file,
            manifest_text,
            encoding="utf-8",
            backup=False,
            create_parents=True,
        )
        safe_write_text(
            contract_file,
            contract.to_json(indent=2) + "\n",
            encoding="utf-8",
            backup=False,
            create_parents=True,
        )
        state_file = self._write_state_snapshot(run_dir, initial_state)

        # Verify persisted contract, context snapshots, and state 0001 before writing run.json
        self._read_and_verify_contract_from_dir(run_dir, record)
        self._read_and_verify_state_file(
            resolved_run_id,
            1,
            state_file,
            contract=contract,
        )

        self._write_run_record(run_dir, record)
        return record

    def _commit_next_state(
        self,
        record: RunRecord,
        contract: ExecutionContract,
        next_state: RunState,
    ) -> RunState:
        run_dir = self._resolve_run_dir(record.id)
        state_file = self._write_state_snapshot(run_dir, next_state)
        verified_state = self._read_and_verify_state_file(
            record.id,
            next_state.revision,
            state_file,
            contract=contract,
        )
        updated_record = RunRecord(
            schema_version=RUN_SCHEMA_VERSION,
            id=record.id,
            spec_id=record.spec_id,
            spec_revision=record.spec_revision,
            contract_digest=record.contract_digest,
            current_state_revision=next_state.revision,
        )
        self._write_run_record(run_dir, updated_record)
        return verified_state

    def transition_status(
        self,
        run_id: str,
        target_status: RunStatus | str,
        *,
        reason: str = "",
    ) -> RunState:
        """Transition RunStatus (`PREPARED -> ACTIVE`, `ACTIVE -> FINISHED`, etc.) creating a new immutable state revision."""
        record = self.get(run_id)
        contract = self.get_contract(run_id)
        current_state = self.get_state(run_id)

        coerced_target = validate_run_status_transition(
            current_state.status,
            target_status,
        )
        enforce_run_transition_preconditions(current_state, coerced_target)

        next_revision = record.current_state_revision + 1
        cleaned_reason = (
            reason.strip()
            if isinstance(reason, str) and reason.strip()
            else f"Run status transitioned from '{current_state.status.value}' to '{coerced_target.value}'."
        )
        next_state = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=record.id,
            revision=next_revision,
            status=coerced_target,
            tasks=current_state.tasks,
            gates=current_state.gates,
            change_kind=f"run.status.{coerced_target.value}",
            reason=cleaned_reason,
        )
        return self._commit_next_state(record, contract, next_state)

    def transition_task(
        self,
        run_id: str,
        task_id: str,
        target_status: TaskStatus | str,
        *,
        reason: str = "",
    ) -> RunState:
        """Transition a task in the run ledger (`T001`, etc.) creating a new immutable state revision."""
        record = self.get(run_id)
        contract = self.get_contract(run_id)
        current_state = self.get_state(run_id)

        if current_state.status.is_terminal:
            raise InvalidRunTransitionError(
                f"Cannot modify tasks for run '{run_id}' in terminal status '{current_state.status.value}'."
            )

        validated_task_id = validate_task_id(task_id)
        coerced_target = TaskStatus.coerce(target_status)

        updated_tasks: list[TaskState] = []
        found = False
        for task in current_state.tasks:
            if task.id == validated_task_id:
                found = True
                validate_task_status_transition(task.status, coerced_target)
                updated_tasks.append(
                    TaskState(
                        id=task.id,
                        description=task.description,
                        status=coerced_target,
                        reason=reason.strip() if isinstance(reason, str) else "",
                    )
                )
            else:
                updated_tasks.append(task)

        if not found:
            raise InvalidTaskTransitionError(
                f"Task '{validated_task_id}' does not exist in run '{run_id}'."
            )

        next_revision = record.current_state_revision + 1
        cleaned_reason = (
            reason.strip()
            if isinstance(reason, str) and reason.strip()
            else f"Task '{validated_task_id}' transitioned to '{coerced_target.value}'."
        )
        next_state = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=record.id,
            revision=next_revision,
            status=current_state.status,
            tasks=tuple(updated_tasks),
            gates=current_state.gates,
            change_kind=f"task.{validated_task_id}.{coerced_target.value}",
            reason=cleaned_reason,
        )
        return self._commit_next_state(record, contract, next_state)

    def transition_gate(
        self,
        run_id: str,
        gate_id: str,
        disposition: GateDisposition | str,
        *,
        reason: str = "",
    ) -> RunState:
        """Acknowledge or waive a gate in the run ledger creating a new immutable state revision."""
        record = self.get(run_id)
        contract = self.get_contract(run_id)
        current_state = self.get_state(run_id)

        if current_state.status.is_terminal:
            raise InvalidRunTransitionError(
                f"Cannot modify gates for run '{run_id}' in terminal status '{current_state.status.value}'."
            )

        if not isinstance(gate_id, str) or not gate_id.strip():
            raise InvalidGateTransitionError("Gate ID must be a non-empty string.")
        cleaned_gate_id = gate_id.strip()
        target_disp = GateDisposition.coerce(disposition)

        updated_gates: list[GateState] = []
        found = False
        for gate in current_state.gates:
            if gate.id == cleaned_gate_id:
                found = True
                validate_gate_transition(
                    gate.disposition,
                    target_disp,
                    waivable=gate.waivable,
                    reason=reason,
                )
                updated_gates.append(
                    GateState(
                        id=gate.id,
                        kind=gate.kind,
                        phase=gate.phase,
                        required=gate.required,
                        waivable=gate.waivable,
                        disposition=target_disp,
                        reason=reason.strip() if isinstance(reason, str) else "",
                    )
                )
            else:
                updated_gates.append(gate)

        if not found:
            raise InvalidGateTransitionError(
                f"Gate '{cleaned_gate_id}' does not exist in run '{run_id}'."
            )

        next_revision = record.current_state_revision + 1
        cleaned_reason = (
            reason.strip()
            if isinstance(reason, str) and reason.strip()
            else f"Gate '{cleaned_gate_id}' marked '{target_disp.value}'."
        )
        next_state = RunState(
            schema_version=RUN_STATE_SCHEMA_VERSION,
            run_id=record.id,
            revision=next_revision,
            status=current_state.status,
            tasks=current_state.tasks,
            gates=tuple(updated_gates),
            change_kind=f"gate.{cleaned_gate_id}.{target_disp.value}",
            reason=cleaned_reason,
        )
        return self._commit_next_state(record, contract, next_state)

    def validate(self):
        from rapid_os.domain.validation import validate_run_registry

        return validate_run_registry(self.rapid_dir, self.root)

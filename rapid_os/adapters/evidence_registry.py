import json
from pathlib import Path
from typing import Iterable, Mapping

from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.core.filesystem import (
    ensure_path_within_root,
    resolve_child_path,
    safe_write_bytes,
    safe_write_text,
)
from rapid_os.domain.evidence import (
    RUN_EVIDENCE_SCHEMA_VERSION,
    EvidenceArtifact,
    EvidenceArtifactIntegrityError,
    EvidenceBindingMismatchError,
    EvidenceError,
    EvidenceKind,
    EvidenceNotFoundError,
    EvidenceOverwriteError,
    EvidenceSequenceGapError,
    InvalidEvidenceIdError,
    InvalidEvidencePayloadError,
    InvalidEvidenceReferenceError,
    InvalidRunEvidenceError,
    RunEvidence,
    UnsafeEvidencePathError,
    compute_evidence_set_digest,
    format_evidence_file_name,
    format_evidence_id,
    is_canonical_evidence_file_name,
    parse_evidence_ordinal,
    sha256_bytes,
    validate_evidence_artifact_path,
    validate_evidence_id,
    validate_relative_posix_path,
    verify_evidence_against_run,
)
from rapid_os.domain.execution import (
    ExecutionContract,
    ExecutionError,
    RunRecord,
    RunState,
    validate_run_id,
)


EVIDENCE_DIRNAME = "evidence"
RECORDS_DIRNAME = "records"
ARTIFACTS_DIRNAME = "artifacts"

ALLOWED_AUTHORING_KEYS = frozenset(
    {
        "kind",
        "producer",
        "summary",
        "state_revision",
        "task_ids",
        "gate_ids",
        "capability_ids",
        "payload",
        "artifacts",
    }
)
REQUIRED_AUTHORING_KEYS = frozenset(
    {
        "kind",
        "producer",
        "summary",
        "payload",
    }
)


def resolve_evidence_root_dir(
    project_root: Path,
    project_rapid_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Return `(root, rapid_dir, evidence_dir)` with containment verification."""
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
        evidence_dir = resolve_child_path(
            contained_rapid,
            EVIDENCE_DIRNAME,
            single_segment=True,
        )
        ensure_path_within_root(root, evidence_dir)
    except ValueError as exc:
        raise UnsafeEvidencePathError(
            str(exc),
            path=rapid_dir / EVIDENCE_DIRNAME,
        ) from exc

    return root, contained_rapid, evidence_dir


class EvidenceRegistry:
    """Append-only filesystem Evidence Registry under `.rapid-os/evidence/<run-id>/`."""

    def __init__(
        self,
        project_root: Path = Path("."),
        project_rapid_dir: Path | None = None,
    ):
        root, rapid_dir, evidence_dir = resolve_evidence_root_dir(
            project_root,
            project_rapid_dir,
        )
        self.root = root
        self.rapid_dir = rapid_dir
        self.evidence_dir = evidence_dir
        self.run_registry = RunRegistry(self.root, self.rapid_dir)

    def _validate_run_id(self, run_id: str) -> str:
        try:
            return validate_run_id(run_id)
        except ExecutionError as exc:
            raise InvalidRunEvidenceError(
                str(exc),
                path=self.evidence_dir,
            ) from exc

    def _resolve_run_evidence_dir(self, run_id: str) -> Path:
        validated_run_id = self._validate_run_id(run_id)
        if self.evidence_dir.is_symlink():
            raise UnsafeEvidencePathError(
                f"Evidence registry root '{self.evidence_dir}' cannot be a symlink.",
                path=self.evidence_dir,
            )
        try:
            run_ev_dir = resolve_child_path(
                self.evidence_dir,
                validated_run_id,
                single_segment=True,
            )
            ensure_path_within_root(self.root, run_ev_dir)
        except ValueError as exc:
            raise UnsafeEvidencePathError(str(exc), path=run_id) from exc
        if run_ev_dir.is_symlink():
            raise UnsafeEvidencePathError(
                f"Run evidence directory '{run_ev_dir}' cannot be a symlink.",
                path=run_ev_dir,
            )
        return run_ev_dir

    def _resolve_records_dir(self, run_ev_dir: Path) -> Path:
        try:
            records_dir = resolve_child_path(
                run_ev_dir,
                RECORDS_DIRNAME,
                single_segment=True,
            )
            ensure_path_within_root(self.root, records_dir)
        except ValueError as exc:
            raise UnsafeEvidencePathError(str(exc), path=run_ev_dir) from exc
        if records_dir.is_symlink():
            raise UnsafeEvidencePathError(
                f"Evidence records directory '{records_dir}' cannot be a symlink.",
                path=records_dir,
            )
        return records_dir

    def _resolve_artifacts_dir(self, run_ev_dir: Path) -> Path:
        try:
            artifacts_dir = resolve_child_path(
                run_ev_dir,
                ARTIFACTS_DIRNAME,
                single_segment=True,
            )
            ensure_path_within_root(self.root, artifacts_dir)
        except ValueError as exc:
            raise UnsafeEvidencePathError(str(exc), path=run_ev_dir) from exc
        if artifacts_dir.is_symlink():
            raise UnsafeEvidencePathError(
                f"Evidence artifacts directory '{artifacts_dir}' cannot be a symlink.",
                path=artifacts_dir,
            )
        return artifacts_dir

    def _resolve_record_file(self, run_ev_dir: Path, evidence_id: str) -> Path:
        validated_id = validate_evidence_id(evidence_id)
        records_dir = self._resolve_records_dir(run_ev_dir)
        filename = format_evidence_file_name(validated_id)
        try:
            record_file = resolve_child_path(
                records_dir,
                filename,
                single_segment=True,
            )
            ensure_path_within_root(self.root, record_file)
        except ValueError as exc:
            raise UnsafeEvidencePathError(str(exc), path=records_dir) from exc
        if record_file.is_symlink():
            raise UnsafeEvidencePathError(
                f"Evidence record file '{record_file}' cannot be a symlink.",
                path=record_file,
            )
        return record_file

    def _resolve_evidence_artifact_dir(
        self,
        run_ev_dir: Path,
        evidence_id: str,
    ) -> Path:
        validated_id = validate_evidence_id(evidence_id)
        artifacts_dir = self._resolve_artifacts_dir(run_ev_dir)
        try:
            ev_art_dir = resolve_child_path(
                artifacts_dir,
                validated_id,
                single_segment=True,
            )
            ensure_path_within_root(self.root, ev_art_dir)
        except ValueError as exc:
            raise UnsafeEvidencePathError(str(exc), path=artifacts_dir) from exc
        if ev_art_dir.is_symlink():
            raise UnsafeEvidencePathError(
                f"Evidence artifact directory '{ev_art_dir}' cannot be a symlink.",
                path=ev_art_dir,
            )
        return ev_art_dir

    def _load_run_context(
        self,
        run_id: str,
    ) -> tuple[RunRecord, ExecutionContract]:
        validated_run_id = self._validate_run_id(run_id)
        record = self.run_registry.get(validated_run_id)
        contract = self.run_registry.get_contract(validated_run_id)
        return record, contract

    def _load_run_state_for_evidence(
        self,
        run_id: str,
        state_revision: int,
        *,
        current_state_revision: int,
    ) -> RunState:
        if (
            isinstance(state_revision, bool)
            or not isinstance(state_revision, int)
            or state_revision < 1
            or state_revision > current_state_revision
        ):
            raise EvidenceBindingMismatchError(
                f"Invalid state_revision '{state_revision}' for run '{run_id}' (current_state_revision={current_state_revision})."
            )
        try:
            return self.run_registry.get_state(run_id, revision=state_revision)
        except ExecutionError as exc:
            raise EvidenceBindingMismatchError(
                f"Cannot bind evidence to state s{state_revision} of run '{run_id}': {exc}"
            ) from exc

    def _verify_artifacts_for_record(
        self,
        run_ev_dir: Path,
        evidence: RunEvidence,
    ) -> None:
        ev_art_dir = self._resolve_evidence_artifact_dir(
            run_ev_dir,
            evidence.id,
        )
        expected_rel_paths: set[str] = set()

        for artifact in evidence.artifacts:
            validate_evidence_artifact_path(
                artifact.path,
                expected_run_id=evidence.run_id,
                expected_evidence_id=evidence.id,
            )
            prefix = f".rapid-os/evidence/{evidence.run_id}/artifacts/{evidence.id}/"
            rel_inside = artifact.path[len(prefix) :]
            expected_rel_paths.add(rel_inside)

            try:
                art_file = resolve_child_path(
                    ev_art_dir,
                    rel_inside,
                    single_segment=False,
                )
                ensure_path_within_root(self.root, art_file)
                ensure_path_within_root(ev_art_dir, art_file)
            except ValueError as exc:
                raise UnsafeEvidencePathError(
                    str(exc),
                    path=artifact.path,
                ) from exc

            # Check intermediate directories for symlinks
            if ev_art_dir.exists():
                curr = art_file.parent
                while curr != ev_art_dir and ev_art_dir in curr.parents:
                    if curr.is_symlink():
                        raise UnsafeEvidencePathError(
                            f"Artifact parent directory '{curr}' cannot be a symlink.",
                            path=curr,
                        )
                    curr = curr.parent

            if art_file.is_symlink():
                raise UnsafeEvidencePathError(
                    f"Evidence artifact '{art_file}' cannot be a symlink.",
                    path=art_file,
                )
            if not art_file.exists() or not art_file.is_file():
                raise EvidenceArtifactIntegrityError(
                    f"Evidence artifact '{artifact.path}' is missing on disk.",
                    path=art_file,
                )

            try:
                raw_bytes = art_file.read_bytes()
            except OSError as exc:
                raise EvidenceArtifactIntegrityError(
                    f"Evidence artifact '{artifact.path}' could not be read: {exc}",
                    path=art_file,
                ) from exc

            actual_size = len(raw_bytes)
            if actual_size != artifact.size_bytes:
                raise EvidenceArtifactIntegrityError(
                    f"Evidence artifact '{artifact.path}' size mismatch: expected {artifact.size_bytes} bytes, got {actual_size} bytes.",
                    path=art_file,
                )
            actual_sha256 = sha256_bytes(raw_bytes)
            if actual_sha256 != artifact.sha256:
                raise EvidenceArtifactIntegrityError(
                    f"Evidence artifact '{artifact.path}' SHA-256 digest mismatch: expected '{artifact.sha256}', got '{actual_sha256}'.",
                    path=art_file,
                )

        # Also check if ev_art_dir exists and contains unexpected symlinks or unlisted files
        if ev_art_dir.exists():
            if not ev_art_dir.is_dir():
                raise UnsafeEvidencePathError(
                    f"Evidence artifact path '{ev_art_dir}' is not a directory.",
                    path=ev_art_dir,
                )
            for item in sorted(ev_art_dir.rglob("*"), key=lambda p: str(p)):
                if item.is_symlink():
                    raise UnsafeEvidencePathError(
                        f"Symlink '{item}' is not allowed inside evidence artifacts.",
                        path=item,
                    )
                if item.is_file():
                    rel_pos = item.relative_to(ev_art_dir).as_posix()
                    if rel_pos not in expected_rel_paths:
                        raise EvidenceArtifactIntegrityError(
                            f"Untracked file '{rel_pos}' found in artifact directory for '{evidence.id}'.",
                            path=item,
                        )

    def _read_and_verify_record_file(
        self,
        run_ev_dir: Path,
        expected_run_id: str,
        expected_evidence_id: str,
        record_file: Path,
        *,
        record: RunRecord,
        contract: ExecutionContract,
        state_cache: dict[int, RunState],
    ) -> RunEvidence:
        if record_file.is_symlink():
            raise UnsafeEvidencePathError(
                f"Evidence record '{record_file}' cannot be a symlink.",
                path=record_file,
            )
        if not record_file.exists():
            raise EvidenceNotFoundError(
                f"Evidence '{expected_evidence_id}' was not found for run '{expected_run_id}'.",
                path=record_file,
            )
        if not record_file.is_file():
            raise UnsafeEvidencePathError(
                f"Evidence record '{record_file}' is not a regular file.",
                path=record_file,
            )

        try:
            raw = record_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnsafeEvidencePathError(
                f"Evidence record '{record_file}' could not be read as UTF-8: {exc}",
                path=record_file,
            ) from exc

        try:
            evidence = RunEvidence.from_json(raw, verify_digest=True)
        except EvidenceError as exc:
            raise type(exc)(str(exc), code=exc.code, path=record_file) from exc

        if evidence.id != expected_evidence_id:
            raise EvidenceSequenceGapError(
                f"RunEvidence.id '{evidence.id}' does not match filename '{record_file.name}'.",
                path=record_file,
            )
        if evidence.run_id != expected_run_id:
            raise EvidenceBindingMismatchError(
                f"RunEvidence.run_id '{evidence.run_id}' does not match run directory '{expected_run_id}'.",
                path=record_file,
            )

        if evidence.state_revision not in state_cache:
            try:
                state_cache[evidence.state_revision] = (
                    self._load_run_state_for_evidence(
                        expected_run_id,
                        evidence.state_revision,
                        current_state_revision=record.current_state_revision,
                    )
                )
            except EvidenceError as exc:
                raise type(exc)(
                    str(exc),
                    code=exc.code,
                    path=record_file,
                ) from exc

        target_state = state_cache[evidence.state_revision]
        try:
            verify_evidence_against_run(
                evidence,
                contract,
                target_state,
                current_state_revision=record.current_state_revision,
            )
        except EvidenceError as exc:
            raise type(exc)(str(exc), code=exc.code, path=record_file) from exc

        self._verify_artifacts_for_record(run_ev_dir, evidence)
        return evidence

    def _scan_run_evidence(
        self,
        run_id: str,
    ) -> tuple[
        RunRecord,
        ExecutionContract,
        Path,
        tuple[RunEvidence, ...],
        tuple[Path, ...],
    ]:
        """Inspect and verify all evidence records and artifact directories for `run_id`.

        Returns `(run_record, contract, run_ev_dir, ordered_records, orphan_artifact_dirs)`.
        """
        record, contract = self._load_run_context(run_id)
        if self.evidence_dir.exists():
            if self.evidence_dir.is_symlink() or not self.evidence_dir.is_dir():
                raise UnsafeEvidencePathError(
                    f"Evidence registry root '{self.evidence_dir}' is not a valid directory.",
                    path=self.evidence_dir,
                )

        run_ev_dir = self._resolve_run_evidence_dir(record.id)
        if not run_ev_dir.exists():
            return record, contract, run_ev_dir, (), ()
        if not run_ev_dir.is_dir():
            raise UnsafeEvidencePathError(
                f"Run evidence path '{run_ev_dir}' is not a directory.",
                path=run_ev_dir,
            )

        for child in sorted(run_ev_dir.iterdir(), key=lambda p: p.name):
            if child.is_symlink():
                raise UnsafeEvidencePathError(
                    f"Symlink '{child}' is not allowed in run evidence directory.",
                    path=child,
                )
            if child.name not in {RECORDS_DIRNAME, ARTIFACTS_DIRNAME}:
                raise InvalidRunEvidenceError(
                    f"Unexpected entry '{child.name}' in run evidence directory '{run_ev_dir}'.",
                    path=child,
                )

        records_dir = self._resolve_records_dir(run_ev_dir)
        artifacts_dir = self._resolve_artifacts_dir(run_ev_dir)

        record_files_by_ordinal: dict[int, tuple[str, Path]] = {}
        if records_dir.exists():
            if not records_dir.is_dir():
                raise UnsafeEvidencePathError(
                    f"Evidence records path '{records_dir}' is not a directory.",
                    path=records_dir,
                )
            for entry in sorted(records_dir.iterdir(), key=lambda p: p.name):
                if entry.is_symlink():
                    raise UnsafeEvidencePathError(
                        f"Evidence record '{entry}' cannot be a symlink.",
                        path=entry,
                    )
                if not entry.is_file():
                    raise InvalidRunEvidenceError(
                        f"Unexpected non-file entry '{entry.name}' in evidence records directory.",
                        path=entry,
                    )
                if not is_canonical_evidence_file_name(entry.name):
                    raise InvalidEvidenceIdError(
                        f"Non-canonical evidence record filename '{entry.name}': expected E001.json..E999.json.",
                        path=entry,
                    )
                ev_id = entry.name[:-5]
                ordinal = parse_evidence_ordinal(ev_id)
                if ordinal in record_files_by_ordinal:
                    raise EvidenceSequenceGapError(
                        f"Duplicate evidence ordinal for '{entry.name}'.",
                        path=entry,
                    )
                record_files_by_ordinal[ordinal] = (ev_id, entry)

        artifact_dirs_by_ordinal: dict[int, tuple[str, Path]] = {}
        if artifacts_dir.exists():
            if not artifacts_dir.is_dir():
                raise UnsafeEvidencePathError(
                    f"Evidence artifacts path '{artifacts_dir}' is not a directory.",
                    path=artifacts_dir,
                )
            for entry in sorted(artifacts_dir.iterdir(), key=lambda p: p.name):
                if entry.is_symlink():
                    raise UnsafeEvidencePathError(
                        f"Evidence artifact directory '{entry}' cannot be a symlink.",
                        path=entry,
                    )
                if not entry.is_dir():
                    raise UnsafeEvidencePathError(
                        f"Unexpected non-directory entry '{entry.name}' in evidence artifacts directory.",
                        path=entry,
                    )
                try:
                    ev_id = validate_evidence_id(
                        entry.name,
                        "evidence artifact directory",
                    )
                except InvalidEvidenceIdError as exc:
                    raise InvalidEvidenceIdError(
                        str(exc),
                        path=entry,
                    ) from exc
                ordinal = parse_evidence_ordinal(ev_id)
                artifact_dirs_by_ordinal[ordinal] = (ev_id, entry)

        # Sequence continuity check across records and artifact directories:
        # Every record 1..max_record_ordinal must exist (an artifact directory never excuses a missing historical record).
        # Only a single trailing artifact directory at max_record_ordinal + 1 is allowed as a crash orphan (RAPID1209 WARNING).
        max_record_ordinal = max(record_files_by_ordinal.keys(), default=0)
        max_seen_ordinal = max(
            list(record_files_by_ordinal.keys())
            + list(artifact_dirs_by_ordinal.keys()),
            default=0,
        )
        for expected_ord in range(1, max_seen_ordinal + 1):
            if expected_ord not in record_files_by_ordinal:
                is_trailing_crash_orphan = (
                    expected_ord == max_seen_ordinal
                    and expected_ord == max_record_ordinal + 1
                    and expected_ord in artifact_dirs_by_ordinal
                )
                if not is_trailing_crash_orphan:
                    missing_id = format_evidence_id(expected_ord)
                    raise EvidenceSequenceGapError(
                        f"Evidence sequence gap detected for run '{record.id}': missing record '{missing_id}.json'.",
                        path=records_dir / f"{missing_id}.json",
                    )

        state_cache: dict[int, RunState] = {}
        verified_records: list[RunEvidence] = []
        for ordinal in sorted(record_files_by_ordinal.keys()):
            ev_id, rec_file = record_files_by_ordinal[ordinal]
            verified_records.append(
                self._read_and_verify_record_file(
                    run_ev_dir,
                    record.id,
                    ev_id,
                    rec_file,
                    record=record,
                    contract=contract,
                    state_cache=state_cache,
                )
            )

        orphan_dirs: list[Path] = []
        for ordinal in sorted(artifact_dirs_by_ordinal.keys()):
            if ordinal not in record_files_by_ordinal:
                _, orphan_path = artifact_dirs_by_ordinal[ordinal]
                for item in sorted(orphan_path.rglob("*"), key=lambda p: str(p)):
                    if item.is_symlink():
                        raise UnsafeEvidencePathError(
                            f"Symlink '{item}' is not allowed inside orphan evidence artifacts.",
                            path=item,
                        )
                orphan_dirs.append(orphan_path)

        return (
            record,
            contract,
            run_ev_dir,
            tuple(verified_records),
            tuple(orphan_dirs),
        )

    def _next_evidence_id(self, run_id: str) -> str:
        """Compute the next sequential evidence ID (`E001`, ...), failing safely if a trailing crash orphan exists."""
        _, _, _, records, orphan_dirs = self._scan_run_evidence(run_id)
        if orphan_dirs:
            orphan_path = orphan_dirs[0]
            raise EvidenceOverwriteError(
                f"Cannot add new evidence while trailing orphan artifact directory '{orphan_path.name}' exists without a committed record ({orphan_path}). "
                "The previous evidence write may have been interrupted. "
                "Resolve or inspect the orphan directory before adding new evidence.",
                path=orphan_path,
            )

        max_ordinal = max(
            (parse_evidence_ordinal(rec.id) for rec in records),
            default=0,
        )
        return format_evidence_id(max_ordinal + 1)

    def list(self, run_id: str) -> tuple[RunEvidence, ...]:
        """List all verified `RunEvidence` records for `run_id` in `E001..E<N>` order."""
        _, _, _, records, _ = self._scan_run_evidence(run_id)
        return records

    def verify(self, run_id: str) -> tuple[RunEvidence, ...]:
        """Verify all evidence records, bindings, sequence continuity, and artifact digests for `run_id`."""
        _, _, _, records, _ = self._scan_run_evidence(run_id)
        return records

    def orphan_artifact_dirs(self, run_id: str) -> tuple[Path, ...]:
        """Return any orphan artifact directories (`artifacts/E00N` without `records/E00N.json`) for `run_id`."""
        _, _, _, _, orphans = self._scan_run_evidence(run_id)
        return orphans

    def get(self, run_id: str, evidence_id: str) -> RunEvidence:
        """Load and verify a single `RunEvidence` record and its artifacts by `evidence_id`."""
        validated_run_id = self._validate_run_id(run_id)
        validated_ev_id = validate_evidence_id(evidence_id)
        record, contract = self._load_run_context(validated_run_id)
        run_ev_dir = self._resolve_run_evidence_dir(record.id)
        record_file = self._resolve_record_file(run_ev_dir, validated_ev_id)
        if not record_file.exists():
            raise EvidenceNotFoundError(
                f"Evidence '{validated_ev_id}' was not found for run '{record.id}'.",
                path=record_file,
            )
        # Verify full run evidence ledger so sequence gaps or tampering are never ignored
        records = self.list(record.id)
        for item in records:
            if item.id == validated_ev_id:
                return item
        raise EvidenceNotFoundError(
            f"Evidence '{validated_ev_id}' was not found for run '{record.id}'.",
            path=record_file,
        )

    def evidence_set_digest(self, run_id: str) -> str:
        """Compute canonical SHA-256 digest of the verified evidence set for `run_id`."""
        validated_run_id = self._validate_run_id(run_id)
        records = self.list(validated_run_id)
        return compute_evidence_set_digest(validated_run_id, records)

    def validate(self, run_id: str | None = None):
        """Return a `ValidationReport` for the evidence registry (optionally scoped to `run_id`)."""
        from rapid_os.domain.validation import validate_evidence_registry

        return validate_evidence_registry(
            self.rapid_dir,
            self.root,
            run_id=run_id,
        )

    def _parse_authoring_input(
        self,
        authoring_input: Mapping[str, object] | str | Path,
        *,
        base_dir: Path | None = None,
    ) -> tuple[Mapping[str, object], Path]:
        resolved_base = base_dir if base_dir is not None else self.root
        if isinstance(authoring_input, Path):
            input_path = authoring_input
            if not input_path.is_absolute():
                input_path = self.root / input_path
            if input_path.is_symlink():
                raise UnsafeEvidencePathError(
                    f"Evidence authoring file '{input_path}' cannot be a symlink.",
                    path=input_path,
                )
            if not input_path.exists() or not input_path.is_file():
                raise InvalidRunEvidenceError(
                    f"Evidence authoring file '{input_path}' does not exist.",
                    path=input_path,
                )
            try:
                raw_text = input_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise UnsafeEvidencePathError(
                    f"Evidence authoring file '{input_path}' could not be read: {exc}",
                    path=input_path,
                ) from exc
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise InvalidRunEvidenceError(
                    f"Invalid evidence authoring JSON in '{input_path}': {exc.msg}",
                    path=input_path,
                ) from exc
            if not isinstance(parsed, Mapping):
                raise InvalidRunEvidenceError(
                    "Evidence authoring JSON root must be an object.",
                    path=input_path,
                )
            if base_dir is None:
                resolved_base = input_path.parent
            return parsed, resolved_base

        if isinstance(authoring_input, str):
            try:
                parsed = json.loads(authoring_input)
            except json.JSONDecodeError as exc:
                raise InvalidRunEvidenceError(
                    f"Invalid evidence authoring JSON: {exc.msg}"
                ) from exc
            if not isinstance(parsed, Mapping):
                raise InvalidRunEvidenceError(
                    "Evidence authoring JSON root must be an object."
                )
            return parsed, resolved_base

        if isinstance(authoring_input, Mapping):
            return authoring_input, resolved_base

        raise InvalidRunEvidenceError(
            "Evidence authoring input must be a mapping, JSON string, or file Path."
        )

    def _resolve_source_artifact_bytes(
        self,
        raw_entry: object,
        *,
        base_dir: Path,
    ) -> tuple[str, bytes]:
        """Validate relative artifact path and read source bytes safely without symlink escape."""
        rel_posix = validate_relative_posix_path(
            raw_entry,
            "authoring artifact path",
            error_cls=UnsafeEvidencePathError,
        )

        # Candidate 1: relative to base_dir; Candidate 2: relative to project root
        candidates: list[tuple[Path, Path]] = []
        for root_candidate in (base_dir, self.root):
            try:
                candidate = resolve_child_path(
                    root_candidate,
                    rel_posix,
                    single_segment=False,
                )
                ensure_path_within_root(root_candidate, candidate)
                candidates.append((root_candidate, candidate))
            except ValueError as exc:
                raise UnsafeEvidencePathError(
                    str(exc),
                    path=rel_posix,
                ) from exc

        selected_root: Path | None = None
        selected_path: Path | None = None
        for root_cand, path_cand in candidates:
            if path_cand.is_symlink() or path_cand.exists():
                selected_root = root_cand
                selected_path = path_cand
                break

        if selected_path is None or selected_root is None:
            raise EvidenceArtifactIntegrityError(
                f"Source artifact '{rel_posix}' does not exist.",
                path=base_dir / rel_posix,
            )

        # Verify no intermediate directory is a symlink
        curr = selected_path.parent
        while curr != selected_root and selected_root in curr.parents:
            if curr.is_symlink():
                raise UnsafeEvidencePathError(
                    f"Source artifact parent directory '{curr}' cannot be a symlink.",
                    path=curr,
                )
            curr = curr.parent

        if selected_path.is_symlink():
            raise UnsafeEvidencePathError(
                f"Source artifact '{selected_path}' cannot be a symlink.",
                path=selected_path,
            )
        if not selected_path.is_file():
            raise EvidenceArtifactIntegrityError(
                f"Source artifact '{selected_path}' is not a regular file.",
                path=selected_path,
            )
        try:
            data = selected_path.read_bytes()
        except OSError as exc:
            raise EvidenceArtifactIntegrityError(
                f"Source artifact '{selected_path}' could not be read: {exc}",
                path=selected_path,
            ) from exc

        return rel_posix, data

    def _write_artifact_file(
        self,
        run_id: str,
        evidence_id: str,
        rel_posix: str,
        content_bytes: bytes,
    ) -> EvidenceArtifact:
        run_ev_dir = self._resolve_run_evidence_dir(run_id)
        ev_art_dir = self._resolve_evidence_artifact_dir(run_ev_dir, evidence_id)
        rel_validated = validate_relative_posix_path(
            rel_posix,
            "artifact relative path",
            error_cls=UnsafeEvidencePathError,
        )
        try:
            dest_file = resolve_child_path(
                ev_art_dir,
                rel_validated,
                single_segment=False,
            )
            ensure_path_within_root(self.root, dest_file)
            ensure_path_within_root(ev_art_dir, dest_file)
        except ValueError as exc:
            raise UnsafeEvidencePathError(str(exc), path=rel_posix) from exc

        if dest_file.is_symlink():
            raise UnsafeEvidencePathError(
                f"Evidence artifact destination '{dest_file}' cannot be a symlink.",
                path=dest_file,
            )
        if dest_file.exists():
            raise EvidenceOverwriteError(
                f"Cannot overwrite existing evidence artifact '{dest_file}'.",
                path=dest_file,
            )

        try:
            safe_write_bytes(
                dest_file,
                content_bytes,
                backup=False,
                create_parents=True,
                allow_overwrite=False,
            )
        except FileExistsError as exc:
            raise EvidenceOverwriteError(
                f"Cannot overwrite existing evidence artifact '{dest_file}'.",
                path=dest_file,
            ) from exc
        except ValueError as exc:
            raise UnsafeEvidencePathError(str(exc), path=dest_file) from exc

        canonical_rel_path = (
            f".rapid-os/evidence/{run_id}/artifacts/{evidence_id}/{rel_validated}"
        )
        return EvidenceArtifact(
            path=canonical_rel_path,
            sha256=sha256_bytes(content_bytes),
            size_bytes=len(content_bytes),
        )

    def _write_record_file(
        self,
        run_id: str,
        evidence: RunEvidence,
    ) -> Path:
        run_ev_dir = self._resolve_run_evidence_dir(run_id)
        record_file = self._resolve_record_file(run_ev_dir, evidence.id)
        if record_file.exists():
            raise EvidenceOverwriteError(
                f"Cannot overwrite existing evidence record '{record_file}'.",
                path=record_file,
            )
        try:
            safe_write_text(
                record_file,
                evidence.to_json(indent=2) + "\n",
                backup=False,
                create_parents=True,
                allow_overwrite=False,
            )
        except FileExistsError as exc:
            raise EvidenceOverwriteError(
                f"Cannot overwrite existing evidence record '{record_file}'.",
                path=record_file,
            ) from exc
        except ValueError as exc:
            raise UnsafeEvidencePathError(str(exc), path=record_file) from exc
        return record_file

    def add(
        self,
        run_id: str,
        authoring_input: Mapping[str, object] | str | Path,
        *,
        base_dir: Path | None = None,
    ) -> RunEvidence:
        """Ingest a new append-only `RunEvidence` record and copy its artifacts into the registry."""
        payload_map, resolved_base = self._parse_authoring_input(
            authoring_input,
            base_dir=base_dir,
        )

        if "id" in payload_map:
            raise InvalidEvidenceIdError(
                "Authoring input cannot specify 'id'; evidence IDs are allocated sequentially by Rapid OS."
            )
        unknown = set(payload_map.keys()) - ALLOWED_AUTHORING_KEYS
        if unknown:
            raise InvalidRunEvidenceError(
                f"Unexpected fields in evidence authoring input: {sorted(unknown)}."
            )
        missing = REQUIRED_AUTHORING_KEYS - set(payload_map.keys())
        if missing:
            raise InvalidRunEvidenceError(
                f"Missing required fields in evidence authoring input: {sorted(missing)}."
            )

        # 1. Validate Run, Contract, and target RunState
        record, contract, run_ev_dir, existing_records, orphan_dirs = (
            self._scan_run_evidence(run_id)
        )
        if orphan_dirs:
            orphan_path = orphan_dirs[0]
            raise EvidenceOverwriteError(
                f"Cannot add new evidence for run '{record.id}' while trailing orphan artifact directory '{orphan_path}' exists without a committed record.",
                path=orphan_path,
            )
        raw_state_rev = payload_map.get(
            "state_revision",
            record.current_state_revision,
        )
        target_state = self._load_run_state_for_evidence(
            record.id,
            raw_state_rev,  # type: ignore[arg-type]
            current_state_revision=record.current_state_revision,
        )

        # 2. Allocate next sequential evidence ID
        max_ordinal = max(
            (parse_evidence_ordinal(rec.id) for rec in existing_records),
            default=0,
        )
        evidence_id = format_evidence_id(max_ordinal + 1)

        # 3. Validate declarative fields and pre-read source artifacts before mutating disk
        raw_artifacts = payload_map.get("artifacts", ())
        if isinstance(raw_artifacts, (str, bytes)) or not isinstance(
            raw_artifacts, Iterable
        ):
            raise InvalidRunEvidenceError(
                "Authoring field 'artifacts' must be a list of relative file paths."
            )

        prepared_artifacts: list[tuple[str, bytes]] = []
        seen_rel_paths: set[str] = set()
        for raw_art in raw_artifacts:
            rel_posix, raw_bytes = self._resolve_source_artifact_bytes(
                raw_art,
                base_dir=resolved_base,
            )
            if rel_posix in seen_rel_paths:
                raise EvidenceOverwriteError(
                    f"Duplicate artifact path '{rel_posix}' in evidence authoring input."
                )
            seen_rel_paths.add(rel_posix)
            prepared_artifacts.append((rel_posix, raw_bytes))

        provisional_artifacts = tuple(
            EvidenceArtifact(
                path=f".rapid-os/evidence/{record.id}/artifacts/{evidence_id}/{rel_pos}",
                sha256=sha256_bytes(data_bytes),
                size_bytes=len(data_bytes),
            )
            for rel_pos, data_bytes in prepared_artifacts
        )

        provisional_evidence = RunEvidence(
            schema_version=RUN_EVIDENCE_SCHEMA_VERSION,
            id=evidence_id,
            run_id=record.id,
            contract_digest=contract.contract_digest,
            state_revision=target_state.revision,
            state_digest=target_state.content_digest,
            kind=EvidenceKind.coerce(payload_map["kind"]),
            producer=payload_map["producer"],  # type: ignore[arg-type]
            summary=payload_map["summary"],  # type: ignore[arg-type]
            task_ids=payload_map.get("task_ids", ()),  # type: ignore[arg-type]
            gate_ids=payload_map.get("gate_ids", ()),  # type: ignore[arg-type]
            capability_ids=payload_map.get("capability_ids", ()),  # type: ignore[arg-type]
            payload=payload_map["payload"],  # type: ignore[arg-type]
            artifacts=provisional_artifacts,
        )
        verify_evidence_against_run(
            provisional_evidence,
            contract,
            target_state,
            current_state_revision=record.current_state_revision,
        )

        # 4. Copy artifact bytes into `.rapid-os/evidence/<run-id>/artifacts/<evidence-id>/`
        ev_art_dir = self._resolve_evidence_artifact_dir(run_ev_dir, evidence_id)
        if ev_art_dir.exists():
            raise EvidenceOverwriteError(
                f"Evidence artifact directory '{ev_art_dir}' already exists.",
                path=ev_art_dir,
            )

        written_artifacts: list[EvidenceArtifact] = []
        if prepared_artifacts:
            ev_art_dir.mkdir(parents=True, exist_ok=False)
            for rel_pos, data_bytes in prepared_artifacts:
                written_artifacts.append(
                    self._write_artifact_file(
                        record.id,
                        evidence_id,
                        rel_pos,
                        data_bytes,
                    )
                )

        # 5. Build final RunEvidence and write `records/E00N.json` LAST (commit point)
        final_evidence = RunEvidence(
            schema_version=RUN_EVIDENCE_SCHEMA_VERSION,
            id=evidence_id,
            run_id=record.id,
            contract_digest=contract.contract_digest,
            state_revision=target_state.revision,
            state_digest=target_state.content_digest,
            kind=provisional_evidence.kind,
            producer=provisional_evidence.producer,
            summary=provisional_evidence.summary,
            task_ids=provisional_evidence.task_ids,
            gate_ids=provisional_evidence.gate_ids,
            capability_ids=provisional_evidence.capability_ids,
            payload=provisional_evidence.payload,
            artifacts=tuple(written_artifacts),
        )
        verify_evidence_against_run(
            final_evidence,
            contract,
            target_state,
            current_state_revision=record.current_state_revision,
        )
        self._write_record_file(record.id, final_evidence)
        return final_evidence

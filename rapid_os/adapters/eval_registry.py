from pathlib import Path
from typing import Iterable

from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.core.filesystem import (
    ensure_path_within_root,
    resolve_child_path,
    safe_write_text,
)
from rapid_os.domain.capabilities import CapabilityRequirement
from rapid_os.domain.evals import (
    BEHAVIORAL_RULESET_VERSION,
    DEFAULT_BEHAVIORAL_RULESET_DIGEST,
    BehavioralEvaluator,
    EvaluationBindingMismatchError,
    EvaluationError,
    EvaluationOverwriteError,
    EvaluationReport,
    EvaluationReportNotFoundError,
    InvalidEvaluationReportError,
    UnsafeEvaluationPathError,
    format_eval_report_file_name,
    is_canonical_eval_report_file_name,
    parse_eval_report_revision,
)
from rapid_os.domain.evidence import (
    EvidenceError,
    RunEvidence,
    compute_evidence_set_digest,
)
from rapid_os.domain.execution import (
    ExecutionContract,
    ExecutionError,
    RunRecord,
    RunState,
    validate_run_id,
)


EVALS_DIRNAME = "evals"
REPORTS_DIRNAME = "reports"


def resolve_evals_root_dir(
    project_root: Path,
    project_rapid_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Return `(root, rapid_dir, evals_dir)` with containment verification."""
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
        evals_dir = resolve_child_path(
            contained_rapid,
            EVALS_DIRNAME,
            single_segment=True,
        )
        ensure_path_within_root(root, evals_dir)
    except ValueError as exc:
        raise UnsafeEvaluationPathError(
            str(exc),
            path=rapid_dir / EVALS_DIRNAME,
        ) from exc

    return root, contained_rapid, evals_dir


class EvalRegistry:
    """Append-only filesystem Evaluation Report Registry under `.rapid-os/evals/<run-id>/reports/`."""

    def __init__(
        self,
        project_root: Path = Path("."),
        project_rapid_dir: Path | None = None,
        *,
        evaluator: BehavioralEvaluator | None = None,
    ):
        root, rapid_dir, evals_dir = resolve_evals_root_dir(
            project_root,
            project_rapid_dir,
        )
        self.root = root
        self.rapid_dir = rapid_dir
        self.evals_dir = evals_dir
        self.run_registry = RunRegistry(self.root, self.rapid_dir)
        self.evidence_registry = EvidenceRegistry(self.root, self.rapid_dir)
        self.evaluator = evaluator or BehavioralEvaluator()

    def _validate_run_id(self, run_id: str) -> str:
        try:
            return validate_run_id(run_id)
        except ExecutionError as exc:
            raise InvalidEvaluationReportError(
                str(exc),
                path=self.evals_dir,
            ) from exc

    def _resolve_run_evals_dir(self, run_id: str) -> Path:
        validated_run_id = self._validate_run_id(run_id)
        if self.evals_dir.is_symlink():
            raise UnsafeEvaluationPathError(
                f"Eval registry root '{self.evals_dir}' cannot be a symlink.",
                path=self.evals_dir,
            )
        try:
            run_evals_dir = resolve_child_path(
                self.evals_dir,
                validated_run_id,
                single_segment=True,
            )
            ensure_path_within_root(self.root, run_evals_dir)
        except ValueError as exc:
            raise UnsafeEvaluationPathError(str(exc), path=run_id) from exc
        if run_evals_dir.is_symlink():
            raise UnsafeEvaluationPathError(
                f"Run evals directory '{run_evals_dir}' cannot be a symlink.",
                path=run_evals_dir,
            )
        return run_evals_dir

    def _resolve_reports_dir(self, run_evals_dir: Path) -> Path:
        try:
            reports_dir = resolve_child_path(
                run_evals_dir,
                REPORTS_DIRNAME,
                single_segment=True,
            )
            ensure_path_within_root(self.root, reports_dir)
        except ValueError as exc:
            raise UnsafeEvaluationPathError(
                str(exc),
                path=run_evals_dir,
            ) from exc
        if reports_dir.is_symlink():
            raise UnsafeEvaluationPathError(
                f"Eval reports directory '{reports_dir}' cannot be a symlink.",
                path=reports_dir,
            )
        return reports_dir

    def _resolve_report_file(self, run_evals_dir: Path, revision: int) -> Path:
        reports_dir = self._resolve_reports_dir(run_evals_dir)
        filename = format_eval_report_file_name(revision)
        try:
            report_file = resolve_child_path(
                reports_dir,
                filename,
                single_segment=True,
            )
            ensure_path_within_root(self.root, report_file)
        except ValueError as exc:
            raise UnsafeEvaluationPathError(
                str(exc),
                path=reports_dir,
            ) from exc
        if report_file.is_symlink():
            raise UnsafeEvaluationPathError(
                f"Evaluation report file '{report_file}' cannot be a symlink.",
                path=report_file,
            )
        return report_file

    def _verify_report_bindings(
        self,
        report: EvaluationReport,
        *,
        record: RunRecord,
        contract: ExecutionContract,
        evidence_records: tuple[RunEvidence, ...],
        state_cache: dict[int, RunState],
        report_path: Path | None = None,
    ) -> None:
        if report.run_id != record.id:
            raise EvaluationBindingMismatchError(
                f"EvaluationReport.run_id '{report.run_id}' does not match run '{record.id}'.",
                path=report_path,
            )
        if report.contract_digest != contract.contract_digest:
            raise EvaluationBindingMismatchError(
                f"EvaluationReport.contract_digest '{report.contract_digest}' does not match ExecutionContract digest '{contract.contract_digest}'.",
                path=report_path,
            )
        if report.state_revision > record.current_state_revision:
            raise EvaluationBindingMismatchError(
                f"EvaluationReport.state_revision s{report.state_revision} exceeds current_state_revision s{record.current_state_revision}.",
                path=report_path,
            )
        if report.state_revision not in state_cache:
            try:
                state_cache[report.state_revision] = self.run_registry.get_state(
                    record.id,
                    revision=report.state_revision,
                )
            except ExecutionError as exc:
                raise EvaluationBindingMismatchError(
                    f"Cannot bind EvaluationReport to RunState s{report.state_revision}: {exc}",
                    path=report_path,
                ) from exc

        bound_state = state_cache[report.state_revision]
        if report.state_digest != bound_state.content_digest:
            raise EvaluationBindingMismatchError(
                f"EvaluationReport.state_digest '{report.state_digest}' does not match persisted RunState s{bound_state.revision} digest '{bound_state.content_digest}'.",
                path=report_path,
            )

        if (
            report.ruleset_version == BEHAVIORAL_RULESET_VERSION
            and report.ruleset_digest != DEFAULT_BEHAVIORAL_RULESET_DIGEST
            and report.ruleset_digest != self.evaluator.ruleset_digest
        ):
            raise EvaluationBindingMismatchError(
                f"EvaluationReport.ruleset_digest '{report.ruleset_digest}' does not match ruleset v{BEHAVIORAL_RULESET_VERSION} digest.",
                path=report_path,
            )

        # Match `report.evidence_set_digest` against a prefix `evidence_records[:k]` of the append-only evidence ledger
        matched_prefix: tuple[RunEvidence, ...] | None = None
        for k in range(len(evidence_records) + 1):
            candidate_prefix = evidence_records[:k]
            candidate_digest = compute_evidence_set_digest(
                record.id,
                candidate_prefix,
            )
            if candidate_digest == report.evidence_set_digest:
                matched_prefix = candidate_prefix
                break

        if matched_prefix is None:
            raise EvaluationBindingMismatchError(
                f"EvaluationReport.evidence_set_digest '{report.evidence_set_digest}' does not match any historical evidence set for run '{record.id}'.",
                path=report_path,
            )

        valid_ev_ids = {ev.id for ev in matched_prefix}
        for ev in matched_prefix:
            if ev.state_revision > report.state_revision:
                raise EvaluationBindingMismatchError(
                    f"EvaluationReport at state s{report.state_revision} includes evidence '{ev.id}' bound to later state s{ev.state_revision}.",
                    path=report_path,
                )
        for assertion in report.assertions:
            for ref_ev_id in assertion.evidence_ids:
                if ref_ev_id not in valid_ev_ids:
                    raise EvaluationBindingMismatchError(
                        f"EvalAssertion '{assertion.id}' references evidence '{ref_ev_id}' not present in the evaluated evidence set.",
                        path=report_path,
                    )

        # Mandatory semantic replay: reconstruct evaluation from contract + historical RunState +
        # exact historical evidence set + behavioral ruleset + extra capability requirements
        try:
            replayed = self.evaluator.evaluate(
                contract,
                bound_state,
                matched_prefix,
                extra_capability_requirements=report.extra_capability_ids,
            )
        except (EvaluationError, EvidenceError) as exc:
            raise EvaluationBindingMismatchError(
                f"Semantic replay failed for EvaluationReport of run '{record.id}': {exc}",
                path=report_path,
            ) from exc

        if (
            report.assertions != replayed.assertions
            or report.verdict != replayed.verdict
            or report.ruleset_digest != replayed.ruleset_digest
            or report.evidence_set_digest != replayed.evidence_set_digest
            or report.extra_capability_ids != replayed.extra_capability_ids
            or report.report_digest != replayed.report_digest
        ):
            raise EvaluationBindingMismatchError(
                f"EvaluationReport for run '{record.id}' at state s{report.state_revision} does not match deterministic semantic replay.",
                path=report_path,
            )

    def _scan_run_reports(
        self,
        run_id: str,
    ) -> tuple[
        RunRecord,
        ExecutionContract,
        tuple[RunEvidence, ...],
        Path,
        tuple[tuple[int, Path, EvaluationReport], ...],
    ]:
        validated_run_id = self._validate_run_id(run_id)
        record = self.run_registry.get(validated_run_id)
        contract = self.run_registry.get_contract(validated_run_id)
        evidence_records = self.evidence_registry.list(validated_run_id)

        if self.evals_dir.exists():
            if self.evals_dir.is_symlink() or not self.evals_dir.is_dir():
                raise UnsafeEvaluationPathError(
                    f"Eval registry root '{self.evals_dir}' is not a valid directory.",
                    path=self.evals_dir,
                )

        run_evals_dir = self._resolve_run_evals_dir(record.id)
        if not run_evals_dir.exists():
            return record, contract, evidence_records, run_evals_dir, ()
        if not run_evals_dir.is_dir():
            raise UnsafeEvaluationPathError(
                f"Run evals path '{run_evals_dir}' is not a directory.",
                path=run_evals_dir,
            )

        for child in sorted(run_evals_dir.iterdir(), key=lambda p: p.name):
            if child.is_symlink():
                raise UnsafeEvaluationPathError(
                    f"Symlink '{child}' is not allowed in run evals directory.",
                    path=child,
                )
            if child.name != REPORTS_DIRNAME:
                raise InvalidEvaluationReportError(
                    f"Unexpected entry '{child.name}' in run evals directory '{run_evals_dir}'.",
                    path=child,
                )

        reports_dir = self._resolve_reports_dir(run_evals_dir)
        if not reports_dir.exists():
            return record, contract, evidence_records, run_evals_dir, ()
        if not reports_dir.is_dir():
            raise UnsafeEvaluationPathError(
                f"Eval reports path '{reports_dir}' is not a directory.",
                path=reports_dir,
            )

        report_files_by_rev: dict[int, Path] = {}
        for entry in sorted(reports_dir.iterdir(), key=lambda p: p.name):
            if entry.is_symlink():
                raise UnsafeEvaluationPathError(
                    f"Evaluation report '{entry}' cannot be a symlink.",
                    path=entry,
                )
            if not entry.is_file():
                raise InvalidEvaluationReportError(
                    f"Unexpected non-file entry '{entry.name}' in eval reports directory.",
                    path=entry,
                )
            if not is_canonical_eval_report_file_name(entry.name):
                raise InvalidEvaluationReportError(
                    f"Non-canonical evaluation report filename '{entry.name}': expected 0001.json..9999.json.",
                    path=entry,
                )
            rev_num = parse_eval_report_revision(entry.name)
            report_files_by_rev[rev_num] = entry

        if report_files_by_rev:
            max_rev = max(report_files_by_rev.keys())
            for expected_rev in range(1, max_rev + 1):
                if expected_rev not in report_files_by_rev:
                    missing_name = format_eval_report_file_name(expected_rev)
                    raise InvalidEvaluationReportError(
                        f"Evaluation report sequence gap detected for run '{record.id}': missing '{missing_name}'.",
                        path=reports_dir / missing_name,
                    )

        state_cache: dict[int, RunState] = {}
        verified_entries: list[tuple[int, Path, EvaluationReport]] = []
        for rev_num in sorted(report_files_by_rev.keys()):
            rep_file = report_files_by_rev[rev_num]
            try:
                raw_text = rep_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise UnsafeEvaluationPathError(
                    f"Evaluation report '{rep_file}' could not be read as UTF-8: {exc}",
                    path=rep_file,
                ) from exc
            try:
                rep_obj = EvaluationReport.from_json(raw_text, verify_digest=True)
            except EvaluationError as exc:
                raise type(exc)(str(exc), code=exc.code, path=rep_file) from exc

            self._verify_report_bindings(
                rep_obj,
                record=record,
                contract=contract,
                evidence_records=evidence_records,
                state_cache=state_cache,
                report_path=rep_file,
            )
            verified_entries.append((rev_num, rep_file, rep_obj))

        return (
            record,
            contract,
            evidence_records,
            run_evals_dir,
            tuple(verified_entries),
        )

    def is_report_stale(
        self,
        report: EvaluationReport,
        *,
        current_state: RunState | None = None,
        current_evidence_set_digest: str | None = None,
    ) -> bool:
        """Return True if `report` is stale relative to the run's current `RunState`, `evidence_set_digest`, or active ruleset."""
        resolved_state = current_state or self.run_registry.get_state(
            report.run_id
        )
        resolved_ev_digest = (
            current_evidence_set_digest
            or self.evidence_registry.evidence_set_digest(report.run_id)
        )
        return (
            report.state_digest != resolved_state.content_digest
            or report.evidence_set_digest != resolved_ev_digest
            or report.ruleset_digest != self.evaluator.ruleset_digest
        )

    def list_report_entries(
        self,
        run_id: str,
    ) -> tuple[tuple[int, Path, EvaluationReport, bool], ...]:
        """Return `(revision, path, report, is_stale)` for all persisted reports of `run_id` in chronological order."""
        record, _, evidence_records, _, entries = self._scan_run_reports(run_id)
        if not entries:
            return ()
        current_state = self.run_registry.get_state(
            record.id,
            revision=record.current_state_revision,
        )
        current_ev_digest = compute_evidence_set_digest(
            record.id,
            evidence_records,
        )
        return tuple(
            (
                rev_num,
                rep_path,
                rep_obj,
                self.is_report_stale(
                    rep_obj,
                    current_state=current_state,
                    current_evidence_set_digest=current_ev_digest,
                ),
            )
            for rev_num, rep_path, rep_obj in entries
        )

    def list_reports(self, run_id: str) -> tuple[EvaluationReport, ...]:
        """List all persisted `EvaluationReport` snapshots for `run_id` in `0001..000N` order."""
        _, _, _, _, entries = self._scan_run_reports(run_id)
        return tuple(rep_obj for _, _, rep_obj in entries)

    def get_report(
        self,
        run_id: str,
        revision: int | None = None,
    ) -> EvaluationReport:
        """Load and verify a specific or latest persisted `EvaluationReport` for `run_id`."""
        record, _, _, run_evals_dir, entries = self._scan_run_reports(run_id)
        if not entries:
            reports_dir = self._resolve_reports_dir(run_evals_dir)
            raise EvaluationReportNotFoundError(
                f"No persisted evaluation reports found for run '{record.id}'.",
                path=reports_dir,
            )
        if revision is None:
            return entries[-1][2]

        target_rev = parse_eval_report_revision(revision)
        for rev_num, _, rep_obj in entries:
            if rev_num == target_rev:
                return rep_obj

        missing_file = self._resolve_report_file(run_evals_dir, target_rev)
        raise EvaluationReportNotFoundError(
            f"Evaluation report revision {target_rev} ('{missing_file.name}') was not found for run '{record.id}'.",
            path=missing_file,
        )

    def write_report_file(
        self,
        report: EvaluationReport,
        *,
        revision: int | None = None,
    ) -> tuple[int, Path]:
        """Persist `report` as the next append-only `reports/000N.json` snapshot and return `(revision, path)`."""
        if not isinstance(report, EvaluationReport):
            raise InvalidEvaluationReportError(
                "EvalRegistry.write_report requires an EvaluationReport instance."
            )
        record, contract, evidence_records, run_evals_dir, entries = (
            self._scan_run_reports(report.run_id)
        )
        state_cache: dict[int, RunState] = {}
        self._verify_report_bindings(
            report,
            record=record,
            contract=contract,
            evidence_records=evidence_records,
            state_cache=state_cache,
        )

        next_rev = (entries[-1][0] + 1) if entries else 1
        target_rev = next_rev if revision is None else parse_eval_report_revision(revision)
        report_file = self._resolve_report_file(run_evals_dir, target_rev)

        if report_file.exists():
            raise EvaluationOverwriteError(
                f"Cannot overwrite existing evaluation report '{report_file}'.",
                path=report_file,
            )
        if target_rev != next_rev:
            raise InvalidEvaluationReportError(
                f"Cannot write evaluation report revision {target_rev}; next sequential revision is {next_rev}.",
                path=report_file,
            )

        try:
            safe_write_text(
                report_file,
                report.to_json(indent=2) + "\n",
                backup=False,
                create_parents=True,
                allow_overwrite=False,
            )
        except FileExistsError as exc:
            raise EvaluationOverwriteError(
                f"Cannot overwrite existing evaluation report '{report_file}'.",
                path=report_file,
            ) from exc
        except ValueError as exc:
            raise UnsafeEvaluationPathError(
                str(exc),
                path=report_file,
            ) from exc

        return target_rev, report_file

    def write_report(self, report: EvaluationReport) -> EvaluationReport:
        """Persist `report` as the next append-only `reports/000N.json` snapshot and return `report`."""
        self.write_report_file(report)
        return report

    def evaluate_run(
        self,
        run_id: str,
        *,
        extra_capability_requirements: Iterable[CapabilityRequirement | str] = (),
        write: bool = False,
    ) -> EvaluationReport:
        """Evaluate `run_id` against its current `RunState` and verified `RunEvidence` set.

        Read-only unless `write=True`, in which case `.rapid-os/evals/<run-id>/reports/000N.json` is appended.
        """
        validated_run_id = self._validate_run_id(run_id)
        record = self.run_registry.get(validated_run_id)
        contract = self.run_registry.get_contract(validated_run_id)
        current_state = self.run_registry.get_state(
            validated_run_id,
            revision=record.current_state_revision,
        )
        evidence_records = self.evidence_registry.verify(validated_run_id)

        report = self.evaluator.evaluate(
            contract,
            current_state,
            evidence_records,
            extra_capability_requirements=extra_capability_requirements,
        )
        if write:
            self.write_report_file(report)
        return report

    def validate(self, run_id: str | None = None):
        """Return a `ValidationReport` for the eval registry (optionally scoped to `run_id`)."""
        from rapid_os.domain.validation import validate_eval_registry

        return validate_eval_registry(
            self.rapid_dir,
            self.root,
            run_id=run_id,
        )

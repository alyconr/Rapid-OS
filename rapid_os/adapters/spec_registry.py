import json
import re
from pathlib import Path
from typing import Iterable, Mapping

from rapid_os.core.filesystem import (
    ensure_path_within_root,
    resolve_child_path,
    safe_write_text,
)
from rapid_os.domain.project import normalize_evidence_path
from rapid_os.domain.scope import ScopeSpec, write_scope_artifacts
from rapid_os.domain.specs import (
    SPEC_ARTIFACT_FILENAMES,
    SPEC_REVISION_SCHEMA_VERSION,
    SPEC_SCHEMA_VERSION,
    CurrentRevisionMissingError,
    DuplicateSpecIdentityError,
    InvalidRevisionManifestError,
    InvalidSpecRecordError,
    SpecArtifactDriftError,
    SpecLifecycleError,
    SpecMode,
    SpecNotFoundError,
    SpecRecord,
    SpecRevision,
    SpecStatus,
    UnsafeSpecPathError,
    derive_spec_id,
    scope_spec_from_revision,
    sha256_text,
    spec_revision_from_scope,
    validate_spec_id,
    validate_status_transition,
)


SPECS_DIRNAME = "specs"
SPEC_RECORD_FILENAME = "spec.json"
REVISIONS_DIRNAME = "revisions"
REVISION_MANIFEST_FILENAME = "revision.json"
REVISION_DIR_RE = re.compile(r"^\d{4}$")


def resolve_specs_root_dir(
    project_root: Path,
    project_rapid_dir: Path | None = None,
) -> tuple[Path, Path, Path]:
    """Return `(root, rapid_dir, specs_dir)` with containment verification."""
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
        specs_dir = resolve_child_path(
            contained_rapid,
            SPECS_DIRNAME,
            single_segment=True,
        )
        ensure_path_within_root(root, specs_dir)
    except ValueError as exc:
        raise UnsafeSpecPathError(
            str(exc),
            path=rapid_dir / SPECS_DIRNAME,
        ) from exc

    return root, contained_rapid, specs_dir


class SpecRegistry:
    """Filesystem-backed canonical Spec Registry under `.rapid-os/specs/`."""

    def __init__(
        self,
        project_root: Path = Path("."),
        project_rapid_dir: Path | None = None,
    ):
        root, rapid_dir, specs_dir = resolve_specs_root_dir(
            project_root,
            project_rapid_dir,
        )
        self.root = root
        self.rapid_dir = rapid_dir
        self.specs_dir = specs_dir

    def _resolve_spec_dir(self, spec_id: str) -> Path:
        validated_id = validate_spec_id(spec_id)
        try:
            spec_dir = resolve_child_path(
                self.specs_dir,
                validated_id,
                single_segment=True,
            )
            ensure_path_within_root(self.root, spec_dir)
        except ValueError as exc:
            raise UnsafeSpecPathError(str(exc), path=spec_id) from exc
        if spec_dir.is_symlink():
            raise UnsafeSpecPathError(
                f"Spec directory '{spec_id}' cannot be a symlink.",
                path=spec_dir,
            )
        return spec_dir

    def _resolve_revision_dir(self, spec_dir: Path, revision: int) -> Path:
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise InvalidRevisionManifestError(
                f"Invalid revision number '{revision}': must be a positive integer."
            )
        rev_name = f"{revision:04d}"
        try:
            revisions_dir = resolve_child_path(
                spec_dir,
                REVISIONS_DIRNAME,
                single_segment=True,
            )
            rev_dir = resolve_child_path(
                revisions_dir,
                rev_name,
                single_segment=True,
            )
            ensure_path_within_root(self.root, rev_dir)
        except ValueError as exc:
            raise UnsafeSpecPathError(str(exc), path=spec_dir) from exc
        if revisions_dir.is_symlink() or rev_dir.is_symlink():
            raise UnsafeSpecPathError(
                f"Revision directory '{rev_name}' cannot be a symlink.",
                path=rev_dir,
            )
        return rev_dir

    def _read_spec_record_from_dir(
        self,
        spec_dir: Path,
        expected_id: str,
    ) -> SpecRecord:
        try:
            record_file = resolve_child_path(
                spec_dir,
                SPEC_RECORD_FILENAME,
                single_segment=True,
            )
            ensure_path_within_root(self.root, record_file)
        except ValueError as exc:
            raise UnsafeSpecPathError(str(exc), path=spec_dir) from exc

        if record_file.is_symlink():
            raise UnsafeSpecPathError(
                f"Spec record '{record_file}' cannot be a symlink.",
                path=record_file,
            )
        if not record_file.exists():
            raise InvalidSpecRecordError(
                f"Spec record '{SPEC_RECORD_FILENAME}' is missing for '{expected_id}'.",
                path=record_file,
            )
        if not record_file.is_file():
            raise UnsafeSpecPathError(
                f"Spec record '{record_file}' is not a regular file.",
                path=record_file,
            )

        try:
            raw_text = record_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnsafeSpecPathError(
                f"Spec record '{record_file}' could not be read as UTF-8: {exc}",
                path=record_file,
            ) from exc

        record = SpecRecord.from_json(raw_text)
        if record.id != expected_id:
            raise DuplicateSpecIdentityError(
                f"Spec record id '{record.id}' does not match directory '{expected_id}'.",
                path=record_file,
            )
        return record

    def _read_and_verify_revision_dir(
        self,
        spec_id: str,
        revision: int,
        rev_dir: Path,
    ) -> SpecRevision:
        try:
            manifest_file = resolve_child_path(
                rev_dir,
                REVISION_MANIFEST_FILENAME,
                single_segment=True,
            )
            ensure_path_within_root(self.root, manifest_file)
        except ValueError as exc:
            raise UnsafeSpecPathError(str(exc), path=rev_dir) from exc

        if manifest_file.is_symlink():
            raise UnsafeSpecPathError(
                f"Revision manifest '{manifest_file}' cannot be a symlink.",
                path=manifest_file,
            )
        if not manifest_file.exists():
            raise InvalidRevisionManifestError(
                f"Revision manifest '{REVISION_MANIFEST_FILENAME}' is missing for '{spec_id}' r{revision}.",
                path=manifest_file,
            )
        if not manifest_file.is_file():
            raise UnsafeSpecPathError(
                f"Revision manifest '{manifest_file}' is not a regular file.",
                path=manifest_file,
            )

        try:
            raw_manifest = manifest_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise UnsafeSpecPathError(
                f"Revision manifest '{manifest_file}' could not be read as UTF-8: {exc}",
                path=manifest_file,
            ) from exc

        try:
            payload = json.loads(raw_manifest)
        except json.JSONDecodeError as exc:
            raise InvalidRevisionManifestError(
                f"Revision manifest '{manifest_file}' is invalid JSON: {exc.msg}",
                path=manifest_file,
            ) from exc

        if not isinstance(payload, Mapping):
            raise InvalidRevisionManifestError(
                f"Revision manifest '{manifest_file}' must be a JSON object.",
                path=manifest_file,
            )

        if "artifact_digests" not in payload or not isinstance(
            payload.get("artifact_digests"), Mapping
        ):
            raise InvalidRevisionManifestError(
                f"Revision manifest '{manifest_file}' is missing 'artifact_digests'.",
                path=manifest_file,
            )
        if "content_digest" not in payload or not isinstance(
            payload.get("content_digest"), str
        ):
            raise InvalidRevisionManifestError(
                f"Revision manifest '{manifest_file}' is missing 'content_digest'.",
                path=manifest_file,
            )

        spec_rev = SpecRevision.from_dict(payload, verify_digests=False)
        if spec_rev.spec_id != spec_id:
            raise InvalidRevisionManifestError(
                f"Revision manifest spec_id '{spec_rev.spec_id}' does not match '{spec_id}'.",
                path=manifest_file,
            )
        if spec_rev.revision != revision:
            raise InvalidRevisionManifestError(
                f"Revision manifest number '{spec_rev.revision}' does not match directory '{revision:04d}'.",
                path=manifest_file,
            )

        recorded_digests = dict(payload["artifact_digests"])  # type: ignore[arg-type]
        if set(recorded_digests.keys()) != set(SPEC_ARTIFACT_FILENAMES):
            raise InvalidRevisionManifestError(
                f"Revision manifest 'artifact_digests' must contain exactly {list(SPEC_ARTIFACT_FILENAMES)}.",
                path=manifest_file,
            )

        expected_digests = spec_rev.artifact_digests
        for filename in SPEC_ARTIFACT_FILENAMES:
            try:
                artifact_path = resolve_child_path(
                    rev_dir,
                    filename,
                    single_segment=True,
                )
                ensure_path_within_root(self.root, artifact_path)
            except ValueError as exc:
                raise UnsafeSpecPathError(str(exc), path=rev_dir) from exc

            if artifact_path.is_symlink():
                raise UnsafeSpecPathError(
                    f"Spec artifact '{artifact_path}' cannot be a symlink.",
                    path=artifact_path,
                )
            if not artifact_path.exists():
                raise SpecArtifactDriftError(
                    f"Spec artifact '{filename}' is missing for '{spec_id}' r{revision}.",
                    path=artifact_path,
                )
            if not artifact_path.is_file():
                raise UnsafeSpecPathError(
                    f"Spec artifact '{artifact_path}' is not a regular file.",
                    path=artifact_path,
                )

            try:
                artifact_text = artifact_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise UnsafeSpecPathError(
                    f"Spec artifact '{artifact_path}' could not be read as UTF-8: {exc}",
                    path=artifact_path,
                ) from exc

            disk_digest = sha256_text(artifact_text)
            manifest_digest = recorded_digests.get(filename)
            if disk_digest != manifest_digest or disk_digest != expected_digests[filename]:
                raise SpecArtifactDriftError(
                    f"Artifact digest mismatch in '{filename}' for '{spec_id}' r{revision}.",
                    path=artifact_path,
                )

        if payload["content_digest"] != spec_rev.content_digest:
            raise SpecArtifactDriftError(
                f"Revision content_digest mismatch for '{spec_id}' r{revision}.",
                path=manifest_file,
            )

        return spec_rev

    def exists(self, spec_id: str) -> bool:
        """Return True if `<spec-id>/spec.json` exists in `.rapid-os/specs`."""
        spec_dir = self._resolve_spec_dir(spec_id)
        if not spec_dir.exists() or not spec_dir.is_dir():
            return False
        record_file = spec_dir / SPEC_RECORD_FILENAME
        return record_file.exists() and record_file.is_file()

    def list_specs(self) -> tuple[SpecRecord, ...]:
        """Deterministically discover all specs in `.rapid-os/specs/*/spec.json` ordered by `id` ASC."""
        if not self.specs_dir.exists():
            return ()
        if self.specs_dir.is_symlink() or not self.specs_dir.is_dir():
            raise UnsafeSpecPathError(
                f"Specs registry root '{self.specs_dir}' is not a valid directory.",
                path=self.specs_dir,
            )

        records: list[SpecRecord] = []
        for entry in sorted(self.specs_dir.iterdir(), key=lambda p: p.name):
            if entry.is_symlink():
                raise UnsafeSpecPathError(
                    f"Spec entry '{entry}' cannot be a symlink.",
                    path=entry,
                )
            if not entry.is_dir():
                raise InvalidSpecRecordError(
                    f"Unexpected non-directory entry '{entry.name}' in spec registry.",
                    path=entry,
                )
            validate_spec_id(entry.name)
            record = self._read_spec_record_from_dir(entry, entry.name)
            records.append(record)

        records.sort(key=lambda r: r.id)
        return tuple(records)

    def get(self, spec_id: str) -> SpecRecord:
        """Load and validate `SpecRecord` for `spec_id`, verifying current revision directory exists."""
        spec_dir = self._resolve_spec_dir(spec_id)
        if not spec_dir.exists():
            raise SpecNotFoundError(
                f"Spec '{spec_id}' was not found in registry.",
                path=spec_dir,
            )
        if not spec_dir.is_dir():
            raise UnsafeSpecPathError(
                f"Spec path '{spec_dir}' is not a directory.",
                path=spec_dir,
            )
        record = self._read_spec_record_from_dir(spec_dir, spec_id)
        current_rev_dir = self._resolve_revision_dir(
            spec_dir,
            record.current_revision,
        )
        if not current_rev_dir.exists() or not current_rev_dir.is_dir():
            raise CurrentRevisionMissingError(
                f"Current revision r{record.current_revision} directory is missing for spec '{spec_id}'.",
                path=current_rev_dir,
            )
        return record

    def get_revision(
        self,
        spec_id: str,
        revision: int | None = None,
    ) -> SpecRevision:
        """Load and validate a specific or current `SpecRevision` without fallback."""
        record = self.get(spec_id)
        target_rev = record.current_revision if revision is None else revision
        if (
            isinstance(target_rev, bool)
            or not isinstance(target_rev, int)
            or target_rev < 1
        ):
            raise InvalidRevisionManifestError(
                f"Invalid revision '{target_rev}': must be a positive integer."
            )

        spec_dir = self._resolve_spec_dir(spec_id)
        rev_dir = self._resolve_revision_dir(spec_dir, target_rev)
        if not rev_dir.exists() or not rev_dir.is_dir():
            if target_rev == record.current_revision:
                raise CurrentRevisionMissingError(
                    f"Current revision r{target_rev} is missing for spec '{spec_id}'.",
                    path=rev_dir,
                )
            raise SpecNotFoundError(
                f"Revision r{target_rev} was not found for spec '{spec_id}'.",
                path=rev_dir,
            )

        return self._read_and_verify_revision_dir(spec_id, target_rev, rev_dir)

    def get_artifact_paths(
        self,
        spec_id: str,
        revision: int | None = None,
    ) -> dict[str, str]:
        """Return portable repository-relative POSIX paths for a spec revision's derived artifacts."""
        rev = self.get_revision(spec_id, revision=revision)
        spec_dir = self._resolve_spec_dir(spec_id)
        rev_dir = self._resolve_revision_dir(spec_dir, rev.revision)
        return {
            filename: normalize_evidence_path(rev_dir / filename, self.root)
            for filename in SPEC_ARTIFACT_FILENAMES
        }

    def get_artifact_contents(
        self,
        spec_id: str,
        revision: int | None = None,
    ) -> dict[str, tuple[str, str]]:
        """Return `{filename: (portable_posix_path, utf8_content)}` after full digest verification."""
        rev = self.get_revision(spec_id, revision=revision)
        spec_dir = self._resolve_spec_dir(spec_id)
        rev_dir = self._resolve_revision_dir(spec_dir, rev.revision)
        result: dict[str, tuple[str, str]] = {}
        for filename in SPEC_ARTIFACT_FILENAMES:
            artifact_path = resolve_child_path(
                rev_dir,
                filename,
                single_segment=True,
            )
            portable = normalize_evidence_path(artifact_path, self.root)
            content = artifact_path.read_text(encoding="utf-8")
            result[filename] = (portable, content)
        return result

    def _build_revision_input(
        self,
        *,
        spec_id: str | None,
        revision_num: int,
        spec_or_scope: SpecRevision | ScopeSpec | None = None,
        base_revision: SpecRevision | None = None,
        fields: Mapping[str, object] | None = None,
    ) -> SpecRevision:
        extra = dict(fields or {})
        raw_tags = extra.pop("tags", None)

        if isinstance(spec_or_scope, SpecRevision):
            resolved_id = (
                validate_spec_id(spec_id)
                if spec_id is not None and str(spec_id).strip()
                else spec_or_scope.spec_id
            )
            return SpecRevision(
                schema_version=SPEC_REVISION_SCHEMA_VERSION,
                spec_id=resolved_id,
                revision=revision_num,
                title=str(extra.get("title", spec_or_scope.title)),
                mode=extra.get("mode", spec_or_scope.mode),  # type: ignore[arg-type]
                business_objective=str(
                    extra.get(
                        "business_objective",
                        spec_or_scope.business_objective,
                    )
                ),
                problem_statement=str(
                    extra.get(
                        "problem_statement",
                        spec_or_scope.problem_statement,
                    )
                ),
                scope=extra.get("scope", spec_or_scope.scope),  # type: ignore[arg-type]
                out_of_scope=extra.get(
                    "out_of_scope", spec_or_scope.out_of_scope
                ),  # type: ignore[arg-type]
                actors_users=extra.get(
                    "actors_users",
                    extra.get("actors", spec_or_scope.actors_users),
                ),  # type: ignore[arg-type]
                main_flow=extra.get("main_flow", spec_or_scope.main_flow),  # type: ignore[arg-type]
                edge_cases=extra.get("edge_cases", spec_or_scope.edge_cases),  # type: ignore[arg-type]
                business_rules=extra.get(
                    "business_rules", spec_or_scope.business_rules
                ),  # type: ignore[arg-type]
                technical_constraints=extra.get(
                    "technical_constraints",
                    spec_or_scope.technical_constraints,
                ),  # type: ignore[arg-type]
                affected_paths=extra.get(
                    "affected_paths",
                    extra.get(
                        "affected_files_modules",
                        spec_or_scope.affected_paths,
                    ),
                ),  # type: ignore[arg-type]
                data_impact=str(
                    extra.get("data_impact", spec_or_scope.data_impact)
                ),
                acceptance_criteria=extra.get(
                    "acceptance_criteria",
                    spec_or_scope.acceptance_criteria,
                ),  # type: ignore[arg-type]
                testing_strategy=extra.get(
                    "testing_strategy",
                    spec_or_scope.testing_strategy,
                ),  # type: ignore[arg-type]
                implementation_tasks=extra.get(
                    "implementation_tasks",
                    spec_or_scope.implementation_tasks,
                ),  # type: ignore[arg-type]
                tags=raw_tags if raw_tags is not None else spec_or_scope.tags,  # type: ignore[arg-type]
            )

        if isinstance(spec_or_scope, ScopeSpec):
            converted = spec_revision_from_scope(
                spec_or_scope,
                spec_id=spec_id,
                revision=revision_num,
                tags=raw_tags if raw_tags is not None else (base_revision.tags if base_revision else ()),  # type: ignore[arg-type]
            )
            if not extra:
                return converted
            return self._build_revision_input(
                spec_id=converted.spec_id,
                revision_num=revision_num,
                spec_or_scope=converted,
                fields=extra,
            )

        if base_revision is not None:
            return self._build_revision_input(
                spec_id=spec_id or base_revision.spec_id,
                revision_num=revision_num,
                spec_or_scope=base_revision,
                fields={
                    **extra,
                    **({"tags": raw_tags} if raw_tags is not None else {}),
                },
            )

        raw_title = str(
            extra.get("title") or extra.get("initiative_name") or ""
        ).strip()
        resolved_id = (
            validate_spec_id(spec_id)
            if spec_id is not None and str(spec_id).strip()
            else derive_spec_id(raw_title)
        )
        resolved_title = raw_title if raw_title else resolved_id

        return SpecRevision(
            schema_version=SPEC_REVISION_SCHEMA_VERSION,
            spec_id=resolved_id,
            revision=revision_num,
            title=resolved_title,
            mode=extra.get("mode", SpecMode.FEATURE),  # type: ignore[arg-type]
            business_objective=str(extra.get("business_objective", "")),
            problem_statement=str(extra.get("problem_statement", "")),
            scope=extra.get("scope", ()),  # type: ignore[arg-type]
            out_of_scope=extra.get("out_of_scope", ()),  # type: ignore[arg-type]
            actors_users=extra.get(
                "actors_users", extra.get("actors", ())
            ),  # type: ignore[arg-type]
            main_flow=extra.get("main_flow", ()),  # type: ignore[arg-type]
            edge_cases=extra.get("edge_cases", ()),  # type: ignore[arg-type]
            business_rules=extra.get("business_rules", ()),  # type: ignore[arg-type]
            technical_constraints=extra.get(
                "technical_constraints", ()
            ),  # type: ignore[arg-type]
            affected_paths=extra.get(
                "affected_paths",
                extra.get("affected_files_modules", ()),
            ),  # type: ignore[arg-type]
            data_impact=str(extra.get("data_impact", "")),
            acceptance_criteria=extra.get("acceptance_criteria", ()),  # type: ignore[arg-type]
            testing_strategy=extra.get("testing_strategy", ()),  # type: ignore[arg-type]
            implementation_tasks=extra.get(
                "implementation_tasks", ()
            ),  # type: ignore[arg-type]
            tags=raw_tags if raw_tags is not None else (),  # type: ignore[arg-type]
        )

    def _write_immutable_revision_and_commit_record(
        self,
        spec_dir: Path,
        revision: SpecRevision,
        record: SpecRecord,
    ) -> SpecRecord:
        """Execute the filesystem commit-point pipeline:
        validate -> create revision dir -> write artifacts -> write revision.json ->
        validate complete revision -> update spec.json LAST.
        """
        rev_dir = self._resolve_revision_dir(spec_dir, revision.revision)
        if rev_dir.exists():
            raise InvalidRevisionManifestError(
                f"Immutable revision directory r{revision.revision} already exists for '{record.id}'.",
                path=rev_dir,
            )

        rev_dir.mkdir(parents=True, exist_ok=False)

        for filename, content in revision.render_artifacts().items():
            artifact_target = resolve_child_path(
                rev_dir,
                filename,
                single_segment=True,
            )
            safe_write_text(
                artifact_target,
                content,
                encoding="utf-8",
                backup=False,
                create_parents=True,
            )

        manifest_target = resolve_child_path(
            rev_dir,
            REVISION_MANIFEST_FILENAME,
            single_segment=True,
        )
        safe_write_text(
            manifest_target,
            revision.to_json(indent=2) + "\n",
            encoding="utf-8",
            backup=False,
            create_parents=True,
        )

        # Verify complete revision on disk BEFORE updating spec.json pointer
        self._read_and_verify_revision_dir(
            record.id,
            revision.revision,
            rev_dir,
        )

        record_target = resolve_child_path(
            spec_dir,
            SPEC_RECORD_FILENAME,
            single_segment=True,
        )
        safe_write_text(
            record_target,
            record.to_json(indent=2) + "\n",
            encoding="utf-8",
            backup=False,
            create_parents=True,
        )
        return record

    def create(
        self,
        spec_or_id: SpecRevision | ScopeSpec | str | None = None,
        *,
        spec_id: str | None = None,
        scope_spec: ScopeSpec | None = None,
        **fields: object,
    ) -> SpecRecord:
        """Create a new spec with `revision = 1` and `status = draft`."""
        explicit_id = spec_id
        input_obj: SpecRevision | ScopeSpec | None = scope_spec

        if isinstance(spec_or_id, (SpecRevision, ScopeSpec)):
            input_obj = spec_or_id
        elif isinstance(spec_or_id, str):
            explicit_id = spec_or_id
        elif spec_or_id is not None:
            raise TypeError(
                "SpecRegistry.create() expects a spec_id string, SpecRevision, ScopeSpec, or keyword fields."
            )

        if "id" in fields and explicit_id is None:
            raw_id_field = fields.pop("id")
            if raw_id_field is not None:
                explicit_id = str(raw_id_field)

        revision = self._build_revision_input(
            spec_id=explicit_id,
            revision_num=1,
            spec_or_scope=input_obj,
            fields=fields,
        )
        spec_dir = self._resolve_spec_dir(revision.spec_id)
        if spec_dir.exists():
            raise DuplicateSpecIdentityError(
                f"Spec '{revision.spec_id}' already exists in registry.",
                path=spec_dir,
            )

        record = SpecRecord(
            schema_version=SPEC_SCHEMA_VERSION,
            id=revision.spec_id,
            status=SpecStatus.DRAFT,
            current_revision=1,
        )
        return self._write_immutable_revision_and_commit_record(
            spec_dir,
            revision,
            record,
        )

    def revise(
        self,
        spec_id: str,
        spec_or_scope: SpecRevision | ScopeSpec | None = None,
        **changes: object,
    ) -> SpecRecord:
        """Create immutable revision `current_revision + 1` and reset status to `draft`."""
        record = self.get(spec_id)
        if record.status == SpecStatus.ARCHIVED:
            raise SpecLifecycleError(
                f"Cannot revise archived spec '{spec_id}': archived status is terminal.",
                path=self._resolve_spec_dir(spec_id) / SPEC_RECORD_FILENAME,
            )

        current_rev = self.get_revision(spec_id, record.current_revision)
        next_rev_num = record.current_revision + 1

        new_revision = self._build_revision_input(
            spec_id=record.id,
            revision_num=next_rev_num,
            spec_or_scope=spec_or_scope,
            base_revision=current_rev,
            fields=changes,
        )
        updated_record = SpecRecord(
            schema_version=SPEC_SCHEMA_VERSION,
            id=record.id,
            status=SpecStatus.DRAFT,
            current_revision=next_rev_num,
        )
        spec_dir = self._resolve_spec_dir(record.id)
        return self._write_immutable_revision_and_commit_record(
            spec_dir,
            new_revision,
            updated_record,
        )

    def set_status(
        self,
        spec_id: str,
        status: SpecStatus | str,
    ) -> SpecRecord:
        """Transition a spec's authoring lifecycle status (`draft`, `ready`, `archived`)."""
        record = self.get(spec_id)
        # Ensure current revision is valid before changing status
        self.get_revision(spec_id, record.current_revision)

        target_status = validate_status_transition(record.status, status)
        updated_record = SpecRecord(
            schema_version=SPEC_SCHEMA_VERSION,
            id=record.id,
            status=target_status,
            current_revision=record.current_revision,
        )
        spec_dir = self._resolve_spec_dir(record.id)
        record_target = resolve_child_path(
            spec_dir,
            SPEC_RECORD_FILENAME,
            single_segment=True,
        )
        safe_write_text(
            record_target,
            updated_record.to_json(indent=2) + "\n",
            encoding="utf-8",
            backup=False,
            create_parents=True,
        )
        return updated_record

    def export_legacy(
        self,
        spec_id: str,
        target_dir: Path | None = None,
        *,
        revision: int | None = None,
    ) -> tuple[Path, ...]:
        """Project a spec revision to legacy `SPECS.md`, `TASKS.md`, and `ACCEPTANCE.md` with backups."""
        rev = self.get_revision(spec_id, revision=revision)
        legacy_scope = scope_spec_from_revision(rev)
        dest_dir = Path(target_dir) if target_dir is not None else self.root
        written = write_scope_artifacts(legacy_scope, dest_dir)
        return tuple(written)

    def validate(self):
        """Validate the Spec Registry using `validate_spec_registry` (`RAPID800-RAPID809`)."""
        from rapid_os.domain.validation import validate_spec_registry

        return validate_spec_registry(self.rapid_dir, self.root)

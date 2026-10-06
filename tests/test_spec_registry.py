import contextlib
import io
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from rapid_os.adapters.context_sources import (
    ContextSourceLoader,
    discover_context_sources,
)
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.cli import main as cli_main
from rapid_os.domain.context import (
    ContextCompiler,
    ContextPriority,
    ContextRequest,
    ContextSourceKind,
)
from rapid_os.domain.scope import ScopeSpec
from rapid_os.domain.specs import (
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
)
from rapid_os.domain.validation import ERROR, INFO, WARNING, validate_spec_registry


def _sample_spec_kwargs(**overrides) -> dict[str, object]:
    base: dict[str, object] = {
        "spec_id": "booking-idempotency",
        "title": "Booking Idempotency",
        "mode": "bugfix",
        "business_objective": "Prevent duplicate bookings on retry.",
        "problem_statement": "Client retries create duplicate booking rows.",
        "scope": ("Idempotency key validation", "Transactional lock"),
        "out_of_scope": ("Payment gateway redesign",),
        "actors_users": ("Customer", "Booking API"),
        "main_flow": (
            "Receive booking request with idempotency key",
            "Check existing reservation by key",
            "Persist reservation atomically",
        ),
        "edge_cases": ("Concurrent duplicate requests", "Expired key"),
        "business_rules": ("One active booking per idempotency key",),
        "technical_constraints": ("PostgreSQL unique constraint required",),
        "affected_paths": ("rapid_os/domain/specs.py", "rapid_os/adapters/spec_registry.py"),
        "data_impact": "Add unique index on idempotency_key.",
        "acceptance_criteria": (
            "Retries return original booking payload",
            "No duplicate rows created under concurrency",
        ),
        "testing_strategy": ("Unit tests for key handling", "Integration retry test"),
        "implementation_tasks": (
            "Add idempotency key model validation",
            "Enforce atomic persistence",
        ),
        "tags": ("Booking", "database", "booking"),
    }
    base.update(overrides)
    return base


class SpecDomainModelTests(unittest.TestCase):
    def test_validate_spec_id_accepts_valid_slugs_and_rejects_invalid_identities(self):
        for valid in (
            "booking-idempotency",
            "whatsapp-confirmation-flow",
            "context-budget-hardening",
            "agent-builder-tools",
            "a1",
        ):
            self.assertEqual(validate_spec_id(valid), valid)

        for invalid in (
            "../spec",
            "foo/bar",
            "Foo",
            "_booking",
            r"C:\spec",
            "../../etc",
            "spec id",
            "",
            "   ",
            "-leading-hyphen",
            "a" * 64,
            "null\x00byte",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(DuplicateSpecIdentityError) as ctx:
                    validate_spec_id(invalid)
                self.assertEqual(ctx.exception.code, "RAPID806")

    def test_derive_spec_id_produces_deterministic_slug(self):
        self.assertEqual(
            derive_spec_id("Booking Idempotency Reliability"),
            "booking-idempotency-reliability",
        )
        self.assertEqual(
            derive_spec_id("  WhatsApp_Template -- Hardening!! "),
            "whatsapp-template-hardening",
        )
        with self.assertRaises(DuplicateSpecIdentityError):
            derive_spec_id("   !!!   ")

    def test_spec_status_allows_only_authoring_states_and_rejects_execution_states(self):
        self.assertEqual(SpecStatus.coerce("draft"), SpecStatus.DRAFT)
        self.assertEqual(SpecStatus.coerce("READY"), SpecStatus.READY)
        self.assertEqual(SpecStatus.coerce("archived"), SpecStatus.ARCHIVED)

        for execution_state in (
            "running",
            "in_progress",
            "blocked",
            "failed",
            "passed",
            "completed",
            "awaiting_review",
        ):
            with self.subTest(state=execution_state):
                with self.assertRaises(ValueError):
                    SpecStatus.coerce(execution_state)

    def test_spec_mode_normalizes_canonical_and_legacy_modes(self):
        self.assertEqual(SpecMode.coerce("feature"), SpecMode.FEATURE)
        self.assertEqual(SpecMode.coerce("new feature"), SpecMode.FEATURE)
        self.assertEqual(SpecMode.coerce("legacy hardening"), SpecMode.HARDENING)
        self.assertEqual(SpecMode.coerce("hardening"), SpecMode.HARDENING)
        self.assertEqual(SpecMode.coerce("bugfix"), SpecMode.BUGFIX)
        self.assertEqual(SpecMode.coerce("refactor"), SpecMode.REFACTOR)
        self.assertEqual(SpecMode.coerce("research"), SpecMode.RESEARCH)

        with self.assertRaises(ValueError):
            SpecMode.coerce("unknown-mode")

    def test_spec_record_round_trip_serialization(self):
        record = SpecRecord(
            schema_version=SPEC_SCHEMA_VERSION,
            id="booking-idempotency",
            status=SpecStatus.READY,
            current_revision=2,
        )
        expected_dict = {
            "schema_version": 1,
            "id": "booking-idempotency",
            "status": "ready",
            "current_revision": 2,
        }
        self.assertEqual(record.to_dict(), expected_dict)
        reconstructed = SpecRecord.from_json(record.to_json())
        self.assertEqual(reconstructed, record)

    def test_spec_revision_preserves_semantic_order_and_sorts_only_tags(self):
        rev_a = SpecRevision(
            **_sample_spec_kwargs(
                main_flow=("Step Z", "Step A", "Step M"),
                implementation_tasks=("Task 3", "Task 1", "Task 2"),
                acceptance_criteria=("Criterion B", "Criterion A"),
                scope=("Scope 2", "Scope 1"),
                tags=("Database", "booking", "API", "booking"),
            )
        )
        rev_b = SpecRevision(
            **_sample_spec_kwargs(
                main_flow=("Step Z", "Step A", "Step M"),
                implementation_tasks=("Task 3", "Task 1", "Task 2"),
                acceptance_criteria=("Criterion B", "Criterion A"),
                scope=("Scope 2", "Scope 1"),
                tags=("api", "booking", "database"),
            )
        )

        # Semantic order is strictly preserved
        self.assertEqual(rev_a.main_flow, ("Step Z", "Step A", "Step M"))
        self.assertEqual(rev_a.implementation_tasks, ("Task 3", "Task 1", "Task 2"))
        self.assertEqual(rev_a.acceptance_criteria, ("Criterion B", "Criterion A"))
        self.assertEqual(rev_a.scope, ("Scope 2", "Scope 1"))

        # Tags are lowercased, deduplicated, and sorted
        self.assertEqual(rev_a.tags, ("api", "booking", "database"))

        # Semantically identical revisions produce identical JSON and digests
        self.assertEqual(rev_a.to_json(), rev_b.to_json())
        self.assertEqual(rev_a.artifact_digests, rev_b.artifact_digests)
        self.assertEqual(rev_a.content_digest, rev_b.content_digest)

        # Round-trip serialization
        self.assertEqual(SpecRevision.from_json(rev_a.to_json()), rev_a)

    def test_affected_paths_enforces_relative_posix_and_rejects_traversal_or_absolute(self):
        rev = SpecRevision(
            **_sample_spec_kwargs(
                affected_paths=(r"rapid_os\domain\specs.py", "./tests/test_spec_registry.py"),
            )
        )
        self.assertEqual(
            rev.affected_paths,
            ("rapid_os/domain/specs.py", "tests/test_spec_registry.py"),
        )

        for unsafe_path in ("../outside.py", "/etc/passwd", r"C:\Windows\System32"):
            with self.subTest(unsafe_path=unsafe_path):
                with self.assertRaises(InvalidRevisionManifestError):
                    SpecRevision(**_sample_spec_kwargs(affected_paths=(unsafe_path,)))

    def test_scope_spec_compatibility_conversion_round_trip(self):
        legacy_scope = ScopeSpec(
            initiative_name="Booking Idempotency",
            mode="legacy hardening",
            business_objective="Prevent duplicate bookings",
            problem_statement="Retries duplicate records",
            scope=["Check key", "Lock row"],
            out_of_scope=["UI redesign"],
            actors_users=["User", "API"],
            main_flow=["Send key", "Verify key"],
            edge_cases=["Timeout"],
            business_rules=["Unique key"],
            technical_constraints=["Postgres"],
            affected_files_modules=[r"rapid_os\domain\specs.py"],
            data_impact="New index",
            acceptance_criteria=["Idempotent response"],
            testing_strategy=["Unit test"],
            implementation_tasks=["Add unique index"],
        )
        rev = spec_revision_from_scope(
            legacy_scope,
             tags=("Hardening", "Booking"),
        )
        self.assertEqual(rev.spec_id, "booking-idempotency")
        self.assertEqual(rev.mode, SpecMode.HARDENING)
        self.assertEqual(rev.affected_paths, ("rapid_os/domain/specs.py",))
        self.assertEqual(rev.tags, ("booking", "hardening"))

        projected = scope_spec_from_revision(rev)
        self.assertEqual(projected.initiative_name, "Booking Idempotency")
        self.assertEqual(projected.mode, "legacy hardening")
        self.assertEqual(projected.affected_files_modules, ["rapid_os/domain/specs.py"])


class SpecRegistryFilesystemTests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory(dir=self.repo_root)
        self.project_root = Path(self.temp_dir.name) / "project"
        self.project_root.mkdir(parents=True)
        self.rapid_dir = self.project_root / ".rapid-os"
        self.registry = SpecRegistry(self.project_root, self.rapid_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_spec_persists_record_revision_and_derived_artifacts_with_valid_digests(self):
        record = self.registry.create(**_sample_spec_kwargs())
        self.assertEqual(record.schema_version, SPEC_SCHEMA_VERSION)
        self.assertEqual(record.id, "booking-idempotency")
        self.assertEqual(record.status, SpecStatus.DRAFT)
        self.assertEqual(record.current_revision, 1)

        spec_dir = self.rapid_dir / "specs" / "booking-idempotency"
        spec_json_path = spec_dir / "spec.json"
        rev_dir = spec_dir / "revisions" / "0001"
        rev_json_path = rev_dir / "revision.json"
        req_path = rev_dir / "requirements.md"
        tasks_path = rev_dir / "tasks.md"
        acc_path = rev_dir / "acceptance.md"

        self.assertTrue(spec_json_path.is_file())
        self.assertTrue(rev_json_path.is_file())
        self.assertTrue(req_path.is_file())
        self.assertTrue(tasks_path.is_file())
        self.assertTrue(acc_path.is_file())

        loaded_rev = self.registry.get_revision("booking-idempotency")
        self.assertEqual(loaded_rev.schema_version, SPEC_REVISION_SCHEMA_VERSION)
        self.assertEqual(loaded_rev.revision, 1)
        self.assertEqual(loaded_rev.tags, ("booking", "database"))

        # Verify artifact digests match exact UTF-8 bytes on disk
        for filename, path in (
            ("requirements.md", req_path),
            ("tasks.md", tasks_path),
            ("acceptance.md", acc_path),
        ):
            disk_digest = sha256_text(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded_rev.artifact_digests[filename], disk_digest)

        report = self.registry.validate()
        self.assertFalse(report.has_errors)
        self.assertTrue(any(d.code == "RAPID800" for d in report.diagnostics))

    def test_duplicate_id_fails_without_overwriting_or_auto_suffixing(self):
        self.registry.create(**_sample_spec_kwargs())
        spec_json_before = (
            self.rapid_dir / "specs" / "booking-idempotency" / "spec.json"
        ).read_bytes()

        with self.assertRaises(DuplicateSpecIdentityError) as ctx:
            self.registry.create(
                **_sample_spec_kwargs(title="Completely Different Title")
            )
        self.assertEqual(ctx.exception.code, "RAPID806")

        spec_json_after = (
            self.rapid_dir / "specs" / "booking-idempotency" / "spec.json"
        ).read_bytes()
        self.assertEqual(spec_json_before, spec_json_after)
        self.assertEqual(len(self.registry.list_specs()), 1)

    def test_revise_creates_immutable_next_revision_and_resets_status_to_draft(self):
        self.registry.create(**_sample_spec_kwargs())
        self.registry.set_status("booking-idempotency", SpecStatus.READY)

        r1_dir = (
            self.rapid_dir / "specs" / "booking-idempotency" / "revisions" / "0001"
        )
        r1_snapshots = {
            p.name: p.read_bytes() for p in r1_dir.iterdir() if p.is_file()
        }

        updated_record = self.registry.revise(
            "booking-idempotency",
            business_rules=(
                "One active booking per idempotency key",
                "Provider timeout must reuse idempotency token",
            ),
        )
        self.assertEqual(updated_record.current_revision, 2)
        self.assertEqual(updated_record.status, SpecStatus.DRAFT)

        # r1 remains unchanged byte-for-byte
        r1_snapshots_after = {
            p.name: p.read_bytes() for p in r1_dir.iterdir() if p.is_file()
        }
        self.assertEqual(r1_snapshots, r1_snapshots_after)

        # Both r1 and r2 are readable and valid
        rev1 = self.registry.get_revision("booking-idempotency", revision=1)
        rev2 = self.registry.get_revision("booking-idempotency", revision=2)
        self.assertEqual(len(rev1.business_rules), 1)
        self.assertEqual(len(rev2.business_rules), 2)
        self.assertNotEqual(rev1.content_digest, rev2.content_digest)

    def test_lifecycle_transitions_draft_ready_reopen_archive_and_terminal_archived(self):
        self.registry.create(**_sample_spec_kwargs())

        # draft -> ready
        ready_rec = self.registry.set_status("booking-idempotency", "ready")
        self.assertEqual(ready_rec.status, SpecStatus.READY)

        # ready -> draft (reopen)
        reopened_rec = self.registry.set_status("booking-idempotency", "draft")
        self.assertEqual(reopened_rec.status, SpecStatus.DRAFT)

        # draft -> ready -> archived
        self.registry.set_status("booking-idempotency", "ready")
        archived_rec = self.registry.set_status("booking-idempotency", "archived")
        self.assertEqual(archived_rec.status, SpecStatus.ARCHIVED)

        spec_json_path = (
            self.rapid_dir / "specs" / "booking-idempotency" / "spec.json"
        )
        archived_bytes = spec_json_path.read_bytes()

        # archived is terminal: archived -> ready and archived -> draft fail without mutating files
        for invalid_target in ("ready", "draft", "archived"):
            with self.subTest(target=invalid_target):
                with self.assertRaises(SpecLifecycleError) as ctx:
                    self.registry.set_status("booking-idempotency", invalid_target)
                self.assertEqual(ctx.exception.code, "RAPID805")
                self.assertEqual(spec_json_path.read_bytes(), archived_bytes)

        # revising an archived spec also fails
        with self.assertRaises(SpecLifecycleError) as ctx_rev:
            self.registry.revise("booking-idempotency", title="New Title")
        self.assertEqual(ctx_rev.exception.code, "RAPID805")
        self.assertEqual(spec_json_path.read_bytes(), archived_bytes)

    def test_manual_artifact_drift_is_detected_with_rapid804(self):
        self.registry.create(**_sample_spec_kwargs())
        req_file = (
            self.rapid_dir
            / "specs"
            / "booking-idempotency"
            / "revisions"
            / "0001"
            / "requirements.md"
        )
        req_file.write_text("# SPEC: Tampered Manually\n", encoding="utf-8")

        with self.assertRaises(SpecArtifactDriftError) as ctx:
            self.registry.get_revision("booking-idempotency")
        self.assertEqual(ctx.exception.code, "RAPID804")

        report = validate_spec_registry(self.rapid_dir, self.project_root)
        self.assertTrue(report.has_errors)
        codes = [d.code for d in report.diagnostics]
        self.assertIn("RAPID804", codes)
        self.assertNotIn("RAPID800", codes)

    def test_missing_current_revision_emits_rapid802(self):
        self.registry.create(**_sample_spec_kwargs())
        spec_json = self.rapid_dir / "specs" / "booking-idempotency" / "spec.json"
        spec_json.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "id": "booking-idempotency",
                    "status": "draft",
                    "current_revision": 5,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        with self.assertRaises(CurrentRevisionMissingError) as ctx:
            self.registry.get("booking-idempotency")
        self.assertEqual(ctx.exception.code, "RAPID802")

        report = validate_spec_registry(self.rapid_dir, self.project_root)
        self.assertTrue(report.has_errors)
        self.assertIn("RAPID802", [d.code for d in report.diagnostics])

    def test_corrupt_current_revision_never_falls_back_to_previous_revision(self):
        self.registry.create(**_sample_spec_kwargs(business_objective="Objective v1"))
        self.registry.revise(
            "booking-idempotency",
            business_objective="Objective v2",
        )
        r2_manifest = (
            self.rapid_dir
            / "specs"
            / "booking-idempotency"
            / "revisions"
            / "0002"
            / "revision.json"
        )
        r2_manifest.write_text("{corrupt-json", encoding="utf-8")

        with self.assertRaises(InvalidRevisionManifestError) as ctx:
            self.registry.get_revision("booking-idempotency")
        self.assertEqual(ctx.exception.code, "RAPID803")

        report = validate_spec_registry(self.rapid_dir, self.project_root)
        self.assertTrue(report.has_errors)
        self.assertIn("RAPID803", [d.code for d in report.diagnostics])

    def test_orphan_revision_keeps_current_revision_valid_and_emits_rapid809_warning(self):
        self.registry.create(**_sample_spec_kwargs(business_objective="Objective v1"))
        self.registry.revise(
            "booking-idempotency",
            business_objective="Objective v2",
        )
        # Simulate an incomplete/unreferenced revision 0003 while current_revision == 2
        orphan_dir = (
            self.rapid_dir
            / "specs"
            / "booking-idempotency"
            / "revisions"
            / "0003"
        )
        orphan_dir.mkdir(parents=True)
        (orphan_dir / "requirements.md").write_text(
            "partial write before crash", encoding="utf-8"
        )

        record = self.registry.get("booking-idempotency")
        self.assertEqual(record.current_revision, 2)
        current_rev = self.registry.get_revision("booking-idempotency")
        self.assertEqual(current_rev.revision, 2)
        self.assertEqual(current_rev.business_objective, "Objective v2")

        report = validate_spec_registry(self.rapid_dir, self.project_root)
        self.assertFalse(report.has_errors)
        self.assertTrue(report.has_warnings)
        codes = [d.code for d in report.diagnostics]
        self.assertIn("RAPID800", codes)
        self.assertIn("RAPID809", codes)


class SpecRegistryContextAndE2ETests(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.temp_dir = tempfile.TemporaryDirectory(dir=self.repo_root)
        self.project_root = Path(self.temp_dir.name) / "project"
        self.standards_dir = self.project_root / ".rapid-os" / "standards"
        self.standards_dir.mkdir(parents=True)
        (self.standards_dir / "security.md").write_text(
            "# Security\nValidate all inputs.", encoding="utf-8"
        )
        (self.standards_dir / "tech-stack.md").write_text(
            "# Tech Stack\nPython 3.12", encoding="utf-8"
        )
        self.rapid_dir = self.project_root / ".rapid-os"
        self.registry = SpecRegistry(self.project_root, self.rapid_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_coexisting_specs_and_legacy_singleton_do_not_contaminate_selected_spec_context(self):
        # Legacy singleton on root
        (self.project_root / "SPECS.md").write_text(
            "# SPEC: Legacy Singleton Initiative\nLegacy singleton rule.",
            encoding="utf-8",
        )
        (self.project_root / "TASKS.md").write_text(
            "# TASKS: Legacy Singleton\n- [ ] Legacy task",
            encoding="utf-8",
        )
        (self.project_root / "ACCEPTANCE.md").write_text(
            "# ACCEPTANCE: Legacy Singleton\n- [ ] Legacy acceptance",
            encoding="utf-8",
        )

        # Spec A r1 and r2
        self.registry.create(
            **_sample_spec_kwargs(
                spec_id="spec-a",
                title="Spec A Initiative",
                business_rules=("Spec A old rule r1",),
                implementation_tasks=("Spec A task r1",),
                acceptance_criteria=("Spec A acceptance r1",),
            )
        )
        self.registry.revise(
            "spec-a",
            business_rules=("Spec A new rule r2",),
            implementation_tasks=("Spec A task r2",),
            acceptance_criteria=("Spec A acceptance r2",),
        )
        self.registry.set_status("spec-a", "ready")

        # Spec B r1
        self.registry.create(
            **_sample_spec_kwargs(
                spec_id="spec-b",
                title="Spec B Initiative",
                business_rules=("Spec B secret rule",),
                implementation_tasks=("Spec B task",),
                acceptance_criteria=("Spec B acceptance",),
            )
        )
        self.registry.set_status("spec-b", "ready")

        # 1. Compile with --spec spec-a (defaults to current revision r2)
        request_a_current = ContextRequest(mode="feature", spec_id="spec-a")
        sources_a = discover_context_sources(
            self.project_root,
            self.rapid_dir,
            request=request_a_current,
        )
        compiled_a = ContextCompiler().compile(
            request=request_a_current,
            sources=sources_a,
        )

        selected_ids = [entry.source_id for entry in compiled_a.manifest.selected]
        self.assertIn("spec.spec-a.requirements", selected_ids)
        self.assertIn("spec.spec-a.tasks", selected_ids)
        self.assertIn("spec.spec-a.acceptance", selected_ids)
        self.assertNotIn("spec.scope", selected_ids)
        self.assertNotIn("spec.tasks", selected_ids)
        self.assertNotIn("spec.acceptance", selected_ids)
        self.assertFalse(any("spec-b" in sid for sid in selected_ids))

        self.assertIn("Spec A new rule r2", compiled_a.content)
        self.assertNotIn("Spec A old rule r1", compiled_a.content)
        self.assertNotIn("Spec B secret rule", compiled_a.content)
        self.assertNotIn("Legacy Singleton Initiative", compiled_a.content)

        # Verify manifest provenance points to .rapid-os/specs/spec-a/revisions/0002/...
        by_id = {entry.source_id: entry for entry in compiled_a.manifest.selected}
        self.assertEqual(
            by_id["spec.spec-a.requirements"].provenance,
            ".rapid-os/specs/spec-a/revisions/0002/requirements.md",
        )
        self.assertEqual(by_id["spec.spec-a.requirements"].kind, "spec")
        self.assertEqual(
            by_id["spec.spec-a.tasks"].provenance,
            ".rapid-os/specs/spec-a/revisions/0002/tasks.md",
        )
        self.assertEqual(by_id["spec.spec-a.tasks"].kind, "tasks")
        self.assertEqual(
            by_id["spec.spec-a.acceptance"].provenance,
            ".rapid-os/specs/spec-a/revisions/0002/acceptance.md",
        )
        self.assertEqual(by_id["spec.spec-a.acceptance"].kind, "acceptance")

        # 2. Historical revision: --spec spec-a --spec-revision 1
        request_a_r1 = ContextRequest(
            mode="feature",
            spec_id="spec-a",
            spec_revision=1,
        )
        sources_a_r1 = discover_context_sources(
            self.project_root,
            self.rapid_dir,
            request=request_a_r1,
        )
        compiled_a_r1 = ContextCompiler().compile(
            request=request_a_r1,
            sources=sources_a_r1,
        )
        self.assertIn("Spec A old rule r1", compiled_a_r1.content)
        self.assertNotIn("Spec A new rule r2", compiled_a_r1.content)
        by_id_r1 = {
            entry.source_id: entry for entry in compiled_a_r1.manifest.selected
        }
        self.assertEqual(
            by_id_r1["spec.spec-a.requirements"].provenance,
            ".rapid-os/specs/spec-a/revisions/0001/requirements.md",
        )

        # 3. Without --spec: legacy fallback behavior remains intact
        request_legacy = ContextRequest(mode="feature")
        sources_legacy = discover_context_sources(
            self.project_root,
            self.rapid_dir,
            request=request_legacy,
        )
        compiled_legacy = ContextCompiler().compile(
            request=request_legacy,
            sources=sources_legacy,
        )
        legacy_selected_ids = [
            entry.source_id for entry in compiled_legacy.manifest.selected
        ]
        self.assertIn("spec.scope", legacy_selected_ids)
        self.assertIn("Legacy Singleton Initiative", compiled_legacy.content)
        self.assertNotIn("Spec A new rule r2", compiled_legacy.content)

    def test_draft_and_archived_specs_fail_context_compilation(self):
        self.registry.create(**_sample_spec_kwargs(spec_id="draft-spec"))
        self.registry.create(**_sample_spec_kwargs(spec_id="archived-spec"))
        self.registry.set_status("archived-spec", "archived")

        for non_ready_id in ("draft-spec", "archived-spec"):
            with self.subTest(spec_id=non_ready_id):
                req = ContextRequest(mode="feature", spec_id=non_ready_id)
                discovery = ContextSourceLoader().load(
                    self.project_root,
                    self.rapid_dir,
                    request=req,
                )
                self.assertTrue(discovery.load_errors)
                self.assertEqual(discovery.load_errors[0].code, "RAPID805")

                out_buf = io.StringIO()
                err_buf = io.StringIO()
                cli_args = cli_main.create_parser().parse_args(
                    ["context", "--spec", non_ready_id]
                )
                with patch.object(cli_main, "CURRENT_DIR", self.project_root), patch.object(
                    cli_main, "PROJECT_RAPID_DIR", self.rapid_dir
                ), contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(
                    err_buf
                ):
                    with self.assertRaises(SystemExit) as cm:
                        cli_main.context_command(cli_args)
                self.assertEqual(cm.exception.code, 1)
                self.assertEqual(out_buf.getvalue(), "")
                self.assertIn("RAPID805", err_buf.getvalue())

    def test_full_e2e_lifecycle_create_show_ready_compile_revise_ready_compile_export_legacy(self):
        def run_cli(argv):
            out = io.StringIO()
            err = io.StringIO()
            args = cli_main.create_parser().parse_args(argv)
            with patch.object(cli_main, "CURRENT_DIR", self.project_root), patch.object(
                cli_main, "PROJECT_RAPID_DIR", self.rapid_dir
            ), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                if args.command == "spec":
                    code = cli_main.spec_command(args)
                elif args.command == "context":
                    code = cli_main.context_command(args)
                else:
                    raise AssertionError(f"Unexpected command {args.command}")
            return code, out.getvalue(), err.getvalue()

        # 1. Create spec via CLI wizard
        create_answers = iter(
            [
                "",  # derive ID from title
                "Booking Idempotency",
                "bugfix",
                "Prevent duplicate bookings",
                "Retries duplicate rows",
                "Check idempotency key",
                "Billing UI",
                "Customer, API",
                "Receive request; Check key; Save",
                "Timeout on first attempt",
                "Rule v1: key expires in 1h",
                "PostgreSQL 16",
                "rapid_os/domain/specs.py",
                "Add idempotency_keys table",
                "Duplicate request returns 200 with original booking",
                "Integration test",
                "Create migration; Add middleware",
                "Booking, Database",
            ]
        )
        with patch("builtins.input", lambda prompt="": next(create_answers)):
            code, _, _ = run_cli(["spec", "create"])
        self.assertEqual(code, 0)

        # 2. Show JSON
        code, show_out, _ = run_cli(["spec", "show", "booking-idempotency", "--json"])
        self.assertEqual(code, 0)
        show_payload = json.loads(show_out)
        self.assertEqual(show_payload["id"], "booking-idempotency")
        self.assertEqual(show_payload["status"], "draft")
        self.assertEqual(show_payload["current_revision"], 1)

        # 3. Mark ready
        code, _, _ = run_cli(["spec", "status", "booking-idempotency", "ready"])
        self.assertEqual(code, 0)

        # 4. Compile context --spec
        code, ctx_r1_out, _ = run_cli(
            ["context", "--mode", "feature", "--spec", "booking-idempotency", "--json"]
        )
        self.assertEqual(code, 0)
        ctx_r1 = json.loads(ctx_r1_out)
        self.assertIn("Rule v1: key expires in 1h", ctx_r1["content"])

        # 5. Revise via CLI wizard (updating business_rules, keeping defaults for others)
        r1_req_bytes = (
            self.rapid_dir
            / "specs"
            / "booking-idempotency"
            / "revisions"
            / "0001"
            / "requirements.md"
        ).read_bytes()

        revise_answers = iter(
            [
                "",  # title default
                "",  # mode default
                "",  # objective default
                "",  # problem default
                "",  # scope default
                "",  # out_of_scope default
                "",  # actors default
                "",  # main_flow default
                "",  # edge_cases default
                "Rule v2: key expires in 24h",  # updated business_rules
                "",  # technical_constraints default
                "",  # affected_paths default
                "",  # data_impact default
                "",  # acceptance_criteria default
                "",  # testing_strategy default
                "",  # implementation_tasks default
                "",  # tags default
            ]
        )
        with patch("builtins.input", lambda prompt="": next(revise_answers)):
            code, _, _ = run_cli(["spec", "revise", "booking-idempotency"])
        self.assertEqual(code, 0)

        # 6. Current revision advanced to 2, status reset to draft, r1 immutable
        record_after_revise = self.registry.get("booking-idempotency")
        self.assertEqual(record_after_revise.current_revision, 2)
        self.assertEqual(record_after_revise.status, SpecStatus.DRAFT)
        self.assertEqual(
            (
                self.rapid_dir
                / "specs"
                / "booking-idempotency"
                / "revisions"
                / "0001"
                / "requirements.md"
            ).read_bytes(),
            r1_req_bytes,
        )

        # 7. Mark ready again and compile new revision
        code, _, _ = run_cli(["spec", "status", "booking-idempotency", "ready"])
        self.assertEqual(code, 0)

        code, ctx_r2_out, _ = run_cli(
            ["context", "--mode", "feature", "--spec", "booking-idempotency", "--json"]
        )
        self.assertEqual(code, 0)
        ctx_r2 = json.loads(ctx_r2_out)
        self.assertIn("Rule v2: key expires in 24h", ctx_r2["content"])
        self.assertNotIn("Rule v1: key expires in 1h", ctx_r2["content"])

        # 8. Export legacy and verify SPECS.md, TASKS.md, ACCEPTANCE.md projection + backup on re-export
        code, _, _ = run_cli(["spec", "export-legacy", "booking-idempotency"])
        self.assertEqual(code, 0)
        self.assertTrue((self.project_root / "SPECS.md").is_file())
        self.assertTrue((self.project_root / "TASKS.md").is_file())
        self.assertTrue((self.project_root / "ACCEPTANCE.md").is_file())
        self.assertIn(
            "Rule v2: key expires in 24h",
            (self.project_root / "SPECS.md").read_text(encoding="utf-8"),
        )

        # Export r1 over existing legacy files -> creates .bak backups and does not change registry state
        code, _, _ = run_cli(
            ["spec", "export-legacy", "booking-idempotency", "--revision", "1"]
        )
        self.assertEqual(code, 0)
        self.assertIn(
            "Rule v1: key expires in 1h",
            (self.project_root / "SPECS.md").read_text(encoding="utf-8"),
        )
        self.assertTrue(list(self.project_root.glob("SPECS.md.*.bak")))

        final_record = self.registry.get("booking-idempotency")
        self.assertEqual(final_record.current_revision, 2)
        self.assertEqual(final_record.status, SpecStatus.READY)


if __name__ == "__main__":
    unittest.main()

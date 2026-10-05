from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from rapid_os.adapters.context_sources import (
    ContextSourceLoader,
    discover_context_sources,
)
from rapid_os.domain.context import (
    CONTEXT_MANIFEST_SCHEMA_VERSION,
    DEFAULT_CONTEXT_POLICY,
    CompiledContext,
    ContextBudgetExceededError,
    ContextCompiler,
    ContextConflict,
    ContextFragment,
    ContextManifest,
    ContextMode,
    ContextPolicy,
    ContextPriority,
    ContextRequest,
    ContextResolver,
    ContextSource,
    ContextSourceKind,
    ManifestEntry,
    build_project_intelligence_source,
)
from rapid_os.domain.project import (
    Confidence,
    Evidence,
    ProjectFact,
    ProjectModel,
    SourceType,
)
from rapid_os.domain.scanner import build_project_model


class ContextDomainModelTests(unittest.TestCase):
    def test_valid_source_fragment_and_request_construction(self):
        source = ContextSource(
            id="standard.security",
            kind=ContextSourceKind.SECURITY,
            content="Never execute shell=True.",
            priority=ContextPriority.CRITICAL,
            required=True,
            path=".rapid-os/standards/security.md",
            tags=("security", "process"),
        )
        self.assertEqual(source.id, "standard.security")
        self.assertEqual(source.kind, ContextSourceKind.SECURITY)
        self.assertEqual(source.priority, ContextPriority.CRITICAL)
        self.assertTrue(source.required)
        self.assertEqual(source.path, ".rapid-os/standards/security.md")
        self.assertEqual(source.tags, ("process", "security"))

        fragment = ContextFragment(
            id="standard.security#root",
            source_id=source.id,
            kind=source.kind,
            content=source.content,
            priority=source.priority,
            required=source.required,
            reason="selected: required security standard",
            path=source.path,
            tags=source.tags,
        )
        self.assertEqual(fragment.chars, len("Never execute shell=True."))

        request = ContextRequest(
            mode="bugfix",
            harness="codex",
            objective="Fix database connection retry",
            affected_paths=("rapid_os/core/process.py",),
            tags=("database", "Security"),
            max_chars=16000,
        )
        self.assertEqual(request.mode, ContextMode.BUGFIX)
        self.assertEqual(request.harness, "codex")
        self.assertEqual(request.tags, ("database", "security"))
        self.assertEqual(request.affected_paths, ("rapid_os/core/process.py",))

    def test_invalid_source_ids_and_paths_are_rejected(self):
        for invalid_id in ("", "_load_security", "BadId", "standard..security", "-bad"):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(ValueError):
                    ContextSource(
                        id=invalid_id,
                        kind=ContextSourceKind.SECURITY,
                        content="Rules",
                    )

        for invalid_path in ("/etc/passwd", "../secret.md", "docs/../../escape.md"):
            with self.subTest(invalid_path=invalid_path):
                with self.assertRaises(ValueError):
                    ContextSource(
                        id="standard.security",
                        kind=ContextSourceKind.SECURITY,
                        content="Rules",
                        path=invalid_path,
                    )

    def test_invalid_context_requests_are_rejected(self):
        with self.assertRaises(ValueError):
            ContextRequest(mode="unknown_mode")

        with self.assertRaises(ValueError):
            ContextRequest(harness="unknown_harness")

        with self.assertRaises(ValueError):
            ContextRequest(max_chars=0)

        with self.assertRaises(ValueError):
            ContextRequest(max_chars=-50)

        with self.assertRaises(ValueError):
            ContextRequest(max_chars=True)

        with self.assertRaises(ValueError):
            ContextRequest(affected_paths=("../outside.py",))

    def test_duplicate_source_ids_are_rejected(self):
        s1 = ContextSource(
            id="standard.security",
            kind=ContextSourceKind.SECURITY,
            content="Rule A",
        )
        s2 = ContextSource(
            id="standard.security",
            kind=ContextSourceKind.SECURITY,
            content="Rule B",
        )
        compiler = ContextCompiler()
        with self.assertRaises(ValueError) as ctx:
            compiler.compile(ContextRequest(), sources=(s1, s2))
        self.assertIn("Duplicate ContextSource id", str(ctx.exception))


class ContextPrecedenceAndDeterminismTests(unittest.TestCase):
    def test_precedence_orders_security_over_coding_rules_and_business_over_intelligence(self):
        coding_rules = ContextSource(
            id="standard.coding-rules",
            kind=ContextSourceKind.CODING_RULES,
            content="Use snake_case.",
            priority=ContextPriority.MEDIUM,
        )
        security = ContextSource(
            id="standard.security",
            kind=ContextSourceKind.SECURITY,
            content="Validate all inputs.",
            priority=ContextPriority.CRITICAL,
            required=True,
        )
        business = ContextSource(
            id="standard.business",
            kind=ContextSourceKind.BUSINESS,
            content="Orders must be idempotent.",
            priority=ContextPriority.HIGH,
        )
        task_constraints = ContextSource(
            id="task.constraints",
            kind=ContextSourceKind.TASK_CONSTRAINTS,
            content="Do not touch legacy billing module.",
            priority=ContextPriority.CRITICAL,
            required=True,
        )
        project_model = ProjectModel(
            facts=(
                ProjectFact(
                    category="language",
                    value="python",
                    confidence=Confidence.HIGH,
                    detector="language.python",
                    evidence=(
                        Evidence(
                            path="pyproject.toml",
                            reason="Python project file",
                            source_type=SourceType.FILE,
                            detector="language.python",
                        ),
                    ),
                ),
            )
        )

        compiler = ContextCompiler()
        compiled = compiler.compile(
            ContextRequest(mode="feature"),
            sources=(coding_rules, business, security, task_constraints),
            project_model=project_model,
        )

        selected_ids = [entry.source_id for entry in compiled.manifest.selected]
        self.assertEqual(
            selected_ids,
            [
                "task.constraints",
                "standard.security",
                "standard.business",
                "standard.coding-rules",
                "project.intelligence",
            ],
        )

    def test_compilation_is_deterministic_independent_of_source_input_order(self):
        sources_a = [
            ContextSource(
                id="standard.security",
                kind=ContextSourceKind.SECURITY,
                content="Never use shell=True.",
                priority=ContextPriority.CRITICAL,
                required=True,
                path=".rapid-os/standards/security.md",
            ),
            ContextSource(
                id="standard.business",
                kind=ContextSourceKind.BUSINESS,
                content="Database: PostgreSQL.",
                priority=ContextPriority.HIGH,
                path=".rapid-os/standards/business.md",
            ),
            ContextSource(
                id="standard.tech-stack",
                kind=ContextSourceKind.TECH_STACK,
                content="Python 3.12 + FastAPI.",
                priority=ContextPriority.HIGH,
                required=True,
                path=".rapid-os/standards/tech-stack.md",
            ),
            ContextSource(
                id="standard.coding-rules",
                kind=ContextSourceKind.CODING_RULES,
                content="Prefer immutable dataclasses.",
                priority=ContextPriority.MEDIUM,
                path=".rapid-os/standards/coding-rules.md",
            ),
            ContextSource(
                id="ref.vision",
                kind=ContextSourceKind.REFERENCE,
                content="Minimalist dashboard aesthetic.",
                priority=ContextPriority.LOW,
                path="references/VISION_CONTEXT.md",
            ),
        ]

        request = ContextRequest(
            mode="feature",
            harness="codex",
            objective="Implement user profile endpoint",
            max_chars=12000,
        )
        compiler = ContextCompiler()
        compiled_1 = compiler.compile(request, sources_a)
        compiled_2 = compiler.compile(request, list(reversed(sources_a)))

        self.assertEqual(compiled_1, compiled_2)
        self.assertEqual(compiled_1.to_json(), compiled_2.to_json())


class ContextBudgetAndRequiredTests(unittest.TestCase):
    def test_required_sources_within_or_equal_to_budget_succeed(self):
        required_source = ContextSource(
            id="standard.security",
            kind=ContextSourceKind.SECURITY,
            content="Disallow shell=True.",
            priority=ContextPriority.CRITICAL,
            required=True,
        )
        compiler = ContextCompiler()
        baseline = compiler.compile(
            ContextRequest(mode="general", max_chars=5000),
            sources=(required_source,),
        )
        exact_budget = len(baseline.content)

        compiled_exact = compiler.compile(
            ContextRequest(mode="general", max_chars=exact_budget),
            sources=(required_source,),
        )
        self.assertEqual(len(compiled_exact.content), exact_budget)
        self.assertEqual(compiled_exact.manifest.compiled_chars, exact_budget)

    def test_required_sources_exceeding_budget_raise_explicit_error_without_truncating(self):
        required_source = ContextSource(
            id="standard.security",
            kind=ContextSourceKind.SECURITY,
            content="A" * 500,
            priority=ContextPriority.CRITICAL,
            required=True,
        )
        compiler = ContextCompiler()
        with self.assertRaises(ContextBudgetExceededError) as ctx:
            compiler.compile(
                ContextRequest(mode="general", max_chars=200),
                sources=(required_source,),
            )
        self.assertEqual(ctx.exception.max_chars, 200)
        self.assertGreater(ctx.exception.required_chars, 200)
        self.assertIn("standard.security", ctx.exception.required_sources)

    def test_optional_sources_fitting_budget_are_included_and_overflow_is_skipped_without_truncation(self):
        req_source = ContextSource(
            id="standard.security",
            kind=ContextSourceKind.SECURITY,
            content="Strict validation.",
            priority=ContextPriority.CRITICAL,
            required=True,
        )
        opt_fits = ContextSource(
            id="standard.business",
            kind=ContextSourceKind.BUSINESS,
            content="Short business rule.",
            priority=ContextPriority.HIGH,
        )
        opt_overflow = ContextSource(
            id="ref.vision",
            kind=ContextSourceKind.REFERENCE,
            content="V" * 2000,
            priority=ContextPriority.LOW,
        )

        compiler = ContextCompiler()
        compiled = compiler.compile(
            ContextRequest(mode="feature", max_chars=600),
            sources=(req_source, opt_fits, opt_overflow),
        )

        self.assertLessEqual(len(compiled.content), 600)
        selected_ids = [e.source_id for e in compiled.manifest.selected]
        skipped_map = {e.source_id: e.reason for e in compiled.manifest.skipped}

        self.assertIn("standard.security", selected_ids)
        self.assertIn("standard.business", selected_ids)
        self.assertNotIn("ref.vision", selected_ids)
        self.assertEqual(skipped_map.get("ref.vision"), "skipped: source exceeds remaining budget")
        self.assertIn("Short business rule.", compiled.content)
        self.assertNotIn("VVVV", compiled.content)

    def test_missing_required_kind_is_recorded_in_manifest(self):
        policy = ContextPolicy(
            required_kinds=(ContextSourceKind.SECURITY,),
        )
        resolver = ContextResolver(policy=policy)
        selection = resolver.resolve(
            ContextRequest(mode="hardening"),
            sources=(),
        )
        self.assertIn(ContextSourceKind.SECURITY, selection.missing_required_kinds)
        self.assertTrue(
            any(
                entry.source_id == "missing.security" and entry.required
                for entry in selection.skipped
            )
        )


class ContextConflictAndManifestSerializationTests(unittest.TestCase):
    def test_conflict_detected_between_business_and_tech_stack_databases(self):
        business = ContextSource(
            id="standard.business",
            kind=ContextSourceKind.BUSINESS,
            content="We must store financial records in MySQL.",
            priority=ContextPriority.HIGH,
        )
        tech_stack = ContextSource(
            id="standard.tech-stack",
            kind=ContextSourceKind.TECH_STACK,
            content="Primary database: PostgreSQL.",
            priority=ContextPriority.HIGH,
            required=True,
        )

        compiler = ContextCompiler()
        compiled = compiler.compile(
            ContextRequest(mode="feature"),
            sources=(tech_stack, business),
        )

        self.assertEqual(len(compiled.manifest.conflicts), 1)
        conflict = compiled.manifest.conflicts[0]
        self.assertEqual(conflict.category, "database")
        self.assertEqual(conflict.winner, "standard.business")
        self.assertIn("standard.business", conflict.sources)
        self.assertIn("standard.tech-stack", conflict.sources)

    def test_conflict_detected_between_user_standard_and_detected_project_intelligence(self):
        tech_stack = ContextSource(
            id="standard.tech-stack",
            kind=ContextSourceKind.TECH_STACK,
            content="Database: PostgreSQL",
            priority=ContextPriority.HIGH,
            required=True,
        )
        project_model = ProjectModel(
            facts=(
                ProjectFact(
                    category="database",
                    value="mongodb",
                    confidence=Confidence.HIGH,
                    detector="database.mongodb",
                    evidence=(
                        Evidence(
                            path="package.json",
                            reason="mongoose dependency",
                            source_type=SourceType.DEPENDENCY,
                            detector="database.mongodb",
                        ),
                    ),
                ),
            )
        )

        compiler = ContextCompiler()
        compiled = compiler.compile(
            ContextRequest(mode="feature"),
            sources=(tech_stack,),
            project_model=project_model,
        )

        self.assertEqual(len(compiled.manifest.conflicts), 1)
        conflict = compiled.manifest.conflicts[0]
        self.assertEqual(conflict.category, "database")
        self.assertEqual(conflict.winner, "standard.tech-stack")
        self.assertIn("project.intelligence", conflict.sources)

    def test_manifest_and_compiled_context_round_trip_serialization(self):
        source = ContextSource(
            id="standard.security",
            kind=ContextSourceKind.SECURITY,
            content="Validate remote package references.",
            priority=ContextPriority.CRITICAL,
            required=True,
            path=".rapid-os/standards/security.md",
        )
        compiler = ContextCompiler()
        compiled = compiler.compile(
            ContextRequest(
                mode="hardening",
                harness="claude",
                objective="Audit package references",
                max_chars=8000,
            ),
            sources=(source,),
        )

        self.assertEqual(compiled.manifest.schema_version, CONTEXT_MANIFEST_SCHEMA_VERSION)
        json_payload = compiled.to_json(indent=2)
        restored = CompiledContext.from_json(json_payload)
        self.assertEqual(compiled, restored)

        manifest_json = compiled.manifest.to_json(indent=2)
        restored_manifest = ContextManifest.from_json(manifest_json)
        self.assertEqual(compiled.manifest, restored_manifest)


class ProjectModelIntegrationAndSafetyTests(unittest.TestCase):
    def test_project_model_is_rendered_compactly_and_filtered_by_task_relevance(self):
        model = ProjectModel(
            facts=(
                ProjectFact(
                    category="language",
                    value="python",
                    confidence=Confidence.HIGH,
                    detector="language.python",
                    evidence=(
                        Evidence(
                            path="pyproject.toml",
                            reason="pyproject.toml found",
                            source_type=SourceType.FILE,
                            detector="language.python",
                        ),
                    ),
                ),
                ProjectFact(
                    category="testing",
                    value="pytest",
                    confidence=Confidence.HIGH,
                    detector="testing.pytest",
                    evidence=(
                        Evidence(
                            path="pyproject.toml",
                            reason="pytest configured",
                            source_type=SourceType.CONFIG,
                            detector="testing.pytest",
                        ),
                    ),
                ),
                ProjectFact(
                    category="database",
                    value="postgres",
                    confidence=Confidence.MEDIUM,
                    detector="database.postgres",
                    evidence=(
                        Evidence(
                            path=".env.example",
                            reason="POSTGRES_URL variable",
                            source_type=SourceType.ENVIRONMENT_KEY,
                            detector="database.postgres",
                        ),
                    ),
                ),
                ProjectFact(
                    category="deploy_provider",
                    value="vercel",
                    confidence=Confidence.HIGH,
                    detector="deploy.vercel",
                    evidence=(
                        Evidence(
                            path="vercel.json",
                            reason="vercel.json file",
                            source_type=SourceType.CONFIG,
                            detector="deploy.vercel",
                        ),
                    ),
                ),
            )
        )

        # In bugfix mode with no deployment tag, deploy_provider is excluded while language/testing are kept
        bugfix_req = ContextRequest(mode="bugfix", objective="Fix unit test runner")
        pi_source = build_project_intelligence_source(model, bugfix_req)
        self.assertIsNotNone(pi_source)
        self.assertIn("Languages:\n- python", pi_source.content)
        self.assertIn("Testing:\n- pytest", pi_source.content)
        self.assertNotIn("Deployment:", pi_source.content)
        self.assertNotIn("schema_version", pi_source.content)

        # When database tag is explicitly requested, database fact is included
        db_req = ContextRequest(mode="bugfix", tags=("database",))
        pi_db_source = build_project_intelligence_source(model, db_req)
        self.assertIsNotNone(pi_db_source)
        self.assertIn("Database:\n- postgres", pi_db_source.content)

    def test_secret_values_from_dotenv_are_never_included_in_compiled_context(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
            (root / ".env").write_text(
                "OPENAI_API_KEY=sk-live-super-secret-value-999\n"
                "DATABASE_URL=postgresql://admin:topsecretpass@db.internal:5432/prod\n",
                encoding="utf-8",
            )
            standards_dir = root / ".rapid-os" / "standards"
            standards_dir.mkdir(parents=True)
            (standards_dir / "security.md").write_text(
                "# Security\nNever expose credentials.\n",
                encoding="utf-8",
            )
            # Arbitrary file outside known context sources must be ignored
            (root / "RANDOM_NOTES.md").write_text(
                "UNTRUSTED_NOTE_TOKEN_12345",
                encoding="utf-8",
            )

            project_model = build_project_model(root)
            sources = discover_context_sources(
                root,
                root / ".rapid-os",
                project_model=project_model,
            )
            compiler = ContextCompiler()
            compiled = compiler.compile(
                ContextRequest(mode="general"),
                sources=sources,
                project_model=project_model,
            )

            self.assertNotIn("sk-live-super-secret-value-999", compiled.content)
            self.assertNotIn("topsecretpass", compiled.content)
            self.assertNotIn("sk-live-super-secret-value-999", compiled.to_json())
            self.assertNotIn("UNTRUSTED_NOTE_TOKEN_12345", compiled.content)

    def test_context_source_loader_discovers_known_sources_cleanly(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir = root / ".rapid-os"
            standards = rapid_dir / "standards"
            standards.mkdir(parents=True)
            (standards / "security.md").write_text("Security rules", encoding="utf-8")
            (standards / "tech-stack.md").write_text("Python 3.12", encoding="utf-8")
            (root / "SPECS.md").write_text("Feature spec", encoding="utf-8")

            loader = ContextSourceLoader()
            result = loader.load(
                root,
                rapid_dir,
                include_project_intelligence=False,
            )
            self.assertEqual(len(result.load_errors), 0)
            discovered_ids = [s.id for s in result.sources]
            self.assertEqual(
                discovered_ids,
                ["standard.security", "standard.tech-stack", "spec.scope"],
            )


if __name__ == "__main__":
    unittest.main()

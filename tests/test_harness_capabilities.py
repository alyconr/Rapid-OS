import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rapid_os.adapters.capability_lock import (
    build_capability_lock,
    load_capability_lock,
    write_capability_lock,
)
from rapid_os.adapters.harness_registry import (
    BUILTIN_HARNESS_PROFILES,
    HarnessRegistry,
)
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.cli import main as cli_main
from rapid_os.domain.capabilities import (
    CANONICAL_CAPABILITY_CATALOG,
    CANONICAL_CAPABILITY_IDS,
    CAPABILITY_LOCK_SCHEMA_VERSION,
    CAPABILITY_RESOLUTION_SCHEMA_VERSION,
    HARNESS_PROFILE_SCHEMA_VERSION,
    CapabilityCategory,
    CapabilityRequirement,
    CapabilityRequirementResolver,
    CapabilityResolution,
    CapabilityResolver,
    CapabilitySupport,
    CapabilitySupportStatus,
    CompatibilityStatus,
    HarnessProfile,
    validate_capability_id,
)
from rapid_os.domain.context import ContextCompiler, ContextRequest, ContextSource
from rapid_os.domain.execution import (
    ExecutionClass,
    ExecutionContract,
    GateKind,
    GatePhase,
    GateRequirement,
    PolicyDecision,
    RiskLevel,
    TaskContract,
    WorkspaceRequirement,
)
from rapid_os.domain.harnesses import (
    BUILTIN_HARNESS_IDS,
    CapabilityResolutionDigestMismatchError,
    HarnessIdentityError,
    HarnessProfileNotFoundError,
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
from rapid_os.domain.specs import SpecMode, SpecStatus
from rapid_os.domain.validation import (
    ERROR,
    INFO,
    WARNING,
    validate_capability_lock,
    validate_harness_registry,
)


def _sample_contract(
    *,
    run_id: str = "run-001",
    harness: str = "codex",
    classification: ExecutionClass = ExecutionClass.BOUNDED,
    risk: RiskLevel = RiskLevel.MEDIUM,
    workspace: WorkspaceRequirement = WorkspaceRequirement.CURRENT_ALLOWED,
    with_tasks: bool = True,
    with_tests_gate: bool = True,
    with_human_gates: bool = True,
) -> ExecutionContract:
    tasks = (
        (
            TaskContract(
                id="T001",
                description="Implement capability registry",
            ),
        )
        if with_tasks
        else ()
    )
    gates: list[GateRequirement] = [
        GateRequirement(
            id="gate.baseline",
            kind=GateKind.BASELINE_CHECK,
            phase=GatePhase.PRE_EXECUTION,
            required=True,
            waivable=False,
            reason="Baseline must be clean.",
        ),
    ]
    if with_tests_gate:
        gates.append(
            GateRequirement(
                id="gate.tests",
                kind=GateKind.IMPLEMENTATION_TESTS,
                phase=GatePhase.POST_EXECUTION,
                required=True,
                waivable=False,
                reason="Tests must pass.",
            )
        )
    if with_human_gates:
        gates.extend(
            [
                GateRequirement(
                    id="gate.peer-review",
                    kind=GateKind.PEER_REVIEW,
                    phase=GatePhase.POST_EXECUTION,
                    required=True,
                    waivable=True,
                    reason="Peer review required.",
                ),
                GateRequirement(
                    id="gate.security-review",
                    kind=GateKind.SECURITY_REVIEW,
                    phase=GatePhase.POST_EXECUTION,
                    required=True,
                    waivable=False,
                    reason="Security review required.",
                ),
                GateRequirement(
                    id="gate.manual-approval",
                    kind=GateKind.MANUAL_APPROVAL,
                    phase=GatePhase.POST_EXECUTION,
                    required=True,
                    waivable=False,
                    reason="Manual sign-off required.",
                ),
            ]
        )
    decision = PolicyDecision(
        classification=classification,
        risk=risk,
        risk_signals=(),
        workspace=workspace,
        gates=tuple(gates),
        reasons=("Deterministic test contract.",),
    )
    return ExecutionContract(
        schema_version=1,
        run_id=run_id,
        spec_id="auth-session",
        spec_revision=1,
        spec_content_digest="a" * 64,
        harness=harness,
        context_digest="d" * 64,
        context_manifest_digest="e" * 64,
        project_model_digest="b" * 64,
        policy_source="default",
        policy_digest="c" * 64,
        decision=decision,
        classification=classification,
        risk=risk,
        risk_signals=(),
        workspace=workspace,
        gates=tuple(gates),
        tasks=tasks,
    )


def _profile_with_overrides(
    harness_id: str,
    overrides: dict[str, CapabilitySupportStatus],
) -> HarnessProfile:
    entries: list[CapabilitySupport] = []
    for cap_id in CANONICAL_CAPABILITY_IDS:
        status = overrides.get(cap_id, CapabilitySupportStatus.UNKNOWN)
        entries.append(
            CapabilitySupport(
                capability_id=cap_id,
                status=status,
                reason=f"Explicit {status.value} declaration for {cap_id}.",
            )
        )
    return HarnessProfile(
        schema_version=HARNESS_PROFILE_SCHEMA_VERSION,
        id=harness_id,
        capabilities=tuple(entries),
    )


class HarnessIdentityAndCatalogTests(unittest.TestCase):
    def test_validate_harness_id_accepts_valid_slugs_and_rejects_unsafe_values(self):
        for valid in (
            "codex",
            "claude",
            "cursor",
            "vscode",
            "antigravity",
            "my-company-agent",
            "agent1",
            "a",
        ):
            self.assertEqual(validate_harness_id(valid), valid)

        for invalid in (
            "",
            "..",
            "../x",
            "/abs/path",
            "\\abs\\path",
            "C:agent",
            "C:\\agent",
            "UpperCase",
            "has space",
            " leading",
            "trailing ",
            "null\x00byte",
            "under_score",
            "-starts-with-dash",
            "a" * 64,
        ):
            with self.assertRaises(HarnessIdentityError) as ctx:
                validate_harness_id(invalid)
            self.assertEqual(ctx.exception.code, "RAPID1104")

    def test_validate_harness_profile_source_enforces_portable_provenance(self):
        self.assertEqual(
            validate_harness_profile_source(
                "builtin:codex",
                expected_harness_id="codex",
            ),
            "builtin:codex",
        )
        self.assertEqual(
            validate_harness_profile_source(
                ".rapid-os/harnesses/my-agent.json",
                expected_harness_id="my-agent",
            ),
            ".rapid-os/harnesses/my-agent.json",
        )
        for bad_source in (
            "/etc/passwd",
            "C:\\Users\\alyco\\codex.json",
            ".rapid-os/harnesses/../codex.json",
            "builtin:other",
            ".rapid-os/harnesses/other.json",
        ):
            with self.assertRaises(UnsafeHarnessPathError):
                validate_harness_profile_source(
                    bad_source,
                    expected_harness_id="codex",
                )

    def test_canonical_capability_catalog_is_complete_and_rejects_unknown_ids(self):
        expected_ids = {
            "context.consume",
            "repository.read",
            "repository.write",
            "workspace.current",
            "workspace.isolated",
            "shell.execute",
            "tests.execute",
            "git.inspect",
            "git.modify",
            "mcp.invoke",
            "subagents.delegate",
        }
        self.assertEqual(set(CANONICAL_CAPABILITY_IDS), expected_ids)
        self.assertEqual(set(CANONICAL_CAPABILITY_CATALOG.keys()), expected_ids)
        self.assertEqual(
            CANONICAL_CAPABILITY_CATALOG["context.consume"].category,
            CapabilityCategory.CONTEXT,
        )

        for cap_id in expected_ids:
            self.assertEqual(validate_capability_id(cap_id), cap_id)

        for invalid_cap in (
            "",
            "gate.peer-review",
            "custom.arbitrary",
            "UPPER.CASE",
            "../escape",
            "null\x00cap",
        ):
            with self.assertRaises(InvalidCapabilityIdError) as ctx:
                validate_capability_id(invalid_cap)
            self.assertEqual(ctx.exception.code, "RAPID1101")

    def test_phase5_modules_do_not_import_subprocess_or_runtime_exec(self):
        repo_root = Path(__file__).resolve().parents[1]
        phase5_files = (
            repo_root / "rapid_os" / "domain" / "harnesses.py",
            repo_root / "rapid_os" / "domain" / "capabilities.py",
            repo_root / "rapid_os" / "adapters" / "harness_registry.py",
            repo_root / "rapid_os" / "adapters" / "capability_lock.py",
        )
        forbidden_tokens = ("subprocess", "os.system", "Popen", "shell=True")
        for file_path in phase5_files:
            content = file_path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(
                    token,
                    content,
                    f"Forbidden token '{token}' found in {file_path.name}",
                )


class ContextAndExecutionContractHarnessExtensibilityTests(unittest.TestCase):
    def test_context_request_and_compiler_accept_custom_harness_without_reading_registry(self):
        req = ContextRequest(
            mode="feature",
            harness="my-company-agent",
            objective="Build custom agent flow",
        )
        self.assertEqual(req.harness, "my-company-agent")

        compiler = ContextCompiler()
        sources = (
            ContextSource(
                id="core.standards",
                kind="coding_rules",
                content="Standard rules.",
                required=True,
            ),
        )
        artifact = compiler.compile(req, sources)
        self.assertEqual(artifact.manifest.harness, "my-company-agent")
        self.assertIn("my-company-agent", artifact.content)

    def test_execution_contract_accepts_custom_harness_with_schema_v1_preserved(self):
        contract = _sample_contract(harness="my-company-agent")
        self.assertEqual(contract.schema_version, 1)
        self.assertEqual(contract.harness, "my-company-agent")
        roundtrip = ExecutionContract.from_json(contract.to_json())
        self.assertEqual(roundtrip, contract)


class BuiltinAndProjectHarnessProfileTests(unittest.TestCase):
    def test_builtin_profiles_are_valid_deterministic_and_conservative(self):
        self.assertEqual(
            set(BUILTIN_HARNESS_PROFILES.keys()),
            set(BUILTIN_HARNESS_IDS),
        )
        for harness_id, profile in BUILTIN_HARNESS_PROFILES.items():
            self.assertEqual(profile.id, harness_id)
            self.assertEqual(profile.schema_version, HARNESS_PROFILE_SCHEMA_VERSION)
            self.assertEqual(len(profile.content_digest), 64)
            self.assertEqual(profile, HarnessProfile.from_json(profile.to_json()))

            status_map = profile.support_map()
            self.assertEqual(set(status_map.keys()), set(CANONICAL_CAPABILITY_IDS))
            self.assertEqual(
                status_map["context.consume"].status,
                CapabilitySupportStatus.SUPPORTED,
            )
            self.assertEqual(
                status_map["repository.read"].status,
                CapabilitySupportStatus.SUPPORTED,
            )
            self.assertEqual(
                status_map["workspace.current"].status,
                CapabilitySupportStatus.SUPPORTED,
            )
            for unknown_cap in (
                "repository.write",
                "workspace.isolated",
                "shell.execute",
                "tests.execute",
                "git.inspect",
                "git.modify",
                "mcp.invoke",
                "subagents.delegate",
            ):
                self.assertEqual(
                    status_map[unknown_cap].status,
                    CapabilitySupportStatus.UNKNOWN,
                    f"{harness_id} builtin {unknown_cap} should be UNKNOWN",
                )

    def test_harness_profile_digest_is_optional_on_input_and_verified_when_present(self):
        raw_without_digest = {
            "schema_version": 1,
            "id": "codex",
            "capabilities": [
                {
                    "capability_id": "context.consume",
                    "status": "supported",
                    "reason": "Consumes context.",
                },
                {
                    "capability_id": "repository.read",
                    "status": "supported",
                    "reason": "Reads repo.",
                },
            ],
        }
        profile = HarnessProfile.from_dict(raw_without_digest)
        self.assertEqual(len(profile.content_digest), 64)
        serialized = json.loads(profile.to_json())
        self.assertEqual(serialized["content_digest"], profile.content_digest)

        self.assertEqual(HarnessProfile.from_dict(serialized), profile)

        tampered = dict(serialized)
        tampered["content_digest"] = "0" * 64
        with self.assertRaises(InvalidHarnessProfileError) as ctx:
            HarnessProfile.from_dict(tampered)
        self.assertEqual(ctx.exception.code, "RAPID1102")

    def test_strict_profile_schema_rejects_unknown_fields_and_duplicates(self):
        for forbidden_key in (
            "agent_status",
            "last_seen",
            "model",
            "execution_result",
        ):
            payload = {
                "schema_version": 1,
                "id": "codex",
                "capabilities": [],
                forbidden_key: "value",
            }
            with self.assertRaises(InvalidHarnessProfileError) as ctx:
                HarnessProfile.from_dict(payload)
            self.assertEqual(ctx.exception.code, "RAPID1102")

        duplicate_caps = {
            "schema_version": 1,
            "id": "codex",
            "capabilities": [
                {
                    "capability_id": "context.consume",
                    "status": "supported",
                    "reason": "First.",
                },
                {
                    "capability_id": "context.consume",
                    "status": "unsupported",
                    "reason": "Duplicate.",
                },
            ],
        }
        with self.assertRaises(InvalidCapabilitySupportError) as ctx:
            HarnessProfile.from_dict(duplicate_caps)
        self.assertEqual(ctx.exception.code, "RAPID1106")

    def test_project_profile_override_replaces_builtin_without_partial_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir = root / ".rapid-os"
            registry = HarnessRegistry(root, rapid_dir)

            initial = registry.resolve_active_profile("codex")
            self.assertEqual(initial.source, "builtin:codex")
            self.assertEqual(len(initial.profile.capabilities), 11)

            minimal_profile = HarnessProfile(
                schema_version=1,
                id="codex",
                capabilities=(
                    CapabilitySupport(
                        capability_id="context.consume",
                        status=CapabilitySupportStatus.SUPPORTED,
                        reason="Minimal project override.",
                    ),
                ),
            )
            registry.write_project_profile(minimal_profile)

            active = registry.resolve_active_profile("codex")
            self.assertEqual(active.source, ".rapid-os/harnesses/codex.json")
            self.assertEqual(len(active.profile.capabilities), 1)
            self.assertIsNone(active.profile.get_support("repository.read"))
            self.assertEqual(
                active.profile.status_for("repository.read"),
                CapabilitySupportStatus.UNKNOWN,
            )

    def test_corrupt_project_profile_fails_loudly_without_falling_back_to_builtin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir = root / ".rapid-os"
            harnesses_dir = rapid_dir / "harnesses"
            harnesses_dir.mkdir(parents=True, exist_ok=True)
            (harnesses_dir / "codex.json").write_text("{not valid json", encoding="utf-8")

            registry = HarnessRegistry(root, rapid_dir)
            with self.assertRaises(InvalidHarnessProfileError) as ctx:
                registry.resolve_active_profile("codex")
            self.assertEqual(ctx.exception.code, "RAPID1102")

            with self.assertRaises(InvalidHarnessProfileError):
                registry.list_profiles()

            report = validate_harness_registry(rapid_dir, root)
            error_codes = [d.code for d in report.diagnostics if d.level == ERROR]
            self.assertIn("RAPID1102", error_codes)

    def test_initialize_project_profile_rejects_unknown_custom_id_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir = root / ".rapid-os"
            registry = HarnessRegistry(root, rapid_dir)

            with self.assertRaises(HarnessProfileNotFoundError) as ctx:
                registry.initialize_project_profile("my-custom-agent")
            self.assertEqual(ctx.exception.code, "RAPID1103")

            created = registry.initialize_project_profile("codex")
            self.assertTrue(created.exists())

            with self.assertRaises(InvalidHarnessProfileError) as ctx2:
                registry.initialize_project_profile("codex")
            self.assertEqual(ctx2.exception.code, "RAPID1102")


class RequirementDerivationAndResolutionTests(unittest.TestCase):
    def test_requirement_derivation_respects_contract_and_ignores_human_gates(self):
        contract = _sample_contract(
            classification=ExecutionClass.BOUNDED,
            workspace=WorkspaceRequirement.CURRENT_ALLOWED,
            with_tasks=True,
            with_tests_gate=True,
            with_human_gates=True,
        )
        reqs = CapabilityRequirementResolver.derive(contract)
        req_ids = [r.capability_id for r in reqs]
        self.assertEqual(
            req_ids,
            [
                "context.consume",
                "repository.read",
                "repository.write",
                "tests.execute",
                "workspace.current",
            ],
        )
        by_id = {r.capability_id: r for r in reqs}
        self.assertEqual(by_id["context.consume"].source, "contract.context")
        self.assertEqual(by_id["repository.read"].source, "contract.repository")
        self.assertEqual(by_id["repository.write"].source, "contract.tasks")
        self.assertEqual(by_id["tests.execute"].source, "contract.gate.tests")
        self.assertEqual(by_id["workspace.current"].source, "contract.workspace")

        # ARCHITECTURAL + no tasks -> repository.write NOT automatically required
        isolated_contract = _sample_contract(
            classification=ExecutionClass.ARCHITECTURAL,
            risk=RiskLevel.HIGH,
            workspace=WorkspaceRequirement.ISOLATED_REQUIRED,
            with_tasks=False,
            with_tests_gate=False,
            with_human_gates=True,
        )
        isolated_reqs = CapabilityRequirementResolver.derive(isolated_contract)
        isolated_by_id = {r.capability_id: r for r in isolated_reqs}
        self.assertEqual(
            [r.capability_id for r in isolated_reqs],
            [
                "context.consume",
                "repository.read",
                "workspace.isolated",
            ],
        )
        self.assertNotIn("repository.write", isolated_by_id)
        self.assertEqual(
            isolated_by_id["workspace.isolated"].source,
            "contract.workspace",
        )

        # SPIKE + tasks -> repository.write required with source="contract.tasks"
        spike_with_tasks = _sample_contract(
            classification=ExecutionClass.SPIKE,
            risk=RiskLevel.LOW,
            workspace=WorkspaceRequirement.CURRENT_ALLOWED,
            with_tasks=True,
            with_tests_gate=False,
            with_human_gates=False,
        )
        spike_reqs = CapabilityRequirementResolver.derive(spike_with_tasks)
        spike_by_id = {r.capability_id: r for r in spike_reqs}
        self.assertIn("repository.write", spike_by_id)
        self.assertEqual(spike_by_id["repository.write"].source, "contract.tasks")

    def test_additive_extra_requirements_and_deduplication(self):
        contract = _sample_contract(
            workspace=WorkspaceRequirement.CURRENT_ALLOWED,
            with_tasks=True,
            with_tests_gate=False,
        )
        reqs = CapabilityRequirementResolver.derive(
            contract,
            extra_requirements=("mcp.invoke", "subagents.delegate", "context.consume"),
        )
        by_id = {r.capability_id: r for r in reqs}
        self.assertEqual(
            set(by_id.keys()),
            {
                "context.consume",
                "repository.read",
                "repository.write",
                "workspace.current",
                "mcp.invoke",
                "subagents.delegate",
            },
        )
        # Contract-derived requirement preserves primary contractual provenance
        self.assertEqual(by_id["context.consume"].source, "contract.context")
        self.assertEqual(by_id["repository.read"].source, "contract.repository")
        self.assertEqual(by_id["repository.write"].source, "contract.tasks")
        self.assertEqual(by_id["workspace.current"].source, "contract.workspace")
        self.assertEqual(by_id["mcp.invoke"].source, "cli.require")
        self.assertEqual(by_id["subagents.delegate"].source, "cli.require")

    def test_resolution_outcomes_compatible_incompatible_and_unresolved(self):
        contract = _sample_contract(
            harness="codex",
            workspace=WorkspaceRequirement.ISOLATED_REQUIRED,
            with_tasks=True,
            with_tests_gate=True,
        )
        builtin_profile = BUILTIN_HARNESS_PROFILES["codex"]
        unresolved_res = CapabilityResolver.resolve(
            contract,
            builtin_profile,
            profile_source="builtin:codex",
        )
        self.assertEqual(unresolved_res.status, CompatibilityStatus.UNRESOLVED)
        self.assertEqual(
            unresolved_res.satisfied,
            ("context.consume", "repository.read"),
        )
        self.assertEqual(
            unresolved_res.unknown,
            ("repository.write", "tests.execute", "workspace.isolated"),
        )
        self.assertEqual(unresolved_res.missing, ())

        incompat_profile = _profile_with_overrides(
            "codex",
            {
                "context.consume": CapabilitySupportStatus.SUPPORTED,
                "repository.read": CapabilitySupportStatus.SUPPORTED,
                "repository.write": CapabilitySupportStatus.SUPPORTED,
                "workspace.isolated": CapabilitySupportStatus.UNSUPPORTED,
                "tests.execute": CapabilitySupportStatus.UNKNOWN,
            },
        )
        incompat_res = CapabilityResolver.resolve(
            contract,
            incompat_profile,
            profile_source=".rapid-os/harnesses/codex.json",
        )
        self.assertEqual(incompat_res.status, CompatibilityStatus.INCOMPATIBLE)
        self.assertEqual(incompat_res.missing, ("workspace.isolated",))
        self.assertEqual(incompat_res.unknown, ("tests.execute",))

        compat_profile = _profile_with_overrides(
            "codex",
            {
                "context.consume": CapabilitySupportStatus.SUPPORTED,
                "repository.read": CapabilitySupportStatus.SUPPORTED,
                "repository.write": CapabilitySupportStatus.SUPPORTED,
                "workspace.isolated": CapabilitySupportStatus.SUPPORTED,
                "tests.execute": CapabilitySupportStatus.SUPPORTED,
            },
        )
        compat_res = CapabilityResolver.resolve(
            contract,
            compat_profile,
            profile_source=".rapid-os/harnesses/codex.json",
        )
        self.assertEqual(compat_res.status, CompatibilityStatus.COMPATIBLE)
        self.assertEqual(compat_res.missing, ())
        self.assertEqual(compat_res.unknown, ())

        compat_res_2 = CapabilityResolver.resolve(
            contract,
            compat_profile,
            profile_source=".rapid-os/harnesses/codex.json",
        )
        self.assertEqual(compat_res.to_json(), compat_res_2.to_json())
        self.assertEqual(compat_res.resolution_digest, compat_res_2.resolution_digest)
        self.assertEqual(
            CapabilityResolution.from_json(compat_res.to_json()),
            compat_res,
        )

        bad_payload = compat_res.to_dict()
        bad_payload["resolution_digest"] = "f" * 64
        with self.assertRaises(CapabilityResolutionDigestMismatchError) as ctx:
            CapabilityResolution.from_dict(bad_payload)
        self.assertEqual(ctx.exception.code, "RAPID1109")


class SymlinkAndPathContainmentTests(unittest.TestCase):
    def test_symlinked_harnesses_dir_profile_or_lock_file_is_rejected_with_rapid1105(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside_tmp:
            root = Path(tmp)
            outside = Path(outside_tmp)
            rapid_dir = root / ".rapid-os"
            rapid_dir.mkdir(parents=True, exist_ok=True)

            outside_profile = outside / "codex.json"
            outside_profile.write_text(
                BUILTIN_HARNESS_PROFILES["codex"].to_json(indent=2),
                encoding="utf-8",
            )
            harnesses_dir = rapid_dir / "harnesses"
            harnesses_dir.mkdir(parents=True, exist_ok=True)
            symlink_profile = harnesses_dir / "codex.json"
            try:
                os.symlink(outside_profile, symlink_profile)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"Symlinks not available in this environment: {exc}")

            registry = HarnessRegistry(root, rapid_dir)
            with self.assertRaises(UnsafeHarnessPathError) as ctx:
                registry.resolve_active_profile("codex")
            self.assertEqual(ctx.exception.code, "RAPID1105")

            report = validate_harness_registry(rapid_dir, root)
            self.assertIn(
                "RAPID1105",
                [d.code for d in report.diagnostics if d.level == ERROR],
            )


class EndToEndHarnessCapabilityFlowsTests(unittest.TestCase):
    def _run_cli(self, root: Path, argv: list[str]) -> tuple[int, str, str]:
        rapid_dir = root / ".rapid-os"
        config_file = rapid_dir / "config.json"
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        exit_code = 0
        with (
            patch.object(cli_main, "CURRENT_DIR", root),
            patch.object(cli_main, "PROJECT_RAPID_DIR", rapid_dir),
            patch.object(cli_main, "CONFIG_FILE", config_file),
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            try:
                result = cli_main.main(argv)
                if isinstance(result, int):
                    exit_code = result
            except SystemExit as exc:
                exit_code = int(exc.code) if exc.code is not None else 0
        return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def _create_ready_spec(
        self,
        root: Path,
        *,
        spec_id: str = "billing-update",
        affected_paths: tuple[str, ...] = ("src/billing/service.py",),
        tags: tuple[str, ...] = ("billing",),
        tasks: tuple[str, ...] = ("Update billing calculation",),
    ) -> None:
        rapid_dir = root / ".rapid-os"
        standards_dir = rapid_dir / "standards"
        standards_dir.mkdir(parents=True, exist_ok=True)
        for fname, title in (
            ("business.md", "Business Rules"),
            ("tech-stack.md", "Tech Stack"),
            ("topology.md", "Topology"),
            ("security.md", "Security"),
            ("coding-rules.md", "Coding Rules"),
        ):
            target = standards_dir / fname
            if not target.exists():
                target.write_text(f"# {title}\n- Deterministic rule.\n", encoding="utf-8")
        config_file = rapid_dir / "config.json"
        if not config_file.exists():
            config_file.write_text(
                json.dumps({"tools": ["cursor"]}, indent=2) + "\n",
                encoding="utf-8",
            )
        spec_reg = SpecRegistry(root, rapid_dir)
        rec = spec_reg.create(
            spec_id=spec_id,
            title=f"Spec {spec_id}",
            mode=SpecMode.FEATURE,
            status=SpecStatus.READY,
            business_objective="Deliver billing update safely",
            problem_statement="Need deterministic billing update",
            scope=("Update billing module",),
            out_of_scope=("Legacy v1",),
            actors_users=("Customer",),
            main_flow=("Compute invoice",),
            edge_cases=("Zero balance",),
            business_rules=("Never negative total",),
            technical_constraints=("Deterministic math",),
            affected_paths=affected_paths,
            data_impact="none",
            acceptance_criteria=("Unit tests pass",),
            testing_strategy=("Run unit suite",),
            implementation_tasks=tasks,
            tags=tags,
        )
        if rec.status != SpecStatus.READY:
            spec_reg.set_status(rec.id, SpecStatus.READY)

    def test_e2e_1_builtin_and_project_capability_resolution_without_run_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._create_ready_spec(root, spec_id="billing-update")

            code, out, err = self._run_cli(
                root,
                [
                    "run",
                    "create",
                    "--spec",
                    "billing-update",
                    "--id",
                    "run-billing",
                    "--harness",
                    "codex",
                    "--json",
                ],
            )
            self.assertEqual(code, 0, err)

            run_dir = root / ".rapid-os" / "runs" / "run-billing"
            tracked_artifacts = (
                run_dir / "run.json",
                run_dir / "contract.json",
                run_dir / "context.md",
                run_dir / "context-manifest.json",
                run_dir / "states" / "0001.json",
            )
            before_bytes = {p.name: p.read_bytes() for p in tracked_artifacts}

            # Resolve against conservative builtin:codex -> UNRESOLVED
            code, out, err = self._run_cli(
                root,
                ["harness", "resolve", "--run", "run-billing", "--json"],
            )
            self.assertEqual(code, 0, err)
            res_payload = json.loads(out)
            self.assertEqual(res_payload["status"], "unresolved")
            self.assertEqual(res_payload["profile_source"], "builtin:codex")
            self.assertIn("repository.write", res_payload["unknown"])
            self.assertIn("tests.execute", res_payload["unknown"])

            # --require-compatible fails with exit code 1 and RAPID1110
            code, out, err = self._run_cli(
                root,
                [
                    "harness",
                    "resolve",
                    "--run",
                    "run-billing",
                    "--require-compatible",
                ],
            )
            self.assertEqual(code, 1)
            self.assertIn("RAPID1110", err)

            # Initialize project profile for codex and declare required capabilities supported
            code, out, err = self._run_cli(
                root,
                ["harness", "init", "codex", "--json"],
            )
            self.assertEqual(code, 0, err)
            init_payload = json.loads(out)
            self.assertEqual(
                init_payload["source"],
                ".rapid-os/harnesses/codex.json",
            )

            registry = HarnessRegistry(root, root / ".rapid-os")
            registry.write_project_profile(
                _profile_with_overrides(
                    "codex",
                    {
                        "context.consume": CapabilitySupportStatus.SUPPORTED,
                        "repository.read": CapabilitySupportStatus.SUPPORTED,
                        "repository.write": CapabilitySupportStatus.SUPPORTED,
                        "workspace.current": CapabilitySupportStatus.SUPPORTED,
                        "tests.execute": CapabilitySupportStatus.SUPPORTED,
                    },
                )
            )

            # Live resolution now reports COMPATIBLE and --require-compatible exits 0
            code, out, err = self._run_cli(
                root,
                [
                    "harness",
                    "resolve",
                    "--run",
                    "run-billing",
                    "--require-compatible",
                    "--json",
                ],
            )
            self.assertEqual(code, 0, err)
            compat_payload = json.loads(out)
            self.assertEqual(compat_payload["status"], "compatible")
            self.assertEqual(
                compat_payload["profile_source"],
                ".rapid-os/harnesses/codex.json",
            )

            # Phase 4 Run artifacts were NEVER mutated
            after_bytes = {p.name: p.read_bytes() for p in tracked_artifacts}
            self.assertEqual(before_bytes, after_bytes)

    def test_e2e_2_custom_harness_creation_run_and_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._create_ready_spec(
                root,
                spec_id="auth-migration",
                affected_paths=("src/auth/login.py", "migrations/001_auth.sql"),
                tags=("auth", "security"),
            )

            # Explicitly write custom harness profile 'my-agent'
            registry = HarnessRegistry(root, root / ".rapid-os")
            registry.write_project_profile(
                _profile_with_overrides(
                    "my-agent",
                    {
                        "context.consume": CapabilitySupportStatus.SUPPORTED,
                        "repository.read": CapabilitySupportStatus.SUPPORTED,
                        "repository.write": CapabilitySupportStatus.SUPPORTED,
                        "workspace.isolated": CapabilitySupportStatus.SUPPORTED,
                        "tests.execute": CapabilitySupportStatus.SUPPORTED,
                    },
                )
            )

            # rapid harness show my-agent works
            code, out, err = self._run_cli(
                root,
                ["harness", "show", "my-agent", "--json"],
            )
            self.assertEqual(code, 0, err)
            show_payload = json.loads(out)
            self.assertEqual(show_payload["id"], "my-agent")
            self.assertEqual(
                show_payload["source"],
                ".rapid-os/harnesses/my-agent.json",
            )

            # rapid run create --harness my-agent works
            code, out, err = self._run_cli(
                root,
                [
                    "run",
                    "create",
                    "--spec",
                    "auth-migration",
                    "--id",
                    "run-custom",
                    "--harness",
                    "my-agent",
                    "--json",
                ],
            )
            self.assertEqual(code, 0, err)
            run_payload = json.loads(out)
            self.assertEqual(run_payload["harness"], "my-agent")
            self.assertEqual(run_payload["workspace"], "isolated_required")

            # rapid harness resolve --run run-custom works and is COMPATIBLE
            code, out, err = self._run_cli(
                root,
                [
                    "harness",
                    "resolve",
                    "--run",
                    "run-custom",
                    "--require-compatible",
                    "--json",
                ],
            )
            self.assertEqual(code, 0, err)
            res_payload = json.loads(out)
            self.assertEqual(res_payload["status"], "compatible")
            self.assertIn("workspace.isolated", res_payload["satisfied"])

    def test_e2e_3_live_vs_locked_resolution_reproducibility_and_stale_lock_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._create_ready_spec(root, spec_id="acme-feature")

            registry = HarnessRegistry(root, root / ".rapid-os")
            # Profile v1: all required capabilities + mcp.invoke supported
            registry.write_project_profile(
                _profile_with_overrides(
                    "codex",
                    {
                        "context.consume": CapabilitySupportStatus.SUPPORTED,
                        "repository.read": CapabilitySupportStatus.SUPPORTED,
                        "repository.write": CapabilitySupportStatus.SUPPORTED,
                        "workspace.current": CapabilitySupportStatus.SUPPORTED,
                        "tests.execute": CapabilitySupportStatus.SUPPORTED,
                        "mcp.invoke": CapabilitySupportStatus.SUPPORTED,
                    },
                )
            )

            code, out, err = self._run_cli(
                root,
                [
                    "run",
                    "create",
                    "--spec",
                    "acme-feature",
                    "--id",
                    "run-acme",
                    "--harness",
                    "codex",
                    "--json",
                ],
            )
            self.assertEqual(code, 0, err)

            # Lock active profiles (v1) — deterministic byte-for-byte across repeated calls
            code, lock_out_1, err = self._run_cli(root, ["harness", "lock", "--json"])
            self.assertEqual(code, 0, err)
            lock_file = root / ".rapid-os" / "capabilities.lock"
            lock_bytes_1 = lock_file.read_bytes()

            code, lock_out_2, err = self._run_cli(root, ["harness", "lock", "--json"])
            self.assertEqual(code, 0, err)
            lock_bytes_2 = lock_file.read_bytes()
            self.assertEqual(lock_bytes_1, lock_bytes_2)

            # Edit live profile -> v2 (repository.write = unsupported)
            registry.write_project_profile(
                _profile_with_overrides(
                    "codex",
                    {
                        "context.consume": CapabilitySupportStatus.SUPPORTED,
                        "repository.read": CapabilitySupportStatus.SUPPORTED,
                        "repository.write": CapabilitySupportStatus.UNSUPPORTED,
                        "workspace.current": CapabilitySupportStatus.SUPPORTED,
                        "tests.execute": CapabilitySupportStatus.SUPPORTED,
                    },
                )
            )

            # Live resolution uses v2 -> INCOMPATIBLE
            code, live_out, err = self._run_cli(
                root,
                ["harness", "resolve", "--run", "run-acme", "--json"],
            )
            self.assertEqual(code, 0, err)
            live_res = json.loads(live_out)
            self.assertEqual(live_res["status"], "incompatible")
            self.assertEqual(live_res["missing"], ["repository.write"])

            # Locked resolution uses v1 from capabilities.lock -> COMPATIBLE
            code, locked_out, err = self._run_cli(
                root,
                [
                    "harness",
                    "resolve",
                    "--run",
                    "run-acme",
                    "--locked",
                    "--require-compatible",
                    "--json",
                ],
            )
            self.assertEqual(code, 0, err)
            locked_res = json.loads(locked_out)
            self.assertEqual(locked_res["status"], "compatible")
            self.assertEqual(locked_res["missing"], [])

            # Same contract_digest, different profile_digest and resolution_digest
            self.assertEqual(
                live_res["contract_digest"],
                locked_res["contract_digest"],
            )
            self.assertNotEqual(
                live_res["profile_digest"],
                locked_res["profile_digest"],
            )
            self.assertNotEqual(
                live_res["resolution_digest"],
                locked_res["resolution_digest"],
            )

            # validate_capability_lock emits RAPID1112 WARNING (stale lock) without mutating lock
            drift_report = validate_capability_lock(root / ".rapid-os", root)
            self.assertIn(
                "RAPID1112",
                [d.code for d in drift_report.diagnostics if d.level == WARNING],
            )
            self.assertEqual(lock_file.read_bytes(), lock_bytes_1)

    def test_validation_product_truth_detects_all_profile_and_lock_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rapid_dir = root / ".rapid-os"
            harnesses_dir = rapid_dir / "harnesses"
            harnesses_dir.mkdir(parents=True, exist_ok=True)

            # 1. Profile id != filename -> RAPID1104
            (harnesses_dir / "codex.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "claude",
                        "capabilities": [],
                    }
                ),
                encoding="utf-8",
            )
            rep_id = validate_harness_registry(rapid_dir, root)
            self.assertIn(
                "RAPID1104",
                [d.code for d in rep_id.diagnostics if d.level == ERROR],
            )

            # 2. Unknown capability -> RAPID1101
            (harnesses_dir / "codex.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "codex",
                        "capabilities": [
                            {
                                "capability_id": "unknown.cap",
                                "status": "supported",
                                "reason": "bad",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            rep_cap = validate_harness_registry(rapid_dir, root)
            self.assertIn(
                "RAPID1101",
                [d.code for d in rep_cap.diagnostics if d.level == ERROR],
            )

            # 3. Invalid status -> RAPID1106
            (harnesses_dir / "codex.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "codex",
                        "capabilities": [
                            {
                                "capability_id": "context.consume",
                                "status": "maybe",
                                "reason": "bad status",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            rep_status = validate_harness_registry(rapid_dir, root)
            self.assertIn(
                "RAPID1106",
                [d.code for d in rep_status.diagnostics if d.level == ERROR],
            )

            # 4. Digest drift -> RAPID1102
            (harnesses_dir / "codex.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": "codex",
                        "capabilities": [],
                        "content_digest": "0" * 64,
                    }
                ),
                encoding="utf-8",
            )
            rep_digest = validate_harness_registry(rapid_dir, root)
            self.assertIn(
                "RAPID1102",
                [d.code for d in rep_digest.diagnostics if d.level == ERROR],
            )

            # 5. Corrupt capabilities.lock -> RAPID1111
            (rapid_dir / "capabilities.lock").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profiles": [],
                        "content_digest": "0" * 64,
                    }
                ),
                encoding="utf-8",
            )
            rep_lock = validate_capability_lock(rapid_dir, root)
            self.assertIn(
                "RAPID1111",
                [d.code for d in rep_lock.diagnostics if d.level == ERROR],
            )

    def test_cli_list_show_and_error_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._create_ready_spec(root, spec_id="cli-check")

            # harness list text + json
            code, out_txt, err = self._run_cli(root, ["harness", "list"])
            self.assertEqual(code, 0, err)
            self.assertIn("builtin:codex", out_txt)

            code, out_json, err = self._run_cli(root, ["harness", "list", "--json"])
            self.assertEqual(code, 0, err)
            list_payload = json.loads(out_json)
            self.assertEqual(
                [p["id"] for p in list_payload["profiles"]],
                list(BUILTIN_HARNESS_IDS),
            )

            # harness show text + json
            code, show_txt, err = self._run_cli(root, ["harness", "show", "codex"])
            self.assertEqual(code, 0, err)
            self.assertIn("builtin:codex", show_txt)

            # harness show unknown -> RAPID1103
            code, _, err = self._run_cli(root, ["harness", "show", "nonexistent"])
            self.assertEqual(code, 1)
            self.assertIn("RAPID1103", err)

            # harness init custom non-builtin -> RAPID1103
            code, _, err = self._run_cli(root, ["harness", "init", "custom-no-builtin"])
            self.assertEqual(code, 1)
            self.assertIn("RAPID1103", err)

            # harness resolve --locked without capabilities.lock -> RAPID1111
            self._run_cli(
                root,
                [
                    "run",
                    "create",
                    "--spec",
                    "cli-check",
                    "--id",
                    "run-cli",
                    "--harness",
                    "codex",
                ],
            )
            code, _, err = self._run_cli(
                root,
                ["harness", "resolve", "--run", "run-cli", "--locked"],
            )
            self.assertEqual(code, 1)
            self.assertIn("RAPID1111", err)

            # unresolved + --require-compatible -> exit 1 + RAPID1110
            code, _, err = self._run_cli(
                root,
                [
                    "harness",
                    "resolve",
                    "--run",
                    "run-cli",
                    "--require-compatible",
                ],
            )
            self.assertEqual(code, 1)
            self.assertIn("RAPID1110", err)

            # --require mcp.invoke (cli.require) & --require context.consume (does not replace contract.context)
            code, req_out, err = self._run_cli(
                root,
                [
                    "harness",
                    "resolve",
                    "--run",
                    "run-cli",
                    "--require",
                    "mcp.invoke",
                    "--require",
                    "context.consume",
                    "--json",
                ],
            )
            self.assertEqual(code, 0, err)
            req_res = json.loads(req_out)
            req_sources = {
                item["capability_id"]: item["source"]
                for item in req_res["requirements"]
            }
            self.assertEqual(req_sources["context.consume"], "contract.context")
            self.assertEqual(req_sources["repository.read"], "contract.repository")
            self.assertEqual(req_sources["repository.write"], "contract.tasks")
            self.assertEqual(req_sources["workspace.current"], "contract.workspace")
            self.assertEqual(req_sources["tests.execute"], "contract.gate.tests")
            self.assertEqual(req_sources["mcp.invoke"], "cli.require")

            # incompatible + --require-compatible -> exit 1 + RAPID1110
            registry = HarnessRegistry(root, root / ".rapid-os")
            registry.write_project_profile(
                _profile_with_overrides(
                    "codex",
                    {
                        "context.consume": CapabilitySupportStatus.SUPPORTED,
                        "repository.read": CapabilitySupportStatus.SUPPORTED,
                        "repository.write": CapabilitySupportStatus.UNSUPPORTED,
                        "workspace.current": CapabilitySupportStatus.SUPPORTED,
                        "tests.execute": CapabilitySupportStatus.SUPPORTED,
                    },
                )
            )
            code, _, err = self._run_cli(
                root,
                [
                    "harness",
                    "resolve",
                    "--run",
                    "run-cli",
                    "--require-compatible",
                ],
            )
            self.assertEqual(code, 1)
            self.assertIn("RAPID1110", err)

            # rapid harness resolve --harness ... is rejected by the CLI parser
            parser = cli_main.create_parser()
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as parser_ctx:
                    parser.parse_args(
                        [
                            "harness",
                            "resolve",
                            "--run",
                            "run-cli",
                            "--harness",
                            "claude",
                        ]
                    )
            self.assertNotEqual(parser_ctx.exception.code, 0)

            # Contract vs profile harness mismatch -> RAPID1108
            contract = _sample_contract(harness="codex")
            claude_profile = BUILTIN_HARNESS_PROFILES["claude"]
            with self.assertRaises(InvalidCapabilityResolutionError) as ctx:
                CapabilityResolver.resolve(
                    contract,
                    claude_profile,
                    profile_source="builtin:claude",
                )
            self.assertEqual(ctx.exception.code, "RAPID1108")


if __name__ == "__main__":
    unittest.main()


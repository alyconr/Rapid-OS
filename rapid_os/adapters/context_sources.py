from dataclasses import dataclass
from pathlib import Path

from rapid_os.adapters.project_snapshot import (
    read_project_snapshot,
    resolve_project_snapshot_path,
)
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.core.filesystem import ensure_path_within_root
from rapid_os.domain.context import (
    ContextPriority,
    ContextRequest,
    ContextSource,
    ContextSourceKind,
    build_project_intelligence_source,
)
from rapid_os.domain.project import ProjectModel, normalize_evidence_path
from rapid_os.domain.scanner import build_project_model
from rapid_os.domain.specs import SpecRegistryError, SpecStatus


LEGACY_SINGLETON_SPEC_IDS = frozenset(
    {
        "spec.scope",
        "spec.tasks",
        "spec.acceptance",
    }
)


@dataclass(frozen=True)
class KnownContextSourceSpec:
    id: str
    kind: ContextSourceKind
    relative_path: str
    priority: ContextPriority
    tags: tuple[str, ...]
    under_rapid_dir: bool = False


KNOWN_CONTEXT_SOURCE_SPECS: tuple[KnownContextSourceSpec, ...] = (
    KnownContextSourceSpec(
        id="standard.security",
        kind=ContextSourceKind.SECURITY,
        relative_path="standards/security.md",
        priority=ContextPriority.CRITICAL,
        tags=("security", "backend", "api", "auth"),
        under_rapid_dir=True,
    ),
    KnownContextSourceSpec(
        id="standard.business",
        kind=ContextSourceKind.BUSINESS,
        relative_path="standards/business.md",
        priority=ContextPriority.HIGH,
        tags=("business", "domain", "product"),
        under_rapid_dir=True,
    ),
    KnownContextSourceSpec(
        id="standard.architecture",
        kind=ContextSourceKind.ARCHITECTURE,
        relative_path="standards/architecture.md",
        priority=ContextPriority.HIGH,
        tags=("architecture", "backend", "frontend"),
        under_rapid_dir=True,
    ),
    KnownContextSourceSpec(
        id="standard.topology",
        kind=ContextSourceKind.TOPOLOGY,
        relative_path="standards/topology.md",
        priority=ContextPriority.HIGH,
        tags=("architecture", "topology", "backend", "frontend"),
        under_rapid_dir=True,
    ),
    KnownContextSourceSpec(
        id="standard.tech-stack",
        kind=ContextSourceKind.TECH_STACK,
        relative_path="standards/tech-stack.md",
        priority=ContextPriority.HIGH,
        tags=("stack", "backend", "frontend", "database", "testing"),
        under_rapid_dir=True,
    ),
    KnownContextSourceSpec(
        id="standard.coding-rules",
        kind=ContextSourceKind.CODING_RULES,
        relative_path="standards/coding-rules.md",
        priority=ContextPriority.MEDIUM,
        tags=("coding-rules", "testing", "quality"),
        under_rapid_dir=True,
    ),
    KnownContextSourceSpec(
        id="standard.design",
        kind=ContextSourceKind.DESIGN,
        relative_path="standards/design.md",
        priority=ContextPriority.LOW,
        tags=("design", "frontend", "ui"),
        under_rapid_dir=True,
    ),
    KnownContextSourceSpec(
        id="spec.scope",
        kind=ContextSourceKind.SPEC,
        relative_path="SPECS.md",
        priority=ContextPriority.HIGH,
        tags=("spec", "feature", "scope"),
        under_rapid_dir=False,
    ),
    KnownContextSourceSpec(
        id="spec.tasks",
        kind=ContextSourceKind.TASKS,
        relative_path="TASKS.md",
        priority=ContextPriority.MEDIUM,
        tags=("tasks", "feature", "scope"),
        under_rapid_dir=False,
    ),
    KnownContextSourceSpec(
        id="spec.acceptance",
        kind=ContextSourceKind.ACCEPTANCE,
        relative_path="ACCEPTANCE.md",
        priority=ContextPriority.MEDIUM,
        tags=("acceptance", "testing", "verification"),
        under_rapid_dir=False,
    ),
    KnownContextSourceSpec(
        id="reference.vision",
        kind=ContextSourceKind.REFERENCE,
        relative_path="references/VISION_CONTEXT.md",
        priority=ContextPriority.LOW,
        tags=("vision", "design", "frontend", "ui"),
        under_rapid_dir=False,
    ),
)


@dataclass(frozen=True)
class ContextSourceLoadError:
    source_id: str
    path: Path | str
    message: str
    code: str = "RAPID704"

    @property
    def error(self) -> str:
        return self.message


@dataclass(frozen=True)
class ContextDiscoveryResult:
    sources: tuple[ContextSource, ...]
    project_model: ProjectModel | None
    load_errors: tuple[ContextSourceLoadError, ...] = ()


class ContextSourceLoader:
    """Discover and safely load known project context sources without resolving relevance."""

    def _load_selected_registry_spec_sources(
        self,
        root: Path,
        rapid_dir: Path,
        spec_id: str,
        spec_revision: int | None,
    ) -> tuple[tuple[ContextSource, ...], tuple[ContextSourceLoadError, ...]]:
        try:
            registry = SpecRegistry(root, rapid_dir)
            record = registry.get(spec_id)
            if record.status != SpecStatus.READY:
                return (
                    (),
                    (
                        ContextSourceLoadError(
                            source_id=f"spec.{spec_id}",
                            path=f".rapid-os/specs/{spec_id}/spec.json",
                            message=(
                                f"Spec '{spec_id}' has status '{record.status.value}'; "
                                "only 'ready' specs can be compiled into operational context."
                            ),
                            code="RAPID805",
                        ),
                    ),
                )
            rev = registry.get_revision(spec_id, revision=spec_revision)
            artifacts = registry.get_artifact_contents(
                spec_id,
                revision=rev.revision,
            )
        except SpecRegistryError as exc:
            err_path = (
                str(exc.path)
                if exc.path is not None
                else f".rapid-os/specs/{spec_id}"
            )
            return (
                (),
                (
                    ContextSourceLoadError(
                        source_id=f"spec.{spec_id}",
                        path=err_path,
                        message=str(exc),
                        code=exc.code,
                    ),
                ),
            )
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            return (
                (),
                (
                    ContextSourceLoadError(
                        source_id=f"spec.{spec_id}",
                        path=f".rapid-os/specs/{spec_id}",
                        message=str(exc),
                        code="RAPID808",
                    ),
                ),
            )

        spec_sources: list[ContextSource] = []
        mapping = (
            (
                "requirements.md",
                f"spec.{record.id}.requirements",
                ContextSourceKind.SPEC,
                ContextPriority.HIGH,
                ("spec", "feature", "scope", *rev.tags),
            ),
            (
                "tasks.md",
                f"spec.{record.id}.tasks",
                ContextSourceKind.TASKS,
                ContextPriority.MEDIUM,
                ("tasks", "feature", "scope", *rev.tags),
            ),
            (
                "acceptance.md",
                f"spec.{record.id}.acceptance",
                ContextSourceKind.ACCEPTANCE,
                ContextPriority.MEDIUM,
                ("acceptance", "testing", "verification", *rev.tags),
            ),
        )
        for filename, source_id, kind, priority, tags in mapping:
            portable_path, raw_text = artifacts[filename]
            if not raw_text.strip():
                continue
            spec_sources.append(
                ContextSource(
                    id=source_id,
                    kind=kind,
                    content=raw_text.strip(),
                    path=portable_path,
                    priority=priority,
                    required=False,
                    tags=tags,
                    provenance=portable_path,
                )
            )
        return tuple(spec_sources), ()

    def load(
        self,
        project_root: Path,
        project_rapid_dir: Path | None = None,
        *,
        project_model: ProjectModel | None = None,
        request: ContextRequest | None = None,
        include_project_intelligence: bool = True,
    ) -> ContextDiscoveryResult:
        root = Path(project_root)
        rapid_dir = (
            Path(project_rapid_dir)
            if project_rapid_dir is not None
            else (root / ".rapid-os")
        )

        loaded_sources: list[ContextSource] = []
        load_errors: list[ContextSourceLoadError] = []

        use_registry_spec = bool(request is not None and request.spec_id is not None)

        for spec in KNOWN_CONTEXT_SOURCE_SPECS:
            if use_registry_spec and spec.id in LEGACY_SINGLETON_SPEC_IDS:
                continue

            base_dir = rapid_dir if spec.under_rapid_dir else root
            candidate = base_dir / spec.relative_path
            if not candidate.exists():
                continue

            try:
                contained = ensure_path_within_root(root, candidate)
            except ValueError as exc:
                load_errors.append(
                    ContextSourceLoadError(
                        source_id=spec.id,
                        path=spec.relative_path,
                        message=str(exc),
                    )
                )
                continue

            portable_path = normalize_evidence_path(contained, root)
            if not contained.is_file():
                load_errors.append(
                    ContextSourceLoadError(
                        source_id=spec.id,
                        path=portable_path,
                        message=f"Context source '{portable_path}' is not a regular file.",
                    )
                )
                continue

            try:
                raw_text = contained.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                load_errors.append(
                    ContextSourceLoadError(
                        source_id=spec.id,
                        path=portable_path,
                        message=f"Could not read context source '{portable_path}' as UTF-8: {exc}",
                    )
                )
                continue

            if not raw_text.strip():
                continue

            loaded_sources.append(
                ContextSource(
                    id=spec.id,
                    kind=spec.kind,
                    content=raw_text.strip(),
                    path=portable_path,
                    priority=spec.priority,
                    required=False,
                    tags=spec.tags,
                    provenance=portable_path,
                )
            )

        if use_registry_spec and request is not None and request.spec_id is not None:
            reg_sources, reg_errors = self._load_selected_registry_spec_sources(
                root=root,
                rapid_dir=rapid_dir,
                spec_id=request.spec_id,
                spec_revision=request.spec_revision,
            )
            loaded_sources.extend(reg_sources)
            load_errors.extend(reg_errors)

        resolved_model = project_model
        pi_provenance = "scan:live"
        if include_project_intelligence and resolved_model is None:
            snapshot_path = resolve_project_snapshot_path(rapid_dir)
            if snapshot_path.exists():
                try:
                    contained_snapshot = ensure_path_within_root(root, snapshot_path)
                    portable_snapshot = normalize_evidence_path(contained_snapshot, root)
                except ValueError as exc:
                    load_errors.append(
                        ContextSourceLoadError(
                            source_id="project.intelligence",
                            path=".rapid-os/project.json",
                            message=str(exc),
                        )
                    )
                else:
                    if not contained_snapshot.is_file():
                        load_errors.append(
                            ContextSourceLoadError(
                                source_id="project.intelligence",
                                path=portable_snapshot,
                                message=f"Project intelligence snapshot '{portable_snapshot}' is not a regular file.",
                            )
                        )
                    else:
                        try:
                            resolved_model = read_project_snapshot(rapid_dir, root)
                            pi_provenance = f"snapshot:{portable_snapshot}"
                        except (OSError, UnicodeDecodeError, ValueError) as exc:
                            load_errors.append(
                                ContextSourceLoadError(
                                    source_id="project.intelligence",
                                    path=portable_snapshot,
                                    message=f"Invalid project intelligence snapshot '{portable_snapshot}': {exc}",
                                )
                            )
            else:
                resolved_model = build_project_model(root)
                pi_provenance = "scan:live"

        if include_project_intelligence and resolved_model is not None:
            pi_source = build_project_intelligence_source(
                resolved_model,
                request=request,
                provenance=pi_provenance,
            )
            if pi_source is not None:
                loaded_sources.append(pi_source)

        return ContextDiscoveryResult(
            sources=tuple(loaded_sources),
            project_model=resolved_model,
            load_errors=tuple(load_errors),
        )


def discover_context_sources(
    project_root: Path,
    project_rapid_dir: Path | None = None,
    *,
    project_model: ProjectModel | None = None,
    request: ContextRequest | None = None,
    include_project_intelligence: bool = True,
) -> tuple[ContextSource, ...]:
    """Convenience helper returning discovered `ContextSource` items for `project_root`."""
    loader = ContextSourceLoader()
    result = loader.load(
        project_root=project_root,
        project_rapid_dir=project_rapid_dir,
        project_model=project_model,
        request=request,
        include_project_intelligence=include_project_intelligence,
    )
    if result.load_errors:
        first = result.load_errors[0]
        raise ValueError(first.message)
    return result.sources

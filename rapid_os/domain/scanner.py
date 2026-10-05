import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from rapid_os.domain.project import (
    FACT_CATEGORIES,
    PROJECT_MODEL_SCHEMA_VERSION,
    Confidence,
    Evidence,
    ProjectFact,
    ProjectModel,
    SourceType,
    canonical_detector_id,
    normalize_facts,
)


ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CONFIDENCE_HIGH = Confidence.HIGH.value
CONFIDENCE_MEDIUM = Confidence.MEDIUM.value
CONFIDENCE_LOW = Confidence.LOW.value

IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".docusaurus",
    "coverage",
    ".rapid-os",
}

DETECTION_CATEGORIES = FACT_CATEGORIES

# Legacy alias: Detection is ProjectFact.
Detection = ProjectFact


@dataclass(frozen=True, init=False)
class ProjectScan:
    """Legacy compatibility facade wrapping the canonical `ProjectModel` without duplicating state."""

    model: ProjectModel

    def __init__(
        self,
        root: Path | ProjectModel = Path("."),
        detections: tuple[ProjectFact, ...] = (),
        *,
        model: ProjectModel | None = None,
    ):
        if isinstance(root, ProjectModel):
            resolved_model = root
        elif model is not None:
            resolved_model = model
        else:
            resolved_model = ProjectModel(
                schema_version=PROJECT_MODEL_SCHEMA_VERSION,
                root=Path(root),
                facts=tuple(detections),
            )
        object.__setattr__(self, "model", resolved_model)

    @classmethod
    def from_model(cls, model: ProjectModel) -> "ProjectScan":
        return cls(model=model)

    @property
    def schema_version(self) -> int:
        return self.model.schema_version

    @property
    def root(self) -> Path:
        return self.model.root

    @property
    def facts(self) -> tuple[ProjectFact, ...]:
        return self.model.facts

    @property
    def detections(self) -> tuple[ProjectFact, ...]:
        return self.model.facts

    def to_model(self) -> ProjectModel:
        return self.model

    def facts_for(self, category: str) -> tuple[ProjectFact, ...]:
        return self.model.facts_for(category)

    def by_category(self, category: str) -> tuple[ProjectFact, ...]:
        return self.model.facts_for(category)

    def values(self, category: str) -> tuple[str, ...]:
        return self.model.values(category)

    def has(
        self,
        category: str,
        value: str | None = None,
    ) -> bool:
        return self.model.has(category, value)

    def to_dict(self) -> dict[str, object]:
        return self.model.to_dict()

    def to_json(self, *, indent: int = 2) -> str:
        return self.model.to_json(indent=indent)


@dataclass(frozen=True)
class InitSuggestion:
    field: str
    value: str
    confidence: Confidence | str
    reason: str
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "confidence", Confidence.coerce(self.confidence))
        object.__setattr__(self, "evidence", tuple(self.evidence or ()))

    def to_dict(self):
        return {
            "field": self.field,
            "value": self.value,
            "confidence": self.confidence.value,
            "reason": self.reason,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class InitSuggestions:
    stack: InitSuggestion | None = None
    topology: InitSuggestion | None = None

    def has_any(self):
        return self.stack is not None or self.topology is not None

    def to_dict(self):
        return {
            "stack": self.stack.to_dict() if self.stack else None,
            "topology": self.topology.to_dict() if self.topology else None,
        }


def build_project_model(project_dir: Path) -> ProjectModel:
    """Run the Project Intelligence pipeline and return the canonical `ProjectModel`."""
    root = Path(project_dir)
    files = _collect_files(root)
    package_manifests = _load_package_manifests(files, root)
    raw_facts = _run_detectors(files, root, package_manifests)
    normalized_facts = normalize_facts(raw_facts, root=root)
    return ProjectModel(
        schema_version=PROJECT_MODEL_SCHEMA_VERSION,
        root=root,
        facts=normalized_facts,
    )


def scan_project(project_dir: Path) -> ProjectScan:
    """Scan `project_dir` and return a `ProjectScan` facade backed by `ProjectModel`."""
    model = build_project_model(project_dir)
    return ProjectScan.from_model(model)


def _run_detectors(files, root: Path, package_manifests) -> list[ProjectFact]:
    text_cache: dict[Path, str] = {}
    facts: list[ProjectFact] = []
    facts.extend(_detect_languages(files, root, package_manifests))
    facts.extend(_detect_frameworks(files, root, package_manifests, text_cache))
    facts.extend(_detect_package_managers(files, root))
    facts.extend(_detect_docker(files, root))
    facts.extend(_detect_testing(files, root, package_manifests))
    facts.extend(_detect_monorepo(files, root, package_manifests))
    facts.extend(_detect_databases(files, root, package_manifests, text_cache))
    facts.extend(_detect_deploy_providers(files, root))
    return facts


def suggest_init_choices(scan: ProjectModel | ProjectScan) -> InitSuggestions:
    model = scan.to_model() if isinstance(scan, ProjectScan) else scan
    framework_values = set(model.values("framework"))
    language_values = set(model.values("language"))
    database_values = set(model.values("database"))

    app_frameworks = framework_values & {
        "docusaurus",
        "nextjs",
        "fastapi",
    }
    has_conflict = len(app_frameworks) > 1

    stack = None
    topology = None

    if not has_conflict and model.has("framework", "docusaurus"):
        evidence = _first_evidence(model, "framework", "docusaurus")
        stack = InitSuggestion(
            "stack",
            "docs-modern",
            Confidence.HIGH,
            "Docusaurus project detected.",
            evidence,
        )
        topology = InitSuggestion(
            "topology",
            "doc-site",
            Confidence.HIGH,
            "Docusaurus projects match the doc-site topology.",
            evidence,
        )
    elif not has_conflict and model.has("framework", "nextjs"):
        evidence = _first_evidence(model, "framework", "nextjs")
        stack = InitSuggestion(
            "stack",
            "web-modern",
            Confidence.HIGH,
            "Next.js project detected.",
            evidence,
        )
        if "supabase" in database_values:
            topology = InitSuggestion(
                "topology",
                "fullstack-baas",
                Confidence.MEDIUM,
                "Next.js and Supabase hints were detected.",
                evidence + _first_evidence(model, "database", "supabase"),
            )
    elif not has_conflict and model.has("framework", "fastapi"):
        evidence = _first_evidence(model, "framework", "fastapi")
        if "python" in language_values:
            stack = InitSuggestion(
                "stack",
                "python-ai",
                Confidence.HIGH,
                "Python and FastAPI project detected.",
                evidence,
            )
            topology = InitSuggestion(
                "topology",
                "fullstack-separated",
                Confidence.MEDIUM,
                "FastAPI usually acts as a separate backend service.",
                evidence,
            )
    elif not has_conflict and _has_node_ai_hints(model):
        evidence = (
            _first_evidence(model, "framework", "langchain")
            or _first_evidence(model, "framework", "langgraph")
            or _first_evidence(model, "framework", "crewai")
        )
        stack = InitSuggestion(
            "stack",
            "nodejs-ai",
            Confidence.MEDIUM,
            "Node.js AI framework hints were detected.",
            evidence,
        )
    elif not has_conflict and _has_frontend_without_backend(model):
        evidence = (
            _first_evidence(model, "framework", "react")
            or _first_evidence(model, "framework", "vite")
        )
        topology = InitSuggestion(
            "topology",
            "front-end-only",
            Confidence.MEDIUM,
            "Frontend framework detected without backend or database hints.",
            evidence,
        )

    return InitSuggestions(stack=stack, topology=topology)


def _collect_files(root: Path):
    files = []
    if not root.exists():
        return tuple(files)

    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        dirnames[:] = sorted(
            dirname
            for dirname in dirnames
            if dirname not in IGNORED_DIRS
            and not _is_ignored_path(current_path / dirname, root)
        )
        for filename in sorted(filenames):
            path = current_path / filename
            if not _is_ignored_path(path, root):
                files.append(path)

    return tuple(sorted(files))


def _is_ignored_path(path: Path, root: Path):
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return any(part in IGNORED_DIRS for part in relative.parts)


def _load_package_manifests(files, root: Path):
    manifests = {}
    for path in files:
        if path.name != "package.json":
            continue
        try:
            manifests[path] = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            manifests[path] = {}
    return manifests


def _detect_languages(files, root, package_manifests):
    facts = []
    names = {path.name: path for path in files}
    suffixes = {path.suffix.lower() for path in files}

    for filename in ("pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock"):
        if filename in names:
            facts.append(
                _fact(
                    "language",
                    "python",
                    Confidence.HIGH,
                    names[filename],
                    filename,
                    source_type=SourceType.MANIFEST,
                )
            )
            break

    if "package.json" in names:
        facts.append(
            _fact(
                "language",
                "javascript",
                Confidence.MEDIUM,
                names["package.json"],
                "package.json",
                source_type=SourceType.MANIFEST,
            )
        )

    if "tsconfig.json" in names or ".ts" in suffixes or ".tsx" in suffixes:
        if "tsconfig.json" in names:
            evidence_path = names["tsconfig.json"]
            source_type = SourceType.CONFIG
        else:
            evidence_path = _first_file_with_suffix(files, (".ts", ".tsx"))
            source_type = SourceType.FILE
        facts.append(
            _fact(
                "language",
                "typescript",
                Confidence.HIGH,
                evidence_path,
                "TypeScript project files",
                source_type=source_type,
            )
        )

    if "go.mod" in names:
        facts.append(
            _fact(
                "language",
                "go",
                Confidence.HIGH,
                names["go.mod"],
                "go.mod",
                source_type=SourceType.MANIFEST,
            )
        )

    if "Cargo.toml" in names:
        facts.append(
            _fact(
                "language",
                "rust",
                Confidence.HIGH,
                names["Cargo.toml"],
                "Cargo.toml",
                source_type=SourceType.MANIFEST,
            )
        )

    if not any(f.value == "python" for f in facts) and ".py" in suffixes:
        facts.append(
            _fact(
                "language",
                "python",
                Confidence.LOW,
                _first_file_with_suffix(files, (".py",)),
                "Python source file",
                source_type=SourceType.FILE,
            )
        )

    for path, manifest in package_manifests.items():
        dependencies = _manifest_dependencies(manifest)
        if "typescript" in dependencies and not any(
            f.value == "typescript" for f in facts
        ):
            facts.append(
                _fact(
                    "language",
                    "typescript",
                    Confidence.MEDIUM,
                    path,
                    "typescript dependency",
                    source_type=SourceType.DEPENDENCY,
                )
            )

    return facts


def _detect_frameworks(files, root, package_manifests, text_cache):
    facts = []
    for path in files:
        name = path.name
        if _matches_config(name, "next.config"):
            facts.append(
                _fact(
                    "framework",
                    "nextjs",
                    Confidence.HIGH,
                    path,
                    name,
                    source_type=SourceType.CONFIG,
                )
            )
        if _matches_config(name, "docusaurus.config"):
            facts.append(
                _fact(
                    "framework",
                    "docusaurus",
                    Confidence.HIGH,
                    path,
                    name,
                    source_type=SourceType.CONFIG,
                )
            )
        if _matches_config(name, "vite.config"):
            facts.append(
                _fact(
                    "framework",
                    "vite",
                    Confidence.HIGH,
                    path,
                    name,
                    source_type=SourceType.CONFIG,
                )
            )

    for path, manifest in package_manifests.items():
        dependencies = _manifest_dependencies(manifest)
        dependency_map = {
            "next": "nextjs",
            "react": "react",
            "@docusaurus/core": "docusaurus",
            "vite": "vite",
            "langchain": "langchain",
            "@langchain/core": "langchain",
            "@langchain/langgraph": "langgraph",
            "langgraph": "langgraph",
            "crewai": "crewai",
        }
        for dependency, framework in dependency_map.items():
            if dependency in dependencies:
                facts.append(
                    _fact(
                        "framework",
                        framework,
                        Confidence.MEDIUM,
                        path,
                        f"{dependency} dependency",
                        source_type=SourceType.DEPENDENCY,
                    )
                )

    for path in files:
        if path.suffix.lower() == ".py":
            content = _read_text(path, text_cache)
            if (
                "FastAPI(" in content
                or "from fastapi" in content
                or "import fastapi" in content
            ):
                facts.append(
                    _fact(
                        "framework",
                        "fastapi",
                        Confidence.LOW,
                        path,
                        "FastAPI reference",
                        source_type=SourceType.FILE,
                    )
                )

    for path in _python_manifest_files(files):
        content = _read_text(path, text_cache).lower()
        for framework in ("fastapi", "langchain", "langgraph", "crewai"):
            if framework in content:
                facts.append(
                    _fact(
                        "framework",
                        framework,
                        Confidence.MEDIUM,
                        path,
                        f"{framework} manifest reference",
                        source_type=SourceType.DEPENDENCY,
                    )
                )

    return facts


def _detect_package_managers(files, root):
    mapping = {
        "package-lock.json": "npm",
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "poetry.lock": "poetry",
        "Pipfile.lock": "pipenv",
    }
    facts = []
    for path in files:
        if path.name in mapping:
            facts.append(
                _fact(
                    "package_manager",
                    mapping[path.name],
                    Confidence.HIGH,
                    path,
                    path.name,
                    source_type=SourceType.MANIFEST,
                )
            )
        elif path.name.startswith("bun.lock"):
            facts.append(
                _fact(
                    "package_manager",
                    "bun",
                    Confidence.HIGH,
                    path,
                    path.name,
                    source_type=SourceType.MANIFEST,
                )
            )
    return facts


def _detect_docker(files, root):
    docker_files = {
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        ".dockerignore",
    }
    return tuple(
        _fact(
            "docker",
            "present",
            Confidence.HIGH,
            path,
            path.name,
            source_type=SourceType.CONFIG,
        )
        for path in files
        if path.name in docker_files
    )


def _detect_testing(files, root, package_manifests):
    facts = []
    test_config_prefixes = {
        "jest.config": "jest",
        "vitest.config": "vitest",
        "playwright.config": "playwright",
        "cypress.config": "cypress",
    }
    for path in files:
        for prefix, value in test_config_prefixes.items():
            if _matches_config(path.name, prefix):
                facts.append(
                    _fact(
                        "testing",
                        value,
                        Confidence.HIGH,
                        path,
                        path.name,
                        source_type=SourceType.CONFIG,
                    )
                )
        if path.name == "pytest.ini":
            facts.append(
                _fact(
                    "testing",
                    "pytest",
                    Confidence.HIGH,
                    path,
                    "pytest.ini",
                    source_type=SourceType.CONFIG,
                )
            )
        if _relative_parts(path, root)[0:1] == ("tests",):
            facts.append(
                _fact(
                    "testing",
                    "tests-directory",
                    Confidence.MEDIUM,
                    root / "tests",
                    "tests directory",
                    source_type=SourceType.DIRECTORY,
                )
            )

    for path, manifest in package_manifests.items():
        dependencies = _manifest_dependencies(manifest)
        for package, value in (
            ("jest", "jest"),
            ("vitest", "vitest"),
            ("@playwright/test", "playwright"),
            ("cypress", "cypress"),
        ):
            if package in dependencies:
                facts.append(
                    _fact(
                        "testing",
                        value,
                        Confidence.MEDIUM,
                        path,
                        f"{package} dependency",
                        source_type=SourceType.DEPENDENCY,
                    )
                )

    for path in _python_manifest_files(files):
        if "pytest" in _read_text(path, {}).lower():
            facts.append(
                _fact(
                    "testing",
                    "pytest",
                    Confidence.MEDIUM,
                    path,
                    "pytest reference",
                    source_type=SourceType.DEPENDENCY,
                )
            )

    return facts


def _detect_monorepo(files, root, package_manifests):
    facts = []
    names = {path.name: path for path in files}
    for filename, value in (
        ("pnpm-workspace.yaml", "pnpm-workspace"),
        ("turbo.json", "turbo"),
        ("nx.json", "nx"),
    ):
        if filename in names:
            facts.append(
                _fact(
                    "monorepo",
                    value,
                    Confidence.HIGH,
                    names[filename],
                    filename,
                    source_type=SourceType.CONFIG,
                )
            )

    for path, manifest in package_manifests.items():
        if "workspaces" in manifest:
            facts.append(
                _fact(
                    "monorepo",
                    "package-workspaces",
                    Confidence.HIGH,
                    path,
                    "package.json workspaces",
                    source_type=SourceType.MANIFEST,
                )
            )

    root_dirs = (
        {path.name for path in root.iterdir() if path.is_dir()}
        if root.exists()
        else set()
    )
    if "apps" in root_dirs and "packages" in root_dirs:
        facts.append(
            ProjectFact(
                category="monorepo",
                value="apps-packages-layout",
                confidence=Confidence.MEDIUM,
                evidence=(
                    Evidence(
                        root / "apps",
                        "apps directory",
                        source_type=SourceType.DIRECTORY,
                    ),
                    Evidence(
                        root / "packages",
                        "packages directory",
                        source_type=SourceType.DIRECTORY,
                    ),
                ),
                detector=canonical_detector_id("monorepo", "apps-packages-layout"),
            )
        )

    return facts


def read_env_keys(path: Path) -> tuple[str, ...]:
    """Read only variable names before '=' from an env file, ignoring comments, invalid lines, and values."""
    keys = []
    seen = set()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as env_file:
            for raw_line in env_file:
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key_part, _, _ = stripped.partition("=")
                key_part = key_part.strip()
                if key_part.startswith("export "):
                    key_part = key_part[len("export ") :].strip()
                if not ENV_KEY_PATTERN.match(key_part):
                    continue
                if key_part not in seen:
                    seen.add(key_part)
                    keys.append(key_part)
    except OSError:
        return ()
    return tuple(keys)


def _detect_databases(files, root, package_manifests, text_cache):
    facts = []
    for path in files:
        relative = _relative_parts(path, root)
        if relative and relative[0] == "supabase":
            facts.append(
                _fact(
                    "database",
                    "supabase",
                    Confidence.HIGH,
                    path,
                    "supabase directory",
                    source_type=SourceType.DIRECTORY,
                )
            )
        if relative == ("prisma", "schema.prisma"):
            facts.append(
                _fact(
                    "database",
                    "prisma",
                    Confidence.HIGH,
                    path,
                    "prisma schema",
                    source_type=SourceType.CONFIG,
                )
            )
        if path.name.startswith(".env"):
            env_keys = tuple(key.upper() for key in read_env_keys(path))
            if any("SUPABASE" in key for key in env_keys):
                facts.append(
                    _fact(
                        "database",
                        "supabase",
                        Confidence.LOW,
                        path,
                        "SUPABASE env key",
                        source_type=SourceType.ENVIRONMENT_KEY,
                    )
                )
            if any(
                key in {"DATABASE_URL", "POSTGRES_URL"} or "POSTGRES" in key
                for key in env_keys
            ):
                facts.append(
                    _fact(
                        "database",
                        "postgres",
                        Confidence.LOW,
                        path,
                        "database env key",
                        source_type=SourceType.ENVIRONMENT_KEY,
                    )
                )
            if any("MONGO" in key for key in env_keys):
                facts.append(
                    _fact(
                        "database",
                        "mongo",
                        Confidence.LOW,
                        path,
                        "mongo env key",
                        source_type=SourceType.ENVIRONMENT_KEY,
                    )
                )

    dependency_map = {
        "@supabase/supabase-js": "supabase",
        "pg": "postgres",
        "postgres": "postgres",
        "prisma": "prisma",
        "@prisma/client": "prisma",
        "mongoose": "mongo",
        "mongodb": "mongo",
    }
    for path, manifest in package_manifests.items():
        dependencies = _manifest_dependencies(manifest)
        for dependency, value in dependency_map.items():
            if dependency in dependencies:
                facts.append(
                    _fact(
                        "database",
                        value,
                        Confidence.MEDIUM,
                        path,
                        f"{dependency} dependency",
                        source_type=SourceType.DEPENDENCY,
                    )
                )

    for path in _python_manifest_files(files):
        content = _read_text(path, text_cache).lower()
        for package, value in (
            ("asyncpg", "postgres"),
            ("psycopg", "postgres"),
            ("pymongo", "mongo"),
            ("supabase", "supabase"),
        ):
            if package in content:
                facts.append(
                    _fact(
                        "database",
                        value,
                        Confidence.MEDIUM,
                        path,
                        f"{package} reference",
                        source_type=SourceType.DEPENDENCY,
                    )
                )

    return facts


def _detect_deploy_providers(files, root):
    facts = []
    for path in files:
        relative = _relative_parts(path, root)
        if path.name == "vercel.json" or (relative and relative[0] == ".vercel"):
            facts.append(
                _fact(
                    "deploy_provider",
                    "vercel",
                    Confidence.HIGH,
                    path,
                    path.name,
                    source_type=SourceType.CONFIG,
                )
            )
        if path.name == "netlify.toml":
            facts.append(
                _fact(
                    "deploy_provider",
                    "netlify",
                    Confidence.HIGH,
                    path,
                    path.name,
                    source_type=SourceType.CONFIG,
                )
            )
        if path.name == "wrangler.toml":
            facts.append(
                _fact(
                    "deploy_provider",
                    "cloudflare",
                    Confidence.HIGH,
                    path,
                    path.name,
                    source_type=SourceType.CONFIG,
                )
            )
        if path.name == "railway.json":
            facts.append(
                _fact(
                    "deploy_provider",
                    "railway",
                    Confidence.HIGH,
                    path,
                    path.name,
                    source_type=SourceType.CONFIG,
                )
            )
        if path.name == "fly.toml":
            facts.append(
                _fact(
                    "deploy_provider",
                    "fly",
                    Confidence.HIGH,
                    path,
                    path.name,
                    source_type=SourceType.CONFIG,
                )
            )
        if len(relative) >= 3 and relative[0:2] == (".github", "workflows"):
            facts.append(
                _fact(
                    "deploy_provider",
                    "github-actions",
                    Confidence.HIGH,
                    path,
                    ".github/workflows",
                    source_type=SourceType.WORKFLOW,
                )
            )
    return facts


def _fact(
    category: str,
    value: str,
    confidence: Confidence | str,
    path: Path,
    reason: str,
    *,
    source_type: SourceType = SourceType.FILE,
    detector: str | None = None,
) -> ProjectFact:
    resolved_detector = detector or canonical_detector_id(category, value)
    return ProjectFact(
        category=category,
        value=value,
        confidence=Confidence.coerce(confidence),
        evidence=(
            Evidence(
                path=path,
                reason=reason,
                source_type=source_type,
                detector=resolved_detector,
            ),
        ),
        detector=resolved_detector,
    )


def _dedupe_detections(detections, root: Path | None = None):
    return normalize_facts(detections, root=root)


def _manifest_dependencies(manifest):
    dependencies = {}
    for key in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    ):
        value = manifest.get(key, {})
        if isinstance(value, dict):
            dependencies.update(value)
    return dependencies


def _matches_config(filename, prefix):
    return filename == prefix or filename.startswith(prefix + ".")


def _read_text(path, cache):
    if path in cache:
        return cache[path]
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        content = ""
    cache[path] = content
    return content


def _first_file_with_suffix(files, suffixes):
    for path in files:
        if path.suffix.lower() in suffixes:
            return path
    return Path(".")


def _python_manifest_files(files):
    names = {"pyproject.toml", "requirements.txt", "Pipfile"}
    return tuple(path for path in files if path.name in names)


def _relative_parts(path, root):
    try:
        return path.relative_to(root).parts
    except ValueError:
        return path.parts


def _first_evidence(scan: ProjectModel | ProjectScan, category, value):
    model = scan.to_model() if isinstance(scan, ProjectScan) else scan
    matched = model.fact(category, value)
    if matched is not None:
        return matched.evidence
    return ()


def _has_node_ai_hints(scan: ProjectModel | ProjectScan):
    ai_frameworks = {"langchain", "langgraph", "crewai"}
    return (
        "javascript" in scan.values("language")
        or "typescript" in scan.values("language")
    ) and bool(ai_frameworks & set(scan.values("framework")))


def _has_frontend_without_backend(scan: ProjectModel | ProjectScan):
    frontend_frameworks = {"react", "vite"}
    backend_frameworks = {"nextjs", "fastapi"}
    return (
        bool(frontend_frameworks & set(scan.values("framework")))
        and not bool(backend_frameworks & set(scan.values("framework")))
        and not scan.values("database")
    )

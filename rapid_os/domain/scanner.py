import json
import os
from dataclasses import dataclass
from pathlib import Path


CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

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

DETECTION_CATEGORIES = (
    "language",
    "framework",
    "package_manager",
    "docker",
    "testing",
    "monorepo",
    "database",
    "deploy_provider",
)


@dataclass(frozen=True)
class Evidence:
    path: Path
    reason: str

    def to_dict(self):
        return {"path": str(self.path), "reason": self.reason}


@dataclass(frozen=True)
class Detection:
    category: str
    value: str
    confidence: str
    evidence: tuple[Evidence, ...] = ()

    def to_dict(self):
        return {
            "category": self.category,
            "value": self.value,
            "confidence": self.confidence,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class ProjectScan:
    root: Path
    detections: tuple[Detection, ...] = ()

    def by_category(self, category: str):
        return tuple(
            detection
            for detection in self.detections
            if detection.category == category
        )

    def values(self, category: str):
        return tuple(detection.value for detection in self.by_category(category))

    def has(self, category: str, value: str):
        return value in self.values(category)

    def to_dict(self):
        return {
            "root": str(self.root),
            "detections": [detection.to_dict() for detection in self.detections],
        }


@dataclass(frozen=True)
class InitSuggestion:
    field: str
    value: str
    confidence: str
    reason: str
    evidence: tuple[Evidence, ...] = ()

    def to_dict(self):
        return {
            "field": self.field,
            "value": self.value,
            "confidence": self.confidence,
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


def scan_project(project_dir: Path):
    root = Path(project_dir)
    files = _collect_files(root)
    package_manifests = _load_package_manifests(files, root)
    text_cache = {}

    detections = []
    detections.extend(_detect_languages(files, root, package_manifests))
    detections.extend(_detect_frameworks(files, root, package_manifests, text_cache))
    detections.extend(_detect_package_managers(files, root))
    detections.extend(_detect_docker(files, root))
    detections.extend(_detect_testing(files, root, package_manifests))
    detections.extend(_detect_monorepo(files, root, package_manifests))
    detections.extend(_detect_databases(files, root, package_manifests, text_cache))
    detections.extend(_detect_deploy_providers(files, root))

    return ProjectScan(root=root, detections=_dedupe_detections(detections))


def suggest_init_choices(scan: ProjectScan):
    framework_values = set(scan.values("framework"))
    language_values = set(scan.values("language"))
    database_values = set(scan.values("database"))

    app_frameworks = framework_values & {
        "docusaurus",
        "nextjs",
        "fastapi",
    }
    has_conflict = len(app_frameworks) > 1

    stack = None
    topology = None

    if not has_conflict and scan.has("framework", "docusaurus"):
        evidence = _first_evidence(scan, "framework", "docusaurus")
        stack = InitSuggestion(
            "stack",
            "docs-modern",
            CONFIDENCE_HIGH,
            "Docusaurus project detected.",
            evidence,
        )
        topology = InitSuggestion(
            "topology",
            "doc-site",
            CONFIDENCE_HIGH,
            "Docusaurus projects match the doc-site topology.",
            evidence,
        )
    elif not has_conflict and scan.has("framework", "nextjs"):
        evidence = _first_evidence(scan, "framework", "nextjs")
        stack = InitSuggestion(
            "stack",
            "web-modern",
            CONFIDENCE_HIGH,
            "Next.js project detected.",
            evidence,
        )
        if "supabase" in database_values:
            topology = InitSuggestion(
                "topology",
                "fullstack-baas",
                CONFIDENCE_MEDIUM,
                "Next.js and Supabase hints were detected.",
                evidence + _first_evidence(scan, "database", "supabase"),
            )
    elif not has_conflict and scan.has("framework", "fastapi"):
        evidence = _first_evidence(scan, "framework", "fastapi")
        if "python" in language_values:
            stack = InitSuggestion(
                "stack",
                "python-ai",
                CONFIDENCE_HIGH,
                "Python and FastAPI project detected.",
                evidence,
            )
            topology = InitSuggestion(
                "topology",
                "fullstack-separated",
                CONFIDENCE_MEDIUM,
                "FastAPI usually acts as a separate backend service.",
                evidence,
            )
    elif not has_conflict and _has_node_ai_hints(scan):
        evidence = (
            _first_evidence(scan, "framework", "langchain")
            or _first_evidence(scan, "framework", "langgraph")
            or _first_evidence(scan, "framework", "crewai")
        )
        stack = InitSuggestion(
            "stack",
            "nodejs-ai",
            CONFIDENCE_MEDIUM,
            "Node.js AI framework hints were detected.",
            evidence,
        )
    elif not has_conflict and _has_frontend_without_backend(scan):
        evidence = (
            _first_evidence(scan, "framework", "react")
            or _first_evidence(scan, "framework", "vite")
        )
        topology = InitSuggestion(
            "topology",
            "front-end-only",
            CONFIDENCE_MEDIUM,
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
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in IGNORED_DIRS
            and not _is_ignored_path(current_path / dirname, root)
        ]
        for filename in filenames:
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
    detections = []
    names = {path.name: path for path in files}
    suffixes = {path.suffix.lower() for path in files}

    for filename in ("pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock"):
        if filename in names:
            detections.append(
                _detection("language", "python", CONFIDENCE_HIGH, names[filename], filename)
            )
            break

    if "package.json" in names:
        detections.append(
            _detection("language", "javascript", CONFIDENCE_MEDIUM, names["package.json"], "package.json")
        )

    if "tsconfig.json" in names or ".ts" in suffixes or ".tsx" in suffixes:
        evidence_path = names.get("tsconfig.json") or _first_file_with_suffix(files, (".ts", ".tsx"))
        detections.append(
            _detection("language", "typescript", CONFIDENCE_HIGH, evidence_path, "TypeScript project files")
        )

    if "go.mod" in names:
        detections.append(_detection("language", "go", CONFIDENCE_HIGH, names["go.mod"], "go.mod"))

    if "Cargo.toml" in names:
        detections.append(
            _detection("language", "rust", CONFIDENCE_HIGH, names["Cargo.toml"], "Cargo.toml")
        )

    if not any(d.value == "python" for d in detections) and ".py" in suffixes:
        detections.append(
            _detection("language", "python", CONFIDENCE_LOW, _first_file_with_suffix(files, (".py",)), "Python source file")
        )

    for path, manifest in package_manifests.items():
        dependencies = _manifest_dependencies(manifest)
        if "typescript" in dependencies and not any(d.value == "typescript" for d in detections):
            detections.append(
                _detection("language", "typescript", CONFIDENCE_MEDIUM, path, "typescript dependency")
            )

    return detections


def _detect_frameworks(files, root, package_manifests, text_cache):
    detections = []
    for path in files:
        name = path.name
        if _matches_config(name, "next.config"):
            detections.append(_detection("framework", "nextjs", CONFIDENCE_HIGH, path, name))
        if _matches_config(name, "docusaurus.config"):
            detections.append(
                _detection("framework", "docusaurus", CONFIDENCE_HIGH, path, name)
            )
        if _matches_config(name, "vite.config"):
            detections.append(_detection("framework", "vite", CONFIDENCE_HIGH, path, name))

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
                detections.append(
                    _detection(
                        "framework",
                        framework,
                        CONFIDENCE_MEDIUM,
                        path,
                        f"{dependency} dependency",
                    )
                )

    for path in files:
        if path.suffix.lower() == ".py":
            content = _read_text(path, text_cache)
            if "FastAPI(" in content or "from fastapi" in content or "import fastapi" in content:
                detections.append(
                    _detection("framework", "fastapi", CONFIDENCE_LOW, path, "FastAPI reference")
                )

    for path in _python_manifest_files(files):
        content = _read_text(path, text_cache).lower()
        for framework in ("fastapi", "langchain", "langgraph", "crewai"):
            if framework in content:
                detections.append(
                    _detection(
                        "framework",
                        framework,
                        CONFIDENCE_MEDIUM,
                        path,
                        f"{framework} manifest reference",
                    )
                )

    return detections


def _detect_package_managers(files, root):
    mapping = {
        "package-lock.json": "npm",
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "poetry.lock": "poetry",
        "Pipfile.lock": "pipenv",
    }
    detections = []
    for path in files:
        if path.name in mapping:
            detections.append(
                _detection(
                    "package_manager",
                    mapping[path.name],
                    CONFIDENCE_HIGH,
                    path,
                    path.name,
                )
            )
        elif path.name.startswith("bun.lock"):
            detections.append(
                _detection("package_manager", "bun", CONFIDENCE_HIGH, path, path.name)
            )
    return detections


def _detect_docker(files, root):
    docker_files = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"}
    return tuple(
        _detection("docker", "present", CONFIDENCE_HIGH, path, path.name)
        for path in files
        if path.name in docker_files
    )


def _detect_testing(files, root, package_manifests):
    detections = []
    test_config_prefixes = {
        "jest.config": "jest",
        "vitest.config": "vitest",
        "playwright.config": "playwright",
        "cypress.config": "cypress",
    }
    for path in files:
        for prefix, value in test_config_prefixes.items():
            if _matches_config(path.name, prefix):
                detections.append(
                    _detection("testing", value, CONFIDENCE_HIGH, path, path.name)
                )
        if path.name == "pytest.ini":
            detections.append(
                _detection("testing", "pytest", CONFIDENCE_HIGH, path, "pytest.ini")
            )
        if _relative_parts(path, root)[0:1] == ("tests",):
            detections.append(
                _detection("testing", "tests-directory", CONFIDENCE_MEDIUM, path.parent, "tests directory")
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
                detections.append(
                    _detection("testing", value, CONFIDENCE_MEDIUM, path, f"{package} dependency")
                )

    for path in _python_manifest_files(files):
        if "pytest" in _read_text(path, {}).lower():
            detections.append(
                _detection("testing", "pytest", CONFIDENCE_MEDIUM, path, "pytest reference")
            )

    return detections


def _detect_monorepo(files, root, package_manifests):
    detections = []
    names = {path.name: path for path in files}
    for filename, value in (
        ("pnpm-workspace.yaml", "pnpm-workspace"),
        ("turbo.json", "turbo"),
        ("nx.json", "nx"),
    ):
        if filename in names:
            detections.append(
                _detection("monorepo", value, CONFIDENCE_HIGH, names[filename], filename)
            )

    for path, manifest in package_manifests.items():
        if "workspaces" in manifest:
            detections.append(
                _detection("monorepo", "package-workspaces", CONFIDENCE_HIGH, path, "package.json workspaces")
            )

    root_dirs = {path.name for path in root.iterdir() if path.is_dir()} if root.exists() else set()
    if "apps" in root_dirs and "packages" in root_dirs:
        detections.append(
            Detection(
                "monorepo",
                "apps-packages-layout",
                CONFIDENCE_MEDIUM,
                (
                    Evidence(root / "apps", "apps directory"),
                    Evidence(root / "packages", "packages directory"),
                ),
            )
        )

    return detections


def _detect_databases(files, root, package_manifests, text_cache):
    detections = []
    for path in files:
        relative = _relative_parts(path, root)
        if relative and relative[0] == "supabase":
            detections.append(
                _detection("database", "supabase", CONFIDENCE_HIGH, path, "supabase directory")
            )
        if relative == ("prisma", "schema.prisma"):
            detections.append(
                _detection("database", "prisma", CONFIDENCE_HIGH, path, "prisma schema")
            )
        if path.name.startswith(".env"):
            content = _read_text(path, text_cache).upper()
            if "SUPABASE" in content:
                detections.append(
                    _detection("database", "supabase", CONFIDENCE_LOW, path, "SUPABASE env key")
                )
            if "DATABASE_URL" in content or "POSTGRES_URL" in content:
                detections.append(
                    _detection("database", "postgres", CONFIDENCE_LOW, path, "database env key")
                )
            if "MONGO" in content:
                detections.append(
                    _detection("database", "mongo", CONFIDENCE_LOW, path, "mongo env key")
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
                detections.append(
                    _detection("database", value, CONFIDENCE_MEDIUM, path, f"{dependency} dependency")
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
                detections.append(
                    _detection("database", value, CONFIDENCE_MEDIUM, path, f"{package} reference")
                )

    return detections


def _detect_deploy_providers(files, root):
    detections = []
    for path in files:
        relative = _relative_parts(path, root)
        if path.name == "vercel.json" or (relative and relative[0] == ".vercel"):
            detections.append(_detection("deploy_provider", "vercel", CONFIDENCE_HIGH, path, path.name))
        if path.name == "netlify.toml":
            detections.append(_detection("deploy_provider", "netlify", CONFIDENCE_HIGH, path, path.name))
        if path.name == "wrangler.toml":
            detections.append(_detection("deploy_provider", "cloudflare", CONFIDENCE_HIGH, path, path.name))
        if path.name == "railway.json":
            detections.append(_detection("deploy_provider", "railway", CONFIDENCE_HIGH, path, path.name))
        if path.name == "fly.toml":
            detections.append(_detection("deploy_provider", "fly", CONFIDENCE_HIGH, path, path.name))
        if len(relative) >= 3 and relative[0:2] == (".github", "workflows"):
            detections.append(
                _detection("deploy_provider", "github-actions", CONFIDENCE_HIGH, path, ".github/workflows")
            )
    return detections


def _detection(category, value, confidence, path, reason):
    return Detection(category, value, confidence, (Evidence(path, reason),))


def _dedupe_detections(detections):
    grouped = {}
    order = []
    confidence_rank = {CONFIDENCE_LOW: 0, CONFIDENCE_MEDIUM: 1, CONFIDENCE_HIGH: 2}
    for detection in detections:
        key = (detection.category, detection.value)
        if key not in grouped:
            grouped[key] = detection
            order.append(key)
            continue

        existing = grouped[key]
        confidence = (
            detection.confidence
            if confidence_rank[detection.confidence] > confidence_rank[existing.confidence]
            else existing.confidence
        )
        grouped[key] = Detection(
            existing.category,
            existing.value,
            confidence,
            existing.evidence + detection.evidence,
        )

    return tuple(grouped[key] for key in order)


def _manifest_dependencies(manifest):
    dependencies = {}
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
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
    return Path()


def _python_manifest_files(files):
    names = {"pyproject.toml", "requirements.txt", "Pipfile"}
    return tuple(path for path in files if path.name in names)


def _relative_parts(path, root):
    try:
        return path.relative_to(root).parts
    except ValueError:
        return path.parts


def _first_evidence(scan, category, value):
    for detection in scan.detections:
        if detection.category == category and detection.value == value:
            return detection.evidence
    return ()


def _has_node_ai_hints(scan):
    ai_frameworks = {"langchain", "langgraph", "crewai"}
    return (
        "javascript" in scan.values("language")
        or "typescript" in scan.values("language")
    ) and bool(ai_frameworks & set(scan.values("framework")))


def _has_frontend_without_backend(scan):
    frontend_frameworks = {"react", "vite"}
    backend_frameworks = {"nextjs", "fastapi"}
    return (
        bool(frontend_frameworks & set(scan.values("framework")))
        and not bool(backend_frameworks & set(scan.values("framework")))
        and not scan.values("database")
    )

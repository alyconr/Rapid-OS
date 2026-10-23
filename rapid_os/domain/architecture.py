"""Modular-monolith architecture rule and its import checker. Pure: no I/O.

The rule (`.rapid-os/standards/architecture.json`) says where the modules live, what each layer is
called in the stack's language, which layers a layer may import and which libraries the pure layer
must never touch. The checker takes the rule and the source text of the files under `modules_root`
and `shared_root` and returns the violations. Python is read with `ast`; TypeScript/JavaScript (and
the script of `.vue`, `.svelte` and `.astro` files), Go, Java, Kotlin, C#, Rust and PHP with regular
expressions: nothing is executed. Ruby on Rails has no imports to read; its rule delegates to
packwerk (`delegate`).
"""

from __future__ import annotations

import ast
import posixpath
import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from rapid_os.domain.architecture_profiles import (
    BACKEND_LAYERS,
    BACKEND_RULES,
    CANONICAL,
    FRONTEND_RULES,
    ROLE_TEXT,
    RuleSpec,
)
from rapid_os.domain.stack_aliases import LEGACY_STACKS

ARCHITECTURE_SCHEMA_VERSION = 1
ARCHITECTURE_CODE = "RAPID1420"
LANGUAGES = ("python", "typescript", "go", "java", "kotlin", "csharp", "rust", "php", "ruby")
LAYER_NAMES = ("api", "application", "domain", "infrastructure")
SOURCE_SUFFIXES: Mapping[str, tuple[str, ...]] = {
    "python": (".py",),
    "typescript": (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro"),
    "go": (".go",),
    "java": (".java",),
    "kotlin": (".kt", ".kts"),
    "csharp": (".cs", ".csproj"),
    "rust": (".rs",),
    "php": (".php",),
    "ruby": (".rb",),
}
_ALL_SUFFIXES = tuple(sorted({s for suffixes in SOURCE_SUFFIXES.values() for s in suffixes}, key=len, reverse=True))
PUBLIC_POLICIES = ("entry", "root")

RULE_LAYER = "layer"
RULE_CROSS_MODULE = "cross_module"
RULE_SHARED = "shared"
RULE_DOMAIN_FORBIDDEN = "domain_forbidden_import"
RULE_INIT_REEXPORT = "init_reexport"


class ArchitectureConfigError(ValueError):
    """Invalid `architecture.json` (reported with RAPID1420)."""

    code = ARCHITECTURE_CODE


# --- the rule of a project ------------------------------------------------------------------


def stacks_of_legacy(stack_id: str) -> dict[str, str]:
    """`{component: stack}` for a stack id, accepting the ids of before the component catalog."""
    legacy = LEGACY_STACKS.get(stack_id)
    if legacy is not None:
        return dict(legacy.stacks)
    if stack_id in BACKEND_RULES and stack_id not in FRONTEND_RULES:
        return {"backend": stack_id}
    if stack_id in FRONTEND_RULES and stack_id not in BACKEND_RULES:
        return {"frontend": stack_id}
    if stack_id in BACKEND_RULES:  # nextjs, nuxt, sveltekit: one stack for both
        return {"frontend": stack_id, "backend": stack_id}
    return {}


def rules_for(stacks: Mapping[str, str]) -> list[tuple[str, str, RuleSpec, str]]:
    """`(component, stack_id, rule, root)` for each rule a project gets, backend first.

    A backend and a frontend that are different stacks live in `backend/` and `frontend/`; one
    stack that covers both (Next.js, Nuxt, SvelteKit) keeps its two rules at the project root, and a
    project with only one of them keeps it at the root too."""
    found: list[tuple[str, str, RuleSpec]] = []
    backend_id = stacks.get("backend")
    frontend_id = stacks.get("frontend")
    if backend_id in BACKEND_RULES:
        found.append(("backend", backend_id, BACKEND_RULES[backend_id]))
    if frontend_id in FRONTEND_RULES and (frontend_id != backend_id or backend_id in BACKEND_RULES):
        found.append(("frontend", frontend_id, FRONTEND_RULES[frontend_id]))
    separate = len(found) == 2 and found[0][1] != found[1][1]
    return [(c, sid, spec, c if separate else "") for c, sid, spec in found]


def architecture_document(stacks: Mapping[str, str]) -> dict:
    """The content of `architecture.json` for the stacks of a project, or `{}` when none gets a rule."""
    rules = rules_for(stacks)
    if not rules:
        return {}
    dicts = [{"schema_version": ARCHITECTURE_SCHEMA_VERSION, **spec.to_dict(root)} for _c, _s, spec, root in rules]
    document = dict(dicts[0])
    if len(dicts) > 1:
        document["rules"] = dicts
    return document


def default_config(stack_id: str) -> dict:
    """The machine-readable rule for one stack id (legacy ids included), or `{}`."""
    return architecture_document(stacks_of_legacy(stack_id))


# --- reading the rule -----------------------------------------------------------------------


@dataclass(frozen=True)
class ArchitectureConfig:
    language: str
    modules_root: str
    shared_root: str
    public_entry: str
    layers: Mapping[str, tuple[str, ...]]
    domain_forbidden_imports: tuple[str, ...]
    roles: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    pure_layer: str = "domain"
    public_policy: str = "entry"
    public_dirs: tuple[str, ...] = ()
    namespace_root: str = ""
    aliases: Mapping[str, str] = field(default_factory=dict)
    delegate: str = ""
    component: str = "backend"
    root: str = ""
    # The test of the stack's own ecosystem (Spring Modulith, Deptrac, NetArchTest, packwerk) the scaffold adds.
    complementary: str = ""

    @property
    def public_stem(self) -> str:
        return _stem(self.public_entry.split("|")[0])

    @property
    def public_entries(self) -> tuple[str, ...]:
        return tuple(_stem(item) for item in self.public_entry.split("|"))

    @property
    def root_segments(self) -> tuple[str, ...]:
        return tuple(part for part in self.root.split("/") if part)

    @property
    def relative_modules_root(self) -> tuple[str, ...]:
        return tuple(self.modules_root.split("/"))[len(self.root_segments):]

    def role_dirs(self, role: str, module: str) -> tuple[str, ...]:
        dirs = self.roles.get(role) or (role,)
        return tuple(item.replace("{m}", module).replace("{M}", module) for item in dirs)

    @classmethod
    def from_dict(cls, data: object) -> "ArchitectureConfig":
        def fail(message: str) -> ArchitectureConfigError:
            return ArchitectureConfigError(f"{ARCHITECTURE_CODE} architecture.json inválido: {message}")

        if not isinstance(data, dict):
            raise fail("debe ser un objeto JSON.")
        version = data.get("schema_version")
        if isinstance(version, bool) or version != ARCHITECTURE_SCHEMA_VERSION:
            raise fail(f"schema_version debe ser {ARCHITECTURE_SCHEMA_VERSION}.")
        language = data.get("language")
        if language not in LANGUAGES:
            raise fail(f"language debe ser uno de {list(LANGUAGES)}.")

        def relative(key: str, value: object) -> str:
            if not isinstance(value, str) or not value.strip() or value.startswith("/") or ".." in value.split("/"):
                raise fail(f"{key} debe ser una ruta relativa no vacía.")
            return value.strip().strip("/")

        root = data.get("root", "")
        root = relative("root", root) if root else ""
        paths = {key: relative(key, data.get(key)) for key in ("modules_root", "shared_root")}
        entry = data.get("public_entry")
        if not isinstance(entry, str) or not entry.strip() or entry.startswith("/") or ".." in entry.split("/"):
            raise fail("public_entry debe ser una ruta relativa no vacía.")
        raw_layers = data.get("layers")
        if not isinstance(raw_layers, dict) or not raw_layers:
            raise fail("layers debe ser un objeto {capa: [capas permitidas]}.")
        layers: dict[str, tuple[str, ...]] = {}
        for layer, allowed in raw_layers.items():
            if not isinstance(layer, str) or not isinstance(allowed, list) or not all(
                isinstance(item, str) for item in allowed
            ):
                raise fail("cada capa de layers debe mapear a una lista de nombres de capa.")
            unknown = [item for item in allowed if item not in raw_layers]
            if unknown:
                raise fail(f"layers.{layer} permite capas que no existen: {', '.join(unknown)}.")
            layers[layer] = tuple(allowed)
        forbidden = data.get("domain_forbidden_imports", [])
        if not isinstance(forbidden, list) or not all(isinstance(item, str) and item for item in forbidden):
            raise fail("domain_forbidden_imports debe ser una lista de nombres de librería.")
        raw_roles = data.get("roles", {})
        roles: dict[str, tuple[str, ...]] = {}
        if not isinstance(raw_roles, dict):
            raise fail("roles debe ser un objeto {capa: carpeta o lista de carpetas}.")
        for role, dirs in raw_roles.items():
            names = [dirs] if isinstance(dirs, str) else dirs
            if (
                role not in layers
                or not isinstance(names, list)
                or not names
                or not all(isinstance(item, str) and item for item in names)
            ):
                raise fail(f"roles.{role} debe nombrar una capa de layers y una carpeta o lista de carpetas.")
            roles[role] = tuple(names)
        pure_layer = data.get("pure_layer", "domain")
        if pure_layer not in layers:
            raise fail(f"pure_layer '{pure_layer}' no es una capa de layers.")
        policy = data.get("public_policy", "entry")
        if policy not in PUBLIC_POLICIES:
            raise fail(f"public_policy debe ser uno de {list(PUBLIC_POLICIES)}.")
        public_dirs = data.get("public_dirs", [])
        if not isinstance(public_dirs, list) or not all(isinstance(item, str) and item for item in public_dirs):
            raise fail("public_dirs debe ser una lista de carpetas.")
        namespace_root = data.get("namespace_root", "")
        if not isinstance(namespace_root, str):
            raise fail("namespace_root debe ser un texto.")
        aliases = data.get("aliases", {"@/": "src/"} if language == "typescript" else {})
        if not isinstance(aliases, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in aliases.items()):
            raise fail("aliases debe ser un objeto {prefijo: carpeta}.")
        delegate = data.get("delegate", "")
        if not isinstance(delegate, str):
            raise fail("delegate debe ser un texto.")
        component = data.get("component", "backend")
        if not isinstance(component, str) or not component:
            raise fail("component debe ser un texto.")
        complementary = data.get("complementary", "")
        if not isinstance(complementary, str):
            raise fail("complementary debe ser un texto.")
        prefix = f"{root}/" if root else ""
        return cls(
            language=language,
            modules_root=prefix + paths["modules_root"],
            shared_root=prefix + paths["shared_root"],
            public_entry=entry.strip().strip("/") if "|" not in entry else entry.strip(),
            layers=layers,
            domain_forbidden_imports=tuple(forbidden),
            roles=roles,
            pure_layer=pure_layer,
            public_policy=policy,
            public_dirs=tuple(public_dirs),
            namespace_root=namespace_root,
            aliases={k: (v if v.endswith("/") or not v else v + "/") for k, v in aliases.items()},
            delegate=delegate,
            component=component,
            root=root,
            complementary=complementary,
        )


def load_rules(data: object) -> list[ArchitectureConfig]:
    """Every rule of an `architecture.json`: the `rules` list when it has one, else the file itself."""
    if isinstance(data, dict) and isinstance(data.get("rules"), list) and data["rules"]:
        version = data.get("schema_version")
        return [ArchitectureConfig.from_dict({"schema_version": version, **rule}) for rule in data["rules"]]
    return [ArchitectureConfig.from_dict(data)]


@dataclass(frozen=True)
class Violation:
    rule: str
    file: str
    line: int
    imported: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "code": ARCHITECTURE_CODE,
            "rule": self.rule,
            "file": self.file,
            "line": self.line,
            "import": self.imported,
            "message": self.message,
        }

    def to_line(self) -> str:
        return f"{ARCHITECTURE_CODE} {self.file}:{self.line} importa '{self.imported}': {self.message}"


@dataclass(frozen=True)
class ArchitectureReport:
    language: str
    modules: tuple[str, ...]
    checked_files: int
    violations: tuple[Violation, ...]
    skipped: tuple[str, ...] = ()
    delegate: str = ""

    @property
    def ok(self) -> bool:
        return not self.violations


# --- where a file or an import target lives -------------------------------------------------


@dataclass(frozen=True)
class _Place:
    """A path inside the tree: `kind` is `module`, `shared` or `other`."""

    kind: str
    module: str | None = None
    layer: str | None = None  # the role of the first segment under the module, "" for the module's own files
    rest: tuple[str, ...] = ()  # the segments after the module (the layer first)


def _stem(segment: str) -> str:
    """`public.py` -> `public`, `pay.module.ts` -> `pay.module`; a directory such as `Pay.Api` keeps its dots."""
    for suffix in _ALL_SUFFIXES:
        if segment.endswith(suffix) and len(segment) > len(suffix):
            return segment[: -len(suffix)]
    return segment


def _role_of(config: ArchitectureConfig, module: str, segment: str) -> str | None:
    stem = _stem(segment)
    for role in config.layers:
        if stem in {_stem(item) for item in config.role_dirs(role, module)}:
            return role
    return None


def _locate(config: ArchitectureConfig, segments: tuple[str, ...], *, file: bool = False) -> _Place:
    """Where a path lives. A *file* directly in `modules_root` is not a module (only directories
    are); an *import* of `<modules_root>/<m>` does name the module."""
    modules_root = tuple(config.modules_root.split("/"))
    shared_root = tuple(config.shared_root.split("/"))
    if segments[: len(shared_root)] == shared_root:
        return _Place("shared")
    if segments[: len(modules_root)] == modules_root and len(segments) > len(modules_root) + (1 if file else 0):
        module = segments[len(modules_root)]
        rest = segments[len(modules_root) + 1 :]
        layer = ""
        if rest:
            layer = _role_of(config, module, rest[0]) or _stem(rest[0])
        return _Place("module", module=module, layer=layer, rest=rest)
    return _Place("other")


def _is_public(config: ArchitectureConfig, module: str, rest: tuple[str, ...]) -> bool:
    """The module itself or what the rule calls its public contract; never one of its layers."""
    if not rest:
        return True
    first = _stem(rest[0])
    if first in {_stem(item.replace("{m}", module).replace("{M}", module)) for item in config.public_dirs}:
        return True
    if config.public_policy == "root":
        return _role_of(config, module, rest[0]) is None
    return first in {_stem(item.replace("{m}", module).replace("{M}", module)) for item in config.public_entry.split("|")}


def _split(name: str) -> tuple[str, ...]:
    return tuple(part for part in re.split(r"[./\\:]+", name) if part)


def _forbidden(config: ArchitectureConfig, top: str) -> bool:
    spelled = _split(top)
    return any(spelled[: len(lib)] == lib for lib in (_split(item) for item in config.domain_forbidden_imports) if lib)


# --- the check -----------------------------------------------------------------------------


def _violations_for_target(
    config: ArchitectureConfig,
    source: _Place,
    file: str,
    line: int,
    spelled: str,
    target_segments: tuple[str, ...] | None,
    top_package: str,
) -> list[Violation]:
    found: list[Violation] = []
    if source.layer == config.pure_layer and top_package and _forbidden(config, top_package):
        found.append(
            Violation(
                RULE_DOMAIN_FORBIDDEN, file, line, spelled,
                f"{config.pure_layer} no puede importar '{top_package}' (framework web, ORM o cliente externo); "
                "la regla está en domain_forbidden_imports de architecture.json",
            )
        )
    if target_segments is None:
        return found
    target = _locate(config, target_segments)
    if source.kind == "shared" and target.kind == "module":
        found.append(
            Violation(
                RULE_SHARED, file, line, spelled,
                f"shared no puede importar ningún módulo (aquí, '{target.module}')",
            )
        )
    elif source.kind == "module" and target.kind == "module":
        if target.module != source.module:
            if not _is_public(config, target.module or "", target.rest):
                found.append(
                    Violation(
                        RULE_CROSS_MODULE, file, line, spelled,
                        f"el módulo '{source.module}' solo puede importar el punto público "
                        f"({config.public_entry.replace('{m}', target.module or '').replace('{M}', target.module or '')}) "
                        f"del módulo '{target.module}', no su capa '{target.layer or target.rest[0]}'",
                    )
                )
        elif source.layer in config.layers and target.layer in config.layers and target.layer != source.layer:
            if target.layer not in config.layers[source.layer]:
                allowed = ", ".join(config.layers[source.layer]) or "ninguna"
                found.append(
                    Violation(
                        RULE_LAYER, file, line, spelled,
                        f"la capa '{source.layer}' no puede importar la capa '{target.layer}' "
                        f"(permitidas: {allowed})",
                    )
                )
    return found


def _init_violations(config: ArchitectureConfig, place: _Place, path: str, text: str) -> list[Violation]:
    """The `__init__.py` at the root of a Python module may be empty or re-export only the
    module's own public entry. Anything else would let `from app.modules.pagos import Repo`
    reach an internal layer through the package, a back door around the public entry."""
    module_root = tuple(config.modules_root.split("/")) + (place.module or "",)
    public = module_root + (config.public_stem,)
    package = _python_package(path)
    message = f"el __init__.py del módulo '{place.module}' solo puede reexportar su {config.public_entry}"
    found: list[Violation] = []
    for node in ast.walk(ast.parse(text, filename=path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if tuple(alias.name.split("."))[: len(public)] != public:
                    found.append(Violation(RULE_INIT_REEXPORT, path, node.lineno, alias.name, message))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module == "__future__":
                continue  # a compiler directive, not a re-export
            base, spelled, _top = _resolve_from(package, node)
            if base is not None:
                if tuple(base[: len(public)]) == public:
                    continue  # from .public import x
                if tuple(base) == module_root and all(a.name == config.public_stem for a in node.names):
                    continue  # from . import public
            found.append(Violation(RULE_INIT_REEXPORT, path, node.lineno, spelled, message))
    return found


def _dedupe(violations: Iterable[Violation]) -> list[Violation]:
    seen: set[tuple[str, int, str]] = set()
    unique: list[Violation] = []
    for item in violations:
        key = (item.file, item.line, item.rule)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def check_architecture(config: ArchitectureConfig, sources: Mapping[str, str]) -> ArchitectureReport:
    """`sources` maps a project-relative posix path to its text. Only files under `modules_root`
    and `shared_root` are expected; anything else is ignored."""
    if config.delegate:
        return ArchitectureReport(config.language, (), 0, (), (), delegate=config.delegate)
    violations: list[Violation] = []
    skipped: list[str] = []
    modules: set[str] = set()
    checked = 0
    for path in sorted(sources):
        place = _locate(config, tuple(path.split("/")), file=True)
        if place.kind == "other":
            continue
        if place.kind == "module" and place.module:
            modules.add(place.module)
        checked += 1
        try:
            refs = list(_references(config, path, sources[path]))
        except SyntaxError as exc:
            skipped.append(f"{path}: no se pudo leer ({exc.msg}, línea {exc.lineno})")
            continue
        for line, spelled, target_segments, top_package in refs:
            violations.extend(
                _violations_for_target(config, place, path, line, spelled, target_segments, top_package)
            )
        if config.language == "python" and place.kind == "module" and place.rest == ("__init__.py",):
            violations.extend(_init_violations(config, place, path, sources[path]))
    return ArchitectureReport(
        language=config.language,
        modules=tuple(sorted(modules)),
        checked_files=checked,
        violations=tuple(_dedupe(violations)),
        skipped=tuple(skipped),
    )


# (line, spelled import, segments of the target inside the project or None, name for the forbidden-library rule)
_Ref = tuple[int, str, "tuple[str, ...] | None", str]


def _references(config: ArchitectureConfig, path: str, text: str) -> Iterable[_Ref]:
    language = config.language
    if language == "python":
        return _python_imports(path, text, frozenset(config.layers))
    if language == "typescript":
        return _typescript_imports(path, _script_text(path, text), config.aliases)
    if language == "go":
        return _go_imports(config, path, text)
    if language in ("java", "kotlin"):
        return _jvm_imports(config, path, text)
    if language == "csharp":
        return _csharp_refs(config, path, text)
    if language == "rust":
        return _rust_uses(config, path, text)
    if language == "php":
        return _php_uses(config, path, text)
    return ()


# --- comments -------------------------------------------------------------------------------

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"(^|[\s;{}()])//[^\n]*")


def _strip_c_comments(text: str) -> str:
    text = _BLOCK_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return _LINE_COMMENT.sub(lambda m: m.group(1), text)


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


# --- Python ---------------------------------------------------------------------------------


def _python_package(path: str) -> list[str]:
    """The package a file belongs to, as dotted-name parts from the project root."""
    parts = path[: -len(".py")].split("/")
    return parts[:-1]  # `pkg/__init__.py` and `pkg/mod.py` both live in `pkg`


def _resolve_from(package: list[str], node: ast.ImportFrom) -> "tuple[list[str] | None, str, str]":
    """(dotted parts of the module a `from` imports from, as spelled, top-level library name).

    The parts are None when a relative import climbs out of the project."""
    if node.level:
        if node.level - 1 > len(package):
            return None, "." * node.level + (node.module or ""), ""
        base = package[: len(package) - (node.level - 1)] + (node.module.split(".") if node.module else [])
        # A relative import is never a library.
        return base, "." * node.level + (node.module or ""), ""
    base = node.module.split(".") if node.module else []
    return base, node.module or "", base[0] if base else ""


def _python_imports(path: str, text: str, layer_names: frozenset[str]) -> Iterable[_Ref]:
    """Every import of a Python file, absolute or relative, resolved from the project root.

    `from pkg import name` may bring an attribute or a submodule: the submodule is looked at
    only when `name` is one of the layers (`from app.modules.pagos import infrastructure`),
    because that is the case the rule is about and an attribute may be a re-export.
    """
    tree = ast.parse(text, filename=path)
    package = _python_package(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                yield node.lineno, alias.name, tuple(parts), parts[0]
        elif isinstance(node, ast.ImportFrom):
            base, spelled, top = _resolve_from(package, node)
            if base is None:
                continue  # climbs out of the project: not ours to judge
            yield node.lineno, spelled, tuple(base), top
            for alias in node.names:
                if alias.name in layer_names:
                    joined = spelled if spelled.endswith(".") or not spelled else spelled + "."
                    yield node.lineno, f"{joined}{alias.name}", tuple(base) + (alias.name,), top


# --- TypeScript / JavaScript (and the script of .vue, .svelte and .astro) --------------------

_TS_IMPORT_PATTERNS = (
    re.compile(r"""\b(?:import|export)\b[^;'"]*?\bfrom\s*['"]([^'"\n]+)['"]""", re.DOTALL),
    re.compile(r"""\bimport\s*['"]([^'"\n]+)['"]"""),
    re.compile(r"""\bimport\s*\(\s*['"]([^'"\n]+)['"]\s*\)"""),
    re.compile(r"""\brequire\s*\(\s*['"]([^'"\n]+)['"]\s*\)"""),
)
_TS_EXTENSIONS = (".d.ts", ".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs", ".vue", ".svelte", ".astro")
_SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
_ASTRO_FRONTMATTER = re.compile(r"\A\s*---[ \t]*\n(.*?)\n---", re.DOTALL)


def _script_text(path: str, text: str) -> str:
    """For a single-file component only the code inside `<script>` (and an Astro frontmatter) counts.

    Every other character becomes blank but newlines stay, so a line number is still the file's."""
    if not path.endswith((".vue", ".svelte", ".astro")):
        return text
    ranges = [(m.start(1), m.end(1)) for m in _SCRIPT_BLOCK.finditer(text)]
    if path.endswith(".astro"):
        front = _ASTRO_FRONTMATTER.match(text)
        if front is not None:
            ranges.append((front.start(1), front.end(1)))
    ranges.sort()
    out: list[str] = []
    cursor = 0
    for start, end in ranges:
        out.append("\n" * text.count("\n", cursor, start))
        out.append(text[start:end])
        cursor = end
    out.append("\n" * text.count("\n", cursor))
    return "".join(out)


def _ts_target(path: str, spec: str, aliases: Mapping[str, str]) -> tuple[tuple[str, ...] | None, str]:
    """(segments of the target inside the project or None, top-level package for the domain rule)."""
    if spec.startswith("."):
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), spec))
        if resolved.startswith(".."):
            return None, spec
        return _ts_segments(resolved), spec
    for prefix, folder in aliases.items():
        if prefix and spec.startswith(prefix):
            return _ts_segments(folder + spec[len(prefix):]), spec
    first = spec.split("/")[0]
    if first in ("src", "app", "server"):
        return _ts_segments(spec), spec
    return None, spec


def _ts_segments(resolved: str) -> tuple[str, ...]:
    for extension in _TS_EXTENSIONS:
        if resolved.endswith(extension):
            resolved = resolved[: -len(extension)]
            break
    return tuple(part for part in resolved.split("/") if part and part != ".")


def _typescript_imports(path: str, text: str, aliases: Mapping[str, str]) -> Iterable[_Ref]:
    clean = _strip_c_comments(text)
    for pattern in _TS_IMPORT_PATTERNS:
        for match in pattern.finditer(clean):
            spec = match.group(1)
            line = _line_of(clean, match.start(1))
            segments, top = _ts_target(path, spec, aliases)
            yield line, spec, segments, top


# --- Go ---------------------------------------------------------------------------------------

_GO_BLOCK = re.compile(r"\bimport\s*\((.*?)\)", re.DOTALL)
_GO_SINGLE = re.compile(r"""^[ \t]*import[ \t]+(?:[\w.]+[ \t]+)?"([^"\n]+)\"""", re.MULTILINE)
_GO_SPEC = re.compile(r"""^[ \t]*(?:[\w.]+[ \t]+)?"([^"\n]+)\"""", re.MULTILINE)


def _go_imports(config: ArchitectureConfig, path: str, text: str) -> Iterable[_Ref]:
    if path.endswith("_test.go"):
        return
    clean = _strip_c_comments(text)
    specs: list[tuple[int, str]] = []
    for block in _GO_BLOCK.finditer(clean):
        for item in _GO_SPEC.finditer(block.group(1)):
            specs.append((_line_of(clean, block.start(1) + item.start(1)), item.group(1)))
    for item in _GO_SINGLE.finditer(clean):
        specs.append((_line_of(clean, item.start(1)), item.group(1)))
    marker = config.relative_modules_root
    for line, spec in sorted(specs):
        parts = tuple(spec.split("/"))
        target = None
        for index in range(len(parts) - len(marker) + 1):
            if parts[index : index + len(marker)] == marker:
                target = config.root_segments + parts[index:]
                break
        yield line, spec, target, spec


# --- Java and Kotlin -------------------------------------------------------------------------

_JVM_IMPORT = re.compile(r"^[ \t]*import[ \t]+(?:static[ \t]+)?([\w.]+?)(?:\.\*)?(?:[ \t]+as[ \t]+\w+)?[ \t]*;?[ \t]*$", re.MULTILINE)


def _jvm_imports(config: ArchitectureConfig, path: str, text: str) -> Iterable[_Ref]:
    clean = _strip_c_comments(text)
    package = tuple(config.namespace_root.split(".")) if config.namespace_root else ()
    modules_root = tuple(config.modules_root.split("/"))
    for match in _JVM_IMPORT.finditer(clean):
        spec = match.group(1)
        parts = tuple(spec.split("."))
        target = None
        if package and parts[: len(package)] == package:
            target = modules_root + parts[len(package):]
        yield _line_of(clean, match.start(1)), spec, target, spec


# --- C# -----------------------------------------------------------------------------------------

_CS_USING = re.compile(r"^[ \t]*(?:global[ \t]+)?using[ \t]+(?!static\b)(?:\w+[ \t]*=[ \t]*)?([\w.]+)[ \t]*;", re.MULTILINE)
_CS_PROJECT_REF = re.compile(r"""<ProjectReference\b[^>]*\bInclude\s*=\s*"([^"]+)\"""", re.IGNORECASE)
_CS_PACKAGE_REF = re.compile(r"""<PackageReference\b[^>]*\bInclude\s*=\s*"([^"]+)\"""", re.IGNORECASE)


def _csharp_refs(config: ArchitectureConfig, path: str, text: str) -> Iterable[_Ref]:
    modules_root = tuple(config.modules_root.split("/"))
    if path.endswith(".csproj"):
        for match in _CS_PROJECT_REF.finditer(text):
            spec = match.group(1).replace("\\", "/")
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), spec))
            if resolved.startswith(".."):
                continue
            project_dir = posixpath.dirname(resolved)
            yield _line_of(text, match.start(1)), spec, tuple(p for p in project_dir.split("/") if p), ""
        for match in _CS_PACKAGE_REF.finditer(text):
            yield _line_of(text, match.start(1)), match.group(1), None, match.group(1)
        return
    clean = _strip_c_comments(text)
    root = config.namespace_root
    for match in _CS_USING.finditer(clean):
        spec = match.group(1)
        parts = spec.split(".")
        target = None
        if root and parts[0] == root and len(parts) > 1:
            module = parts[1]
            tail = (f"{module}.{parts[2]}",) + tuple(parts[3:]) if len(parts) > 2 else ()
            target = modules_root + (module,) + tail
        yield _line_of(clean, match.start(1)), spec, target, spec


# --- Rust -------------------------------------------------------------------------------------

_RUST_USE = re.compile(r"\buse\s+([^;]+);", re.DOTALL)


def _rust_expand(path: str) -> list[str]:
    """`a::{b, c::{d, e}}` -> `a::b`, `a::c::d`, `a::c::e`; `as` renames and `*` are dropped."""
    path = path.strip()
    if "{" not in path:
        path = re.sub(r"\s+as\s+\w+$", "", path)
        return [path[: -len("::*")] if path.endswith("::*") else path]
    head, _, rest = path.partition("{")
    rest = rest[: rest.rindex("}")]
    items: list[str] = []
    depth = 0
    current = ""
    for char in rest:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        if char == "," and depth == 0:
            items.append(current)
            current = ""
        else:
            current += char
    items.append(current)
    base = head.rstrip(":")
    expanded: list[str] = []
    for item in items:
        item = item.strip()
        if not item:
            continue
        if item == "self":
            expanded.append(base)
            continue
        for sub in _rust_expand(item):
            expanded.append(f"{base}::{sub}" if base else sub)
    return expanded


def _rust_uses(config: ArchitectureConfig, path: str, text: str) -> Iterable[_Ref]:
    clean = _strip_c_comments(text)
    current = tuple(part for part in path[: -len(".rs")].split("/") if part)
    if current and current[-1] == "mod":
        current = current[:-1]
    crate_root = config.root_segments + ("src",)
    for match in _RUST_USE.finditer(clean):
        body = " ".join(match.group(1).split())
        line = _line_of(clean, match.start(1))
        for spelled in _rust_expand(body):
            parts = [p for p in spelled.split("::") if p]
            if not parts:
                continue
            if parts[0] == "crate":
                target = crate_root + tuple(parts[1:])
            elif parts[0] == "super":
                base = list(current)
                rest = list(parts)
                while rest and rest[0] == "super":
                    rest.pop(0)
                    if base:
                        base.pop()
                target = tuple(base) + tuple(rest)
            elif parts[0] == "self":
                target = current + tuple(parts[1:])
            else:
                yield line, spelled, None, spelled.replace("::", "/")
                continue
            yield line, spelled, target, ""


# --- PHP --------------------------------------------------------------------------------------

_PHP_USE = re.compile(r"^[ \t]*use[ \t]+(?:function[ \t]+|const[ \t]+)?([\\\w]+?)(?:\\\{[^}]*\})?(?:[ \t]+as[ \t]+\w+)?[ \t]*;", re.MULTILINE)


def _php_uses(config: ArchitectureConfig, path: str, text: str) -> Iterable[_Ref]:
    clean = _strip_c_comments(text)
    root = config.namespace_root
    for match in _PHP_USE.finditer(clean):
        spec = match.group(1).strip("\\")
        parts = spec.split("\\")
        target = None
        if root and parts[0] == root:
            target = config.root_segments + ("app",) + tuple(parts[1:])
        yield _line_of(clean, match.start(1)), spec, target, spec


# --- the text the agent reads ---------------------------------------------------------------


def canonical_table(spec: RuleSpec, root: str = "") -> str:
    """A table that maps the names of the stack's language to the canonical responsibilities."""
    rows = ["| Nombre en este stack | Responsabilidad canónica |", "|---|---|"]
    for role in spec.layers or BACKEND_LAYERS:
        names = spec.roles.get(role) or (role,)
        shown = " o ".join(f"`{n}`" for n in names)
        rows.append(f"| {shown} | {CANONICAL.get(role, role)} |")
    contract = spec.public_contract
    rows.append(f"| {_code(contract)} | {CANONICAL['contract']} |")
    return "\n".join(rows)


def _code(text: str) -> str:
    """A file or folder in code style; a sentence (the root package of a module...) as it is."""
    return text if " " in text else f"`{text}`"


def _layer_bullets(spec: RuleSpec) -> list[str]:
    bullets = []
    for role in spec.layers or BACKEND_LAYERS:
        names = spec.roles.get(role) or (role,)
        shown = " o ".join(f"`{n}`" if _stem(n) != n else f"`{n}/`" for n in names)
        bullets.append(f"- {shown}: {ROLE_TEXT.get(role, role)}.")
    bullets.append(f"- **Un único punto público** ({_code(spec.public_contract)}): lo único que otros módulos pueden usar.")
    return bullets


def render_architecture_markdown(template: str, items: list[tuple[str, str, RuleSpec, str]]) -> str:
    """`architecture.md`: the language-neutral rule of the template, then the structure of each
    stack with its own names and a table that maps them to the canonical responsibilities."""
    heading = "## Estructura por stack"
    head = template.split(heading)[0].rstrip("\n")
    blocks = [head, "", heading, ""]
    for component, stack_id, spec, root in items:
        where = f" (en `{root}/`)" if root else ""
        blocks += [f"### {stack_id} — {component}{where}", "", "```text", spec.tree.rstrip("\n"), "```", ""]
        blocks += [
            f"Módulos en `{(root + '/' if root else '') + spec.module_pattern.lstrip('/')}`; contrato público: {spec.public_contract}.",
            "",
            "Cada módulo tiene:",
            "",
            *_layer_bullets(spec),
            "",
            canonical_table(spec, root),
            "",
        ]
        if spec.notes:
            blocks += [spec.notes, ""]
        if spec.complementary:
            blocks += [f"Test complementario (el gate sigue siendo `rapid arch check`): {spec.complementary}.", ""]
    tail = template.split(heading, 1)[1] if heading in template else ""
    verification = tail[tail.find("\n## Verificación"):] if "\n## Verificación" in tail else ""
    return "\n".join(blocks).rstrip("\n") + "\n" + verification

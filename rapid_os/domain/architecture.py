"""Modular-monolith architecture rule and its import checker. Pure: no I/O.

The rule (`.rapid-os/standards/architecture.json`) says where the modules live, which layers a
layer may import and which libraries the domain must never touch. The checker takes the config
and the source text of the files under `modules_root` and `shared_root` and returns the
violations. Python is read with `ast`, TypeScript/JavaScript with regular expressions: nothing
is executed.
"""

from __future__ import annotations

import ast
import posixpath
import re
from dataclasses import dataclass
from typing import Iterable, Mapping

ARCHITECTURE_SCHEMA_VERSION = 1
ARCHITECTURE_CODE = "RAPID1420"
LANGUAGES = ("python", "typescript")
LAYER_NAMES = ("api", "application", "domain", "infrastructure")
# Stacks that get the rule (the others - docs-modern, frontend-creative, generic - do not).
MODULAR_STACKS: Mapping[str, str] = {
    "python-api": "python",
    "python-ai": "python",
    "nodejs-ai": "typescript",
    "web-modern": "typescript",
}
SOURCE_SUFFIXES: Mapping[str, tuple[str, ...]] = {
    "python": (".py",),
    "typescript": (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"),
}

RULE_LAYER = "layer"
RULE_CROSS_MODULE = "cross_module"
RULE_SHARED = "shared"
RULE_DOMAIN_FORBIDDEN = "domain_forbidden_import"


class ArchitectureConfigError(ValueError):
    """Invalid `architecture.json` (reported with RAPID1420)."""

    code = ARCHITECTURE_CODE


def default_config(stack_id: str) -> dict:
    """The machine-readable rule for a stack, or `{}` when the stack does not get one."""
    language = MODULAR_STACKS.get(stack_id)
    if language is None:
        return {}
    python = language == "python"
    return {
        "schema_version": ARCHITECTURE_SCHEMA_VERSION,
        "language": language,
        "modules_root": "app/modules" if python else "src/modules",
        "shared_root": "app/shared" if python else "src/shared",
        "public_entry": "public.py" if python else "index.ts",
        "layers": {
            "api": ["application", "domain"],
            "application": ["domain"],
            "domain": [],
            "infrastructure": ["application", "domain"],
        },
        "domain_forbidden_imports": (
            ["fastapi", "sqlalchemy", "starlette", "httpx"]
            if python
            else ["next", "react", "express", "@prisma/client"]
        ),
    }


@dataclass(frozen=True)
class ArchitectureConfig:
    language: str
    modules_root: str
    shared_root: str
    public_entry: str
    layers: Mapping[str, tuple[str, ...]]
    domain_forbidden_imports: tuple[str, ...]

    @property
    def public_stem(self) -> str:
        return posixpath.splitext(self.public_entry)[0]

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
        paths = {}
        for key in ("modules_root", "shared_root", "public_entry"):
            value = data.get(key)
            if not isinstance(value, str) or not value.strip() or value.startswith("/") or ".." in value.split("/"):
                raise fail(f"{key} debe ser una ruta relativa no vacía.")
            paths[key] = value.strip().strip("/")
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
        return cls(
            language=language,
            modules_root=paths["modules_root"],
            shared_root=paths["shared_root"],
            public_entry=paths["public_entry"],
            layers=layers,
            domain_forbidden_imports=tuple(forbidden),
        )


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

    @property
    def ok(self) -> bool:
        return not self.violations


# --- where a file or an import target lives -------------------------------------------------


@dataclass(frozen=True)
class _Place:
    """A path inside the tree: `kind` is `module`, `shared` or `other`."""

    kind: str
    module: str | None = None
    layer: str | None = None  # first segment under the module, "" for the module's own files
    rest: tuple[str, ...] = ()  # the segments after the module (the layer first)


def _locate(config: ArchitectureConfig, segments: tuple[str, ...]) -> _Place:
    modules_root = tuple(config.modules_root.split("/"))
    shared_root = tuple(config.shared_root.split("/"))
    if segments[: len(shared_root)] == shared_root:
        return _Place("shared")
    if segments[: len(modules_root)] == modules_root and len(segments) > len(modules_root):
        rest = segments[len(modules_root) + 1 :]
        return _Place("module", module=segments[len(modules_root)], layer=_stem(rest[0]) if rest else "", rest=rest)
    return _Place("other")


def _stem(segment: str) -> str:
    """`public.py` -> `public`; a directory name has no extension to lose."""
    return posixpath.splitext(segment)[0] if "." in segment else segment


def _is_public(config: ArchitectureConfig, rest: tuple[str, ...]) -> bool:
    """The module itself or its public entry (and what is imported from it); never one of its layers."""
    return not rest or _stem(rest[0]) == config.public_stem


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
    if source.layer == "domain" and any(
        top_package == lib or top_package.startswith(lib + "/") for lib in config.domain_forbidden_imports
    ):
        found.append(
            Violation(
                RULE_DOMAIN_FORBIDDEN, file, line, spelled,
                f"domain no puede importar '{top_package}' (framework web, ORM o cliente externo); "
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
            if not _is_public(config, target.rest):
                found.append(
                    Violation(
                        RULE_CROSS_MODULE, file, line, spelled,
                        f"el módulo '{source.module}' solo puede importar el punto público "
                        f"({config.public_entry}) del módulo '{target.module}', no su capa "
                        f"'{target.layer or target.rest[0]}'",
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


def _dedupe(violations: Iterable[Violation]) -> list[Violation]:
    seen: set[tuple[str, int, str]] = set()
    unique: list[Violation] = []
    for item in violations:
        key = (item.file, item.line, item.rule)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def check_architecture(
    config: ArchitectureConfig, sources: Mapping[str, str]
) -> ArchitectureReport:
    """`sources` maps a project-relative posix path to its text. Only files under `modules_root`
    and `shared_root` are expected; anything else is ignored."""
    violations: list[Violation] = []
    skipped: list[str] = []
    modules: set[str] = set()
    checked = 0
    for path in sorted(sources):
        place = _locate(config, tuple(path.split("/")))
        if place.kind == "other":
            continue
        if place.kind == "module" and place.module:
            modules.add(place.module)
        checked += 1
        try:
            if config.language == "python":
                refs = list(_python_imports(path, sources[path], frozenset(config.layers)))
            else:
                refs = list(_typescript_imports(path, sources[path]))
        except SyntaxError as exc:
            skipped.append(f"{path}: no se pudo leer ({exc.msg}, línea {exc.lineno})")
            continue
        for line, spelled, target_segments, top_package in refs:
            violations.extend(
                _violations_for_target(config, place, path, line, spelled, target_segments, top_package)
            )
    return ArchitectureReport(
        language=config.language,
        modules=tuple(sorted(modules)),
        checked_files=checked,
        violations=tuple(_dedupe(violations)),
        skipped=tuple(skipped),
    )


# --- Python ---------------------------------------------------------------------------------

# (line, spelled import, segments of the target inside the project or None, top-level package)
_Ref = tuple[int, str, "tuple[str, ...] | None", str]


def _python_package(path: str) -> list[str]:
    """The package a file belongs to, as dotted-name parts from the project root."""
    parts = path[: -len(".py")].split("/")
    return parts[:-1]  # `pkg/__init__.py` and `pkg/mod.py` both live in `pkg`


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
            if node.level:
                if node.level - 1 > len(package):
                    continue  # climbs out of the project: not ours to judge
                base = package[: len(package) - (node.level - 1)] + (node.module.split(".") if node.module else [])
                spelled = "." * node.level + (node.module or "")
                top = ""  # a relative import is never a library
            else:
                base = node.module.split(".") if node.module else []
                spelled = node.module or ""
                top = base[0] if base else ""
            yield node.lineno, spelled, tuple(base), top
            for alias in node.names:
                if alias.name in layer_names:
                    joined = spelled if spelled.endswith(".") or not spelled else spelled + "."
                    yield node.lineno, f"{joined}{alias.name}", tuple(base) + (alias.name,), top


# --- TypeScript / JavaScript ----------------------------------------------------------------

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"(^|[\s;{}()])//[^\n]*")
_TS_IMPORT_PATTERNS = (
    re.compile(r"""\b(?:import|export)\b[^;'"]*?\bfrom\s*['"]([^'"\n]+)['"]""", re.DOTALL),
    re.compile(r"""\bimport\s*['"]([^'"\n]+)['"]"""),
    re.compile(r"""\bimport\s*\(\s*['"]([^'"\n]+)['"]\s*\)"""),
    re.compile(r"""\brequire\s*\(\s*['"]([^'"\n]+)['"]\s*\)"""),
)
_TS_EXTENSIONS = (".d.ts", ".tsx", ".ts", ".jsx", ".js", ".mjs", ".cjs")


def _strip_ts_comments(text: str) -> str:
    text = _BLOCK_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return _LINE_COMMENT.sub(lambda m: m.group(1), text)


def _ts_target(path: str, spec: str) -> tuple[tuple[str, ...] | None, str]:
    """(segments of the target inside the project or None, top-level package for the domain rule)."""
    if spec.startswith("."):
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), spec))
        if resolved.startswith(".."):
            return None, spec
        return _ts_segments(resolved), spec
    if spec.startswith("@/"):
        return _ts_segments("src/" + spec[2:]), spec
    first = spec.split("/")[0]
    if first in ("src", "app"):
        return _ts_segments(spec), spec
    return None, spec


def _ts_segments(resolved: str) -> tuple[str, ...]:
    for extension in _TS_EXTENSIONS:
        if resolved.endswith(extension):
            resolved = resolved[: -len(extension)]
            break
    return tuple(part for part in resolved.split("/") if part and part != ".")


def _typescript_imports(path: str, text: str) -> Iterable[_Ref]:
    clean = _strip_ts_comments(text)
    for pattern in _TS_IMPORT_PATTERNS:
        for match in pattern.finditer(clean):
            spec = match.group(1)
            line = clean.count("\n", 0, match.start(1)) + 1
            segments, top = _ts_target(path, spec)
            yield line, spec, segments, top

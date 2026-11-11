"""The root cause a bugfix spec declares (H-67): where the defect lives and how it was found.

A test that passes is not a fix: in a bugfix run the agent first names the cause (`root_cause`), the reproduction
test exercises that code, and the hand-over separates the change at the cause from additional defenses. Rapid OS
checks that the declared file exists in the repository; it cannot check that the explanation is right, only make
it visible to the person who approves."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

ROOT_CAUSE_CODE = "RAPID1438"
ROOT_CAUSE_KEYS = ("file", "symbol", "line", "how_found", "explanation")
ROOT_CAUSE_SHAPE = (
    '"root_cause": {"file": "<ruta del archivo>", "symbol": "<función o clase>" o "line": <n>, '
    '"how_found": "git blame | git log -S | traza del test | lectura del código", "explanation": "<por qué falla>"}'
)


@dataclass(frozen=True)
class RootCause:
    file: str
    how_found: str
    explanation: str
    symbol: str = ""
    line: int | None = None

    def __post_init__(self):
        for name in ("file", "how_found", "explanation"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"root_cause.{name} must be a non-empty string")
            object.__setattr__(self, name, value.strip())
        if not isinstance(self.symbol, str):
            raise ValueError("root_cause.symbol must be a string")
        object.__setattr__(self, "symbol", self.symbol.strip())
        if self.line is not None and (isinstance(self.line, bool) or not isinstance(self.line, int) or self.line < 1):
            raise ValueError("root_cause.line must be a positive integer")
        if not self.symbol and self.line is None:
            raise ValueError("root_cause needs symbol or line")
        object.__setattr__(self, "file", normalize_root_cause_path(self.file))

    @property
    def location(self) -> str:
        """`file:symbol`, `file:line` or both, as a person reads it."""
        parts = [self.file]
        if self.symbol:
            parts.append(self.symbol)
        if self.line is not None:
            parts.append(f"línea {self.line}")
        return " · ".join(parts)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"file": self.file}
        if self.symbol:
            payload["symbol"] = self.symbol
        if self.line is not None:
            payload["line"] = self.line
        payload["how_found"] = self.how_found
        payload["explanation"] = self.explanation
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "RootCause":
        if not isinstance(payload, Mapping):
            raise ValueError("root_cause must be an object")
        unknown = set(payload) - set(ROOT_CAUSE_KEYS)
        if unknown:
            raise ValueError(f"root_cause has unexpected fields: {sorted(unknown)}")
        return cls(
            file=payload.get("file", ""),  # type: ignore[arg-type]
            how_found=payload.get("how_found", ""),  # type: ignore[arg-type]
            explanation=payload.get("explanation", ""),  # type: ignore[arg-type]
            symbol=payload.get("symbol", "") or "",  # type: ignore[arg-type]
            line=payload.get("line"),  # type: ignore[arg-type]
        )


def normalize_root_cause_path(raw: str) -> str:
    """A relative POSIX path inside the project; raises ValueError for an absolute path or one that escapes it."""
    text = str(raw).strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    path = PurePosixPath(text)
    if not text or path.is_absolute() or (len(text) > 1 and text[1] == ":") or ".." in path.parts:
        raise ValueError("root_cause.file must be a path relative to the project, inside it")
    return path.as_posix()


def root_cause_error(raw: object, project_root: Path) -> str | None:
    """RAPID1438 when a bugfix spec's `root_cause` is missing or invalid, naming what is missing; else None."""
    if raw is None or raw == {} or raw == "":
        return (
            f"{ROOT_CAUSE_CODE} Una spec bugfix requiere root_cause: localiza la causa antes de redactar la spec "
            f"(git blame, git log -S, la traza de un test o la lectura del código) y añádela: {ROOT_CAUSE_SHAPE}."
        )
    if isinstance(raw, RootCause):
        cause = raw
    else:
        if not isinstance(raw, Mapping):
            return f"{ROOT_CAUSE_CODE} root_cause debe ser un objeto: {ROOT_CAUSE_SHAPE}."
        missing = [key for key in ("file", "how_found", "explanation") if not str(raw.get(key) or "").strip()]
        if not str(raw.get("symbol") or "").strip() and raw.get("line") in (None, ""):
            missing.append("symbol o line")
        if missing:
            return f"{ROOT_CAUSE_CODE} A root_cause le falta: {', '.join(missing)}. Forma: {ROOT_CAUSE_SHAPE}."
        try:
            cause = RootCause.from_dict(raw)
        except ValueError as exc:
            return f"{ROOT_CAUSE_CODE} root_cause no es válido: {exc}. Forma: {ROOT_CAUSE_SHAPE}."
    target = Path(project_root) / cause.file
    if cause.file.split("/")[0] == ".rapid-os" or not target.is_file():
        return (
            f"{ROOT_CAUSE_CODE} root_cause.file '{cause.file}' no existe en el repositorio: indica la ruta, relativa a "
            "la raíz del proyecto, del archivo donde está el defecto."
        )
    return None

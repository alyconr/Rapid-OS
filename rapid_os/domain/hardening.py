"""Validation for the structured findings required by hardening specs."""

import difflib
import re
from pathlib import Path
from typing import Iterable, Mapping

from rapid_os.domain.cvss4 import score_vector


FINDING_CODE = "RAPID1343"
_CWE = re.compile(r"^CWE-\d+$")
_FINDING_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _citations(security_text: str) -> list[str]:
    """Each comma-separated item inside the square brackets of security.md (a full citation)."""
    found: dict[str, str] = {}
    for group in re.findall(r"\[([^\]]+)\]", security_text):
        for item in group.split(","):
            item = item.strip()
            if item:
                found.setdefault(item.casefold(), item)
    return list(found.values())


def _similar(reference: str, citations: list[str]) -> list[str]:
    needle = reference.casefold()
    close = [c for c in citations if needle in c.casefold() or c.casefold() in needle]
    for c in difflib.get_close_matches(reference, citations, n=5, cutoff=0.4):
        if c not in close:
            close.append(c)
    return close[:5]


def validate_hardening_findings(
    findings: Iterable[Mapping[str, object]], security_file: Path
) -> str | None:
    """Return a RAPID1343 message when a hardening finding is invalid."""
    entries = list(findings)
    if not entries:
        return f"{FINDING_CODE} Una spec hardening requiere al menos un hallazgo en findings."
    try:
        security_text = security_file.read_text(encoding="utf-8")
    except OSError as exc:
        first = entries[0] if isinstance(entries[0], Mapping) else {}
        label = str(first.get("id") or first.get("title") or 1)
        return (
            f"{FINDING_CODE} Hallazgo {label}: no se puede validar standard_ref; falta {security_file.as_posix()}: {exc}. "
            "Ejecuta rapid init para crear la base de seguridad."
        )
    citations = _citations(security_text)
    by_key = {c.casefold() for c in citations}
    for index, finding in enumerate(entries, 1):
        if not isinstance(finding, Mapping):
            return f"{FINDING_CODE} Hallazgo {index}: debe ser un objeto"
        label = str(finding.get("id") or finding.get("title") or index)
        def invalid(reason: str) -> str:
            return f"{FINDING_CODE} Hallazgo {label}: {reason}"
        if not _FINDING_ID.fullmatch(str(finding.get("id", ""))):
            return invalid("id debe ser un identificador corto (letras, números, punto, guion o guion bajo)")
        for key in ("title", "standard_ref"):
            if not isinstance(finding.get(key), str) or not str(finding[key]).strip():
                return invalid(f"{key} es obligatorio")
        cwe = str(finding.get("cwe", ""))
        if not _CWE.fullmatch(cwe):
            return invalid("cwe debe tener el formato CWE-<n>")
        try:
            score, expected = score_vector(finding.get("cvss_v4_vector", ""))
        except ValueError as exc:
            return invalid(str(exc))
        severity = str(finding.get("severity", "")).strip().casefold()
        if severity != expected:
            return invalid(
                f"severity no corresponde a la puntuación CVSS v4.0 {score:.1f} del vector: "
                f"esperada {expected}, recibida {severity or 'vacío'}"
            )
        reference = str(finding["standard_ref"]).strip()
        if reference.casefold() not in by_key:
            similar = _similar(reference, citations)
            hint = f"; citas parecidas: {', '.join(similar)}" if similar else ""
            return invalid(
                f"standard_ref {finding['standard_ref']!r} no es una cita completa de {security_file}{hint}"
            )
    return None

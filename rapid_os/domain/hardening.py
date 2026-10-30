"""Validation for the structured findings required by hardening specs."""

import re
from pathlib import Path
from typing import Iterable, Mapping


FINDING_CODE = "RAPID1343"
_CWE = re.compile(r"^CWE-\d+$")
_FINDING_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_BASE_METRICS = {
    "AV": set("NALP"), "AC": set("LH"), "AT": set("NP"),
    "PR": set("NLH"), "UI": set("NPA"),
    "VC": set("HLN"), "VI": set("HLN"), "VA": set("HLN"),
    "SC": set("HLN"), "SI": set("HLN"), "SA": set("HLN"),
}
_BASE_ORDER = tuple(_BASE_METRICS)


def _parse_vector(vector: str) -> dict[str, str]:
    if not isinstance(vector, str) or not vector.startswith("CVSS:4.0/"):
        raise ValueError("cvss_v4_vector debe empezar por CVSS:4.0/")
    metrics: dict[str, str] = {}
    for part in vector[len("CVSS:4.0/"):].split("/"):
        key, sep, value = part.partition(":")
        if not sep or key not in _BASE_METRICS or value not in _BASE_METRICS[key] or key in metrics:
            raise ValueError(f"vector CVSS v4.0 inválido cerca de {part!r}")
        metrics[key] = value
    if tuple(metrics) != _BASE_ORDER:
        raise ValueError("el vector debe incluir, en orden, todas las métricas base CVSS v4.0")
    return metrics


def _severity_allowed(metrics: Mapping[str, str]) -> set[str]:
    """Bound severity to impact class without pretending to score CVSS."""
    impacts = [metrics[key] for key in ("VC", "VI", "VA", "SC", "SI", "SA")]
    if "H" in impacts:
        return {"high", "critical"}
    if "L" in impacts:
        return {"low", "medium", "high"}
    return {"none", "low"}


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
    references = [item.casefold() for item in re.findall(r"\[([^\]]+)\]", security_text)]
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
            metrics = _parse_vector(finding.get("cvss_v4_vector", ""))
        except ValueError as exc:
            return invalid(str(exc))
        severity = str(finding.get("severity", "")).strip().casefold()
        allowed = _severity_allowed(metrics)
        if severity not in allowed:
            return invalid(
                "severity debe ser coherente con los impactos del vector "
                f"(valores permitidos: {', '.join(sorted(allowed))}; recibido {severity or 'vacío'})"
            )
        reference = str(finding["standard_ref"]).strip().casefold()
        if not any(reference in cited for cited in references):
            return invalid(f"standard_ref {finding['standard_ref']!r} no aparece en {security_file}")
    return None

"""`rapid arch check` for a stack with no imports to read: it asks the stack's own tool.

Ruby on Rails loads its code by convention, so there is nothing in the source text for a static
reader. Its rule delegates to packwerk (`bin/packwerk check`). When packwerk is not there the check
does not pass: a gate that cannot look must not look satisfied.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

PACKWERK_MISSING = (
    "RAPID1420 packwerk no está disponible: Ruby on Rails no tiene imports que leer y la regla delega en "
    "`bin/packwerk check`. Instálalo (`bundle add packwerk --group development && bundle binstub packwerk`) "
    "y vuelve a ejecutar `rapid arch check`; mientras tanto el gate no se da por satisfecho."
)
SUPPORTED_DELEGATES = ("packwerk",)


@dataclass(frozen=True)
class DelegateResult:
    ok: bool
    output: str
    missing: bool = False


def run_delegate(delegate: str, project_root: Path | str) -> DelegateResult:
    root = Path(project_root)
    if delegate != "packwerk":
        return DelegateResult(False, f"RAPID1420 herramienta delegada desconocida: {delegate}.", missing=True)
    binstub = root / "bin" / "packwerk"
    if binstub.is_file():
        command = ["ruby", str(binstub), "check"] if os.name == "nt" else [str(binstub), "check"]
        if os.name == "nt" and shutil.which("ruby") is None:
            return DelegateResult(False, PACKWERK_MISSING, missing=True)
    elif shutil.which("packwerk"):
        command = ["packwerk", "check"]
    else:
        return DelegateResult(False, PACKWERK_MISSING, missing=True)
    try:
        proc = subprocess.run(
            command, cwd=str(root), capture_output=True, text=True, check=False, shell=False, timeout=600
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DelegateResult(False, f"RAPID1420 no se pudo ejecutar packwerk: {exc}", missing=True)
    output = "\n".join(part for part in (proc.stdout.strip(), proc.stderr.strip()) if part)
    return DelegateResult(proc.returncode == 0, output)

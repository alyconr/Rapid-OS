"""A fingerprint of the working tree, to notice code that changed after the last verification.

Every `rapid check` records one when it ends. `rapid next` (before asking for approval), `rapid approve`
and `rapid finish` compare the tree with the one the last `gate.tests` check saw: if a test was deleted or a
file edited in between, nothing verified that code, so they ask for a new check and name the files.

The fingerprint is the set of files that differ from `HEAD` (tracked changes, deletions and untracked files,
without `.rapid-os/` and without tool artifacts) with the SHA-256 of each one. The map is kept in
`.rapid-os/scratch/trees/<run>/<digest>.json` (not versioned); the digest goes in the evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from rapid_os.core.filesystem import safe_write_text
from rapid_os.domain.file_changes import is_tool_artifact, normalize_path
from rapid_os.orchestration.git import run_git

MISSING = "<missing>"  # a tracked file that was deleted
TREES_DIR = ("scratch", "trees")


def working_tree_snapshot(cwd: Path | str) -> dict[str, str] | None:
    """`{path: sha256}` of the files that differ from HEAD, or None when git cannot answer."""
    root = Path(cwd)
    try:
        has_head = run_git(root, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
        tracked = run_git(root, "diff", "HEAD", "--name-only") if has_head else run_git(root, "ls-files")
        untracked = run_git(root, "ls-files", "--others", "--exclude-standard")
    except Exception:
        return None
    if tracked.returncode != 0 or untracked.returncode != 0:
        return None
    paths = {normalize_path(line) for line in tracked.stdout.splitlines() + untracked.stdout.splitlines()}
    snapshot: dict[str, str] = {}
    for path in sorted(p for p in paths if p):
        if path.startswith(".rapid-os/") or is_tool_artifact(path):
            continue
        target = root / path
        try:
            snapshot[path] = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else MISSING
        except OSError:
            snapshot[path] = MISSING
    return snapshot


def digest(snapshot: Mapping[str, str]) -> str:
    body = "\n".join(f"{path}\0{sha}" for path, sha in sorted(snapshot.items()))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _tree_file(rapid_dir: Path | str, run_id: str, tree_digest: str) -> Path:
    return Path(rapid_dir, *TREES_DIR, run_id, f"{tree_digest}.json")


def save_snapshot(rapid_dir: Path | str, run_id: str, snapshot: Mapping[str, str]) -> str:
    """Store the map under its digest and return the digest."""
    tree_digest = digest(snapshot)
    safe_write_text(
        _tree_file(rapid_dir, run_id, tree_digest),
        json.dumps(dict(sorted(snapshot.items())), indent=0),
        encoding="utf-8",
        allow_overwrite=True,
        create_parents=True,
    )
    return tree_digest


def load_snapshot(rapid_dir: Path | str, run_id: str, tree_digest: str) -> dict[str, str] | None:
    try:
        data = json.loads(_tree_file(rapid_dir, run_id, tree_digest).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def changed_files(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    """Files added, removed or edited between two fingerprints."""
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


@dataclass(frozen=True)
class StaleVerification:
    """The tree is not the one `gate.tests` was last checked on."""

    files: tuple[str, ...]
    gate_id: str
    command: tuple[str, ...] | None

    def message(self, code: str = "RAPID1423") -> str:
        shown = ", ".join(self.files[:8]) + (f" (+{len(self.files) - 8} más)" if len(self.files) > 8 else "")
        how = (
            f"`rapid check --gate {self.gate_id} -- {' '.join(self.command)}`"
            if self.command
            else f"`rapid check --gate {self.gate_id} -- <comando de test>`"
        )
        return (
            f"{code} El código cambió desde el último check de {self.gate_id}: {shown}. Nada verificó esos cambios. "
            f"Vuelve a ejecutar {how} y repite el comando."
        )


def stale_verification(
    rapid_dir: Path | str,
    cwd: Path | str,
    run_id: str,
    test_gate_ids: Sequence[str],
    evidence: Sequence,
    test_command: Sequence[str] | None = None,
) -> StaleVerification | None:
    """None when the tree is the one the last `gate.tests` check saw, or when that cannot be told
    (no such check, a check that predates the fingerprint, or git cannot answer)."""
    last = None
    for item in evidence:
        if item.kind.value in ("test_result", "command_result") and set(item.gate_ids) & set(test_gate_ids):
            if item.payload.get("expectation") != "fail" and item.payload.get("tree"):
                last = item
    if last is None:
        return None
    before = load_snapshot(rapid_dir, run_id, str(last.payload["tree"]))
    now = working_tree_snapshot(cwd)
    if before is None or now is None:
        return None
    changed = changed_files(before, now)
    if not changed:
        return None
    gate_id = next(g for g in last.gate_ids if g in test_gate_ids)
    return StaleVerification(tuple(changed), gate_id, tuple(test_command) if test_command else None)

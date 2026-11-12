"""Bugfix (H-67): the reproduction test must fail where the bug lives, not only pass where the fix is.

When the fix task of a bugfix run is closed, Rapid OS builds a temporary git worktree with the tree of the run's
baseline (`start_head`) plus the test files the run added or changed, runs the project's test command there and
requires it to fail; on the current tree it must pass (the usual `task done` check). The result is its own
evidence (`reproduction_holds`). A test that passes on the baseline does not reproduce the bug: the task stays open.
The temporary worktree is always removed."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Sequence

from rapid_os.domain.execution import TaskContract
from rapid_os.orchestration.check import parse_failed_test_files, parse_test_summary, resolve_executable
from rapid_os.orchestration.git import run_git
from rapid_os.orchestration.session import Session, observed_changes
from rapid_os.orchestration.workspace import REPRODUCTION_WORKTREE_PREFIX

REPRODUCTION_LABEL = "reproduction_holds"
REPRODUCTION_CODE = "RAPID1439"

# Directories a test run needs that git does not check out (dependencies, virtualenvs): linked, never copied.
DEPENDENCY_DIRS = ("node_modules", ".venv", "venv")
# Local files git ignores that integration tests read (DATABASE_URL...): copied.
LOCAL_FILES = (".env",)

_TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "testing", "e2e", "integration_tests", "test_integration"}
_TEST_SUFFIX = re.compile(r"[_.-](test|tests|spec|specs)\.[A-Za-z0-9]+$", re.IGNORECASE)
_TEST_CAMEL = re.compile(r"[a-z0-9](Test|Tests|Spec|IT)\.[A-Za-z0-9]+$")


def is_test_path(path: str) -> bool:
    """A test file by its path: under a test directory, or named like one (`test_x.py`, `x.test.ts`, `XTest.java`)."""
    parts = path.replace("\\", "/").split("/")
    name = parts[-1]
    if any(part.lower() in _TEST_DIRS for part in parts[:-1]):
        return True
    lower = name.lower()
    return (
        lower.startswith("test_")
        or lower.startswith("test.")
        or lower in ("conftest.py", "tests.py", "test.py")
        or bool(_TEST_SUFFIX.search(name))
        or bool(_TEST_CAMEL.search(name))
    )


def reproduction_task_id(tasks: Sequence[TaskContract]) -> str | None:
    """The task that writes the red test: the first one that says it reproduces, else the first task (older specs)."""
    for task in tasks:
        if "reproduc" in task.description.casefold():
            return task.id
    return tasks[0].id if tasks else None


def fix_task_id(tasks: Sequence[TaskContract]) -> str | None:
    """The task that corrects the cause: the one right after the reproduction task."""
    repro = reproduction_task_id(tasks)
    ids = [task.id for task in tasks]
    if repro is None or ids.index(repro) + 1 >= len(ids):
        return None
    return ids[ids.index(repro) + 1]


@dataclass
class ReproductionOutcome:
    # holds: on the baseline tree the run's tests make more tests fail than fail without them (and, when the runner
    # names them, one of the failing tests is the run's); not_reproduced: they do not, only other tests fail, or no
    # test changed; inconclusive: an output without a test summary to count; unavailable: there is no baseline tree
    # to build (no commit at start). The exit code alone never proves a reproduction.
    status: str
    message: str
    test_files: list[str] = field(default_factory=list)
    exit_code: int | None = None
    counts: dict[str, int] | None = None
    log_path: Path | None = None
    baseline_failed: int | None = None
    failed_tests: list[str] = field(default_factory=list)


def _same_test_file(named: str, test_file: str) -> bool:
    """A failed test the runner names (`tests/test_x.py`, `tests/test_x` for unittest) is in a file of the run.

    Paths may be relative to another directory than the repository root: one must end with the other."""
    def stem(path: str) -> str:
        path = path.replace("\\", "/").strip("/")
        name = path.rsplit("/", 1)[-1]
        return path[: len(path) - len(name)] + (name.split(".", 1)[0] if "." in name else name)

    a, b = stem(named), stem(test_file)
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def baseline_failed_count(evidence) -> int | None:
    """Failed tests of the run's own baseline (`gate.baseline`, taken at start on the tree without the run's tests),
    when that evidence counted them; None otherwise."""
    for ev in reversed(list(evidence)):
        payload = ev.payload or {}
        if "gate.baseline" in ev.gate_ids and "failed" in payload and payload.get("counted"):
            return int(payload["failed"])
    return None


def _run_tests(test_command: Sequence[str], cwd: Path, timeout: float) -> tuple[str, int]:
    try:
        result = subprocess.run(
            resolve_executable(list(test_command)), cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", check=False, shell=False, timeout=timeout,
        )
        return result.stdout or "", result.returncode
    except FileNotFoundError:
        return f"Command not found: {test_command[0]}\n", 127
    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s\n", 124


def _log(project_rapid_dir: Path, run_id: str, name: str, output: str) -> Path:
    checks_dir = Path(project_rapid_dir) / "scratch" / "checks" / run_id
    checks_dir.mkdir(parents=True, exist_ok=True)
    log_path = checks_dir / f"{name}-{len(list(checks_dir.glob(name + '-*.log'))) + 1}.log"
    log_path.write_text(output, encoding="utf-8")
    return log_path


def _link_dir(target: Path, link: Path) -> bool:
    try:
        link.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, AttributeError):
        return False


def _unlink_dir(link: Path) -> None:
    """Remove a junction or symlink without touching what it points to."""
    try:
        if os.name == "nt":
            os.rmdir(link)  # a junction: removes the link only
        else:
            os.unlink(link)
    except OSError:
        pass


def _prepare_local_environment(toplevel: Path, cwd: Path, baseline: Path) -> list[Path]:
    """Link dependency directories and copy ignored local files of `cwd` and its subdirectories into the baseline.

    Returns the links created, which must be removed before the worktree is."""
    links: list[Path] = []
    sources = [cwd]
    try:
        sources += sorted(
            d for d in cwd.iterdir()
            if d.is_dir() and not d.is_symlink() and d.name not in DEPENDENCY_DIRS and d.name not in (".git", ".rapid-os")
        )
    except OSError:
        pass
    for source in sources:
        try:
            mirror = baseline / source.relative_to(toplevel)
        except ValueError:
            continue
        if not mirror.is_dir():
            continue
        for name in DEPENDENCY_DIRS:
            if (source / name).is_dir() and not (mirror / name).exists() and _link_dir(source / name, mirror / name):
                links.append(mirror / name)
        for name in LOCAL_FILES:
            if (source / name).is_file() and not (mirror / name).exists():
                try:
                    shutil.copy2(source / name, mirror / name)
                except OSError:
                    pass
    return links


def check_reproduction(
    project_rapid_dir: Path,
    run_id: str,
    session: Session,
    test_command: Sequence[str],
    *,
    cwd: Path,
    timeout: float = 600,
    baseline_failed: int | None = None,
) -> ReproductionOutcome:
    """Run `test_command` on the baseline tree plus the run's new or changed tests: they must make tests fail there.

    `baseline_failed` is the failed count of the run's own baseline (`baseline_failed_count`); without it the
    baseline tree is also run without the run's tests to get it."""
    if not session.start_head:
        return ReproductionOutcome(
            "unavailable",
            "El run empezó sin commit, así que no hay árbol de baseline donde comprobar que el test de "
            "reproducción falla; la comprobación no se hizo.",
        )
    cwd = Path(cwd).resolve()
    top = run_git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return ReproductionOutcome("unavailable", f"git no pudo dar la raíz del repositorio: {top.stderr.strip()}")
    toplevel = Path(top.stdout.strip()).resolve()

    changed = observed_changes(cwd, session.start_head, session.start_untracked or ())
    test_files = [path for path in changed if is_test_path(path)]
    if not test_files:
        return ReproductionOutcome(
            "not_reproduced",
            f"{REPRODUCTION_CODE} El run no añadió ni cambió ningún archivo de test: no hay test de reproducción "
            "que comprobar contra el baseline. Escribe el test que reproduce el bug (debe ejecutar el código de "
            "root_cause) y regístralo con `rapid check --expect fail`.",
        )

    temp_root = Path(tempfile.mkdtemp(prefix=REPRODUCTION_WORKTREE_PREFIX))
    baseline = temp_root / "baseline"
    links: list[Path] = []
    added = False
    try:
        proc = run_git(toplevel, "-c", "core.longpaths=true", "worktree", "add", "--detach", str(baseline), session.start_head)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            return ReproductionOutcome(
                "unavailable",
                f"No se pudo crear el worktree del baseline: {detail[-1] if detail else 'error desconocido'}",
                test_files,
            )
        added = True
        links = _prepare_local_environment(toplevel, cwd, baseline)
        try:
            run_cwd = baseline / cwd.relative_to(toplevel)
        except ValueError:
            run_cwd = baseline
        short = session.start_head[:10]
        files = ", ".join(test_files)

        if baseline_failed is None:
            # The run's baseline evidence has no count: count the baseline tree without the run's tests.
            base_output, _ = _run_tests(test_command, run_cwd, timeout)
            base_log = _log(project_rapid_dir, run_id, "reproduction-baseline", base_output)
            base_counts = parse_test_summary(base_output)
            if base_counts is None:
                return ReproductionOutcome(
                    "inconclusive",
                    f"{REPRODUCTION_CODE} En el árbol del baseline ({short}) y sin los tests del run, el comando de "
                    "tests no dio un resumen de tests que contar, así que no hay con qué comparar: no se sabe si el "
                    "test de reproducción falla allí. La tarea de corrección no se cierra. Revisa el log: "
                    f"{base_log}",
                    test_files, None, None, base_log,
                )
            baseline_failed = base_counts["failed"]

        for path in test_files:
            source, target = toplevel / path, baseline / path
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            elif target.exists():
                target.unlink()  # the run deleted it: the baseline run must not have it either
        output, exit_code = _run_tests(test_command, run_cwd, timeout)
        log_path = _log(project_rapid_dir, run_id, "reproduction", output)
        counts = parse_test_summary(output)
        if counts is None:
            return ReproductionOutcome(
                "inconclusive",
                f"{REPRODUCTION_CODE} En el árbol del baseline ({short}) con {files}, el comando de tests salió con "
                f"código {exit_code} sin un resumen de tests que contar: no se sabe si el test de reproducción falló "
                "o si los tests no llegaron a ejecutarse (dependencias, servicios o un paso de build que falta "
                f"allí), así que la tarea de corrección no se cierra. Revisa el log: {log_path}",
                test_files, exit_code, counts, log_path, baseline_failed,
            )
        failed_tests = parse_failed_test_files(output)
        ours = [name for name in failed_tests if any(_same_test_file(name, f) for f in test_files)]
        if counts["failed"] <= baseline_failed:
            return ReproductionOutcome(
                "not_reproduced",
                f"{REPRODUCTION_CODE} En el árbol del baseline ({short}) los tests del run ({files}) no hacen fallar "
                f"ningún test más: {counts['failed']} fallidos con ellos y {baseline_failed} sin ellos. El test no "
                "reproduce el bug, así que la tarea de corrección no se cierra. Debe ejecutar el código de "
                "root_cause (si la causa está en un adaptador, en infraestructura o en la base de datos, con un test "
                "de integración y los servicios levantados, no con dobles del componente defectuoso) y fallar sin "
                f"la corrección. Log: {log_path}",
                test_files, exit_code, counts, log_path, baseline_failed, failed_tests,
            )
        if failed_tests and not ours:
            return ReproductionOutcome(
                "not_reproduced",
                f"{REPRODUCTION_CODE} En el árbol del baseline ({short}) fallan otros tests en el baseline, no el de "
                f"reproducción: {', '.join(failed_tests)} (los tests del run son {files}). La tarea de corrección no "
                f"se cierra. Log: {log_path}",
                test_files, exit_code, counts, log_path, baseline_failed, failed_tests,
            )
        return ReproductionOutcome(
            "holds",
            f"El test de reproducción falla en el árbol del baseline ({short}): {counts['failed']} fallidos con los "
            f"tests del run ({files}) frente a {baseline_failed} sin ellos"
            + (f" ({', '.join(ours)})" if ours else "")
            + ", y pasa en el actual.",
            test_files, exit_code, counts, log_path, baseline_failed, failed_tests,
        )
    finally:
        for link in links:
            _unlink_dir(link)
        if added:
            run_git(toplevel, "worktree", "remove", "--force", str(baseline))
        shutil.rmtree(temp_root, ignore_errors=True)
        run_git(toplevel, "worktree", "prune")


def reproduction_evidence_input(run_id: str, task_id: str, state_revision: int, outcome: ReproductionOutcome, project_root: Path) -> dict[str, object]:
    """The `reproduction_holds` evidence of the fix task (a command_result that passed)."""
    try:
        log = outcome.log_path.relative_to(project_root).as_posix() if outcome.log_path else None
    except ValueError:
        log = None
    summary = (
        f"Reproduction holds: on the baseline tree the run's tests make {(outcome.counts or {}).get('failed', 0)} "
        f"tests fail against {outcome.baseline_failed or 0} without them, and they pass on the current tree"
    )
    return {
        "kind": "command_result",
        "producer": "rapid:check",
        "summary": summary,
        "state_revision": state_revision,
        "task_ids": [task_id],
        "gate_ids": [],
        "capability_ids": ["shell.execute"],
        "payload": {"label": REPRODUCTION_LABEL, "exit_code": 0},
        "artifacts": [log] if log else [],
    }


MAX_CAUSE_DIFF_LINES = 60
NOT_AT_CAUSE_WARNING = "el arreglo no toca la causa declarada"


def _diff_numstat(cwd: Path, start_head: str) -> dict[str, tuple[int, int]]:
    proc = run_git(cwd, "diff", "--numstat", start_head)
    stats: dict[str, tuple[int, int]] = {}
    if proc.returncode != 0:
        return stats
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            added = int(parts[0]) if parts[0].isdigit() else 0
            removed = int(parts[1]) if parts[1].isdigit() else 0
            stats[parts[2].replace("\\", "/")] = (added, removed)
    return stats


def bugfix_handover(project_rapid_dir: Path, cause, evidence, *, cwd: Path, session: Session | None) -> dict[str, object]:
    """What the person needs to approve a bugfix: the declared cause, the diff lines that change it, the other
    production changes (additional defenses, listed apart) and the `reproduction_holds` evidence.

    `touches_root_cause` is False when the diff does not change the root_cause file: `warning` says so."""
    holds = [ev.id for ev in evidence if (ev.payload or {}).get("label") == REPRODUCTION_LABEL]
    accepted = accepted_reproductions(evidence)
    handover: dict[str, object] = {
        "root_cause": {**cause.to_dict(), "location": cause.location},
        "reproduction_holds": holds[-1] if holds else None,
        "reproduction_accepted": accepted[-1] if accepted else None,
        "fix_at_cause": [],
        "additional_defenses": [],
        "touches_root_cause": False,
    }
    start_head = session.start_head if session is not None else None
    if not start_head:
        handover["warning"] = "sin commit de partida no se puede leer el diff del run"
        return handover
    cwd = Path(cwd)
    top = run_git(cwd, "rev-parse", "--show-toplevel")
    toplevel = Path(top.stdout.strip()).resolve() if top.returncode == 0 else cwd.resolve()
    try:
        prefix = Path(cwd).resolve().relative_to(toplevel).as_posix()
    except ValueError:
        prefix = "."
    cause_path = cause.file if prefix in ("", ".") else f"{prefix}/{cause.file}"

    diff = run_git(toplevel, "diff", "--unified=0", start_head, "--", cause_path)
    lines = [
        line for line in (diff.stdout or "").splitlines()
        if line.startswith("@@") or (line[:1] in "+-" and not line.startswith(("+++", "---")))
    ]
    handover["touches_root_cause"] = any(line[:1] in "+-" for line in lines)
    if len(lines) > MAX_CAUSE_DIFF_LINES:
        lines = lines[:MAX_CAUSE_DIFF_LINES] + [f"… ({len(lines) - MAX_CAUSE_DIFF_LINES} líneas más: git diff {start_head[:10]} -- {cause_path})"]
    handover["fix_at_cause"] = lines

    stats = _diff_numstat(toplevel, start_head)
    defenses = []
    for path in observed_changes(cwd, start_head, session.start_untracked or ()):
        if path == cause_path or is_test_path(path):
            continue
        added, removed = stats.get(path, (None, None))
        if added is None and (toplevel / path).is_file():  # a new file git does not track yet: all its lines
            try:
                added, removed = len((toplevel / path).read_text(encoding="utf-8", errors="replace").splitlines()), 0
            except OSError:
                pass
        defenses.append({"file": path, "added": added, "removed": removed})
    handover["additional_defenses"] = defenses
    if not handover["touches_root_cause"]:
        handover["warning"] = f"{NOT_AT_CAUSE_WARNING} ({cause.location})"
    return handover


def handover_lines(handover: dict[str, object]) -> list[str]:
    cause = handover["root_cause"]
    lines = [
        f"Causa raíz: {cause['location']}",
        f"  Cómo se encontró: {cause['how_found']}",
        f"  Explicación: {cause['explanation']}",
    ]
    if handover.get("warning"):
        lines.append(f"AVISO: {handover['warning']}.")
    if handover["fix_at_cause"]:
        lines.append(f"Corrección en la causa ({cause['file']}):")
        lines.extend(f"  {line}" for line in handover["fix_at_cause"])
    defenses = handover["additional_defenses"]
    lines.append("Defensas adicionales (fuera de la causa):" if defenses else "Defensas adicionales: ninguna")
    for item in defenses:
        counts = "" if item["added"] is None else f" (+{item['added']} −{item['removed']})"
        lines.append(f"  - {item['file']}{counts}")
    holds = handover.get("reproduction_holds")
    accepted = handover.get("reproduction_accepted")
    if holds:
        lines.append(f"Reproducción: el test falla en el baseline y pasa ahora (evidencia: {holds})")
    elif accepted:
        lines.append(
            f"Reproducción: no comprobada en el baseline; la aceptó {accepted['reviewer']}: «{accepted['reason']}» "
            f"(evidencia: {accepted['evidence_id']})"
        )
    else:
        lines.append("Reproducción: sin evidencia reproduction_holds")
    return lines


def accepted_reproductions(evidence) -> list[dict[str, str]]:
    """The reproductions a person accepted without the baseline check (`--accept-reproduction`)."""
    found = []
    for ev in evidence:
        payload = ev.payload or {}
        if ev.kind.value == "review" and payload.get("accepts") == "reproduction_inconclusive":
            found.append({
                "evidence_id": ev.id,
                "task_id": ev.task_ids[0] if ev.task_ids else "",
                "reviewer": str(payload.get("reviewer", "")),
                "reason": str(payload.get("reason", "")),
            })
    return found

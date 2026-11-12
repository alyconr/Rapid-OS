"""Run the Rapid OS test suite in parallel, one process per test module.

Uses only the standard library. Usage (from the repository root):

    python scripts/test.py              # fast suite: every module except the slow ones
    python scripts/test.py --all        # whole suite, including the slow end-to-end modules
    python scripts/test.py --slow       # only the slow end-to-end modules
    python scripts/test.py -j 8         # number of parallel processes (default: CPU count)
    python scripts/test.py test_hooks   # only the named modules

The slow modules are listed in SLOW_MODULES below. Keep that list in sync when a
module starts or stops driving the CLI end to end.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

# Modules that drive the CLI end to end (many subprocesses, temporary repos, go/node).
# Measured 2026-10-31 (760 s serial): these eleven modules take ~70% of it.
SLOW_MODULES: set[str] = {
    "test_architecture_baseline",
    "test_brief_seed",
    "test_f5_e2e_codex",
    "test_git_sandbox",
    "test_intent_loop",
    "test_modular_monolith",
    "test_no_git",
    "test_onboarding_templates",
    "test_rc4_evidence_integrity",
    "test_setup_writes",
    "test_stdin_utf8_and_resolution",
    "test_verification_integrity",
}


def discover() -> list[str]:
    return sorted(p.stem for p in TESTS.glob("test_*.py"))


def run_module(name: str) -> tuple[str, int, float, str]:
    start = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", f"tests.{name}"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return name, proc.returncode, time.monotonic() - start, proc.stdout + proc.stderr


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="include the slow end-to-end modules")
    group.add_argument("--slow", action="store_true", help="run only the slow end-to-end modules")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 2)
    parser.add_argument("modules", nargs="*", help="module names, e.g. test_hooks")
    args = parser.parse_args(argv)

    every = discover()
    if args.modules:
        unknown = [m for m in args.modules if m not in every]
        if unknown:
            print(f"Unknown test modules: {', '.join(unknown)}", file=sys.stderr)
            return 2
        selected = args.modules
    elif args.all:
        selected = every
    elif args.slow:
        selected = [m for m in every if m in SLOW_MODULES]
    else:
        selected = [m for m in every if m not in SLOW_MODULES]

    print(f"Running {len(selected)} modules with {args.jobs} processes...", flush=True)
    start = time.monotonic()
    failed: list[tuple[str, str]] = []
    timings: list[tuple[float, str]] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_module, m) for m in selected]
        for future in as_completed(futures):
            name, code, seconds, output = future.result()
            timings.append((seconds, name))
            mark = "ok  " if code == 0 else "FAIL"
            print(f"  {mark} {name} ({seconds:.1f}s)", flush=True)
            if code != 0:
                failed.append((name, output))

    for name, output in failed:
        print(f"\n===== {name} =====\n{output}")
    slowest = ", ".join(f"{n} {s:.0f}s" for s, n in sorted(timings, reverse=True)[:5])
    print(f"\nSlowest: {slowest}")
    total = time.monotonic() - start
    if failed:
        print(f"FAILED: {len(failed)} of {len(selected)} modules ({total:.0f}s)")
        return 1
    print(f"OK: {len(selected)} modules ({total:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

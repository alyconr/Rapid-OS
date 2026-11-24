"""Rapid OS test package."""

import os
import sys


sys.dont_write_bytecode = True

# H-82: the CLI subprocesses of the suite must not take the harness of whoever runs it (Claude Code, Codex): this
# turns off only the harness detection from the process tree (step 3b of detect_harness). The RAPID1310 barrier
# of approve and the other person-only decisions does not read it. Tests that exercise the tree inject it.
os.environ["RAPID_HARNESS_FROM_ANCESTRY"] = "0"


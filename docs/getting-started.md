# Getting Started with Rapid OS v3.0.0

This guide walks through installing Rapid OS `v3.0.0` and executing a complete, governed engineering workflow from repository scanning to behavioral evaluation.

---

## 1. Prerequisites

- **Python 3.10+** (standard library only; zero external Python dependencies)
- **Git**

---

## 2. Installation

### Option A: Standard Python Package (`pip` / `venv`)

From a local clone of the repository:

```bash
python -m pip install .
rapid --version
```

Expected output:

```text
Rapid OS 3.0.0
```

### Option B: Shell / PowerShell Installer

- **Linux / macOS / WSL**:
  ```bash
  curl -sL https://raw.githubusercontent.com/alyconr/Rapid-OS/main/install.sh | bash
  ```
- **Windows PowerShell**:
  ```powershell
  irm https://raw.githubusercontent.com/alyconr/Rapid-OS/main/install.ps1 | iex
  ```

### Option C: Direct Repository Checkout

```bash
python rapid.py --version
python rapid.py guide
```

---

## 3. Initialize or Inspect Your Project

Navigate to the root of your target project directory:

```bash
cd /path/to/your-project
rapid doctor
```

If you want to initialize project standards (`.rapid-os/standards/`, `.rapid-os/config.json`, and agent instruction files):

```bash
rapid init
```

Or create the minimal standards structure non-interactively before running the v3 governance loop.

---

## 4. End-to-End Governance Walkthrough

### Step 1: Scan Project Intelligence (`rapid scan`)

Scan the repository for deterministic facts (`ProjectModel`) and persist `.rapid-os/project.json`:

```bash
rapid scan --write
```

### Step 2: Create and Ready an Immutable Spec (`rapid spec`)

Create a structured specification in `.rapid-os/specs/checkout-idempotency/` and mark it `ready`:

```bash
rapid spec create \
  --id checkout-idempotency \
  --title "Checkout Idempotency" \
  --mode feature \
  --objective "Prevent duplicate charges on payment retries" \
  --problem "Network retries can submit duplicate payment requests" \
  --scope "src/checkout.py" \
  --acceptance "Duplicate idempotency keys return the original result" \
  --task "Implement idempotency key store and unit tests" \
  --status ready
```

### Step 3: Compile Task-Specific Context (`rapid context`)

Compile a budgeted, provenance-backed context bundle (`CompiledContext`) for your coding harness:

```bash
rapid context compile --mode feature --spec checkout-idempotency --harness codex --manifest
```

### Step 4: Create an Immutable Run Contract (`rapid policy` & `rapid run`)

Inspect the active execution policy and create a governed Run (`checkout-idempotency-r1-run-001`):

```bash
rapid policy show
rapid run create --spec checkout-idempotency --harness codex
```

### Step 5: Resolve Harness Capabilities (`rapid harness`)

Initialize and lock a project harness profile if your run requires capabilities beyond the conservative built-in profile (such as `repository.write` and `tests.execute`), then verify compatibility:

```bash
rapid harness list
rapid harness show codex
rapid harness resolve --run checkout-idempotency-r1-run-001
```

### Step 6: Execute Work & Advance Run State (`rapid run`)

Acknowledge pre-execution gates, activate the run, and record task progress as your coding harness executes the work:

```bash
rapid run gate checkout-idempotency-r1-run-001 gate.baseline acknowledged --reason "Baseline test suite green"
rapid run status checkout-idempotency-r1-run-001 active
rapid run task checkout-idempotency-r1-run-001 T001 in_progress
rapid run task checkout-idempotency-r1-run-001 T001 done
rapid run gate checkout-idempotency-r1-run-001 gate.tests acknowledged --reason "Unit tests passing"
rapid run gate checkout-idempotency-r1-run-001 gate.final-verification acknowledged --reason "Ready for final verification"
rapid run status checkout-idempotency-r1-run-001 finished
```

### Step 7: Attach Verifiable Run Evidence (`rapid evidence`)

> **Important**: Acknowledging gates in Step 6 is a *declaration*, not proof. Without evidence, `rapid eval run` will report `unverified`.

Ingest immutable `RunEvidence` records (`E001`, `E002`, ...) and copy supporting artifacts into `.rapid-os/evidence/<run-id>/`:

```bash
rapid evidence add --run checkout-idempotency-r1-run-001 --input baseline-evidence.json
rapid evidence add --run checkout-idempotency-r1-run-001 --input implementation-evidence.json
rapid evidence verify --run checkout-idempotency-r1-run-001
```

### Step 8: Run Behavioral Evaluation & Validate Project (`rapid eval` & `rapid validate`)

Evaluate the run against Phase 6 behavioral rules and require a passing verdict:

```bash
rapid eval run --run checkout-idempotency-r1-run-001 --write --require-pass
rapid validate
```

When all required lifecycle, task, gate, and observable capability assertions are backed by verified evidence, `rapid eval run --require-pass` emits `Verdict: pass` and exits `0`.

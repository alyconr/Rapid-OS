import argparse
import contextlib
import json
import shutil
import os
import shlex
import subprocess
import sys
from pathlib import Path

from rapid_os import __version__
from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
from rapid_os.core.harness_detect import detect_harness

from rapid_os.adapters.mcp import (
    render_mcp_install_content,
    resolve_mcp_install_target,
    resolve_supported_mcp_scopes,
    write_mcp_install_target,
)
from rapid_os.core.config import (
    inspect_project_config_file,
    load_project_config,
    save_project_config,
)
from rapid_os.core.context import compose_project_context
from rapid_os.core.filesystem import (
    check_node_installed,
    create_backup,
    resolve_child_path,
    safe_append_text,
    safe_copy_file,
    safe_rmtree_child,
    safe_write_text,
)
from rapid_os.core.identifiers import (
    validate_identifier,
    validate_remote_package_reference,
)
from rapid_os.core.output import (
    ensure_utf8_stdio,
    print_error,
    print_step,
    print_success,
    print_warning,
)
from rapid_os.core.paths import (
    CONFIG_FILE,
    CURRENT_DIR,
    PROJECT_RAPID_DIR,
    RAPID_HOME,
    SCRIPT_DIR,
    TEMPLATES_DIR,
)
from rapid_os.adapters.capability_lock import (
    load_capability_lock,
    write_capability_lock,
)
from rapid_os.adapters.context_sources import ContextSourceLoader
from rapid_os.adapters.eval_registry import EvalRegistry
from rapid_os.adapters.evidence_registry import EvidenceRegistry
from rapid_os.adapters.execution_policy import (
    load_execution_policy,
    write_default_execution_policy,
)
from rapid_os.adapters.harness_registry import HarnessRegistry
from rapid_os.adapters.project_snapshot import write_project_snapshot
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.core.process import run_npx_skills_add
from rapid_os.core.text import read_text_best_effort
from rapid_os.domain.agents import generate_agent_contexts
from rapid_os.adapters.project_commands import propose_test_command
from rapid_os.domain.catalog import (
    GENERIC_STACK_ID,
    CatalogError,
    build_generic_stack,
    load_catalog,
)
from rapid_os.domain.capabilities import (
    HARNESS_PROFILE_SCHEMA_VERSION,
    CapabilityResolver,
    CompatibilityStatus,
)
from rapid_os.domain.context import (
    ContextBudgetExceededError,
    ContextCompiler,
    ContextManifest,
    ContextRequest,
    ContextRequiredSourceMissingError,
)
from rapid_os.domain.evals import (
    EVALUATION_REPORT_SCHEMA_VERSION,
    EvaluationError,
    EvaluationFailedError,
    EvaluationReport,
    EvaluationUnverifiedError,
    EvaluationVerdict,
    InvalidEvaluationReportError,
)
from rapid_os.domain.evidence import (
    RUN_EVIDENCE_SCHEMA_VERSION,
    EvidenceError,
    EvidenceKind,
    InvalidRunEvidenceError,
    RunEvidence,
    compute_evidence_set_digest,
)
from rapid_os.domain.execution import (
    EXECUTION_POLICY_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    ExecutionError,
    GateKind,
    InvalidExecutionPolicyError,
    InvalidGateTransitionError,
    InvalidRunRecordError,
    InvalidSpecBindingError,
    InvalidTaskTransitionError,
    RunStatus,
    TaskStatus,
)
from rapid_os.domain.harnesses import (
    CapabilityLockError,
    HarnessCapabilityError,
    IncompatibleHarnessError,
    InvalidCapabilityResolutionError,
)
from rapid_os.domain.mcp import build_mcp_config
from rapid_os.domain.project import ProjectModel
from rapid_os.domain.scanner import (
    build_project_model,
    scan_project,
    suggest_init_choices,
)
from rapid_os.domain.scope import (
    ScopeSpec,
    normalize_mode,
    parse_list,
    write_scope_artifacts,
)
from rapid_os.domain.specs import (
    SPEC_SCHEMA_VERSION,
    InvalidRevisionManifestError,
    SpecMode,
    SpecRegistryError,
    SpecRevision,
    SpecStatus,
    spec_revision_from_scope,
)
from rapid_os.domain.validation import (
    ERROR,
    INFO,
    WARNING,
    Diagnostic,
    ValidationReport,
    inspect_project_context,
    validate_capability_lock,
    validate_composed_context,
    validate_eval_registry,
    validate_evidence_registry,
    validate_execution_policy,
    validate_harness_registry,
    validate_project,
    validate_project_config,
    validate_project_intelligence,
    validate_project_standards,
    validate_run_registry,
    validate_spec_registry,
    validate_stack_topology,
    validate_templates,
)


EXIT_TOKENS = {"0", "q", "quit", "exit", "salir", "cancelar"}
SUPPORTED_ARCHETYPES = ("mvp", "corporate")

def is_exit_token(value):
    return value.strip().lower() in EXIT_TOKENS


def prompt_input(message, input_fn=None):
    input_fn = input if input_fn is None else input_fn
    try:
        value = input_fn(message).strip()
    except (EOFError, StopIteration):
        return None
    if is_exit_token(value):
        return None
    return value


def prompt_yes_no(message, default=False, input_fn=None):
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        value = prompt_input(message + suffix, input_fn=input_fn)
        if value is None:
            return None
        if not value:
            return default
        normalized = value.lower()
        if normalized in {"y", "yes", "s", "si", "sí"}:
            return True
        if normalized in {"n", "no"}:
            return False
        print_warning("Respuesta no valida. Usa y/n o 0 para cancelar.")


def prompt_menu(title, options, input_fn=None):
    print(f"\n{title}")
    for index, label in enumerate(options, 1):
        print(f" {index}) {label}")
    print(" 0) exit")

    while True:
        value = prompt_input("Opcion: ", input_fn=input_fn)
        if value is None:
            return None
        if value.isdigit():
            index = int(value) - 1
            if 0 <= index < len(options):
                return index
        print_warning("Opcion no valida. Usa un numero de la lista o 0 para salir.")


def parse_agent_selection(agent_sel):
    selected_tools = []
    if not agent_sel or not agent_sel.strip():
        return ["cursor"]

    name_map = {
        "1": "cursor",
        "cursor": "cursor",
        "2": "claude",
        "claude": "claude",
        "3": "antigravity",
        "antigravity": "antigravity",
        "4": "vscode",
        "vscode": "vscode",
        "5": "codex",
        "codex": "codex",
    }
    parts = [part.strip().lower() for part in agent_sel.split(",")]
    for part in parts:
        tool_name = name_map.get(part)
        if tool_name and tool_name not in selected_tools:
            selected_tools.append(tool_name)
    return selected_tools or ["cursor"]


def _load_config_with_warning(config_file=CONFIG_FILE):
    result = inspect_project_config_file(config_file)
    if not result.is_valid:
        print_warning(
            f"Configuracion invalida en {config_file} ({result.status}): {result.error}"
        )
    return result.config


def regenerate_context():
    """Compila estándares y genera SOLO para las herramientas seleccionadas."""
    full_context = compose_project_context(PROJECT_RAPID_DIR, CURRENT_DIR)
    config = _load_config_with_warning(CONFIG_FILE)
    tools = config.get("tools", [])
    generate_agent_contexts(full_context, tools, CURRENT_DIR)


def print_scan_summary(scan, suggestions, stack_override=None):
    print("\nRapid OS detected:")
    for category, label in (
        ("language", "Language"),
        ("framework", "Framework"),
        ("package_manager", "Package manager"),
        ("testing", "Testing"),
        ("docker", "Docker"),
        ("monorepo", "Monorepo"),
        ("database", "Database"),
        ("deploy_provider", "Deploy provider"),
    ):
        values = scan.values(category)
        if values:
            print(f"- {label}: {', '.join(values)}")
        else:
            print(f"- {label}: none detected")

    if suggestions.has_any() or stack_override:
        print("\nSuggested init choices:")
        if stack_override:
            print(f"- Stack: {stack_override} (--stack)")
        elif suggestions.stack:
            print(f"- Stack: {suggestions.stack.value}")
        if suggestions.topology:
            print(f"- Topology: {suggestions.topology.value}")


def confirm_scan_suggestions(scan, suggestions, stack_override=None):
    if not suggestions.has_any():
        return False

    print_scan_summary(scan, suggestions, stack_override)
    try:
        response = input("\nUse these suggestions? [Y/n]: ").strip().lower()
    except EOFError:
        response = "n"
    return response != "n"


INIT_DOCS_PENDING_MESSAGE = "Completa la documentación con /rapid-init o rapid setup next"


def _init_pending_message(selected_tools):
    """Codex invokes skills with `$`, every other harness with `/`."""
    others = [tool for tool in selected_tools if tool in DEFAULT_AGENT_REGISTRY.ids() and tool != "codex"]
    if "codex" not in selected_tools:
        return INIT_DOCS_PENDING_MESSAGE
    if not others:
        return INIT_DOCS_PENDING_MESSAGE.replace("/rapid-init", "$rapid-init")
    return INIT_DOCS_PENDING_MESSAGE.replace("/rapid-init", "/rapid-init (o $rapid-init en Codex)")
RAPID_NOT_ON_PATH_MESSAGE = (
    "RAPID1414 Los shortcuts y hooks ejecutan rapid desde el shell del agente, y rapid no está "
    "en el PATH. Instálalo con el instalador o con pipx."
)


def _warn_if_rapid_not_on_path():
    """RAPID1414: shortcuts and hooks run `rapid` from the agent's shell. Warning only."""
    if shutil.which("rapid") is None:
        print_warning(RAPID_NOT_ON_PATH_MESSAGE)
        return True
    return False


def _read_doc_file(path_str):
    """`(text, "")` for a readable file, `(None, reason)` otherwise. Never raises."""
    if not path_str:
        return None, "La ruta está vacía."
    local_path = Path(path_str).expanduser()
    if local_path.is_dir():
        return None, f"'{local_path}' es un directorio, no un archivo."
    if not local_path.is_file():
        return None, f"No existe el archivo '{local_path}'."
    try:
        text = local_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"No se pudo leer '{local_path}': {exc}"
    if not text.strip():
        return None, f"'{local_path}' está vacío."
    return text, ""


def _read_multiline(message):
    """Text typed in the terminal; two empty lines in a row (or EOF) end it."""
    print(message)
    lines = []
    blanks = 0
    while True:
        try:
            line = input()
        except (EOFError, StopIteration):
            break
        blanks = blanks + 1 if not line.strip() else 0
        if blanks >= 2:
            break
        lines.append(line)
    return "\n".join(lines).strip("\n")


def _ask_init_doc(bank):
    """What to do with one onboarding document: `(status, text)`.

    Without more input (EOF) the document stays pending: leaving it for the agent is the safe
    answer, so a piped `rapid init` never fails here nor invents anything.
    """

    def ask(message):
        try:
            return input(message).strip()
        except (EOFError, StopIteration):
            return None

    while True:
        print(f"\n📄 {bank.title} ({bank.file})")
        print(" 1) Pegar o importar un archivo (.md, .txt)")
        print(" 2) Escribirlo aquí (termina con dos líneas vacías)")
        print(" 3) Dejarlo para tu agente (/rapid-init)")
        print(" 4) Omitir")
        choice = ask("Opción [3]: ")
        if choice in (None, "", "3"):
            return "pending", None
        if choice == "4":
            return "skipped", None
        if choice == "1":
            while True:
                raw = ask("📂 Ruta del archivo (.md, .txt; 0 para volver): ")
                if raw is None or is_exit_token(raw):
                    break
                cleaned = raw.replace("'", "").replace('"', "")
                text, reason = _read_doc_file(cleaned)
                if text is not None:
                    print_success(f"Leído correctamente: {Path(cleaned).name}")
                    return "provided", text
                print_warning(f"{reason} Prueba con otra ruta.")
        elif choice == "2":
            text = _read_multiline(f"Escribe {bank.title.lower()} (dos líneas vacías para terminar):")
            if text.strip():
                return "provided", text
            print_warning("No escribiste nada.")
        else:
            print_warning("Opción no válida. Usa 1, 2, 3 o 4.")


def _collect_init_docs(args, banks, kept):
    """`{doc_id: (status, text)}`; status is provided, pending, skipped or keep (already resolved)."""
    from rapid_os.domain.setup import SETUP_DOC_ORDER

    business_file = getattr(args, "business_file", None)
    business_text = None
    if business_file:
        business_text, reason = _read_doc_file(business_file.replace("'", "").replace('"', ""))
        if business_text is None:
            print_error(f"RAPID1413 --business-file: {reason}")

    choices = {}
    for doc_id in SETUP_DOC_ORDER:
        if doc_id == "business" and business_text is not None:
            choices[doc_id] = ("provided", business_text)
        elif doc_id in kept:
            print(f"ℹ️  {banks[doc_id].file} ya está resuelto; se conserva.")
            choices[doc_id] = ("keep", None)
        elif getattr(args, "skip_docs", False):
            choices[doc_id] = ("skipped", None)
        elif getattr(args, "yes", False):
            choices[doc_id] = ("pending", None)
        else:
            if not choices:
                print("\n--- DOCUMENTACIÓN DEL PROYECTO ---")
            choices[doc_id] = _ask_init_doc(banks[doc_id])
    return choices


def _init_doc_banks():
    """Question banks of the onboarding documents; `{}` when the templates do not carry them."""
    from rapid_os.domain.catalog import load_setup_doc_banks

    if not (TEMPLATES_DIR / "setup" / "docs").is_dir():
        return {}
    try:
        return load_setup_doc_banks(TEMPLATES_DIR)
    except CatalogError as exc:
        print_error(str(exc))


def init_project(args):
    from dataclasses import replace as dc_replace

    from rapid_os.adapters.setup_store import read_setup, write_setup
    from rapid_os.domain.setup import DocState, SetupState, SetupStateError, StackChoice
    from rapid_os.orchestration.setup_apply import (
        SetupApplyError,
        apply_setup,
        update_gitignore,
        write_doc,
    )

    print_step("Inicializando Rapid OS...")

    def safe_prompt(prompt_msg: str, default: str = "", flag_hint: str = "") -> str:
        try:
            val = input(prompt_msg)
            return val.strip()
        except (EOFError, StopIteration):
            if getattr(args, "yes", False):
                return default
            if not sys.stdin.isatty():
                print_error(
                    f"RAPID1302 Entrada interactiva requerida pero stdin no es una terminal. "
                    f"Usa {flag_hint or '--yes'} para ejecutar 'rapid init' de forma desatendida."
                )
                sys.exit(1)
            return default

    scan = None
    suggestions = None
    use_suggestions = False

    if not getattr(args, "no_scan", False):
        scan = scan_project(CURRENT_DIR)
        suggestions = suggest_init_choices(scan)
        if suggestions.has_any():
            if getattr(args, "yes", False):
                use_suggestions = True
            else:
                use_suggestions = confirm_scan_suggestions(scan, suggestions, args.stack)
        else:
            print_scan_summary(scan, suggestions, args.stack)

    standards_dest = PROJECT_RAPID_DIR / "standards"
    standards_dest.mkdir(parents=True, exist_ok=True)

    # 1. Stack
    suggested_stack = suggestions.stack.value if suggestions and suggestions.stack else None
    if args.stack:
        stack_name = args.stack
    elif use_suggestions and suggested_stack:
        stack_name = suggested_stack
    elif getattr(args, "yes", False):
        stack_name = suggested_stack or GENERIC_STACK_ID
    else:
        stacks_path = TEMPLATES_DIR / "stacks"
        if not stacks_path.exists():
            print_error(f"Templates no encontrados en {stacks_path}")
            return
        stacks = sorted([f.stem for f in stacks_path.glob("*.md")])
        if not stacks:
            print_error(f"No se encontraron templates de stack en {stacks_path}")
            return
        print("\n🛠  SELECCIONA TECH STACK:")
        for i, s in enumerate(stacks, 1):
            print(f" {i}) {s}")
        val = safe_prompt("Opción: ", default="1", flag_hint="--stack <name>")
        try:
            idx = int(val) - 1
            stack_name = stacks[idx] if 0 <= idx < len(stacks) else stacks[0]
        except (ValueError, IndexError):
            stack_name = stacks[0]

    try:
        catalog = load_catalog(TEMPLATES_DIR)
    except CatalogError as exc:
        print_error(str(exc))
        return

    try:
        stack_name = validate_identifier(stack_name, "stack")
        stack_src = resolve_child_path(
            TEMPLATES_DIR / "stacks", f"{stack_name}.md", single_segment=True
        )
    except ValueError as exc:
        print_error(str(exc))
        return

    is_generic_stack = stack_name == GENERIC_STACK_ID and not stack_src.exists()
    if not is_generic_stack and not stack_src.exists():
        print_error(f"Template de stack no encontrado: {stack_name} ({stack_src})")
        return

    # 2. Topología
    topologies_path = TEMPLATES_DIR / "topologies"
    if not topologies_path.exists():
        topologies_path.mkdir(parents=True, exist_ok=True)
    topos = sorted([f.stem for f in topologies_path.glob("*.md")])
    topo_name = None
    explicit_topology = getattr(args, "topology", None)

    if explicit_topology:
        topo_name = explicit_topology
    else:
        suggested_topology = (
            suggestions.topology.value if suggestions and suggestions.topology else None
        )
        if use_suggestions and suggested_topology in topos:
            topo_name = suggested_topology
        elif getattr(args, "yes", False):
            topo_name = catalog.default_topology_for_stack(stack_name, suggested_topology, topos)
        elif topos:
            print("\n🏗️  SELECCIONA TOPOLOGÍA:")
            for i, t in enumerate(topos, 1):
                print(f" {i}) {t}")
            val = safe_prompt("Opción: ", default="1", flag_hint="--topology <id>")
            try:
                idx = int(val) - 1
                topo_name = topos[idx] if 0 <= idx < len(topos) else topos[0]
            except (ValueError, IndexError):
                topo_name = topos[0]

    # 3. Arquetipo
    explicit_archetype = getattr(args, "archetype", None)
    if explicit_archetype:
        try:
            archetype = validate_identifier(explicit_archetype, "archetype")
        except ValueError as exc:
            print_error(str(exc))
            return
        if archetype not in SUPPORTED_ARCHETYPES:
            print_error(
                f"Arquetipo no soportado: '{archetype}'. Usa 'mvp' o 'corporate'."
            )
            return
    elif getattr(args, "yes", False):
        archetype = "mvp"
    else:
        print("\n📊 SELECCIONA ARQUETIPO:")
        print(" 1) mvp        (Velocidad)")
        print(" 2) corporate  (Seguridad)")
        sel = safe_prompt("Opción [1]: ", default="1", flag_hint="--archetype {mvp,corporate}")
        archetype = "corporate" if sel == "2" else "mvp"

    # 4. Agentes
    explicit_agents = getattr(args, "agents", None)
    if explicit_agents:
        selected_tools = parse_agent_selection(explicit_agents)
    elif getattr(args, "yes", False):
        selected_tools = ["cursor"]
    else:
        print("\n🤖 SELECCIONA TUS AGENTES (Separados por coma):")
        print(" 1) Cursor (.cursorrules)")
        print(" 2) Claude Code (CLAUDE.md)")
        print(" 3) Google Antigravity (.agent/rules)")
        print(" 4) VS Code / Copilot (INSTRUCTIONS.md)")
        print(" 5) Codex (AGENTS.md)")
        agent_sel = safe_prompt("Opción [1]: ", default="1", flag_hint="--agents <lista>")
        selected_tools = parse_agent_selection(agent_sel)

    # 5. Herramientas de Investigación (Research)
    if not getattr(args, "yes", False):
        print("\n🔍 CAPACIDADES DE INVESTIGACIÓN (Opcional):")
        print(" 1) Context7 (Documentación actualizada de librerías)")
        print(" 2) Firecrawl (Rastreo web y extracción de datos)")
        res_sel = safe_prompt("Opción (ej. 1,2 o Enter para ninguna): ", default="", flag_hint="--yes")

        if res_sel:
            parts = res_sel.split(",")
            if "1" in parts and "context7" not in selected_tools:
                selected_tools.append("context7")
            if "2" in parts and "firecrawl" not in selected_tools:
                selected_tools.append("firecrawl")

    # 6. Test Command
    configured_test_cmd: list[str] | None = None
    explicit_test_cmd = getattr(args, "test_command", None)
    if explicit_test_cmd:
        configured_test_cmd = shlex.split(explicit_test_cmd)
    else:
        proposed_cmd = None
        if scan is not None:
            scan_model = scan.to_model() if hasattr(scan, "to_model") else scan
            proposed_cmd = propose_test_command(scan_model.root, scan_model)
        if proposed_cmd is not None:
            cmd_display = " ".join(proposed_cmd)
            if getattr(args, "yes", False):
                configured_test_cmd = proposed_cmd
            else:
                print(f"\n🧪 COMANDO DE TEST DETECTADO: {cmd_display}")
                ans = safe_prompt(f"¿Usar este comando de test? [{cmd_display}] [Y/n]: ", default="y", flag_hint="--test-command '<cmd>'")
                if ans.lower() != "n":
                    configured_test_cmd = proposed_cmd
                else:
                    custom_input = safe_prompt("Escribe el comando de test (o Enter para omitir): ", default="", flag_hint="--test-command '<cmd>'")
                    if custom_input:
                        configured_test_cmd = shlex.split(custom_input)

    # 7. Documentación del proyecto (brief, negocio, modelo de datos, arquitectura)
    banks = _init_doc_banks()
    kept = {}
    if banks:
        try:
            previous = read_setup(
                CURRENT_DIR, PROJECT_RAPID_DIR, CONFIG_FILE, TEMPLATES_DIR, catalog, banks
            )
            kept = {
                doc_id: previous.state.doc(doc_id)
                for doc_id in banks
                if previous.state.doc(doc_id).status != "pending"
            }
        except SetupStateError:
            kept = {}
    doc_choices = _collect_init_docs(args, banks, kept) if banks else {}

    # Same state and same writes as `rapid setup`: nothing below is specific to init.
    registry_ids = set(DEFAULT_AGENT_REGISTRY.ids())
    stack_source = (
        "generic"
        if is_generic_stack
        else "catalog"
        if stack_name in catalog.stacks
        else "custom"
    )
    docs = {}
    for doc_id, (status, _text) in doc_choices.items():
        if status == "keep":
            docs[doc_id] = kept[doc_id]
        elif status == "skipped":
            docs[doc_id] = DocState("skipped", False, "")
        elif status == "pending":
            docs[doc_id] = DocState()
    state = SetupState(
        stack=StackChoice(stack_name, stack_source),
        topology=topo_name,
        archetype=archetype,
        agents=tuple(tool for tool in selected_tools if tool in registry_ids),
        test_command=tuple(configured_test_cmd or ()),
        docs=docs,
    )
    scan_model = (
        (scan.to_model() if hasattr(scan, "to_model") else scan) if scan is not None else None
    )
    try:
        for doc_id, (status, text) in doc_choices.items():
            if status == "provided":
                state = write_doc(CURRENT_DIR, state, banks[doc_id], source="provided", text=text)
                print_success(f"{banks[doc_id].file} creado")
        apply_setup(
            CURRENT_DIR,
            PROJECT_RAPID_DIR,
            CONFIG_FILE,
            TEMPLATES_DIR,
            state,
            catalog,
            scan_model=scan_model,
            scanned=scan is not None,
            extra_tools=tuple(tool for tool in selected_tools if tool not in registry_ids),
            regenerate=False,
        )
    except SetupApplyError as exc:
        print_error(" ".join(exc.lines))
        return
    pending_docs = [doc_id for doc_id, doc in state.docs.items() if doc.status == "pending"]
    if banks:
        state = dc_replace(state, finished=not pending_docs)
        write_setup(PROJECT_RAPID_DIR, state)
    regenerate_context()
    installed_agent_hooks = _offer_shortcuts(args, selected_tools, safe_prompt)
    installed_agent_hooks = _install_hooks_for_init(args, selected_tools) or installed_agent_hooks
    if installed_agent_hooks:
        _warn_if_rapid_not_on_path()

    # Update .gitignore if present in project root
    gitignore_path = CURRENT_DIR / ".gitignore"
    if gitignore_path.exists():
        do_update = False
        if getattr(args, "yes", False):
            do_update = True
        else:
            ans = safe_prompt(
                "\n¿Añadir archivos de sesión, scratch y artefactos de herramientas (__pycache__, *.pyc, .pytest_cache) a .gitignore? [Y/n]: ",
                default="y",
                flag_hint="--yes",
            )
            do_update = ans.lower() != "n"
        if do_update:
            update_gitignore(CURRENT_DIR)

    print("\n🚀 ¡Rapid OS activo!")
    if pending_docs:
        print(_init_pending_message(selected_tools))


def _install_hooks_for_init(args, selected_tools):
    """`rapid init --hooks`: only with the explicit flag, never as a side effect of --shortcuts."""
    if not getattr(args, "hooks", False):
        return False
    from rapid_os.adapters import claude_hooks
    from rapid_os.adapters.shortcut_installer import ShortcutError

    try:
        plan = _plan_claude_hooks("install", tuple(selected_tools))
        claude_hooks.apply_plan(CURRENT_DIR, plan)
    except ShortcutError as exc:
        print_warning(str(exc))
        return False
    print_success(f"Hooks de Claude Code: {plan.action} ({plan.path.as_posix()}).")
    return True


def _offer_shortcuts(args, selected_tools, prompt):
    """Offer the /rapid-<mode> shortcuts at the end of `rapid init`.

    Never prompts unattended: --yes and non-interactive stdin only install with --shortcuts.
    """
    from rapid_os.adapters.shortcut_installer import ShortcutError, resolve_harness_ids

    accepted = getattr(args, "shortcuts", False)
    if not accepted and not getattr(args, "yes", False) and sys.stdin.isatty():
        answer = prompt(
            "\n¿Instalar los shortcuts /rapid-<modo> para tus agentes? [y/N]: ",
            default="n",
            flag_hint="--shortcuts",
        )
        accepted = answer.lower() in {"y", "yes", "s", "si", "sí"}
    if not accepted:
        print("\nTip: 'rapid shortcuts install' crea los comandos /rapid-<modo> en tus agentes.")
        return False
    try:
        harness_ids = resolve_harness_ids(None, selected_tools)
        _warn_folder_overlaps(harness_ids)
        plan, written = _install_shortcuts(harness_ids, dry_run=False)
    except ShortcutError as exc:
        print_warning(str(exc))
        return False
    print_success(f"Shortcuts instalados: {len(written)} archivo(s) escritos.")
    for warning in plan.warnings:
        print_warning(warning)
    return True


def manage_skills(args):
    """Gestor Híbrido de Skills (Local + Vercel CLI)."""
    action = args.action
    skill_name = args.name

    if action is None:
        choice = prompt_menu(
            "RAPID SKILLS",
            ("list", "install local template", "add remote skill"),
        )
        if choice is None:
            print_warning("Operacion cancelada.")
            return
        action = ("list", "install", "add")[choice]

    if action in {"install", "add"} and not skill_name:
        prompt = (
            "Nombre del template local: "
            if action == "install"
            else "Nombre remoto (ej. vercel-labs/agent-skills): "
        )
        skill_name = prompt_input(prompt)
        if skill_name is None:
            print_warning("Operacion cancelada.")
            return

    # MODO 1: LISTAR LOCALES + AYUDA REMOTA
    if action == "list":
        print("\n🧰 SKILLS LOCALES (Templates):")
        skills_source = TEMPLATES_DIR / "skills"
        if skills_source.exists():
            for s in sorted([d.name for d in skills_source.iterdir() if d.is_dir()]):
                print(f" - {s}")
        else:
            print(" (No hay templates locales en templates/skills)")

        print("\n🌐 SKILLS REMOTAS (Vercel Marketplace):")
        print(
            " Usa 'rapid skill add <nombre>' para instalar miles de skills de la comunidad."
        )
        print(" Ej: rapid skill add vercel-labs/agent-skills")
        return

    # MODO 2: INSTALAR REMOTO (VERCEL CLI)
    if action == "add":
        if not skill_name or not str(skill_name).strip():
            print_error("Especifica el nombre (ej. vercel-labs/agent-skills).")
            return

        try:
            validated_skill = validate_remote_package_reference(
                skill_name,
                label="remote skill",
            )
        except ValueError as exc:
            print_error(f"Referencia de skill remota invalida: {exc}")
            return

        if not check_node_installed():
            print_error("Necesitas Node.js (npx) para instalar skills remotas.")
            return

        print_step(f"Invocando Vercel Skills para instalar '{validated_skill}'...")
        try:
            run_npx_skills_add(validated_skill, runner=subprocess.run)
            print_success(f"Skill '{validated_skill}' instalada.")
        except (subprocess.CalledProcessError, OSError, ValueError):
            print_error("Falló la instalación remota.")
        return

    # MODO 3: INSTALAR LOCAL (RAPID TEMPLATES)
    if action == "install":
        if not skill_name or not str(skill_name).strip():
            print_error("Especifica el nombre del template local.")
            return

        try:
            safe_skill_name = validate_identifier(skill_name, "local skill")
            src_skill = resolve_child_path(
                TEMPLATES_DIR / "skills",
                safe_skill_name,
                single_segment=True,
            )
        except ValueError as exc:
            print_error(f"Nombre de skill local inseguro o invalido: {exc}")
            return

        if not src_skill.exists() or not src_skill.is_dir():
            print_error(
                f"Template '{safe_skill_name}' no existe. Usa 'add' para buscar en remoto."
            )
            return

        config = _load_config_with_warning(CONFIG_FILE)
        tools = config.get("tools", ["cursor", "claude", "antigravity"])

        targets = []
        if "cursor" in tools:
            targets.append(CURRENT_DIR / ".cursor" / "skills")
        if "claude" in tools:
            targets.append(CURRENT_DIR / ".claude" / "skills")
        if "antigravity" in tools:
            targets.append(CURRENT_DIR / ".agent" / "skills")

        resolved_targets = []
        try:
            for target_root in targets:
                target_path = resolve_child_path(
                    target_root,
                    safe_skill_name,
                    single_segment=True,
                )
                resolved_targets.append((target_root, target_path))
        except ValueError as exc:
            print_error(f"Ruta de destino insegura para skill local: {exc}")
            return

        print_step(f"Instalando template local '{safe_skill_name}'...")
        for target_root, target_path in resolved_targets:
            try:
                target_root.mkdir(parents=True, exist_ok=True)
                if target_path.exists() or target_path.is_symlink():
                    safe_rmtree_child(target_root, target_path)
                shutil.copytree(src_skill, target_path)
                print(f"  -> {target_root.name}/{safe_skill_name}")
            except ValueError as exc:
                print_error(f"Containment error al instalar skill local: {exc}")
                return
            except OSError as e:
                print_warning(f"Error: {e}")

        print_success("Skill local activada.")


def generate_mcp_config(args):
    print_step("Configurando MCP...")
    ide = getattr(args, "ide", None)
    if not ide:
        ide_options = ("codex", "claude", "cursor", "vscode", "antigravity")
        ide_choice = prompt_menu("Selecciona IDE/editor MCP", ide_options)
        if ide_choice is None:
            print_warning("Configuracion MCP cancelada.")
            return
        ide = ide_options[ide_choice]

    scope = getattr(args, "scope", None)
    if not scope:
        scope_options = resolve_supported_mcp_scopes(ide)
        scope_choice = prompt_menu(
            f"Selecciona scope MCP para {ide}",
            scope_options,
        )
        if scope_choice is None:
            print_warning("Configuracion MCP cancelada.")
            return
        scope = scope_options[scope_choice]

    topo_file = PROJECT_RAPID_DIR / "standards" / "topology.md"
    if not topo_file.exists():
        choice = prompt_menu(
            "No se detecto inicializacion Rapid OS para MCP.",
            ("continue with a minimal MCP setup", "cancel"),
        )
        if choice != 0:
            print_warning("Configuracion MCP cancelada.")
            return
        safe_write_text(
            topo_file,
            "# Topology\n\nMinimal MCP setup for standalone rapid mcp usage.\n",
            encoding="utf-8",
            backup=True,
            create_parents=True,
        )
        if not CONFIG_FILE.exists():
            save_project_config({"tools": []}, PROJECT_RAPID_DIR, CONFIG_FILE)

    topo_content = topo_file.read_text(encoding="utf-8")
    config = _load_config_with_warning(CONFIG_FILE)
    tools = config.get("tools", [])
    mcp_config = build_mcp_config(topo_content, tools, CURRENT_DIR, TEMPLATES_DIR)

    for warning in mcp_config.warnings:
        print_warning(warning.message)

    try:
        target = resolve_mcp_install_target(ide, scope, CURRENT_DIR)
        rendered_content = render_mcp_install_content(target, mcp_config)
        written_path = write_mcp_install_target(target, rendered_content)
    except ValueError as exc:
        print_error(str(exc))
        return
    print_success(f"Configuracion MCP: {written_path}")


def scope_feature(args):
    print("\n🔭 SCOPE WIZARD")
    print("Modo:")
    print(" 1) new feature")
    print(" 2) refactor")
    print(" 3) bugfix")
    print(" 4) legacy hardening")
    print("Tip: usa comas o punto y coma para respuestas tipo lista.")

    spec = ScopeSpec(
        initiative_name=input("Nombre iniciativa: ").strip(),
        mode=normalize_mode(input("Modo [1]: ").strip()),
        business_objective=input("Objetivo de negocio: ").strip(),
        problem_statement=input("Problema a resolver: ").strip(),
        scope=parse_list(input("Alcance: ").strip()),
        out_of_scope=parse_list(input("Fuera de alcance: ").strip()),
        actors_users=parse_list(input("Actores/usuarios: ").strip()),
        main_flow=parse_list(input("Flujo principal: ").strip()),
        edge_cases=parse_list(input("Casos borde: ").strip()),
        business_rules=parse_list(input("Reglas de negocio: ").strip()),
        technical_constraints=parse_list(input("Restricciones técnicas: ").strip()),
        affected_files_modules=parse_list(
            input("Archivos/módulos afectados si se conocen: ").strip()
        ),
        data_impact=input("Impacto en datos: ").strip(),
        acceptance_criteria=parse_list(input("Criterios de aceptación: ").strip()),
        testing_strategy=parse_list(input("Estrategia de pruebas: ").strip()),
        implementation_tasks=parse_list(input("Tareas de implementación: ").strip()),
    )

    for target in write_scope_artifacts(spec, CURRENT_DIR):
        print_success(f"{target.name} creado")

    if getattr(args, "register", False):
        try:
            registry = SpecRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)
            explicit_spec_id = getattr(args, "spec_id", None)
            rev_input = spec_revision_from_scope(
                spec,
                spec_id=explicit_spec_id,
                revision=1,
            )
            created_record = registry.create(rev_input)
            requested_status = getattr(args, "status", None)
            if requested_status == "ready":
                created_record = registry.set_status(
                    created_record.id,
                    SpecStatus.READY,
                )
            print_success(
                f"Spec '{created_record.id}' registrada (r{created_record.current_revision}, status={created_record.status.value})"
            )
        except SpecRegistryError as exc:
            print(f"{exc.code} {exc}", file=sys.stderr)
            sys.exit(1)
        except ValueError as exc:
            print(f"RAPID801 {exc}", file=sys.stderr)
            sys.exit(1)
    return 0


def deploy_assistant(args):
    raw_target = args.target or input("Target (e.g. aws): ").strip()
    try:
        target = validate_identifier(raw_target, "deploy target")
        tpl = resolve_child_path(
            TEMPLATES_DIR / "deploy", f"{target}.md", single_segment=True
        )
    except ValueError as exc:
        print_error(str(exc))
        return

    instructions = (
        read_text_best_effort(tpl) if tpl.exists() else f"Deploy to {target}"
    )
    safe_write_text(
        CURRENT_DIR / "DEPLOY.md",
        f"# DEPLOY {target}\n{instructions}",
        encoding="utf-8",
        backup=True,
        create_parents=True,
    )
    print_success("DEPLOY.md creado")


def add_visual_reference(args):
    path_value = args.path
    if not path_value:
        path_value = prompt_input("Image path (0 to cancel): ")
        if path_value is None:
            print_warning("Referencia visual cancelada.")
            return

    src = Path(path_value)
    if not src.exists() or not src.is_file():
        print_error("Imagen no existe")
        return

    try:
        dest = resolve_child_path(
            CURRENT_DIR / "references", src.name, single_segment=True
        )
    except ValueError as exc:
        print_error(str(exc))
        return

    safe_copy_file(src, dest, backup=False, create_parents=True)
    desc = input("Descripción imagen: ")
    meta = dest.parent / "VISION_CONTEXT.md"
    safe_append_text(
        meta,
        f"\n- **{src.name}**: {desc}",
        encoding="utf-8",
        create_parents=True,
    )
    print_success("Referencia agregada")
    regenerate_context()


def refine_standard(args):
    path = Path(args.file)
    if not path.exists():
        print_error("Archivo no existe")
        return
    print(
        "Prompt para IA: ACT AS ARCHITECT. REFINE:\n\n"
        f"{read_text_best_effort(path)}"
    )


def generate_prompt(args):
    """Genera un prompt optimizado basado en el contexto del proyecto."""
    if not PROJECT_RAPID_DIR.exists():
        print_error("No se detectó un proyecto Rapid OS. Ejecuta 'rapid init' primero.")
        return

    print("\n🔮 GENERADOR DE PROMPTS")
    print(" 1) Nuevo Proyecto (Start)")
    print(" 2) Refactorización (Refine)")

    try:
        option = input("Opción [1]: ").strip()
    except EOFError:
        option = "1"

    is_refactor = option == "2"

    # 1. Analizar Contexto
    context_files = []
    if (PROJECT_RAPID_DIR / "standards" / "business.md").exists():
        context_files.append("business.md (Reglas de Negocio)")
    if (PROJECT_RAPID_DIR / "standards" / "tech-stack.md").exists():
        context_files.append("tech-stack.md (Stack Tecnológico)")

    specs_path = CURRENT_DIR / "SPECS.md"
    has_specs = specs_path.exists()
    if has_specs:
        context_files.append("SPECS.md (Especificaciones)")

    skills = []
    for d in [CURRENT_DIR / ".cursor" / "skills", CURRENT_DIR / ".agent" / "skills"]:
        if d.exists():
            skills.extend([s.name for s in d.iterdir() if d.is_dir()])

    # 2. Construir Prompt
    prompt = "# 🧠 SYSTEM PROMPT: ACT AS SENIOR SOFTWARE ARCHITECT\n\n"
    prompt += "## CONTEXTO DEL PROYECTO\n"
    prompt += "Estás trabajando en un entorno **Rapid OS**. Debes obedecer ESTRICTAMENTE los archivos de normas en `.rapid-os/standards/`.\n\n"

    if context_files:
        prompt += "### 📂 FUENTES DE VERDAD ACTIVAS:\n"
        for f in context_files:
            prompt += f"- {f}\n"

    if skills:
        prompt += "\n### 🛠️ SKILLS DISPONIBLES:\n"
        prompt += f"Tienes acceso a herramientas especializadas: {', '.join(skills)}. Úsalas si es necesario.\n"

    if is_refactor:
        prompt += "\n## 🎯 OBJETIVO: REFACTORIZACIÓN\n"
        prompt += (
            "1.  **ANÁLISIS**: Lee `business.md` y compara con el código actual.\n"
        )
        prompt += "2.  **DETECCIÓN**: Identifica violaciones a las nuevas reglas.\n"
        prompt += "3.  **PLAN**: Enumera los cambios antes de ejecutar.\n"
        prompt += "4.  **ACCIÓN**: Refactoriza priorizando la mantenibilidad y el cumplimiento de normas.\n"
    else:
        prompt += "\n## 🚀 OBJETIVO: INICIO DE PROYECTO\n"
        if has_specs:
            prompt += (
                "Implementa la funcionalidad descrita en **SPECS.md** paso a paso.\n"
            )
        else:
            prompt += "Estructura el proyecto inicial siguiendo el `tech-stack.md`.\n"
        prompt += "- Crea primero la estructura de carpetas.\n"
        prompt += "- Configura el entorno base.\n"

    prompt += "\n## 🛡️ REGLAS DE ORO\n"
    prompt += "1. No inventes reglas que contradigan `business.md`.\n"
    prompt += "2. Si falta información, PREGUNTA.\n"
    prompt += "3. Usa Clean Architecture y principios SOLID.\n"

    print("\n" + "=" * 50)
    print("✂️  COPIA ESTE PROMPT EN TU AGENTE (CURSOR/CLAUDE)")
    print("=" * 50 + "\n")
    print(prompt)
    print("\n" + "=" * 50)


def render_validation_report(report, json_output=False, strict=False):
    if json_output:
        print(json.dumps(report.to_dict(strict=strict), indent=2))
        return report.exit_code(strict=strict)

    for diagnostic in report.diagnostics:
        line = f"[{diagnostic.level}] {diagnostic.code} {diagnostic.message}"
        if diagnostic.path:
            line += f" ({diagnostic.path})"
        print(line)
        if diagnostic.hint:
            print(f"  hint: {diagnostic.hint}")

    counts = report.counts()
    print(
        "Summary: "
        f"{counts[INFO]} info, {counts[WARNING]} warning, {counts[ERROR]} error"
    )
    return report.exit_code(strict=strict)


def validate_command(args):
    report = validate_project(
        PROJECT_RAPID_DIR,
        CURRENT_DIR,
        CONFIG_FILE,
        TEMPLATES_DIR,
        DEFAULT_AGENT_REGISTRY,
    )
    from rapid_os.orchestration.session import validate_session
    session_report = validate_session(PROJECT_RAPID_DIR, CURRENT_DIR)
    report = report.merge(session_report)
    sys.exit(render_validation_report(report, args.json, args.strict))


def _agent_shortcuts_or_hooks_installed():
    """True when the project has /rapid-<mode> shortcuts or Rapid OS hooks that call `rapid`."""
    from rapid_os.adapters.claude_hooks import hooks_installed
    from rapid_os.adapters.shortcut_installer import ShortcutError, list_entries, resolve_harness_ids

    if hooks_installed(CURRENT_DIR):
        return True
    try:
        tools = load_project_config(CONFIG_FILE).get("tools", [])
        entries, _skipped = list_entries(
            CURRENT_DIR, resolve_harness_ids(None, tools), TEMPLATES_DIR
        )
    except (ShortcutError, OSError, ValueError):
        return False
    return any(entry.state in ("installed", "outdated") for entry in entries)


def doctor_command(args):
    diagnostics = [
        Diagnostic(INFO, "RAPID900", f"Current directory: {CURRENT_DIR}", CURRENT_DIR),
        Diagnostic(INFO, "RAPID901", f"Rapid home: {RAPID_HOME}", RAPID_HOME),
        Diagnostic(INFO, "RAPID902", f"Script directory: {SCRIPT_DIR}", SCRIPT_DIR),
        Diagnostic(INFO, "RAPID903", f"Templates directory: {TEMPLATES_DIR}", TEMPLATES_DIR),
        Diagnostic(
            INFO,
            "RAPID904",
            f"Project Rapid OS directory: {PROJECT_RAPID_DIR}",
            PROJECT_RAPID_DIR,
        ),
        Diagnostic(INFO, "RAPID905", f"Config file: {CONFIG_FILE}", CONFIG_FILE),
    ]

    if CONFIG_FILE.exists():
        loaded_cfg = _load_config_with_warning(CONFIG_FILE)
        def_harness = loaded_cfg.get("default_harness")
        t_cmd = loaded_cfg.get("test_command")
        harness_str = def_harness if def_harness else "(not set; fallback: cursor)"
        test_cmd_str = json.dumps(t_cmd) if t_cmd else "(not set)"
        diagnostics.append(
            Diagnostic(INFO, "RAPID908", f"Default harness: {harness_str}", CONFIG_FILE)
        )
        diagnostics.append(
            Diagnostic(INFO, "RAPID909", f"Test command: {test_cmd_str}", CONFIG_FILE)
        )

    from rapid_os.core.ancestry import find_agent_ancestor, read_ancestry

    ancestry = read_ancestry()
    harness_ancestor = find_agent_ancestor(ancestry)
    if ancestry.error:
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID1319",
                f"Process ancestry could not be read ({ancestry.error}); 'rapid approve' cannot look for "
                "an agent harness among its parent processes and relies on the TTY and "
                "CLAUDE_CODE_CHILD_SESSION checks only.",
            )
        )
    elif harness_ancestor is not None:
        diagnostics.append(
            Diagnostic(
                INFO,
                "RAPID1319",
                f"Running under the agent harness '{harness_ancestor.harness}' (ancestor process "
                f"'{harness_ancestor.ancestor.name}', pid {harness_ancestor.ancestor.pid}): "
                "'rapid approve' is refused here (RAPID1310); run it in your own terminal.",
            )
        )

    from rapid_os.adapters.claude_hooks import hooks_installed

    if hooks_installed(CURRENT_DIR) and shutil.which("rapid") is None:
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID1339",
                "Claude Code hooks are installed in .claude/settings.json but 'rapid' is not on PATH; "
                "the hooks cannot start (Claude Code treats that as a non-blocking error) and the run is not enforced.",
                CURRENT_DIR / ".claude" / "settings.json",
                hint="Install Rapid OS where Claude Code can find it (for example 'pipx install git+https://github.com/alyconr/Rapid-OS.git') or add its scripts directory to PATH.",
            )
        )

    if shutil.which("rapid") is None and _agent_shortcuts_or_hooks_installed():
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID1414",
                RAPID_NOT_ON_PATH_MESSAGE.removeprefix("RAPID1414 "),
                CURRENT_DIR,
                hint="Install Rapid OS with the installer or with 'pipx install git+https://github.com/alyconr/Rapid-OS.git'.",
            )
        )

    if not check_node_installed():
        diagnostics.append(
            Diagnostic(
                WARNING,
                "RAPID906",
                "Node.js/npx is not available. Remote skills and some MCP flows may not work.",
            )
        )

    report = ValidationReport(tuple(diagnostics)).merge(validate_templates(TEMPLATES_DIR))

    if PROJECT_RAPID_DIR.exists():
        report = report.merge(
            validate_project_standards(PROJECT_RAPID_DIR),
            validate_project_config(CONFIG_FILE, DEFAULT_AGENT_REGISTRY),
            validate_stack_topology(PROJECT_RAPID_DIR, TEMPLATES_DIR),
            validate_composed_context(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_project_intelligence(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_spec_registry(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_execution_policy(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_run_registry(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_harness_registry(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_capability_lock(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_evidence_registry(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_eval_registry(PROJECT_RAPID_DIR, CURRENT_DIR),
        )
    else:
        report = report.extend(
            (
                Diagnostic(
                    INFO,
                    "RAPID907",
                    "No Rapid OS project detected in the current directory.",
                    PROJECT_RAPID_DIR,
                ),
            )
        )

    sys.exit(render_validation_report(report, args.json, args.strict))


def inspect_context_command(args):
    inspection = inspect_project_context(PROJECT_RAPID_DIR, CURRENT_DIR, CONFIG_FILE)

    if args.json:
        print(
            json.dumps(
                inspection.to_dict(
                    strict=False,
                    include_context=not args.summary,
                ),
                indent=2,
            )
        )
        sys.exit(inspection.report.exit_code())

    render_validation_report(inspection.report)
    print("\nIncluded sections:")
    if inspection.included_sections:
        for section in inspection.included_sections:
            print(f"- {section}")
    else:
        print("- none")

    print("\nSelected tools:")
    if inspection.selected_tools:
        for tool in inspection.selected_tools:
            print(f"- {tool}")
    else:
        print("- none")

    print(f"\nContext length: {len(inspection.context)} characters")
    if not args.summary:
        print("\n--- Context Preview ---")
        print(inspection.context)

    sys.exit(inspection.report.exit_code())


SCAN_CATEGORY_LABELS = (
    ("language", "Languages"),
    ("framework", "Frameworks"),
    ("package_manager", "Package Managers"),
    ("docker", "Docker"),
    ("testing", "Testing"),
    ("monorepo", "Monorepo"),
    ("database", "Databases"),
    ("deploy_provider", "Deployment"),
)


def render_project_intelligence_summary(model, verbose=False) -> str:
    lines = ["Rapid OS Project Intelligence"]
    if not model.facts:
        lines.append("")
        lines.append("No project facts detected.")
        return "\n".join(lines)

    rendered_categories = set()
    for category, heading in SCAN_CATEGORY_LABELS:
        facts = model.facts_for(category)
        if not facts:
            continue
        rendered_categories.add(category)
        lines.append("")
        lines.append(heading)
        for fact in facts:
            lines.append(
                f"  {fact.value:<22} {fact.confidence.value:<8} ({fact.detector})"
            )
            if verbose:
                for item in fact.evidence:
                    lines.append(
                        f"    - {item.portable_path()}: {item.reason} [{item.source_type.value}]"
                    )

    for category in model.categories():
        if category in rendered_categories:
            continue
        facts = model.facts_for(category)
        lines.append("")
        lines.append(category.replace("_", " ").title())
        for fact in facts:
            lines.append(
                f"  {fact.value:<22} {fact.confidence.value:<8} ({fact.detector})"
            )
            if verbose:
                for item in fact.evidence:
                    lines.append(
                        f"    - {item.portable_path()}: {item.reason} [{item.source_type.value}]"
                    )

    return "\n".join(lines)


def scan_command(args):
    model = build_project_model(CURRENT_DIR)
    snapshot_path = None
    if getattr(args, "write", False):
        snapshot_path = write_project_snapshot(
            model,
            PROJECT_RAPID_DIR,
            backup=True,
        )

    if getattr(args, "json", False):
        print(model.to_json(indent=2))
        return 0

    print(
        render_project_intelligence_summary(
            model,
            verbose=getattr(args, "verbose", False),
        )
    )
    if snapshot_path is not None:
        print_success(f"Snapshot escrito en: {snapshot_path}")
    return 0


def render_context_manifest(manifest: ContextManifest) -> str:
    lines = [
        "Rapid OS Context Manifest",
        "",
        f"Mode: {manifest.mode}",
        f"Harness: {manifest.harness or 'default'}",
        f"Budget: {manifest.compiled_chars} / {manifest.budget_max_chars} chars",
        "",
        "SELECTED",
    ]
    if manifest.selected:
        for entry in manifest.selected:
            chars_label = f"{entry.chars} chars"
            lines.append(
                f"  {entry.source_id:<22} {entry.priority_label:<9} {chars_label:<12} {entry.reason}"
            )
    else:
        lines.append("  none")

    lines.append("")
    lines.append("SKIPPED")
    if manifest.skipped:
        for entry in manifest.skipped:
            chars_label = f"{entry.chars} chars"
            lines.append(
                f"  {entry.source_id:<22} {entry.priority_label:<9} {chars_label:<12} {entry.reason}"
            )
    else:
        lines.append("  none")

    lines.append("")
    lines.append("CONFLICTS")
    if manifest.conflicts:
        for conflict in manifest.conflicts:
            lines.append(
                f"  {conflict.category:<21} {', '.join(conflict.sources)} -> winner: {conflict.winner} ({conflict.reason})"
            )
    else:
        lines.append("  none")

    return "\n".join(lines)


def context_command(args):
    """Compile task-specific context (read-only: never writes files, never prompts)."""
    try:
        request_kwargs = {
            "mode": getattr(args, "mode", None) or "general",
            "objective": getattr(args, "objective", None) or "",
            "tags": tuple(getattr(args, "tag", None) or ()),
            "affected_paths": tuple(getattr(args, "path", None) or ()),
            "constraints": tuple(getattr(args, "constraint", None) or ()),
            "max_chars": getattr(args, "max_chars", None),
            "spec_id": getattr(args, "spec", None),
            "spec_revision": getattr(args, "spec_revision", None),
        }
        if getattr(args, "harness", None):
            request_kwargs["harness"] = args.harness
        request = ContextRequest(**request_kwargs)
    except ValueError as exc:
        code = getattr(exc, "code", None) or "RAPID705"
        print(
            f"{code} Solicitud de contexto invalida: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    discovery = ContextSourceLoader().load(
        CURRENT_DIR, PROJECT_RAPID_DIR, request=request
    )
    if discovery.load_errors:
        for err in discovery.load_errors:
            err_code = getattr(err, "code", None) or "RAPID704"
            print(
                f"{err_code} No se pudo leer la fuente de contexto {err.source_id} ({err.path}): {err.message}",
                file=sys.stderr,
            )
        sys.exit(1)

    try:
        compiled = ContextCompiler().compile(
            request=request,
            sources=discovery.sources,
            project_model=discovery.project_model,
        )
    except ContextRequiredSourceMissingError as exc:
        if exc.manifest is not None:
            for entry in exc.manifest.skipped:
                if entry.required:
                    print(
                        f"RAPID701 {entry.source_id}: {entry.reason}",
                        file=sys.stderr,
                    )
        else:
            print(f"RAPID701 {exc}", file=sys.stderr)
        sys.exit(1)
    except ContextBudgetExceededError as exc:
        print(f"RAPID702 {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"RAPID705 {exc}", file=sys.stderr)
        sys.exit(1)

    # Diagnostics go to stderr so stdout stays machine-readable in --json mode.
    for conflict in compiled.manifest.conflicts:
        print(
            f"RAPID703 Conflicto de contexto en '{conflict.category}': "
            f"{', '.join(conflict.sources)} (prevalece {conflict.winner})",
            file=sys.stderr,
        )

    if getattr(args, "json", False):
        print(compiled.to_json(indent=2))
        return 0
    if getattr(args, "manifest", False):
        print(render_context_manifest(compiled.manifest))
        return 0

    print(compiled.content, end="")
    return 0


def _prompt_with_default(prompt_label: str, default_value: str = "") -> str:
    try:
        raw = input(prompt_label).strip()
    except (EOFError, StopIteration):
        raw = ""
    return raw if raw else default_value


def _prompt_list_with_default(
    prompt_label: str,
    default_items: tuple[str, ...] = (),
) -> tuple[str, ...]:
    try:
        raw = input(prompt_label).strip()
    except (EOFError, StopIteration):
        raw = ""
    if not raw:
        return tuple(default_items)
    return tuple(parse_list(raw))


SPEC_AUTHORING_SCALAR_FIELDS = (
    "title",
    "mode",
    "business_objective",
    "problem_statement",
    "data_impact",
)

SPEC_AUTHORING_LIST_FIELDS = (
    "scope",
    "out_of_scope",
    "actors_users",
    "main_flow",
    "edge_cases",
    "business_rules",
    "technical_constraints",
    "affected_paths",
    "acceptance_criteria",
    "testing_strategy",
    "implementation_tasks",
    "tags",
)


def _extract_non_interactive_spec_fields(args) -> dict[str, object]:
    """Extract explicitly supplied CLI authoring flags without prompting."""
    fields: dict[str, object] = {}
    for scalar_name in SPEC_AUTHORING_SCALAR_FIELDS:
        val = getattr(args, scalar_name, None)
        if val is not None:
            fields[scalar_name] = val
    for list_name in SPEC_AUTHORING_LIST_FIELDS:
        val = getattr(args, list_name, None)
        if val is not None:
            fields[list_name] = tuple(val)
    return fields


def _has_non_interactive_spec_flags(args, *, is_create: bool = False) -> bool:
    for name in SPEC_AUTHORING_SCALAR_FIELDS + SPEC_AUTHORING_LIST_FIELDS:
        if getattr(args, name, None) is not None:
            return True
    if is_create:
        if getattr(args, "status", None) is not None:
            return True
        if getattr(args, "export_legacy", False):
            return True
    if getattr(args, "json", False):
        return True
    return False


def _collect_spec_wizard_fields(
    *,
    explicit_id: str | None = None,
    base_revision: SpecRevision | None = None,
) -> dict[str, object]:
    is_revise = base_revision is not None
    header = "✏️  SPEC REVISE WIZARD" if is_revise else "📐 SPEC WIZARD (v3 Registry)"
    print(f"\n{header}")
    print("Modo:")
    print(" 1) feature")
    print(" 2) refactor")
    print(" 3) bugfix")
    print(" 4) hardening")
    print(" 5) research")
    print("Tip: usa comas o punto y coma para respuestas tipo lista.")

    resolved_id = explicit_id
    if not is_revise and not resolved_id:
        raw_id = _prompt_with_default("Spec ID (Enter para derivar del nombre): ", "")
        if raw_id:
            resolved_id = raw_id

    default_title = base_revision.title if base_revision else ""
    default_mode = base_revision.mode.value if base_revision else SpecMode.FEATURE.value
    title = _prompt_with_default("Nombre iniciativa: ", default_title)
    mode_input = _prompt_with_default("Modo [1]: ", default_mode)
    mode = SpecMode.coerce(mode_input) if mode_input else SpecMode.FEATURE

    business_objective = _prompt_with_default(
        "Objetivo de negocio: ",
        base_revision.business_objective if base_revision else "",
    )
    problem_statement = _prompt_with_default(
        "Problema a resolver: ",
        base_revision.problem_statement if base_revision else "",
    )
    scope = _prompt_list_with_default(
        "Alcance: ",
        base_revision.scope if base_revision else (),
    )
    out_of_scope = _prompt_list_with_default(
        "Fuera de alcance: ",
        base_revision.out_of_scope if base_revision else (),
    )
    actors_users = _prompt_list_with_default(
        "Actores/usuarios: ",
        base_revision.actors_users if base_revision else (),
    )
    main_flow = _prompt_list_with_default(
        "Flujo principal: ",
        base_revision.main_flow if base_revision else (),
    )
    edge_cases = _prompt_list_with_default(
        "Casos borde: ",
        base_revision.edge_cases if base_revision else (),
    )
    business_rules = _prompt_list_with_default(
        "Reglas de negocio: ",
        base_revision.business_rules if base_revision else (),
    )
    technical_constraints = _prompt_list_with_default(
        "Restricciones técnicas: ",
        base_revision.technical_constraints if base_revision else (),
    )
    affected_paths = _prompt_list_with_default(
        "Archivos/módulos afectados si se conocen: ",
        base_revision.affected_paths if base_revision else (),
    )
    data_impact = _prompt_with_default(
        "Impacto en datos: ",
        base_revision.data_impact if base_revision else "",
    )
    acceptance_criteria = _prompt_list_with_default(
        "Criterios de aceptación: ",
        base_revision.acceptance_criteria if base_revision else (),
    )
    testing_strategy = _prompt_list_with_default(
        "Estrategia de pruebas: ",
        base_revision.testing_strategy if base_revision else (),
    )
    implementation_tasks = _prompt_list_with_default(
        "Tareas de implementación: ",
        base_revision.implementation_tasks if base_revision else (),
    )
    tags = _prompt_list_with_default(
        "Tags: ",
        base_revision.tags if base_revision else (),
    )

    payload: dict[str, object] = {
        "title": title,
        "mode": mode,
        "business_objective": business_objective,
        "problem_statement": problem_statement,
        "scope": scope,
        "out_of_scope": out_of_scope,
        "actors_users": actors_users,
        "main_flow": main_flow,
        "edge_cases": edge_cases,
        "business_rules": business_rules,
        "technical_constraints": technical_constraints,
        "affected_paths": affected_paths,
        "data_impact": data_impact,
        "acceptance_criteria": acceptance_criteria,
        "testing_strategy": testing_strategy,
        "implementation_tasks": implementation_tasks,
        "tags": tags,
    }
    if resolved_id is not None:
        payload["spec_id"] = resolved_id
    return payload


def render_spec_show_text(
    record,
    revision: SpecRevision,
    artifact_paths: dict[str, str],
) -> str:
    scope_summary = ", ".join(revision.scope) if revision.scope else "none"
    paths_summary = (
        ", ".join(revision.affected_paths) if revision.affected_paths else "none"
    )
    tags_summary = ", ".join(revision.tags) if revision.tags else "none"
    lines = [
        f"ID:               {record.id}",
        f"Status:           {record.status.value}",
        f"Current Revision: r{record.current_revision}",
        f"Revision:         r{revision.revision}",
        f"Title:            {revision.title}",
        f"Mode:             {revision.mode.value}",
        f"Business Obj:     {revision.business_objective or 'none'}",
        f"Problem:          {revision.problem_statement or 'none'}",
        f"Scope:            {scope_summary}",
        f"Affected Paths:   {paths_summary}",
        f"Tags:             {tags_summary}",
        "Artifacts:",
    ]
    for name in ("requirements.md", "tasks.md", "acceptance.md"):
        if name in artifact_paths:
            lines.append(f"  - {artifact_paths[name]}")
    return "\n".join(lines)


def spec_command(args):
    """Execute `rapid spec` subcommands (`create`, `list`, `show`, `revise`, `status`, `export-legacy`)."""
    action = getattr(args, "spec_action", None) or getattr(args, "action", None)
    try:
        registry = SpecRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)

        if action == "list":
            records = registry.list_specs()
            status_filter = getattr(args, "status", None)
            if status_filter is not None:
                coerced_filter = SpecStatus.coerce(status_filter)
                records = tuple(
                    rec for rec in records if rec.status == coerced_filter
                )
            if getattr(args, "json", False):
                payload = {
                    "schema_version": SPEC_SCHEMA_VERSION,
                    "specs": [rec.to_dict() for rec in records],
                }
                print(json.dumps(payload, indent=2))
                return 0
            if not records:
                print("No specs registered.")
                return 0
            for rec in records:
                print(
                    f"{rec.id:<25} {rec.status.value:<10} r{rec.current_revision}"
                )
            return 0

        if action == "show":
            spec_id = getattr(args, "spec_id", None) or getattr(args, "id", None)
            rev_arg = getattr(args, "revision", None)
            record = registry.get(spec_id)
            revision = registry.get_revision(spec_id, revision=rev_arg)
            artifact_paths = registry.get_artifact_paths(
                spec_id,
                revision=revision.revision,
            )
            if getattr(args, "json", False):
                payload = {
                    "schema_version": SPEC_SCHEMA_VERSION,
                    "id": record.id,
                    "status": record.status.value,
                    "current_revision": record.current_revision,
                    "spec": record.to_dict(),
                    "record": record.to_dict(),
                    "revision": revision.to_dict(),
                    "artifacts": artifact_paths,
                }
                print(json.dumps(payload, indent=2))
                return 0
            print(render_spec_show_text(record, revision, artifact_paths))
            return 0

        if action == "create":
            explicit_id = getattr(args, "spec_id", None) or getattr(
                args, "id", None
            )
            if _has_non_interactive_spec_flags(args, is_create=True):
                fields = _extract_non_interactive_spec_fields(args)
                raw_title = str(fields.get("title") or "").strip()
                if not raw_title:
                    raise InvalidRevisionManifestError(
                        "Spec 'title' (--title) is required in non-interactive mode."
                    )
                if explicit_id is not None:
                    fields["spec_id"] = explicit_id
            else:
                fields = _collect_spec_wizard_fields(explicit_id=explicit_id)

            created_record = registry.create(**fields)
            requested_status = getattr(args, "status", None)
            if requested_status == "ready":
                created_record = registry.set_status(
                    created_record.id,
                    SpecStatus.READY,
                )
            elif requested_status is not None and requested_status != "draft":
                raise InvalidRevisionManifestError(
                    f"Invalid initial spec status '{requested_status}': only 'draft' or 'ready' are allowed on create."
                )

            written_legacy = ()
            if getattr(args, "export_legacy", False):
                written_legacy = registry.export_legacy(
                    created_record.id,
                    CURRENT_DIR,
                    revision=created_record.current_revision,
                )

            if getattr(args, "json", False):
                created_rev = registry.get_revision(
                    created_record.id,
                    revision=created_record.current_revision,
                )
                payload = {
                    **created_record.to_dict(),
                    "spec": created_record.to_dict(),
                    "revision": created_rev.to_dict(),
                }
                if written_legacy:
                    payload["legacy_exports"] = [
                        target.name for target in written_legacy
                    ]
                print(json.dumps(payload, indent=2))
                return 0

            print_success(
                f"Spec '{created_record.id}' creada (r{created_record.current_revision}, status={created_record.status.value})"
            )
            for target in written_legacy:
                print_success(f"{target.name} exportado")
            return 0

        if action == "revise":
            spec_id = getattr(args, "spec_id", None) or getattr(args, "id", None)
            record = registry.get(spec_id)
            current_rev = registry.get_revision(spec_id, record.current_revision)
            if _has_non_interactive_spec_flags(args, is_create=False):
                fields = _extract_non_interactive_spec_fields(args)
            else:
                fields = _collect_spec_wizard_fields(
                    explicit_id=record.id,
                    base_revision=current_rev,
                )
                fields.pop("spec_id", None)

            updated_record = registry.revise(spec_id, **fields)
            if getattr(args, "json", False):
                updated_rev = registry.get_revision(
                    updated_record.id,
                    revision=updated_record.current_revision,
                )
                payload = {
                    **updated_record.to_dict(),
                    "spec": updated_record.to_dict(),
                    "revision": updated_rev.to_dict(),
                }
                print(json.dumps(payload, indent=2))
                return 0

            print_success(
                f"Spec '{updated_record.id}' actualizada a r{updated_record.current_revision} (status={updated_record.status.value})"
            )
            return 0

        if action == "status":
            spec_id = getattr(args, "spec_id", None) or getattr(args, "id", None)
            target_status = getattr(args, "status", None)
            updated_record = registry.set_status(spec_id, target_status)
            if getattr(args, "json", False):
                print(updated_record.to_json(indent=2))
                return 0
            print_success(
                f"Spec '{updated_record.id}' status -> {updated_record.status.value} (r{updated_record.current_revision})"
            )
            return 0

        if action == "export-legacy":
            spec_id = getattr(args, "spec_id", None) or getattr(args, "id", None)
            rev_arg = getattr(args, "revision", None)
            written = registry.export_legacy(
                spec_id,
                CURRENT_DIR,
                revision=rev_arg,
            )
            for target in written:
                print_success(f"{target.name} exportado")
            return 0

        print("RAPID801 Subcomando 'rapid spec' requerido.", file=sys.stderr)
        sys.exit(1)
    except SpecRegistryError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"RAPID801 {exc}", file=sys.stderr)
        sys.exit(1)


def render_policy_show_text(policy, source: str) -> str:
    waivable_str = (
        ", ".join(policy.waivable_gate_ids)
        if policy.waivable_gate_ids
        else "none"
    )
    extra_gates_str = (
        ", ".join(policy.extra_required_gate_ids)
        if policy.extra_required_gate_ids
        else "none"
    )
    workspace_str = ", ".join(
        f"{k}={v}" for k, v in policy.workspace_by_risk.items()
    )
    return "\n".join(
        [
            "Rapid OS Execution Policy",
            f"Source:                 {source}",
            f"Schema Version:         {policy.schema_version}",
            f"Minimum Classification: {policy.minimum_classification.value}",
            f"Minimum Risk:           {policy.minimum_risk.label}",
            f"Workspace by Risk:      {workspace_str}",
            f"Waivable Gate IDs:      {waivable_str}",
            f"Extra Required Gates:   {extra_gates_str}",
            f"Policy Digest:          {policy.digest}",
        ]
    )


def policy_command(args):
    """Execute `rapid policy` subcommands (`show`, `init`)."""
    action = getattr(args, "policy_action", None) or getattr(
        args, "action", None
    )
    try:
        if action == "show":
            policy, source = load_execution_policy(
                CURRENT_DIR,
                PROJECT_RAPID_DIR,
            )
            if getattr(args, "json", False):
                payload = {
                    **policy.to_dict(),
                    "source": source,
                    "policy_digest": policy.content_digest(),
                    "policy": policy.to_dict(),
                }
                print(json.dumps(payload, indent=2))
                return 0
            print(render_policy_show_text(policy, source))
            return 0

        if action == "init":
            written_path = write_default_execution_policy(
                CURRENT_DIR,
                PROJECT_RAPID_DIR,
            )
            policy, source = load_execution_policy(
                CURRENT_DIR,
                PROJECT_RAPID_DIR,
            )
            if getattr(args, "json", False):
                payload = {
                    **policy.to_dict(),
                    "source": source,
                    "path": written_path.relative_to(CURRENT_DIR).as_posix(),
                    "policy_digest": policy.content_digest(),
                    "policy": policy.to_dict(),
                }
                print(json.dumps(payload, indent=2))
                return 0
            print_success(f"Execution policy inicializada en: {written_path}")
            return 0

        print("RAPID1005 Subcomando 'rapid policy' requerido.", file=sys.stderr)
        sys.exit(1)
    except ExecutionError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"RAPID1005 {exc}", file=sys.stderr)
        sys.exit(1)


def render_run_show_text(
    record,
    contract,
    state,
    artifact_paths: dict[str, str],
) -> str:
    done_or_skipped = sum(1 for t in state.tasks if t.status.is_terminal)
    total_tasks = len(state.tasks)
    lines = [
        f"ID:                    {record.id}",
        f"Status:                {state.status.value} (s{state.revision})",
        f"Spec:                  {record.spec_id} (r{record.spec_revision})",
        f"Spec Content Digest:   {contract.spec_content_digest}",
        f"Harness:               {contract.harness}",
        f"Classification:        {contract.classification.value}",
        f"Risk:                  {contract.risk.label}",
        f"Workspace Requirement: {contract.workspace.value}",
        f"Policy Source:         {contract.policy_source}",
        f"Policy Digest:         {contract.policy_digest}",
        f"Project Model Digest:  {contract.project_model_digest}",
        f"Context Digest:        {contract.context_digest}",
        f"Contract Digest:       {contract.contract_digest}",
        "Reasons:",
    ]
    if contract.decision.reasons:
        for reason in contract.decision.reasons:
            lines.append(f"  - {reason}")
    else:
        lines.append("  - none")

    lines.append("Risk Signals:")
    if contract.risk_signals:
        for sig in contract.risk_signals:
            lines.append(
                f"  - {sig.id} ({sig.level.label}, source={sig.source}): {sig.reason}"
            )
    else:
        lines.append("  - none")

    lines.append(f"Tasks ({done_or_skipped}/{total_tasks} terminal):")
    if state.tasks:
        for task in state.tasks:
            task_line = f"  - {task.id} [{task.status.value}] {task.description}"
            if task.reason:
                task_line += f" (reason: {task.reason})"
            lines.append(task_line)
    else:
        lines.append("  - none")

    lines.append("Required Gates:")
    if state.gates:
        contract_gates_by_id = {g.id: g for g in contract.gates}
        for gate in state.gates:
            c_gate = contract_gates_by_id.get(gate.id)
            gate_reason = gate.reason or (c_gate.reason if c_gate else "")
            lines.append(
                f"  - {gate.id} ({gate.kind.value}, {gate.phase.value}, waivable={str(gate.waivable).lower()}) -> {gate.disposition.value}"
            )
            if gate_reason:
                lines.append(f"    reason: {gate_reason}")
    else:
        lines.append("  - none")

    lines.append("Artifacts:")
    for name in (
        "run.json",
        "contract.json",
        "context.md",
        "context-manifest.json",
        "state.json",
    ):
        if name in artifact_paths:
            lines.append(f"  - {artifact_paths[name]}")
    return "\n".join(lines)


def run_command(args):
    """Execute `rapid run` subcommands (`create`, `list`, `show`, `status`, `task`, `gate`)."""
    action = getattr(args, "run_action", None) or getattr(args, "action", None)
    try:
        registry = RunRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)

        if action == "list":
            status_filter = getattr(args, "status", None)
            records = registry.list_runs(status=status_filter)
            run_items = []
            for rec in records:
                contract = registry.get_contract(rec.id)
                state = registry.get_state(rec.id)
                run_items.append((rec, contract, state))

            if getattr(args, "json", False):
                payload = {
                    "schema_version": RUN_SCHEMA_VERSION,
                    "runs": [
                        {
                            **rec.to_dict(),
                            "status": state.status.value,
                            "classification": contract.classification.value,
                            "risk": contract.risk.label,
                            "workspace": contract.workspace.value,
                            "harness": contract.harness,
                            "spec_content_digest": contract.spec_content_digest,
                        }
                        for rec, contract, state in run_items
                    ],
                }
                print(json.dumps(payload, indent=2))
                return 0

            if not run_items:
                print("No runs registered.")
                return 0

            for rec, contract, state in run_items:
                print(
                    f"{rec.id:<32} {state.status.value:<10} {contract.classification.value:<14} {contract.risk.label:<9} r{rec.spec_revision} s{rec.current_state_revision}"
                )
            return 0

        if action == "show":
            run_id = getattr(args, "run_id", None) or getattr(args, "id", None)
            state_rev = getattr(args, "state_revision", None)
            record = registry.get(run_id)
            contract = registry.get_contract(run_id)
            state = registry.get_state(run_id, revision=state_rev)
            artifact_paths = registry.get_artifact_paths(
                run_id,
                state_revision=state.revision,
            )
            if getattr(args, "json", False):
                payload = {
                    "schema_version": RUN_SCHEMA_VERSION,
                    **record.to_dict(),
                    "status": state.status.value,
                    "classification": contract.classification.value,
                    "risk": contract.risk.label,
                    "workspace": contract.workspace.value,
                    "harness": contract.harness,
                    "spec_content_digest": contract.spec_content_digest,
                    "policy_source": contract.policy_source,
                    "policy_digest": contract.policy_digest,
                    "project_model_digest": contract.project_model_digest,
                    "context_digest": contract.context_digest,
                    "context_manifest_digest": contract.context_manifest_digest,
                    "reasons": list(contract.decision.reasons),
                    "risk_signals": [s.to_dict() for s in contract.risk_signals],
                    "tasks": [t.to_dict() for t in state.tasks],
                    "gates": [g.to_dict() for g in state.gates],
                    "run": record.to_dict(),
                    "record": record.to_dict(),
                    "contract": contract.to_dict(),
                    "state": state.to_dict(),
                    "artifacts": artifact_paths,
                }
                print(json.dumps(payload, indent=2))
                return 0
            print(render_run_show_text(record, contract, state, artifact_paths))
            return 0

        if action == "create":
            spec_id = getattr(args, "spec", None)
            if not spec_id or not str(spec_id).strip():
                raise InvalidSpecBindingError(
                    "Option '--spec' is required to create a run."
                )
            config = _load_config_with_warning(CONFIG_FILE)
            detection = detect_harness(
                getattr(args, "harness", None),
                os.environ,
                config,
            )
            if detection.source == "fallback" and detection.warning:
                print(detection.warning, file=sys.stderr)

            record = registry.create(
                spec_id=spec_id,
                spec_revision=getattr(args, "spec_revision", None),
                run_id=getattr(args, "run_id", None),
                harness=detection.harness_id,
                classification=getattr(args, "classification", None),
                risk=getattr(args, "risk", None),
            )
            contract = registry.get_contract(record.id)
            state = registry.get_state(record.id)
            artifact_paths = registry.get_artifact_paths(record.id)

            if getattr(args, "json", False):
                payload = {
                    **record.to_dict(),
                    "status": state.status.value,
                    "classification": contract.classification.value,
                    "risk": contract.risk.label,
                    "workspace": contract.workspace.value,
                    "harness": contract.harness,
                    "harness_source": detection.source,
                    "spec_content_digest": contract.spec_content_digest,
                    "run": record.to_dict(),
                    "contract": contract.to_dict(),
                    "state": state.to_dict(),
                    "artifacts": artifact_paths,
                }
                print(json.dumps(payload, indent=2))
                return 0
            print_success(
                f"Run '{record.id}' creado (spec={record.spec_id}@r{record.spec_revision}, status={state.status.value}, class={contract.classification.value}, risk={contract.risk.label})"
            )
            return 0

        if action == "status":
            run_id = getattr(args, "run_id", None) or getattr(args, "id", None)
            target_status = getattr(args, "status", None)
            reason = getattr(args, "reason", None) or ""
            next_state = registry.transition_status(
                run_id,
                target_status,
                reason=reason,
            )
            updated_record = registry.get(run_id)
            if getattr(args, "json", False):
                payload = {
                    **updated_record.to_dict(),
                    "status": next_state.status.value,
                    "run": updated_record.to_dict(),
                    "state": next_state.to_dict(),
                }
                print(json.dumps(payload, indent=2))
                return 0
            print_success(
                f"Run '{updated_record.id}' status -> {next_state.status.value} (s{next_state.revision})"
            )
            return 0

        if action == "task":
            run_id = getattr(args, "run_id", None) or getattr(args, "id", None)
            task_id = getattr(args, "task_id", None)
            target_status = getattr(args, "status", None)
            reason = getattr(args, "reason", None) or ""
            next_state = registry.transition_task(
                run_id,
                task_id,
                target_status,
                reason=reason,
            )
            updated_record = registry.get(run_id)
            if getattr(args, "json", False):
                payload = {
                    **updated_record.to_dict(),
                    "status": next_state.status.value,
                    "run": updated_record.to_dict(),
                    "state": next_state.to_dict(),
                }
                print(json.dumps(payload, indent=2))
                return 0
            print_success(
                f"Run '{updated_record.id}' task '{task_id}' -> {target_status} (s{next_state.revision})"
            )
            return 0

        if action == "gate":
            run_id = getattr(args, "run_id", None) or getattr(args, "id", None)
            gate_id = getattr(args, "gate_id", None)
            disposition = getattr(args, "disposition", None)
            reason = getattr(args, "reason", None) or ""
            next_state = registry.transition_gate(
                run_id,
                gate_id,
                disposition,
                reason=reason,
            )
            updated_record = registry.get(run_id)
            if getattr(args, "json", False):
                payload = {
                    **updated_record.to_dict(),
                    "status": next_state.status.value,
                    "run": updated_record.to_dict(),
                    "state": next_state.to_dict(),
                }
                print(json.dumps(payload, indent=2))
                return 0
            print_success(
                f"Run '{updated_record.id}' gate '{gate_id}' -> {disposition} (s{next_state.revision})"
            )
            return 0

        print("RAPID1001 Subcomando 'rapid run' requerido.", file=sys.stderr)
        sys.exit(1)
    except ExecutionError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except SpecRegistryError as exc:
        print(f"RAPID1003 {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"RAPID1001 {exc}", file=sys.stderr)
        sys.exit(1)


def render_harness_show_text(resolved) -> str:
    profile = resolved.profile
    lines = [
        f"ID:             {resolved.id}",
        f"Source:         {resolved.source}",
        f"Profile Digest: {resolved.profile_digest}",
        "Capabilities:",
    ]
    if profile.capabilities:
        for cap in profile.capabilities:
            lines.append(
                f"  - {cap.capability_id:<22} {cap.status.value:<12} ({cap.reason})"
            )
    else:
        lines.append("  - none")
    return "\n".join(lines)


def render_capability_resolution_text(resolution, *, run_id: str = "") -> str:
    lines = []
    if run_id:
        lines.append(f"Run:               {run_id}")
    lines.extend(
        [
            f"Harness:           {resolution.harness_id}",
            f"Profile Source:    {resolution.profile_source}",
            f"Profile Digest:    {resolution.profile_digest}",
            f"Contract Digest:   {resolution.contract_digest}",
            f"Resolution Digest: {resolution.resolution_digest}",
            f"Compatibility:     {resolution.status.value.upper()} ({resolution.status.value})",
            "",
            "Required:",
        ]
    )
    if resolution.requirements:
        for req in resolution.requirements:
            lines.append(
                f"  {req.capability_id} (source={req.source}, reason={req.reason})"
            )
    else:
        lines.append("  none")

    lines.append("")
    lines.append("Satisfied:")
    if resolution.satisfied:
        for cap_id in resolution.satisfied:
            lines.append(f"  {cap_id}")
    else:
        lines.append("  none")

    lines.append("")
    lines.append("Missing:")
    if resolution.missing:
        for cap_id in resolution.missing:
            lines.append(f"  {cap_id}")
    else:
        lines.append("  none")

    lines.append("")
    lines.append("Unknown:")
    if resolution.unknown:
        for cap_id in resolution.unknown:
            lines.append(f"  {cap_id}")
    else:
        lines.append("  none")

    return "\n".join(lines)


def harness_command(args):
    """Execute `rapid harness` subcommands (`list`, `show`, `init`, `lock`, `resolve`)."""
    action = getattr(args, "harness_action", None) or getattr(args, "action", None)
    try:
        registry = HarnessRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)

        if action == "list":
            profiles = registry.list_profiles()
            if getattr(args, "json", False):
                payload = {
                    "schema_version": HARNESS_PROFILE_SCHEMA_VERSION,
                    "profiles": [
                        {
                            "id": item.id,
                            "source": item.source,
                            "profile_digest": item.profile_digest,
                            "content_digest": item.profile_digest,
                            "capabilities": [
                                cap.to_dict() for cap in item.profile.capabilities
                            ],
                            "profile": item.profile.to_dict(),
                        }
                        for item in profiles
                    ],
                }
                print(json.dumps(payload, indent=2))
                return 0

            for item in profiles:
                print(
                    f"{item.id:<20} {item.source:<36} {item.profile_digest[:12]}"
                )
            return 0

        if action == "show":
            harness_id = getattr(args, "harness_id", None) or getattr(args, "id", None)
            resolved = registry.resolve_active_profile(harness_id)
            if getattr(args, "json", False):
                payload = {
                    "schema_version": HARNESS_PROFILE_SCHEMA_VERSION,
                    "id": resolved.id,
                    "source": resolved.source,
                    "profile_digest": resolved.profile_digest,
                    "content_digest": resolved.profile_digest,
                    "capabilities": [
                        cap.to_dict() for cap in resolved.profile.capabilities
                    ],
                    "profile": resolved.profile.to_dict(),
                }
                print(json.dumps(payload, indent=2))
                return 0
            print(render_harness_show_text(resolved))
            return 0

        if action == "init":
            harness_id = getattr(args, "harness_id", None) or getattr(args, "id", None)
            path = registry.initialize_project_profile(harness_id)
            resolved = registry.resolve_active_profile(harness_id)
            if getattr(args, "json", False):
                payload = {
                    "schema_version": HARNESS_PROFILE_SCHEMA_VERSION,
                    "id": resolved.id,
                    "source": resolved.source,
                    "path": resolved.source,
                    "profile_digest": resolved.profile_digest,
                    "content_digest": resolved.profile_digest,
                    "capabilities": [
                        cap.to_dict() for cap in resolved.profile.capabilities
                    ],
                    "profile": resolved.profile.to_dict(),
                }
                print(json.dumps(payload, indent=2))
                return 0
            print_success(f"Harness profile '{resolved.id}' escrito en: {path}")
            return 0

        if action == "lock":
            lock_obj, lock_path = write_capability_lock(
                CURRENT_DIR,
                PROJECT_RAPID_DIR,
                registry=registry,
            )
            if getattr(args, "json", False):
                print(lock_obj.to_json(indent=2))
                return 0
            print_success(
                f"Capabilities lock escrito en: {lock_path} ({len(lock_obj.profiles)} profiles)"
            )
            return 0

        if action == "resolve":
            run_id = getattr(args, "run", None) or getattr(args, "run_id", None)
            if not run_id or not str(run_id).strip():
                raise InvalidCapabilityResolutionError(
                    "Option '--run' is required to resolve harness capabilities."
                )
            run_registry = RunRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)
            record = run_registry.get(run_id)
            contract = run_registry.get_contract(record.id)

            if getattr(args, "locked", False):
                lock_obj = load_capability_lock(CURRENT_DIR, PROJECT_RAPID_DIR)
                locked_entry = lock_obj.get_profile(contract.harness)
                target_profile = locked_entry.profile
                target_source = locked_entry.source
            else:
                resolved = registry.resolve_active_profile(contract.harness)
                target_profile = resolved.profile
                target_source = resolved.source

            extra_reqs = tuple(getattr(args, "require", None) or ())
            resolution = CapabilityResolver().resolve(
                contract,
                target_profile,
                profile_source=target_source,
                extra_requirements=extra_reqs,
            )

            if getattr(args, "json", False):
                print(resolution.to_json(indent=2))
            else:
                print(render_capability_resolution_text(resolution, run_id=record.id))

            if (
                getattr(args, "require_compatible", False)
                and resolution.status != CompatibilityStatus.COMPATIBLE
            ):
                raise IncompatibleHarnessError(
                    f"Harness '{resolution.harness_id}' is not compatible with run '{record.id}' (status={resolution.status.value}). "
                    "Declare or verify required capabilities in '.rapid-os/harnesses/' or select a compatible harness."
                )
            return 0

        print(
            "RAPID1102 Subcomando 'rapid harness' requerido (use: list, show, init, lock, resolve).",
            file=sys.stderr,
        )
        sys.exit(1)
    except HarnessCapabilityError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except ExecutionError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        code = getattr(exc, "code", None) or "RAPID1102"
        print(f"{code} {exc}", file=sys.stderr)
        sys.exit(1)


def render_evidence_show_text(evidence: RunEvidence) -> str:
    lines = [
        f"Evidence: {evidence.id}",
        f"Run: {evidence.run_id}",
        f"Kind: {evidence.kind.value}",
        f"Producer: {evidence.producer}",
        f"Summary: {evidence.summary}",
        f"Contract Digest: {evidence.contract_digest}",
        f"State Revision: s{evidence.state_revision} ({evidence.state_digest})",
        f"Content Digest: {evidence.content_digest}",
        f"Tasks: {', '.join(evidence.task_ids) if evidence.task_ids else 'none'}",
        f"Gates: {', '.join(evidence.gate_ids) if evidence.gate_ids else 'none'}",
        f"Capabilities: {', '.join(evidence.capability_ids) if evidence.capability_ids else 'none'}",
        "",
        "Payload:",
    ]
    for key, val in sorted(evidence.payload.items()):
        lines.append(f"  {key}: {json.dumps(val, ensure_ascii=False)}")

    lines.append("")
    lines.append("Artifacts:")
    if evidence.artifacts:
        for art in evidence.artifacts:
            lines.append(
                f"  {art.path} ({art.size_bytes} bytes, sha256={art.sha256[:12]})"
            )
    else:
        lines.append("  none")
    return "\n".join(lines)


def evidence_command(args):
    """Execute `rapid evidence` subcommands (`list`, `show`, `add`, `verify`)."""
    action = getattr(args, "evidence_action", None) or getattr(args, "action", None)
    try:
        registry = EvidenceRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)

        if action == "list":
            run_id = getattr(args, "run", None) or getattr(args, "run_id", None)
            if not run_id or not str(run_id).strip():
                raise InvalidRunEvidenceError(
                    "Option '--run' is required to list evidence records."
                )
            records = registry.list(run_id)
            set_digest = compute_evidence_set_digest(run_id, records)
            if getattr(args, "json", False):
                payload = {
                    "schema_version": RUN_EVIDENCE_SCHEMA_VERSION,
                    "run_id": run_id,
                    "evidence_set_digest": set_digest,
                    "records": [rec.to_dict() for rec in records],
                }
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return 0

            if not records:
                print(f"No evidence records found for run '{run_id}'.")
                return 0
            for rec in records:
                print(
                    f"{rec.id:<8} s{rec.state_revision:<4} {rec.kind.value:<18} {rec.producer:<22} {rec.summary}"
                )
            return 0

        if action == "show":
            run_id = getattr(args, "run", None) or getattr(args, "run_id", None)
            evidence_id = getattr(args, "evidence_id", None) or getattr(
                args, "id", None
            )
            if not run_id or not str(run_id).strip():
                raise InvalidRunEvidenceError(
                    "Option '--run' is required to show an evidence record."
                )
            if not evidence_id or not str(evidence_id).strip():
                raise InvalidRunEvidenceError(
                    "Argument '<evidence-id>' is required to show an evidence record."
                )
            record_obj = registry.get(run_id, evidence_id)
            if getattr(args, "json", False):
                print(record_obj.to_json(indent=2))
                return 0
            print(render_evidence_show_text(record_obj))
            return 0

        if action == "add":
            run_id = getattr(args, "run", None) or getattr(args, "run_id", None)
            input_file = getattr(args, "input", None)
            if not run_id or not str(run_id).strip():
                raise InvalidRunEvidenceError(
                    "Option '--run' is required to add evidence."
                )
            if not input_file or not str(input_file).strip():
                raise InvalidRunEvidenceError(
                    "Option '--input' is required to add evidence."
                )
            input_path = Path(input_file)
            if not input_path.is_absolute():
                input_path = CURRENT_DIR / input_path
            added = registry.add(run_id, input_path)
            if getattr(args, "json", False):
                print(added.to_json(indent=2))
                return 0
            print_success(
                f"Evidence '{added.id}' ({added.kind.value}) registrada para run '{added.run_id}'."
            )
            return 0

        if action == "verify":
            run_id = getattr(args, "run", None) or getattr(args, "run_id", None)
            if not run_id or not str(run_id).strip():
                raise InvalidRunEvidenceError(
                    "Option '--run' is required to verify evidence."
                )
            records = registry.verify(run_id)
            orphans = registry.orphan_artifact_dirs(run_id)
            set_digest = compute_evidence_set_digest(run_id, records)
            if getattr(args, "json", False):
                payload = {
                    "schema_version": RUN_EVIDENCE_SCHEMA_VERSION,
                    "ok": True,
                    "run_id": run_id,
                    "record_count": len(records),
                    "evidence_set_digest": set_digest,
                    "records": [rec.to_dict() for rec in records],
                    "orphan_artifact_dirs": [p.name for p in orphans],
                }
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return 0

            print(
                f"Evidence verified for run '{run_id}': {len(records)} record(s), digest={set_digest}"
            )
            for orphan in orphans:
                print(
                    f"RAPID1209 Trailing evidence artifact {orphan.name} detected (orphan evidence artifact directory: {orphan.name}). "
                    "The previous evidence write may have been interrupted. "
                    "Resolve or inspect the orphan before adding new evidence.",
                    file=sys.stderr,
                )
            return 0

        print(
            "RAPID1202 Subcomando 'rapid evidence' requerido (use: list, show, add, verify).",
            file=sys.stderr,
        )
        sys.exit(1)
    except EvidenceError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except ExecutionError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        code = getattr(exc, "code", None) or "RAPID1202"
        print(f"{code} {exc}", file=sys.stderr)
        sys.exit(1)


def render_evaluation_report_text(
    report: EvaluationReport,
    *,
    stale: bool = False,
) -> str:
    extra_caps_text = (
        ", ".join(report.extra_capability_ids)
        if report.extra_capability_ids
        else "none"
    )
    lines = [
        f"Run: {report.run_id}",
        f"Contract Digest: {report.contract_digest}",
        f"State Revision: s{report.state_revision} ({report.state_digest})",
        f"Evidence Set Digest: {report.evidence_set_digest}",
        f"Ruleset: v{report.ruleset_version} ({report.ruleset_digest})",
        f"Extra Capabilities: {extra_caps_text}",
        f"Report Digest: {report.report_digest}",
        f"Verdict: {report.verdict.value.upper()}",
    ]
    if stale:
        lines.append("Stale: YES (RAPID1227)")

    lines.append("")
    lines.append("Assertions:")
    for item in report.assertions:
        req_tag = "required" if item.required else "optional"
        ev_str = (
            f" [evidence: {', '.join(item.evidence_ids)}]"
            if item.evidence_ids
            else ""
        )
        lines.append(
            f"  {item.id:<40} {item.status.value.upper():<16} ({req_tag}) {item.reason}{ev_str}"
        )
    return "\n".join(lines)


def eval_command(args):
    """Execute `rapid eval` subcommands (`run`, `list`, `show`)."""
    action = getattr(args, "eval_action", None) or getattr(args, "action", None)
    try:
        registry = EvalRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)

        if action == "run":
            run_id = getattr(args, "run", None) or getattr(args, "run_id", None)
            if not run_id or not str(run_id).strip():
                raise InvalidEvaluationReportError(
                    "Option '--run' is required to evaluate a run."
                )
            extra_reqs = tuple(getattr(args, "require", None) or ())
            ruleset_version = getattr(args, "ruleset", 2)
            report = registry.evaluate_run(
                run_id,
                extra_capability_requirements=extra_reqs,
                write=bool(getattr(args, "write", False)),
                ruleset_version=ruleset_version,
            )

            if getattr(args, "json", False):
                print(report.to_json(indent=2))
            else:
                print(render_evaluation_report_text(report))

            if getattr(args, "require_pass", False):
                if report.verdict == EvaluationVerdict.UNVERIFIED:
                    raise EvaluationUnverifiedError(
                        f"Evaluation for run '{report.run_id}' is unverified (verdict={report.verdict.value}). "
                        "One or more required assertions lack verified evidence; attach qualifying evidence with 'rapid evidence add' and re-run evaluation."
                    )
                if report.verdict == EvaluationVerdict.FAIL:
                    raise EvaluationFailedError(
                        f"Evaluation for run '{report.run_id}' failed (verdict={report.verdict.value}). "
                        "Inspect failing assertions in the evaluation report and resolve the underlying failures."
                    )
            return 0

        if action == "list":
            run_id = getattr(args, "run", None) or getattr(args, "run_id", None)
            if not run_id or not str(run_id).strip():
                raise InvalidEvaluationReportError(
                    "Option '--run' is required to list evaluation reports."
                )
            entries = registry.list_report_entries(run_id)
            if getattr(args, "json", False):
                payload = {
                    "schema_version": EVALUATION_REPORT_SCHEMA_VERSION,
                    "run_id": run_id,
                    "reports": [
                        {
                            "revision": rev_num,
                            "file": rep_path.name,
                            "verdict": rep_obj.verdict.value,
                            "state_revision": rep_obj.state_revision,
                            "state_digest": rep_obj.state_digest,
                            "evidence_set_digest": rep_obj.evidence_set_digest,
                            "ruleset_version": rep_obj.ruleset_version,
                            "ruleset_digest": rep_obj.ruleset_digest,
                            "extra_capability_ids": list(
                                rep_obj.extra_capability_ids
                            ),
                            "report_digest": rep_obj.report_digest,
                            "stale": is_stale,
                        }
                        for rev_num, rep_path, rep_obj, is_stale in entries
                    ],
                }
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return 0

            if not entries:
                print(f"No evaluation reports found for run '{run_id}'.")
                return 0
            for rev_num, rep_path, rep_obj, is_stale in entries:
                stale_label = "STALE" if is_stale else "CURRENT"
                print(
                    f"{rep_path.name:<12} rev={rev_num:<4} s{rep_obj.state_revision:<4} {rep_obj.verdict.value.upper():<18} {stale_label:<8} {rep_obj.report_digest[:12]}"
                )
            return 0

        if action == "show":
            run_id = getattr(args, "run", None) or getattr(args, "run_id", None)
            if not run_id or not str(run_id).strip():
                raise InvalidEvaluationReportError(
                    "Option '--run' is required to show an evaluation report."
                )
            revision = getattr(args, "revision", None)
            report = registry.get_report(run_id, revision=revision)
            stale = registry.is_report_stale(report)
            if getattr(args, "json", False):
                print(report.to_json(indent=2))
                return 0
            print(render_evaluation_report_text(report, stale=stale))
            return 0

        print(
            "RAPID1221 Subcomando 'rapid eval' requerido (use: run, list, show).",
            file=sys.stderr,
        )
        sys.exit(1)
    except EvaluationError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except EvidenceError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except HarnessCapabilityError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except ExecutionError as exc:
        print(f"{exc.code} {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        code = getattr(exc, "code", None) or "RAPID1221"
        print(f"{code} {exc}", file=sys.stderr)
        sys.exit(1)


def check_command(args):
    """Execute rapid check command."""
    import subprocess
    from rapid_os.orchestration.session import load_session
    from rapid_os.orchestration.check import run_check

    raw_argv = getattr(args, "argv", None) or []
    argv = list(raw_argv)
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print("No command provided for rapid check (use: rapid check -- <argv...>).", file=sys.stderr)
        sys.exit(1)

    session = load_session(PROJECT_RAPID_DIR)
    if not session or not session.active_run_id:
        print("RAPID1307 No active run session found (.rapid-os/session.json).", file=sys.stderr)
        sys.exit(1)

    run_id = session.active_run_id
    registry = RunRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)
    try:
        current_state = registry.get_state(run_id)
        contract = registry.get_contract(run_id)
    except Exception as exc:
        print(f"RAPID1304 Run '{run_id}' not found: {exc}", file=sys.stderr)
        sys.exit(1)

    task_arg = getattr(args, "task", None)
    task_ids = [task_arg] if task_arg else []
    gate_arg = getattr(args, "gate", None)
    gate_ids = [gate_arg] if gate_arg else []
    expect = getattr(args, "expect", "pass")

    if expect == "fail":
        if gate_arg:
            print(
                "RAPID1320 'rapid check --expect fail' cannot be bound to a gate (--gate). "
                "Expected failures must be linked exclusively to a task.",
                file=sys.stderr,
            )
            sys.exit(1)
        if not task_ids:
            in_prog = [t.id for t in current_state.tasks if t.status == TaskStatus.IN_PROGRESS]
            if len(in_prog) == 1:
                task_ids = [in_prog[0]]
            else:
                print(
                    "RAPID1320 'rapid check --expect fail' must be bound to a task via --task or "
                    f"require exactly one task in_progress (found {len(in_prog)}).",
                    file=sys.stderr,
                )
                sys.exit(1)
        gate_ids = []
    else:
        # Default binding when neither --task nor --gate is passed
        if not task_ids and not gate_ids:
            if current_state.status == RunStatus.PREPARED:
                gate_ids = ["gate.baseline"]
            elif current_state.status == RunStatus.ACTIVE:
                in_prog = [t.id for t in current_state.tasks if t.status == TaskStatus.IN_PROGRESS]
                if len(in_prog) == 1:
                    task_ids = [in_prog[0]]
                else:
                    terminal_tasks = [
                        t for t in current_state.tasks
                        if t.status in (TaskStatus.DONE, TaskStatus.SKIPPED)
                    ]
                    if len(terminal_tasks) == len(current_state.tasks):
                        test_gates = [g.id for g in contract.gates if g.kind == GateKind.IMPLEMENTATION_TESTS]
                        gate_ids = test_gates or ["gate.tests"]

    kind = getattr(args, "kind", None)
    if kind == "test":
        kind = "test_result"
    elif kind == "command":
        kind = "command_result"

    config = load_project_config(CONFIG_FILE)
    test_cmd = config.get("test_command")
    timeout = float(config.get("check_timeout_s", 600))
    try:
        check_cwd = _run_workspace_cwd()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    try:
        res = run_check(
            CURRENT_DIR,
            PROJECT_RAPID_DIR,
            run_id,
            argv,
            task_ids=task_ids,
            gate_ids=gate_ids,
            kind=kind,
            test_command=test_cmd if isinstance(test_cmd, (list, tuple)) else None,
            timeout=timeout,
            expect=expect,
            cwd=check_cwd,
        )
    except FileNotFoundError:
        print(f"Command not found: '{argv[0]}'", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"Command timed out after {timeout}s: {' '.join(argv)}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error executing check: {exc}", file=sys.stderr)
        sys.exit(1)

    if expect == "fail":
        if getattr(args, "json", False):
            payload = {
                "run_id": res.run_id,
                "argv": list(res.argv),
                "exit_code": res.exit_code,
                "log_path": str(res.log_path.relative_to(CURRENT_DIR)).replace("\\", "/"),
                "kind": res.kind,
                "passed": res.passed,
                "failed": res.failed,
                "skipped": res.skipped,
                "evidence_id": res.evidence.id if res.evidence else None,
            }
            print(json.dumps(payload, indent=2))
            sys.exit(0 if res.evidence is not None else 1)

        if res.evidence is None:
            print(f"Check expected failure, but command succeeded (exit code {res.exit_code})", file=sys.stderr)
            sys.exit(1)

        print_success(f"Expected failure confirmed (evidence {res.evidence.id})")
        return 0

    if getattr(args, "json", False):
        payload = {
            "run_id": res.run_id,
            "argv": list(res.argv),
            "exit_code": res.exit_code,
            "log_path": str(res.log_path.relative_to(CURRENT_DIR)).replace("\\", "/"),
            "kind": res.kind,
            "passed": res.passed,
            "failed": res.failed,
            "skipped": res.skipped,
            "evidence_id": res.evidence.id if res.evidence else None,
        }
        print(json.dumps(payload, indent=2))
        sys.exit(0 if res.exit_code == 0 else res.exit_code)

    if res.exit_code != 0:
        print(f"Check failed with exit code {res.exit_code}", file=sys.stderr)
        print(f"Log: {res.log_path}", file=sys.stderr)
        if res.output:
            lines = res.output.strip().splitlines()
            tail = "\n".join(lines[-10:])
            print(f"Tail:\n{tail}", file=sys.stderr)
        sys.exit(res.exit_code)

    print_success(f"Check passed (evidence {res.evidence.id if res.evidence else 'recorded'})")
    return 0


def task_command(args):
    """Execute rapid task start|done|skip command."""
    from rapid_os.orchestration.session import load_session
    from rapid_os.orchestration.check import run_check

    action = getattr(args, "task_action", None)
    if not action:
        print("RAPID1306 Subcomando de tarea requerido (start, done, skip).", file=sys.stderr)
        sys.exit(1)

    session = load_session(PROJECT_RAPID_DIR)
    if not session or not session.active_run_id:
        print("RAPID1307 No active run session found (.rapid-os/session.json).", file=sys.stderr)
        sys.exit(1)

    run_id = session.active_run_id
    registry = RunRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)
    evidence_reg = EvidenceRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)

    try:
        run_record = registry.get(run_id)
        current_state = registry.get_state(run_id)
    except Exception as exc:
        print(f"RAPID1304 Run '{run_id}' not found: {exc}", file=sys.stderr)
        sys.exit(1)

    target_task_id = getattr(args, "task_id", None)
    reason = getattr(args, "reason", None) or ""

    if action == "start":
        if not target_task_id:
            # find first pending task
            pending = [t for t in current_state.tasks if t.status == TaskStatus.PENDING]
            if not pending:
                print("RAPID1306 No pending tasks found to start.", file=sys.stderr)
                sys.exit(1)
            target_task_id = pending[0].id

        try:
            next_state = registry.transition_task(
                run_id,
                target_task_id,
                TaskStatus.IN_PROGRESS,
                reason=reason or f"Started task {target_task_id}",
            )
        except Exception as exc:
            print(f"RAPID1306 Error transitioning task: {exc}", file=sys.stderr)
            sys.exit(1)

        if getattr(args, "json", False):
            print(json.dumps({
                "run_id": run_id,
                "task_id": target_task_id,
                "status": "in_progress",
                "revision": next_state.revision,
            }, indent=2))
            return 0
        print_success(f"Task '{target_task_id}' -> in_progress (s{next_state.revision})")
        return 0

    elif action == "done":
        if not target_task_id:
            in_prog = [t for t in current_state.tasks if t.status == TaskStatus.IN_PROGRESS]
            if len(in_prog) == 0:
                print("RAPID1306 No task is currently in_progress. Specify task ID.", file=sys.stderr)
                sys.exit(1)
            if len(in_prog) > 1:
                print("RAPID1306 Multiple tasks are in_progress. Specify task ID explicitly.", file=sys.stderr)
                sys.exit(1)
            target_task_id = in_prog[0].id

        # Run check unless --no-check
        no_check = getattr(args, "no_check", False)
        if not no_check:
            config = load_project_config(CONFIG_FILE)
            test_cmd = config.get("test_command")
            if not test_cmd or not isinstance(test_cmd, (list, tuple)):
                print("RAPID1301 No test_command configured in .rapid-os/config.json to verify task.", file=sys.stderr)
                sys.exit(1)

            timeout = float(config.get("check_timeout_s", 600))
            try:
                task_cwd = _run_workspace_cwd()
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                sys.exit(1)
            res = run_check(
                CURRENT_DIR,
                PROJECT_RAPID_DIR,
                run_id,
                test_cmd,
                task_ids=[target_task_id],
                kind=EvidenceKind.TEST_RESULT.value,
                test_command=test_cmd,
                timeout=timeout,
                cwd=task_cwd,
            )
            if res.exit_code != 0:
                print(f"Verification tests failed for task '{target_task_id}' (exit {res.exit_code}). Log: {res.log_path}", file=sys.stderr)
                sys.exit(res.exit_code)
        else:
            print(
                f"Warning: task '{target_task_id}' marked done with --no-check; "
                "assertion remains UNVERIFIED and 'rapid next' will require verification.",
                file=sys.stderr,
            )

        try:
            next_state = registry.transition_task(
                run_id,
                target_task_id,
                TaskStatus.DONE,
                reason=reason or f"Completed task {target_task_id}",
            )
        except Exception as exc:
            print(f"RAPID1306 Error transitioning task: {exc}", file=sys.stderr)
            sys.exit(1)

        if getattr(args, "json", False):
            print(json.dumps({
                "run_id": run_id,
                "task_id": target_task_id,
                "status": "done",
                "revision": next_state.revision,
            }, indent=2))
            return 0
        print_success(f"Task '{target_task_id}' -> done (s{next_state.revision})")
        return 0

    elif action == "skip":
        if not target_task_id:
            print("RAPID1306 Task ID is required to skip a task.", file=sys.stderr)
            sys.exit(1)
        if not reason:
            print("RAPID1306 Reason is required (--reason) to skip a task.", file=sys.stderr)
            sys.exit(1)

        try:
            next_state = registry.transition_task(
                run_id,
                target_task_id,
                TaskStatus.SKIPPED,
                reason=reason,
            )
        except Exception as exc:
            print(f"RAPID1306 Error transitioning task: {exc}", file=sys.stderr)
            sys.exit(1)

        if getattr(args, "json", False):
            print(json.dumps({
                "run_id": run_id,
                "task_id": target_task_id,
                "status": "skipped",
                "reason": reason,
                "revision": next_state.revision,
            }, indent=2))
            return 0
        print_success(f"Task '{target_task_id}' -> skipped (s{next_state.revision})")
        return 0

    print("RAPID1306 Unknown task action.", file=sys.stderr)
    sys.exit(1)


def _run_workspace_cwd():
    """Directory where run commands execute (the run's worktree, else the project root)."""
    from rapid_os.orchestration.workspace import resolve_workspace_cwd

    return resolve_workspace_cwd(CURRENT_DIR, PROJECT_RAPID_DIR)


def attach_command(args):
    """Execute rapid attach command."""
    from rapid_os.orchestration.lifecycle import execute_attach

    code, msg = execute_attach(
        CURRENT_DIR, PROJECT_RAPID_DIR, args.path, args.label, task_id=getattr(args, "task", None)
    )
    if code != 0:
        print(msg, file=sys.stderr)
        sys.exit(code)
    print_success(msg)
    return 0


def start_command(args):
    """Execute rapid start command."""
    from rapid_os.orchestration.lifecycle import execute_start

    mode = getattr(args, "mode", None)
    resume = getattr(args, "resume", False)
    if not mode and not resume:
        print("RAPID1306 Mode is required when starting a run (e.g. 'rapid start feature'). Use --resume to continue an existing session.", file=sys.stderr)
        sys.exit(1)

    objective = getattr(args, "objective", None)
    spec_id = getattr(args, "spec", None)
    spec_file = getattr(args, "spec_file", None)
    harness = getattr(args, "harness", None)

    code, res = execute_start(
        CURRENT_DIR,
        PROJECT_RAPID_DIR,
        mode,
        objective=objective,
        spec_id=spec_id,
        spec_file=spec_file,
        harness=harness,
        resume=resume,
        config_file=CONFIG_FILE,
        templates_dir=TEMPLATES_DIR,
        worktree=getattr(args, "worktree", False),
    )
    if code != 0:
        print(res, file=sys.stderr)
        sys.exit(code)

    if getattr(args, "json", False):
        print(json.dumps(res.to_dict(), indent=2))
        return 0

    cmd_str = f" -> {' '.join(res.command)}" if res.command else ""
    print(f"Next: {res.kind.value}{cmd_str}")
    for note in res.notes:
        print(f"Nota: {note}")
    return 0


def _load_setup_inputs():
    """Catalog, doc banks and stack questions; a broken sidecar is reported as RAPID1401."""
    from rapid_os.domain.catalog import load_catalog, load_setup_doc_banks, load_stack_questions

    try:
        return (
            load_catalog(TEMPLATES_DIR),
            load_setup_doc_banks(TEMPLATES_DIR),
            load_stack_questions(TEMPLATES_DIR),
        )
    except CatalogError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def _format_setup_action(action) -> list[str]:
    data = action.to_dict()
    kind = data["kind"]
    lines = [f"Setup next: {kind}"]
    if kind == "choose_stack":
        facts = ", ".join(f"{f['category']}={f['value']}" for f in data["facts"]) or "none detected"
        top = ", ".join(f"{o['id']} ({o['score']})" for o in data["options"][:4])
        lines += [f"Detected: {facts}", f"Options: {top}", f"Recommended: {data['recommended'] or 'none'}"]
    elif kind == "choose_topology":
        lines += [
            f"Stack: {data['stack']}",
            f"Options: {', '.join(o['id'] for o in data['options'])}",
            f"Recommended: {data['recommended'] or 'none'}",
        ]
    elif kind in ("choose_archetype", "choose_agents"):
        lines.append(f"Options: {', '.join(o['id'] for o in data['options'])}")
    elif kind == "set_test_command":
        proposed = " ".join(data["recommended"]) if data["recommended"] else "none detected"
        lines.append(f"Suggested test command: {proposed}")
    elif kind == "resolve_doc":
        if data.get("legacy_source"):
            lines.append(
                f"Legacy source: {data['legacy_source']} (import with: rapid setup doc {data['doc']} --from-legacy)"
            )
        lines += [
            f"Document: {data['doc']} -> {data['target']}",
            f"Choices: {', '.join(data['choices'])} (max {data['max_chars']} chars)",
            f"Command: {' '.join(data['command'])}",
        ]
    elif data.get("unconfirmed_docs"):
        lines.append(f"Unconfirmed drafts: {', '.join(data['unconfirmed_docs'])}")
    return lines


SETUP_SUBCOMMANDS = "next, show, set, stack, doc, finish"


def _read_setup_input(source):
    """Text from `--file -` (stdin) or from a file path. RAPID1413 when it cannot be read."""
    from rapid_os.orchestration.setup_apply import SetupApplyError

    if not source:
        raise SetupApplyError("RAPID1413", "Missing --file (use '-' to read the text from stdin).")
    try:
        if source == "-":
            stream = getattr(sys.stdin, "buffer", None)
            raw = stream.read() if stream is not None else sys.stdin.read()
        else:
            path = Path(source)
            if not path.is_file():
                raise SetupApplyError("RAPID1413", f"'{source}' is not a file.")
            raw = path.read_bytes()
        return raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    except (OSError, UnicodeDecodeError) as exc:
        raise SetupApplyError("RAPID1413", f"Cannot read the text from '{source}': {exc}") from exc


def _setup_doc_mode(args):
    """The one thing `rapid setup doc` was asked to do, or RAPID1413."""
    from rapid_os.orchestration.setup_apply import SetupApplyError

    flags = [
        name
        for name in ("skip", "confirm", "reopen", "from_legacy")
        if getattr(args, name, False)
    ]
    writes = bool(getattr(args, "source", None) or getattr(args, "file", None))
    if len(flags) + (1 if writes else 0) != 1:
        raise SetupApplyError(
            "RAPID1413",
            "Choose exactly one of: --source <provided|drafted> --file <path|->, --skip, --confirm, "
            "--reopen or --from-legacy.",
        )
    if flags:
        return flags[0]
    if not (getattr(args, "source", None) and getattr(args, "file", None)):
        raise SetupApplyError("RAPID1413", "Writing a document needs both --source and --file.")
    return "write"


def _setup_write(args, action_name, state, catalog, doc_banks):
    """Run one writing subcommand. Returns `(new_state, summary, notes, touched_docs)`."""
    from rapid_os.adapters.setup_store import write_setup
    from rapid_os.orchestration import setup_apply as apply

    if action_name == "set":
        key = getattr(args, "key", None)
        new_state, notes = apply.set_decision(
            state, key, getattr(args, "value", None), catalog, DEFAULT_AGENT_REGISTRY.ids()
        )
        write_setup(PROJECT_RAPID_DIR, new_state)
        return new_state, f"Setup: {key} = {args.value.strip()}", notes, False

    if action_name == "stack":
        if not getattr(args, "custom", False):
            raise apply.SetupApplyError(
                "RAPID1413", "Use 'rapid setup stack --custom --file -' (a catalog stack: 'rapid setup set stack <id>')."
            )
        text = _read_setup_input(getattr(args, "file", None))
        new_state = apply.write_custom_stack(PROJECT_RAPID_DIR, state, catalog, text)
        write_setup(PROJECT_RAPID_DIR, new_state)
        return new_state, "Setup: stack = custom (.rapid-os/standards/tech-stack.md)", (), False

    if action_name == "doc":
        doc_id = getattr(args, "doc_id", None)
        bank = doc_banks.get(doc_id)
        if bank is None:
            raise apply.SetupApplyError(
                "RAPID1413", f"Unknown document '{doc_id}'. Use one of: {', '.join(doc_banks)}."
            )
        mode = _setup_doc_mode(args)
        replace_existing = getattr(args, "replace", False)
        if replace_existing and mode not in ("write", "from_legacy"):
            raise apply.SetupApplyError("RAPID1413", "--replace only goes with writing a document or --from-legacy.")
        if mode == "write":
            text = _read_setup_input(args.file)
            new_state = apply.write_doc(
                CURRENT_DIR, state, bank, source=args.source, text=text, replace_existing=replace_existing
            )
            summary = f"Setup: {bank.file} written ({args.source})"
        elif mode == "from_legacy":
            new_state = apply.import_legacy_business(
                CURRENT_DIR, PROJECT_RAPID_DIR, state, bank, replace_existing=replace_existing
            )
            summary = f"Setup: {bank.file} imported from .rapid-os/standards/business.md"
        elif mode == "confirm":
            new_state = apply.confirm_doc(CURRENT_DIR, state, bank)
            summary = f"Setup: {bank.file} confirmed"
        elif mode == "skip":
            new_state = apply.skip_doc(CURRENT_DIR, state, bank)
            summary = f"Setup: {bank.id} skipped"
        else:
            new_state = apply.reopen_doc(CURRENT_DIR, state, bank)
            summary = f"Setup: {bank.id} reopened"
        write_setup(PROJECT_RAPID_DIR, new_state)
        return new_state, summary, (), True

    raise apply.SetupApplyError("RAPID1413", f"Unknown setup subcommand '{action_name}'.")


def setup_command(args):
    """Execute rapid setup. next and show are read-only; set, stack, doc and finish write."""
    from dataclasses import replace as dc_replace

    from rapid_os.adapters.project_docs import legacy_business_source
    from rapid_os.adapters.setup_store import read_setup, write_setup
    from rapid_os.domain.setup import SetupStateError
    from rapid_os.orchestration import setup_apply as apply
    from rapid_os.orchestration.setup_conductor import next_setup_action

    action_name = getattr(args, "setup_action", None)
    if not action_name:
        print(f"RAPID1413 Subcomando de setup requerido ({SETUP_SUBCOMMANDS}).", file=sys.stderr)
        sys.exit(1)

    catalog, doc_banks, stack_questions = _load_setup_inputs()
    try:
        project_model = scan_project(CURRENT_DIR).to_model()
        snapshot = read_setup(
            CURRENT_DIR,
            PROJECT_RAPID_DIR,
            CONFIG_FILE,
            TEMPLATES_DIR,
            catalog,
            doc_banks,
            project_model,
        )
    except SetupStateError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    as_json = getattr(args, "json", False)
    if action_name == "show":
        state = snapshot.state.to_dict()
        if as_json:
            print(json.dumps({"origin": snapshot.origin, "state": state}, indent=2))
            return 0
        stack = state["stack"]["id"] if state["stack"] else "-"
        docs = ", ".join(f"{k}={v['status']}" for k, v in state["docs"].items()) or "-"
        test_command = " ".join(state["test_command"]) if state["test_command"] else "-"
        print(f"Setup state ({snapshot.origin}): finished={str(state['finished']).lower()}")
        print(f"Stack: {stack}  Topology: {state['topology'] or '-'}  Archetype: {state['archetype'] or '-'}")
        print(f"Agents: {', '.join(state['agents']) or '-'}  Test command: {test_command}")
        print(f"Docs: {docs}")
        return 0

    def next_action(state):
        return next_setup_action(
            state,
            project_model,
            catalog,
            doc_banks,
            stack_questions=stack_questions,
            agent_ids=DEFAULT_AGENT_REGISTRY.ids(),
            proposed_test_command=snapshot.proposed_test_command,
            detected_agent=snapshot.detected_agent,
            legacy_business=legacy_business_source(CURRENT_DIR, PROJECT_RAPID_DIR, doc_banks["business"]),
        )

    def write_section():
        """The writing subcommands. Returns `(state, summary)`."""
        if action_name == "finish":
            state = snapshot.state
            apply.ensure_finishable(next_action(state))
            if not state.finished:
                result = apply.apply_setup(
                    CURRENT_DIR,
                    PROJECT_RAPID_DIR,
                    CONFIG_FILE,
                    TEMPLATES_DIR,
                    state,
                    catalog,
                    scan_model=project_model,
                    scanned=True,
                    only_changes=True,
                )
                for warning in result.warnings:
                    print(f"WARNING {warning}", file=sys.stderr)
                apply.update_gitignore(CURRENT_DIR)
                state = dc_replace(state, finished=True)
                write_setup(PROJECT_RAPID_DIR, state)
            return state, "Setup finished.", ()
        state, summary, notes, touched_docs = _setup_write(
            args, action_name, snapshot.state, catalog, doc_banks
        )
        for note in notes:
            print(f"NOTE {note}", file=sys.stderr)
        if touched_docs and apply.project_has_standards(PROJECT_RAPID_DIR, CONFIG_FILE):
            for warning in apply.regenerate_agent_context(CURRENT_DIR, PROJECT_RAPID_DIR, CONFIG_FILE):
                print(f"WARNING {warning}", file=sys.stderr)
        return state, summary, notes

    summary = None
    notes = ()
    state = snapshot.state
    if action_name != "next":
        # JSON mode keeps stdout for the JSON alone: the agent files report on stderr.
        quiet = contextlib.redirect_stdout(sys.stderr) if as_json else contextlib.nullcontext()
        try:
            with quiet:
                state, summary, notes = write_section()
        except apply.SetupApplyError as exc:
            print("\n".join(exc.lines), file=sys.stderr)
            sys.exit(1)
        except OSError as exc:
            print(f"RAPID1413 Cannot write the setup files: {exc}", file=sys.stderr)
            sys.exit(1)

    action = next_action(state)
    if as_json:
        payload = action.to_dict()
        if notes:
            payload["notes"] = list(notes)
        print(json.dumps(payload, indent=2))
        return 0
    if summary:
        print(summary)
    print("\n".join(_format_setup_action(action)))
    return 0


def next_command(args):
    """Execute rapid next command."""
    from rapid_os.orchestration.lifecycle import execute_next

    code, action = execute_next(
        CURRENT_DIR,
        PROJECT_RAPID_DIR,
        config_file=CONFIG_FILE,
        templates_dir=TEMPLATES_DIR,
    )
    if code != 0:
        sys.exit(code)

    if getattr(args, "json", False):
        print(json.dumps(action.to_dict(), indent=2))
        return 0

    cmd_str = f" -> {' '.join(action.command)}" if action.command else ""
    print(f"Next: {action.kind.value}{cmd_str}")
    return 0


STORY_TAG_PREFIX = "story:"
NO_BASELINE_LINE = "Sin baseline: proyecto nuevo"


def _baseline_waived(run_id):
    """True when the run was created without `gate.baseline` (a brand-new project)."""
    try:
        return RunRegistry(CURRENT_DIR, PROJECT_RAPID_DIR).get_contract(run_id).baseline_waived is not None
    except Exception:
        return False


def _story_suggestions(run_id):
    """Lines suggesting the person to tick the brief's stories that the finished run covered.

    A spec cites a story with the tag `story:<ID>` (SpecRevision has no dedicated field).
    Rapid OS never edits the brief: the person ticks the story.
    """
    from rapid_os.adapters.project_docs import load_banks

    try:
        contract = RunRegistry(CURRENT_DIR, PROJECT_RAPID_DIR).get_contract(run_id)
        revision = SpecRegistry(CURRENT_DIR, PROJECT_RAPID_DIR).get_revision(
            contract.spec_id, revision=contract.spec_revision
        )
    except Exception:  # a suggestion must never break `rapid finish`
        return []
    story_ids = [
        tag[len(STORY_TAG_PREFIX):].strip()
        for tag in revision.tags
        if tag.lower().startswith(STORY_TAG_PREFIX) and tag[len(STORY_TAG_PREFIX):].strip()
    ]
    brief = load_banks(TEMPLATES_DIR).get("brief")
    brief_file = brief.file if brief is not None else "docs/PRODUCT_BRIEF.md"
    # Spec tags are stored in lower case: show the id the way the brief writes it.
    written = {}
    if brief is not None:
        from rapid_os.adapters.project_docs import load_project_docs
        from rapid_os.domain.project_docs import open_stories

        managed = load_project_docs(CURRENT_DIR, PROJECT_RAPID_DIR, TEMPLATES_DIR).managed.get("brief")
        if managed is not None:
            written = {story["id"].lower(): story["id"] for story in open_stories(managed.body, brief)}
    return [
        f"Marca {written.get(story_id.lower(), story_id.upper())} como hecha en {brief_file}"
        for story_id in story_ids
    ]


def finish_command(args):
    """Execute rapid finish command."""
    from rapid_os.orchestration.actions import NextAction
    from rapid_os.orchestration.lifecycle import execute_finish

    code, result = execute_finish(
        CURRENT_DIR,
        PROJECT_RAPID_DIR,
        config_file=CONFIG_FILE,
        templates_dir=TEMPLATES_DIR,
    )
    if isinstance(result, str):
        print(result, file=sys.stderr)
        sys.exit(code)

    if isinstance(result, NextAction):
        if getattr(args, "json", False):
            print(json.dumps(result.to_dict(), indent=2))
            sys.exit(code)
        if result.kind.value == "done":
            outcome = result.outcome or "ended"
            print(
                f"Run '{result.run_id}' already ended ({outcome}); no new evidence recorded.",
                file=sys.stderr if code else sys.stdout,
            )
            sys.exit(code)
        cmd_str = f" -> {' '.join(result.command)}" if result.command else ""
        print(f"Cannot finish yet. Next: {result.kind.value}{cmd_str}")
        return 0

    # result is EvaluationReport
    suggestions = (
        _story_suggestions(result.run_id)
        if result.verdict.value in ("pass", "pass_with_waivers")
        else []
    )
    no_baseline = _baseline_waived(result.run_id)
    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), indent=2))
        # stdout stays the report alone; the notes go to stderr.
        if no_baseline:
            print(NO_BASELINE_LINE, file=sys.stderr)
        for line in suggestions:
            print(line, file=sys.stderr)
        sys.exit(code)

    # Reports are numbered by their file (0001.json, ...): the stored/latest one is the last.
    revision = len(EvalRegistry(CURRENT_DIR, PROJECT_RAPID_DIR).list_reports(result.run_id))
    print(
        f"Evaluation report {revision:04d} for run '{result.run_id}': "
        f"verdict {result.verdict.value.upper()}"
    )
    if no_baseline:
        print(NO_BASELINE_LINE)
    for line in suggestions:
        print(line)
    sys.exit(code)


def approve_command(args):
    """Execute rapid approve command."""
    from rapid_os.orchestration.lifecycle import execute_approve

    gate_id = getattr(args, "gate_id", None)
    reviewer = getattr(args, "reviewer", None)
    reject = getattr(args, "reject", False)
    waive = getattr(args, "waive", False)
    reason = getattr(args, "reason", None)

    code, msg = execute_approve(
        CURRENT_DIR,
        PROJECT_RAPID_DIR,
        gate_id,
        reviewer=reviewer,
        reject=reject,
        waive=waive,
        reason=reason,
    )
    if code != 0:
        print(msg, file=sys.stderr)
        sys.exit(code)

    if gate_id:
        print_success(msg)
    else:
        print(msg)
    return 0


def status_command(args):
    """Execute rapid status command."""
    from rapid_os.orchestration.session import load_session

    sess = load_session(PROJECT_RAPID_DIR)
    if not sess or not sess.active_run_id:
        if getattr(args, "json", False):
            print(json.dumps({"session": None, "run": None}, indent=2))
            return 0
        print("No active run session found (.rapid-os/session.json).")
        return 0

    run_reg = RunRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)
    eval_reg = EvalRegistry(CURRENT_DIR, PROJECT_RAPID_DIR)

    try:
        record = run_reg.get(sess.active_run_id)
        contract = run_reg.get_contract(sess.active_run_id)
        state = run_reg.get_state(sess.active_run_id)
    except Exception as exc:
        print(f"RAPID1304 Run '{sess.active_run_id}' not found: {exc}", file=sys.stderr)
        sys.exit(1)

    reports = eval_reg.list_reports(sess.active_run_id)
    last_verdict = reports[-1].verdict.value if reports else None

    if getattr(args, "json", False):
        payload = {
            "session": sess.to_dict(),
            "run": {
                "id": record.id,
                "status": state.status.value,
                "revision": state.revision,
                "mode": sess.mode,
                "harness": contract.harness,
                "classification": contract.classification.value,
                "risk": contract.risk.label,
                "tasks": [t.to_dict() for t in state.tasks],
                "gates": [g.to_dict() for g in state.gates],
                "last_verdict": last_verdict,
            },
        }
        if contract.baseline_waived is not None:
            payload["run"]["baseline_waived"] = contract.baseline_waived
        print(json.dumps(payload, indent=2))
        return 0

    done_tasks = sum(1 for t in state.tasks if t.status in (TaskStatus.DONE, TaskStatus.SKIPPED))
    print(f"Session Run:   {record.id} ({state.status.value}, s{state.revision})")
    print(f"Mode/Harness:  {sess.mode} / {contract.harness}")
    print(f"Tasks:         {done_tasks}/{len(state.tasks)} terminal")
    if contract.baseline_waived is not None:
        print(f"Baseline:      {NO_BASELINE_LINE}")
    if last_verdict:
        print(f"Last Verdict:  {last_verdict.upper()}")
    return 0


def abort_command(args):
    """Execute rapid abort command."""
    from rapid_os.orchestration.lifecycle import execute_abort

    reason = getattr(args, "reason", None)
    code, msg = execute_abort(
        CURRENT_DIR,
        PROJECT_RAPID_DIR,
        reason=reason,
    )
    if code != 0:
        print(msg, file=sys.stderr)
        sys.exit(code)

    print_success(msg)
    return 0


def show_guide():
    print(f"📘 RAPID OS v{__version__} - GOVERNANCE LOOP & CLI GUIDE")
    print("")
    print("Recommended Porcelain Workflow (Agent/Intent Layer):")
    print("  1. start        -> rapid start <mode> [--spec-file <path>|-] [--spec <id>] [writes state]")
    print("  2. next         -> rapid next [--json] (determine deterministic next action) [read-only]")
    print("  3. task start   -> rapid task start [<task-id>] [writes state]")
    print("  4. task done    -> rapid task done [<task-id>] [--no-check] (verifies with test_command) [writes state]")
    print("  5. check        -> rapid check [--task <id>] [--gate <id>] -- <argv...> [writes state]")
    print("  6. approve      -> rapid approve <gate-id> (interactive review gate confirmation) [writes state]")
    print("  7. finish       -> rapid finish [--json] (records file_change, checks machine gates, evaluates) [writes state]")
    print("  8. status/abort -> rapid status (read-only) | rapid abort [--reason <text>] [writes state]")
    print("")
    print("Recommended Plumbing Governance Workflow:")
    print("  1. scan       -> rapid scan [--write] (inspect & snapshot repository facts)")
    print("  2. spec       -> rapid spec create ... --status ready (author immutable spec revision)")
    print("  3. context    -> rapid context --spec <spec-id> (compile task-aware budgeted context)")
    print("  4. policy/run -> rapid policy show | rapid run create --spec <spec-id> (govern execution contract & state)")
    print("  5. harness    -> rapid harness resolve --run <run-id> (resolve declared harness capability compatibility)")
    print("  6. evidence   -> rapid evidence add --run <run-id> --input <file> (record SHA-256 verified evidence)")
    print("  7. eval       -> rapid eval run --run <run-id> [--write] [--require-pass] (evaluate behavioral ruleset)")
    print("  8. validate   -> rapid validate [--strict] (verify end-to-end project & registry integrity)")
    print("")
    print("Core Porcelain Commands:")
    print("  start           -> Begin or resume intent workflow session [writes state]")
    print("  next            -> Compute deterministic next action and suggested command [read-only]")
    print("  check           -> Execute command/test and record verified evidence [writes state]")
    print("  task            -> Transition task state (start, done, skip) [writes state]")
    print("  finish          -> Record repo changes, verify machine gates, and evaluate run [writes state]")
    print("  approve         -> Interactively approve human review gate [writes state]")
    print("  status          -> Display active session and run progress [read-only]")
    print("  abort           -> Cancel active run and clear session [writes state]")
    print("")
    print("Core Plumbing Commands:")
    print("  init            -> Initialize project standards and agent rule files [writes state]")
    print("  scan            -> Inspect project intelligence (read-only; --write persists .rapid-os/project.json)")
    print("  context         -> Compile task-selective context [read-only]")
    print("  spec            -> Manage Spec Registry v3 (list/show read-only; create/revise/status/export-legacy write)")
    print("  policy          -> Manage Execution Policy v3 (show read-only; init writes .rapid-os/policy.json)")
    print("  run             -> Manage Run Contracts & Lifecycle v3 (list/show read-only; create/status/task/gate write)")
    print("  harness         -> Manage Harness Capability Registry v3 (list/show/resolve read-only; init/lock write)")
    print("  evidence        -> Manage Evidence Engine v3 (list/show/verify read-only; add writes append-only records)")
    print("  eval            -> Run Behavioral Evals v3 (list/show/run read-only; run --write persists report)")
    print("  validate        -> Validate project standards, config, and v3 registries [read-only]")
    print("  doctor          -> Diagnose local installation and project health [read-only]")
    print("  inspect-context -> Preview assembled v2 project context [read-only]")
    print("")
    print("Project & Legacy Compatibility Commands:")
    print("  skill           -> List or install local/remote agent skills (list read-only; install/add write)")
    print("  mcp             -> Generate editor-specific MCP server configuration [writes state]")
    print("  vision          -> Add visual reference image to references/ [writes state]")
    print("  deploy          -> Generate DEPLOY.md from local deployment template [writes state]")
    print("  refine          -> Print AI refinement prompt for a standards file [read-only]")
    print("  scope           -> Legacy singleton SPECS.md/TASKS.md/ACCEPTANCE.md wizard (--register adds to v3 specs)")
    print("  prompt          -> Generate starter/refactor prompt from standards (legacy compatibility) [read-only]")


def _add_spec_authoring_arguments(subparser, *, is_create: bool = False):
    if is_create:
        subparser.add_argument("--id", dest="spec_id", help="Explicit spec slug ID (derived from --title if omitted).")
    subparser.add_argument("--title", help="Human-readable spec title.")
    subparser.add_argument("--mode", help="Spec mode: feature, bugfix, refactor, hardening, or research.")
    subparser.add_argument(
        "--objective",
        "--business-objective",
        dest="business_objective",
        help="Business objective for the spec.",
    )
    subparser.add_argument(
        "--problem",
        "--problem-statement",
        dest="problem_statement",
        help="Problem statement addressed by the spec.",
    )
    subparser.add_argument("--scope", action="append", help="In-scope item (repeatable).")
    subparser.add_argument(
        "--out-of-scope",
        dest="out_of_scope",
        action="append",
        help="Out-of-scope item (repeatable).",
    )
    subparser.add_argument(
        "--actor",
        "--actors-users",
        dest="actors_users",
        action="append",
        help="Actor or user role (repeatable).",
    )
    subparser.add_argument(
        "--main-flow",
        "--flow",
        dest="main_flow",
        action="append",
        help="Main flow step (repeatable).",
    )
    subparser.add_argument(
        "--edge-case",
        dest="edge_cases",
        action="append",
        help="Edge case to handle (repeatable).",
    )
    subparser.add_argument(
        "--business-rule",
        "--rule",
        dest="business_rules",
        action="append",
        help="Business rule (repeatable).",
    )
    subparser.add_argument(
        "--technical-constraint",
        "--constraint",
        dest="technical_constraints",
        action="append",
        help="Technical constraint (repeatable).",
    )
    subparser.add_argument(
        "--affected-path",
        dest="affected_paths",
        action="append",
        help="Repository-relative affected path (repeatable).",
    )
    subparser.add_argument("--data-impact", dest="data_impact", help="Data or schema impact description.")
    subparser.add_argument(
        "--acceptance",
        "--acceptance-criteria",
        dest="acceptance_criteria",
        action="append",
        help="Verifiable acceptance criterion (repeatable).",
    )
    subparser.add_argument(
        "--testing",
        "--testing-strategy",
        dest="testing_strategy",
        action="append",
        help="Testing strategy item (repeatable).",
    )
    subparser.add_argument(
        "--task",
        "--implementation-task",
        dest="implementation_tasks",
        action="append",
        help="Implementation task (repeatable; becomes T001, T002, ... in Run contracts).",
    )
    subparser.add_argument("--tag", dest="tags", action="append", help="Spec classification tag (repeatable).")
    if is_create:
        subparser.add_argument(
            "--status",
            choices=["draft", "ready"],
            help="Initial authoring status (default: draft).",
        )
        subparser.add_argument(
            "--export-legacy",
            dest="export_legacy",
            action="store_true",
            help="Also export root SPECS.md, TASKS.md, and ACCEPTANCE.md.",
        )
    subparser.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")


def _shortcut_entry_json(planned):
    return {
        "path": planned.path.as_posix(),
        "shortcut": planned.shortcut,
        "harnesses": list(planned.harnesses),
        "action": planned.action,
    }


def _skipped_json(skipped):
    return [
        {"shortcut": s.shortcut, "mode": s.mode, "code": s.code, "reason": s.reason}
        for s in skipped
    ]


def _warn_folder_overlaps(harness_ids):
    """RAPID1321: warn (stderr) when the selection leaves a /rapid-* in two folders a tool reads.

    Informational only: it never changes the exit code or what is written.
    """
    from rapid_os.domain.shortcuts import detect_folder_overlaps

    overlaps = detect_folder_overlaps(harness_ids)
    for overlap in overlaps:
        print(f"WARNING {overlap.message}", file=sys.stderr)
    return overlaps


def _install_shortcuts(harness_ids, *, dry_run, scope="project", only=None):
    """Plan and (unless dry_run) write shortcuts. Returns (plan, written paths).

    With `scope="global"` the files go under the user's home directory.
    """
    from rapid_os.adapters.shortcut_installer import apply_plan, build_plan

    root = Path.home() if scope == "global" else CURRENT_DIR
    plan = build_plan(root, harness_ids, TEMPLATES_DIR, scope=scope, only=only)
    written = () if dry_run else apply_plan(root, plan)
    return plan, written


def _plan_claude_hooks(action, harness_ids):
    """Plan the .claude/settings.json hooks change; RAPID1337/RAPID1338 when it cannot apply."""
    from rapid_os.adapters import claude_hooks
    from rapid_os.adapters.shortcut_installer import ShortcutError

    if "claude" not in harness_ids:
        raise ShortcutError(
            "RAPID1337",
            "--hooks only applies to Claude Code: select the claude harness "
            "(--harness claude, or add 'claude' to 'tools' in .rapid-os/config.json).",
        )
    if action == "install":
        return claude_hooks.plan_install(CURRENT_DIR)
    return claude_hooks.plan_remove(CURRENT_DIR)


def hook_command(args):
    """Execute rapid hook stop|pre-tool: read the Claude Code hook JSON on stdin.

    Never fails the agent: internal errors, invalid stdin or a missing project produce no output
    and exit 0 (see rapid_os.orchestration.hook_runtime).
    """
    from rapid_os.orchestration.hook_runtime import run_hook

    event = getattr(args, "hook_event", None)
    if not event:
        print("Usage: rapid hook {stop,pre-tool}  (reads the Claude Code hook JSON from stdin)", file=sys.stderr)
        return 0
    try:
        raw_stdin = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    except Exception:
        raw_stdin = ""
    code, output = run_hook(event, raw_stdin, os.environ, templates_dir=TEMPLATES_DIR)
    if output:
        sys.stdout.write(output + "\n")
        sys.stdout.flush()
    sys.exit(code)


def shortcuts_command(args):
    """Execute rapid shortcuts install|list|remove."""
    from rapid_os.adapters.shortcut_installer import (
        ShortcutError,
        apply_removal,
        list_entries,
        plan_removal,
        resolve_harness_ids,
    )

    action = getattr(args, "shortcuts_action", None)
    if not action:
        print("RAPID1318 Subcomando de shortcuts requerido (install, list, remove).", file=sys.stderr)
        sys.exit(1)

    as_json = getattr(args, "json", False)
    dry_run = getattr(args, "dry_run", False)
    scope = "global" if getattr(args, "global_scope", False) else "project"
    only = getattr(args, "only", None)
    root = Path.home() if scope == "global" else CURRENT_DIR

    try:
        if scope == "global" and getattr(args, "hooks", False):
            raise ShortcutError("RAPID1413", "--hooks writes the project's .claude/settings.json and cannot be combined with --global.")
        if scope == "global" and not getattr(args, "harness", None):
            raise ShortcutError("RAPID1413", "--global needs --harness <id>: there is no project config to choose the harnesses from.")
        # A missing config would otherwise yield the generic default tools; only an explicit
        # --harness or a project config may decide where shortcut files are written.
        config_tools = (
            _load_config_with_warning(CONFIG_FILE).get("tools", [])
            if scope == "project" and Path(CONFIG_FILE).exists()
            else []
        )
        harness_ids = resolve_harness_ids(getattr(args, "harness", None), config_tools)

        if action == "install":
            from rapid_os.adapters import claude_hooks

            hooks_plan = _plan_claude_hooks("install", harness_ids) if getattr(args, "hooks", False) else None
            plan, written = _install_shortcuts(harness_ids, dry_run=dry_run, scope=scope, only=only)
            overlaps = _warn_folder_overlaps(harness_ids) if scope == "project" else []
            if hooks_plan is not None and not dry_run:
                claude_hooks.apply_plan(CURRENT_DIR, hooks_plan)
            if as_json:
                payload = {
                    "schema_version": 1,
                    "command": "install",
                    "dry_run": dry_run,
                    **({"scope": "global"} if scope == "global" else {}),
                    "harnesses": list(plan.harnesses),
                    "files": [_shortcut_entry_json(f) for f in plan.files],
                    "skipped": _skipped_json(plan.skipped),
                    "warnings": [*plan.warning_objects, *(o.to_dict() for o in overlaps)],
                }
                if hooks_plan is not None:
                    payload["hooks"] = hooks_plan.to_dict()
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return 0
            prefix = "[dry-run] " if dry_run else ""
            for planned in plan.files:
                owners = ",".join(planned.harnesses)
                print(f"{prefix}{planned.action:<9} {planned.path.as_posix()} [{owners}]")
            if hooks_plan is not None:
                print(f"{prefix}{hooks_plan.action:<9} {hooks_plan.path.as_posix()} [hooks: Stop, PreToolUse]")
            changed = sum(1 for f in plan.files if f.action != "unchanged")
            print(f"{prefix}{changed} archivo(s) a escribir, {len(plan.files) - changed} sin cambios.")
            for warning in plan.warnings:
                print(f"WARNING {warning}", file=sys.stderr)
            return 0

        if action == "list":
            entries, skipped = list_entries(root, harness_ids, TEMPLATES_DIR, scope=scope, only=only)
            overlaps = _warn_folder_overlaps(harness_ids) if scope == "project" else []
            if as_json:
                payload = {
                    "schema_version": 1,
                    "command": "list",
                    "harnesses": list(harness_ids),
                    "shortcuts": [
                        {"harness": e.harness, "shortcut": e.shortcut,
                         "path": e.path.as_posix(), "state": e.state}
                        for e in entries
                    ],
                    "skipped": _skipped_json(skipped),
                }
                if overlaps:
                    payload["warnings"] = [o.to_dict() for o in overlaps]
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return 0
            for e in entries:
                print(f"{e.state:<10} {e.harness:<12} {e.path.as_posix()}")
            for s in skipped:
                print(f"omitido    {s.shortcut}: {s.code} {s.reason}")
            return 0

        # remove
        from rapid_os.adapters import claude_hooks

        hooks_plan = _plan_claude_hooks("remove", harness_ids) if getattr(args, "hooks", False) else None
        entries = plan_removal(root, harness_ids, TEMPLATES_DIR, scope=scope, only=only)
        removed = () if dry_run else apply_removal(root, entries)
        if hooks_plan is not None and not dry_run:
            claude_hooks.apply_plan(CURRENT_DIR, hooks_plan)
        warnings = [
            f"RAPID1317 {e.path.as_posix()} has no generated marker; left untouched."
            for e in entries if e.action == "skip_unmarked"
        ]
        if as_json:
            payload = {
                "schema_version": 1,
                "command": "remove",
                "dry_run": dry_run,
                "harnesses": list(harness_ids),
                "files": [
                    {"path": e.path.as_posix(), "shortcut": e.shortcut,
                     "harnesses": list(e.harnesses), "action": e.action}
                    for e in entries
                ],
                "warnings": warnings,
            }
            if hooks_plan is not None:
                payload["hooks"] = hooks_plan.to_dict()
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        prefix = "[dry-run] " if dry_run else ""
        for e in entries:
            if e.action != "absent":
                print(f"{prefix}{e.action:<13} {e.path.as_posix()}")
        if hooks_plan is not None and hooks_plan.action != "absent":
            print(f"{prefix}{hooks_plan.action:<13} {hooks_plan.path.as_posix()} [hooks: Stop, PreToolUse]")
        print(f"{prefix}{sum(1 for e in entries if e.action == 'remove')} archivo(s) a eliminar.")
        for warning in warnings:
            print(f"WARNING {warning}", file=sys.stderr)
        return 0
    except ShortcutError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def create_parser():
    parser = argparse.ArgumentParser(
        prog="rapid",
        description=(
            f"Rapid OS {__version__} — Deterministic project intelligence, task-aware context compilation, "
            "spec governance, execution contracts, harness capabilities, and behavioral evaluations."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Rapid OS {__version__}",
        help="Print the Rapid OS version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser(
        "init",
        help="Initialize .rapid-os/ standards and agent context files (writes state).",
        description="Initialize .rapid-os/ standards, config.json, and agent instruction files in the current directory (writes state with .bak backups).",
    )
    init.add_argument("--stack", help="Explicit stack template name (overrides scanner suggestion).")
    init.add_argument(
        "--archetype",
        type=str.lower,
        choices=list(SUPPORTED_ARCHETYPES),
        help="Engineering archetype: mvp or corporate.",
    )
    init.add_argument("--topology", help="Explicit topology template name (e.g. fullstack-separated, microservices).")
    init.add_argument("--agents", help="Comma-separated agent names or numeric options (e.g. cursor,claude or 1,2).")
    init.add_argument(
        "-y",
        "--yes",
        dest="yes",
        action="store_true",
        help="Accept default values without interactive prompting and skip business rules import.",
    )
    init.add_argument("--test-command", dest="test_command", help="Explicit test command string to store in config (e.g. 'python -m pytest').")
    init.add_argument("--no-scan", action="store_true", help="Skip local project scanner during initialization.")
    init.add_argument(
        "--hooks",
        action="store_true",
        help="Also install the Rapid OS hooks in .claude/settings.json (requires the claude agent; independent of --shortcuts).",
    )
    init.add_argument(
        "--shortcuts",
        action="store_true",
        help="Install the /rapid-<mode> shortcuts for the selected agents without asking (writes state).",
    )
    init.add_argument(
        "--business-file",
        dest="business_file",
        metavar="PATH",
        help="Import this file as docs/BUSINESS_RULES.md, provided by a person and stored as is (writes state).",
    )
    init.add_argument(
        "--skip-docs",
        dest="skip_docs",
        action="store_true",
        help="Skip the project documents (brief, business rules, data model, architecture) instead of leaving them pending.",
    )

    scan = subparsers.add_parser(
        "scan",
        help="Scan repository and build deterministic ProjectModel (read-only unless --write).",
        description="Scan the current repository and emit normalized ProjectFact records. Read-only unless --write is passed to persist .rapid-os/project.json.",
    )
    scan.add_argument("--json", action="store_true", help="Emit pure ProjectModel JSON on stdout.")
    scan.add_argument("--write", action="store_true", help="Persist .rapid-os/project.json snapshot (with backup).")
    scan.add_argument("--verbose", action="store_true", help="Include per-fact evidence provenance in text output.")

    context = subparsers.add_parser(
        "context",
        help="Compile task-specific, budgeted context with provenance (read-only).",
        description="Compile task-relevant context from ProjectModel, standards, and ready specs. Always read-only (never writes files).",
    )
    context.add_argument("action", choices=["compile"], nargs="?", help="Optional explicit 'compile' action.")
    context.add_argument("--mode", default="general", help="Task mode: feature, bugfix, refactor, hardening, research, or general.")
    context.add_argument("--harness", help="Target harness identifier (e.g. codex, claude, cursor, vscode, antigravity).")
    context.add_argument("--objective", help="Task objective for relevance ranking.")
    context.add_argument("--max-chars", type=int, help="Maximum character budget for compiled Markdown.")
    context.add_argument("--constraint", action="append", help="Explicit task constraint (repeatable).")
    context.add_argument("--tag", action="append", help="Task tag for source selection (repeatable).")
    context.add_argument("--path", action="append", help="Affected relative path (repeatable).")
    context.add_argument("--spec", help="Ready spec ID from .rapid-os/specs/<id>/ to include.")
    context.add_argument("--spec-revision", type=int, help="Pinned spec revision number.")
    context.add_argument("--json", action="store_true", help="Emit pure CompiledContext JSON on stdout.")
    context.add_argument("--manifest", action="store_true", help="Print human-readable ContextManifest summary.")

    spec = subparsers.add_parser(
        "spec",
        help="Manage Spec Registry v3 in .rapid-os/specs/ (list/show read-only; create/revise/status/export-legacy write).",
        description=(
            "Manage immutable multi-spec revisions under .rapid-os/specs/<spec-id>/. "
            "Read-only actions: list, show. State-writing actions: create, revise, status, export-legacy."
        ),
    )
    spec_subparsers = spec.add_subparsers(dest="spec_action")

    spec_create = spec_subparsers.add_parser(
        "create",
        help="Create a new spec and revision r1 (writes .rapid-os/specs/<id>/).",
        description="Create a new spec record and immutable revision 0001 under .rapid-os/specs/<spec-id>/ (writes state).",
    )
    _add_spec_authoring_arguments(spec_create, is_create=True)

    spec_list = spec_subparsers.add_parser(
        "list",
        help="List registered specs in deterministic ID order (read-only).",
        description="List registered specs from .rapid-os/specs/ in deterministic ID order (read-only).",
    )
    spec_list.add_argument(
        "--status",
        choices=["draft", "ready", "archived"],
        help="Filter specs by authoring status.",
    )
    spec_list.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    spec_show = spec_subparsers.add_parser(
        "show",
        help="Show a spec and its current or pinned revision (read-only).",
        description="Display a spec record and revision details without modifying any files (read-only).",
    )
    spec_show.add_argument("spec_id", help="Spec identifier.")
    spec_show.add_argument("--revision", type=int, help="Specific revision number (defaults to current_revision).")
    spec_show.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    spec_revise = spec_subparsers.add_parser(
        "revise",
        help="Create next immutable spec revision and reset status to draft (writes state).",
        description="Create immutable revision current_revision + 1 and reset spec status to draft (writes state).",
    )
    spec_revise.add_argument("spec_id", help="Spec identifier to revise.")
    _add_spec_authoring_arguments(spec_revise, is_create=False)

    spec_status = spec_subparsers.add_parser(
        "status",
        help="Transition spec authoring status: draft, ready, or archived (writes state).",
        description="Transition a spec's authoring lifecycle status in .rapid-os/specs/<id>/spec.json (writes state).",
    )
    spec_status.add_argument("spec_id", help="Spec identifier.")
    spec_status.add_argument("status", help="Target status: draft, ready, or archived.")
    spec_status.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    spec_export = spec_subparsers.add_parser(
        "export-legacy",
        help="Export a spec revision to root SPECS.md, TASKS.md, and ACCEPTANCE.md (writes state).",
        description="Export a spec revision to legacy root SPECS.md, TASKS.md, and ACCEPTANCE.md files with .bak backups (writes state).",
    )
    spec_export.add_argument("spec_id", help="Spec identifier to export.")
    spec_export.add_argument("--revision", type=int, help="Specific revision number to export.")

    policy = subparsers.add_parser(
        "policy",
        help="Inspect or initialize Execution Policy in .rapid-os/policy.json (show read-only; init writes).",
        description=(
            "Inspect the active execution policy or initialize .rapid-os/policy.json. "
            "Read-only actions: show. State-writing actions: init."
        ),
    )
    policy_subparsers = policy.add_subparsers(dest="policy_action")

    policy_show = policy_subparsers.add_parser(
        "show",
        help="Show effective execution policy and digest (read-only).",
        description="Display the active execution policy (default or .rapid-os/policy.json) without modifying files (read-only).",
    )
    policy_show.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    policy_init = policy_subparsers.add_parser(
        "init",
        help="Write default .rapid-os/policy.json without overwriting existing files (writes state).",
        description="Initialize .rapid-os/policy.json with default execution policy rules (writes state; never overwrites).",
    )
    policy_init.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    run = subparsers.add_parser(
        "run",
        help="Manage Execution Contracts & Run State Ledger in .rapid-os/runs/ (list/show read-only; create/status/task/gate write).",
        description=(
            "Create immutable ExecutionContract snapshots and append-only RunState revisions under .rapid-os/runs/<run-id>/. "
            "Read-only actions: list, show. State-writing actions: create, status, task, gate."
        ),
    )
    run_subparsers = run.add_subparsers(dest="run_action")

    run_create = run_subparsers.add_parser(
        "create",
        help="Create a governed Run bound to a ready Spec revision (writes .rapid-os/runs/<run-id>/).",
        description="Evaluate policy, compile context, and persist an immutable ExecutionContract and initial RunState s1 (writes state).",
    )
    run_create.add_argument("--spec", help="Ready spec identifier to bind.")
    run_create.add_argument("--spec-revision", dest="spec_revision", type=int, help="Pinned spec revision number.")
    run_create.add_argument("--id", dest="run_id", help="Explicit run identifier (defaults to <spec>-r<rev>-run-<NNN>).")
    run_create.add_argument(
        "--harness",
        default=None,
        help="Target harness identifier bound to the contract (default: auto-detected, fallback cursor).",
    )
    run_create.add_argument("--classification", help="Optional classification override (cannot downgrade policy).")
    run_create.add_argument("--risk", help="Optional risk level override (cannot downgrade policy).")
    run_create.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    run_list = run_subparsers.add_parser(
        "list",
        help="List registered runs in deterministic ID order (read-only).",
        description="List runs from .rapid-os/runs/ in deterministic ID order without modifying files (read-only).",
    )
    run_list.add_argument("--status", help="Filter runs by current RunStatus.")
    run_list.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    run_show = run_subparsers.add_parser(
        "show",
        help="Show a run's contract, tasks, gates, and state (read-only).",
        description="Display a run record, immutable contract, and current or historical state revision (read-only).",
    )
    run_show.add_argument("run_id", help="Run identifier.")
    run_show.add_argument("--state-revision", dest="state_revision", type=int, help="Historical state revision to inspect.")
    run_show.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    run_status = run_subparsers.add_parser(
        "status",
        help="Append a new state revision transitioning run lifecycle status (writes state).",
        description="Append a new RunState snapshot transitioning run status (active, blocked, finished, failed, cancelled) (writes state).",
    )
    run_status.add_argument("run_id", help="Run identifier.")
    run_status.add_argument("status", help="Target run status: active, blocked, finished, failed, or cancelled.")
    run_status.add_argument("--reason", help="Optional reason for the transition.")
    run_status.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    run_task = run_subparsers.add_parser(
        "task",
        help="Append a new state revision transitioning a task status (writes state).",
        description="Append a new RunState snapshot transitioning a task (T001, ...) while the run is active (writes state).",
    )
    run_task.add_argument("run_id", help="Run identifier.")
    run_task.add_argument("task_id", help="Task identifier (e.g. T001).")
    run_task.add_argument("status", help="Target task status: in_progress, done, blocked, or skipped.")
    run_task.add_argument("--reason", help="Optional reason for the task transition.")
    run_task.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    run_gate = run_subparsers.add_parser(
        "gate",
        help="Append a new state revision acknowledging or waiving a gate (writes state).",
        description="Append a new RunState snapshot acknowledging or waiving a required gate (writes state).",
    )
    run_gate.add_argument("run_id", help="Run identifier.")
    run_gate.add_argument("gate_id", help="Gate identifier (e.g. gate.baseline, gate.tests).")
    run_gate.add_argument("disposition", help="Target gate disposition: acknowledged or waived.")
    run_gate.add_argument("--reason", help="Reason (required when waiving a gate).")
    run_gate.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    harness = subparsers.add_parser(
        "harness",
        help="Manage Harness Capability Registry & Lock (list/show/resolve read-only; init/lock write).",
        description=(
            "Inspect harness capability profiles, initialize project profile overrides in .rapid-os/harnesses/, "
            "write .rapid-os/capabilities.lock, and resolve contract compatibility. "
            "Read-only actions: list, show, resolve. State-writing actions: init, lock."
        ),
    )
    harness_subparsers = harness.add_subparsers(dest="harness_action")

    harness_list = harness_subparsers.add_parser(
        "list",
        help="List active harness profiles in deterministic ID order (read-only).",
        description="List built-in and project-overridden harness capability profiles (read-only).",
    )
    harness_list.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    harness_show = harness_subparsers.add_parser(
        "show",
        help="Show an active harness profile and capability declarations (read-only).",
        description="Display a resolved HarnessProfile, its source provenance, and capability statuses (read-only).",
    )
    harness_show.add_argument("harness_id", help="Harness identifier (e.g. codex, claude, cursor).")
    harness_show.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    harness_init = harness_subparsers.add_parser(
        "init",
        help="Materialize a built-in harness profile to .rapid-os/harnesses/<id>.json (writes state).",
        description="Write a customizable project harness profile to .rapid-os/harnesses/<id>.json without overwriting existing files (writes state).",
    )
    harness_init.add_argument("harness_id", help="Built-in harness identifier to copy.")
    harness_init.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    harness_lock = harness_subparsers.add_parser(
        "lock",
        help="Write deterministic .rapid-os/capabilities.lock snapshot (writes state).",
        description="Persist a deterministic .rapid-os/capabilities.lock snapshot of all active harness profiles (writes state).",
    )
    harness_lock.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    harness_resolve = harness_subparsers.add_parser(
        "resolve",
        help="Resolve an ExecutionContract's required capabilities against its harness profile (read-only).",
        description="Evaluate a run's ExecutionContract against the active or locked HarnessProfile without mutating the run (read-only).",
    )
    harness_resolve.add_argument("--run", dest="run", help="Run identifier whose ExecutionContract is evaluated.")
    harness_resolve.add_argument("--locked", action="store_true", help="Resolve against .rapid-os/capabilities.lock.")
    harness_resolve.add_argument("--require", action="append", help="Extra additive canonical capability ID (repeatable).")
    harness_resolve.add_argument(
        "--require-compatible",
        dest="require_compatible",
        action="store_true",
        help="Exit non-zero (RAPID1110) unless compatibility status is 'compatible'.",
    )
    harness_resolve.add_argument("--json", action="store_true", help="Emit pure CapabilityResolution JSON on stdout.")

    evidence = subparsers.add_parser(
        "evidence",
        help="Manage immutable RunEvidence & SHA-256 artifacts (list/show/verify read-only; add writes).",
        description=(
            "Ingest, inspect, and verify append-only RunEvidence records and copied artifacts under .rapid-os/evidence/<run-id>/. "
            "Read-only actions: list, show, verify. State-writing actions: add."
        ),
    )
    evidence_subparsers = evidence.add_subparsers(dest="evidence_action")

    evidence_list = evidence_subparsers.add_parser(
        "list",
        help="List verified evidence records for a run (read-only).",
        description="List recorded RunEvidence items (E001..E00N) and evidence_set_digest for a run (read-only).",
    )
    evidence_list.add_argument("--run", dest="run", required=True, help="Target run identifier.")
    evidence_list.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    evidence_show = evidence_subparsers.add_parser(
        "show",
        help="Show a single verified evidence record and its artifacts (read-only).",
        description="Display a RunEvidence record, bindings, payload, and copied artifacts (read-only).",
    )
    evidence_show.add_argument("--run", dest="run", required=True, help="Target run identifier.")
    evidence_show.add_argument("evidence_id", help="Evidence identifier (e.g. E001).")
    evidence_show.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    evidence_add = evidence_subparsers.add_parser(
        "add",
        help="Ingest a new append-only RunEvidence record and copy artifacts (writes state).",
        description="Validate and append a new RunEvidence record and SHA-256 verified artifacts under .rapid-os/evidence/<run-id>/ (writes state).",
    )
    evidence_add.add_argument("--run", dest="run", required=True, help="Target run identifier.")
    evidence_add.add_argument("--input", dest="input", required=True, help="Path to authoring evidence JSON file.")
    evidence_add.add_argument("--json", action="store_true", help="Emit pure RunEvidence JSON on stdout.")

    evidence_verify = evidence_subparsers.add_parser(
        "verify",
        help="Verify all evidence records, bindings, sequence continuity, and artifact digests (read-only).",
        description="Verify integrity of all RunEvidence records and copied artifacts for a run (read-only).",
    )
    evidence_verify.add_argument("--run", dest="run", required=True, help="Target run identifier.")
    evidence_verify.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    eval_parser = subparsers.add_parser(
        "eval",
        help="Run deterministic Behavioral Evals (list/show and default run are read-only; run --write persists).",
        description=(
            "Evaluate a run's ExecutionContract, RunState, and verified RunEvidence set against the BehavioralRuleset. "
            "Read-only actions: list, show, and 'run' without --write. State-writing action: 'run --write'."
        ),
    )
    eval_subparsers = eval_parser.add_subparsers(dest="eval_action")

    eval_run = eval_subparsers.add_parser(
        "run",
        help="Evaluate a run deterministically (read-only unless --write is passed).",
        description="Evaluate a run's lifecycle, tasks, gates, and observable capabilities. Read-only unless --write is passed.",
    )
    eval_run.add_argument("--run", dest="run", required=True, help="Target run identifier.")
    eval_run.add_argument("--ruleset", type=int, choices=[1, 2], default=2, help="Behavioral ruleset version to evaluate (1 or 2, defaults to 2).")
    eval_run.add_argument("--require", action="append", help="Extra additive canonical capability ID to evaluate (repeatable).")
    eval_run.add_argument("--write", action="store_true", help="Persist append-only EvaluationReport under .rapid-os/evals/<run-id>/reports/.")
    eval_run.add_argument(
        "--require-pass",
        dest="require_pass",
        action="store_true",
        help="Exit non-zero (RAPID1225 on unverified, RAPID1226 on fail) unless verdict is pass or pass_with_waivers.",
    )
    eval_run.add_argument("--json", action="store_true", help="Emit pure EvaluationReport JSON on stdout.")

    eval_list = eval_subparsers.add_parser(
        "list",
        help="List persisted EvaluationReport snapshots for a run (read-only).",
        description="List persisted EvaluationReport files (0001.json, ...) for a run with staleness status (read-only).",
    )
    eval_list.add_argument("--run", dest="run", required=True, help="Target run identifier.")
    eval_list.add_argument("--json", action="store_true", help="Emit pure JSON output on stdout.")

    eval_show = eval_subparsers.add_parser(
        "show",
        help="Show the latest or pinned persisted EvaluationReport (read-only).",
        description="Load, replay-verify, and display a persisted EvaluationReport for a run (read-only).",
    )
    eval_show.add_argument("--run", dest="run", required=True, help="Target run identifier.")
    eval_show.add_argument("--revision", type=int, help="Specific report revision number (defaults to latest).")
    eval_show.add_argument("--json", action="store_true", help="Emit pure EvaluationReport JSON on stdout.")

    skill = subparsers.add_parser(
        "skill",
        help="List or install local/remote agent skills (list read-only; install/add write).",
        description="Manage local skill templates or remote community skills via npx.",
    )
    skill.add_argument("action", choices=["list", "install", "add"], nargs="?", help="Action: list, install, or add.")
    skill.add_argument("name", nargs="?", help="Template name or remote package reference.")

    scope = subparsers.add_parser(
        "scope",
        help="Legacy singleton SPECS.md/TASKS.md/ACCEPTANCE.md wizard (--register adds to v3 Spec Registry).",
        description="Interactive legacy scope wizard that writes SPECS.md, TASKS.md, and ACCEPTANCE.md (and optionally registers in .rapid-os/specs/).",
    )
    scope.add_argument("--register", action="store_true", help="Also register the authored spec in .rapid-os/specs/.")
    scope.add_argument("--spec-id", dest="spec_id", help="Explicit spec ID when --register is used.")
    scope.add_argument("--status", choices=["draft", "ready"], help="Initial status when --register is used.")

    deploy = subparsers.add_parser(
        "deploy",
        help="Generate DEPLOY.md from local deployment template (writes state).",
        description="Generate DEPLOY.md in the project root from templates/deploy/<target>.md (writes state with backup).",
    )
    deploy.add_argument("target", nargs="?", help="Deployment target identifier (e.g. aws).")

    vision = subparsers.add_parser(
        "vision",
        help="Copy a visual reference image to references/ and update VISION_CONTEXT.md (writes state).",
        description="Copy an image into references/, append its description to references/VISION_CONTEXT.md, and regenerate agent contexts.",
    )
    vision.add_argument("path", nargs="?", help="Path to reference image file.")

    mcp = subparsers.add_parser(
        "mcp",
        help="Generate editor-specific MCP configuration file (writes state).",
        description="Render and write editor-specific MCP server configuration with backup protection.",
    )
    mcp.add_argument("--ide", choices=["codex", "claude", "cursor", "vscode", "antigravity"], help="Target IDE/harness.")
    mcp.add_argument("--scope", choices=["project", "global"], help="Target configuration scope.")

    refine = subparsers.add_parser(
        "refine",
        help="Print an AI refinement prompt for a standards file (read-only).",
        description="Read a markdown/text file and print a structured refinement prompt to stdout (read-only).",
    )
    refine.add_argument("file", help="Path to the file to refine.")

    subparsers.add_parser(
        "prompt",
        help="Generate a starter/refactor prompt from project standards (legacy read-only workflow).",
        description="Generate a copyable starter or refactor system prompt from .rapid-os/standards/ (read-only).",
    )

    validate = subparsers.add_parser(
        "validate",
        help="Validate project standards, config, and all v3 registries (read-only).",
        description="Validate templates, standards, config.json, and all Rapid OS v3 registries without modifying files (read-only).",
    )
    validate.add_argument("--json", action="store_true", help="Emit pure ValidationReport JSON on stdout.")
    validate.add_argument("--strict", action="store_true", help="Treat warnings as non-zero exit errors.")

    doctor = subparsers.add_parser(
        "doctor",
        help="Diagnose local Rapid OS installation, paths, and current project health (read-only).",
        description="Inspect resolved paths, template availability, optional Node/npx, and current project state (read-only).",
    )
    doctor.add_argument("--json", action="store_true", help="Emit pure ValidationReport JSON on stdout.")
    doctor.add_argument("--strict", action="store_true", help="Treat warnings as non-zero exit errors.")

    inspect_context = subparsers.add_parser(
        "inspect-context",
        help="Preview assembled v2 project context and included sections (read-only).",
        description="Assemble and preview v2 project standards context without writing agent files (read-only).",
    )
    inspect_context.add_argument("--json", action="store_true", help="Emit pure ContextInspection JSON on stdout.")
    inspect_context.add_argument("--summary", action="store_true", help="Omit full context preview text.")

    subparsers.add_parser(
        "guide",
        help="Show Rapid OS v3 governance workflow and command overview (read-only).",
        description="Print the recommended Rapid OS v3 governance loop and command reference (read-only).",
    )

    # rapid check
    check_p = subparsers.add_parser(
        "check",
        help="Execute verification check and record append-only RunEvidence on success.",
        description="Run test or command argv, save log in scratch/checks/<run-id>/, and record evidence.",
    )
    check_p.add_argument("--task", dest="task", help="Target task identifier (e.g. T001).")
    check_p.add_argument("--gate", dest="gate", help="Target gate identifier (e.g. gate.baseline).")
    check_p.add_argument("--kind", dest="kind", choices=["test", "command", "test_result", "command_result"], help="Evidence kind to produce.")
    check_p.add_argument("--expect", dest="expect", choices=["pass", "fail"], default="pass", help="Expected outcome of check ('pass' or 'fail').")
    check_p.add_argument("--json", action="store_true", help="Emit JSON result on stdout.")
    check_p.add_argument("argv", nargs=argparse.REMAINDER, help="Command line arguments to execute after --.")

    # rapid task
    task_p = subparsers.add_parser(
        "task",
        help="Manage active run tasks (start, done, skip).",
        description="Transition task status in the active run session.",
    )
    task_sub = task_p.add_subparsers(dest="task_action")

    task_start = task_sub.add_parser("start", help="Mark task as in_progress.")
    task_start.add_argument("task_id", nargs="?", help="Task identifier (defaults to first pending task).")
    task_start.add_argument("--reason", help="Optional transition reason.")
    task_start.add_argument("--json", action="store_true", help="Emit JSON output.")

    task_done = task_sub.add_parser("done", help="Verify with test_command and mark task done.")
    task_done.add_argument("task_id", nargs="?", help="Task identifier (defaults to current in_progress task).")
    task_done.add_argument("--reason", help="Optional transition reason.")
    task_done.add_argument("--no-check", action="store_true", help="Mark task done without running verification tests.")
    task_done.add_argument("--json", action="store_true", help="Emit JSON output.")

    task_skip = task_sub.add_parser("skip", help="Skip task with mandatory reason.")
    task_skip.add_argument("task_id", help="Task identifier to skip.")
    task_skip.add_argument("--reason", required=True, help="Mandatory reason for skipping the task.")
    task_skip.add_argument("--json", action="store_true", help="Emit JSON output.")

    # rapid start
    start_p = subparsers.add_parser(
        "start",
        help="Start or resume a governed intent workflow session.",
        description="Initialize session, compile or bind spec, evaluate contract, and execute initial baseline check.",
    )
    start_p.add_argument("mode", nargs="?", choices=["feature", "bugfix", "refactor", "hardening", "research"], help="Engineering workflow mode (required unless --resume).")
    start_p.add_argument("objective", nargs="?", help="Optional business objective or feature goal.")
    start_p.add_argument("--spec-file", dest="spec_file", help="Path to JSON spec authoring file (or '-' for stdin).")
    start_p.add_argument("--spec", dest="spec", help="Existing ready spec identifier.")
    start_p.add_argument("--harness", dest="harness", help="Explicit harness override.")
    start_p.add_argument("--resume", action="store_true", help="Resume baseline check and activation on active run.")
    start_p.add_argument(
        "--worktree",
        action="store_true",
        help="When the contract requires an isolated workspace, create a git worktree at ../<repo>-<run-id> on branch rapid/<run-id> (writes state).",
    )
    start_p.add_argument("--json", action="store_true", help="Emit NextAction JSON output.")

    # rapid next
    next_p = subparsers.add_parser(
        "next",
        help="Determine the next deterministic workflow action.",
        description="Compute and print the next action according to active run state, evidence, and playbook rules.",
    )
    next_p.add_argument("--json", action="store_true", help="Emit NextAction JSON output.")

    # rapid finish
    finish_p = subparsers.add_parser(
        "finish",
        help="Complete run, record file changes, acknowledge machine gates, and evaluate.",
        description="Collect git diff file changes, acknowledge satisfied machine gates, evaluate ruleset, and finish run.",
    )
    finish_p.add_argument("--json", action="store_true", help="Emit EvaluationReport or NextAction JSON output.")

    # rapid approve
    approve_p = subparsers.add_parser(
        "approve",
        help="Interactively review and approve or reject a human gate.",
        description="Require interactive TTY confirmation to record user review evidence and acknowledge or reject a gate.",
    )
    approve_p.add_argument("gate_id", nargs="?", help="Target human review gate identifier (e.g. gate.peer-review, gate.final-verification). Omit to list pending human gates.")
    approve_p.add_argument("--reviewer", dest="reviewer", help="Human reviewer name or handle (default: git config user.name, else asked on the terminal).")
    approve_p.add_argument("--reject", action="store_true", help="Reject the gate (review outcome changes_requested); the gate stays FAIL for the rest of the run.")
    approve_p.add_argument("--waive", action="store_true", help="Waive a waivable gate instead of approving it (requires --reason).")
    approve_p.add_argument("--reason", dest="reason", help="Review transition reason (required with --reject or --waive).")

    # rapid status
    status_p = subparsers.add_parser(
        "status",
        help="Display active session, run state, tasks, gates, and last evaluation verdict.",
        description="Print a summary of the active run session and lifecycle state.",
    )
    status_p.add_argument("--json", action="store_true", help="Emit status summary JSON output.")

    # rapid attach
    attach_p = subparsers.add_parser(
        "attach",
        help="Attach a file to the active run as artifact evidence (writes state).",
        description="Copy a file into the run evidence as an artifact (producer rapid:attach) with a human-readable label.",
    )
    attach_p.add_argument("path", help="File to attach (inside the project or the run workspace).")
    attach_p.add_argument("--label", required=True, help="Short description of what the artifact shows.")
    attach_p.add_argument("--task", dest="task", help="Task identifier the artifact backs (default: the only in_progress task).")

    # rapid abort
    abort_p = subparsers.add_parser(
        "abort",
        help="Cancel the active run and clear the porcelain session.",
        description="Transition active run to cancelled and remove .rapid-os/session.json.",
    )
    abort_p.add_argument("--reason", dest="reason", help="Cancellation reason.")

    # rapid setup
    setup_p = subparsers.add_parser(
        "setup",
        help="Drive the onboarding: next/show read it, set/stack/doc/finish write it.",
        description=(
            "Complete the onboarding with commands only. next and show never write, not even "
            ".rapid-os/setup.json; set, stack, doc and finish write it atomically and return the next decision."
        ),
    )
    setup_sub = setup_p.add_subparsers(dest="setup_action")
    for _name, _help in (
        ("next", "Print the next onboarding decision (read-only)."),
        ("show", "Print the onboarding state, persisted or derived from disk (read-only)."),
    ):
        _sp = setup_sub.add_parser(_name, help=_help, description=_help)
        _sp.add_argument("--json", action="store_true", help="Emit JSON output.")

    _sp = setup_sub.add_parser(
        "set",
        help="Record a decision: stack, topology, archetype, agents or test-command (writes state).",
        description=(
            "Record one onboarding decision in .rapid-os/setup.json. Standards are written by 'rapid setup finish'. "
            "Keys: stack <id>, topology <id>, archetype <mvp|corporate>, agents <id,id>, test-command '<cmd>' ('none' for no command)."
        ),
    )
    _sp.add_argument("key", nargs="?", help="stack, topology, archetype, agents or test-command.")
    _sp.add_argument("value", nargs="?", help="Value of the decision.")
    _sp.add_argument("--json", action="store_true", help="Emit JSON output.")

    _sp = setup_sub.add_parser(
        "stack",
        help="Store a tech-stack.md written by your agent (writes state).",
        description=(
            "Read a tech-stack.md from --file (use - for stdin) with the sections Runtime, Framework and Testing, "
            "write it to .rapid-os/standards/tech-stack.md and record stack.source = custom."
        ),
    )
    _sp.add_argument("--custom", action="store_true", help="Use a stack written by the agent instead of a catalog stack.")
    _sp.add_argument("--file", dest="file", metavar="PATH", help="File with the tech-stack.md, or - for stdin.")
    _sp.add_argument("--json", action="store_true", help="Emit JSON output.")

    _sp = setup_sub.add_parser(
        "doc",
        help="Write, skip, confirm or reopen a project document (writes state).",
        description=(
            "Write docs/<FILE>.md for brief, business, data-model or architecture. The agent sends only the body; "
            "Rapid OS adds the frontmatter (rapid-doc, source, status, sha256) and keeps a .bak of the previous file. "
            "provided => confirmed; drafted => draft until --confirm."
        ),
    )
    _sp.add_argument("doc_id", help="brief, business, data-model or architecture.")
    _sp.add_argument("--source", choices=("provided", "drafted"), help="Who wrote the body: the person (provided) or the agent (drafted).")
    _sp.add_argument("--file", dest="file", metavar="PATH", help="File with the body, or - for stdin.")
    _sp.add_argument("--replace", action="store_true", help="Let a draft replace content a person provided, or import over an existing file.")
    _sp.add_argument("--skip", action="store_true", help="Record that the document is not needed.")
    _sp.add_argument("--confirm", action="store_true", help="A person confirms a draft; only the status changes.")
    _sp.add_argument("--reopen", action="store_true", help="Return a skipped document to pending, or a confirmed draft to draft.")
    _sp.add_argument("--from-legacy", dest="from_legacy", action="store_true", help="Import .rapid-os/standards/business.md as docs/BUSINESS_RULES.md (business only).")
    _sp.add_argument("--json", action="store_true", help="Emit JSON output.")

    _sp = setup_sub.add_parser(
        "finish",
        help="Apply the decisions to the project and close the onboarding (writes state).",
        description=(
            "When no decision is left (RAPID1407 otherwise), copy stack, topology, archetype and security to "
            ".rapid-os/standards, save the config, rebuild the agent files and mark the setup finished. Idempotent."
        ),
    )
    _sp.add_argument("--json", action="store_true", help="Emit JSON output.")

    # rapid shortcuts
    shortcuts_p = subparsers.add_parser(
        "shortcuts",
        help="Install, list or remove generated /rapid-<mode> harness shortcuts (install/remove write state).",
        description="Generate /rapid-<mode> shortcuts for each harness from templates/shortcuts (writes with .bak backups).",
    )
    shortcuts_sub = shortcuts_p.add_subparsers(dest="shortcuts_action")
    for _name, _help in (
        ("install", "Write the shortcut files for the selected harnesses (idempotent)."),
        ("list", "Show installed state per harness and modes skipped for lack of a playbook (read-only)."),
        ("remove", "Delete shortcut files that carry the generated marker."),
    ):
        _sp = shortcuts_sub.add_parser(_name, help=_help, description=_help)
        _sp.add_argument(
            "--harness",
            action="append",
            dest="harness",
            help="Harness id (repeatable). Defaults to the tools in .rapid-os/config.json.",
        )
        _sp.add_argument("--dry-run", dest="dry_run", action="store_true", help="Show what would change without writing or deleting.")
        _sp.add_argument("--json", action="store_true", help="Emit JSON output.")
        _sp.add_argument(
            "--global",
            dest="global_scope",
            action="store_true",
            help="Use the user-level skills folder of each harness (in your home directory) instead of the project; needs --harness.",
        )
        _sp.add_argument(
            "--only",
            action="append",
            dest="only",
            metavar="SHORTCUT",
            help="Only this shortcut (repeatable), e.g. --only rapid-init.",
        )
        if _name != "list":
            _sp.add_argument(
                "--hooks",
                action="store_true",
                help="Also install (or remove) the Rapid OS hooks in .claude/settings.json; requires the claude harness.",
            )

    # rapid hook
    hook_p = subparsers.add_parser(
        "hook",
        help="Claude Code hook entry points (read the hook JSON from stdin; never fail the agent).",
        description="Run as a Claude Code hook: 'stop' keeps the agent working until the run needs a person; 'pre-tool' denies reserved commands and edits inside .rapid-os/.",
    )
    hook_sub = hook_p.add_subparsers(dest="hook_event")
    hook_sub.add_parser("stop", help="Stop hook: block the stop while the run still has agent work.")
    hook_sub.add_parser("pre-tool", help="PreToolUse hook: deny reserved rapid commands and writes to .rapid-os/.")

    return parser


def main(argv=None):
    ensure_utf8_stdio()
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        init_project(args)
    elif args.command == "scan":
        scan_command(args)
    elif args.command == "context":
        context_command(args)
    elif args.command == "spec":
        spec_command(args)
    elif args.command == "policy":
        policy_command(args)
    elif args.command == "run":
        run_command(args)
    elif args.command == "start":
        start_command(args)
    elif args.command == "next":
        next_command(args)
    elif args.command == "finish":
        finish_command(args)
    elif args.command == "approve":
        approve_command(args)
    elif args.command == "status":
        status_command(args)
    elif args.command == "abort":
        abort_command(args)
    elif args.command == "attach":
        attach_command(args)
    elif args.command == "hook":
        hook_command(args)
    elif args.command == "shortcuts":
        shortcuts_command(args)
    elif args.command == "setup":
        setup_command(args)
    elif args.command == "check":
        check_command(args)
    elif args.command == "task":
        task_command(args)
    elif args.command == "harness":
        harness_command(args)
    elif args.command == "evidence":
        evidence_command(args)
    elif args.command == "eval":
        eval_command(args)
    elif args.command == "skill":
        manage_skills(args)
    elif args.command == "mcp":
        generate_mcp_config(args)
    elif args.command == "scope":
        scope_feature(args)
    elif args.command == "deploy":
        deploy_assistant(args)
    elif args.command == "vision":
        add_visual_reference(args)
    elif args.command == "refine":
        refine_standard(args)
    elif args.command == "prompt":
        generate_prompt(args)
    elif args.command == "validate":
        validate_command(args)
    elif args.command == "doctor":
        doctor_command(args)
    elif args.command == "inspect-context":
        inspect_context_command(args)
    elif args.command == "guide":
        show_guide()
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())




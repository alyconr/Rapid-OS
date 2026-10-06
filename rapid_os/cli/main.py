import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
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
from rapid_os.adapters.context_sources import ContextSourceLoader
from rapid_os.adapters.execution_policy import (
    load_execution_policy,
    write_default_execution_policy,
)
from rapid_os.adapters.project_snapshot import write_project_snapshot
from rapid_os.adapters.run_registry import RunRegistry
from rapid_os.adapters.spec_registry import SpecRegistry
from rapid_os.core.process import run_npx_skills_add
from rapid_os.core.text import read_text_best_effort
from rapid_os.domain.agents import generate_agent_contexts
from rapid_os.domain.context import (
    ContextBudgetExceededError,
    ContextCompiler,
    ContextManifest,
    ContextRequest,
    ContextRequiredSourceMissingError,
)
from rapid_os.domain.execution import (
    EXECUTION_POLICY_SCHEMA_VERSION,
    RUN_SCHEMA_VERSION,
    ExecutionError,
    InvalidExecutionPolicyError,
    InvalidGateTransitionError,
    InvalidRunRecordError,
    InvalidSpecBindingError,
    InvalidTaskTransitionError,
    RunStatus,
    TaskStatus,
)
from rapid_os.domain.mcp import build_mcp_config
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
    validate_composed_context,
    validate_execution_policy,
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

OPTIONAL_DOC_TEMPLATES = {
    "BUSINESS_RULES.md": """# Business Rules

## Purpose
Describe the business rules this project must obey.

## Business goals
- TODO: List the business outcomes this software supports.

## Non-negotiable rules
- TODO: Add rules that must not be violated.

## Constraints
- TODO: Document operational, legal, budget, timing, or platform constraints.

## Assumptions
- TODO: List assumptions that should be confirmed.

## Glossary
- TODO: Define business terms and acronyms.
""",
    "SPECS.md": """# Specs

## Objective
Describe the feature or project objective.

## Scope
- TODO: List what is included.

## Out of scope
- TODO: List what is explicitly excluded.

## Functional flow
- TODO: Describe the expected user or system flow.

## Acceptance criteria
- TODO: Add testable acceptance criteria.

## Dependencies
- TODO: List systems, services, data, or people required.

## Risks
- TODO: Capture implementation and product risks.
""",
    "USER_STORIES.md": """# User Stories

## Actor
TODO: Identify the user, role, or system actor.

## User story
As a TODO, I want TODO, so that TODO.

## Expected value
- TODO: Explain the value delivered.

## Acceptance criteria
- TODO: Add criteria that prove the story is complete.

## Priority
TODO: Set priority or sequencing notes.

## Notes
TODO: Add open details, links, or follow-up questions.
""",
    "DATA_MODEL.md": """# Data Model

## Entities
- TODO: List domain entities.

## Attributes
- TODO: Describe important fields for each entity.

## Relationships
- TODO: Describe relationships between entities.

## Validation rules
- TODO: Add required fields, formats, ranges, and invariants.

## Enums / constants
- TODO: List known states, types, or fixed values.

## Open questions
- TODO: Capture unresolved modeling decisions.
""",
}


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

    parts = [part.strip() for part in agent_sel.split(",")]
    if "1" in parts:
        selected_tools.append("cursor")
    if "2" in parts:
        selected_tools.append("claude")
    if "3" in parts:
        selected_tools.append("antigravity")
    if "4" in parts:
        selected_tools.append("vscode")
    if "5" in parts:
        selected_tools.append("codex")
    return selected_tools


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


def create_optional_docs_scaffold(input_fn=None):
    wants_docs = prompt_yes_no(
        "Do you want to create optional documentation scaffolding in /docs?",
        default=False,
        input_fn=input_fn,
    )
    if wants_docs is None:
        print_warning("Documentacion opcional cancelada.")
        return []
    if not wants_docs:
        return []

    selected = []
    for filename in OPTIONAL_DOC_TEMPLATES:
        should_create = prompt_yes_no(
            f"Create docs/{filename}?",
            default=False,
            input_fn=input_fn,
        )
        if should_create is None:
            print_warning("Documentacion opcional cancelada; no se escribieron docs.")
            return []
        if should_create:
            selected.append(filename)

    if not selected:
        return []

    docs_dir = CURRENT_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for filename in selected:
        target = resolve_child_path(docs_dir, filename, single_segment=True)
        safe_write_text(
            target,
            OPTIONAL_DOC_TEMPLATES[filename],
            encoding="utf-8",
            backup=True,
            create_parents=True,
        )
        print_success(f"docs/{filename} creado")
        written.append(target)
    return written


def init_project(args):
    print_step("Inicializando Rapid OS...")
    scan = None
    suggestions = None
    use_suggestions = False

    if not getattr(args, "no_scan", False):
        scan = scan_project(CURRENT_DIR)
        suggestions = suggest_init_choices(scan)
        if suggestions.has_any():
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
    else:
        stacks_path = TEMPLATES_DIR / "stacks"
        if not stacks_path.exists():
            print_error(f"Templates no encontrados en {stacks_path}")
            return
        print(f"DEBUG: Buscando templates en {stacks_path}")
        stacks = sorted([f.stem for f in stacks_path.glob("*.md")])
        if not stacks:
            print_error(f"No se encontraron templates de stack en {stacks_path}")
            return
        print(f"DEBUG: Encontrados: {stacks}")
        print("\n🛠  SELECCIONA TECH STACK:")
        for i, s in enumerate(stacks, 1):
            print(f" {i}) {s}")
        try:
            idx = int(input("Opción: ").strip()) - 1
            stack_name = stacks[idx] if 0 <= idx < len(stacks) else stacks[0]
        except (ValueError, IndexError, EOFError):
            stack_name = stacks[0]

    try:
        stack_name = validate_identifier(stack_name, "stack")
        stack_src = resolve_child_path(
            TEMPLATES_DIR / "stacks", f"{stack_name}.md", single_segment=True
        )
    except ValueError as exc:
        print_error(str(exc))
        return

    if not stack_src.exists():
        print_error(f"Template de stack no encontrado: {stack_name} ({stack_src})")
        return

    # 2. Topología
    topologies_path = TEMPLATES_DIR / "topologies"
    if not topologies_path.exists():
        topologies_path.mkdir(parents=True, exist_ok=True)
    topos = sorted([f.stem for f in topologies_path.glob("*.md")])
    topo_name = None
    suggested_topology = (
        suggestions.topology.value if suggestions and suggestions.topology else None
    )
    if use_suggestions and suggested_topology in topos:
        topo_name = suggested_topology
    if topos and topo_name is None:
        print("\n🏗️  SELECCIONA TOPOLOGÍA:")
        for i, t in enumerate(topos, 1):
            print(f" {i}) {t}")
        try:
            idx = int(input("Opción: ").strip()) - 1
            topo_name = topos[idx] if 0 <= idx < len(topos) else topos[0]
        except (ValueError, IndexError, EOFError):
            topo_name = topos[0]
    if topo_name:
        try:
            topo_name = validate_identifier(topo_name, "topology")
            topo_src = resolve_child_path(
                topologies_path, f"{topo_name}.md", single_segment=True
            )
            safe_copy_file(topo_src, standards_dest / "topology.md", backup=True)
        except (ValueError, OSError) as exc:
            print_error(f"No se pudo copiar la topologia '{topo_name}': {exc}")
            return

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
    else:
        print("\n📊 SELECCIONA ARQUETIPO:")
        print(" 1) mvp        (Velocidad)")
        print(" 2) corporate  (Seguridad)")
        sel = input("Opción [1]: ").strip()
        archetype = "corporate" if sel == "2" else "mvp"

    try:
        archetype_dir = resolve_child_path(
            TEMPLATES_DIR / "archetypes", archetype, single_segment=True
        )
        safe_copy_file(
            stack_src,
            standards_dest / "tech-stack.md",
            backup=True,
        )
        rules_src = resolve_child_path(
            archetype_dir, "coding-rules.md", single_segment=True
        )
        if rules_src.exists():
            safe_copy_file(rules_src, standards_dest / "coding-rules.md", backup=True)
        sec_src = resolve_child_path(
            archetype_dir, "security.md", single_segment=True
        )
        if sec_src.exists():
            safe_copy_file(sec_src, standards_dest / "security.md", backup=True)
    except (ValueError, OSError) as exc:
        print_error(f"No se pudieron inicializar los estandares del proyecto: {exc}")
        return

    # 4. Agentes
    print("\n🤖 SELECCIONA TUS AGENTES (Separados por coma):")
    print(" 1) Cursor (.cursorrules)")
    print(" 2) Claude Code (CLAUDE.md)")
    print(" 3) Google Antigravity (.agent/rules)")
    print(" 4) VS Code / Copilot (INSTRUCTIONS.md)")
    print(" 5) Codex (AGENTS.md)")
    agent_sel = input("Opción [1]: ").strip()
    selected_tools = parse_agent_selection(agent_sel)

    # 5. Herramientas de Investigación (Research)
    print("\n🔍 CAPACIDADES DE INVESTIGACIÓN (Opcional):")
    print(" 1) Context7 (Documentación actualizada de librerías)")
    print(" 2) Firecrawl (Rastreo web y extracción de datos)")
    res_sel = input("Opción (ej. 1,2 o Enter para ninguna): ").strip()

    if res_sel:
        parts = res_sel.split(",")
        if "1" in parts:
            selected_tools.append("context7")
        if "2" in parts:
            selected_tools.append("firecrawl")

    save_project_config({"tools": selected_tools}, PROJECT_RAPID_DIR, CONFIG_FILE)

    # 5. Negocio (Smart Import - Soporte TXT)
    print("\n--- CONFIGURACIÓN DE NEGOCIO ---")
    biz_templates_path = TEMPLATES_DIR / "business"
    if not biz_templates_path.exists():
        biz_templates_path.mkdir(parents=True, exist_ok=True)
    biz_files = sorted([f.stem for f in biz_templates_path.glob("*.md")])
    biz_content = ""

    if not biz_files:
        print("ℹ️  No hay plantillas guardadas.")
        # --- AQUÍ ESTÁ EL CAMBIO PARA SOPORTAR TXT ---
        if input("¿Importar archivo (md/txt)? [Y/n]: ").lower() != "n":
            path_str = (
                input("📂 Arrastra el archivo (.md, .txt): ")
                .strip()
                .replace("'", "")
                .replace('"', "")
            )
            local_path = Path(path_str)
            if local_path.exists():
                try:
                    biz_content = local_path.read_text(encoding="utf-8")
                    print_success(f"Leído correctamente: {local_path.name}")

                    if input("¿Guardar como plantilla? [y/N]: ").lower() == "y":
                        tpl_name = input("Nombre plantilla: ").strip()
                        safe_tpl_name = validate_identifier(
                            tpl_name, "business template"
                        )
                        tpl_target = resolve_child_path(
                            biz_templates_path,
                            f"{safe_tpl_name}.md",
                            single_segment=True,
                        )
                        # Siempre guardamos como .md internamente para mantener formato
                        safe_write_text(
                            tpl_target,
                            biz_content,
                            encoding="utf-8",
                            backup=True,
                        )
                except (OSError, UnicodeDecodeError, ValueError) as e:
                    print_error(f"No se pudo procesar la plantilla de negocio: {e}")
                    return
            else:
                rules = input("Archivo no existe. Escribe reglas manuales: ")
                if rules:
                    biz_content = f"# BUSINESS RULES\n{rules}"
        else:
            rules = input("Escribe reglas manuales: ")
            if rules:
                biz_content = f"# BUSINESS RULES\n{rules}"
    else:
        print(" 1) Escribir manual")
        print(" 2) Importar archivo local (.md, .txt)")
        for i, b in enumerate(biz_files, 1):
            print(f" {i + 2}) {b}")
        opcion = input("Opción [1]: ").strip()

        if opcion == "2":
            path_str = (
                input("📂 Arrastra el archivo (.md, .txt): ")
                .strip()
                .replace("'", "")
                .replace('"', "")
            )
            local_path = Path(path_str)
            if local_path.exists():
                try:
                    biz_content = local_path.read_text(encoding="utf-8")
                    print_success(f"Leído correctamente: {local_path.name}")
                except (OSError, UnicodeDecodeError) as e:
                    print_error(f"Error leyendo archivo: {e}")
                    return

        elif opcion.isdigit() and int(opcion) > 2:
            idx = int(opcion) - 3
            if 0 <= idx < len(biz_files):
                try:
                    selected_biz = validate_identifier(
                        biz_files[idx], "business template"
                    )
                    biz_path = resolve_child_path(
                        biz_templates_path,
                        f"{selected_biz}.md",
                        single_segment=True,
                    )
                    biz_content = biz_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError, ValueError) as e:
                    print_error(f"Error leyendo plantilla de negocio: {e}")
                    return

        if (
            not biz_content
            and opcion != "2"
            and not (opcion.isdigit() and int(opcion) > 2)
        ):
            rules = input("Reglas manuales: ")
            if rules:
                biz_content = f"# BUSINESS RULES\n{rules}"

    if biz_content:
        safe_write_text(
            standards_dest / "business.md",
            biz_content,
            encoding="utf-8",
            backup=True,
        )

    create_optional_docs_scaffold()
    regenerate_context()
    print("\n🚀 ¡Rapid OS activo!")


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
    sys.exit(render_validation_report(report, args.json, args.strict))


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
            validate_stack_topology(PROJECT_RAPID_DIR),
            validate_composed_context(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_project_intelligence(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_spec_registry(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_execution_policy(PROJECT_RAPID_DIR, CURRENT_DIR),
            validate_run_registry(PROJECT_RAPID_DIR, CURRENT_DIR),
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
            record = registry.create(
                spec_id=spec_id,
                spec_revision=getattr(args, "spec_revision", None),
                run_id=getattr(args, "run_id", None),
                harness=getattr(args, "harness", None) or "cursor",
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


def show_guide():
    print("📘 RAPID OS - COMANDOS")
    print(" init    -> Configurar proyecto")
    print(" scan    -> Inspeccionar inteligencia del proyecto")
    print(" context -> Compilar contexto selectivo por tarea")
    print(" spec    -> Gestionar Spec Registry v3 (create, list, show, revise, status, export-legacy)")
    print(" policy  -> Gestionar Execution Policy v3 (show, init)")
    print(" run     -> Gestionar Run Contracts & Lifecycle v3 (create, list, show, status, task, gate)")
    print(" skill   -> Instalar capacidades (Local/Vercel)")
    print(" mcp     -> Configurar herramientas BD")
    print(" vision  -> Agregar referencias visuales")
    print(" scope   -> Crear specs (legacy singleton workflow)")
    print(" prompt  -> Generar prompt para IA")
    print(" validate -> Validar proyecto Rapid OS")
    print(" doctor  -> Diagnosticar instalacion local")
    print(" inspect-context -> Previsualizar contexto ensamblado")


def _add_spec_authoring_arguments(subparser, *, is_create: bool = False):
    if is_create:
        subparser.add_argument("--id", dest="spec_id")
    subparser.add_argument("--title")
    subparser.add_argument("--mode")
    subparser.add_argument(
        "--objective",
        "--business-objective",
        dest="business_objective",
    )
    subparser.add_argument(
        "--problem",
        "--problem-statement",
        dest="problem_statement",
    )
    subparser.add_argument("--scope", action="append")
    subparser.add_argument(
        "--out-of-scope",
        dest="out_of_scope",
        action="append",
    )
    subparser.add_argument(
        "--actor",
        "--actors-users",
        dest="actors_users",
        action="append",
    )
    subparser.add_argument(
        "--main-flow",
        "--flow",
        dest="main_flow",
        action="append",
    )
    subparser.add_argument(
        "--edge-case",
        dest="edge_cases",
        action="append",
    )
    subparser.add_argument(
        "--business-rule",
        "--rule",
        dest="business_rules",
        action="append",
    )
    subparser.add_argument(
        "--technical-constraint",
        "--constraint",
        dest="technical_constraints",
        action="append",
    )
    subparser.add_argument(
        "--affected-path",
        dest="affected_paths",
        action="append",
    )
    subparser.add_argument("--data-impact", dest="data_impact")
    subparser.add_argument(
        "--acceptance",
        "--acceptance-criteria",
        dest="acceptance_criteria",
        action="append",
    )
    subparser.add_argument(
        "--testing",
        "--testing-strategy",
        dest="testing_strategy",
        action="append",
    )
    subparser.add_argument(
        "--task",
        "--implementation-task",
        dest="implementation_tasks",
        action="append",
    )
    subparser.add_argument("--tag", dest="tags", action="append")
    if is_create:
        subparser.add_argument("--status", choices=["draft", "ready"])
        subparser.add_argument(
            "--export-legacy",
            dest="export_legacy",
            action="store_true",
        )
    subparser.add_argument("--json", action="store_true")


def create_parser():
    parser = argparse.ArgumentParser(description="Rapid OS")
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init")
    init.add_argument("--stack")
    init.add_argument(
        "--archetype",
        type=str.lower,
        choices=list(SUPPORTED_ARCHETYPES),
    )
    init.add_argument("--no-scan", action="store_true")

    scan = subparsers.add_parser("scan")
    scan.add_argument("--json", action="store_true")
    scan.add_argument("--write", action="store_true")
    scan.add_argument("--verbose", action="store_true")

    context = subparsers.add_parser("context")
    context.add_argument("action", choices=["compile"], nargs="?")
    context.add_argument("--mode", default="general")
    context.add_argument(
        "--harness",
        choices=["cursor", "claude", "codex", "vscode", "antigravity"],
    )
    context.add_argument("--objective")
    context.add_argument("--max-chars", type=int)
    context.add_argument("--constraint", action="append")
    context.add_argument("--tag", action="append")
    context.add_argument("--path", action="append")
    context.add_argument("--spec")
    context.add_argument("--spec-revision", type=int)
    context.add_argument("--json", action="store_true")
    context.add_argument("--manifest", action="store_true")

    spec = subparsers.add_parser("spec")
    spec_subparsers = spec.add_subparsers(dest="spec_action")

    spec_create = spec_subparsers.add_parser("create")
    _add_spec_authoring_arguments(spec_create, is_create=True)

    spec_list = spec_subparsers.add_parser("list")
    spec_list.add_argument(
        "--status",
        choices=["draft", "ready", "archived"],
    )
    spec_list.add_argument("--json", action="store_true")

    spec_show = spec_subparsers.add_parser("show")
    spec_show.add_argument("spec_id")
    spec_show.add_argument("--revision", type=int)
    spec_show.add_argument("--json", action="store_true")

    spec_revise = spec_subparsers.add_parser("revise")
    spec_revise.add_argument("spec_id")
    _add_spec_authoring_arguments(spec_revise, is_create=False)

    spec_status = spec_subparsers.add_parser("status")
    spec_status.add_argument("spec_id")
    spec_status.add_argument("status")
    spec_status.add_argument("--json", action="store_true")

    spec_export = spec_subparsers.add_parser("export-legacy")
    spec_export.add_argument("spec_id")
    spec_export.add_argument("--revision", type=int)

    policy = subparsers.add_parser("policy")
    policy_subparsers = policy.add_subparsers(dest="policy_action")

    policy_show = policy_subparsers.add_parser("show")
    policy_show.add_argument("--json", action="store_true")

    policy_init = policy_subparsers.add_parser("init")
    policy_init.add_argument("--json", action="store_true")

    run = subparsers.add_parser("run")
    run_subparsers = run.add_subparsers(dest="run_action")

    run_create = run_subparsers.add_parser("create")
    run_create.add_argument("--spec")
    run_create.add_argument("--spec-revision", dest="spec_revision", type=int)
    run_create.add_argument("--id", dest="run_id")
    run_create.add_argument(
        "--harness",
        default="cursor",
        choices=["cursor", "claude", "codex", "vscode", "antigravity"],
    )
    run_create.add_argument("--classification")
    run_create.add_argument("--risk")
    run_create.add_argument("--json", action="store_true")

    run_list = run_subparsers.add_parser("list")
    run_list.add_argument("--status")
    run_list.add_argument("--json", action="store_true")

    run_show = run_subparsers.add_parser("show")
    run_show.add_argument("run_id")
    run_show.add_argument("--state-revision", dest="state_revision", type=int)
    run_show.add_argument("--json", action="store_true")

    run_status = run_subparsers.add_parser("status")
    run_status.add_argument("run_id")
    run_status.add_argument("status")
    run_status.add_argument("--reason")
    run_status.add_argument("--json", action="store_true")

    run_task = run_subparsers.add_parser("task")
    run_task.add_argument("run_id")
    run_task.add_argument("task_id")
    run_task.add_argument("status")
    run_task.add_argument("--reason")
    run_task.add_argument("--json", action="store_true")

    run_gate = run_subparsers.add_parser("gate")
    run_gate.add_argument("run_id")
    run_gate.add_argument("gate_id")
    run_gate.add_argument("disposition")
    run_gate.add_argument("--reason")
    run_gate.add_argument("--json", action="store_true")

    skill = subparsers.add_parser("skill")
    skill.add_argument("action", choices=["list", "install", "add"], nargs="?")
    skill.add_argument("name", nargs="?")

    scope = subparsers.add_parser("scope")
    scope.add_argument("--register", action="store_true")
    scope.add_argument("--spec-id", dest="spec_id")
    scope.add_argument("--status", choices=["draft", "ready"])

    deploy = subparsers.add_parser("deploy")
    deploy.add_argument("target", nargs="?")
    vision = subparsers.add_parser("vision")
    vision.add_argument("path", nargs="?")
    mcp = subparsers.add_parser("mcp")
    mcp.add_argument("--ide", choices=["codex", "claude", "cursor", "vscode", "antigravity"])
    mcp.add_argument("--scope", choices=["project", "global"])
    refine = subparsers.add_parser("refine")
    refine.add_argument("file")
    subparsers.add_parser("prompt")
    validate = subparsers.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    validate.add_argument("--strict", action="store_true")
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--strict", action="store_true")
    inspect_context = subparsers.add_parser("inspect-context")
    inspect_context.add_argument("--json", action="store_true")
    inspect_context.add_argument("--summary", action="store_true")
    subparsers.add_parser("guide")
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


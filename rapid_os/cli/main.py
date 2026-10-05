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
from rapid_os.core.identifiers import validate_identifier
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
from rapid_os.core.process import run_npx_skills_add
from rapid_os.core.text import read_text_best_effort
from rapid_os.domain.agents import generate_agent_contexts
from rapid_os.domain.mcp import build_mcp_config
from rapid_os.domain.scanner import scan_project, suggest_init_choices
from rapid_os.domain.scope import (
    ScopeSpec,
    normalize_mode,
    parse_list,
    write_scope_artifacts,
)
from rapid_os.domain.validation import (
    ERROR,
    INFO,
    WARNING,
    Diagnostic,
    ValidationReport,
    inspect_project_context,
    validate_composed_context,
    validate_project,
    validate_project_config,
    validate_project_standards,
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

        if not check_node_installed():
            print_error("Necesitas Node.js (npx) para instalar skills remotas.")
            return

        print_step(f"Invocando Vercel Skills para instalar '{skill_name}'...")
        try:
            run_npx_skills_add(skill_name, runner=subprocess.run)
            print_success(f"Skill '{skill_name}' instalada.")
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


def deploy_assistant(args):
    raw_target = args.target or input("Target (aws, vercel): ").strip()
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


def show_guide():
    print("📘 RAPID OS - COMANDOS")
    print(" init    -> Configurar proyecto")
    print(" skill   -> Instalar capacidades (Local/Vercel)")
    print(" mcp     -> Configurar herramientas BD")
    print(" vision  -> Agregar referencias visuales")
    print(" scope   -> Crear specs")
    print(" prompt  -> Generar prompt para IA")
    print(" validate -> Validar proyecto Rapid OS")
    print(" doctor  -> Diagnosticar instalacion local")
    print(" inspect-context -> Previsualizar contexto ensamblado")


def create_parser():
    parser = argparse.ArgumentParser(description="Rapid OS")
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init")
    init.add_argument("--stack")
    init.add_argument("--archetype", choices=list(SUPPORTED_ARCHETYPES))
    init.add_argument("--no-scan", action="store_true")

    skill = subparsers.add_parser("skill")
    skill.add_argument("action", choices=["list", "install", "add"], nargs="?")
    skill.add_argument("name", nargs="?")

    subparsers.add_parser("scope")
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

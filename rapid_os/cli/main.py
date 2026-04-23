import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from rapid_os.adapters.agents import DEFAULT_AGENT_REGISTRY
from rapid_os.adapters.mcp import render_claude_desktop_config
from rapid_os.core.config import load_project_config, save_project_config
from rapid_os.core.context import compose_project_context
from rapid_os.core.filesystem import check_node_installed, create_backup
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


def regenerate_context():
    """Compila estándares y genera SOLO para las herramientas seleccionadas."""
    full_context = compose_project_context(PROJECT_RAPID_DIR, CURRENT_DIR)
    config = load_project_config(CONFIG_FILE)
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
        target = docs_dir / filename
        create_backup(target)
        target.write_text(OPTIONAL_DOC_TEMPLATES[filename], encoding="utf-8")
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
        print(f"DEBUG: Buscando templates en {stacks_path}")
        stacks = sorted([f.stem for f in stacks_path.glob("*.md")])
        print(f"DEBUG: Encontrados: {stacks}")
        print("\n🛠  SELECCIONA TECH STACK:")
        for i, s in enumerate(stacks, 1):
            print(f" {i}) {s}")
        try:
            idx = int(input("Opción: ").strip()) - 1
            stack_name = stacks[idx] if 0 <= idx < len(stacks) else stacks[0]
        except Exception:
            stack_name = stacks[0]

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
        except Exception:
            topo_name = topos[0]
    if topo_name:
        shutil.copy(topologies_path / f"{topo_name}.md", standards_dest / "topology.md")

    # 3. Arquetipo
    print("\n📊 SELECCIONA ARQUETIPO:")
    print(" 1) mvp        (Velocidad)")
    print(" 2) corporate  (Seguridad)")
    sel = input("Opción [1]: ").strip()
    archetype = "corporate" if sel == "2" else "mvp"

    try:
        shutil.copy(
            TEMPLATES_DIR / "stacks" / f"{stack_name}.md",
            standards_dest / "tech-stack.md",
        )
        rules_src = TEMPLATES_DIR / "archetypes" / archetype / "coding-rules.md"
        if rules_src.exists():
            shutil.copy(rules_src, standards_dest / "coding-rules.md")
        sec_src = TEMPLATES_DIR / "archetypes" / archetype / "security.md"
        if sec_src.exists():
            shutil.copy(sec_src, standards_dest / "security.md")
    except Exception:
        pass

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
                        # Siempre guardamos como .md internamente para mantener formato
                        (biz_templates_path / f"{tpl_name}.md").write_text(
                            biz_content, encoding="utf-8"
                        )
                except Exception as e:
                    print_error(f"No se pudo leer el archivo: {e}")
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
                except Exception as e:
                    print_error(f"Error leyendo archivo: {e}")

        elif opcion.isdigit() and int(opcion) > 2:
            idx = int(opcion) - 3
            if 0 <= idx < len(biz_files):
                biz_content = (biz_templates_path / f"{biz_files[idx]}.md").read_text(
                    encoding="utf-8"
                )

        if (
            not biz_content
            and opcion != "2"
            and not (opcion.isdigit() and int(opcion) > 2)
        ):
            rules = input("Reglas manuales: ")
            if rules:
                biz_content = f"# BUSINESS RULES\n{rules}"

    if biz_content:
        (standards_dest / "business.md").write_text(biz_content, encoding="utf-8")

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
        if not skill_name:
            print_error("Especifica el nombre (ej. vercel-labs/agent-skills).")

        if not check_node_installed():
            print_error("Necesitas Node.js (npx) para instalar skills remotas.")

        print_step(f"Invocando Vercel Skills para instalar '{skill_name}'...")
        try:
            # Usamos shell=True para compatibilidad con npx en Windows
            cmd = f"npx skills add {skill_name}"
            subprocess.run(cmd, shell=True, check=True)
            print_success(f"Skill '{skill_name}' instalada.")
        except subprocess.CalledProcessError:
            print_error("Falló la instalación remota.")
        return

    # MODO 3: INSTALAR LOCAL (RAPID TEMPLATES)
    if action == "install":
        if not skill_name:
            print_error("Especifica el nombre del template local.")

        src_skill = TEMPLATES_DIR / "skills" / skill_name
        if not src_skill.exists():
            print_error(
                f"Template '{skill_name}' no existe. Usa 'add' para buscar en remoto."
            )

        config = load_project_config(CONFIG_FILE)
        tools = config.get("tools", ["cursor", "claude", "antigravity"])

        targets = []
        if "cursor" in tools:
            targets.append(CURRENT_DIR / ".cursor" / "skills")
        if "claude" in tools:
            targets.append(CURRENT_DIR / ".claude" / "skills")
        if "antigravity" in tools:
            targets.append(CURRENT_DIR / ".agent" / "skills")

        print_step(f"Instalando template local '{skill_name}'...")
        for target_root in targets:
            target_path = target_root / skill_name
            if target_path.exists():
                shutil.rmtree(target_path)
            try:
                target_root.mkdir(parents=True, exist_ok=True)
                shutil.copytree(src_skill, target_path)
                print(f"  -> {target_root.name}/{skill_name}")
            except Exception as e:
                print_warning(f"Error: {e}")

        print_success("Skill local activada.")


def generate_mcp_config(args):
    print_step("Configurando MCP...")
    topo_file = PROJECT_RAPID_DIR / "standards" / "topology.md"
    if not topo_file.exists():
        choice = prompt_menu(
            "No se detecto inicializacion Rapid OS para MCP.",
            ("continue with a minimal MCP setup", "cancel"),
        )
        if choice != 0:
            print_warning("Configuracion MCP cancelada.")
            return
        standards_dir = PROJECT_RAPID_DIR / "standards"
        standards_dir.mkdir(parents=True, exist_ok=True)
        topo_file.write_text(
            "# Topology\n\nMinimal MCP setup for standalone rapid mcp usage.\n",
            encoding="utf-8",
        )
        if not CONFIG_FILE.exists():
            save_project_config({"tools": []}, PROJECT_RAPID_DIR, CONFIG_FILE)

    topo_content = topo_file.read_text(encoding="utf-8")
    config = load_project_config(CONFIG_FILE)
    tools = config.get("tools", [])
    mcp_config = build_mcp_config(topo_content, tools, CURRENT_DIR, TEMPLATES_DIR)

    for warning in mcp_config.warnings:
        print_warning(warning.message)

    target = CURRENT_DIR / "claude_desktop_config.json"
    create_backup(target)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(render_claude_desktop_config(mcp_config), f, indent=2)
    print_success(f"Configuración MCP: {target.name}")


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
    target = args.target or input("Target (aws, vercel): ").strip()
    tpl = TEMPLATES_DIR / "deploy" / f"{target}.md"
    instructions = (
        read_text_best_effort(tpl) if tpl.exists() else f"Deploy to {target}"
    )
    (CURRENT_DIR / "DEPLOY.md").write_text(
        f"# DEPLOY {target}\n{instructions}", encoding="utf-8"
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
    if not src.exists():
        print_error("Imagen no existe")
    dest = CURRENT_DIR / "references" / src.name
    dest.parent.mkdir(exist_ok=True)
    shutil.copy(src, dest)
    desc = input("Descripción imagen: ")
    meta = dest.parent / "VISION_CONTEXT.md"
    with open(meta, "a", encoding="utf-8") as f:
        f.write(f"\n- **{src.name}**: {desc}")
    print_success("Referencia agregada")
    regenerate_context()


def refine_standard(args):
    path = Path(args.file)
    if not path.exists():
        print_error("Archivo no existe")
    print(
        "Prompt para IA: ACT AS ARCHITECT. REFINE:\n\n"
        f"{read_text_best_effort(path)}"
    )


def generate_prompt(args):
    """Genera un prompt optimizado basado en el contexto del proyecto."""
    if not PROJECT_RAPID_DIR.exists():
        print_error("No se detectó un proyecto Rapid OS. Ejecuta 'rapid init' primero.")

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
    init.add_argument("--archetype")
    init.add_argument("--no-scan", action="store_true")

    skill = subparsers.add_parser("skill")
    skill.add_argument("action", choices=["list", "install", "add"], nargs="?")
    skill.add_argument("name", nargs="?")

    subparsers.add_parser("scope")
    deploy = subparsers.add_parser("deploy")
    deploy.add_argument("target", nargs="?")
    vision = subparsers.add_parser("vision")
    vision.add_argument("path", nargs="?")
    subparsers.add_parser("mcp")
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

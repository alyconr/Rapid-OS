#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import shutil
import argparse
import time
import json
from pathlib import Path

# --- CONFIGURACIÓN GLOBAL ---
RAPID_HOME = Path.home() / ".rapid-os"
TEMPLATES_DIR = RAPID_HOME / "templates"
CURRENT_DIR = Path.cwd()
PROJECT_RAPID_DIR = CURRENT_DIR / ".rapid-os"


# --- UTILIDADES ---
def print_step(msg):
    print(f"🔹 {msg}")


def print_success(msg):
    print(f"✅ {msg}")


def print_warning(msg):
    print(f"⚠️  {msg}")


def print_error(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def create_backup(file_path):
    """Crea una copia de seguridad con timestamp si el archivo existe"""
    path = Path(file_path)
    if path.exists():
        timestamp = int(time.time())
        backup_path = path.parent / f"{path.name}.{timestamp}.bak"
        shutil.copy(path, backup_path)
        print_warning(f"Backup creado: {backup_path.name}")


# --- GENERADORES DE CONTEXTO (ADAPTADORES) ---


def generate_cursor_rules(context):
    """Adaptador para Cursor IDE"""
    target = CURRENT_DIR / ".cursorrules"
    create_backup(target)
    content = f"# RAPID OS - SYSTEM CONTEXT\n# DO NOT EDIT. Generated automatically.\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: .cursorrules (Cursor)")


def generate_claude_config(context):
    """Adaptador para Claude Code CLI"""
    target = CURRENT_DIR / "CLAUDE.md"
    create_backup(target)
    content = f"# PROJECT MEMORY\n# SOURCE OF TRUTH FOR AI.\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: CLAUDE.md (Claude Code)")


def generate_antigravity_config(context):
    """Adaptador para Google Antigravity (Rules System)"""
    # CORRECCIÓN: Según documentación oficial, las reglas van en .agent/rules
    antigravity_dir = CURRENT_DIR / ".agent" / "rules"
    antigravity_dir.mkdir(parents=True, exist_ok=True)

    target = antigravity_dir / "constitution.md"
    create_backup(target)

    # Agregamos instrucciones explícitas para que el agente sepa cuándo usarla
    header = """# PROJECT CONSTITUTION
# ACTIVATION: ALWAYS_ON
# DESCRIPTION: The core immutable rules and architecture for this project.

"""
    content = (
        header
        + f"""# IMMUTABLE TRUTH FOR GEMINI AGENTS.
# IF CONFLICTS ARISE, THIS DOCUMENT WINS.

{context}
"""
    )
    target.write_text(content, encoding="utf-8")
    print_success("Generado: .agent/rules/constitution.md (Antigravity)")


def generate_vscode_instructions(context):
    """Adaptador para VS Code / GitHub Copilot"""
    target = CURRENT_DIR / "INSTRUCTIONS.md"
    create_backup(target)
    content = f"# AI INSTRUCTIONS (COPILOT)\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: INSTRUCTIONS.md (VS Code)")


def regenerate_context():
    """Compila todos los estándares + REFERENCIAS VISUALES"""
    standards_dir = PROJECT_RAPID_DIR / "standards"
    full_context = ""

    # 1. ESTÁNDARES DE TEXTO
    priority = [
        "tech-stack.md",
        "topology.md",
        "security.md",
        "design.md",
        "business.md",
        "coding-rules.md",
    ]

    for filename in priority:
        path = standards_dir / filename
        if path.exists():
            full_context += (
                f"\n### 🛑 {filename.replace('.md', '').upper().replace('-', ' ')}\n"
            )
            full_context += path.read_text(encoding="utf-8") + "\n"

    # 2. REFERENCIAS VISUALES
    vision_meta = CURRENT_DIR / "references" / "VISION_CONTEXT.md"
    if vision_meta.exists():
        full_context += "\n### 👁️ VISUAL STANDARDS (SCREENSHOTS)\n"
        full_context += "I have provided screenshots in the `references/` directory.\n"
        full_context += (
            "Use these images as Ground Truth for UI structure, spacing, and colors.\n"
        )
        full_context += vision_meta.read_text(encoding="utf-8")
        full_context += (
            "\n\nINSTRUCTION: Before generating frontend code, ANALYZE these images.\n"
        )

    # Inyectar en todos los editores
    generate_cursor_rules(full_context)
    generate_claude_config(full_context)
    generate_antigravity_config(full_context)
    generate_vscode_instructions(full_context)


# --- COMANDOS PRINCIPALES ---


def init_project(args):
    print_step("Inicializando Rapid OS...")

    standards_dest = PROJECT_RAPID_DIR / "standards"
    standards_dest.mkdir(parents=True, exist_ok=True)

    # Selección de Stack
    if not args.stack:
        stacks_path = TEMPLATES_DIR / "stacks"
        if not stacks_path.exists():
            print_error("Templates no encontrados. Reinstala Rapid OS.")

        stacks = sorted([f.stem for f in stacks_path.glob("*.md")])
        if not stacks:
            print_error("No hay stacks disponibles.")

        print("\n🛠  SELECCIONA TECH STACK:")
        for i, s in enumerate(stacks, 1):
            print(f" {i}) {s}")

        sel = input("Opción: ").strip()
        try:
            idx = int(sel) - 1
            stack_name = stacks[idx] if 0 <= idx < len(stacks) else stacks[0]
        except ValueError:
            stack_name = stacks[0]
    else:
        stack_name = args.stack

    # Selección de Topología
    topologies_path = TEMPLATES_DIR / "topologies"
    if not topologies_path.exists():
        topologies_path.mkdir(parents=True, exist_ok=True)

    topos = sorted([f.stem for f in topologies_path.glob("*.md")])
    if topos:
        print("\n🏗️  SELECCIONA TOPOLOGÍA (ARQUITECTURA):")
        for i, t in enumerate(topos, 1):
            print(f" {i}) {t}")
        sel = input("Opción: ").strip()
        try:
            idx = int(sel) - 1
            topo_name = topos[idx] if 0 <= idx < len(topos) else topos[0]
        except ValueError:
            topo_name = topos[0]
        try:
            shutil.copy(
                topologies_path / f"{topo_name}.md", standards_dest / "topology.md"
            )
        except Exception as e:
            print_error(f"Error copiando topología: {e}")

    # Selección de Arquetipo
    if not args.archetype:
        print("\n📊 SELECCIONA ARQUETIPO:")
        print(" 1) mvp        (Velocidad)")
        print(" 2) corporate  (Seguridad estricta)")
        sel = input("Opción [1]: ").strip()
        archetype = "corporate" if sel == "2" else "mvp"
    else:
        archetype = args.archetype

    # Copia de Templates
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
    except Exception as e:
        print_error(f"Error copiando templates: {e}")

    # Negocio
    print("\n--- CONFIGURACIÓN DE NEGOCIO ---")
    if input("¿Definir reglas de negocio permanentes? [y/N]: ").lower() == "y":
        rules = input("Escribe las reglas clave: ")
        (standards_dest / "business.md").write_text(
            f"# BUSINESS RULES\n{rules}", encoding="utf-8"
        )

    regenerate_context()
    print("\n🚀 ¡Rapid OS activo! Tu IA ahora es un Senior Engineer.")


def generate_mcp_config(args):
    """Genera la configuración de herramientas MCP basada en la Topología"""
    print_step("Analizando Topología para Herramientas MCP...")

    # 1. Detectar Topología
    topo_file = PROJECT_RAPID_DIR / "standards" / "topology.md"
    if not topo_file.exists():
        print_error("No se detectó topología. Ejecuta 'rapid init' primero.")

    topo_content = topo_file.read_text(encoding="utf-8").lower()
    mcp_config = {"mcpServers": {}}

    # 2. Filesystem (Siempre activo para ver código)
    mcp_config["mcpServers"]["filesystem"] = {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", str(CURRENT_DIR)],
    }

    # 3. Detectar Bases de Datos en la Topología
    # PostgreSQL Local
    if "postgres" in topo_content and "supabase" not in topo_content:
        tpl_path = TEMPLATES_DIR / "mcp" / "postgres.json"
        if tpl_path.exists():
            print_step("✅ Detectado PostgreSQL. Inyectando driver MCP...")
            try:
                data = json.loads(tpl_path.read_text(encoding="utf-8"))
                mcp_config["mcpServers"].update(data)
            except Exception as e:
                print_warning(f"Error leyendo template postgres: {e}")

    # Supabase (SaaS)
    if "supabase" in topo_content:
        tpl_path = TEMPLATES_DIR / "mcp" / "supabase.json"
        if tpl_path.exists():
            print_step("✅ Detectado Supabase. Inyectando driver MCP...")
            try:
                data = json.loads(tpl_path.read_text(encoding="utf-8"))
                mcp_config["mcpServers"].update(data)
            except Exception as e:
                print_warning(f"Error leyendo template supabase: {e}")

    # 4. Guardar Configuración
    target = CURRENT_DIR / "claude_desktop_config.json"  # Estándar común
    create_backup(target)

    with open(target, "w", encoding="utf-8") as f:
        json.dump(mcp_config, f, indent=2)

    print_success(f"Configuración MCP generada en {target.name}")
    print(
        "👉 IMPORTANTE: Revisa el archivo generado y actualiza las credenciales (USER/PASS/URL)."
    )
    print(
        "👉 Luego copia este contenido a la configuración de tu Agente (Cursor/Claude)."
    )


def scope_feature(args):
    print("\n🔭 SCOPE WIZARD (Generador de Especificaciones)")
    name = input("Nombre de la funcionalidad: ").strip()
    goal = input("Objetivo (User Goal): ").strip()
    flow = input("Flujo paso a paso: ").strip()
    content = f"# SPEC: {name.upper()}\n\n## GOAL\n{goal}\n\n## FLOW\n{flow}"
    target = CURRENT_DIR / "SPECS.md"
    target.write_text(content, encoding="utf-8")
    print_success(f"Especificación guardada en {target.name}")


def deploy_assistant(args):
    target = args.target or input("Destino (aws, vercel, gcp): ").strip()
    print(f"\n☁️  Generando plan de despliegue para {target.upper()}...")
    tpl = TEMPLATES_DIR / "deploy" / f"{target}.md"
    instructions = (
        tpl.read_text(encoding="utf-8")
        if tpl.exists()
        else f"Generate deployment for {target}."
    )
    stack_file = PROJECT_RAPID_DIR / "standards" / "tech-stack.md"
    stack = (
        stack_file.read_text(encoding="utf-8")
        if stack_file.exists()
        else "Unknown Stack"
    )
    prompt = f"# DEPLOYMENT TASK\nTARGET: {target}\nSTACK: {stack}\n\nINSTRUCTIONS:\n{instructions}"
    (CURRENT_DIR / "DEPLOY.md").write_text(prompt, encoding="utf-8")
    print_success("Plan generado en DEPLOY.md")


def add_visual_reference(args):
    source_path = Path(args.path)
    if not source_path.exists():
        print_error(f"La imagen {source_path} no existe.")
    refs_dir = CURRENT_DIR / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)
    dest_path = refs_dir / source_path.name
    shutil.copy(source_path, dest_path)
    meta_file = refs_dir / "VISION_CONTEXT.md"
    description = input(f"Describe qué representa '{source_path.name}': ")
    entry = f"\n- **{source_path.name}**: {description}"
    if not meta_file.exists():
        header = "# 🎨 VISUAL REFERENCES\n"
        meta_file.write_text(header + entry, encoding="utf-8")
    else:
        with open(meta_file, "a", encoding="utf-8") as f:
            f.write(entry)
    print_success(f"Referencia visual agregada.")
    regenerate_context()


def refine_standard(args):
    target = Path(args.file)
    if not target.exists():
        print_error("Archivo no encontrado")
    content = target.read_text(encoding="utf-8")
    prompt = f"ACT AS: Principal Architect. REFINE this document:\n\n{content}"
    print(
        "\n📋 Copia este prompt en tu IA:\n"
        + "-" * 40
        + "\n"
        + prompt
        + "\n"
        + "-" * 40
    )


def show_guide():
    topics = {
        "1": "Rapid OS Basics",
        "2": "Daily Workflow",
        "3": "Scope Wizard",
        "4": "Vision Command",
        "5": "MCP Tools (New)",
    }
    clear_screen()
    print("📘 RAPID OS - MANUAL")
    for k, v in topics.items():
        print(f"{k}) {v}")
    input("\n(Ctrl+C para salir)")


# --- MAIN ENTRY POINT ---


def main():
    parser = argparse.ArgumentParser(
        description="Rapid OS - Context Injection Framework"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Comandos
    init = subparsers.add_parser("init", help="Configurar proyecto")
    init.add_argument("--stack")
    init.add_argument("--archetype")
    subparsers.add_parser("scope", help="Crear Specs")
    deploy = subparsers.add_parser("deploy", help="DevOps")
    deploy.add_argument("target", nargs="?")
    vision = subparsers.add_parser("vision", help="Agregar screenshot")
    vision.add_argument("path")
    refine = subparsers.add_parser("refine", help="Refinar docs")
    refine.add_argument("file")

    # NUEVO COMANDO MCP
    subparsers.add_parser("mcp", help="Configurar Herramientas MCP")

    subparsers.add_parser("guide", help="Ayuda")

    args = parser.parse_args()

    if args.command == "init":
        init_project(args)
    elif args.command == "scope":
        scope_feature(args)
    elif args.command == "deploy":
        deploy_assistant(args)
    elif args.command == "vision":
        add_visual_reference(args)
    elif args.command == "mcp":
        generate_mcp_config(args)  # <--- CONECTADO
    elif args.command == "refine":
        refine_standard(args)
    elif args.command == "guide":
        show_guide()
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operación cancelada por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)

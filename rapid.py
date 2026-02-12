#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import shutil
import argparse
import time
import json
import subprocess
from pathlib import Path

# --- CONFIGURACIÓN GLOBAL ---
RAPID_HOME = Path.home() / ".rapid-os"

# Detect if running from source (local templates)
SCRIPT_DIR = Path(__file__).resolve().parent
if (SCRIPT_DIR / "templates").exists():
    TEMPLATES_DIR = SCRIPT_DIR / "templates"
else:
    TEMPLATES_DIR = RAPID_HOME / "templates"
CURRENT_DIR = Path.cwd()
PROJECT_RAPID_DIR = CURRENT_DIR / ".rapid-os"
CONFIG_FILE = PROJECT_RAPID_DIR / "config.json"


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


def save_project_config(config_data):
    """Guarda la configuración del proyecto"""
    PROJECT_RAPID_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)


def load_project_config():
    """Carga la configuración. Si no existe, devuelve defaults."""
    if not CONFIG_FILE.exists():
        return {"tools": ["cursor", "claude", "antigravity", "vscode"]}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"tools": []}


def check_node_installed():
    """Verifica si npx/node está disponible"""
    try:
        subprocess.run(
            ["npx", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
        return True
    except:
        return False


# --- GENERADORES DE CONTEXTO ---


def generate_cursor_rules(context):
    target = CURRENT_DIR / ".cursorrules"
    create_backup(target)
    content = f"# RAPID OS - SYSTEM CONTEXT\n# DO NOT EDIT. Generated automatically.\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: .cursorrules")


def generate_claude_config(context):
    target = CURRENT_DIR / "CLAUDE.md"
    create_backup(target)
    content = f"# PROJECT MEMORY\n# SOURCE OF TRUTH FOR AI.\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: CLAUDE.md")


def generate_antigravity_config(context):
    antigravity_dir = CURRENT_DIR / ".agent" / "rules"
    antigravity_dir.mkdir(parents=True, exist_ok=True)
    target = antigravity_dir / "constitution.md"
    create_backup(target)
    header = "# PROJECT CONSTITUTION\n# ACTIVATION: ALWAYS_ON\n\n"
    content = header + f"# IMMUTABLE TRUTH FOR GEMINI AGENTS.\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: .agent/rules/constitution.md")


def generate_vscode_instructions(context):
    target = CURRENT_DIR / "INSTRUCTIONS.md"
    create_backup(target)
    content = f"# AI INSTRUCTIONS (COPILOT)\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: INSTRUCTIONS.md")


def regenerate_context():
    """Compila estándares y genera SOLO para las herramientas seleccionadas"""
    standards_dir = PROJECT_RAPID_DIR / "standards"
    full_context = ""

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

    vision_meta = CURRENT_DIR / "references" / "VISION_CONTEXT.md"
    if vision_meta.exists():
        full_context += "\n### 👁️ VISUAL STANDARDS\n" + vision_meta.read_text(
            encoding="utf-8"
        )

    config = load_project_config()
    tools = config.get("tools", [])

    if "cursor" in tools:
        generate_cursor_rules(full_context)
    if "claude" in tools:
        generate_claude_config(full_context)
    if "antigravity" in tools:
        generate_antigravity_config(full_context)
    if "vscode" in tools:
        generate_vscode_instructions(full_context)


# --- COMANDOS PRINCIPALES ---


def init_project(args):
    print_step("Inicializando Rapid OS...")
    standards_dest = PROJECT_RAPID_DIR / "standards"
    standards_dest.mkdir(parents=True, exist_ok=True)

    # 1. Stack
    if not args.stack:
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
        except:
            stack_name = stacks[0]
    else:
        stack_name = args.stack

    # 2. Topología
    topologies_path = TEMPLATES_DIR / "topologies"
    if not topologies_path.exists():
        topologies_path.mkdir(parents=True, exist_ok=True)
    topos = sorted([f.stem for f in topologies_path.glob("*.md")])
    if topos:
        print("\n🏗️  SELECCIONA TOPOLOGÍA:")
        for i, t in enumerate(topos, 1):
            print(f" {i}) {t}")
        try:
            idx = int(input("Opción: ").strip()) - 1
            topo_name = topos[idx] if 0 <= idx < len(topos) else topos[0]
        except:
            topo_name = topos[0]
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
    except:
        pass

    # 4. Agentes
    print("\n🤖 SELECCIONA TUS AGENTES (Separados por coma):")
    print(" 1) Cursor (.cursorrules)")
    print(" 2) Claude Code (CLAUDE.md)")
    print(" 3) Google Antigravity (.agent/rules)")
    print(" 4) VS Code / Copilot (INSTRUCTIONS.md)")
    agent_sel = input("Opción [1]: ").strip()
    selected_tools = []
    if not agent_sel:
        selected_tools = ["cursor"]
    else:
        parts = agent_sel.split(",")
        if "1" in parts:
            selected_tools.append("cursor")
        if "2" in parts:
            selected_tools.append("claude")
        if "3" in parts:
            selected_tools.append("antigravity")
        if "4" in parts:
            selected_tools.append("vscode")

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

    save_project_config({"tools": selected_tools})

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

    regenerate_context()
    print("\n🚀 ¡Rapid OS activo!")


def manage_skills(args):
    """Gestor Híbrido de Skills (Local + Vercel CLI)"""
    action = args.action
    skill_name = args.name

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

        config = load_project_config()
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
        print_error("Ejecuta 'init' primero.")

    topo_content = topo_file.read_text(encoding="utf-8").lower()
    mcp_config = {"mcpServers": {}}

    mcp_config["mcpServers"]["filesystem"] = {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", str(CURRENT_DIR)],
    }

    if "postgres" in topo_content and "supabase" not in topo_content:
        tpl_path = TEMPLATES_DIR / "mcp" / "postgres.json"
        if tpl_path.exists():
            try:
                mcp_config["mcpServers"].update(json.loads(tpl_path.read_text()))
            except:
                pass

    if "supabase" in topo_content:
        tpl_path = TEMPLATES_DIR / "mcp" / "supabase.json"
        if tpl_path.exists():
            try:
                mcp_config["mcpServers"].update(json.loads(tpl_path.read_text()))
            except:
                pass

    # --- RESEARCH TOOLS ---
    config = load_project_config()
    tools = config.get("tools", [])

    if "context7" in tools:
        mcp_config["mcpServers"]["context7"] = {
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp"],
            "env": {"CONTEXT7_API_KEY": "YOUR_API_KEY_HERE"},  # User must fill this
        }
        print_warning(
            "⚠️  Context7 agregado. Recuerda poner tu API KEY en claude_desktop_config.json"
        )

    if "firecrawl" in tools:
        mcp_config["mcpServers"]["firecrawl"] = {
            "command": "npx",
            "args": ["-y", "firecrawl-mcp"],
            "env": {"FIRECRAWL_API_KEY": "YOUR_API_KEY_HERE"},  # User must fill this
        }
        print_warning(
            "⚠️  Firecrawl agregado. Recuerda poner tu API KEY en claude_desktop_config.json"
        )

    target = CURRENT_DIR / "claude_desktop_config.json"
    create_backup(target)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(mcp_config, f, indent=2)
    print_success(f"Configuración MCP: {target.name}")


def scope_feature(args):
    print("\n🔭 SCOPE WIZARD")
    name = input("Nombre funcionalidad: ").strip()
    goal = input("Objetivo: ").strip()
    flow = input("Flujo: ").strip()
    content = f"# SPEC: {name.upper()}\n\n## GOAL\n{goal}\n\n## FLOW\n{flow}"
    (CURRENT_DIR / "SPECS.md").write_text(content, encoding="utf-8")
    print_success("SPECS.md creado")


def deploy_assistant(args):
    target = args.target or input("Target (aws, vercel): ").strip()
    tpl = TEMPLATES_DIR / "deploy" / f"{target}.md"
    instructions = tpl.read_text() if tpl.exists() else f"Deploy to {target}"
    (CURRENT_DIR / "DEPLOY.md").write_text(
        f"# DEPLOY {target}\n{instructions}", encoding="utf-8"
    )
    print_success("DEPLOY.md creado")


def add_visual_reference(args):
    src = Path(args.path)
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
    print(f"Prompt para IA: ACT AS ARCHITECT. REFINE:\n\n{path.read_text()}")


def show_guide():
    print("📘 RAPID OS - COMANDOS")
    print(" init    -> Configurar proyecto")
    print(" skill   -> Instalar capacidades (Local/Vercel)")
    print(" mcp     -> Configurar herramientas BD")
    print(" vision  -> Agregar referencias visuales")
    print(" scope   -> Crear specs")


def main():
    parser = argparse.ArgumentParser(description="Rapid OS")
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser("init")
    init.add_argument("--stack")
    init.add_argument("--archetype")

    skill = subparsers.add_parser("skill")
    skill.add_argument("action", choices=["list", "install", "add"])
    skill.add_argument("name", nargs="?")

    subparsers.add_parser("scope")
    deploy = subparsers.add_parser("deploy")
    deploy.add_argument("target", nargs="?")
    vision = subparsers.add_parser("vision")
    vision.add_argument("path")
    subparsers.add_parser("mcp")
    refine = subparsers.add_parser("refine")
    refine.add_argument("file")
    subparsers.add_parser("guide")

    args = parser.parse_args()

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
    elif args.command == "guide":
        show_guide()
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

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
CONFIG_FILE = PROJECT_RAPID_DIR / "config.json"

# --- UTILIDADES ---
def print_step(msg): print(f"🔹 {msg}")
def print_success(msg): print(f"✅ {msg}")
def print_warning(msg): print(f"⚠️  {msg}")
def print_error(msg): 
    print(f"❌ {msg}")
    sys.exit(1)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def create_backup(file_path):
    """Crea una copia de seguridad con timestamp si el archivo existe"""
    path = Path(file_path)
    if path.exists():
        timestamp = int(time.time())
        backup_path = path.parent / f"{path.name}.{timestamp}.bak"
        shutil.copy(path, backup_path)
        # print_warning(f"Backup creado: {backup_path.name}") # Opcional: comentar para menos ruido

def save_project_config(config_data):
    """Guarda la configuración del proyecto (ej. herramientas seleccionadas)"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2)

def load_project_config():
    """Carga la configuración. Si no existe, devuelve defaults (todo activado)."""
    if not CONFIG_FILE.exists():
        return {"tools": ["cursor", "claude", "antigravity", "vscode"]} # Default: Todo
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"tools": []}

# --- GENERADORES DE CONTEXTO (ADAPTADORES) ---

def generate_cursor_rules(context):
    target = CURRENT_DIR / ".cursorrules"
    create_backup(target)
    content = f"# RAPID OS - SYSTEM CONTEXT\n# DO NOT EDIT. Generated automatically.\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: .cursorrules (Cursor)")

def generate_claude_config(context):
    target = CURRENT_DIR / "CLAUDE.md"
    create_backup(target)
    content = f"# PROJECT MEMORY\n# SOURCE OF TRUTH FOR AI.\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: CLAUDE.md (Claude Code)")

def generate_antigravity_config(context):
    # CORRECCIÓN: Ruta oficial .agent/rules
    antigravity_dir = CURRENT_DIR / ".agent" / "rules"
    antigravity_dir.mkdir(parents=True, exist_ok=True)
    
    target = antigravity_dir / "constitution.md"
    create_backup(target)
    
    header = """# PROJECT CONSTITUTION
# ACTIVATION: ALWAYS_ON
# DESCRIPTION: The core immutable rules and architecture for this project.

"""
    content = header + f"""# IMMUTABLE TRUTH FOR GEMINI AGENTS.
# IF CONFLICTS ARISE, THIS DOCUMENT WINS.

{context}
"""
    target.write_text(content, encoding="utf-8")
    print_success("Generado: .agent/rules/constitution.md (Antigravity)")

def generate_vscode_instructions(context):
    target = CURRENT_DIR / "INSTRUCTIONS.md"
    create_backup(target)
    content = f"# AI INSTRUCTIONS (COPILOT)\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: INSTRUCTIONS.md (VS Code)")

def regenerate_context():
    """Compila estándares y genera SOLO para las herramientas seleccionadas"""
    standards_dir = PROJECT_RAPID_DIR / "standards"
    full_context = ""
    
    # 1. ESTÁNDARES DE TEXTO
    priority = ["tech-stack.md", "topology.md", "security.md", "design.md", "business.md", "coding-rules.md"]
    
    for filename in priority:
        path = standards_dir / filename
        if path.exists():
            full_context += f"\n### 🛑 {filename.replace('.md', '').upper().replace('-', ' ')}\n"
            full_context += path.read_text(encoding='utf-8') + "\n"

    # 2. REFERENCIAS VISUALES
    vision_meta = CURRENT_DIR / "references" / "VISION_CONTEXT.md"
    if vision_meta.exists():
        full_context += "\n### 👁️ VISUAL STANDARDS (SCREENSHOTS)\n"
        full_context += "I have provided screenshots in the `references/` directory.\n"
        full_context += "Use these images as Ground Truth for UI structure, spacing, and colors.\n"
        full_context += vision_meta.read_text(encoding="utf-8")
        full_context += "\n\nINSTRUCTION: Before generating frontend code, ANALYZE these images.\n"
            
    # 3. GENERACIÓN CONDICIONAL
    config = load_project_config()
    tools = config.get("tools", [])

    if "cursor" in tools: generate_cursor_rules(full_context)
    if "claude" in tools: generate_claude_config(full_context)
    if "antigravity" in tools: generate_antigravity_config(full_context)
    if "vscode" in tools: generate_vscode_instructions(full_context)

# --- COMANDOS PRINCIPALES ---

def init_project(args):
    print_step("Inicializando Rapid OS...")
    
    standards_dest = PROJECT_RAPID_DIR / "standards"
    standards_dest.mkdir(parents=True, exist_ok=True)

    # 1. Stack (Sin cambios)
    if not args.stack:
        stacks_path = TEMPLATES_DIR / "stacks"
        if not stacks_path.exists(): print_error("Templates no encontrados.")
        stacks = sorted([f.stem for f in stacks_path.glob("*.md")])
        print("\n🛠  SELECCIONA TECH STACK:")
        for i, s in enumerate(stacks, 1): print(f" {i}) {s}")
        try:
            idx = int(input("Opción: ").strip()) - 1
            stack_name = stacks[idx] if 0 <= idx < len(stacks) else stacks[0]
        except: stack_name = stacks[0]
    else: stack_name = args.stack

    # 2. Topología (Sin cambios)
    topologies_path = TEMPLATES_DIR / "topologies"
    if not topologies_path.exists(): topologies_path.mkdir(parents=True, exist_ok=True)
    topos = sorted([f.stem for f in topologies_path.glob("*.md")])
    if topos:
        print("\n🏗️  SELECCIONA TOPOLOGÍA:")
        for i, t in enumerate(topos, 1): print(f" {i}) {t}")
        try:
            idx = int(input("Opción: ").strip()) - 1
            topo_name = topos[idx] if 0 <= idx < len(topos) else topos[0]
        except: topo_name = topos[0]
        shutil.copy(topologies_path / f"{topo_name}.md", standards_dest / "topology.md")

    # 3. Arquetipo (Sin cambios)
    print("\n📊 SELECCIONA ARQUETIPO:")
    print(" 1) mvp        (Velocidad)")
    print(" 2) corporate  (Seguridad estricta)")
    sel = input("Opción [1]: ").strip()
    archetype = "corporate" if sel == "2" else "mvp"

    # 4. Copia Templates (Sin cambios)
    try:
        shutil.copy(TEMPLATES_DIR / "stacks" / f"{stack_name}.md", standards_dest / "tech-stack.md")
        rules_src = TEMPLATES_DIR / "archetypes" / archetype / "coding-rules.md"
        if rules_src.exists(): shutil.copy(rules_src, standards_dest / "coding-rules.md")
        sec_src = TEMPLATES_DIR / "archetypes" / archetype / "security.md"
        if sec_src.exists(): shutil.copy(sec_src, standards_dest / "security.md")
    except Exception as e: print_warning(f"Advertencia copiando templates base: {e}")

    # 5. Agentes (Sin cambios)
    print("\n🤖 SELECCIONA TUS AGENTES (Separados por coma):")
    print(" 1) Cursor (.cursorrules)")
    print(" 2) Claude Code (CLAUDE.md)")
    print(" 3) Google Antigravity (.agent/rules)")
    print(" 4) VS Code / Copilot (INSTRUCTIONS.md)")
    agent_sel = input("Opción [1]: ").strip()
    selected_tools = []
    if not agent_sel: selected_tools = ["cursor"]
    else:
        parts = agent_sel.split(",")
        if "1" in parts: selected_tools.append("cursor")
        if "2" in parts: selected_tools.append("claude")
        if "3" in parts: selected_tools.append("antigravity")
        if "4" in parts: selected_tools.append("vscode")
    save_project_config({"tools": selected_tools})

    # --- 6. NEGOCIO (LÓGICA INTERACTIVA MEJORADA) ---
    print("\n--- CONFIGURACIÓN DE NEGOCIO ---")
    
    biz_templates_path = TEMPLATES_DIR / "business"
    # Verificar y crear si no existe
    if not biz_templates_path.exists(): 
        biz_templates_path.mkdir(parents=True, exist_ok=True)
    
    biz_files = sorted([f.stem for f in biz_templates_path.glob("*.md")])
    biz_content = ""

    # CASO A: No hay templates (Carpeta vacía o nueva)
    if not biz_files:
        print("ℹ️  No se encontraron plantillas de negocio guardadas.")
        print("¿Deseas importar un archivo Markdown con tus reglas ahora? (Recomendado)")
        if input("Importar archivo [Y/n]: ").lower() != 'n':
            path_str = input("📂 Arrastra el archivo aquí o escribe la ruta: ").strip().replace("'", "").replace('"', '')
            local_path = Path(path_str)
            if local_path.exists() and local_path.is_file():
                biz_content = local_path.read_text(encoding="utf-8")
                print_success(f"Reglas importadas desde: {local_path.name}")
                
                # Preguntar si quiere guardarlo como template para el futuro
                if input("¿Guardar como plantilla para futuros proyectos? [y/N]: ").lower() == 'y':
                    tpl_name = input("Nombre de la plantilla (ej. saas-b2b): ").strip()
                    (biz_templates_path / f"{tpl_name}.md").write_text(biz_content, encoding="utf-8")
                    print_success("¡Plantilla guardada!")
            else:
                print_error("El archivo no existe. Pasando a modo manual...")
                # Fallback a manual si falla la importación
                print("(Escribe las reglas clave a continuación)")
                rules = input("> ")
                if rules: biz_content = f"# BUSINESS RULES\n{rules}"
        else:
            # Usuario decidió no importar
            print("Escribe las reglas clave manualmente:")
            rules = input("> ")
            if rules: biz_content = f"# BUSINESS RULES\n{rules}"

    # CASO B: Sí hay templates
    else:
        print("¿Cómo quieres cargar las Reglas de Negocio?")
        print(" 1) Escribir manualmente ahora")
        print(" 2) Importar desde ruta de archivo local")
        print(" --- PLANTILLAS ---")
        for i, b in enumerate(biz_files, 1):
            print(f" {i + 2}) {b}")
            
        opcion = input("Opción [1]: ").strip()
        
        if opcion == "2":
            path_str = input("Ruta del archivo .md: ").strip().replace("'", "").replace('"', '')
            local_path = Path(path_str)
            if local_path.exists():
                biz_content = local_path.read_text(encoding="utf-8")
                print_success(f"Importado: {local_path.name}")
            else: print_error("Archivo no encontrado.")
            
        elif opcion.isdigit() and int(opcion) > 2:
            idx = int(opcion) - 3
            if 0 <= idx < len(biz_files):
                tpl_name = biz_files[idx]
                biz_content = (biz_templates_path / f"{tpl_name}.md").read_text(encoding="utf-8")
                print_success(f"Usando plantilla: {tpl_name}")
                
        if (opcion == "1" or not biz_content) and not (opcion.isdigit() and int(opcion) > 2):
            rules = input("Escribe las reglas clave: ")
            if rules: biz_content = f"# BUSINESS RULES\n{rules}"

    # Guardar archivo final
    if biz_content:
        (standards_dest / "business.md").write_text(biz_content, encoding="utf-8")

    regenerate_context()
    print("\n🚀 ¡Rapid OS activo!")

def generate_mcp_config(args):
    """Genera la configuración de herramientas MCP"""
    print_step("Analizando Topología para Herramientas MCP...")
    topo_file = PROJECT_RAPID_DIR / "standards" / "topology.md"
    if not topo_file.exists(): print_error("Ejecuta 'rapid init' primero.")
    
    topo_content = topo_file.read_text(encoding="utf-8").lower()
    mcp_config = {"mcpServers": {}}
    
    # Filesystem
    mcp_config["mcpServers"]["filesystem"] = {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", str(CURRENT_DIR)]
    }

    # DBs
    if "postgres" in topo_content and "supabase" not in topo_content:
        tpl_path = TEMPLATES_DIR / "mcp" / "postgres.json"
        if tpl_path.exists():
            try:
                data = json.loads(tpl_path.read_text(encoding="utf-8"))
                mcp_config["mcpServers"].update(data)
                print_step("✅ Postgres detectado.")
            except: pass

    if "supabase" in topo_content:
        tpl_path = TEMPLATES_DIR / "mcp" / "supabase.json"
        if tpl_path.exists():
            try:
                data = json.loads(tpl_path.read_text(encoding="utf-8"))
                mcp_config["mcpServers"].update(data)
                print_step("✅ Supabase detectado.")
            except: pass

    target = CURRENT_DIR / "claude_desktop_config.json"
    create_backup(target)
    with open(target, "w", encoding="utf-8") as f: json.dump(mcp_config, f, indent=2)
    print_success(f"Configuración MCP generada en {target.name}")

# ... (Las funciones scope_feature, deploy_assistant, add_visual_reference, refine_standard, show_guide se mantienen igual que en la v1.3) ...
# Para ahorrar espacio, asumo que las copias de la versión anterior. 
# Si necesitas que las repita, dímelo.
# Solo asegúrate de copiar 'scope_feature' hacia abajo del script v1.3 anterior.

# --- RESTO DEL SCRIPT (Scope, Deploy, Vision, Main) ---
# Copia aquí las funciones: scope_feature, deploy_assistant, add_visual_reference, refine_standard, show_guide, main
# tal cual estaban en el script anterior, no han cambiado su lógica interna.

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
    instructions = tpl.read_text(encoding="utf-8") if tpl.exists() else f"Generate deployment for {target}."
    stack_file = PROJECT_RAPID_DIR / "standards" / "tech-stack.md"
    stack = stack_file.read_text(encoding="utf-8") if stack_file.exists() else "Unknown Stack"
    prompt = f"# DEPLOYMENT TASK\nTARGET: {target}\nSTACK: {stack}\n\nINSTRUCTIONS:\n{instructions}"
    (CURRENT_DIR / "DEPLOY.md").write_text(prompt, encoding="utf-8")
    print_success("Plan generado en DEPLOY.md")

def add_visual_reference(args):
    source_path = Path(args.path)
    if not source_path.exists(): print_error(f"La imagen {source_path} no existe.")
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
        with open(meta_file, "a", encoding="utf-8") as f: f.write(entry)
    print_success(f"Referencia visual agregada.")
    regenerate_context()

def refine_standard(args):
    target = Path(args.file)
    if not target.exists(): print_error("Archivo no encontrado")
    content = target.read_text(encoding="utf-8")
    prompt = f"ACT AS: Principal Architect. REFINE this document:\n\n{content}"
    print("\n📋 Copia este prompt en tu IA:\n" + "-"*40 + "\n" + prompt + "\n" + "-"*40)

def show_guide():
    topics = {"1": "Rapid OS Basics", "2": "Daily Workflow", "3": "Scope Wizard", "4": "Vision Command", "5": "MCP Tools"}
    clear_screen()
    print("📘 RAPID OS - MANUAL")
    for k,v in topics.items(): print(f"{k}) {v}")
    input("\n(Ctrl+C para salir)")

def main():
    parser = argparse.ArgumentParser(description="Rapid OS - Context Injection Framework")
    subparsers = parser.add_subparsers(dest="command")
    
    init = subparsers.add_parser("init", help="Configurar proyecto")
    init.add_argument("--stack"); init.add_argument("--archetype")
    subparsers.add_parser("scope", help="Crear Specs")
    deploy = subparsers.add_parser("deploy", help="DevOps")
    deploy.add_argument("target", nargs="?")
    vision = subparsers.add_parser("vision", help="Agregar screenshot")
    vision.add_argument("path")
    subparsers.add_parser("mcp", help="Configurar MCP")
    refine = subparsers.add_parser("refine", help="Refinar docs")
    refine.add_argument("file")
    subparsers.add_parser("guide", help="Ayuda")

    args = parser.parse_args()

    if args.command == "init": init_project(args)
    elif args.command == "scope": scope_feature(args)
    elif args.command == "deploy": deploy_assistant(args)
    elif args.command == "vision": add_visual_reference(args)
    elif args.command == "mcp": generate_mcp_config(args)
    elif args.command == "refine": refine_standard(args)
    elif args.command == "guide": show_guide()
    else: parser.print_help()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
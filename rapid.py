#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import shutil
import argparse
import time
from pathlib import Path

# --- CONFIGURACIÓN GLOBAL ---
RAPID_HOME = Path.home() / ".rapid-os"
TEMPLATES_DIR = RAPID_HOME / "templates"
CURRENT_DIR = Path.cwd()
PROJECT_RAPID_DIR = CURRENT_DIR / ".rapid-os"

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
    """Adaptador para Google Antigravity (Spec-Driven Development)"""
    # Crea la estructura requerida: .specify/memory/constitution.md
    antigravity_dir = CURRENT_DIR / ".specify" / "memory"
    antigravity_dir.mkdir(parents=True, exist_ok=True)
    
    target = antigravity_dir / "constitution.md"
    create_backup(target)
    
    content = f"""# PROJECT CONSTITUTION (NIVEL 4)
# IMMUTABLE TRUTH FOR GEMINI AGENTS.
# IF CONFLICTS ARISE, THIS DOCUMENT WINS.

{context}
"""
    target.write_text(content, encoding="utf-8")
    print_success("Generado: .specify/memory/constitution.md (Antigravity)")

def generate_vscode_instructions(context):
    """Adaptador para VS Code / GitHub Copilot"""
    target = CURRENT_DIR / "INSTRUCTIONS.md"
    create_backup(target)
    content = f"# AI INSTRUCTIONS (COPILOT)\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: INSTRUCTIONS.md (VS Code)")

def regenerate_context():
    """Compila todos los estándares en un solo bloque de texto coherente"""
    standards_dir = PROJECT_RAPID_DIR / "standards"
    full_context = ""
    
    # ORDEN DE PRIORIDAD LÓGICA (Critico para que la IA obedezca)
    # 1. Stack (Qué usar)
    # 2. Seguridad (Qué NO hacer)
    # 3. Diseño (Cómo se ve - Nuevo soporte Creative)
    # 4. Negocio (Reglas)
    # 5. Estilo (Cómo se escribe)
    priority = ["tech-stack.md", "security.md", "design.md", "business.md", "coding-rules.md"]
    
    for filename in priority:
        path = standards_dir / filename
        if path.exists():
            full_context += f"\n### 🛑 {filename.replace('.md', '').upper().replace('-', ' ')}\n"
            full_context += path.read_text(encoding='utf-8') + "\n"
            
    # Inyectar en todos los editores
    generate_cursor_rules(full_context)
    generate_claude_config(full_context)
    generate_antigravity_config(full_context)
    generate_vscode_instructions(full_context)

# --- COMANDOS PRINCIPALES ---

def init_project(args):
    print_step("Inicializando Rapid OS...")
    
    # 1. Preparar carpetas
    standards_dest = PROJECT_RAPID_DIR / "standards"
    standards_dest.mkdir(parents=True, exist_ok=True)

    # 2. Selección de Stack (Tecnología)
    if not args.stack:
        stacks_path = TEMPLATES_DIR / "stacks"
        if not stacks_path.exists(): print_error("Templates no encontrados. Reinstala Rapid OS.")
        
        stacks = sorted([f.stem for f in stacks_path.glob("*.md")])
        print("\n🛠  SELECCIONA TECH STACK:")
        for i, s in enumerate(stacks, 1): print(f" {i}) {s}")
        
        sel = input("Opción: ").strip()
        try: stack_name = stacks[int(sel)-1]
        except: stack_name = stacks[0]
    else:
        stack_name = args.stack

    # 3. Selección de Arquetipo (Comportamiento)
    if not args.archetype:
        print("\n📊 SELECCIONA ARQUETIPO:")
        print(" 1) mvp        (Velocidad, deuda técnica aceptable)")
        print(" 2) corporate  (Seguridad estricta, tests obligatorios)")
        sel = input("Opción [1]: ").strip()
        archetype = "corporate" if sel == "2" else "mvp"
    else:
        archetype = args.archetype

    # 4. Copia de Templates Base
    try:
        # Copiar Stack
        shutil.copy(TEMPLATES_DIR / "stacks" / f"{stack_name}.md", standards_dest / "tech-stack.md")
        # Copiar Reglas de Código
        shutil.copy(TEMPLATES_DIR / "archetypes" / archetype / "coding-rules.md", standards_dest / "coding-rules.md")
        # Copiar Seguridad (Si existe para el arquetipo)
        sec_src = TEMPLATES_DIR / "archetypes" / archetype / "security.md"
        if sec_src.exists(): shutil.copy(sec_src, standards_dest / "security.md")
    except Exception as e:
        print_error(f"Error copiando templates: {e}")

    # 5. Entrevista de Negocio (Scope)
    print("\n--- CONFIGURACIÓN DE NEGOCIO ---")
    if input("¿Definir reglas de negocio permanentes? (ej. Monetización, GDPR) [y/N]: ").lower() == 'y':
        rules = input("Escribe las reglas clave: ")
        (standards_dest / "business.md").write_text(f"# BUSINESS RULES\n{rules}", encoding="utf-8")

    # 6. Generación Final
    regenerate_context()
    print("\n🚀 ¡Rapid OS activo! Tu IA ahora es un Senior Engineer.")

def scope_feature(args):
    """Generador interactivo de PRD/Specs"""
    print("\n🔭 SCOPE WIZARD (Generador de Especificaciones)")
    name = input("Nombre de la funcionalidad: ").strip()
    goal = input("Objetivo (User Goal): ").strip()
    flow = input("Flujo paso a paso: ").strip()
    
    content = f"# SPEC: {name.upper()}\n\n## GOAL\n{goal}\n\n## FLOW\n{flow}"
    
    target = CURRENT_DIR / "SPECS.md"
    target.write_text(content, encoding="utf-8")
    print_success(f"Especificación guardada en {target.name}")
    print("👉 Instrucción para la IA: 'Implementa lo que dice en SPECS.md'")

def deploy_assistant(args):
    """Generador de Estrategia DevOps"""
    target = args.target or input("Destino (aws, vercel, gcp, azure): ").strip()
    print(f"\n☁️  Generando plan de despliegue para {target.upper()}...")
    
    # Busca template específico o usa genérico
    tpl = TEMPLATES_DIR / "deploy" / f"{target}.md"
    instructions = tpl.read_text(encoding="utf-8") if tpl.exists() else f"Generate comprehensive deployment configuration for {target}."
    
    # Lee el stack actual para dar contexto
    stack_file = PROJECT_RAPID_DIR / "standards" / "tech-stack.md"
    stack = stack_file.read_text(encoding="utf-8") if stack_file.exists() else "Unknown Stack"
    
    prompt = f"# DEPLOYMENT TASK\nTARGET: {target}\nCURRENT STACK: {stack}\n\nINSTRUCTIONS:\n{instructions}"
    (CURRENT_DIR / "DEPLOY.md").write_text(prompt, encoding="utf-8")
    print_success("Plan generado en DEPLOY.md")

def refine_standard(args):
    """Usa IA para auditar documentos"""
    target = Path(args.file)
    if not target.exists(): print_error("Archivo no encontrado")
    
    content = target.read_text(encoding="utf-8")
    prompt = f"ACT AS: Principal Architect. REFINE this document. Make rules STRICT and NEGATIVE (what NOT to do):\n\n{content}"
    
    print("\n📋 Copia este prompt en tu IA para mejorar el documento:")
    print("-" * 40)
    print(prompt)
    print("-" * 40)

def show_guide():
    """Manual Interactivo"""
    topics = {
        "1": "Qué es Rapid OS y por qué usarlo",
        "2": "Flujo Diario (Cursor, Claude, Antigravity)",
        "3": "Comando 'scope' (Specs complejas)",
        "4": "Comando 'deploy' (DevOps)"
    }
    clear_screen()
    print("📘 RAPID OS - MANUAL")
    for k,v in topics.items(): print(f"{k}) {v}")
    print("\n(Ctrl+C para salir)")
    input("Selecciona opción: ")

# --- MAIN ENTRY POINT ---

def main():
    parser = argparse.ArgumentParser(description="Rapid OS - Context Injection Framework")
    subparsers = parser.add_subparsers(dest="command")
    
    # init
    init = subparsers.add_parser("init", help="Configurar proyecto")
    init.add_argument("--stack"); init.add_argument("--archetype")
    
    # scope
    subparsers.add_parser("scope", help="Crear especificación funcional")
    
    # deploy
    deploy = subparsers.add_parser("deploy", help="Asistente de despliegue")
    deploy.add_argument("target", nargs="?")
    
    # refine
    refine = subparsers.add_parser("refine", help="Mejorar estándares con IA")
    refine.add_argument("file")
    
    # guide
    subparsers.add_parser("guide", help="Ayuda interactiva")

    args = parser.parse_args()

    if args.command == "init": init_project(args)
    elif args.command == "scope": scope_feature(args)
    elif args.command == "deploy": deploy_assistant(args)
    elif args.command == "refine": refine_standard(args)
    elif args.command == "guide": show_guide()
    else: parser.print_help()

if __name__ == "__main__":
    main()
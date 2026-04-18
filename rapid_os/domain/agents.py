from rapid_os.core.filesystem import create_backup
from rapid_os.core.output import print_success
from rapid_os.core.paths import CURRENT_DIR


def generate_cursor_rules(context, current_dir=CURRENT_DIR):
    target = current_dir / ".cursorrules"
    create_backup(target)
    content = f"# RAPID OS - SYSTEM CONTEXT\n# DO NOT EDIT. Generated automatically.\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: .cursorrules")


def generate_claude_config(context, current_dir=CURRENT_DIR):
    target = current_dir / "CLAUDE.md"
    create_backup(target)
    content = f"# PROJECT MEMORY\n# SOURCE OF TRUTH FOR AI.\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: CLAUDE.md")


def generate_antigravity_config(context, current_dir=CURRENT_DIR):
    antigravity_dir = current_dir / ".agent" / "rules"
    antigravity_dir.mkdir(parents=True, exist_ok=True)
    target = antigravity_dir / "constitution.md"
    create_backup(target)
    header = "# PROJECT CONSTITUTION\n# ACTIVATION: ALWAYS_ON\n\n"
    content = header + f"# IMMUTABLE TRUTH FOR GEMINI AGENTS.\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: .agent/rules/constitution.md")


def generate_vscode_instructions(context, current_dir=CURRENT_DIR):
    target = current_dir / "INSTRUCTIONS.md"
    create_backup(target)
    content = f"# AI INSTRUCTIONS (COPILOT)\n\n{context}"
    target.write_text(content, encoding="utf-8")
    print_success("Generado: INSTRUCTIONS.md")


def generate_agent_contexts(context, tools, current_dir=CURRENT_DIR):
    if "cursor" in tools:
        generate_cursor_rules(context, current_dir)
    if "claude" in tools:
        generate_claude_config(context, current_dir)
    if "antigravity" in tools:
        generate_antigravity_config(context, current_dir)
    if "vscode" in tools:
        generate_vscode_instructions(context, current_dir)


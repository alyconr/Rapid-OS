from rapid_os.core.paths import CURRENT_DIR, PROJECT_RAPID_DIR


STANDARDS_PRIORITY = [
    "tech-stack.md",
    "topology.md",
    "security.md",
    "design.md",
    "business.md",
    "coding-rules.md",
]


def compose_project_context(
    project_rapid_dir=PROJECT_RAPID_DIR,
    current_dir=CURRENT_DIR,
    priority=STANDARDS_PRIORITY,
):
    """Compila estandares y referencias visuales en el contexto de agentes."""
    standards_dir = project_rapid_dir / "standards"
    full_context = ""

    for filename in priority:
        path = standards_dir / filename
        if path.exists():
            full_context += (
                f"\n### 🛑 {filename.replace('.md', '').upper().replace('-', ' ')}\n"
            )
            full_context += path.read_text(encoding="utf-8") + "\n"

    vision_meta = current_dir / "references" / "VISION_CONTEXT.md"
    if vision_meta.exists():
        full_context += "\n### 👁️ VISUAL STANDARDS\n" + vision_meta.read_text(
            encoding="utf-8"
        )

    return full_context


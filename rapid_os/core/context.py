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
    templates_dir=None,
):
    """Compila estandares, documentos del onboarding y referencias visuales en el contexto de agentes."""
    # Lazy: the adapters import this package.
    from rapid_os.adapters.project_docs import load_project_docs
    from rapid_os.domain.setup import SETUP_DOC_ORDER

    standards_dir = project_rapid_dir / "standards"
    full_context = ""
    docs = load_project_docs(current_dir, project_rapid_dir, templates_dir)

    for filename in priority:
        if filename == "business.md" and docs.business_supersedes_legacy:
            continue  # doc.business wins over the legacy standard
        path = standards_dir / filename
        if path.exists():
            full_context += (
                f"\n### 🛑 {filename.replace('.md', '').upper().replace('-', ' ')}\n"
            )
            full_context += path.read_text(encoding="utf-8") + "\n"

    for doc_id in SETUP_DOC_ORDER:
        doc = docs.managed.get(doc_id) or docs.skipped.get(doc_id)
        if doc is not None:
            full_context += f"\n### 📄 {doc.bank.title.upper()}\n{doc.content}\n"

    vision_meta = current_dir / "references" / "VISION_CONTEXT.md"
    if vision_meta.exists():
        full_context += "\n### 👁️ VISUAL STANDARDS\n" + vision_meta.read_text(
            encoding="utf-8"
        )

    return full_context


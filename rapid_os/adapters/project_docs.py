"""Reads the onboarding documents of a project: what the agent will see, with its provenance.

Shared by `rapid context` (context sources), the agent files (`compose_project_context`) and
`rapid validate`, so the three always agree. Read-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rapid_os.adapters.setup_store import read_setup_file
from rapid_os.core.filesystem import ensure_path_within_root
from rapid_os.domain.catalog import CatalogError, SetupDocBank, load_setup_doc_banks
from rapid_os.domain.project_docs import (
    is_managed,
    is_unconfirmed_draft,
    parse_doc_frontmatter,
    skipped_line,
    with_provenance,
)
from rapid_os.domain.setup import SETUP_DOC_ORDER, SetupState


@dataclass(frozen=True)
class ManagedDoc:
    """A document that carries `rapid-doc: <id>` frontmatter."""

    id: str
    bank: SetupDocBank
    path: Path
    fields: dict
    body: str

    @property
    def source(self) -> str:
        return self.fields["source"]

    @property
    def unconfirmed_draft(self) -> bool:
        return is_unconfirmed_draft(self.fields)

    @property
    def content(self) -> str:
        """Body as the agent sees it (unconfirmed drafts under the assumptions banner)."""
        return with_provenance(self.fields, self.body)


@dataclass(frozen=True)
class SkippedDoc:
    id: str
    bank: SetupDocBank

    @property
    def content(self) -> str:
        return skipped_line(self.bank.title)


@dataclass(frozen=True)
class ProjectDocs:
    banks: dict[str, SetupDocBank] = field(default_factory=dict)
    managed: dict[str, ManagedDoc] = field(default_factory=dict)
    skipped: dict[str, SkippedDoc] = field(default_factory=dict)
    setup_state: SetupState | None = None
    setup_error: str | None = None

    @property
    def business_supersedes_legacy(self) -> bool:
        return "business" in self.managed


def load_banks(templates_dir: Path | None) -> dict[str, SetupDocBank]:
    """Question banks, or `{}` when the templates do not carry them (the docs feature is then off)."""
    if templates_dir is None:
        from rapid_os.core.paths import TEMPLATES_DIR as templates_dir
    try:
        return load_setup_doc_banks(templates_dir)
    except (CatalogError, OSError):
        return {}


def _read_managed(project_root: Path, doc_id: str, bank: SetupDocBank) -> ManagedDoc | None:
    candidate = project_root / bank.file
    try:
        contained = ensure_path_within_root(project_root, candidate)
        if not contained.is_file():
            return None
        fields, body = parse_doc_frontmatter(contained.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeDecodeError):
        return None
    if not is_managed(fields, doc_id) or not body.strip():
        return None
    return ManagedDoc(doc_id, bank, contained, fields, body)


def _legacy_business_has_content(rapid_dir: Path) -> bool:
    legacy = rapid_dir / "standards" / "business.md"
    try:
        return legacy.is_file() and bool(legacy.read_text(encoding="utf-8").strip())
    except (OSError, UnicodeDecodeError):
        return False


def load_project_docs(
    project_root: Path, rapid_dir: Path, templates_dir: Path | None = None
) -> ProjectDocs:
    """Managed documents, skipped ones (from `setup.json`) and the setup state, tolerantly."""
    banks = load_banks(templates_dir)
    if not banks:
        return ProjectDocs()
    state, error = read_setup_file(rapid_dir)
    managed = {}
    skipped = {}
    for doc_id in SETUP_DOC_ORDER:
        bank = banks.get(doc_id)
        if bank is None:
            continue
        doc = _read_managed(Path(project_root), doc_id, bank)
        if doc is not None:
            managed[doc_id] = doc
        elif state is not None and state.doc(doc_id).status == "skipped":
            # An existing standards/business.md still speaks for the business rules.
            if not (doc_id == "business" and _legacy_business_has_content(rapid_dir)):
                skipped[doc_id] = SkippedDoc(doc_id, bank)
    return ProjectDocs(banks, managed, skipped, state, error)


def legacy_business_source(project_root: Path, rapid_dir: Path, bank: SetupDocBank) -> str | None:
    """Project-relative path of a legacy `standards/business.md` that can be imported, else None.

    Importable means: it has content and `docs/BUSINESS_RULES.md` does not exist yet.
    """
    project_root = Path(project_root)
    if (project_root / bank.file).exists() or not _legacy_business_has_content(rapid_dir):
        return None
    legacy = Path(rapid_dir) / "standards" / "business.md"
    try:
        return legacy.relative_to(project_root).as_posix()
    except ValueError:
        return legacy.as_posix()

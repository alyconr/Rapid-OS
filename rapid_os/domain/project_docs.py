"""Onboarding documents (brief, business, data-model, architecture): frontmatter, provenance, checks.

Pure: no I/O. A document counts as managed only when its frontmatter says `rapid-doc: <id>`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from rapid_os.domain.catalog import SetupDocBank

DOC_FRONTMATTER_KEY = "rapid-doc"
DOC_SOURCES = ("provided", "drafted")
DRAFT_BANNER = "> Supuestos redactados por el agente, no confirmados por la persona."

_FRONTMATTER_RE = re.compile(r"\A---\n(?:(?P<header>.*?)\n)?---[ \t]*(?:\n|\Z)", re.DOTALL)
_H2_RE = re.compile(r"^## (?!#)(.*?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class DocIssue:
    code: str
    message: str


def parse_doc_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split `---` frontmatter from the body. Without valid frontmatter: ({}, text)."""
    normalized = text.replace("\r\n", "\n")
    match = _FRONTMATTER_RE.match(normalized)
    if match is None:
        return {}, normalized
    fields: dict[str, str] = {}
    for line in (match.group("header") or "").splitlines():
        key, colon, value = line.partition(":")
        if colon:
            fields[key.strip()] = value.strip().strip("\"'")
    return fields, normalized[match.end():]


def is_managed(fields: Mapping[str, str], doc_id: str) -> bool:
    return fields.get(DOC_FRONTMATTER_KEY) == doc_id and fields.get("source") in DOC_SOURCES


def is_unconfirmed_draft(fields: Mapping[str, str]) -> bool:
    """A draft written by the agent that no person has confirmed."""
    return fields.get("source") == "drafted" and fields.get("status") != "confirmed"


def with_provenance(fields: Mapping[str, str], body: str) -> str:
    """The text the agent sees: unconfirmed drafts go under the assumptions banner."""
    body = body.strip()
    if is_unconfirmed_draft(fields):
        return f"{DRAFT_BANNER}\n\n{body}"
    return body


def skipped_line(title: str) -> str:
    return f"No hay {title} definido: pregunta, no inventes."


def normalize_body(text: str) -> str:
    """Body without frontmatter and with whitespace collapsed, for comparing two documents."""
    _fields, body = parse_doc_frontmatter(text)
    return " ".join(body.split())


def validate_doc_body(body: str, bank: SetupDocBank) -> tuple[DocIssue, ...]:
    """RAPID1403 for each missing required section, RAPID1404 when the body is too long."""
    headings = {match.group(1).strip().lower() for match in _H2_RE.finditer(body)}
    issues = []
    for section in bank.required_sections:
        if not any(title.strip().lower() in headings for title in section.titles):
            issues.append(
                DocIssue(
                    "RAPID1403",
                    f"Document '{bank.id}' ({bank.file}) is missing the required section "
                    f"'{section.id}' (a '## ' heading titled {' or '.join(repr(t) for t in section.titles)}).",
                )
            )
    if len(body) > bank.max_chars:
        issues.append(
            DocIssue(
                "RAPID1404",
                f"Document '{bank.id}' ({bank.file}) has {len(body)} characters; the limit is {bank.max_chars}.",
            )
        )
    return tuple(issues)

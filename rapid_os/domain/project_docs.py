"""Onboarding documents (brief, business, data-model, architecture): frontmatter, provenance, checks.

Pure: no I/O. A document counts as managed only when its frontmatter says `rapid-doc: <id>`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Mapping

from rapid_os.domain.catalog import SetupDocBank

DOC_FRONTMATTER_KEY = "rapid-doc"
DOC_SOURCES = ("provided", "drafted")
DRAFT_BANNER = "> Supuestos redactados por el agente, no confirmados por la persona."

_FRONTMATTER_RE = re.compile(r"\A---\n(?:(?P<header>.*?)\n)?---[ \t]*(?:\n|\Z)", re.DOTALL)
_RAW_FRONTMATTER_RE = re.compile(
    r"\A---\r?\n(?:(?P<header>.*?)\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.DOTALL
)
_STATUS_LINE_RE = re.compile(r"^status:[^\r\n]*", re.MULTILINE)
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
    return f"{title}: sin definir. Pregunta, no inventes."


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


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n")


def body_sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def prepare_body(text: str) -> str:
    """The body as it is stored: LF newlines and exactly one final newline; nothing else changes."""
    body = normalize_newlines(text)
    return body.rstrip("\n") + "\n" if body.strip() else ""


def render_managed_doc(doc_id: str, source: str, status: str, body: str) -> str:
    """Frontmatter (`rapid-doc`, `source`, `status`, `sha256` of the body) followed by the body."""
    header = (
        f"---\n{DOC_FRONTMATTER_KEY}: {doc_id}\nsource: {source}\nstatus: {status}\n"
        f"sha256: {body_sha256(body)}\n---\n"
    )
    return header + body


def with_doc_status(text: str, status: str) -> str:
    """Change only the `status:` frontmatter line; the body stays byte for byte."""
    match = _RAW_FRONTMATTER_RE.match(text)
    if match is None or match.group("header") is None:
        raise ValueError("the document has no frontmatter to update.")
    header = match.group("header")
    if _STATUS_LINE_RE.search(header):
        header = _STATUS_LINE_RE.sub(f"status: {status}", header, count=1)
    else:
        header = f"{header}\nstatus: {status}"
    return text[: match.start("header")] + header + text[match.end("header"):]


_STORY_RE = re.compile(r"^[ \t]*[-*][ \t]+\[ \][ \t]+([A-Za-z]+-?\d+)[ \t]*[:.\-–][ \t]*(\S.*?)[ \t]*$")
_DONE_STORY_RE = re.compile(r"^[ \t]*[-*][ \t]+\[[xX]\]")


def open_stories(body: str, bank: SetupDocBank) -> tuple[dict[str, str], ...]:
    """Unchecked stories (`- [ ] H001: text`) of the brief's stories section, in order.

    Only the section the bank calls `stories` counts; checked stories (`- [x]`) are skipped.
    """
    titles = {
        title.strip().lower()
        for section in bank.required_sections
        if section.id == "stories"
        for title in section.titles
    }
    stories: list[dict[str, str]] = []
    inside = False
    for line in normalize_newlines(body).split("\n"):
        heading = _H2_RE.match(line)
        if heading is not None:
            inside = heading.group(1).strip().lower() in titles
            continue
        if not inside or _DONE_STORY_RE.match(line):
            continue
        match = _STORY_RE.match(line)
        if match is not None:
            stories.append({"id": match.group(1), "text": match.group(2)})
    return tuple(stories)

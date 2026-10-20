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


_LOST_CHAR_RE = re.compile(r"[^\W\d_]\?[^\W\d_]|(?<![\w¿?])\?[^\W\d_]")
_NOT_PROSE_RE = re.compile(r"```.*?```|`[^`\n]*`|\S+://\S+", re.DOTALL)
LOST_CHARACTERS_MESSAGE = (
    "El texto perdió caracteres (acentos o ñ convertidos en '?'); "
    "envíalo con --file desde un archivo UTF-8"
)


def has_lost_characters(body: str) -> bool:
    """A '?' between two letters ("vac?os") or opening a word ("?xito"): what a non-UTF-8 pipe
    leaves of "vacíos" and "éxito". A question mark that closes a word ("¿Listo?") is not flagged.

    Code and URLs are left out, where `a?b` is legitimate (a query string, a regex).
    """
    return _LOST_CHAR_RE.search(_NOT_PROSE_RE.sub(" ", body)) is not None


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


_STORY_LINE_RE = re.compile(r"^([ \t]*[-*][ \t]+\[)([ xX])(\][ \t]+)([A-Za-z]+-?\d+)(?=[ \t]*[:.\-–])")
_SHA_LINE_RE = re.compile(r"^sha256:[^\r\n]*", re.MULTILINE)


def mark_story_done(text: str, bank: SetupDocBank, story_id: str) -> tuple[str, str, str]:
    """Tick one story of the brief: `- [ ] H001: ...` becomes `- [x] H001: ...`, nothing else.

    `text` is the whole document. Only the stories section counts, and the story id is matched
    without regard to case. Returns `(new_text, outcome, written_id)`: outcome is `marked`,
    `already_done` or `not_found`, and `new_text` is `text` unless it was marked, in which case
    the frontmatter `sha256` follows the new body (`source` and `status` stay as they are).
    """
    titles = {
        title.strip().lower()
        for section in bank.required_sections
        if section.id == "stories"
        for title in section.titles
    }
    frontmatter = _RAW_FRONTMATTER_RE.match(text)
    start = frontmatter.end() if frontmatter is not None else 0
    lines = text[start:].splitlines(keepends=True)
    inside = False
    for index, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        heading = _H2_RE.match(line)
        if heading is not None:
            inside = heading.group(1).strip().lower() in titles
            continue
        match = _STORY_LINE_RE.match(line) if inside else None
        if match is None or match.group(4).lower() != story_id.strip().lower():
            continue
        if match.group(2) != " ":
            return text, "already_done", match.group(4)
        lines[index] = f"{match.group(1)}x{line[match.end(2):]}{raw[len(line):]}"
        body = "".join(lines)
        header = text[:start]
        if frontmatter is not None and frontmatter.group("header") is not None:
            sha_line = f"sha256: {body_sha256(normalize_newlines(body))}"
            if _SHA_LINE_RE.search(header):
                header = _SHA_LINE_RE.sub(sha_line, header, count=1)
        return header + body, "marked", match.group(4)
    return text, "not_found", story_id.strip()

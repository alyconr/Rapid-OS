"""The stamp of a standard Rapid OS writes (H-79), like the one of the security workflows (H-78).

`.rapid-os/standards/security.md` and `coding-rules.md` come from templates that change between versions
(rc.4 added the supply-chain rules for pnpm and uv). Nothing regenerated them in a project onboarded by an
earlier version, so the agent never saw the new rules. Rapid OS now ends each of those files with

    <!-- rapid-os-standard: <name> sha256=<digest of the body above> -->

so `rapid doctor` can tell a standard this version would write differently and nobody edited (replace it)
from one the person edited or that carries no stamp (write the new one beside it as `.new`). The stamp is
an HTML comment: Markdown renderers hide it, and the agent context leaves it out.
"""

from __future__ import annotations

import hashlib
import re

STANDARD_STAMP_PREFIX = "<!-- rapid-os-standard:"
_STAMP = re.compile(
    r"(?:\n)?<!-- rapid-os-standard: (?P<name>[a-z0-9-]+) sha256=(?P<digest>[0-9a-f]{64}) -->\n?\Z"
)


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n")


def _body(text: str) -> str:
    body = _lf(text)
    return body if body.endswith("\n") else body + "\n"


def standard_body_digest(body: str) -> str:
    return hashlib.sha256(_body(body).encode("utf-8")).hexdigest()


def stamp_standard(body: str, name: str) -> str:
    """The standard with its last line: the name and the digest of the body."""
    body = _body(body)
    return f"{body}{STANDARD_STAMP_PREFIX} {name} sha256={standard_body_digest(body)} -->\n"


def strip_standard_stamp(text: str) -> str:
    """The standard without its stamp (unchanged when it has none)."""
    normalized = _lf(text)
    match = _STAMP.search(normalized)
    if match is None:
        return text
    return normalized[: match.start()] + ("\n" if match.group(0).startswith("\n") else "")


def standard_state(text: str, expected: str) -> str:
    """`current` (it is what this version writes), `outdated` (written by Rapid OS and not edited since: it can
    be replaced), `edited` (stamped, but the person changed the body), `unstamped` (no stamp, but its body is
    already the one this version writes: only the stamp is missing) or `unmarked` (no stamp and another body:
    an earlier version, before 3.2.0rc5, or the person wrote it; it is never replaced)."""
    normalized = _lf(text)
    if normalized == _lf(expected):
        return "current"
    match = _STAMP.search(normalized)
    if match is None:
        return "unstamped" if _body(normalized) == strip_standard_stamp(_lf(expected)) else "unmarked"
    body = normalized[: match.start()] + ("\n" if match.group(0).startswith("\n") else "")
    return "outdated" if standard_body_digest(body) == match.group("digest") else "edited"

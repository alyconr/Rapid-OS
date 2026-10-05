import locale


def read_text_best_effort(path):
    """Read user-facing text files across common Windows encodings."""
    preferred_encoding = locale.getpreferredencoding(False)
    encodings = []

    for encoding in ("utf-8", "utf-8-sig", preferred_encoding, "cp1252", "latin-1"):
        normalized = (encoding or "").lower()
        if normalized and normalized not in encodings:
            encodings.append(normalized)

    last_error = None
    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc

    if last_error is not None:
        return path.read_text(encoding="utf-8", errors="replace")

    return path.read_text()

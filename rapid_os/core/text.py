import locale
import re
import shlex
import subprocess
import sys

INPUT_ENCODING_CODE = "RAPID1424"
MOJIBAKE_CODE = "RAPID1425"


class InputEncodingError(ValueError):
    """Text handed to Rapid OS (stdin or `--file`) that is not valid UTF-8 (RAPID1424)."""

    code = INPUT_ENCODING_CODE


def decode_utf8_input(raw: bytes, source: str) -> str:
    """Decode text a person or an agent handed over as UTF-8 (a BOM is accepted).

    On Windows `sys.stdin` reads with the console code page (cp1252), which turns `ó` into `Ã³` and the
    text is stored altered. Input is therefore always read as bytes and decoded here; text that is not
    UTF-8 is refused with a clear error, never stored changed."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputEncodingError(
            f"{INPUT_ENCODING_CODE} El texto de {source} no es UTF-8 válido (byte 0x{raw[exc.start]:02x} en la posición "
            f"{exc.start}). Guarda el contenido como UTF-8 y vuelve a enviarlo; Rapid OS no guarda texto alterado."
        ) from exc


def read_stdin_text() -> str:
    """All of stdin as UTF-8 text, whatever the console encoding is."""
    stream = getattr(sys.stdin, "buffer", None)
    if stream is None:  # a replaced stdin (tests) that only has text
        return sys.stdin.read()
    return decode_utf8_input(stream.read(), "stdin")


def display_command(argv) -> str:
    """The argv as a person can paste it: quoted for the shell of the platform."""
    parts = [str(part) for part in argv]
    if sys.platform == "win32":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def _cp1252_continuation_chars() -> str:
    """The characters cp1252 shows for the bytes 0x80-0xBF (the second byte of a UTF-8 pair read as cp1252)."""
    chars = []
    for value in range(0x80, 0xC0):
        try:
            chars.append(bytes([value]).decode("cp1252"))
        except UnicodeDecodeError:  # 0x81, 0x8d, 0x8f, 0x90, 0x9d are undefined in cp1252
            continue
    return re.escape("".join(chars))


_CONTINUATION = _cp1252_continuation_chars()
# `Ã³` (ó), `Ã±` (ñ), `Â¿` (¿), `â€œ` (“): UTF-8 bytes shown as cp1252 characters.
MOJIBAKE_RE = re.compile(rf"Ã[{_CONTINUATION}]|Â[{_CONTINUATION}]|â€[{_CONTINUATION}]")


def find_mojibake(text: str) -> str | None:
    """The first sequence of UTF-8 read as cp1252 in `text` (for example `Ã³`), or None."""
    match = MOJIBAKE_RE.search(text or "")
    return match.group(0) if match else None


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

    return path.read_text(encoding="utf-8")

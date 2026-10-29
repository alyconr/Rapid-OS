import os
import sys


def ensure_utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (OSError, ValueError, AttributeError):
                pass
    # Piped input (a spec or a document from an agent) is UTF-8; the console code page (cp1252 on Windows)
    # would turn `ó` into `Ã³`. A terminal keeps the encoding its own prompts use. Text that is handed over as
    # data is read as bytes anyway (`rapid_os.core.text.read_stdin_text`).
    stdin = sys.stdin
    try:
        if hasattr(stdin, "reconfigure") and not stdin.isatty():
            stdin.reconfigure(encoding="utf-8")
    except (OSError, ValueError, AttributeError):
        pass


def print_step(msg):
    print(f"🔹 {msg}")


def print_success(msg):
    print(f"✅ {msg}")


def print_warning(msg):
    print(f"⚠️  {msg}")


def print_error(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

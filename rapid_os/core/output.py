import os
import sys


def ensure_utf8_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
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

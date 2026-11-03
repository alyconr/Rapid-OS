"""Local development of a BaaS provider: the `.env.example` variables and what only the person can run. Pure: no I/O.

Supabase runs locally with its CLI (`supabase init`, `supabase start`, which needs a container runtime) and
Firebase with the Emulator Suite (`firebase emulators:start`). Rapid OS writes the variables; the person runs
the commands, as with `docker compose up -d`. Sources (official documentation):
https://supabase.com/docs/guides/local-development/cli/getting-started
https://supabase.com/docs/reference/cli/supabase-start
https://supabase.com/docs/guides/api/api-keys
https://firebase.google.com/docs/emulator-suite/install_and_configure
https://firebase.google.com/docs/emulator-suite/connect_firestore
https://firebase.google.com/docs/emulator-suite/connect_auth
https://firebase.google.com/docs/projects/api-keys
"""

from __future__ import annotations

import re
from typing import Mapping

from rapid_os.domain.security import BAAS_PROVIDERS

ENV_EXAMPLE_FILE = ".env.example"
# The prefix a frontend framework requires for a variable that reaches the browser.
CLIENT_ENV_PREFIX: Mapping[str, str] = {
    "nextjs": "NEXT_PUBLIC_",
    "nuxt": "NUXT_PUBLIC_",
    "sveltekit": "PUBLIC_",
    "astro": "PUBLIC_",
    "react-vite": "VITE_",
    "vue-vite": "VITE_",
    "svelte-vite": "VITE_",
    "angular": "",
}
ENV_HEADER = (
    "# Variables del entorno local del proveedor BaaS, escritas por Rapid OS.\n"
    "# Valores de desarrollo local, sin secretos reales: copia este archivo a .env y completa lo que falta.\n"
)


def env_entries(provider: str, frontend: str | None) -> list[tuple[str, str, str]]:
    """`(comment, name, value)` of the variables of a provider for the frontend framework."""
    prefix = CLIENT_ENV_PREFIX.get(frontend or "", "")
    if provider == "supabase":
        return [
            ("Supabase local (`supabase start`); las claves salen de `supabase status`", f"{prefix}SUPABASE_URL", "http://127.0.0.1:54321"),
            ("Clave publicable (sb_publishable_...): es pública y puede ir al navegador", f"{prefix}SUPABASE_PUBLISHABLE_KEY", ""),
            ("Clave secreta (sb_secret_...): solo en servidor o Edge Functions, nunca con prefijo del cliente", "SUPABASE_SECRET_KEY", ""),
            ("Base de datos local (usuario y clave por defecto del entorno local)", "SUPABASE_DB_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"),
        ]
    if provider == "firebase":
        return [
            ("Configuración web de Firebase (consola de Firebase): identifica el proyecto, no es un secreto", f"{prefix}FIREBASE_API_KEY", ""),
            ("", f"{prefix}FIREBASE_AUTH_DOMAIN", ""),
            ("Un proyecto `demo-` no toca recursos de producción", f"{prefix}FIREBASE_PROJECT_ID", "demo-local"),
            ("Conectar la app a los emuladores en desarrollo", f"{prefix}FIREBASE_USE_EMULATORS", "true"),
            ("Admin SDK contra los emuladores (sin protocolo)", "FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080"),
            ("", "FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099"),
            ("Credenciales de cuenta de servicio: solo en servidor; en entornos de Google usa las credenciales predeterminadas", "GOOGLE_APPLICATION_CREDENTIALS", ""),
        ]
    return []


def render_env(provider: str, frontend: str | None) -> str:
    lines = ENV_HEADER.splitlines()
    for comment, name, value in env_entries(provider, frontend):
        lines += ["", f"# {comment}"] if comment else []
        lines.append(f"{name}={value}")
    return "\n".join(lines) + "\n"


def merge_env(existing: str, provider: str, frontend: str | None) -> str:
    """Append only the variables the file does not define yet; never change a line that is there."""
    defined = {m.group(1) for ln in existing.splitlines() if (m := re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=", ln))}
    missing = [entry for entry in env_entries(provider, frontend) if entry[1] not in defined]
    if not missing:
        return existing
    out = existing.rstrip("\n")
    for comment, name, value in missing:
        out += (f"\n\n# {comment}" if comment else "") + f"\n{name}={value}"
    return out + "\n"


def local_actions(provider: str | None, *, initialized: bool) -> list[dict[str, str]]:
    """What only the person can run to have the provider locally, each with its exact command."""
    if provider not in BAAS_PROVIDERS:
        return []
    actions: list[dict[str, str]] = []
    if provider == "supabase":
        if not initialized:
            actions.append(
                {
                    "id": "baas-init",
                    "why": "Crea supabase/ (config.toml, migraciones, funciones y pruebas). Requiere la CLI de Supabase instalada.",
                    "command": "supabase init",
                    "text": "Para crear el proyecto local de Supabase, ejecuta en tu terminal: {command}",
                }
            )
        actions.append(
            {
                "id": "baas-local",
                "why": "Levanta Postgres, Auth, Storage y Edge Functions en local (necesita Docker u otro runtime de contenedores); las claves salen de `supabase status`.",
                "command": "supabase start",
                "text": "Para levantar Supabase en local, ejecuta en tu terminal: {command}",
            }
        )
    else:
        if not initialized:
            actions.append(
                {
                    "id": "baas-init",
                    "why": "Crea firebase.json, las reglas y la carpeta de funciones, y configura los emuladores. Requiere la CLI de Firebase instalada.",
                    "command": "firebase init",
                    "text": "Para crear el proyecto local de Firebase, ejecuta en tu terminal: {command}",
                }
            )
        actions.append(
            {
                "id": "baas-local",
                "why": "Levanta los emuladores (Authentication, Firestore, Functions, Storage) en local; no son para producción.",
                "command": "firebase emulators:start",
                "text": "Para levantar los emuladores de Firebase, ejecuta en tu terminal: {command}",
            }
        )
    return actions

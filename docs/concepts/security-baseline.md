---
title: Base de seguridad
description: Las reglas de seguridad con las que nace todo proyecto, qué estándar cubre cada una, los niveles de MVP y Corporate, los escaneos de CI que Rapid OS escribe y la sección de IA.
---

# Base de seguridad

Todo proyecto nace con reglas de seguridad concretas, cada una trazable a un estándar, y con escaneos que corren en CI desde el primer PR. MVP y Corporate comparten la base; cambia el nivel. Las reglas viven en `.rapid-os/standards/security.md`, llegan al agente como estándar y `rapid start hardening` las usa para clasificar los hallazgos.

## Qué estándar cubre qué

| Estándar | Qué cubre en `security.md` |
| :--- | :--- |
| [OWASP ASVS 5.0.0](https://github.com/OWASP/ASVS) | El nivel que el proyecto verifica: L1 (MVP) o L2 (Corporate). |
| [OWASP Top 10:2025](https://top10.owasp.org/2025) | Una a tres reglas por categoría, de A01 Broken Access Control a A10 Mishandling of Exceptional Conditions. |
| [OWASP API Security Top 10:2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) | Una regla por ítem API1-API10, solo en los stacks con API (los de backend del catálogo y `nextjs`, `nuxt` y `sveltekit`). |
| [NIST SSDF SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final) | Las familias PO, PS, PW y RV traducidas al flujo de Rapid OS: modelo de amenazas breve en la spec de toda historia que toque autenticación, pagos o datos personales, revisión humana en el gate final y tratamiento de vulnerabilidades por severidad CVSS. |
| [SLSA 1.2](https://slsa.dev/spec/v1.2/) | Lockfile versionado, dependencias fijadas y acciones de CI fijadas por SHA completo. Corporate añade Build L2 y Source L2. |
| [CWE](https://cwe.mitre.org/) y [CVSS v4.0](https://www.first.org/cvss/v4-0/specification-document) | Todo hallazgo se reporta con su CWE y su vector `CVSS:4.0/...`. |
| [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/) y [Top 10 for Agentic Applications for 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) | La sección de IA, si el producto usa modelos o agentes. |

Cada regla cita entre corchetes el estándar que la respalda. Los nombres de las categorías son los oficiales de cada fuente (por ejemplo, A09 se llama `Security Logging and Alerting Failures`), y las URL quedan en un comentario al final de `security.md`.

## Niveles

| | MVP | Corporate |
| :--- | :--- | :--- |
| OWASP ASVS 5.0.0 | Nivel L1 | Nivel L2 |
| SLSA 1.2 | Lockfile, dependencias y acciones fijadas | Además Build L2 (procedencia firmada del artefacto) y Source L2 |
| CI | Secretos, análisis estático, dependencias | Además SBOM y procedencia |

La velocidad de MVP nunca rebaja la base: `coding-rules.md` de MVP lo dice (*La velocidad nunca rebaja la base de seguridad ni la arquitectura modular*) y ya no permite tipado suelto con `any`.

Source L2 de SLSA 1.2 es *historial y procedencia*: el historial de `main` es continuo e inmutable y la plataforma de código emite la procedencia de cada revisión. Que todo cambio entre por un PR con revisión es una práctica del proyecto que se suma, no un requisito de L2. Esta parte se completa al configurar el repositorio.

## ¿Usa IA?

El onboarding hace una pregunta después del arquetipo, `rapid setup set ai yes|no`: *¿El producto usará modelos de IA o agentes (por ejemplo, un asistente que responda por WhatsApp)?* Con `yes`, `security.md` incluye la sección **Seguridad de IA**: la salida del modelo es entrada no confiable, defensa contra la inyección de instrucciones, herramientas en lista permitida con mínimo privilegio, aprobación humana para las acciones irreversibles (pagos, borrados, mensajes a clientes), sin secretos en prompts ni en memoria y límites de costo y de iteraciones. Cada regla cita su ítem de OWASP LLM 2025 y de OWASP Agentic 2026.

Los ids `python-ai` y `nodejs-ai` (de antes del catálogo por componentes) responden `ai: yes` solos: son productos de IA y la sección se incluye. Un `setup.json` sin el campo `ai` se lee como sin decidir mientras el onboarding no haya terminado, y como `no` en un proyecto ya terminado.

## El CI de seguridad lo escribe Rapid OS

Al cerrar el onboarding de un **repositorio vacío**, `rapid setup finish` escribe `.github/workflows/rapid-security.yml` desde `templates/ci/<lenguaje>-security.yml` (Python o TypeScript). Corre en `pull_request` y en `push` a `main`:

- **Secretos:** gitleaks (el binario se descarga con su suma de verificación fijada).
- **Análisis estático:** semgrep con las reglas `p/owasp-top-ten` (funciona en repositorios privados); Python añade bandit.
- **Dependencias:** `pip-audit` (Python) o `npm audit --audit-level=high` (TypeScript).
- **Corporate:** SBOM (`anchore/sbom-action`) y procedencia firmada (`actions/attest-build-provenance`).

Todas las acciones están fijadas por SHA completo del commit, con su versión en un comentario. Rapid OS nunca sobrescribe un workflow existente, ni escribe este en un repositorio que ya tiene código. El archivo aparece en la salida de `setup finish` (y como `added_files` en `--json`): *Rapid OS añadió este workflow; revísalo antes del primer commit*. Durante la revisión de los borradores, la acción `review_drafts` lo anuncia antes con `planned_files`.

## Proyectos ya inicializados

La regla de `security.md` solo cambia por decisión de la persona. Para un proyecto creado antes de esta base:

```bash
rapid setup set archetype mvp --refresh
```

Regenera `security.md` y `coding-rules.md` del arquetipo con las plantillas actuales y deja las copias anteriores como `.bak`. `rapid doctor` lo sugiere con un aviso `RAPID1421` cuando `security.md` no menciona ASVS. Un `security.md` escrito a mano (que no es el de Rapid OS) nunca se reescribe salvo con `--refresh`.

## Modo hardening

La plantilla de spec de `rapid start hardening` incluye `findings` (`cwe`, `cvss_v4_vector`, `severity`, `standard_ref`) y la instrucción de clasificar cada hallazgo con su CWE y su vector CVSS v4.0, y de citar la regla de `security.md` que lo cubre. La spec solo conserva los campos de su esquema, así que el agente repite cada hallazgo como un criterio en `acceptance_criteria` (CWE, vector y regla).

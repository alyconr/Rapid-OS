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

## Proyectos sobre un proveedor BaaS

Con `supabase` o `firebase` como stack `baas`, `security.md` añade una sección del proveedor, con las mismas citas entre corchetes que el resto: Supabase (RLS en toda tabla de un esquema expuesto, privilegios por omisión revocados, políticas probadas con `supabase test db`, la clave publicable es pública y la secreta nunca va al cliente) o Firebase (reglas de Firestore y Storage con deny por defecto probadas en el emulador con `@firebase/rules-unit-testing`, App Check, la `apiKey` web como identificador y no como secreto, credenciales de cuenta de servicio solo en el servidor). Aplica el API Security Top 10, y el workflow de CI añade el job que ejecuta esas pruebas.

Una base de datos de documentos, Firestore o el servicio `database:mongodb`, añade una sección sobre inyección NoSQL [OWASP A05:2025, CWE-943, OWASP ASVS V1]: nunca pases a una consulta un objeto, un operador (`$where`, `$gt`, `$ne`...) ni un nombre de campo tomados de la entrada, comprueba antes el tipo de cada valor y valida la forma de cada documento al escribirlo. Con MongoDB, una sección exige autenticación en todo entorno (también en local) y el puerto solo en `127.0.0.1`, como el `compose.yaml` que escribe Rapid OS. Cambiar de proveedor o de motor de base de datos reescribe un `security.md` que escribió Rapid OS.

## ¿Usa IA?

El onboarding hace una pregunta después del arquetipo, `rapid setup set ai yes|no`: *¿El producto usará modelos de IA o agentes (por ejemplo, un asistente que responda por WhatsApp)?* Con `yes`, `security.md` incluye la sección **Seguridad de IA**: la salida del modelo es entrada no confiable, defensa contra la inyección de instrucciones, herramientas en lista permitida con mínimo privilegio, aprobación humana para las acciones irreversibles (pagos, borrados, mensajes a clientes), sin secretos en prompts ni en memoria y límites de costo y de iteraciones. Cada regla cita su ítem de OWASP LLM 2025 y de OWASP Agentic 2026.

Los ids `python-ai` y `nodejs-ai` (de antes del catálogo por componentes) responden `ai: yes` solos: son productos de IA y la sección se incluye. Un `setup.json` sin el campo `ai` se lee como sin decidir mientras el onboarding no haya terminado, y como `no` en un proyecto ya terminado.

## El CI de seguridad lo escribe Rapid OS

Al cerrar el onboarding de un **repositorio vacío**, `rapid setup finish` escribe un workflow por lenguaje, `.github/workflows/rapid-security-<lenguaje>.yml` (por ejemplo `rapid-security-python.yml`), desde `templates/ci/<lenguaje>-security.yml`. En la pestaña Actions cada uno se llama como su archivo, `rapid-security-<lenguaje>` (por ejemplo `rapid-security-python` y `rapid-security-typescript`), así que dos componentes con lenguajes distintos dan dos workflows distinguibles. Un proyecto que ya tiene `rapid-security.yml` (de antes de este cambio) se deja como está y no recibe otros. Corre en `pull_request` y en `push` a `main`:

- **Secretos:** gitleaks (el binario se descarga con su suma de verificación fijada).
- **Análisis estático:** semgrep con las reglas `p/owasp-top-ten` (funciona en repositorios privados); Python añade bandit.
- **Dependencias:** la auditoría del gestor de paquetes del lenguaje, en la carpeta de cada componente (abajo).
- **Corporate:** SBOM (`anchore/sbom-action`) y procedencia firmada (`actions/attest-build-provenance`).

Todas las acciones están fijadas por SHA completo del commit, con su versión en un comentario. Rapid OS nunca sobrescribe un workflow existente, ni escribe este en un repositorio que ya tiene código. El archivo aparece en la salida de `setup finish` (y como `added_files` en `--json`): *Rapid OS añadió este workflow; revísalo antes del primer commit*. Durante la revisión de los borradores, la acción `review_drafts` lo anuncia antes con `planned_files`.

### Qué audita el job de dependencias, por componente

El manifiesto y el lockfile están en la carpeta de cada componente. Con la topología `fullstack-separated` (un backend y un frontend con stacks distintos) son `backend/` y `frontend/`; cualquier otra topología tiene todo el proyecto en la raíz. El job de dependencias corre una vez por carpeta de su lenguaje (una matriz sobre `dir`, con el nombre `Dependencias (...) · <carpeta>`), con esa carpeta como directorio de trabajo:

| Lenguaje | Qué lee en la carpeta | Comando |
| --- | --- | --- |
| Python | `uv.lock` | `uv export --frozen --format requirements.txt --no-emit-project -o <archivo>` y después `pip-audit --disable-pip -r <archivo>` (los requisitos exportados van fijados con sus hashes, así que pip-audit no vuelve a resolver). `uv audit` existe, pero uv lo marca como experimental. |
| Python | `requirements.txt` | `pip-audit -r requirements.txt` |
| Python | `pyproject.toml` sin lock | `pip install .` y después `pip-audit --skip-editable` |
| TypeScript | `pnpm-lock.yaml`, `package-lock.json` o `yarn.lock` | `pnpm audit --audit-level high`, `npm audit --audit-level=high` o `yarn npm audit --all --recursive --severity high`, tras instalar con el lockfile. La versión de pnpm sale de `packageManager` en el `package.json` de esa carpeta (pnpm 10 si no lo tiene). |
| Go, Rust, Ruby, .NET, PHP | `go.mod`, `Cargo.lock`, `Gemfile.lock`, un `.sln`/`.slnx`/`.csproj`, `composer.lock` | `govulncheck`, `cargo audit`, `bundle-audit`, `dotnet package list --vulnerable`, `composer audit` |

Java y Kotlin usan la revisión de dependencias de GitHub en los pull requests, que cubre todo el repositorio.

Qué pasa en cada carpeta:

- **La carpeta tiene código y su manifiesto o lockfile:** la auditoría corre y falla ante una vulnerabilidad.
- **La carpeta tiene código pero no tiene manifiesto o lockfile:** el job falla y dice qué falta y dónde, por ejemplo `frontend tiene package.json pero ningún lockfile (pnpm-lock.yaml, package-lock.json o yarn.lock)`.
- **La carpeta no existe o todavía no tiene código de ese lenguaje** (un repositorio recién creado): el job pasa y escribe un aviso (`::warning::`) que también sale en el resumen del job: `Nada que auditar: backend no existe o no tiene código Python todavía`. Un job en verde con ese aviso no auditó nada.

Cada workflow empieza con una línea `# rapid-os-ci: <lenguaje> sha256=<digest>`: el SHA-256 del resto del archivo tal como lo escribió Rapid OS. Así una versión posterior sabe si el workflow se editó.

### Poner al día los workflows de un proyecto existente

`rapid doctor` compara cada `rapid-security-<lenguaje>.yml` con lo que escribe la versión actual para los stacks y la topología del proyecto (`.rapid-os/setup.json`):

- **Lo escribió una versión anterior y nadie lo editó** (su sello sigue coincidiendo o, en los workflows de 3.2.0rc1 a rc3, que no tienen sello, su contenido es uno de los que escribían esas versiones): aviso `RAPID1443`.
- **La persona lo editó:** información `RAPID1443`.

```bash
rapid setup ci                # estado de cada workflow: al día, anterior, editado o no existe
rapid setup ci --regenerate   # escribe lo que genera esta versión
```

`--regenerate` reemplaza un workflow que nadie editó (la copia anterior va a `.rapid-os/backups/`) y escribe el que falta. Nunca pisa un workflow editado: el nuevo queda al lado como `rapid-security-<lenguaje>.yml.new` (GitHub no lo ejecuta). Compáralos, lleva tus cambios al nuevo y renómbralo al nombre del workflow. `rapid setup ci` solo lee; con `--json` da `workflows[]` con `file`, `language`, `status` y, con `--regenerate`, `action` (`unchanged`, `replaced`, `written`, `new`) y `written`.

## Proyectos ya inicializados

La regla de `security.md` solo cambia por decisión de la persona. Para un proyecto creado antes de esta base:

```bash
rapid setup set archetype mvp --refresh
```

Regenera `security.md` y `coding-rules.md` del arquetipo con las plantillas actuales y deja las copias anteriores en `.rapid-os/backups/` (las 5 más recientes por archivo), no junto a `standards/`. `rapid doctor` lo sugiere con un aviso `RAPID1421` cuando `security.md` no menciona ASVS. Un `security.md` escrito a mano (que no es el de Rapid OS) nunca se reescribe salvo con `--refresh`.

## Modo hardening

La plantilla de spec de `rapid start hardening` incluye `findings` (`cwe`, `cvss_v4_vector`, `severity`, `standard_ref`) y la instrucción de clasificar cada hallazgo con su CWE y su vector CVSS v4.0, y de citar la regla de `security.md` que lo cubre. La spec solo conserva los campos de su esquema, así que el agente repite cada hallazgo como un criterio en `acceptance_criteria` (CWE, vector y regla).

# Procedimiento de Despliegue de Documentación

Este runbook describe el procedimiento formal, seguro y determinista para publicar el portal de documentación de **RAPID OS v3** en GitHub Pages.

---

## 1. Alcance y Gobernanza

- **Portal:** Documentación canónica de RAPID OS v3.0.0.
- **Framework:** Docusaurus 3 con Node.js 20.
- **Hosting:** GitHub Pages (`alyconr.github.io/Rapid-OS/`).
- **Mecanismo:** Despliegue desacoplado mediante GitHub Actions (`.github/workflows/docs-deploy.yml`).
- **Aprobación requerida:** El despliegue a producción requiere autorización explícita del propietario del repositorio.

---

## 2. Separación de Responsabilidades

| Componente | Workflow | Evento | Permisos |
| :--- | :--- | :--- | :--- |
| **Validación CI** | `.github/workflows/docs.yml` | Pull Request y Push a `main` | `contents: read` |
| **Publicación** | `.github/workflows/docs-deploy.yml` | `workflow_dispatch` o push a `main` | `contents: read`, `pages: write`, `id-token: write` |

> **Nota de Seguridad:** Ningún Pull Request ni fork tiene acceso a publicar en GitHub Pages. Los tokens OIDC temporales solo se emiten en el entorno protegido `github-pages`.

---

## 3. Precondiciones Técnicas (Pre-flight Checklist)

Antes de autorizar o ejecutar un despliegue, el equipo debe verificar:

1. **Suite de Pruebas Unitaria y E2E Verde:**
   ```bash
   python -m unittest discover tests
   ```
2. **Typecheck y Build de Docusaurus Exitosos:**
   ```bash
   cd website
   npm ci
   npm run typecheck
   npm run build
   ```
3. **Validación de Artefactos Estáticos:**
   - Confirmar que `website/build/index.html` existe.
   - Confirmar que `website/build/404.html` existe.
   - Confirmar que `website/build/sitemap.xml` contiene URLs con prefijo `/Rapid-OS/`.
   - Verificar la ausencia de fugas de `localhost` o rutas absolutas de desarrollo (`file:///`).
4. **Configuración de Producción en `website/docusaurus.config.ts`:**
   - `url: 'https://alyconr.github.io'`
   - `baseUrl: '/Rapid-OS/'`
   - `trailingSlash: false`
   - `onBrokenLinks: 'throw'`
5. **Configuración de GitHub Pages en el Repositorio:**
   - Settings → Pages → Source: **GitHub Actions**.

---

## 4. Ejecución del Despliegue

### Opción A: Despliegue Manual Controlado (`workflow_dispatch`)

1. Navegar a **Actions** en el repositorio GitHub.
2. Seleccionar el workflow **Deploy Documentation**.
3. Hacer clic en **Run workflow**.
4. Seleccionar la rama `main` o tag de release aprobado.
5. Confirmar la ejecución.

### Opción B: Despliegue Automático por Push a `main`

1. Tras la aprobación formal y merge del PR de release a `main`, el workflow se iniciará automáticamente si se detectan cambios en `docs/**`, `website/**` o en el propio workflow.

---

## 5. Verificación Post-Despliegue (Smoke Testing)

Una vez completada la ejecución del workflow de despliegue:

1. **Estado del Job en GitHub Actions:**
   - Verificar que el job `build` y el job `deploy` concluyeron con código 0.
   - Inspeccionar la URL generada en la salida del step `deploy`.
2. **Smoke Test HTTP de Producción:**
   - Acceso a Home: `https://alyconr.github.io/Rapid-OS/` (código HTTP 200).
   - Acceso a CLI Reference: `https://alyconr.github.io/Rapid-OS/cli` (código HTTP 200).
   - Acceso a Laboratorios: `https://alyconr.github.io/Rapid-OS/tutorials/` (código HTTP 200).
   - Acceso a Página 404 personalizada: `https://alyconr.github.io/Rapid-OS/non-existent-page` (código HTTP 404 con layout de Docusaurus).
   - Inspección de `sitemap.xml`: `https://alyconr.github.io/Rapid-OS/sitemap.xml` (código HTTP 200).
3. **Ejecución de Smoke Tests Automatizados:**
   ```bash
   RAPID_OS_LIVE_DOCS_URL=https://alyconr.github.io/Rapid-OS python -m unittest tests.test_documentation_deployment.TestLiveDocsSmoke
   ```

---

## 6. Registro y Notificación

1. Anotar el commit SHA desplegado en la bitácora de release.
2. Notificar en el canal del proyecto que la versión de documentación está en línea.

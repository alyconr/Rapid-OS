# Procedimiento de Rollback de Documentación

Este runbook detalla las acciones operativas a seguir en caso de detección de incidentes en el portal público de documentación tras un despliegue.

---

## 1. Criterios de Activación de Rollback

Se debe iniciar un procedimiento de rollback si se presenta cualquiera de las siguientes condiciones en el entorno de producción:

- **P0 - Rotura Crítica:** La página principal (`/Rapid-OS/`) responde con error HTTP 5xx o 404 persistente.
- **P0 - Bloqueo de Navegación:** Fallos globales de scripts (JavaScript runtime error) que impidan interactuar con la barra de navegación o sidebar.
- **P0 - Fuga de Información Confidencial:** Publicación accidental de credenciales, secretos, endpoints internos o datos sensibles en la documentación.
- **P1 - Desalineación Severa de Product Truth:** Publicación de especificaciones erróneas que induzcan a comportamientos destructivos o defectuosos en el CLI de RAPID OS.

---

## 2. Procedimiento Canónico de Rollback (Git Revert Controlado)

Para garantizar la inmutabilidad de la historia de Git, trazabilidad de autoría y gobernanza determinista, el rollback se gestiona mediante reversión explícita en el repositorio:

### Paso 1: Identificar el Último Commit Estable

Consultar el historial en la rama `main` o en los releases para determinar el SHA estable previo:
```bash
git log --oneline -n 10
```
Supongamos que el commit introductorio del fallo es `BROKEN_COMMIT_SHA`.

### Paso 2: Crear Rama de Hotfix / Revert

```bash
git checkout main
git pull origin main
git checkout -b hotfix/revert-docs-incident
git revert --no-edit BROKEN_COMMIT_SHA
```

### Paso 3: Validación Local de Pre-flight

Ejecutar las comprobaciones obligatorias para verificar que el árbol revertido es técnicamente íntegro:
```bash
cd website
npm ci
npm run typecheck
npm run build
cd ..
python -m unittest tests.test_documentation_deployment.TestDocumentationStaticBuildIntegrity -v
```

### Paso 4: Creación, Revisión y Merge del PR de Rollback

1. Publicar la rama de hotfix:
   ```bash
   git push origin hotfix/revert-docs-incident
   ```
2. Crear un Pull Request hacia `main` titulado:
   `fix(rollback): revert commit <BROKEN_COMMIT_SHA> due to documentation incident`
3. Tras la revisión y aprobación por parte de los revisores autorizados y verificación de CI verde (`docs.yml`), fusionar el PR en `main`.

### Paso 5: Despliegue Manual Autorizado

Dado que `.github/workflows/docs-deploy.yml` no realiza publicaciones automáticas:

1. El operador autorizado debe ingresar a la pestaña **Actions** en GitHub.
2. Seleccionar el workflow **Deploy Documentation**.
3. Hacer clic en **Run workflow**, seleccionando la rama `main` (que ya contiene el revert).
4. El job `build` compilará el sitio, el job `deploy` actualizará GitHub Pages y el job `smoke-test` validará automáticamente las rutas públicas en vivo.

---

## 3. Verificación Post-Rollback

Una vez finalizada la ejecución autorizada de `.github/workflows/docs-deploy.yml`:

1. **Verificación Automatizada mediante Smoke Tests:**
   Ejecutar localmente o verificar la salida exitosa del job `smoke-test`:
   ```bash
   RAPID_OS_LIVE_DOCS_URL=https://alyconr.github.io/Rapid-OS python -m unittest tests.test_documentation_deployment.TestLiveDocsSmoke -v
   ```
   Rutas críticas comprobadas con aserciones reales:
   - Homepage: HTTP 200 y presencia del título.
   - CLI Reference: HTTP 200 y presencia de la sección CLI.
   - Tutoriales: HTTP 200 y presencia del índice de laboratorios.
   - Sitemap: HTTP 200 y formato XML canónico.
   - Ruta inexistente: HTTP 404 controlado con plantilla de Docusaurus.

2. **Comprobación Manual:**
   Verificar en navegador en modo incógnito (limpiando caché del navegador) para confirmar que la versión estable está visible para los usuarios finales.

---

## 4. Post-Mortem y Análisis de Causa Raíz

Una vez estabilizado el servicio:

1. Registrar un issue en GitHub con la etiqueta `incident-docs`.
2. Documentar:
   - Causa raíz del incidente.
   - Motivo por el cual las pruebas pre-despliegue no detectaron la falla.
   - Acciones preventivas a incorporar en la suite automatizada de CI (`docs.yml` o tests unitarios).

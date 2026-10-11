# Procedimiento de Rollback de Documentación

Este runbook detalla las acciones inmediatas a seguir en caso de detección de incidentes en el portal público de documentación tras un despliegue.

---

## 1. Criterios de Activación de Rollback

Se debe iniciar un rollback si se presenta cualquiera de las siguientes condiciones en el entorno de producción:

- **P0 - Rotura Crítica:** La página principal (`/Rapid-OS/`) responde con error HTTP 5xx o 404.
- **P0 - Bloqueo de Navegación:** Fallos masivos de scripts (JavaScript runtime error) que impidan interactuar con la barra de navegación o sidebar.
- **P0 - Fuga de Información Confidencial:** Publicación involuntaria de tokens, credenciales, datos internos o secretos en la documentación.
- **P1 - Desalineación Severa de Product Truth:** Publicación de especificaciones erróneas que induzcan a comportamientos destructivos en el CLI de RAPID OS.

---

## 2. Estrategias de Rollback

Existen dos estrategias operativas para restaurar el portal a un estado estable previo:

### Estrategia A: Rollback Rápido por Git Revert / Re-deploy de Commit Estable (Recomendada)

Esta estrategia preserva la inmutabilidad y la trazabilidad del historial de Git.

1. **Identificar el Último Commit Estable:**
   Consultar el historial de despliegues exitosos en GitHub Actions o la bitácora de release.
   ```bash
   git log --oneline -n 10
   ```
   Supongamos que el commit estable previo es `PREV_STABLE_SHA`.

2. **Crear Rama de Hotfix / Revert:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b hotfix/revert-broken-docs
   git revert --no-edit <BROKEN_COMMIT_SHA>
   ```

3. **Verificar Localmente:**
   ```bash
   cd website
   npm ci
   npm run build
   ```

4. **Publicar y Aprobar PR de Emergencia:**
   - Crear PR hacia `main` con etiqueta `emergency-rollback`.
   - Una vez fusionado, `.github/workflows/docs-deploy.yml` compilará y desplegará automáticamente la versión revertida.

---

### Estrategia B: Re-despliegue de Artefacto Estable desde GitHub Actions (Tiempos de Respuesta < 3 min)

Si GitHub Actions conserva los artefactos generados en la ejecución previa exitosa:

1. Ingresar a **Actions** → **Deploy Documentation**.
2. Localizar la última ejecución exitosa previa al incidente.
3. Si el workflow soporta re-run de jobs, seleccionar **Re-run all jobs**.
4. Alternativamente, ejecutar manualmente el workflow (`workflow_dispatch`) apuntando directamente al tag o SHA estable (`git checkout v3.0.0`).

---

## 3. Verificación Post-Rollback

1. Ejecutar de inmediato los smoke tests de validación:
   ```bash
   RAPID_OS_LIVE_DOCS_URL=https://alyconr.github.io/Rapid-OS python -m unittest tests.test_documentation_deployment.TestLiveDocsSmoke
   ```
2. Realizar comprobación manual en navegador con caché desactivada (Hard Refresh / Incognito).
3. Confirmar que el contenido dañado ha sido reemplazado por la versión previa correcta.

---

## 4. Post-Mortem y Análisis de Causa Raíz

Una vez estabilizado el servicio:

1. Registrar un issue en GitHub con la etiqueta `incident-docs`.
2. Documentar:
   - Causa raíz del fallo.
   - Por qué las pruebas pre-despliegue (`npm run build`, `npm run typecheck`, tests unitarios) no detectaron el problema.
   - Medidas preventivas a incorporar en la suite automatizada de CI.

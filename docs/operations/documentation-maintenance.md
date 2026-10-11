# Guía de Mantenimiento y Operación Continua de Documentación

Este documento establece las directrices operativas para mantener la salud técnica, la seguridad, la precisión del contenido y la vigencia del portal de documentación de **RAPID OS v3**.

---

## 1. Cadencia y Tareas de Mantenimiento

### Mensual: Auditoría de Enlaces y Dependencias

1. **Actualización de Dependencias de Node.js:**
   - Revisar vulnerabilidades con `npm audit`:
     ```bash
     cd website
     npm audit
     ```
   - Actualizar paquetes menores/patches respetando las versiones fijadas de Docusaurus:
     ```bash
     npm update
     ```
2. **Validación de Enlaces Rotos:**
   - La configuración de Docusaurus (`onBrokenLinks: 'throw'`) bloquea enlaces internos rotos en cada compilación.
   - En auditorías periódicas, auditar enlaces externos hacia repositorios y herramientas de coding harnesses.

### Trimestral: Auditoría SEO y Metadatos

1. Verificar que los tags de Open Graph y Twitter Cards renderizan adecuadamente en herramientas de vista previa (e.g., opengraph.xyz).
2. Inspeccionar `sitemap.xml` para garantizar que todas las páginas nuevas del portal están indexadas.
3. Verificar compatibilidad con lectores de pantalla y directrices de accesibilidad web (WCAG 2.1 AA) mediante auditorías Lighthouse.

---

## 2. Estrategia de Versionamiento Documental

### Principio Canónico: Documentación Atada al Producto

En RAPID OS, la documentación evoluciona de manera sincronizada con el ciclo de vida del producto:

- **Versión Activa (`v3.0.0`):** La documentación en `docs/` refleja con exactitud la release actual del CLI y la arquitectura determinista v3.
- **Rama de Desarrollo (`develop`):** Contiene cambios pendientes de release; se compila y valida en CI pero **no se publica** a GitHub Pages hasta merge en `main`.

### Procedimiento para Nuevas Versiones Mayores / Menores (Docusaurus Versioning)

Cuando se lance una nueva versión menor o mayor del producto (por ejemplo, RAPID OS v3.1.0 o v4.0.0):

1. **Snapshot de la Versión Previa:**
   Docusaurus incluye soporte nativo para snapshotting documental:
   ```bash
   cd website
   npm run docusaurus docs:version 3.0.0
   ```
   Esto congela la versión actual en `website/versioned_docs/version-3.0.0` y `website/versioned_sidebars/version-3.0.0-sidebars.json`.
2. **Actualización de `docs/`:**
   El directorio raíz `docs/` pasa a ser la versión en desarrollo (`Next`), reflejando las nuevas características de la futura release.
3. **Selector de Versiones:**
   Activar el selector de versiones en `website/docusaurus.config.ts`:
   ```ts
   navbar: {
     items: [
       {
         type: 'docsVersionDropdown',
         position: 'right',
       },
       // ...
     ],
   }
   ```
4. **Regla de Product Truth sobre Snapshots:**
   *No fabricar retroactivamente versiones ficticias anteriores a v3.0.0*. Las versiones previas a la arquitectura unificada v3 no contaban con la suite documental actual; crear snapshots artificiales viola la integridad del producto.

---

## 3. Política de Contribución y Revisión

- **Única Fuente de Verdad:** Toda modificación documental se realiza exclusivamente en `docs/`. Está prohibido duplicar o editar directamente en `website/build/` o crear carpetas paralelas en `website/docs/`.
- **Verificación Automatizada Requerida:** Todo PR que afecte la documentación debe pasar sin advertencias ni errores:
  - `npm ci`
  - `npm run typecheck`
  - `npm run build`
  - Pruebas Python de documentación (`tests/test_documentation_labs.py`, `tests/test_documentation_deployment.py`).

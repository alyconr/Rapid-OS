# Despliegue en Netlify

Plantilla de partida para `docs/DEPLOYMENT.md`. Rapid OS no despliega: lo haces tú.

## Destino
- **Frontend**: Netlify construye el sitio con el comando `command` y publica la carpeta `publish`, ambos bajo `[build]` en `netlify.toml` (la ruta de `publish` es relativa a la carpeta base, la raíz por defecto). La configuración del archivo anula la de la interfaz.
- **Con un BaaS** (Supabase): el frontend es un SPA o un sitio estático que habla con el proveedor desde el navegador; lo privilegiado vive en las Edge Functions de Supabase, no en Netlify. Cada deploy es atómico y los Deploy Previews dejan revisar un cambio antes de publicarlo.

## Configuración y secretos
- Variables de entorno en la interfaz, la CLI o la API de Netlify, o por contexto de despliegue en `netlify.toml` (`[context.production]`, `[context.deploy-preview.environment]`, `[context.branch-deploy.environment]`). Netlify recomienda poner los valores sensibles en la interfaz, la CLI o la API, porque `netlify.toml` está en el repositorio, y avisa de que las variables definidas en `netlify.toml` no están disponibles en el entorno del deploy.
- Para un frontend con Supabase, define en el sitio solo las variables públicas del cliente (la URL del proyecto y la clave publicable, con el prefijo que exija tu framework, por ejemplo `VITE_`). La clave secreta (`sb_secret_...`) no va en Netlify ni en el repositorio.

## Servicios gestionados
| Rol | Opción |
|---|---|
| database, auth, storage, realtime (Supabase) | El proyecto de Supabase en su plataforma; Netlify solo aloja el frontend |
| database (otros), cache, queue, stream | Sin servicio gestionado documentado en esta guía: fuera de Netlify |

Las migraciones y las Edge Functions de Supabase se despliegan desde CI con la CLI de Supabase: `supabase link --project-ref <id>`, `supabase db push` y `supabase functions deploy`, con `SUPABASE_ACCESS_TOKEN` y `SUPABASE_DB_PASSWORD` como secretos del CI (no del sitio de Netlify).

## Verificación y reversión
- Revisar el Deploy Preview antes de fusionar; comprobar el sitio publicado tras el despliegue.
- Reversión: publicar un deploy anterior con **Publish Deploy** (instantáneo, no lanza un deploy nuevo). Con la publicación automática activa, el siguiente deploy por Git sobrescribe el rollback: bloquea el deploy desactivando la publicación automática.

## Fuentes oficiales
- https://docs.netlify.com/build/configure-builds/overview/
- https://docs.netlify.com/build/environment-variables/get-started/
- https://docs.netlify.com/deploy/manage-deploys/manage-deploys-overview/
- https://supabase.com/docs/guides/functions/deploy
- https://supabase.com/docs/guides/deployment/managing-environments

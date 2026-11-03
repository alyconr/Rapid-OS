# ⚡ TECH STACK: SUPABASE (BaaS)
- **Backend como servicio:** Supabase (Postgres administrado, Auth, Storage, Realtime y Edge Functions).
- **Datos:** Postgres relacional; el esquema vive en `supabase/migrations/` y cambia solo por migraciones (`supabase migration new`).
- **Seguridad de datos:** RLS activada en toda tabla de un esquema expuesto, con políticas probadas en `supabase/tests/` (`supabase test db`, pgTAP).
- **Claves:** la clave publicable (`sb_publishable_...`) es pública; la clave secreta (`sb_secret_...`) y `service_role` nunca van al cliente.
- **Funciones en servidor:** Edge Functions en `supabase/functions/<módulo>/` (TypeScript sobre Deno, `supabase functions serve` en local); código compartido en `supabase/functions/_shared/`.
- **Desarrollo local:** Supabase CLI (`supabase init`, `supabase start` con Docker u otro runtime de contenedores, `supabase db reset`); lo ejecuta la persona.
- **Tipos:** `supabase gen types --lang typescript --local` genera los tipos desde el esquema local.
- **Testing:** el comando de test del proyecto es el del frontend (`gate.tests` pasa sin Docker). Las políticas y el esquema se prueban con `supabase test db` en el job de CI y, en local, lo ejecuta la persona tras `supabase start`.
- **Version Control:** Git.
<!-- Fuentes (documentación oficial, verificadas al escribir esta plantilla):
  https://supabase.com/docs/guides/local-development/cli/getting-started
  https://supabase.com/docs/reference/cli/supabase-start
  https://supabase.com/docs/reference/cli/supabase-test-db
  https://supabase.com/docs/guides/database/postgres/row-level-security
  https://supabase.com/docs/guides/api/api-keys
  https://supabase.com/docs/guides/functions/quickstart
  https://supabase.com/docs/guides/functions/development-tips -->

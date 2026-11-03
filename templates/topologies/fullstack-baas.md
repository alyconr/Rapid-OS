# 🏗️ TOPOLOGY: FULL STACK SERVERLESS (BaaS)

## ARCHITECTURE
- **Type:** One frontend on a managed backend (BaaS). There is no backend of your own.
<!-- if supabase -->
- **Provider:** Supabase (Postgres, Auth, Storage, Realtime, Edge Functions).
<!-- endif -->
<!-- if firebase -->
- **Provider:** Firebase (Firestore, Authentication, Storage, Cloud Functions).
<!-- endif -->
<!-- if provider-undecided -->
- **Provider:** the BaaS provider is not decided yet (`rapid setup set stack <id> --component baas`).
<!-- endif -->
<!-- if ssr -->
- **Frontend:** runs code on a server (SSR framework). The server holds the provider session and runs the mutations.
<!-- endif -->
<!-- if spa -->
- **Frontend:** single-page app. The provider SDK runs in the browser.
<!-- endif -->

## DATA STRATEGY
<!-- if ssr -->
- **Mutations:** create, update and delete from the server, with the provider client built for the server. Do not call the provider from client components for writes.
- **Reads:** fetch on the server where the framework allows it; the client SDK is only for what must be live in the browser.
- **Session:** the server client reads the user's session from cookies. Never trust an id sent by the client.
<!-- endif -->
<!-- if spa -->
- **Reads and writes:** the browser SDK talks to the provider directly, so the provider's access rules are the ONLY barrier: nothing in the client protects the data.
- **Privileged work** (payments, admin actions, anything that needs elevated credentials, third-party secrets) goes in the provider's server functions, never in the frontend.
<!-- endif -->
<!-- if supabase -->
- **Access rules:** Row Level Security (RLS) is enabled on every table of an exposed schema, with policies tested by `supabase test db`.
- **Keys:** the publishable key (`sb_publishable_...`, formerly `anon`) may ship to the browser. The secret key (`sb_secret_...`, formerly `service_role`) never leaves a server function.
- **Server functions:** Edge Functions in `supabase/functions/<module>/`.
<!-- endif -->
<!-- if firebase -->
- **Access rules:** Firestore and Storage rules deny by default (`allow read, write: if false;`) and open only what each feature needs; they are tested in the emulator.
- **App Check** is enabled for the services the app uses. The web `apiKey` only identifies the project; it is not a secret and it is not protection either.
- **Server functions:** Cloud Functions in `functions/src/<module>/`. Admin SDK and service-account credentials exist only on the server.
<!-- endif -->
- **Auth:** managed by the provider; the frontend never stores passwords or issues tokens.
- **SDK imports:** the provider SDK is imported only from the `data-access` layer of a feature and from the single provider client in `shared`. `rapid arch check` enforces it.

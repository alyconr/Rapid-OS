# 🏗️ TOPOLOGY: BACKEND ONLY

## ARCHITECTURE
- **Type:** API or service with no interface of its own.
- **Frontend:** NONE. Do not create pages, components or a UI build.
- **Backend:** The only component; it lives at the project root (no `backend/` folder).
- **Database:** Owned by the backend (PostgreSQL / MongoDB), reached through its modules.
- **Communication:** REST API, GraphQL, events or webhooks consumed by other systems.

## RESTRICTIONS
- Do not add a frontend framework, bundler or static pages.
- Publish the API contract (OpenAPI or equivalent) so consumers can build against it.
- Validate every input at the boundary: there is no UI to constrain it.

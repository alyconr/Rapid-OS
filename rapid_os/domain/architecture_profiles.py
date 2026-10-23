"""The modular-monolith rule in the idiom of each stack. Pure data: no I/O.

The responsibilities never change: an entry (HTTP, events), an application (use cases and ports),
a domain (rules without a framework), an infrastructure (persistence and adapters) and the public
contract of the module. What changes between stacks is the name of the folder or package that
holds each one and the mechanism that makes the contract public. Each profile below gives the
machine-readable rule (`architecture.json`) and the text the agent reads (`architecture.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

BACKEND_LAYERS: Mapping[str, list[str]] = {
    "api": ["application", "domain"],
    "application": ["domain"],
    "domain": [],
    "infrastructure": ["application", "domain"],
}
FRONTEND_LAYERS: Mapping[str, list[str]] = {
    "ui": ["state", "model"],
    "state": ["data-access", "model"],
    "data-access": ["model"],
    "model": [],
}
CANONICAL = {
    "api": "Entrada (HTTP, eventos)",
    "application": "Aplicación (casos de uso y puertos)",
    "domain": "Dominio (reglas sin framework)",
    "infrastructure": "Infraestructura (persistencia y adaptadores)",
    "contract": "Contrato público del módulo",
    "ui": "Interfaz (componentes)",
    "state": "Estado de la funcionalidad",
    "data-access": "Acceso a datos (llamadas a la API)",
    "model": "Modelo (tipos y reglas de presentación)",
}
ROLE_TEXT = {
    "api": "entrada: HTTP, eventos y esquemas de entrada y salida",
    "application": "casos de uso; aquí viven los puertos si el módulo es hexagonal",
    "domain": "entidades, reglas e invariantes, sin framework web ni ORM",
    "infrastructure": "repositorios, ORM y adaptadores de sistemas externos",
    "ui": "componentes de la funcionalidad",
    "state": "estado de la funcionalidad",
    "data-access": "llamadas a la API",
    "model": "tipos y reglas de presentación, sin framework de interfaz",
}
PYTHON_INIT_NOTE = (
    "El `__init__.py` de un módulo está vacío o solo reexporta desde su `public.py`; nunca importa de `api`, "
    "`application`, `domain` ni `infrastructure`. Si no, importar el paquete del módulo sería una puerta trasera a sus capas."
)
BACKEND_ROLES = ("api", "application", "domain", "infrastructure")
FRONTEND_ROLES = ("ui", "state", "data-access", "model")

PY_FORBIDDEN = ["fastapi", "sqlalchemy", "starlette", "httpx"]
DJANGO_FORBIDDEN = ["django", "rest_framework"]
TS_FORBIDDEN = ["next", "react", "express", "@prisma/client"]
NEST_FORBIDDEN = ["@nestjs", "typeorm", "@prisma/client", "express"]
FASTIFY_FORBIDDEN = ["fastify", "@fastify", "@prisma/client", "pg"]
GO_FORBIDDEN = ["net/http", "database/sql", "gorm.io", "github.com/gin-gonic"]
RUST_FORBIDDEN = ["axum", "sqlx", "diesel", "tokio_postgres", "tower"]
JAVA_FORBIDDEN = ["org.springframework", "jakarta.persistence", "jakarta.servlet", "javax.persistence"]
CSHARP_FORBIDDEN = ["Microsoft.AspNetCore", "Microsoft.EntityFrameworkCore", "Npgsql"]
PHP_FORBIDDEN = ["Illuminate", "Symfony\\Component\\HttpFoundation"]
UI_FORBIDDEN = ["react", "react-dom", "vue", "svelte", "@angular/core", "next", "nuxt", "@sveltejs/kit", "astro"]


@dataclass(frozen=True)
class RuleSpec:
    """One rule of `architecture.json` plus the text that explains it."""

    component: str  # backend | frontend
    language: str
    modules_root: str
    shared_root: str
    public_entry: str
    roles: Mapping[str, tuple[str, ...]]
    forbidden: tuple[str, ...]
    tree: str
    module_pattern: str
    public_contract: str
    layers: Mapping[str, list[str]] = None  # type: ignore[assignment]
    pure_layer: str = "domain"
    public_policy: str = "entry"
    public_dirs: tuple[str, ...] = ()
    namespace_root: str = ""
    aliases: Mapping[str, str] = None  # type: ignore[assignment]
    delegate: str = ""
    complementary: str = ""
    notes: str = ""

    def to_dict(self, root: str = "") -> dict:
        data: dict = {
            "language": self.language,
            "component": self.component,
            "modules_root": self.modules_root,
            "shared_root": self.shared_root,
            "public_entry": self.public_entry,
            "module_pattern": self.module_pattern,
            "public_contract": self.public_contract,
            "public_policy": self.public_policy,
            "layers": {k: list(v) for k, v in (self.layers or BACKEND_LAYERS).items()},
            "roles": {k: (v[0] if len(v) == 1 else list(v)) for k, v in self.roles.items()},
            "domain_forbidden_imports": list(self.forbidden),
        }
        if self.pure_layer != "domain":
            data["pure_layer"] = self.pure_layer
        if self.public_dirs:
            data["public_dirs"] = list(self.public_dirs)
        if self.namespace_root:
            data["namespace_root"] = self.namespace_root
        if self.aliases:
            data["aliases"] = dict(self.aliases)
        if self.delegate:
            data["delegate"] = self.delegate
        if self.complementary:
            data["complementary"] = self.complementary
        if root:
            data["root"] = root
        return data


def _roles(api, application, domain, infrastructure) -> dict[str, tuple[str, ...]]:
    def one(value):
        return (value,) if isinstance(value, str) else tuple(value)

    return {
        "api": one(api),
        "application": one(application),
        "domain": one(domain),
        "infrastructure": one(infrastructure),
    }


FRONTEND_ROLE_DIRS = {"ui": ("ui",), "state": ("state",), "data-access": ("data-access",), "model": ("model",)}


def _feature_rule(features: str, shared: str, aliases: Mapping[str, str], extra_tree: str = "", notes: str = "") -> RuleSpec:
    base = features.rsplit("/", 1)[0]
    tree = (
        f"{base}/\n"
        f"  shared/                      # componentes y utilidades mínimas, sin importar funcionalidades\n"
        f"  features/\n"
        f"    <f>/\n"
        f"      index.ts                 # único punto público de la funcionalidad\n"
        f"      ui/                      # componentes\n"
        f"      state/                   # estado\n"
        f"      data-access/             # llamadas a la API\n"
        f"      model/                   # tipos y reglas de presentación\n"
    ) + extra_tree
    return RuleSpec(
        component="frontend", language="typescript", modules_root=features, shared_root=shared,
        public_entry="index.ts", roles=FRONTEND_ROLE_DIRS, forbidden=tuple(UI_FORBIDDEN),
        tree=tree, module_pattern=f"{features}/<f>/", public_contract="index.ts",
        layers=FRONTEND_LAYERS, pure_layer="model", aliases=aliases, notes=notes,
    )


def _ts_modules(root: str, shared: str, forbidden, api_dir="api", tree_extra="", public="index.ts", language="typescript") -> RuleSpec:
    tree = (
        f"{root.rsplit('/', 1)[0]}/\n"
        f"  shared/                      # configuración, cliente de BD, errores base\n"
        f"  modules/\n"
        f"    <m>/\n"
        f"      {public.replace('{m}', '<m>'):<24} # único punto público del módulo\n"
        f"      {api_dir}/\n"
        f"      application/             # casos de uso (y puertos si es hexagonal)\n"
        f"      domain/                  # entidades, reglas, invariantes\n"
        f"      infrastructure/          # repositorios, ORM, adaptadores\n"
    ) + tree_extra
    return RuleSpec(
        component="backend", language=language, modules_root=root, shared_root=shared, public_entry=public,
        roles=_roles(api_dir, "application", "domain", "infrastructure"), forbidden=tuple(forbidden),
        tree=tree, module_pattern=f"{root}/<m>/", public_contract=public.replace("{m}", "<m>"),
        aliases={"@/": "src/"},
    )


PYTHON_TREE = """app/
  main.py                      # composición: crea la app y conecta los módulos
  shared/                      # configuración, sesión de BD, errores base
  modules/
    <m>/
      public.py                # único punto público del módulo
      api/                     # rutas y esquemas
      application/             # casos de uso (y puertos si es hexagonal)
      domain/                  # entidades, reglas, invariantes
      infrastructure/          # repositorios, ORM, adaptadores
"""

DJANGO_TREE = """manage.py
config/                        # settings y urls: la composición
apps/
  shared/                      # utilidades mínimas, sin importar apps de negocio
  <m>/                         # una app de Django por módulo
    public.py                  # único punto público de la app
    api/                       # vistas y serializers
    services/                  # casos de uso
    domain/                    # reglas puras, sin Django
    models.py                  # ORM: infraestructura
"""

GO_TREE = """cmd/<app>/main.go             # composición
internal/                      # el compilador impide importar internal/ desde fuera del módulo de Go
  shared/                      # configuración y utilidades mínimas
  <m>/
    <m>.go                     # paquete raíz del módulo = contrato público (identificadores exportados)
    http/                      # entrada: handlers y rutas
    app/                       # casos de uso (y puertos)
    domain/                    # entidades y reglas, sin net/http ni database/sql
    store/                     # persistencia y adaptadores (también puede llamarse adapters/)
"""

RUST_TREE = """src/
  main.rs                      # composición: crea el router y conecta los módulos
  shared/                      # configuración y errores base
  modules/
    mod.rs
    <m>/
      mod.rs                   # `pub use` = contrato público; el resto es pub(crate)
      routes.rs                # entrada
      application.rs           # casos de uso (y puertos)
      domain.rs                # entidades y reglas
      infra.rs                 # persistencia y adaptadores
"""

RAILS_TREE = """packs/
  <m>/                         # un pack de packwerk por módulo
    package.yml                # enforce_dependencies: true
    app/
      controllers/             # entrada
      use_cases/               # casos de uso
      domain/                  # POROs: reglas sin Rails
      models/                  # Active Record: infraestructura
      public/                  # contrato público del pack
"""

DOTNET_TREE = """src/
  Host/                        # composición: Program.cs
  Shared/                      # utilidades mínimas
  Modules/
    <M>/
      <M>.Api/                 # entrada
      <M>.Application/         # casos de uso (y puertos)
      <M>.Domain/              # entidades y reglas
      <M>.Infrastructure/      # EF Core y adaptadores
      <M>.Contracts/           # contrato público del módulo
"""

JAVA_TREE = """src/main/{lang}/com/example/app/    # sustituye com.example.app por tu organización y aplicación
  shared/                      # configuración y utilidades mínimas
  <m>/                         # paquete del módulo: sus tipos públicos son el contrato (Spring Modulith)
    web/                       # entrada: controladores
    application/               # casos de uso (y puertos)
    domain/                    # entidades y reglas
    infrastructure/            # persistencia y adaptadores
"""

LARAVEL_TREE = """app/
  Shared/                      # utilidades mínimas
  Modules/
    <M>/
      <M>ServiceProvider.php   # un ServiceProvider por módulo
      Http/                    # entrada: controladores y requests
      Application/             # casos de uso (y puertos)
      Domain/                  # entidades y reglas
      Infrastructure/          # Eloquent y adaptadores
      Contracts/               # contrato público del módulo
"""


def _spring(lang: str) -> RuleSpec:
    root = f"src/main/{lang}/com/example/app"
    return RuleSpec(
        component="backend", language="java" if lang == "java" else "kotlin", modules_root=root,
        shared_root=f"{root}/shared", public_entry="(paquete raíz del módulo)",
        roles=_roles("web", "application", "domain", "infrastructure"), forbidden=tuple(JAVA_FORBIDDEN),
        tree=JAVA_TREE.replace("{lang}", lang), module_pattern=f"{root}/<m>/",
        public_contract="los tipos del paquete raíz del módulo (Spring Modulith)",
        public_policy="root", namespace_root="com.example.app",
        complementary="Spring Modulith: `ApplicationModules.of(Application.class).verify()` como test complementario",
        notes="Cambia `com.example.app` por tu paquete real en `architecture.json` (`namespace_root`, `modules_root`, `shared_root`).",
    )


BACKEND_RULES: Mapping[str, RuleSpec] = {
    "python-fastapi": RuleSpec(
        component="backend", language="python", modules_root="app/modules", shared_root="app/shared",
        public_entry="public.py", roles=_roles("api", "application", "domain", "infrastructure"),
        forbidden=tuple(PY_FORBIDDEN), tree=PYTHON_TREE, module_pattern="app/modules/<m>/",
        public_contract="public.py", notes=PYTHON_INIT_NOTE,
    ),
    "python-django": RuleSpec(
        component="backend", language="python", modules_root="apps", shared_root="apps/shared",
        public_entry="public.py", roles=_roles("api", "services", "domain", ("models", "infrastructure")),
        forbidden=tuple(DJANGO_FORBIDDEN), tree=DJANGO_TREE, module_pattern="apps/<m>/",
        public_contract="public.py",
        notes="Cada módulo es una app de Django dentro de `apps/`; `models.py` (o el paquete `models/`) es la infraestructura. "
        + PYTHON_INIT_NOTE,
    ),
    "node-nestjs": RuleSpec(
        component="backend", language="typescript", modules_root="src/modules", shared_root="src/shared",
        public_entry="{m}.module.ts|index.ts", roles=_roles("controllers", "application", "domain", "infrastructure"),
        forbidden=tuple(NEST_FORBIDDEN),
        tree="""src/
  main.ts
  app.module.ts                # composición
  shared/                      # configuración y errores base
  modules/
    <m>/
      <m>.module.ts            # exports = contrato público del módulo
      controllers/             # entrada
      application/             # casos de uso (providers) y puertos
      domain/                  # entidades y reglas, sin decoradores de Nest
      infrastructure/          # repositorios, ORM y adaptadores
""",
        module_pattern="src/modules/<m>/", public_contract="<m>.module.ts (exports)", aliases={"@/": "src/"},
    ),
    "node-fastify": _ts_modules(
        "src/modules", "src/shared", FASTIFY_FORBIDDEN, api_dir="routes",
    ),
    "go": RuleSpec(
        component="backend", language="go", modules_root="internal", shared_root="internal/shared",
        public_entry="(paquete raíz del módulo)",
        roles=_roles("http", "app", "domain", ("store", "adapters")), forbidden=tuple(GO_FORBIDDEN),
        tree=GO_TREE, module_pattern="internal/<m>/", public_contract="paquete raíz del módulo (identificadores exportados)",
        public_policy="root",
        notes="`internal/` es una regla del compilador de Go: nada fuera del módulo de Go puede importarlo.",
    ),
    "rust-axum": RuleSpec(
        component="backend", language="rust", modules_root="src/modules", shared_root="src/shared",
        public_entry="mod.rs", roles=_roles("routes", "application", "domain", "infra"),
        forbidden=tuple(RUST_FORBIDDEN), tree=RUST_TREE, module_pattern="src/modules/<m>/",
        public_contract="mod.rs (pub use)", public_policy="root",
        notes="Usa `pub(crate)` para todo lo que no sea contrato. Si el sistema crece, cada módulo puede ser un crate del workspace.",
    ),
    "ruby-rails": RuleSpec(
        component="backend", language="ruby", modules_root="packs", shared_root="packs/shared",
        public_entry="app/public/", roles=_roles("controllers", "use_cases", "domain", "models"),
        forbidden=(), tree=RAILS_TREE, module_pattern="packs/<m>/", public_contract="app/public/ del pack",
        public_policy="root", delegate="packwerk",
        complementary="packwerk: `bin/packwerk check` (el gate delega en él)",
        notes="Rails carga el código por convención y no tiene imports que leer: `rapid arch check` ejecuta `bin/packwerk check`.",
    ),
    "dotnet-aspnetcore": RuleSpec(
        component="backend", language="csharp", modules_root="src/Modules", shared_root="src/Shared",
        public_entry="{m}.Contracts", roles=_roles("{m}.Api", "{m}.Application", "{m}.Domain", "{m}.Infrastructure"),
        forbidden=tuple(CSHARP_FORBIDDEN), tree=DOTNET_TREE, module_pattern="src/Modules/<M>/",
        public_contract="el proyecto <M>.Contracts", public_policy="root", public_dirs=("{m}.Contracts",),
        namespace_root="App",
        complementary="NetArchTest: pruebas arquitectónicas con `NetArchTest.Rules` como test complementario",
        notes="Las referencias entre proyectos (`.csproj`) imponen las capas; cambia `namespace_root` si tu espacio de nombres raíz no es `App`.",
    ),
    "java-spring-boot": _spring("java"),
    "kotlin-spring-boot": _spring("kotlin"),
    "php-laravel": RuleSpec(
        component="backend", language="php", modules_root="app/Modules", shared_root="app/Shared",
        public_entry="Contracts", roles=_roles("Http", "Application", "Domain", "Infrastructure"),
        forbidden=tuple(PHP_FORBIDDEN), tree=LARAVEL_TREE, module_pattern="app/Modules/<M>/",
        public_contract="Contracts/ del módulo", public_policy="root", public_dirs=("Contracts",),
        namespace_root="App",
        complementary="Deptrac: `vendor/bin/deptrac` como test complementario",
        notes="Cada módulo registra sus bindings en su propio ServiceProvider (`bootstrap/providers.php`).",
    ),
    # Frameworks that also host the backend: their server code is a TypeScript modular monolith.
    "nextjs": _ts_modules("src/modules", "src/shared", TS_FORBIDDEN, tree_extra="  app/                         # rutas de Next.js: Route Handlers y páginas, solo importan el punto público\n"),
    "nuxt": _ts_modules("server/modules", "server/shared", ["h3", "nitropack", "@prisma/client", "pg"]),
    "sveltekit": _ts_modules("src/lib/server/modules", "src/lib/server/shared", ["@sveltejs/kit", "@prisma/client", "pg"]),
}

FRONTEND_RULES: Mapping[str, RuleSpec] = {
    "react-vite": _feature_rule("src/features", "src/shared", {"@/": "src/"}),
    "nextjs": _feature_rule("src/features", "src/shared", {"@/": "src/"}, notes="`src/app/` contiene las rutas de Next.js y solo importa el `index.ts` de cada funcionalidad."),
    "angular": _feature_rule("src/app/features", "src/app/shared", {}, notes="Los imports son relativos o por ruta absoluta desde `src/`."),
    "vue-vite": _feature_rule("src/features", "src/shared", {"@/": "src/"}),
    "nuxt": _feature_rule("app/features", "app/shared", {"~/": "app/", "@/": "app/"}),
    "svelte-vite": _feature_rule("src/features", "src/shared", {"@/": "src/"}),
    "sveltekit": _feature_rule("src/lib/features", "src/lib/shared", {"$lib/": "src/lib/"}),
    "astro": _feature_rule("src/features", "src/shared", {"@/": "src/"}),
}

# Stacks that get no rule: `generic`, `docs-modern` and a stack the person wrote themselves.

"""The topology guide of a project: a template with regions chosen by the stacks decided. Pure: no I/O.

Most topologies are one fixed text. `fullstack-baas` depends on two decisions: how the frontend runs
(rendered on a server, or a single-page app that talks to the provider from the browser) and which
BaaS provider is used. Its template marks regions with `<!-- if NAME -->` / `<!-- endif -->`, the
same markers the security baseline uses.
"""

from __future__ import annotations

from typing import Mapping

from rapid_os.domain.security import render_conditionals

# Frontends that run code on a server: the provider client can live there for the mutations.
SSR_FRONTENDS = frozenset({"nextjs", "nuxt", "sveltekit"})
# Frontends that are a browser-only app: the SDK runs in the client and the provider's access rules
# are the only barrier. A frontend the catalog does not know is read as the stricter case.
SPA_FRONTENDS = frozenset({"react-vite", "vue-vite", "svelte-vite", "angular", "astro"})
BAAS_PROVIDERS = ("supabase", "firebase")
DYNAMIC_TOPOLOGIES = frozenset({"fullstack-baas"})


def topology_conditions(stacks: Mapping[str, str]) -> frozenset[str]:
    """The regions of the topology template that hold for `{component: stack_id}`."""
    active = {"ssr" if stacks.get("frontend") in SSR_FRONTENDS else "spa"}
    provider = stacks.get("baas")
    if provider in BAAS_PROVIDERS:
        active.add(provider)
    else:
        active.add("provider-undecided")
    return frozenset(active)


def render_topology(template: str, topology_id: str, stacks: Mapping[str, str]) -> str:
    """The text of `standards/topology.md`; only the dynamic topologies change with the stacks."""
    if topology_id not in DYNAMIC_TOPOLOGIES:
        return template
    return render_conditionals(template, topology_conditions(stacks))


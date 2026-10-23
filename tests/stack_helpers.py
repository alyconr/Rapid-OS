"""A complete set of stacks for a test state, whatever stack id the test thinks in.

A project decides one stack per component of its topology. Most tests only care about the stack
they name, so this fills the other component with a catalog stack and accepts the stack ids of
before the component catalog (`python-api`, `web-modern`...).
"""

from __future__ import annotations

from rapid_os.domain.setup import STACK_COMPONENTS, StackChoice
from rapid_os.domain.stack_aliases import LEGACY_STACKS

# `generic` has no language of its own: it adds neither a second CI workflow nor an architecture rule.
FRONTEND_FALLBACK = "generic"
BACKEND_FALLBACK = "generic"


def complete_stacks(stack_id: str, source: str = "catalog") -> dict[str, StackChoice]:
    if stack_id in ("generic", "custom"):
        choice = StackChoice(stack_id, "generic" if stack_id == "generic" else "custom")
        return {c: choice for c in STACK_COMPONENTS}
    if stack_id == "docs-modern":
        return {"docs": StackChoice(stack_id, source)}
    legacy = LEGACY_STACKS.get(stack_id)
    if legacy is not None:
        stacks = {
            c: StackChoice(s, "catalog", legacy.profile if c == "frontend" else None)
            for c, s in legacy.stacks.items()
        }
    else:
        stacks = {}
        component = "frontend" if stack_id in {
            "react-vite", "angular", "vue-vite", "svelte-vite", "astro", "nextjs", "nuxt", "sveltekit"
        } else "backend"
        stacks[component] = StackChoice(stack_id, source)
        if stack_id in ("nextjs", "nuxt", "sveltekit"):
            stacks["backend"] = StackChoice(stack_id, source)
    if "frontend" not in stacks:
        stacks["frontend"] = StackChoice(FRONTEND_FALLBACK, "generic")
    if "backend" not in stacks:
        stacks["backend"] = StackChoice(BACKEND_FALLBACK, "generic")
    return stacks

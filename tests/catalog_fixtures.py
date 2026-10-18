import json
from pathlib import Path

ALL_BUT_DOC_SITE = ["front-end-only", "fullstack-baas", "fullstack-separated"]


def write_catalog_sidecars(templates: Path) -> None:
    """Write a valid sidecar next to every stack/topology Markdown in a fixture."""
    topologies = sorted(p.stem for p in (templates / "topologies").glob("*.md"))
    for topology in topologies:
        data = {
            "schema_version": 1,
            "id": topology,
            "summary": topology,
            "fits": [],
            "avoid_if": [],
        }
        (templates / "topologies" / f"{topology}.json").write_text(json.dumps(data), encoding="utf-8")
    for stack_file in sorted((templates / "stacks").glob("*.md")):
        stack = stack_file.stem
        compatible = ["doc-site"] if stack == "docs-modern" else ALL_BUT_DOC_SITE
        compatible = [t for t in compatible if t in topologies] or topologies
        data = {
            "schema_version": 1,
            "id": stack,
            "summary": stack,
            "language": "any",
            "fits": [],
            "avoid_if": [],
            "compatible_topologies": compatible,
            "default_topology": compatible[0],
        }
        (templates / "stacks" / f"{stack}.json").write_text(json.dumps(data), encoding="utf-8")

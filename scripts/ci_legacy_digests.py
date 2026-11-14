"""SHA-256 of every CI workflow body that the released versions (v3.2.0-rc.1..rc.3) could write.

Each tag's own templates and its own `rapid_os/domain/security.py` render the combinations of language,
archetype, primary and BaaS provider. Line endings are normalized to LF before hashing.
"""
import hashlib
import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(sys.argv[1])
TAGS = ("v3.2.0-rc.1", "v3.2.0-rc.2", "v3.2.0-rc.3")


def show(tag, path):
    return subprocess.run(["git", "show", f"{tag}:{path}"], cwd=REPO, capture_output=True, check=True).stdout.decode("utf-8")


digests = {}
for tag in TAGS:
    source = show(tag, "rapid_os/domain/security.py")
    with tempfile.TemporaryDirectory() as tmp:
        module_path = Path(tmp) / "sec.py"
        module_path.write_text(source, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(f"sec_{tag.replace('.', '_').replace('-', '_')}", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    render = module.render_ci_workflow
    params = inspect.signature(render).parameters
    names = subprocess.run(["git", "ls-tree", "--name-only", tag, "templates/ci/"], cwd=REPO, capture_output=True, check=True).stdout.decode().split()
    for name in names:
        language = Path(name).name.removesuffix("-security.yml")
        template = show(tag, name)
        for archetype in ("mvp", "corporate"):
            for primary in (True, False):
                for stacks in ([], ["supabase"], ["firebase"], ["supabase", "firebase"]):
                    for lang in (language, None):
                        kwargs = {"archetype": archetype}
                        if "primary" in params:
                            kwargs["primary"] = primary
                        if "language" in params:
                            kwargs["language"] = lang
                        if "stack_ids" in params:
                            kwargs["stack_ids"] = stacks
                        body = render(template, **kwargs).replace("\r\n", "\n")
                        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
                        digests.setdefault(digest, sorted({tag}))
                        if tag not in digests[digest]:
                            digests[digest] = sorted(set(digests[digest]) | {tag})

print(json.dumps(sorted(digests), indent=0))
print(len(digests), file=sys.stderr)

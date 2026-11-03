"""Runs only inside Linux images (Python 3.9 compatible)."""
import importlib.abc
import importlib.machinery
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys


def module_name(root, relative):
    path = root / relative
    parts = [] if path.name == "__init__.py" else [path.stem]
    parent = path.parent
    while parent != root and (parent / "__init__.py").is_file():
        parts.insert(0, parent.name)
        parent = parent.parent
    if not parts or not all(p.isidentifier() for p in parts):
        raise ValueError("Cannot derive importable module: " + relative)
    return ".".join(parts), str(parent)


def verify(root, targets):
    mapping = {}
    for relative in targets:
        module, source_root = module_name(root, relative)
        # find_spec checks origins without importing the edited target itself.
        spec = importlib.util.find_spec(module)
        expected = str((root / relative).resolve())
        if spec is None or not spec.origin or str(Path(spec.origin).resolve()) != expected:
            raise RuntimeError("Import origin mismatch: %s -> %s, expected %s" % (module, getattr(spec, "origin", None), expected))
        mapping[module] = expected
    # Editable installs must refer to /repo rather than a second pristine tree.
    editable = []
    for dist in importlib.metadata.distributions():
        text = dist.read_text("direct_url.json")
        if text:
            value = json.loads(text)
            if value.get("dir_info", {}).get("editable"):
                editable.append(value["url"])
    egg_links = []
    for entry in sys.path:
        if entry and Path(entry).is_dir() and "site-packages" in entry:
            for link in Path(entry).glob("*.egg-link"):
                egg_links.append(link.read_text().splitlines()[0])
    if not any(u.rstrip("/") == "file:///repo" for u in editable) and "/repo" not in egg_links:
        raise RuntimeError("No editable installation rooted at /repo")
    return {"modules": mapping, "editable_urls": editable, "egg_links": egg_links}


class OriginGuard(importlib.abc.MetaPathFinder):
    def __init__(self, modules):
        self.modules = modules
        self.observed = []
        self.errors = []

    def find_spec(self, fullname, path=None, target=None):
        if fullname not in self.modules:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None:
            for finder in sys.meta_path:
                if finder is self or finder is importlib.machinery.PathFinder:
                    continue
                spec = finder.find_spec(fullname, path, target)
                if spec is not None:
                    break
        origin = str(Path(spec.origin).resolve()) if spec and spec.origin else None
        if origin != self.modules[fullname]:
            message = "Import origin mismatch: %s -> %s" % (fullname, origin)
            self.errors.append(message)
            raise ImportError(message)
        self.observed.append({"module": fullname, "origin": origin})
        return None  # preserve pytest/import instrumentation


if __name__ == "__main__":
    root = Path("/repo")
    targets = json.loads(Path("/opt/erb/targets.json").read_text())
    print(json.dumps(verify(root, targets), indent=2))

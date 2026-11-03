"""Runs only inside Linux images (Python 3.9 compatible)."""
import importlib.abc
import importlib.machinery
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys


def module_names(relative):
    path = Path(relative)
    parts = list(path.parts[:-1]) + ([] if path.name == "__init__.py" else [path.stem])
    names = [".".join(parts)]
    if parts and parts[0] in {"src", "lib"}:
        names.append(".".join(parts[1:]))
    return [n for n in names if n]


def resolve_spec(name):
    """Resolve namespace/package paths without executing their __init__.py.
    Some benchmark packages intentionally replace sys.modules entries at import.
    """
    search = None
    prefix = []
    for part in name.split("."):
        prefix.append(part)
        fullname = ".".join(prefix)
        # Unqualified lookup against an explicit parent path avoids NamespacePath
        # requiring a parent in sys.modules (we deliberately do not import it).
        spec = importlib.machinery.PathFinder.find_spec(part, search)
        if spec is None:
            for finder in sys.meta_path:
                if finder is importlib.machinery.PathFinder:
                    continue
                spec = finder.find_spec(fullname, search, None)
                if spec is not None:
                    break
        if spec is None:
            return None
        search = list(spec.submodule_search_locations) if spec.submodule_search_locations is not None else None
        if search is None and fullname != name:
            return None
    return spec


def verify(root, targets):
    mapping = {}
    scripts = []
    for relative in targets:
        expected = str((root / relative).resolve())
        found = False
        for module in module_names(relative):
            spec = resolve_spec(module)
            if spec and spec.origin:
                if str(Path(spec.origin).resolve()) != expected:
                    raise RuntimeError("Import origin mismatch: %s -> %s, expected %s" % (module, spec.origin, expected))
                mapping[module] = expected
                found = True
        if not found:
            # Standalone scripts/examples need not be installed/importable. Their
            # exact target bytes are still verified and exec is observed at run time.
            if not Path(expected).is_file():
                raise RuntimeError("Missing target script: " + expected)
            scripts.append(expected)
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
    if (not any(u.rstrip("/") == "file:///repo" or u.startswith("file:///repo/") for u in editable)
            and not any(u == "/repo" or u.startswith("/repo/") for u in egg_links)):
        raise RuntimeError("No editable installation rooted at /repo")
    return {"modules": mapping, "scripts": scripts, "editable_urls": editable, "egg_links": egg_links}


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

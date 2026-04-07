#!/usr/bin/env python3
"""MemTree Coordinator: scan all configured services' import graphs, output chains.json + shared_files.json.

Reads service definitions from memtree.config.yaml to build per-service dependency
graphs, trace entry-point chains, and identify shared/hot files across the codebase.

Usage:
    python3 scripts/coordinator-scan.py
    python3 scripts/coordinator-scan.py --config path/to/memtree.config.yaml
"""
from __future__ import annotations
import json, re, os, sys
from pathlib import Path
from collections import defaultdict


def load_config(config_path: Path | None = None) -> dict:
    """Load memtree.config.yaml, falling back to example if missing."""
    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML is required. Install with: pip install pyyaml")
        sys.exit(1)

    if config_path is None:
        config_path = Path("memtree.config.yaml")
    if not config_path.exists():
        example = config_path.parent / "memtree.config.example.yaml"
        if example.exists():
            print(f"WARNING: {config_path} not found. Using {example} as fallback.")
            config_path = example
        else:
            print(f"ERROR: {config_path} not found. Copy memtree.config.example.yaml to memtree.config.yaml first.")
            sys.exit(1)
    return yaml.safe_load(config_path.read_text())


def build_services(config: dict) -> tuple[dict[str, dict], Path, set[str]]:
    """Build SERVICES dict from config, resolving paths relative to project root."""
    project_root = Path(config.get("project", {}).get("root", ".")).resolve()
    exclude = set(config.get("exclude", [
        "__pycache__", "node_modules", ".nuxt", "dist", "build", "tests", "migrations", ".git"
    ]))

    services = {}
    for svc in config.get("services", []):
        name = svc["name"]
        svc_path = project_root / svc["path"]
        services[name] = {
            "root": svc_path,
            "lang": normalize_lang(svc.get("lang", "python")),
            "entry_pattern": svc.get("entry_pattern", "**/*.py"),
        }
    return services, project_root, exclude


def normalize_lang(lang: str) -> str:
    """Normalize language identifiers to internal categories."""
    lang = lang.lower()
    if lang in ("python", "py"):
        return "python"
    if lang in ("vue", "nuxt"):
        return "vue_ts"
    if lang in ("tsx", "react", "next"):
        return "tsx"
    if lang in ("ts", "typescript", "javascript", "js"):
        return "ts"
    return lang


LANG_EXTENSIONS: dict[str, list[str]] = {
    "python": [".py"],
    "vue_ts": [".vue", ".ts", ".tsx"],
    "tsx": [".ts", ".tsx"],
    "ts": [".ts", ".tsx"],
}


def list_source_files(root: Path, lang: str, exclude_dirs: set[str]) -> list[Path]:
    """List all source files for a service."""
    exts = LANG_EXTENSIONS.get(lang, [".py"])
    files = []
    for ext in exts:
        for f in root.rglob(f"*{ext}"):
            if any(p in f.parts for p in exclude_dirs):
                continue
            if f.name.endswith(".d.ts") or f.name.endswith(".map"):
                continue
            files.append(f)
    return sorted(files)


def extract_python_imports(filepath: Path, root: Path) -> list[str]:
    """Extract project-internal imports from a Python file."""
    try:
        content = filepath.read_text(errors="replace")
    except Exception:
        return []
    imports = []
    for line in content.split("\n"):
        line = line.strip()
        # from app.routers.trading import ...
        m = re.match(r'from\s+(app\..+?)\s+import', line)
        if m:
            mod = m.group(1).replace("app.", "").replace(".", "/")
            candidate = root / (mod + ".py")
            if candidate.exists():
                imports.append(str(candidate.relative_to(root)))
            else:
                candidate_dir = root / mod / "__init__.py"
                if candidate_dir.exists():
                    imports.append(str(candidate_dir.relative_to(root)))
            continue
        # from .services.xxx import ...
        m = re.match(r'from\s+(\.\S+)\s+import', line)
        if m:
            rel_mod = m.group(1)
            parent = filepath.parent
            parts = rel_mod.lstrip(".")
            dots = len(rel_mod) - len(parts)
            for _ in range(dots - 1):
                parent = parent.parent
            mod_path = parts.replace(".", "/")
            candidate = parent / (mod_path + ".py")
            if candidate.exists():
                try:
                    imports.append(str(candidate.relative_to(root)))
                except ValueError:
                    pass
            continue
        # import app.xxx
        m = re.match(r'import\s+(app\..+)', line)
        if m:
            mod = m.group(1).split()[0].replace("app.", "").replace(".", "/")
            candidate = root / (mod + ".py")
            if candidate.exists():
                imports.append(str(candidate.relative_to(root)))
    return imports


def extract_ts_imports(filepath: Path, root: Path) -> list[str]:
    """Extract project-internal imports from TS/Vue files."""
    try:
        content = filepath.read_text(errors="replace")
    except Exception:
        return []
    imports = []
    for m in re.finditer(r'''(?:import|from)\s+.*?['"]([\./~@][^'"]+)['"]''', content):
        raw = m.group(1)
        if raw.startswith("~") or raw.startswith("@"):
            rel = raw.lstrip("~").lstrip("@").lstrip("/")
            resolved = root / rel
        elif raw.startswith("."):
            resolved = (filepath.parent / raw).resolve()
        else:
            continue
        for ext in ["", ".ts", ".tsx", ".vue", "/index.ts", "/index.tsx", "/index.vue"]:
            candidate = Path(str(resolved) + ext)
            if candidate.exists() and candidate.is_file():
                try:
                    imports.append(str(candidate.relative_to(root)))
                except ValueError:
                    pass
                break
    return imports


def extract_imports(filepath: Path, root: Path, lang: str) -> list[str]:
    """Dispatch to language-specific import extractor."""
    if lang == "python":
        return extract_python_imports(filepath, root)
    else:
        return extract_ts_imports(filepath, root)


def build_dependency_graph(service_name: str, cfg: dict, exclude_dirs: set[str]) -> tuple[dict, list[Path]]:
    """Build dependency graph for a service. Returns (graph, all_files)."""
    root = cfg["root"]
    lang = cfg["lang"]
    all_files = list_source_files(root, lang, exclude_dirs)
    graph: dict[str, list[str]] = {}
    for f in all_files:
        rel = str(f.relative_to(root))
        deps = extract_imports(f, root, lang)
        graph[rel] = deps
    return graph, all_files


def find_entry_points(root: Path, pattern: str, all_files: list[Path]) -> list[str]:
    """Find entry point files matching the pattern."""
    entries = []
    for f in sorted(root.glob(pattern)):
        if f.is_file() and f in all_files:
            entries.append(str(f.relative_to(root)))
    return sorted(set(entries))


def trace_chain(entry: str, graph: dict, max_depth: int = 500) -> list[str]:
    """Iterative DFS to trace all dependencies from an entry point. Max depth prevents stack overflow."""
    visited: set[str] = set()
    stack = [entry]
    chain: list[str] = []
    while stack and len(chain) < max_depth:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        chain.append(current)
        for dep in graph.get(current, []):
            if dep not in visited:
                stack.append(dep)
    return chain


def make_chain_prefix(name: str) -> str:
    """Generate a 2-letter chain ID prefix from a service name."""
    # Use first letters of words, or first two chars
    words = re.split(r'[_\-\s]+', name)
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return name[:2].upper()


def main() -> None:
    config_path = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--config" and i < len(sys.argv) - 1:
            config_path = Path(sys.argv[i + 1])

    config = load_config(config_path)
    services, project_root, exclude_dirs = build_services(config)
    shared_threshold = config.get("advanced", {}).get("shared_threshold", 3)

    all_chains: list[dict] = []
    file_ref_count: dict[str, int] = defaultdict(int)
    chain_prefixes: dict[str, str] = {}
    used_prefixes: set[str] = set()

    for svc_name in services:
        prefix = make_chain_prefix(svc_name)
        # Avoid collisions
        if prefix in used_prefixes:
            prefix = svc_name[:2].upper() + str(len(used_prefixes))
        used_prefixes.add(prefix)
        chain_prefixes[svc_name] = prefix

    for svc_name, cfg in services.items():
        root = cfg["root"]
        if not root.exists():
            print(f"SKIP: {svc_name} root not found: {root}")
            continue

        print(f"Scanning {svc_name} ({root})...")
        graph, all_files = build_dependency_graph(svc_name, cfg, exclude_dirs)
        entries = find_entry_points(root, cfg["entry_pattern"], all_files)

        reached: set[str] = set()
        prefix = chain_prefixes[svc_name]

        for i, entry in enumerate(sorted(entries), 1):
            chain_files = trace_chain(entry, graph)
            reached.update(chain_files)

            chain_id = f"{prefix}{i:02d}"
            name_parts = entry.replace(".py", "").replace(".vue", "").replace(".ts", "").replace(".tsx", "")
            chain_name = name_parts.split("/")[-1].replace("_", " ").title()

            chain = {
                "id": chain_id,
                "name": chain_name,
                "service": svc_name,
                "entry": entry,
                "files": chain_files,
                "file_count": len(chain_files),
            }
            all_chains.append(chain)

            for f in chain_files:
                file_ref_count[f"{svc_name}:{f}"] += 1

        # Unreached files -> misc chain
        all_rels = {str(f.relative_to(root)) for f in all_files}
        unreached = sorted(all_rels - reached)
        if unreached:
            misc_chain = {
                "id": f"{prefix}00",
                "name": f"{svc_name} misc",
                "service": svc_name,
                "entry": "__misc__",
                "files": unreached,
                "file_count": len(unreached),
            }
            all_chains.append(misc_chain)

        print(f"  {svc_name}: {len(all_files)} files, {len(entries)} entries, {len(unreached)} misc")

    # Identify shared files (>= threshold chains)
    shared_files = []
    for key, count in sorted(file_ref_count.items(), key=lambda x: -x[1]):
        if count >= shared_threshold:
            svc, path = key.split(":", 1)
            shared_files.append({"path": path, "ref_count": count, "service": svc})

    # Write outputs to .memory/ directory
    memory_dir = Path(config.get("project", {}).get("root", ".")) / ".memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    with open(memory_dir / "chains.json", "w") as f:
        json.dump(all_chains, f, indent=2, ensure_ascii=False)

    shared_output = {
        "shared": shared_files,
        "total_shared": len(shared_files),
        "total_chains": len(all_chains),
        "dedup_savings_pct": round(
            len(shared_files) / max(sum(c["file_count"] for c in all_chains), 1) * 100, 1
        ),
    }
    with open(memory_dir / "shared_files.json", "w") as f:
        json.dump(shared_output, f, indent=2, ensure_ascii=False)

    print(f"\n=== Summary ===")
    print(f"Total chains: {len(all_chains)}")
    print(f"Total shared files (>={shared_threshold} refs): {len(shared_files)}")
    print(f"chains.json written to {memory_dir / 'chains.json'}")
    print(f"shared_files.json written to {memory_dir / 'shared_files.json'}")


if __name__ == "__main__":
    main()

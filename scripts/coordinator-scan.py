#!/usr/bin/env python3
"""MemTree Coordinator: scan all configured services' import graphs, output chains.json + shared_files.json.

Reads service definitions from memtree.config.yaml to build per-service dependency
graphs, trace entry-point chains, and identify shared/hot files across the codebase.

Usage:
    python3 scripts/coordinator-scan.py
    python3 scripts/coordinator-scan.py --config path/to/memtree.config.yaml
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from collections import defaultdict

from memtree_common import (
    load_config,
    normalize_lang,
    extract_python_imports as _common_extract_python_imports,
    extract_ts_imports as _common_extract_ts_imports,
    LANG_EXTENSIONS,
)


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


def extract_imports(filepath: Path, root: Path, lang: str) -> list[str]:
    """Dispatch to language-specific import extractor."""
    if lang == "python":
        return _common_extract_python_imports(filepath, root)
    else:
        return _common_extract_ts_imports(filepath, root)


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

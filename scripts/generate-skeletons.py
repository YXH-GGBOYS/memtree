#!/usr/bin/env python3
"""Generate skeleton .memory/ files for all source files in configured services.

Extracts: imports, function/class definitions, SHA256 hash, layer detection.
These skeletons are later enriched by Agent deep analysis.

Usage:
    python3 scripts/generate-skeletons.py
    python3 scripts/generate-skeletons.py --config path/to/memtree.config.yaml
"""
from __future__ import annotations
import ast, json, re, sys
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

from memtree_common import (
    load_config,
    normalize_lang,
    detect_layer,
    compute_hash,
    build_path_map as _common_build_path_map,
    source_to_memory as _common_source_to_memory,
)


def _build_path_map_with_context(config: dict) -> tuple[dict[str, tuple[str, str]], Path, Path, set[str]]:
    """Wrap common build_path_map with project_root, memory_dir, exclude set."""
    project_root = Path(config.get("project", {}).get("root", ".")).resolve()
    memory_dir = project_root / ".memory"
    exclude = set(config.get("exclude", [
        "__pycache__", "node_modules", ".nuxt", "dist", "build", "tests", "migrations", ".git"
    ]))
    path_map = _common_build_path_map(config)
    return path_map, project_root, memory_dir, exclude


NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_python_info(filepath: Path, root: Path) -> dict:
    """Extract functions, classes, imports from a Python file."""
    try:
        content = filepath.read_text(errors="replace")
        tree = ast.parse(content, filename=str(filepath))
    except (SyntaxError, Exception):
        content = filepath.read_text(errors="replace")
        return {"functions": [], "classes": [], "imports": [], "content_preview": content[:500]}

    functions: list[dict] = []
    classes: list[dict] = []
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            args = []
            for a in node.args.args:
                ann = ""
                if a.annotation:
                    try:
                        ann = f": {ast.unparse(a.annotation)}"
                    except Exception:
                        ann = ""
                args.append(f"{a.arg}{ann}")
            ret = ""
            if node.returns:
                try:
                    ret = f" -> {ast.unparse(node.returns)}"
                except Exception:
                    pass
            prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            functions.append({
                "name": node.name,
                "signature": f"{prefix}def {node.name}({', '.join(args)}){ret}",
                "line": node.lineno,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            })
        elif isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    pass
            classes.append({
                "name": node.name,
                "bases": bases,
                "line": node.lineno,
            })
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
                if mod.startswith("app."):
                    mod_path = mod.replace("app.", "").replace(".", "/")
                    candidate = root / (mod_path + ".py")
                    if candidate.exists():
                        imports.append(str(candidate.relative_to(root)))
                    else:
                        pkg = root / mod_path / "__init__.py"
                        if pkg.exists():
                            imports.append(str(pkg.relative_to(root)))

    return {"functions": functions, "classes": classes, "imports": imports}


def extract_ts_info(filepath: Path, root: Path) -> dict:
    """Extract exports, imports from TS/Vue files."""
    try:
        content = filepath.read_text(errors="replace")
    except Exception:
        return {"functions": [], "imports": []}

    functions: list[dict] = []
    imports: list[str] = []

    # Extract imports
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

    # Extract exported functions/consts
    for m in re.finditer(r'export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)', content):
        functions.append({"name": m.group(1), "signature": m.group(0), "line": content[:m.start()].count("\n") + 1})
    for m in re.finditer(r'export\s+(?:const|let|var)\s+(\w+)', content):
        functions.append({"name": m.group(1), "signature": m.group(0), "line": content[:m.start()].count("\n") + 1})
    # Vue composables
    for m in re.finditer(r'(?:export\s+)?(?:const|function)\s+(use\w+)', content):
        if not any(f["name"] == m.group(1) for f in functions):
            functions.append({"name": m.group(1), "signature": f"composable {m.group(1)}", "line": content[:m.start()].count("\n") + 1})
    # defineProps for Vue
    for m in re.finditer(r'(?:const\s+\w+\s*=\s*)?defineProps<([^>]+)>', content):
        functions.append({"name": "defineProps", "signature": f"defineProps<{m.group(1)[:60]}>", "line": content[:m.start()].count("\n") + 1})

    return {"functions": functions, "imports": imports}


def generate_memory_file(
    filepath: Path,
    root: Path,
    service: str,
    mem_path: str,
    lang: str,
    reverse_deps: dict,
    project_root: Path,
    path_map: dict,
    project_name: str,
    cached_info: dict | None = None,
) -> str:
    """Generate a .memory/ skeleton file for a source file."""
    rel = str(filepath.relative_to(root))
    src_rel = str(filepath.relative_to(project_root))
    layer = detect_layer(rel)
    src_hash = compute_hash(filepath)

    if cached_info is not None:
        info = cached_info
    elif lang == "python":
        info = extract_python_info(filepath, root)
    else:
        info = extract_ts_info(filepath, root)

    # Build depends_on list (memory paths)
    depends_on: list[str] = []
    for imp in info.get("imports", []):
        dep_src = str(root / imp)
        dep_rel = str(Path(dep_src).relative_to(project_root))
        result = _common_source_to_memory(dep_rel, path_map)
        if result:
            depends_on.append(result[0].replace(".md", ""))

    # Build depended_by from reverse deps
    depended_by: list[str] = []
    file_key = str(filepath)
    for dep_file in reverse_deps.get(file_key, []):
        dep_rel2 = str(Path(dep_file).relative_to(project_root))
        result = _common_source_to_memory(dep_rel2, path_map)
        if result:
            depended_by.append(result[0].replace(".md", ""))

    # Generate Quick Ref
    quick_ref_rows = ""
    for fn in info.get("functions", [])[:15]:
        sig = fn.get("signature", fn["name"])
        if len(sig) > 80:
            sig = sig[:77] + "..."
        quick_ref_rows += f"| {fn['name']} | `{sig}` | — |\n"
    for cls in info.get("classes", [])[:5]:
        bases_str = ", ".join(cls.get("bases", []))
        quick_ref_rows += f"| {cls['name']} | class({bases_str}) | — |\n"

    if not quick_ref_rows:
        quick_ref_rows = "| — | — | — |\n"

    # Determine TL;DR
    fname = filepath.stem
    tldr = f"{layer.title()} | {fname} | {len(info.get('functions', []))} exports, {len(info.get('imports', []))} deps"

    # Build depends_on/depended_by strings
    deps_on_str = ", ".join(f'"{d}"' for d in depends_on[:10]) if depends_on else ""
    deps_by_str = ", ".join(f'"{d}"' for d in depended_by[:10]) if depended_by else ""

    content = f"""---
source: {src_rel}
service: {service}
layer: {layer}
last_analyzed: {NOW}
source_hash: {src_hash}
depends_on: [{deps_on_str}]
depended_by: [{deps_by_str}]
---

# {service}/{rel}

## TL;DR
{tldr}

## Quick Ref
| Export | Signature | Constraints |
|-------|-----------|-------------|
{quick_ref_rows}
> CC #2: 80% of the time, you can stop reading here. Deep analysis below.

## Full Analysis

### Node Position
- **Service**: {service}
- **Layer**: {layer}
- **Ancestor chain**: {project_name} -> {service} -> {'/'.join(rel.split('/')[:-1])} -> **{filepath.name}**

### Dependency Graph

#### Children (this file calls)
| Target | Signature | Return |
|--------|-----------|--------|
{chr(10).join(f'| {d} | — | — |' for d in depends_on[:10]) if depends_on else '| — | — | — |'}

#### Called By
| Source | Call Type | Context |
|--------|-----------|---------|
{chr(10).join(f'| {d} | import | — |' for d in depended_by[:10]) if depended_by else '| — | — | — |'}

### Key Constraints
- [Pending Agent deep analysis]

### Modification Risk
- Impacts {len(depended_by)} dependents
"""
    return content


def main() -> None:
    config_path = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--config" and i < len(sys.argv) - 1:
            config_path = Path(sys.argv[i + 1])

    config = load_config(config_path)
    path_map, project_root, memory_dir, exclude = _build_path_map_with_context(config)
    project_name = config.get("project", {}).get("name", "Project")

    # Build service roots from config
    service_roots: dict[str, tuple[Path, str]] = {}
    for svc in config.get("services", []):
        name = svc["name"]
        svc_path = project_root / svc["path"]
        lang = normalize_lang(svc.get("lang", "python"))
        service_roots[name] = (svc_path, lang)

    # Load chains.json (if available)
    chains_path = memory_dir / "chains.json"
    chains_data: list[dict] = []
    if chains_path.exists():
        chains_data = json.loads(chains_path.read_text())

    # First pass: build import graph for reverse deps + cache extracted info
    reverse_deps: dict[str, set[str]] = defaultdict(set)
    info_cache: dict[str, dict] = {}  # filepath -> extracted info (avoids double-read)
    for svc_name, (root, lang) in service_roots.items():
        if not root.exists():
            continue
        exts = [".py"] if lang == "python" else [".vue", ".ts", ".tsx"]
        for ext in exts:
            for f in root.rglob(f"*{ext}"):
                if any(p in f.parts for p in exclude):
                    continue
                if f.name.endswith(".d.ts"):
                    continue
                if lang == "python":
                    info = extract_python_info(f, root)
                else:
                    info = extract_ts_info(f, root)
                info_cache[str(f)] = info
                for imp in info.get("imports", []):
                    dep_path = str(root / imp)
                    reverse_deps[dep_path].add(str(f))

    # Second pass: generate all .memory/ files
    total = 0
    errors = 0
    for svc_name, (root, lang) in service_roots.items():
        if not root.exists():
            print(f"SKIP: {svc_name}")
            continue
        exts = [".py"] if lang == "python" else [".vue", ".ts", ".tsx"]
        svc_files: list[Path] = []
        for ext in exts:
            for f in root.rglob(f"*{ext}"):
                if any(p in f.parts for p in exclude):
                    continue
                if f.name.endswith(".d.ts") or f.name.endswith(".map"):
                    continue
                svc_files.append(f)

        print(f"Generating {svc_name}: {len(svc_files)} files...")
        for f in sorted(svc_files):
            rel_to_root = str(f.relative_to(project_root))
            result = _common_source_to_memory(rel_to_root, path_map)
            if not result:
                continue
            mem_rel, svc = result
            mem_path = memory_dir / mem_rel

            try:
                content = generate_memory_file(
                    f, root, svc, mem_rel, lang, reverse_deps,
                    project_root, path_map, project_name,
                    cached_info=info_cache.get(str(f)),
                )
                mem_path.parent.mkdir(parents=True, exist_ok=True)
                mem_path.write_text(content)
                total += 1
            except Exception as e:
                print(f"  ERROR: {f}: {e}")
                errors += 1

    print(f"\n=== Done ===")
    print(f"Generated: {total} .memory/ files")
    print(f"Errors: {errors}")
    print(f"Location: {memory_dir}")


if __name__ == "__main__":
    main()

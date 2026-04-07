#!/usr/bin/env python3
"""MemTree incremental updater.

Reads .pending-update and .stale queues, re-generates .memory/ documents for
changed source files. Preserves Agent-enriched analysis sections when possible.

Usage:
    python3 scripts/incremental-update.py                        # Process all pending
    python3 scripts/incremental-update.py --dry-run              # List without updating
    python3 scripts/incremental-update.py --config path/to/cfg   # Custom config path
"""
from __future__ import annotations
import ast, re, sys
from pathlib import Path
from datetime import datetime, timezone

from memtree_common import (
    load_config,
    normalize_lang,
    detect_layer,
    compute_hash,
    build_path_map,
    extract_python_imports as _common_extract_python_imports,
    extract_ts_imports as _common_extract_ts_imports,
)


def build_mappings(config: dict) -> tuple[dict[str, str], dict[str, tuple[str, str]], Path, Path]:
    """Build forward/reverse path maps and locate key directories.

    Returns:
        (mem_to_src_map, src_to_mem_map, project_root, memory_dir)
    """
    project_root = Path(config.get("project", {}).get("root", ".")).resolve()
    memory_dir = project_root / ".memory"

    src_to_mem = build_path_map(config)

    # Build reverse map: mem_prefix -> src_prefix
    mem_to_src: dict[str, str] = {}
    for sp, (mp, _name) in src_to_mem.items():
        mem_to_src[mp] = sp

    return mem_to_src, src_to_mem, project_root, memory_dir


def build_service_roots(config: dict, project_root: Path) -> dict[str, tuple[Path, str]]:
    """Build service_name -> (root_path, lang) mapping."""
    roots: dict[str, tuple[Path, str]] = {}
    for svc in config.get("services", []):
        name = svc["name"]
        lang = normalize_lang(svc.get("lang", "python"))
        roots[name] = (project_root / svc["path"], lang)
    return roots


NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def memory_to_source(mem_rel: str, mem_to_src: dict[str, str], project_root: Path) -> Path | None:
    """Deterministic reverse mapping: .memory/ path -> source file path."""
    for mem_prefix, src_prefix in mem_to_src.items():
        if mem_rel.startswith(mem_prefix):
            rest = mem_rel[len(mem_prefix):]
            if rest.endswith(".md"):
                rest = rest[:-3]
            return project_root / src_prefix / rest
    return None


def extract_python_exports(filepath: Path) -> list[dict]:
    """Extract function/class definitions from Python."""
    try:
        content = filepath.read_text(errors="replace")
        tree = ast.parse(content, filename=str(filepath))
    except Exception:
        return []
    exports: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = []
            for a in node.args.args:
                ann = ""
                if a.annotation:
                    try:
                        ann = f": {ast.unparse(a.annotation)}"
                    except Exception:
                        pass
                args.append(f"{a.arg}{ann}")
            ret = ""
            if node.returns:
                try:
                    ret = f" -> {ast.unparse(node.returns)}"
                except Exception:
                    pass
            prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
            sig = f"{prefix}def {node.name}({', '.join(args)}){ret}"
            exports.append({"name": node.name, "signature": sig[:80]})
        elif isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    pass
            exports.append({"name": node.name, "signature": f"class({', '.join(bases)})"})
    return exports[:15]


def extract_ts_exports(filepath: Path) -> list[dict]:
    """Extract exports from TS/Vue."""
    try:
        content = filepath.read_text(errors="replace")
    except Exception:
        return []
    exports: list[dict] = []
    for m in re.finditer(r'export\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)', content):
        exports.append({"name": m.group(1), "signature": m.group(0)[:80]})
    for m in re.finditer(r'export\s+(?:const|let|var)\s+(\w+)', content):
        exports.append({"name": m.group(1), "signature": m.group(0)[:80]})
    return exports[:15]


def src_to_mem_prefix(src_rel: str, src_to_mem: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    """Source file relative path -> (mem_prefix, service_name)."""
    for prefix, (mem_prefix, svc) in src_to_mem.items():
        if src_rel.startswith(prefix):
            return mem_prefix, svc
    return None


def update_memory_file(
    mem_rel: str,
    dry_run: bool,
    mem_to_src: dict[str, str],
    src_to_mem: dict[str, tuple[str, str]],
    service_roots: dict[str, tuple[Path, str]],
    project_root: Path,
    memory_dir: Path,
    project_name: str,
) -> str:
    """Update a single .memory/ file from its source. Returns status string."""
    mem_path = memory_dir / mem_rel
    src_path = memory_to_source(mem_rel, mem_to_src, project_root)

    if src_path is None:
        return f"SKIP (no source mapping): {mem_rel}"

    if not src_path.exists():
        if mem_path.exists() and not dry_run:
            mem_path.unlink()
            return f"DELETED (source gone): {mem_rel}"
        return f"ORPHAN: {mem_rel}"

    new_hash = compute_hash(src_path)

    # Check if update is actually needed
    if mem_path.exists():
        content = mem_path.read_text()
        m = re.search(r'source_hash:\s*(\w+)', content)
        if m and m.group(1) == new_hash:
            return f"UNCHANGED: {mem_rel}"

    if dry_run:
        return f"WOULD UPDATE: {mem_rel} (hash changed -> {new_hash})"

    # Determine service name and root
    src_rel = str(src_path.relative_to(project_root))
    result = src_to_mem_prefix(src_rel, src_to_mem)
    if not result:
        return f"SKIP (unknown service): {mem_rel}"
    mem_prefix, service = result

    # Find service root
    if service not in service_roots:
        return f"SKIP (service not in config): {mem_rel}"
    root, lang = service_roots[service]
    file_rel = str(src_path.relative_to(root))
    layer = detect_layer(file_rel)

    # Extract imports
    if lang == "python":
        raw_imports = _common_extract_python_imports(src_path, root)
        exports = extract_python_exports(src_path)
    else:
        raw_imports = _common_extract_ts_imports(src_path, root)
        exports = extract_ts_exports(src_path)

    depends_on: list[str] = []
    for imp in raw_imports:
        dep_src_rel = str(root / imp)
        dep_rel_to_root = str(Path(dep_src_rel).relative_to(project_root))
        r = src_to_mem_prefix(dep_rel_to_root, src_to_mem)
        if r:
            mp, _ = r
            for pfx, (_, _) in src_to_mem.items():
                if dep_rel_to_root.startswith(pfx):
                    dep_rest = dep_rel_to_root[len(pfx):]
                    depends_on.append(f"{mp}{dep_rest}")
                    break

    deps_on_str = ", ".join(f'"{d}"' for d in depends_on[:10])

    # Preserve old depended_by (avoid losing Agent analysis data)
    old_depended_by = "[]"
    old_tldr = ""
    old_analysis = ""
    if mem_path.exists():
        old_content = mem_path.read_text()
        m_db = re.search(r'depended_by:\s*(\[.*?\])', old_content)
        if m_db:
            old_depended_by = m_db.group(1)
        m_tldr = re.search(r'## TL;DR\n(.+?)(?=\n##|\n>)', old_content, re.DOTALL)
        if m_tldr and "exports, " not in m_tldr.group(1):
            old_tldr = m_tldr.group(1).strip()
        m_analysis = re.search(r'## Full Analysis\n(.+)', old_content, re.DOTALL)
        if m_analysis and "[Pending Agent deep analysis]" not in m_analysis.group(1):
            old_analysis = m_analysis.group(1).strip()

    # Quick Ref
    qr_rows = ""
    for fn in exports:
        sig = fn.get("signature", fn["name"])
        qr_rows += f"| {fn['name']} | `{sig}` | — |\n"
    if not qr_rows:
        qr_rows = "| — | — | — |\n"

    tldr = old_tldr if old_tldr else f"{layer.title()} | {src_path.stem} | {len(exports)} exports, {len(raw_imports)} deps"

    analysis_section = old_analysis if old_analysis else f"""### Node Position
- **Service**: {service}
- **Layer**: {layer}
- **Ancestor chain**: {project_name} -> {service} -> {'/'.join(file_rel.split('/')[:-1])} -> **{src_path.name}**

### Dependency Graph

#### Children (this file calls)
| Target | Signature | Return |
|--------|-----------|--------|
{chr(10).join(f'| {d} | — | — |' for d in depends_on[:10]) if depends_on else '| — | — | — |'}

### Key Constraints
- [Incremental update -- use /memtree_rebuild for deep analysis]

### Modification Risk
- Impacts dependents (see depended_by)"""

    new_content = f"""---
source: {src_rel}
service: {service}
layer: {layer}
last_analyzed: {NOW}
source_hash: {new_hash}
depends_on: [{deps_on_str}]
depended_by: {old_depended_by}
---

# {service}/{file_rel}

## TL;DR
{tldr}

## Quick Ref
| Export | Signature | Constraints |
|-------|-----------|-------------|
{qr_rows}
> CC #2: 80% of the time, you can stop reading here. Deep analysis below.

## Full Analysis

{analysis_section}
"""

    # Path traversal check
    if not str(mem_path.resolve()).startswith(str(memory_dir.resolve())):
        return f"SKIP (path traversal blocked): {mem_rel}"

    mem_path.parent.mkdir(parents=True, exist_ok=True)
    mem_path.write_text(new_content)
    return f"UPDATED: {mem_rel} (hash -> {new_hash})"


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    config_path = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--config" and i < len(sys.argv) - 1:
            config_path = Path(sys.argv[i + 1])

    config = load_config(config_path)
    mem_to_src, src_to_mem, project_root, memory_dir = build_mappings(config)
    service_roots = build_service_roots(config, project_root)
    project_name = config.get("project", {}).get("name", "Project")

    pending_file = memory_dir / ".pending-update"
    stale_file = memory_dir / ".stale"

    # Collect files to update
    pending: set[str] = set()
    if pending_file.exists():
        lines = pending_file.read_text().strip()
        if lines:
            pending.update(l.strip() for l in lines.split("\n") if l.strip())

    if stale_file.exists():
        lines = stale_file.read_text().strip()
        if lines:
            for l in lines.split("\n"):
                l = l.strip().replace(":cascade", "")
                if l:
                    rel = l.replace(str(memory_dir) + "/", "").replace(".memory/", "")
                    pending.add(rel)

    if not pending:
        print("No files pending update")
        return

    print(f"Pending: {len(pending)} files")
    results: dict[str, int] = {"UPDATED": 0, "UNCHANGED": 0, "DELETED": 0, "SKIP": 0}

    for mem_rel in sorted(pending):
        status = update_memory_file(
            mem_rel, dry_run, mem_to_src, src_to_mem,
            service_roots, project_root, memory_dir, project_name,
        )
        print(f"  {status}")
        for key in results:
            if status.startswith(key) or status.startswith(f"WOULD {key}"):
                results[key] += 1

    # Clear processed queues
    if not dry_run:
        if pending_file.exists():
            pending_file.unlink()
        if stale_file.exists():
            stale_file.unlink()

    print(f"\nDone: {results}")


if __name__ == "__main__":
    main()

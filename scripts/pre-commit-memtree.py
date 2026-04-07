#!/usr/bin/env python3
"""Git pre-commit hook: detect source file changes, compare source_hash, mark stale entries.

When source files are staged for commit, this hook compares their SHA256 hash against
the stored source_hash in .memory/ files. Stale entries (and their one-level dependents)
are written to .stale for later incremental update.

Installation (in a repo with .git):
    # Append to existing pre-commit hook
    echo 'python3 /path/to/memtree/scripts/pre-commit-memtree.py' >> .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

    # Or create a new pre-commit hook
    echo '#!/bin/sh' > .git/hooks/pre-commit
    echo 'python3 /path/to/memtree/scripts/pre-commit-memtree.py' >> .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

Usage:
    python3 scripts/pre-commit-memtree.py
    python3 scripts/pre-commit-memtree.py --config path/to/memtree.config.yaml
"""
from __future__ import annotations
import subprocess, sys, hashlib, re
from pathlib import Path


def load_config(config_path: Path | None = None) -> dict:
    """Load memtree.config.yaml, falling back to example if missing."""
    try:
        import yaml
    except ImportError:
        # Without YAML, we cannot load config; exit silently to not block commits
        sys.exit(0)

    if config_path is None:
        # Search for config in common locations
        candidates = [
            Path("memtree.config.yaml"),
            Path.cwd() / "memtree.config.yaml",
        ]
        for c in candidates:
            if c.exists():
                config_path = c
                break

    if config_path is None or not config_path.exists():
        # No config found; exit silently to not block commits
        sys.exit(0)

    return yaml.safe_load(config_path.read_text())


def build_path_map(config: dict) -> dict[str, str]:
    """Build source path prefix -> .memory/ prefix mapping from config."""
    path_map: dict[str, str] = {}
    if "path_map" in config:
        for src_prefix, mem_prefix in config["path_map"].items():
            path_map[src_prefix] = mem_prefix if mem_prefix.endswith("/") else mem_prefix + "/"
    else:
        for svc in config.get("services", []):
            name = svc["name"]
            src_path = svc["path"]
            if not src_path.endswith("/"):
                src_path += "/"
            path_map[src_path] = f"{name}/"
    return path_map


def main() -> None:
    config_path = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--config" and i < len(sys.argv) - 1:
            config_path = Path(sys.argv[i + 1])

    config = load_config(config_path)
    project_root = Path(config.get("project", {}).get("root", ".")).resolve()
    memory_dir = project_root / ".memory"
    path_map = build_path_map(config)

    if not memory_dir.exists():
        sys.exit(0)

    # Get staged changed files
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        sys.exit(0)

    changed = [f for f in result.stdout.strip().split("\n") if f and not f.startswith(".memory/")]

    # Determine current repo root relative to project root
    cwd = Path.cwd().resolve()
    try:
        cwd_rel = str(cwd.relative_to(project_root))
    except ValueError:
        sys.exit(0)  # Not under project root

    stale: list[str] = []
    for f in changed:
        # Build full relative path from project root
        full_rel = f"{cwd_rel}/{f}" if cwd_rel and cwd_rel != "." else f

        for prefix, mem_prefix in path_map.items():
            if full_rel.startswith(prefix):
                rest = full_rel[len(prefix):]
                mem = memory_dir / f"{mem_prefix}{rest}.md"
                if mem.exists():
                    # Compare source_hash
                    content = mem.read_text()
                    m = re.search(r"source_hash:\s*(\w+)", content)
                    if m:
                        src = project_root / full_rel
                        if src.exists():
                            new_hash = hashlib.sha256(src.read_bytes()).hexdigest()[:8]
                            if new_hash != m.group(1):
                                stale.append(str(mem.relative_to(memory_dir)))
                    else:
                        stale.append(str(mem.relative_to(memory_dir)))
                break

    if stale:
        # Cascade staleness: read depended_by, propagate one level
        cascade: list[str] = []
        for s in stale:
            mem_file = memory_dir / s
            if mem_file.exists():
                mc = re.search(r"depended_by:\s*\[([^\]]*)\]", mem_file.read_text())
                if mc and mc.group(1).strip():
                    for dep in mc.group(1).split(","):
                        dep = dep.strip().strip("'\"").strip()
                        if dep:
                            dep_mem = memory_dir / f"{dep}.md"
                            if dep_mem.exists():
                                cascade.append(f"{dep}:cascade")

        stale_file = memory_dir / ".stale"
        existing: set[str] = set()
        if stale_file.exists():
            lines = stale_file.read_text().strip()
            if lines:
                existing = set(lines.split("\n"))
        existing.update(stale)
        existing.update(cascade)
        existing.discard("")
        stale_file.write_text("\n".join(sorted(existing)) + "\n")

        # Auto-stage the .stale file
        subprocess.run(["git", "add", str(stale_file)], capture_output=True)
        print(f"MemTree: {len(stale)} stale + {len(cascade)} cascade marked")

    sys.exit(0)  # Never block the commit


if __name__ == "__main__":
    main()

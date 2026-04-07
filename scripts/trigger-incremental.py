#!/usr/bin/env python3
"""Claude Code hook-triggered incremental update scheduler.

Receives a modified file path, maps it to its .memory/ counterpart, and appends
it to the .pending-update queue for later batch processing.
Uses file locking to prevent concurrent write conflicts.

Usage:
    python3 scripts/trigger-incremental.py "$TOOL_INPUT_FILE_PATH"

Typically invoked automatically by a Claude Code PostToolUse hook (see hook-post-edit.sh).
"""
from __future__ import annotations
import sys, os
from pathlib import Path

# Try to import fcntl (Unix only); on Windows, skip file locking
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

def find_project_root() -> Path:
    """Find project root by looking for memtree.config.yaml or .memory/"""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "memtree.config.yaml").exists() or (parent / ".memory").exists():
            return parent
    return cwd

PROJECT_ROOT = find_project_root()
MEMORY_DIR = PROJECT_ROOT / ".memory"
PENDING = MEMORY_DIR / ".pending-update"
LOCK_FILE = MEMORY_DIR / ".lock"


def load_path_map() -> tuple[dict[str, str], dict[str, str]]:
    """Load path mapping from memtree.config.yaml.

    Returns:
        Tuple of (relative_path_map, absolute_path_map).
        Each maps source prefix -> .memory/ prefix.
    """
    config_candidates = [
        MEMORY_DIR.parent / "memtree.config.yaml",
        MEMORY_DIR / "memtree.config.yaml",
        Path("memtree.config.yaml"),
    ]

    config = None
    for candidate in config_candidates:
        if candidate.exists():
            try:
                import yaml
                config = yaml.safe_load(candidate.read_text())
                break
            except ImportError:
                break

    if config is None:
        # Fallback: no config found, cannot map paths
        return {}, {}

    project_root = Path(config.get("project", {}).get("root", ".")).resolve()

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

    abs_path_map = {str(project_root / k): v for k, v in path_map.items()}
    return path_map, abs_path_map


def source_to_memory(src: str, path_map: dict[str, str], abs_path_map: dict[str, str]) -> str | None:
    """Deterministic path mapping: source file -> .memory/ relative path."""
    # Try absolute path first
    for prefix, mem_prefix in abs_path_map.items():
        if src.startswith(prefix):
            rel = src[len(prefix):].lstrip("/")
            return f"{mem_prefix}{rel}.md"
    # Try relative path
    for prefix, mem_prefix in path_map.items():
        if src.startswith(prefix):
            rel = src[len(prefix):].lstrip("/")
            return f"{mem_prefix}{rel}.md"
    return None


def main() -> None:
    if len(sys.argv) < 2:
        return

    src_path = sys.argv[1]
    if not src_path:
        return

    # Skip modifications to .memory/ itself
    if ".memory/" in src_path or ".memory\\" in src_path:
        return

    # Skip non-source files
    valid_exts = {".py", ".vue", ".ts", ".tsx", ".jsx", ".js", ".go", ".rs", ".java"}
    if not any(src_path.endswith(ext) for ext in valid_exts):
        return

    path_map, abs_path_map = load_path_map()
    if not path_map and not abs_path_map:
        return

    mem_path = source_to_memory(src_path, path_map, abs_path_map)
    if not mem_path:
        return

    # File lock: prevent concurrent writes
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    if HAS_FCNTL:
        with open(LOCK_FILE, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                _append_to_pending(mem_path)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    else:
        # No file locking on this platform; best-effort write
        _append_to_pending(mem_path)


def _append_to_pending(mem_path: str) -> None:
    """Append mem_path to the pending queue, deduplicating entries."""
    existing: set[str] = set()
    if PENDING.exists():
        lines = PENDING.read_text().strip()
        if lines:
            existing = set(lines.split("\n"))
    existing.add(mem_path)
    existing.discard("")
    PENDING.write_text("\n".join(sorted(existing)) + "\n")


if __name__ == "__main__":
    main()

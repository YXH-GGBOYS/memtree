#!/usr/bin/env python3
"""Shared utilities for MemTree scripts.
Consolidates load_config, normalize_lang, detect_layer, build_path_map,
compute_hash, extract_python_imports, extract_ts_imports, source_to_memory,
and find_project_root -- previously duplicated across 7+ scripts.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


# --- Config Loading ---

def load_config(config_path: Path | None = None, silent: bool = False) -> dict | None:
    """Load memtree.config.yaml. Falls back to .example.yaml.
    If silent=True, returns None instead of sys.exit on failure (for hooks).
    """
    try:
        import yaml
    except ImportError:
        if silent:
            return None
        print("ERROR: PyYAML required. Install: pip install pyyaml")
        sys.exit(1)

    candidates: list[Path] = []
    if config_path:
        candidates.append(config_path)
    candidates.extend([
        Path("memtree.config.yaml"),
        Path("memtree.config.example.yaml"),
    ])

    for p in candidates:
        if p.exists():
            cfg = yaml.safe_load(p.read_text())
            if p.name.endswith(".example.yaml") and not silent:
                print(f"WARNING: Using example config {p}")
            return cfg

    if silent:
        return None
    print("ERROR: memtree.config.yaml not found")
    sys.exit(1)


def find_project_root() -> Path:
    """Walk up from CWD looking for memtree.config.yaml or .memory/"""
    cwd = Path.cwd()
    for parent in [cwd, *list(cwd.parents)]:
        if (parent / "memtree.config.yaml").exists() or (parent / ".memory").exists():
            return parent
    return cwd


# --- Language / Layer ---

def normalize_lang(lang: str) -> str:
    """Normalize language string from config to internal key.
    Returns one of: python, vue_ts, tsx, ts
    """
    lang = lang.lower().strip()
    if lang in ("python", "py"):
        return "python"
    if lang in ("vue", "nuxt", "vue_ts"):
        return "vue_ts"
    if lang in ("tsx", "react", "next", "jsx"):
        return "tsx"
    if lang in ("ts", "typescript", "javascript", "js"):
        return "ts"
    return lang


LANG_EXTENSIONS: dict[str, list[str]] = {
    "python": [".py"],
    "vue_ts": [".vue", ".ts", ".tsx"],
    "tsx": [".ts", ".tsx", ".jsx"],
    "ts": [".ts", ".tsx"],
}


def detect_layer(rel_path: str) -> str:
    """Detect the architectural layer from a relative file path."""
    p = rel_path.lower()
    for keyword, layer in [
        ("route", "router"), ("router", "router"), ("handler", "handler"),
        ("api/v1", "router"), ("api/v2", "router"),
        ("service", "service"),
        ("model", "model"), ("schema", "model"), ("entity", "model"),
        ("page", "page"),
        ("component", "component"), ("widget", "component"),
        ("modal", "component"), ("card", "component"),
        ("composable", "composable"), ("hook", "composable"),
        ("middleware", "middleware"),
        ("util", "util"), ("helper", "util"), ("lib/", "util"),
        ("config", "config"), ("constant", "config"),
        ("store", "store"), ("provider", "store"),
        ("type", "type"),
        ("plugin", "plugin"),
        ("core", "core"),
        ("task", "task"), ("job", "task"), ("worker", "task"),
        ("alarm", "task"),
    ]:
        if keyword in p:
            return layer
    return "module"


# --- Path Mapping ---

def build_path_map(config: dict) -> dict[str, tuple[str, str]]:
    """Build source_prefix -> (memory_prefix, service_name) mapping from config.
    Returns: {"src/api/": ("backend/", "backend"), ...}

    Supports both explicit path_map in config and auto-generation from services.
    """
    path_map: dict[str, tuple[str, str]] = {}
    if "path_map" in config:
        for src_prefix, mem_prefix in config["path_map"].items():
            svc_name = mem_prefix.rstrip("/")
            mp = mem_prefix if mem_prefix.endswith("/") else mem_prefix + "/"
            sp = src_prefix if src_prefix.endswith("/") else src_prefix + "/"
            path_map[sp] = (mp, svc_name)
    else:
        for svc in config.get("services", []):
            name = svc["name"]
            src_path = svc["path"]
            if not src_path.endswith("/"):
                src_path += "/"
            path_map[src_path] = (f"{name}/", name)
    return path_map


def source_to_memory(src_path: str, path_map: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    """Deterministic mapping: source file path -> (.memory/ relative path, service_name).
    Returns None if no mapping matches.
    """
    for prefix, (mem_prefix, svc) in path_map.items():
        if src_path.startswith(prefix):
            rel = src_path[len(prefix):]
            return f"{mem_prefix}{rel}.md", svc
    return None


# --- Hash ---

def compute_hash(filepath: Path) -> str:
    """SHA256 first 8 chars of a file."""
    if filepath.exists():
        return hashlib.sha256(filepath.read_bytes()).hexdigest()[:8]
    return "00000000"


# --- Import Extraction ---

def extract_python_imports(filepath: Path, root: Path) -> list[str]:
    """Extract project-internal Python imports.
    Handles: from app.x import y, from .relative import z, import app.x
    """
    try:
        content = filepath.read_text(errors="replace")
    except OSError:
        return []

    imports: list[str] = []

    for line in content.split("\n"):
        line = line.strip()

        # Pattern 1: from app.xxx import ...
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

        # Pattern 2: from .relative import ...
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

        # Pattern 3: import app.xxx
        m = re.match(r'import\s+(app\..+)', line)
        if m:
            mod = m.group(1).split()[0].replace("app.", "").replace(".", "/")
            candidate = root / (mod + ".py")
            if candidate.exists():
                imports.append(str(candidate.relative_to(root)))

    return list(dict.fromkeys(imports))  # deduplicate, preserve order


def extract_ts_imports(filepath: Path, root: Path) -> list[str]:
    """Extract project-internal TypeScript/Vue imports."""
    try:
        content = filepath.read_text(errors="replace")
    except OSError:
        return []

    imports: list[str] = []
    for m in re.finditer(r'''(?:import|from)\s+.*?['"]([\./~@][^'"]+)['"]''', content):
        raw = m.group(1)
        if raw.startswith("~") or raw.startswith("@"):
            rel = raw.lstrip("~").lstrip("@").lstrip("/")
            resolved = root / rel
        elif raw.startswith("."):
            resolved = (filepath.parent / raw).resolve()
        else:
            continue

        # Try with extensions
        for ext in ["", ".ts", ".tsx", ".vue", "/index.ts", "/index.tsx", "/index.vue"]:
            candidate = Path(str(resolved) + ext)
            if candidate.exists() and candidate.is_file():
                try:
                    imports.append(str(candidate.relative_to(root)))
                except ValueError:
                    pass
                break

    return list(dict.fromkeys(imports))  # deduplicate, preserve order

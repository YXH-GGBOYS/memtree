#!/usr/bin/env python3
"""Generate INDEX.md for every directory in .memory/ that contains per-file .md files.

Creates navigable directory indexes with file summaries extracted from existing
skeleton/analyzed .memory/ documents. Supports per-service and per-directory indexes.

Usage:
    python3 scripts/generate-indexes.py
    python3 scripts/generate-indexes.py --config path/to/memtree.config.yaml
"""
from __future__ import annotations
import re, sys
from pathlib import Path

from memtree_common import load_config


SKIP_DIRS = {"prompts", "scripts", "workers", "cross-refs", ".draft", "db"}
SKIP_FILES = {"INDEX.md", "PITFALLS.md", "ROOT.md"}

# Common directory descriptions (language-agnostic)
DIR_DESCRIPTIONS: dict[str, str] = {
    "routers": "Router layer - API endpoint definitions, request handling",
    "routes": "Route layer - API endpoint definitions, request handling",
    "services": "Service layer - business logic, transaction management",
    "models": "Model layer - ORM models, database mapping",
    "schemas": "Schema layer - validation models (Pydantic, Zod, etc.)",
    "core": "Core - configuration, security, database connections",
    "middleware": "Middleware - request/response processing chain",
    "tasks": "Background tasks - scheduled jobs, async processing",
    "utils": "Utilities - helper functions, common tools",
    "constants": "Constants - enums, configuration constants",
    "pages": "Pages - route page components",
    "components": "Components - UI components, cards, modals",
    "composables": "Composables - state management + API wrappers",
    "hooks": "Hooks - React hooks / Vue composables",
    "api": "API client - backend interface wrappers",
    "types": "Type definitions - TypeScript interfaces/types",
    "store": "Store - state storage (auth, theme, etc.)",
    "lib": "Library - core functionality modules",
    "handlers": "Handlers - message/event handlers",
    "plugins": "Plugins - framework plugins",
    "views": "Views - view components/templates",
    "layouts": "Layouts - page layout components",
    "assets": "Assets - static resources",
    "styles": "Styles - CSS/SCSS stylesheets",
    "controllers": "Controllers - request controllers",
    "repositories": "Repositories - data access layer",
    "entities": "Entities - domain entities/models",
    "dto": "DTOs - data transfer objects",
    "guards": "Guards - authentication/authorization guards",
    "interceptors": "Interceptors - request/response interceptors",
    "decorators": "Decorators - custom decorators",
    "filters": "Filters - exception/validation filters",
    "pipes": "Pipes - data transformation pipes",
    "v1": "API v1 - versioned REST endpoints",
    "v2": "API v2 - versioned REST endpoints",
}


def build_service_descriptions(config: dict) -> dict[str, str]:
    """Build service descriptions from config."""
    descriptions: dict[str, str] = {}
    for svc in config.get("services", []):
        name = svc["name"]
        lang = svc.get("lang", "")
        framework = svc.get("framework", "")
        desc_parts = []
        if framework:
            desc_parts.append(framework.title())
        if lang:
            desc_parts.append(lang)
        desc_parts.append(f"service ({name})")
        descriptions[name] = " ".join(desc_parts)
    return descriptions


def extract_tldr(md_path: Path) -> str:
    """Extract TL;DR from a .memory/ file."""
    try:
        content = md_path.read_text()
        m = re.search(r'## TL;DR\n(.+)', content)
        if m:
            return m.group(1).strip()[:100]
    except Exception:
        pass
    return "—"


def extract_exports(md_path: Path) -> str:
    """Extract key exports from Quick Ref."""
    try:
        content = md_path.read_text()
        exports: list[str] = []
        in_qr = False
        for line in content.split("\n"):
            if "## Quick Ref" in line:
                in_qr = True
                continue
            if in_qr and line.startswith("|") and not line.startswith("| Export") and not line.startswith("|---"):
                parts = line.split("|")
                if len(parts) >= 3:
                    name = parts[1].strip()
                    if name and name != "—":
                        exports.append(name)
            if in_qr and not line.startswith("|") and line.strip():
                break
        return ", ".join(exports[:5])
    except Exception:
        return "—"


def main() -> None:
    config_path = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--config" and i < len(sys.argv) - 1:
            config_path = Path(sys.argv[i + 1])

    config = load_config(config_path)
    project_root = Path(config.get("project", {}).get("root", ".")).resolve()
    memory_dir = project_root / ".memory"

    if not memory_dir.exists():
        print(f"ERROR: .memory/ directory not found at {memory_dir}")
        sys.exit(1)

    service_descriptions = build_service_descriptions(config)
    total_indexes = 0

    # Process each service directory
    for service_dir in sorted(memory_dir.iterdir()):
        if not service_dir.is_dir() or service_dir.name in SKIP_DIRS or service_dir.name.startswith("."):
            continue

        svc_name = service_dir.name
        desc = service_descriptions.get(svc_name, svc_name)

        # Count files per subdirectory
        subdirs: list[tuple[str, str, int]] = []
        for sub in sorted(service_dir.iterdir()):
            if sub.is_dir():
                # rglob to count nested .md files (subdirs may have multiple levels)
                md_count = sum(1 for f in sub.rglob("*.md") if f.name not in SKIP_FILES)
                if md_count > 0:
                    sub_desc = DIR_DESCRIPTIONS.get(sub.name, sub.name)
                    subdirs.append((sub.name, sub_desc, md_count))

        # Direct .md files in service root
        root_mds = [f for f in service_dir.iterdir() if f.is_file() and f.suffix == ".md" and f.name not in SKIP_FILES]

        svc_index = f"# {svc_name}/\n\n## Service Overview\n{desc}\n\n"
        svc_index += "## Directory Structure\n| Directory | Purpose | File Count |\n|-----------|---------|------------|\n"
        for name, desc_sub, count in subdirs:
            svc_index += f"| [{name}/](./{name}/INDEX.md) | {desc_sub} | {count} |\n"
        if root_mds:
            svc_index += f"| (root) | Config/entrypoints | {len(root_mds)} |\n"
        svc_index += f"\n## Pitfalls\n-> [PITFALLS.md](./PITFALLS.md)\n"

        svc_index_path = service_dir / "INDEX.md"
        if not str(svc_index_path.resolve()).startswith(str(memory_dir.resolve())):
            continue
        if svc_index_path.exists() and svc_index_path.read_text() == svc_index:
            continue  # Skip unchanged INDEX.md
        svc_index_path.write_text(svc_index)
        total_indexes += 1

        # Sub-directory INDEX.md files
        for sub in sorted(service_dir.rglob("*")):
            if not sub.is_dir():
                continue
            md_files = [f for f in sub.iterdir() if f.is_file() and f.suffix == ".md" and f.name not in SKIP_FILES]
            if not md_files:
                continue

            dir_name = sub.name
            dir_desc = DIR_DESCRIPTIONS.get(dir_name, dir_name)
            rel_to_svc = sub.relative_to(service_dir)

            idx = f"# {svc_name}/{rel_to_svc}/\n\n## Directory Purpose\n{dir_desc}\n\n"
            idx += "## File List\n| File | Purpose | Key Exports |\n|------|---------|-------------|\n"

            for md in sorted(md_files):
                fname = md.name.replace(".md", "")
                tldr = extract_tldr(md)
                exports = extract_exports(md)
                idx += f"| [{fname}](./{md.name}) | {tldr} | {exports} |\n"

            # Sub-subdirectories
            sub_subs = [d for d in sub.iterdir() if d.is_dir()]
            for ss in sorted(sub_subs):
                # rglob to count nested .md files in sub-subdirectories
                ss_count = sum(1 for f in ss.rglob("*.md") if f.name not in SKIP_FILES)
                if ss_count > 0:
                    ss_desc = DIR_DESCRIPTIONS.get(ss.name, ss.name)
                    idx += f"| [{ss.name}/](./{ss.name}/INDEX.md) | {ss_desc} | {ss_count} files |\n"

            sub_index_path = sub / "INDEX.md"
            if not str(sub_index_path.resolve()).startswith(str(memory_dir.resolve())):
                continue
            if sub_index_path.exists() and sub_index_path.read_text() == idx:
                continue  # Skip unchanged INDEX.md
            sub_index_path.write_text(idx)
            total_indexes += 1

    print(f"Generated {total_indexes} INDEX.md files")


if __name__ == "__main__":
    main()

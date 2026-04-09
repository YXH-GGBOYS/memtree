#!/usr/bin/env python3
"""MemTree quality evaluator.
Layer 1: Deterministic checks (hash match, source exists, import coverage, PITFALL event refs)
Layer 2: Model-based checks (--deep mode, samples files for LLM scoring)"""
from __future__ import annotations
import argparse, hashlib, random, re, sys
from pathlib import Path

try:
    from memtree_common import find_project_root, load_config, build_path_map
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from memtree_common import find_project_root, load_config, build_path_map

ROOT = find_project_root()
MEMORY = ROOT / ".memory"
SKIP_FILES = {"INDEX.md", "ROOT.md", "PITFALLS.md", "HEALTH.md", "TEMPLATE.md"}
SKIP_DIRS = {"prompts", "scripts", "workers", "cross-refs", ".draft", "db", "events"}


def get_per_file_mds() -> list[Path]:
    """Collect all per-file .md files."""
    results = []
    for md in sorted(MEMORY.rglob("*.md")):
        if md.name in SKIP_FILES:
            continue
        rel = md.relative_to(MEMORY)
        if any(str(rel).startswith(d) for d in SKIP_DIRS) or str(rel).startswith("."):
            continue
        results.append(md)
    return results


def check_hash(md: Path) -> tuple[str, str]:
    """Check if source_hash matches actual file hash."""
    content = md.read_text()
    m_hash = re.search(r'source_hash:\s*(\w+)', content)
    m_src = re.search(r'source:\s*(.+)', content)
    if not m_hash or not m_src:
        return "skip", "no frontmatter"
    src = ROOT / m_src.group(1).strip()
    if not src.exists():
        return "orphan", f"source not found: {m_src.group(1).strip()}"
    actual = hashlib.sha256(src.read_bytes()).hexdigest()[:8]
    return ("ok", "") if actual == m_hash.group(1) else ("stale", f"hash {m_hash.group(1)} != {actual}")


def check_imports(md: Path) -> tuple[str, str]:
    """Check if Relations covers source imports."""
    content = md.read_text()
    m_src = re.search(r'source:\s*(.+)', content)
    if not m_src:
        return "skip", "no source"
    src = ROOT / m_src.group(1).strip()
    if not src.exists():
        return "skip", "source missing"

    source_text = src.read_text()
    ext = src.suffix
    imported: set[str] = set()
    stdlib = {"os", "sys", "re", "json", "datetime", "typing", "pathlib", "hashlib",
              "collections", "functools", "logging", "uuid", "enum", "decimal",
              "sqlalchemy", "fastapi", "pydantic", "httpx", "redis", "asyncio"}
    if ext == ".py":
        for m in re.finditer(r'^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))', source_text, re.MULTILINE):
            mod = m.group(1) or m.group(2)
            if mod and mod.split(".")[0] not in stdlib:
                imported.add(mod.split(".")[-1])
    elif ext in (".ts", ".vue", ".tsx"):
        for m in re.finditer(r'(?:import|from)\s+[\'"]([^"\']+)["\']', source_text):
            p = m.group(1)
            if p.startswith("."):
                imported.add(p.split("/")[-1].replace(".vue", "").replace(".ts", ""))
    if not imported:
        return "ok", ""
    relations = re.search(r'## Relations.*?(?=## |\Z)', content, re.DOTALL)
    if not relations:
        return "warn", f"no Relations section, {len(imported)} imports unchecked"
    rel_text = relations.group(0).lower()
    missing = [m for m in imported if m.lower() not in rel_text]
    if len(missing) <= 2:
        return "ok", f"minor: {', '.join(missing)}" if missing else ""
    return "warn", f"{len(missing)} imports missing from Relations"


def check_pitfall_refs() -> list[str]:
    """Check PITFALL event references point to existing files."""
    issues = []
    for pitfalls_path in MEMORY.glob("*/PITFALLS.md"):
        svc = pitfalls_path.parent.name
        content = pitfalls_path.read_text()
        for m in re.finditer(r'\[EVT-(\d{8})-(\d{3})\]\(([^)]+)\)', content):
            evt_file = (pitfalls_path.parent / m.group(3)).resolve()
            if not evt_file.exists():
                issues.append(f"{svc}/PITFALLS.md: EVT-{m.group(1)}-{m.group(2)} → not found")
    return issues


def layer1_eval(files: list[Path]) -> dict:
    """Run deterministic quality checks."""
    results = {"total": len(files), "hash_ok": 0, "hash_stale": 0, "hash_orphan": 0,
               "hash_skip": 0, "import_ok": 0, "import_warn": 0, "import_skip": 0, "details": []}
    for md in files:
        rel = md.relative_to(MEMORY)
        h_status, h_msg = check_hash(md)
        results[f"hash_{h_status}"] += 1
        i_status, i_msg = check_imports(md)
        results[f"import_{i_status}"] += 1
        if h_status not in ("ok", "skip") or i_status == "warn":
            results["details"].append(f"{rel}: hash={h_status} import={i_status} {h_msg} {i_msg}".strip())
    results["pitfall_ref_issues"] = check_pitfall_refs()
    return results


def format_report(results: dict) -> str:
    """Format evaluation report."""
    lines = ["=" * 60, "MemTree Quality Evaluation Report", "=" * 60, "",
             f"Files checked: {results['total']}",
             f"Hash OK: {results['hash_ok']}  Stale: {results['hash_stale']}  Orphan: {results['hash_orphan']}  Skip: {results['hash_skip']}",
             f"Import OK: {results['import_ok']}  Warn: {results['import_warn']}  Skip: {results['import_skip']}", ""]
    if results["pitfall_ref_issues"]:
        lines.append(f"PITFALL event ref issues ({len(results['pitfall_ref_issues'])}):")
        for i in results["pitfall_ref_issues"]:
            lines.append(f"  {i}")
        lines.append("")
    if results["details"]:
        lines.append(f"Details ({len(results['details'])}):")
        for d in results["details"][:30]:
            lines.append(f"  {d}")
        if len(results["details"]) > 30:
            lines.append(f"  ... and {len(results['details']) - 30} more")
        lines.append("")
    checkable = results["hash_ok"] + results["hash_stale"]
    if checkable:
        lines.append(f"Hash pass rate: {results['hash_ok'] / checkable * 100:.1f}%")
    lines += ["", "=" * 60]
    total_issues = results["hash_stale"] + results["hash_orphan"] + len(results["pitfall_ref_issues"])
    lines.append("ALL CHECKS PASSED" if total_issues == 0 else f"ISSUES FOUND: {total_issues}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="MemTree Quality Evaluator")
    parser.add_argument("--deep", action="store_true", help="Enable Layer 2 model-based checks (requires API)")
    parser.add_argument("--sample", type=int, default=0, help="Sample N files (0=all)")
    args = parser.parse_args()
    all_files = get_per_file_mds()
    files = random.sample(all_files, min(args.sample, len(all_files))) if args.sample > 0 else all_files
    print(f"Checking {len(files)}/{len(all_files)} files")
    results = layer1_eval(files)
    report = format_report(results)
    print(report)
    report_file = MEMORY / "quality-eval-report.md"
    report_file.write_text(report + "\n")
    print(f"\nReport: {report_file}")
    if args.deep:
        print("\nLayer 2: Run in Claude Code session — sample files for LLM-based TL;DR/Relations/Constraints scoring")


if __name__ == "__main__":
    main()

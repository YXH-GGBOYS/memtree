#!/usr/bin/env python3
"""MemTree consistency checker. Validates the .memory/ tree against source files.

Checks performed:
  1. source_hash matches current file content (detects stale entries)
  2. depends_on targets exist in .memory/ (detects broken links)
  3. Orphaned .memory/ files (source deleted but .memory/ entry remains)

Used in bootstrap Phase 5, or run manually any time.

Usage:
    python3 scripts/validate-memtree.py
    python3 scripts/validate-memtree.py --config path/to/memtree.config.yaml
"""
from __future__ import annotations
import re, sys
from pathlib import Path

from memtree_common import load_config, compute_hash


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

    errors: list[str] = []
    warnings: list[str] = []
    stats = {"total": 0, "hash_ok": 0, "hash_stale": 0, "hash_orphan": 0}

    skip_files = {"INDEX.md", "ROOT.md", "PITFALLS.md"}
    skip_dirs = {"prompts", "scripts", "workers", "cross-refs", ".draft", "db"}

    for md in sorted(memory_dir.rglob("*.md")):
        # Skip non-per-file docs
        if md.name in skip_files:
            continue
        rel = md.relative_to(memory_dir)
        if any(str(rel).startswith(d) for d in skip_dirs):
            continue
        if str(rel).startswith("."):
            continue

        stats["total"] += 1
        content = md.read_text()

        # 1. source_hash match
        m_hash = re.search(r'source_hash:\s*(\w+)', content)
        m_src = re.search(r'source:\s*(.+)', content)
        if m_hash and m_src:
            src = project_root / m_src.group(1).strip()
            if src.exists():
                actual = compute_hash(src)
                if actual == m_hash.group(1):
                    stats["hash_ok"] += 1
                else:
                    stats["hash_stale"] += 1
                    errors.append(f"STALE: {rel} hash {m_hash.group(1)} != actual {actual}")
            else:
                stats["hash_orphan"] += 1
                errors.append(f"ORPHAN: {rel} source {m_src.group(1).strip()} not found")
        else:
            warnings.append(f"NO_FRONTMATTER: {rel} missing source or source_hash")

        # 2. depends_on: check target files exist in .memory/
        m_deps = re.search(r'depends_on:\s*\[([^\]]*)\]', content)
        if m_deps and m_deps.group(1).strip():
            for dep in m_deps.group(1).split(","):
                dep = dep.strip().strip('"\'').strip()
                if not dep:
                    continue
                dep_mem = memory_dir / f"{dep}.md"
                if not dep_mem.exists():
                    if not (memory_dir / dep).exists():
                        warnings.append(f"DEP_MISSING: {rel} depends_on '{dep}' but .memory/{dep}.md not found")

    # Output report
    report_lines = [
        "=" * 60,
        "MemTree Consistency Report",
        "=" * 60,
        f"Total files: {stats['total']}",
        f"Hash OK: {stats['hash_ok']}",
        f"Hash stale (STALE): {stats['hash_stale']}",
        f"Source missing (ORPHAN): {stats['hash_orphan']}",
        "",
    ]

    if errors:
        report_lines.append(f"=== Errors ({len(errors)}) ===")
        for e in errors:
            report_lines.append(f"  {e}")
        report_lines.append("")

    if warnings:
        report_lines.append(f"=== Warnings ({len(warnings)}) ===")
        for w in warnings[:50]:
            report_lines.append(f"  {w}")
        if len(warnings) > 50:
            report_lines.append(f"  ... and {len(warnings) - 50} more")
        report_lines.append("")

    report_lines.append("=" * 60)
    if not errors:
        report_lines.append("ALL CRITICAL CHECKS PASSED")
    else:
        report_lines.append(f"FAILED: {len(errors)} critical issues")

    report = "\n".join(report_lines)
    print(report)

    # Write report file
    report_file = memory_dir / ".validation-report"
    report_file.write_text(report + "\n")

    sys.exit(min(len(errors), 1))


if __name__ == "__main__":
    main()

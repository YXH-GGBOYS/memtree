#!/usr/bin/env python3
"""Generate .memory/HEALTH.md — system health snapshot.
Reads git log + events/ + PITFALLS.md → outputs hotspots / change coupling / PITFALL stats."""
from __future__ import annotations
import re, subprocess, sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

try:
    from memtree_common import find_project_root, load_config, build_path_map
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from memtree_common import find_project_root, load_config, build_path_map

ROOT = find_project_root()
MEMORY = ROOT / ".memory"
DAYS = 14


def get_services(config: dict) -> list[str]:
    """Get service names from config."""
    if "services" in config:
        return [s["name"] for s in config["services"]]
    if "path_map" in config:
        return list({v.rstrip("/") for v in config["path_map"].values()})
    return []


def source_to_memtree(path: str, path_map: dict) -> str | None:
    """Map source path to MemTree service path."""
    for prefix, (mem_prefix, _) in path_map.items():
        if path.startswith(prefix):
            return mem_prefix + path[len(prefix):]
    return None


def get_git_hotspots(path_map: dict, days: int) -> list[tuple[str, int]]:
    """Get files changed most in the last N days."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--name-only", "--pretty=format:"],
            capture_output=True, text=True, cwd=ROOT, timeout=30
        )
        counter = Counter(f.strip() for f in result.stdout.strip().split("\n") if f.strip())
        hotspots = []
        for path, count in counter.most_common(30):
            mem_path = source_to_memtree(path, path_map)
            if mem_path:
                hotspots.append((mem_path, count))
        return hotspots[:15]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_change_coupling(path_map: dict, days: int) -> list[tuple[str, str, int]]:
    """Find files that frequently change together (cross-service only)."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--name-only", "--pretty=format:---COMMIT---"],
            capture_output=True, text=True, cwd=ROOT, timeout=30
        )
        pair_counts: Counter[tuple[str, str]] = Counter()
        for commit_block in result.stdout.split("---COMMIT---"):
            files_in_commit = []
            for f in commit_block.strip().split("\n"):
                f = f.strip()
                mem = source_to_memtree(f, path_map)
                if mem:
                    files_in_commit.append(mem)
            unique_files = sorted(set(files_in_commit))
            for i, a in enumerate(unique_files):
                for b in unique_files[i + 1:]:
                    if a.split("/")[0] != b.split("/")[0]:
                        pair_counts[(a, b)] += 1
        return [(a, b, c) for (a, b), c in pair_counts.most_common(10) if c >= 2]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def parse_pitfalls(services: list[str]) -> dict[str, list[dict]]:
    """Parse all PITFALLS.md files for lifecycle stats."""
    stats: dict[str, list[dict]] = {}
    for svc in services:
        path = MEMORY / svc / "PITFALLS.md"
        if not path.exists():
            continue
        content = path.read_text()
        entries = []
        current: dict | None = None
        for line in content.split("\n"):
            if line.startswith("### "):
                if current:
                    entries.append(current)
                current = {"title": line[4:].strip(), "resolved": line[4:].strip().startswith("~~"),
                           "type": "unknown", "last_seen": "unknown"}
            elif current and "**type**:" in line.lower() or current and "**类型**:" in line:
                m = re.search(r'(?:\*\*type\*\*|\*\*类型\*\*):\s*(\w[\w-]*)', line, re.IGNORECASE)
                if m:
                    current["type"] = m.group(1)
            elif current and "**last_seen**:" in line.lower():
                m = re.search(r'\*\*last_seen\*\*:\s*([\d-]+)', line, re.IGNORECASE)
                if m:
                    current["last_seen"] = m.group(1)
        if current:
            entries.append(current)
        stats[svc] = entries
    return stats


def find_stale(stats: dict, threshold_days: int = 30) -> list[dict]:
    """Find pitfalls not validated in threshold_days."""
    cutoff = (datetime.now() - timedelta(days=threshold_days)).strftime("%Y-%m-%d")
    stale = []
    for svc, entries in stats.items():
        for e in entries:
            if e["resolved"] or e["type"] == "architecture":
                continue
            if e["last_seen"] != "unknown" and e["last_seen"] < cutoff:
                stale.append({"service": svc, **e})
    return stale


def count_events() -> dict[str, int]:
    """Count events by type."""
    counts: Counter[str] = Counter()
    for evt in MEMORY.glob("events/*/EVT-*.md"):
        content = evt.read_text()
        m = re.search(r'^type:\s*(\w+)', content, re.MULTILINE)
        if m:
            counts[m.group(1)] += 1
    return dict(counts)


def generate(services: list[str], path_map: dict) -> str:
    """Generate HEALTH.md content."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = ["# System Health", "", f"> Auto-generated: {now} | Script: scripts/generate-health.py", ""]

    hotspots = get_git_hotspots(path_map, DAYS)
    lines.append(f"## Change Hotspots (last {DAYS} days)")
    lines.append("")
    if hotspots:
        lines += ["| File | Changes | Risk |", "|------|---------|------|"]
        for path, count in hotspots:
            risk = "🔴 High-churn" if count >= 4 else "🟡" if count >= 2 else "—"
            lines.append(f"| {path} | {count} | {risk} |")
    else:
        lines.append("(no data)")
    lines.append("")

    coupling = get_change_coupling(path_map, DAYS)
    lines.append("## Change Coupling (cross-service)")
    lines.append("")
    if coupling:
        lines += ["| File A | File B | Co-changes |", "|--------|--------|-----------|"]
        for a, b, c in coupling:
            lines.append(f"| {a} | {b} | {c} |")
    else:
        lines.append("(no cross-service coupling detected)")
    lines.append("")

    pitfall_stats = parse_pitfalls(services)
    total_active, total_resolved = 0, 0
    type_counts: Counter[str] = Counter()
    svc_counts: dict[str, int] = {}
    for svc, entries in pitfall_stats.items():
        active = [e for e in entries if not e["resolved"]]
        total_active += len(active)
        total_resolved += sum(1 for e in entries if e["resolved"])
        svc_counts[svc] = len(active)
        for e in active:
            type_counts[e["type"]] += 1
    svc_summary = ", ".join(f"{s} {c}" for s, c in sorted(svc_counts.items(), key=lambda x: -x[1]) if c > 0)

    lines += ["## PITFALL Stats", "", "| Metric | Value |", "|--------|-------|"]
    lines.append(f"| Active | {total_active} ({svc_summary}) |")
    for t in ["architecture", "bug-derived", "config", "unknown"]:
        if type_counts[t]:
            lines.append(f"| {t} | {type_counts[t]} |")
    lines.append(f"| Resolved | {total_resolved} |")

    stale = find_stale(pitfall_stats)
    if stale:
        lines.append(f"| ⚠️ Stale (>30d) | {len(stale)} |")
        lines += ["", "### ⚠️ Stale PITFALLs", "", "| PITFALL | Service | last_seen |", "|---------|---------|-----------|"]
        for s in stale:
            lines.append(f"| {s['title'][:50]} | {s['service']} | {s['last_seen']} |")
    lines.append("")

    event_counts = count_events()
    if event_counts:
        lines += ["## Event Stats", "", "| Type | Count |", "|------|-------|"]
        for t in ["bugfix", "feature", "refactor", "deploy", "incident"]:
            if event_counts.get(t):
                lines.append(f"| {t} | {event_counts[t]} |")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    config = load_config()
    if not config:
        print("ERROR: No config found")
        sys.exit(1)
    services = get_services(config)
    path_map = build_path_map(config)
    health = generate(services, path_map)
    output = MEMORY / "HEALTH.md"
    output.write_text(health + "\n")
    print(health)
    print(f"\nWritten to: {output}")

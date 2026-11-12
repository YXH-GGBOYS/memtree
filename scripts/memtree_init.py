#!/usr/bin/env python3
"""Create a project's `.memory/` from the MemTree templates. Never overwrites an existing file.

Creates (each only if missing):
  .memory/CRITICAL_FACTS.md        hard invariants + the DIGEST block the hooks inject
  .memory/memtree.json             minimal config ("extra_sources" for memq)
  .memory/events/INDEX.md          one line per event
  .memory/events/TEMPLATE.md       event file template
  .memory/threads/_TEMPLATE.md     handoff card template (files starting with "_" are not cards)
  .memory/<area>/PITFALLS.md       one per --areas entry

With --claude-md, also appends the MemTree snippet to <project>/CLAUDE.md, unless the file already
contains the `<!-- memtree:begin -->` marker (creates CLAUDE.md if there is none).

Examples:
  python3 memtree_init.py --areas billing,auth,api
  python3 memtree_init.py --project ../my-app --areas api --claude-md --dry-run
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
MARKER = "<!-- memtree:begin -->"
AREA = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")


def project_root() -> Path:
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    except OSError:
        return Path.cwd()
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else Path.cwd()


def plan(project: Path, areas: List[str]) -> List[Tuple[Path, str]]:
    mem = project / ".memory"
    items = [
        (mem / "CRITICAL_FACTS.md", (TEMPLATES / "CRITICAL_FACTS.md").read_text(encoding="utf-8")),
        (mem / "memtree.json", (TEMPLATES / "memtree.json").read_text(encoding="utf-8")),
        (mem / "events" / "INDEX.md", (TEMPLATES / "events_INDEX.md").read_text(encoding="utf-8")),
        (mem / "events" / "TEMPLATE.md", (TEMPLATES / "EVENT.md").read_text(encoding="utf-8")),
        (mem / "threads" / "_TEMPLATE.md", (TEMPLATES / "thread_card.md").read_text(encoding="utf-8")),
    ]
    pitfalls = (TEMPLATES / "PITFALLS.md").read_text(encoding="utf-8")
    for area in areas:
        items.append((mem / area / "PITFALLS.md", pitfalls.replace("<area>", area)))
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", help="project root (default: git top level, else the current directory)")
    ap.add_argument("--areas", default="", help="comma-separated area / service names, e.g. billing,auth,api")
    ap.add_argument("--claude-md", action="store_true", help="append the MemTree snippet to CLAUDE.md")
    ap.add_argument("--dry-run", action="store_true", help="only print what would be created")
    args = ap.parse_args()

    project = Path(args.project).expanduser().resolve() if args.project else project_root()
    if not project.is_dir():
        print(f"memtree_init: not a directory: {project}", file=sys.stderr)
        return 2
    areas = [a.strip() for a in args.areas.split(",") if a.strip()]
    bad = [a for a in areas if not AREA.fullmatch(a) or a in ("events", "threads", "archive")]
    if bad:
        print(f"memtree_init: invalid area name(s): {', '.join(bad)} (letters, digits, . _ -; "
              "not events/threads/archive)", file=sys.stderr)
        return 2

    created, skipped = [], []
    for path, text in plan(project, areas):
        rel = path.relative_to(project).as_posix()
        if path.exists():
            skipped.append(rel)
            continue
        created.append(rel)
        if not args.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    if args.claude_md:
        claude_md = project / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8") if claude_md.is_file() else ""
        if MARKER in existing:
            skipped.append("CLAUDE.md (MemTree snippet already present)")
        else:
            snippet = (TEMPLATES / "CLAUDE.md.snippet").read_text(encoding="utf-8")
            sep = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
            created.append("CLAUDE.md (snippet appended)" if existing else "CLAUDE.md (new, snippet only)")
            if not args.dry_run:
                claude_md.write_text(existing + sep + snippet, encoding="utf-8")

    verb = "would create" if args.dry_run else "created"
    print(f"project: {project}")
    for rel in created:
        print(f"  {verb}: {rel}")
    for rel in skipped:
        print(f"  kept (already exists): {rel}")
    if not args.dry_run and created:
        print("next: write the real hard invariants into the DIGEST block of .memory/CRITICAL_FACTS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())

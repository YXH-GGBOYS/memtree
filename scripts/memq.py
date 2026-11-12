#!/usr/bin/env python3
"""Look things up in the MemTree knowledge layers and get one short card per hit.

Use this instead of grepping PITFALLS / events/INDEX.md directly: their lines are often hundreds of
characters long, and a broad keyword can pull hundreds of KB into context. A card is one line of
location plus one snippet; when you need the detail, Read that file with offset/limit.

Sources (under the project's .memory/):
  critical  CRITICAL_FACTS.md
  pitfalls  any */PITFALLS*.md (archive/ folders skipped)
  events    events/INDEX.md (one line per event)
  threads   threads/*.md handoff cards (README.md and _*.md skipped)
  extra     paths or globs listed in .memory/memtree.json under "extra_sources" (relative to the project)

Matching: every keyword must appear in the same line (case-insensitive). Each entry (the nearest
heading above the hit, or the event line itself) is shown once, with its best-scoring line.

Output:  [kind] path:line  <heading or event line>
             <snippet, at most 160 characters>
Exit status: 0 when something matched, 1 when nothing did, 2 when no .memory/ was found.

Examples:
  python3 memq.py refund webhook
  python3 memq.py timeout --only pitfalls,events -n 20
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SNIPPET = 160
TITLE = 100
HEADING = re.compile(r"^(#{1,6})\s+(.*)")
KINDS = ("critical", "pitfalls", "threads", "events", "extra")


def _worktree_main(git_file: Path) -> Optional[Path]:
    try:
        line = git_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not line.startswith("gitdir:"):
        return None
    gitdir = Path(line[7:].strip())
    if not gitdir.is_absolute():
        gitdir = (git_file.parent / gitdir).resolve()
    parts = gitdir.parts
    if "worktrees" not in parts:
        return None
    idx = len(parts) - 1 - parts[::-1].index("worktrees")
    dot_git = Path(*parts[:idx])
    return dot_git.parent if dot_git.name == ".git" else None


def find_project(start: Path) -> Optional[Path]:
    """Nearest directory upward that has .memory/ (or whose git worktree main checkout has it)."""
    here = start.resolve()
    for d in (here, *here.parents):
        if (d / ".memory").is_dir():
            return d
        if (d / ".git").is_file():
            main = _worktree_main(d / ".git")
            if main is not None and (main / ".memory").is_dir():
                return main
    return None


def sources(project: Path) -> Dict[str, List[Path]]:
    mem = project / ".memory"
    threads = mem / "threads"
    out: Dict[str, List[Path]] = {
        "critical": [mem / "CRITICAL_FACTS.md"],
        "pitfalls": sorted(p for p in mem.glob("**/PITFALLS*.md") if "archive" not in p.relative_to(mem).parts),
        "threads": sorted(p for p in threads.glob("*.md")
                          if p.name.lower() != "readme.md" and not p.name.startswith("_")) if threads.is_dir() else [],
        "events": [mem / "events" / "INDEX.md"],
        "extra": [],
    }
    cfg = mem / "memtree.json"
    if cfg.is_file():
        try:
            extra = json.loads(cfg.read_text(encoding="utf-8")).get("extra_sources") or []
        except (ValueError, AttributeError):
            extra = []
        for pattern in extra if isinstance(extra, list) else []:
            if isinstance(pattern, str) and pattern and ".." not in Path(pattern).parts:
                out["extra"].extend(sorted(p for p in project.glob(pattern) if p.is_file()))
    return out


@dataclass
class Card:
    kind: str
    path: Path
    line: int
    title: str
    title_line: int
    snippet: str
    score: int


def snippet_around(text: str, words: List[str]) -> str:
    text = text.strip()
    low = text.lower()
    hits = [low.find(w) for w in words if low.find(w) >= 0]
    pos = min(hits) if hits else 0
    start = max(0, pos - SNIPPET // 3)
    body = text[start:start + SNIPPET].strip()
    return ("…" if start else "") + body + ("…" if start + SNIPPET < len(text) else "")


def search(kind: str, path: Path, words: List[str]) -> List[Card]:
    if not path.is_file():
        return []
    cards: List[Card] = []
    title, title_line = "", 0
    for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        m = HEADING.match(line)
        if m:
            title, title_line = m.group(2).strip(), n
        low = line.lower()
        if not all(w in low for w in words):
            continue
        if kind == "events" or not title:
            head, head_line = line.strip(), n  # an index line is its own entry
        else:
            head, head_line = title, title_line
        score = sum(low.count(w) for w in words) + (3 if m else 0)
        title_text = head if len(head) <= TITLE else head[:TITLE - 1] + "…"
        snip = "" if n == head_line and len(head) <= TITLE else snippet_around(line, words)
        cards.append(Card(kind, path, n, title_text, head_line, snip, score))
    return cards


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words", nargs="+", help="keywords; all must appear in the same line")
    ap.add_argument("-n", type=int, default=10, help="maximum number of cards (default 10)")
    ap.add_argument("--only", help="comma-separated subset of: " + ",".join(KINDS))
    ap.add_argument("--root", help="project directory (default: nearest parent with .memory/)")
    args = ap.parse_args()

    project = Path(args.root).resolve() if args.root else find_project(Path.cwd())
    if project is None or not (project / ".memory").is_dir():
        print("memq: no .memory/ directory found (run from inside the project or pass --root)", file=sys.stderr)
        return 2
    wanted = {k.strip() for k in args.only.split(",")} if args.only else set(KINDS)
    words = [w.lower() for w in args.words]

    cards: List[Card] = []
    for kind, paths in sources(project).items():
        if kind in wanted:
            for p in paths:
                cards.extend(search(kind, p, words))
    if not cards:
        print(f"no match for: {' '.join(args.words)} (searched: {', '.join(k for k in KINDS if k in wanted)})")
        return 1

    best: Dict[Tuple[Path, int, str], Card] = {}
    for c in cards:
        key = (c.path, c.title_line, c.title)
        if key not in best or c.score > best[key].score:
            best[key] = c
    ranked = sorted(best.values(), key=lambda c: (-c.score, KINDS.index(c.kind), str(c.path), c.line))
    for c in ranked[: args.n]:
        try:
            shown = c.path.relative_to(project)
        except ValueError:
            shown = c.path
        print(f"[{c.kind}] {shown}:{c.line}  {c.title}")
        if c.snippet:
            print(f"    {c.snippet}")
    if len(ranked) > args.n:
        print(f"…{len(ranked) - args.n} more; raise -n or add a keyword")
    return 0


if __name__ == "__main__":
    sys.exit(main())

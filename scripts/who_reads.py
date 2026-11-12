#!/usr/bin/env python3
"""Before changing a shared field, status value or constant: list everyone who reads it.

The usual mistake is to verify only the path you changed and never ask who else consumes the value.
This script lists every occurrence in code files, grouped as:

  writes      - assignments and updates (`x = ...`, `SET x =`, `.update(`, `setattr(`)
  conditions  - places that decide something from it (`if`, `while`, `where`, `filter`, `case`/`when`,
                `==`, `!=`, `in (...)`, `IS NULL` ...). This is the group people forget: change what a
                field holds and one of these can become always-true or always-false without any error.
  other       - everything else (reads, serialization, logging, tests)

A line can appear under both writes and conditions. Matching is fixed-string and case-sensitive.
Uses `git grep` (tracked + untracked, not ignored files) inside a git repo, else walks the directory.

For each condition, ask: will it see a different value after my change? Is the same rule enforced
elsewhere through a different field? Did my change make it always true or always false?

Exit status: 0 = occurrences found, 1 = none found.

Examples:
  python3 who_reads.py subscription_status
  python3 who_reads.py "'past_due'" --roots ../web-frontend
  python3 who_reads.py retry_count --all-files      # include docs and config too
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

CODE_EXT = (".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".go", ".rs",
            ".java", ".kt", ".kts", ".scala", ".rb", ".php", ".cs", ".swift", ".dart", ".ex", ".exs",
            ".sql", ".sh", ".lua", ".c", ".h", ".cc", ".cpp", ".hpp", ".m", ".mm")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "site-packages", "vendor", "dist", "build",
             "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", ".next", ".nuxt", "target"}
CONDITION = re.compile(
    r"\b(if|elif|else if|while|unless|when|case|switch|where|filter|filter_by|exclude|having|assert|expect)\b"
    r"|==|!=|<>|\bis\s+(not\s+)?(None|null|nil|True|False)\b|\bnot in\b|\bin\s*[(\[{]|\.in_\(|\.includes\(|\bIN\s*\("
    r"|\bIS\s+(NOT\s+)?NULL\b|\?\s|&&|\|\|",
    re.IGNORECASE,
)


def write_pattern(sym: str) -> "re.Pattern[str]":
    s = re.escape(sym)
    return re.compile(
        rf"{s}\s*(=(?!=)|\+=|-=|\*=|/=|\|=|:=|\?\?=)"   # x = ..., x += ...
        rf"|\bSET\b[^;]*{s}\s*="                       # SQL UPDATE ... SET x =
        rf"|\.(update|set|setdefault|values|assign|put|patch)\(.*{s}"
        rf"|setattr\(.*{s}",
        re.IGNORECASE,
    )


def git_root(path: Path) -> Optional[Path]:
    if shutil.which("git") is None:
        return None
    r = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def find(root: Path, sym: str, all_files: bool, use_git: bool) -> List[str]:
    if use_git:
        r = subprocess.run(["git", "-C", str(root), "grep", "-n", "-I", "--untracked", "--no-color", "-F", "-e", sym],
                           capture_output=True, text=True, errors="replace")
        if r.returncode not in (0, 1):
            raise RuntimeError(r.stderr.strip() or f"git grep exited {r.returncode}")
        hits = [ln for ln in r.stdout.splitlines() if ln]
    else:
        hits = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                path = Path(dirpath) / name
                if not all_files and not name.lower().endswith(CODE_EXT):
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                rel = path.relative_to(root).as_posix()
                hits.extend(f"{rel}:{n}:{line}" for n, line in enumerate(text.splitlines(), 1) if sym in line)
    if not all_files:
        hits = [h for h in hits if h.split(":", 1)[0].lower().endswith(CODE_EXT)]
    return hits


def classify(hits: List[str], sym: str) -> Dict[str, List[str]]:
    wp = write_pattern(sym)
    groups: Dict[str, List[str]] = {"writes": [], "conditions": [], "other": []}
    for h in hits:
        parts = h.split(":", 2)
        code = parts[2] if len(parts) == 3 else h
        is_write = bool(wp.search(code))
        is_cond = bool(CONDITION.search(code))
        if is_write:
            groups["writes"].append(h)
        if is_cond:
            groups["conditions"].append(h)
        if not is_write and not is_cond:
            groups["other"].append(h)
    return groups


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("symbol", help="field name, status literal or constant (fixed string)")
    ap.add_argument("--roots", nargs="*", default=[], help="extra directories to search (default: the current repo)")
    ap.add_argument("--all-files", action="store_true", help="include non-code files (docs, config)")
    ap.add_argument("--no-git", action="store_true", help="walk directories even inside a git repo")
    args = ap.parse_args()

    base = git_root(Path.cwd()) or Path.cwd()
    roots: List[Path] = []
    for r in [str(base)] + list(args.roots):
        p = Path(r).expanduser().resolve()
        if p.is_dir() and p not in roots:
            roots.append(p)

    total = 0
    print(f"who reads `{args.symbol}`")
    for root in roots:
        use_git = not args.no_git and git_root(root) is not None
        try:
            hits = find(root, args.symbol, args.all_files, use_git)
        except RuntimeError as exc:
            print(f"\n== {root.name}: search failed, no conclusion: {exc}")
            return 2
        if not hits:
            continue
        total += len(hits)
        groups = classify(hits, args.symbol)
        print(f"\n== {root.name} ({len(hits)} lines)")
        for name, label in (("writes", "writes"), ("conditions", "conditions  <- the group people forget"),
                            ("other", "other")):
            if groups[name]:
                print(f"  [{label}]")
                for h in groups[name]:
                    print(f"    {h[:220]}")
    if not total:
        scope = "code and other files" if args.all_files else "code files"
        print(f"\nno occurrences in {scope} under: {', '.join(str(r) for r in roots)}")
        return 1
    print(f"\n{total} lines. For each condition: does it see a different value after your change? "
          "Is the same rule enforced elsewhere through a different field? Did it just become always true or always false?")
    return 0


if __name__ == "__main__":
    sys.exit(main())

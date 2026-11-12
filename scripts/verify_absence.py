#!/usr/bin/env python3
"""Check a negative assertion ("X doesn't exist", "we can't do X", "needs to be built") before you write it down.

Negative claims are dangerous in a knowledge base: a positive claim fails loudly the first time someone
runs it, but "X doesn't exist" gets copied into handoffs and plans unchallenged, and when it is wrong the
error always points toward extra work (rebuilding something that is already there). One common way to
produce a false "doesn't exist" is a search that silently errored: in zsh, an unquoted
`grep -r foo --include=*.py .` fails with "no matches found" and prints nothing, which looks exactly like
a real zero.

This script searches each root with two independent methods and prints the exact commands and hit
counts, so the claim can be reproduced or refuted later:
  A. fixed string, case-sensitive          (git grep -F, or a Python walk outside git)
  B. case-insensitive regex that also matches separator variants: in `refund_window`, `refund-window`,
     `refundWindow`, `REFUND WINDOW` the separators `_`, `-`, space and camelCase boundaries are optional
git grep searches tracked and untracked files but skips .gitignore'd ones; the Python walk skips common
dependency and build folders. Hits in docs (.md, .txt, .yaml, .json ...) are counted separately: a doc
that discusses a symbol is not code that has it.

Exit status: 0 = found somewhere, 1 = not found in the whole scope, 2 = a search failed (no conclusion).

Even zero hits only means "not found by these searches". Before writing "doesn't exist", also rule out:
another name for it, something that only exists at runtime (a DB column, an env flag, deployed config),
a repository you did not search, and the capability states below.

Capability states (say which one, never just "exists / doesn't"):
  1. doesn't exist           - nothing to find; it really has to be built
  2. built but not wired     - the code is there, nothing calls it
  3. wired but switched off  - it is called, behind a flag or config that is off
  4. live                    - it runs. Claiming this needs runtime evidence (rows, logs, a real run);
                               reading code cannot show it
  trap: running but always "unknown" - it runs and logs, yet every result is "can't tell". Counting rows
        is not enough; check that its output is usable before relying on it.

Examples:
  python3 verify_absence.py refund_window
  python3 verify_absence.py RetryPolicy --roots ../billing-service ../shared-lib
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "site-packages", "vendor", "dist", "build",
             "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", ".next", ".nuxt", "target"}
DOC_EXT = (".md", ".txt", ".rst", ".yaml", ".yml", ".json", ".csv", ".toml", ".ini")
MAX_FILE = 2 * 1024 * 1024


def variant_regex(term: str) -> str:
    """Case-insensitive pattern: separators and camelCase boundaries become optional `[-_ ]?`."""
    parts = [p for p in re.split(r"[-_\s]+|(?<=[a-z0-9])(?=[A-Z])", term) if p]
    return r"[-_ ]?".join(re.escape(p) for p in parts) if parts else re.escape(term)


def git_toplevel(path: Path) -> Optional[Path]:
    if shutil.which("git") is None:
        return None
    r = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def run_git(root: Path, args: List[str]) -> Tuple[List[str], str, Optional[str]]:
    cmd = ["git", "-C", str(root), "grep", "-n", "-I", "--untracked", "--no-color"] + args
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    shown = " ".join(shlex.quote(c) for c in cmd)
    if r.returncode not in (0, 1):  # 1 = no match, anything else = error
        return [], shown, (r.stderr.strip() or f"git grep exited {r.returncode}")
    return [ln for ln in r.stdout.splitlines() if ln], shown, None


def walk(root: Path, matcher: "re.Pattern[str]") -> Tuple[List[str], Optional[str]]:
    hits: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            try:
                if path.stat().st_size > MAX_FILE:
                    continue
                data = path.read_bytes()
            except OSError:
                continue
            if b"\0" in data[:4096]:
                continue  # binary
            rel = path.relative_to(root).as_posix()
            for n, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
                if matcher.search(line):
                    hits.append(f"{rel}:{n}:{line}")
    return hits, None


def search(root: Path, term: str, use_git: bool) -> List[Tuple[str, str, List[str], Optional[str]]]:
    """Return [(method, command, hits, error)] for methods A and B."""
    rx = variant_regex(term)
    if use_git:
        a_hits, a_cmd, a_err = run_git(root, ["-F", "-e", term])
        b_hits, b_cmd, b_err = run_git(root, ["-i", "-E", "-e", rx])
    else:
        a_hits, a_err = walk(root, re.compile(re.escape(term)))
        b_hits, b_err = walk(root, re.compile(rx, re.IGNORECASE))
        skip = ",".join(sorted(SKIP_DIRS))
        a_cmd = f"python walk of {root} (skip: {skip}) fixed string {term!r}"
        b_cmd = f"python walk of {root} (skip: {skip}) regex {rx!r} ignore-case"
    return [("A fixed string", a_cmd, a_hits, a_err), ("B ignore-case variants", b_cmd, b_hits, b_err)]


def is_doc(hit: str) -> bool:
    return hit.split(":", 1)[0].lower().endswith(DOC_EXT)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("terms", nargs="+", help="symbols or strings to look for (taken literally)")
    ap.add_argument("--roots", nargs="*", default=[], help="extra directories to search (default: the current repo)")
    ap.add_argument("--no-git", action="store_true", help="use the Python walk even inside a git repo")
    ap.add_argument("--show", type=int, default=10, help="hit lines to print per method and root (default 10)")
    args = ap.parse_args()

    base = git_toplevel(Path.cwd()) or Path.cwd()
    roots: List[Path] = []
    for r in [str(base)] + list(args.roots):
        p = Path(r).expanduser().resolve()
        if p not in roots:
            roots.append(p)
    missing = [str(p) for p in roots if not p.is_dir()]
    if missing:
        print(f"verify_absence: not a directory: {', '.join(missing)}", file=sys.stderr)
        return 2

    any_found, any_error = False, False
    print("# Negative-assertion check")
    print(f"roots: {', '.join(str(r) for r in roots)}\n")
    for term in args.terms:
        print(f"## `{term}`")
        total = 0
        for root in roots:
            use_git = not args.no_git and git_toplevel(root) is not None
            for method, cmd, hits, err in search(root, term, use_git):
                if err:
                    any_error = True
                    print(f"- {root.name} / {method}: ERROR, no conclusion possible: {err}\n    command: {cmd}")
                    continue
                docs = sum(1 for h in hits if is_doc(h))
                print(f"- {root.name} / {method}: {len(hits)} hit lines ({len(hits) - docs} outside docs)\n    command: {cmd}")
                for h in hits[: args.show]:
                    print(f"      {h[:200]}")
                if len(hits) > args.show:
                    print(f"      ... {len(hits) - args.show} more")
                total += len(hits)
        if total:
            any_found = True
            print(f"\nResult: `{term}` EXISTS somewhere in scope. A claim that it doesn't exist is false; correct it "
                  "in the file where it was written (a correction only said in chat is not a correction).\n")
        else:
            print(f"\nResult: `{term}` not found by either method in {len(roots)} root(s). That is 'not found', not "
                  "'doesn't exist' yet: try other names, runtime-only places, other repos, and decide which capability "
                  "state applies (see --help).\n")
    print("Reproduce: python3 verify_absence.py " + " ".join(shlex.quote(t) for t in args.terms)
          + (" --roots " + " ".join(shlex.quote(r) for r in args.roots) if args.roots else ""))
    if any_error:
        return 2
    return 0 if any_found else 1


if __name__ == "__main__":
    sys.exit(main())

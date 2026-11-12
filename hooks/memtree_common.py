"""Shared helpers for the MemTree hooks (stdlib only, Python 3.9+).

Rules every MemTree hook follows:
  * Inject text only. Never block, rewrite or reroute a tool call; never register a PreToolUse handler.
  * Always exit 0. A hook that exits 2 would block the user's prompt, so `run()` turns any error into
    one visible line instead.
  * Print nothing when the working directory is not inside a MemTree project, so a global install is
    safe. A MemTree project is a directory whose `.memory/` contains `CRITICAL_FACTS.md` or `memtree.json`
    (a bare `.memory/` left by some other tool is ignored).
  * Keep every output under OUTPUT_BUDGET bytes. Claude Code caps hook output at 10,000 characters;
    above that it saves the text to a file and shows the model only a ~2,000-character preview.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable, Dict, Optional

DIGEST_START = "<!-- DIGEST-START -->"
DIGEST_END = "<!-- DIGEST-END -->"
BULLET = "• "  # "• "
OUTPUT_BUDGET = 9000  # bytes, safely below the 10,000-character cap
TRUNCATED = "…truncated ({n:,} more bytes not shown; Read {path} for the rest)"


def read_hook_input() -> Dict[str, object]:
    """Parse the JSON object Claude Code sends on stdin. Anything unparsable becomes {}."""
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def start_dir(data: Dict[str, object]) -> Path:
    """Where to start looking for `.memory/`: the hook's cwd, then the project dir, then our cwd."""
    for cand in (data.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR"), os.getcwd()):
        if isinstance(cand, str) and cand and Path(cand).is_dir():
            return Path(cand)
    return Path.cwd()


def _is_memtree_dir(mem: Path) -> bool:
    return (mem / "CRITICAL_FACTS.md").is_file() or (mem / "memtree.json").is_file()


def _main_checkout_of_worktree(git_file: Path) -> Optional[Path]:
    """A linked git worktree has a `.git` *file* ("gitdir: <main>/.git/worktrees/<name>")."""
    try:
        line = git_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not line.startswith("gitdir:"):
        return None
    gitdir = Path(line[len("gitdir:"):].strip())
    if not gitdir.is_absolute():
        gitdir = (git_file.parent / gitdir).resolve()
    parts = gitdir.parts
    if "worktrees" in parts:
        idx = len(parts) - 1 - parts[::-1].index("worktrees")
        dot_git = Path(*parts[:idx])
        if dot_git.name == ".git":
            return dot_git.parent
    return None


def find_memory_dir(start: Path) -> Optional[Path]:
    """Walk up from `start` to the first `.memory/` that belongs to MemTree.

    Also follows a linked git worktree back to its main checkout, because worktrees usually
    do not carry an untracked or separately committed `.memory/`.
    """
    try:
        here = start.resolve()
    except OSError:
        return None
    for d in (here, *here.parents):
        mem = d / ".memory"
        if _is_memtree_dir(mem):
            return mem
        git = d / ".git"
        if git.is_file():
            main = _main_checkout_of_worktree(git)
            if main is not None and _is_memtree_dir(main / ".memory"):
                return main / ".memory"
    return None


def extract_digest(facts: Path) -> Optional[str]:
    """Return the `• ` lines between the DIGEST markers, or None when markers or bullets are missing."""
    try:
        text = facts.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    start = text.find(DIGEST_START)
    end = text.find(DIGEST_END, start + len(DIGEST_START)) if start >= 0 else -1
    if start < 0 or end < 0:
        return None
    lines = [ln.strip() for ln in text[start + len(DIGEST_START):end].splitlines()]
    bullets = [ln for ln in lines if ln.startswith(BULLET)]
    return "\n".join(bullets) or None


def digest_hash(digest: str) -> str:
    return hashlib.sha256(digest.encode("utf-8")).hexdigest()[:16]


def state_dir(kind: str) -> Path:
    base = os.environ.get("MEMTREE_STATE_DIR")
    root = Path(base) if base else Path.home() / ".claude" / "state" / "memtree"
    return root / kind


def safe_name(session_id: str) -> str:
    """Session ids become file names; anything unusual is hashed so it cannot escape the state dir."""
    if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", session_id) and session_id not in (".", ".."):
        return session_id
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]


def session_id(data: Dict[str, object]) -> str:
    sid = data.get("session_id")
    return sid if isinstance(sid, str) else ""


def read_marker(kind: str, sid: str) -> Optional[str]:
    try:
        return (state_dir(kind) / safe_name(sid)).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def write_marker(kind: str, sid: str, value: str) -> None:
    d = state_dir(kind)
    d.mkdir(parents=True, exist_ok=True)
    (d / safe_name(sid)).write_text(value, encoding="utf-8")


def display_path(path: Path, base: Path) -> str:
    """Path relative to the working directory when that is short, else absolute."""
    try:
        rel = os.path.relpath(path, base)
    except ValueError:  # different drive on Windows
        return str(path)
    return rel if not rel.startswith(".." + os.sep + ".." + os.sep + "..") else str(path)


def clip(text: str, budget: int, source: str = "the file") -> str:
    """Cut `text` to at most `budget` UTF-8 bytes on a character boundary, ending with a visible note."""
    raw = text.encode("utf-8")
    if len(raw) <= budget:
        return text
    note_len = len(TRUNCATED.format(n=len(raw), path=source).encode("utf-8")) + 1
    keep = max(0, budget - note_len)
    head = raw[:keep].decode("utf-8", errors="ignore")  # drops a split trailing character
    omitted = len(raw) - len(head.encode("utf-8"))
    return head.rstrip("\n") + "\n" + TRUNCATED.format(n=omitted, path=source)


def render_digest(digest: str, facts_label: str, changed: bool = False) -> str:
    head = "changed since it was last injected in this session" if changed else "if anything conflicts with these, the file wins"
    return f"\U0001F512 Hard invariants from {facts_label} ({head}):\n{digest}"


def missing_digest_line(facts_label: str) -> str:
    return (f"\U0001F534 MemTree: no DIGEST block found in {facts_label} (expected {DIGEST_START} ... {DIGEST_END} "
            f"with one fact per line starting with '{BULLET.strip()} '). Hard invariants were NOT injected: read "
            f"{facts_label} yourself before acting, and fix the markers.")


def emit(text: str) -> None:
    """Write UTF-8 regardless of the console encoding (Windows consoles default to a code page)."""
    if not text:
        return
    sys.stdout.buffer.write((text.rstrip("\n") + "\n").encode("utf-8"))
    sys.stdout.flush()


def run(main: Callable[[], None]) -> None:
    """Entry point wrapper: a hook error becomes one visible line, never a blocked prompt."""
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - last-resort boundary; the hook must still exit 0
        emit(f"\U0001F534 MemTree hook {Path(sys.argv[0]).name} failed: {type(exc).__name__}: {exc}")
    sys.exit(0)

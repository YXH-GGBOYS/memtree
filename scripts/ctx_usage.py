#!/usr/bin/env python3
"""Show how much context the current Claude Code session is using, read from its transcript.

This is not an estimate. Claude Code writes each assistant call's real usage into the session
transcript (a .jsonl file under ~/.claude/projects/). The context of a call is
input_tokens + cache_read_input_tokens + cache_creation_input_tokens: everything the model was sent.
The last call's number is what the context bar in the UI shows. It is one turn behind, because the
transcript is written when a turn ends.

Which transcript:
  --transcript PATH, else --session ID, else $CLAUDE_CODE_SESSION_ID (searched under projects/*/),
  else the newest transcript in the project folder derived from the current directory.
  The Claude Code config dir is $CLAUDE_CONFIG_DIR, default ~/.claude.

Examples:
  python3 ctx_usage.py
  python3 ctx_usage.py --json
  python3 ctx_usage.py --window 200000
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

WINDOW_1M = 1_000_000
WINDOW_200K = 200_000
KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def config_dir() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env) if env else Path.home() / ".claude"


def project_folder(cwd: str) -> Path:
    """Claude Code names a project's transcript folder after its path, non-alphanumerics -> '-'."""
    return config_dir() / "projects" / re.sub(r"[^A-Za-z0-9]", "-", cwd)


def find_transcript(transcript: Optional[str], session: Optional[str]) -> Optional[Path]:
    if transcript:
        p = Path(transcript).expanduser()
        return p if p.is_file() else None
    sid = session or os.environ.get("CLAUDE_CODE_SESSION_ID")
    projects = config_dir() / "projects"
    if sid and projects.is_dir():
        hits = sorted(projects.glob(f"*/{sid}.jsonl"))
        if hits:
            return hits[0]
    folder = project_folder(os.getcwd())
    if folder.is_dir():
        files = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            return files[0]
    return None


def last_usage(transcript: Path) -> Optional[Dict[str, Any]]:
    """Usage of the last main-thread assistant call (deduplicated by message id)."""
    last: Optional[Dict[str, Any]] = None
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"usage"' not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict) or entry.get("type") != "assistant" or entry.get("isSidechain"):
                continue
            msg = entry.get("message") or {}
            usage = msg.get("usage") if isinstance(msg, dict) else None
            if not isinstance(usage, dict) or sum(int(usage.get(k) or 0) for k in KEYS) <= 0:
                continue
            last = {"id": msg.get("id"), "model": msg.get("model") or "", "usage": usage}
    return last


def guess_window(model: str, tokens: int) -> int:
    m = model.lower()
    if "[1m]" in m or "-1m" in m or tokens > WINDOW_200K:
        return WINDOW_1M
    if "haiku" in m:
        return WINDOW_200K
    return WINDOW_1M


def compute(transcript: Optional[str], session: Optional[str], window: Optional[int]) -> Dict[str, Any]:
    path = find_transcript(transcript, session)
    if path is None:
        return {"error": "no transcript found (pass --transcript, or run inside a Claude Code session)"}
    last = last_usage(path)
    if last is None:
        return {"error": f"no assistant usage recorded yet in {path}"}
    u = last["usage"]
    tokens = sum(int(u.get(k) or 0) for k in KEYS)
    win = window or int(os.environ.get("MEMTREE_CONTEXT_WINDOW") or 0) or guess_window(last["model"], tokens)
    return {
        "context_tokens": tokens,
        "window": win,
        "pct": round(tokens / win * 100, 1),
        "model": last["model"],
        "transcript": str(path),
        "breakdown": {
            "input": int(u.get("input_tokens") or 0),
            "cache_read": int(u.get("cache_read_input_tokens") or 0),
            "cache_creation": int(u.get("cache_creation_input_tokens") or 0),
            "output_last_turn": int(u.get("output_tokens") or 0),
        },
        "note": "one turn behind: the current, in-flight turn is not included",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--transcript", help="path to a session .jsonl")
    ap.add_argument("--session", help="session id to look up under the projects folder")
    ap.add_argument("--window", type=int, help="context window in tokens (default: guessed, see MEMTREE_CONTEXT_WINDOW)")
    args = ap.parse_args()
    r = compute(args.transcript, args.session, args.window)
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
        return 1 if "error" in r else 0
    if "error" in r:
        print(f"ctx_usage: {r['error']}", file=sys.stderr)
        return 1
    filled = min(20, int(r["pct"] / 5))
    b = r["breakdown"]
    print(f"context: {r['context_tokens']:,} / {r['window']:,} tokens  [{'#' * filled}{'.' * (20 - filled)}] {r['pct']}%")
    print(f"  model={r['model'] or 'unknown'}  input={b['input']:,}  cache_read={b['cache_read']:,}  "
          f"cache_creation={b['cache_creation']:,}")
    print(f"  ({r['note']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

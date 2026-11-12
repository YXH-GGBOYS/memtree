#!/usr/bin/env python3
"""UserPromptSubmit hook: remind once per step when the session's context grows past a handoff threshold.

Why: every model call re-sends the whole conversation, so a long session pays for its own length
on every call. Handing off to a fresh session at a clean point keeps each call cheap.

How the context size is read: the last assistant message in the session transcript carries the real
usage of that call; context = input_tokens + cache_read_input_tokens + cache_creation_input_tokens
(entries deduplicated by message id; sidechain and zero-usage entries skipped). The transcript is
written after each turn, so the number is one turn behind.

Thresholds ("steps"), each reminded at most once per session:
  * MEMTREE_HANDOFF_TOKENS="450000,600000,750000"  absolute override, comma separated;
  * otherwise 45% / 60% / 75% of the context window: 450K / 600K / 750K for a 1M window,
    90K / 120K / 150K for a 200K window.
The window: MEMTREE_CONTEXT_WINDOW if set; 1M if the model name says so ("[1m]") or the session is
already past 200K; 200K for models known to have it (haiku); otherwise 1M. Set MEMTREE_CONTEXT_WINDOW
=200000 if you use a 200K model, or the reminders will never fire.

Marker: ~/.claude/state/memtree/handoff/<session_id> holds the highest step already reminded.
Silent outside MemTree projects, silent below the first step, always exit 0.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memtree_common as mc  # noqa: E402

WINDOW_1M = 1_000_000
WINDOW_200K = 200_000
FRACTIONS = (0.45, 0.60, 0.75)
TAIL_BYTES = 4 * 1024 * 1024  # usage sits near the end; read the tail first


def _usage_entries(lines: List[str]) -> Dict[str, Tuple[int, str]]:
    found: Dict[str, Tuple[int, str]] = {}
    for n, line in enumerate(lines):
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
        if not isinstance(usage, dict):
            continue
        tokens = sum(int(usage.get(k) or 0) for k in
                     ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        if tokens <= 0:
            continue
        key = str(msg.get("id") or entry.get("requestId") or f"line{n}")
        found.pop(key, None)  # re-insert so dict order follows the latest occurrence
        found[key] = (tokens, str(msg.get("model") or ""))
    return found


def last_context(transcript: Path) -> Optional[Tuple[int, str]]:
    """(context tokens, model) of the last assistant call in the transcript."""
    try:
        size = transcript.stat().st_size
        with transcript.open("rb") as fh:
            if size > TAIL_BYTES:
                fh.seek(size - TAIL_BYTES)
                fh.readline()  # skip the partial first line
            lines = fh.read().decode("utf-8", errors="replace").splitlines()
            entries = _usage_entries(lines)
            if not entries and size > TAIL_BYTES:
                fh.seek(0)
                entries = _usage_entries(fh.read().decode("utf-8", errors="replace").splitlines())
    except OSError:
        return None
    if not entries:
        return None
    return list(entries.values())[-1]


def find_transcript(data: Dict[str, object]) -> Optional[Path]:
    path = data.get("transcript_path")
    if isinstance(path, str) and path and Path(path).is_file():
        return Path(path)
    sid = mc.session_id(data)
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    projects = (Path(config) if config else Path.home() / ".claude") / "projects"
    if sid and projects.is_dir():
        hits = list(projects.glob(f"*/{mc.safe_name(sid)}.jsonl"))
        if hits:
            return hits[0]
    return None


def context_window(model: str, tokens: int) -> int:
    env = os.environ.get("MEMTREE_CONTEXT_WINDOW", "").strip()
    if env.isdigit() and int(env) > 0:
        return int(env)
    m = model.lower()
    if "[1m]" in m or "-1m" in m or tokens > WINDOW_200K:
        return WINDOW_1M
    if "haiku" in m:
        return WINDOW_200K
    return WINDOW_1M


def steps(window: int) -> List[int]:
    env = os.environ.get("MEMTREE_HANDOFF_TOKENS", "").strip()
    if env:
        vals = sorted({int(x) for x in env.replace(" ", "").split(",") if x.isdigit() and int(x) > 0})
        if vals:
            return vals
    return [int(window * f) for f in FRACTIONS]


def fmt(n: int) -> str:
    return f"{n // 1000}K" if n < 1_000_000 else f"{n / 1_000_000:g}M"


def main() -> None:
    data = mc.read_hook_input()
    sid = mc.session_id(data)
    if not sid or mc.find_memory_dir(mc.start_dir(data)) is None:
        return
    transcript = find_transcript(data)
    if transcript is None:
        return
    found = last_context(transcript)
    if found is None:
        return
    tokens, model = found
    crossed = [s for s in steps(context_window(model, tokens)) if tokens >= s]
    if not crossed:
        return
    step = crossed[-1]
    try:
        done = int(mc.read_marker("handoff", sid) or 0)
    except ValueError:
        done = 0
    if step <= done:
        return
    mc.write_marker("handoff", sid, str(step))
    mc.emit(
        f"⏱️ MemTree handoff reminder: this session's context is {tokens:,} tokens (read from the "
        f"transcript, one turn behind), past the {fmt(step)} step. Finish what the current message asks. "
        "At the next clean point (a step done, tested and committed; finish any deploy, data-migration or "
        "money step first), write a handoff card in .memory/threads/<line-of-work>.md (skill: memtree-handoff) "
        "and start a fresh session from that card. A card never carries production or deploy authorization; "
        "the new session has to be given it again."
    )


if __name__ == "__main__":
    mc.run(main)

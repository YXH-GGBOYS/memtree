#!/usr/bin/env python3
"""SessionStart hook (matcher "compact"): re-ground the model right after a compaction.

A compaction summary is lossy: decisions, authorizations and file:line details can be dropped or
distorted. This hook prints, in order and within OUTPUT_BUDGET (9,000 bytes) in total:

  1. the CRITICAL_FACTS digest in full (and the same per-session marker facts_digest.py uses, so the
     next prompt does not inject it a second time);
  2. a short "the summary is lossy, trust files" reminder;
  3. the head of the most recently modified open handoff card in `.memory/threads/` (README.md,
     `_*.md` templates and cards whose first line says CLOSED are skipped).

Claude Code caps hook output at 10,000 characters; anything longer is saved to a file and the model
sees only a ~2,000-character preview, so the card is cut at a UTF-8 boundary with a visible line.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memtree_common as mc  # noqa: E402

MIN_CARD_BYTES = 600  # below this, a card excerpt is not worth printing


def reminder(mem_label: str) -> str:
    return "\n".join([
        "⚠️ MemTree: the conversation was just compacted. The summary above is lossy; it can drop or "
        "distort decisions, authorizations and file:line details. Trust files over the summary:",
        f"  • {mem_label}/CRITICAL_FACTS.md: hard invariants (re-injected above)",
        "  • the handoff card for this line of work (the latest open one is below, if any)",
        f"  • {mem_label}/<area>/PITFALLS.md before touching an area with known traps",
        "Before continuing, re-check from files: what was decided (and what was overturned), what is "
        "authorized right now (assume nothing carried over), and which environment you are working in.",
    ])


def is_closed(card: Path) -> bool:
    try:
        with card.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.strip():
                    return "CLOSED" in line.upper()
    except OSError:
        return True
    return False


def latest_open_card(threads: Path) -> Optional[Path]:
    if not threads.is_dir():
        return None
    cards = [p for p in threads.glob("*.md")
             if p.name.lower() != "readme.md" and not p.name.startswith("_") and not is_closed(p)]
    return max(cards, key=lambda p: p.stat().st_mtime) if cards else None


def main() -> None:
    data = mc.read_hook_input()
    source = data.get("source")
    if isinstance(source, str) and source and source != "compact":
        return
    base = mc.start_dir(data)
    mem = mc.find_memory_dir(base)
    if mem is None:
        return
    facts = mem / "CRITICAL_FACTS.md"
    facts_label = mc.display_path(facts, base)
    mem_label = mc.display_path(mem, base)
    tail = reminder(mem_label)

    digest = mc.extract_digest(facts)
    if digest is None:
        head = mc.missing_digest_line(facts_label)
    else:
        room = mc.OUTPUT_BUDGET - len(tail.encode("utf-8")) - MIN_CARD_BYTES - 4
        head = mc.clip(mc.render_digest(digest, facts_label), max(room, 1000), facts_label)
        sid = mc.session_id(data)
        if sid:
            mc.write_marker("digest", sid, mc.digest_hash(digest))

    out = head + "\n\n" + tail
    card = latest_open_card(mem / "threads")
    if card is not None:
        label = mc.display_path(card, base)
        top = f"\n\n===== latest open handoff card: {label} ====="
        bottom = "\n===== end of card ====="
        left = mc.OUTPUT_BUDGET - len((out + top + bottom).encode("utf-8")) - 2
        if left >= MIN_CARD_BYTES:
            body = card.read_text(encoding="utf-8", errors="replace").strip()
            out += top + "\n" + mc.clip(body, left, label) + bottom
    elif (mem / "threads").is_dir():
        out += f"\n\n(no open handoff card in {mem_label}/threads/)"
    mc.emit(mc.clip(out, mc.OUTPUT_BUDGET - 1))


if __name__ == "__main__":
    mc.run(main)

#!/usr/bin/env python3
"""UserPromptSubmit hook: put the project's hard invariants in front of the model, once per session.

Source of truth: the `• ` lines between <!-- DIGEST-START --> and <!-- DIGEST-END --> in
`.memory/CRITICAL_FACTS.md`. Nothing is copied anywhere else.

  * First prompt of a session: inject the digest in full and remember its hash in
    ~/.claude/state/memtree/digest/<session_id>  (override the root with MEMTREE_STATE_DIR).
  * Later prompts, digest unchanged: one pointer line instead of the full text. Every model call
    re-sends the whole conversation, so the full digest is already in context.
  * Digest edited mid-session: inject the new version in full.
  * After compaction the conversation no longer holds it; post_compact.py re-injects it and writes
    the same marker.
  * No session id: inject in full every time (nothing to dedupe against).
  * Markers or bullets missing: print one red line so the gap is visible, never silently skip.
  * Not a MemTree project: print nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memtree_common as mc  # noqa: E402


def main() -> None:
    data = mc.read_hook_input()
    base = mc.start_dir(data)
    mem = mc.find_memory_dir(base)
    if mem is None:
        return
    facts = mem / "CRITICAL_FACTS.md"
    label = mc.display_path(facts, base)
    digest = mc.extract_digest(facts)
    if digest is None:
        mc.emit(mc.missing_digest_line(label))
        return
    sid = mc.session_id(data)
    new_hash = mc.digest_hash(digest)
    old_hash = mc.read_marker("digest", sid) if sid else None
    if old_hash == new_hash:
        mc.emit(f"\U0001F512 MemTree: hard invariants from {label} were injected earlier in this session and are "
                "unchanged (they are re-injected after compaction). If anything conflicts with them, the file wins.")
        return
    text = mc.render_digest(digest, label, changed=old_hash is not None)
    mc.emit(mc.clip(text, mc.OUTPUT_BUDGET, label))
    if sid:
        mc.write_marker("digest", sid, new_hash)


if __name__ == "__main__":
    mc.run(main)

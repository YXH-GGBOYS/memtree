---
name: memtree-closeout
description: Close a finished line of work in MemTree - record an event if the work has diagnostic value, update the PITFALLS lifecycle, mark the handoff card CLOSED, and push every correction back into the file it belongs to. TRIGGER when a bug fix or feature is done and verified, when the user says wrap up / close out / record this / we are done with this, or before archiving a thread card. SKIP for pausing unfinished work to continue in a new session (use memtree-handoff), and for trivial changes such as typos or formatting.
---

# memtree-closeout

A fix that is only described in chat is not a fix: the next session will not see the chat. Close-out
puts what was learned into the one file that is the authority for it.

## 1. Event, if it has diagnostic value

Write one when the next person debugging something similar would want it: a real root cause, a
misleading symptom, a cross-area effect. Skip typos, styling and config value tweaks.

- File: `.memory/events/YYYY-MM/EVT-YYYYMMDD-NNN.md` from `.memory/events/TEMPLATE.md`
  (or `${CLAUDE_PLUGIN_ROOT}/templates/EVENT.md`).
- Add one line at the top of `.memory/events/INDEX.md`:
  `- EVT-YYYYMMDD-NNN | areas | symptom -> root cause | events/YYYY-MM/EVT-YYYYMMDD-NNN.md`
- The "Fix" section names how it was verified (test, command, real run). If it was not verified,
  say so.

## 2. PITFALLS lifecycle

In `.memory/<area>/PITFALLS.md`:

- New trap: add an entry (`status: ACTIVE`, `type`, `source event`, `last_seen`, `trap`, `rule`,
  `how to verify`).
- Known trap seen again: update `last_seen` and link the new event.
- Root cause fixed and verified: set `status: RESOLVED`, keep the entry, add the fixing commit.

## 3. Hard invariants

If the work revealed a fact that costs money, data or an incident when gotten wrong, add it to the
DIGEST in `.memory/CRITICAL_FACTS.md` (one line, keep the digest under ~3,000 characters). Ask the
user before adding or changing a digest line.

## 4. Propagate corrections to their source

For every earlier claim this work proved wrong (in a card, plan, PITFALLS entry, doc or event):
edit that file. Mark the old claim as superseded and point to the right one, e.g.
`> Superseded YYYY-MM-DD: wrong, see events/2026-11/EVT-20261112-002.md`.
If two files disagree, fix the one that is not the authority.

Negative claims ("X doesn't exist") that you are writing down need the evidence next to them: the
`verify_absence.py` command and its result.

## 5. Close the card

Make the first line of `.memory/threads/<line-of-work>.md`:
`CLOSED YYYY-MM-DD -> events/YYYY-MM/EVT-YYYYMMDD-NNN.md` (or `-> no event`).
Closed cards are no longer shown after compaction. Move old closed cards to `.memory/threads/archive/`
when the folder gets crowded.

## 6. Report

Tell the user, kept apart: what is done and verified, what is done but not verified, what is not done.

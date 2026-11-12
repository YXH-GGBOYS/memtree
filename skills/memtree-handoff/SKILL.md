---
name: memtree-handoff
description: Write a MemTree handoff card (.memory/threads/<line-of-work>.md, at most 60 lines, 8 fixed sections) and continue the work in a fresh session, or pick up work from a card in a new session. TRIGGER when the MemTree handoff reminder fires, when the context is large and a step just finished, when the user says hand off / switch session / start fresh / continue in a new session, or when a new session is started from a card. SKIP for ending a line of work that is finished (use memtree-closeout), and in the middle of a deploy, migration or money step (finish that step first).
---

# memtree-handoff

Why: every model call re-sends the whole conversation, so a long session pays for its own length on
every call. A fresh session that starts from a short card is cheaper per call and has less stale
context to trip over.

## When

- After the handoff reminder (default: context past 45% of the window), at the next clean point:
  a step is done, tested and committed. Finish any deploy, data-migration or money step first.
- Never in the middle of a step that leaves things half-applied.

## Write the card

File: `.memory/threads/<line-of-work>.md` (short kebab-case name, e.g. `invoice-retry-fix.md`).
One file per line of work; update the existing card if there is one. At most 60 lines.
Template: `${CLAUDE_PLUGIN_ROOT}/templates/thread_card.md`, also copied to `.memory/threads/_TEMPLATE.md`.

The eight sections, in this order:

1. Goal and acceptance: what done means, in checkable terms.
2. Current step: where the work stands right now.
3. Decisions, each with its source: who decided and when, file:line, event, or commit.
4. Authorization: always "None". A card never carries production, deploy or data-change
   authorization; the next session must be given it again by the user.
5. Files and commits touched: repo, branch, commit hashes.
6. Not done or not verified: keep these apart from what is done. Never describe an unverified
   change as working.
7. Next step: numbered; the first one concrete (a command or a file to open).
8. Read first: at most five pointers, each with line numbers or a section (`billing/PITFALLS.md` P003,
   `docs/plan.md:40-75`).

Pointer rule: conclusions that already live in another file go in as pointers, not restated in your
own words (every restatement is a lossy copy). Only facts that this session produced go in as text.

Commit the card with the work if the user commits.

## Start the fresh session

Give the user the card path and a one-line prompt to paste into a new session, for example:
`Continue the work in .memory/threads/invoice-retry-fix.md: read the card and its pointers, verify the state with git, then do the next step.`
If your environment offers a way to open a new session with that prompt, use it; otherwise the user
opens one. After that, stop working on this line in the old session.

## Picking up from a card (new session)

1. Read only the card and the files in its "Read first" list. Do not read whole plans or logs.
2. Check the card against reality before acting: `git log --oneline -10`, `git status`, and the
   files or commits the card names. If they disagree, trust git and the files, and fix the card.
3. Authorization starts at none, whatever the old session had.
4. Do the first next step.

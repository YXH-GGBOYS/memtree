# Design principles

[中文](design-principles_cn.md)

## 1. Context is the cost

Every call re-sends the whole conversation, so long sessions are where tokens go
([context-economics.md](context-economics.md)). Keep sessions short, inject things once, return
small results. Measure before optimizing: `token_report.py` and `ctx_usage.py` read real usage from
your transcripts. Never state a context percentage you did not just measure; guesses drift high when
you have been busy.

## 2. One authority per fact

Each kind of fact has exactly one authoritative file:

| Fact | Authority |
|---|---|
| hard invariants | `.memory/CRITICAL_FACTS.md` (the DIGEST block is injected) |
| known traps of an area | `.memory/<area>/PITFALLS.md` |
| incidents | `.memory/events/` and its `INDEX.md` |
| state of a line of work | `.memory/threads/<name>.md` |

Every other place holds a pointer. When two places disagree, that is a bug; fix the copy toward the
authority. Every restatement in your own words is a lossy copy, and copies of copies drift. That is
also why the hooks render the digest from CRITICAL_FACTS.md instead of keeping their own text.

## 3. Hand-written knowledge over generated summaries

v1 generated a summary for every source file. They went stale and were not read (see
[legacy/README.md](../legacy/README.md)). The source code is always current; what it cannot tell an
agent is why things are the way they are, what broke before, and which rules must never be broken.
Those are the things MemTree keeps, written by people (or by the agent at close-out) and reviewed
like code.

## 4. Inject, never reroute

MemTree hooks add text to the context and do nothing else. They never block, rewrite or reroute a tool
call, add no PreToolUse handlers, add no tools, and keep no copy of tool output. A tool that routes
commands through its own executor also routes them around the PreToolUse safety hooks people rely on,
and may persist what those commands returned. MemTree avoids that whole class of problem by not
touching tool calls at all.

Two corollaries:

- Silent when not wanted: outside a MemTree project (no `.memory/` with `CRITICAL_FACTS.md` or
  `memtree.json`) every hook prints nothing and exits 0, so a user-level install is safe.
- Loud when broken: if CRITICAL_FACTS.md is there but its DIGEST markers are missing, the hook prints a
  red line saying the invariants were not injected. A safety fact that silently disappears is worse
  than a stale one.

## 5. Verify what the model actually receives

For hooks, injections and gates, the evidence is the bytes the model receives and the real exit code,
measured by running the hook with the same stdin Claude Code sends. A script's own "OK" is not
evidence. Channels have limits: hook output above 10,000 characters is replaced by a file path and a
~2,000-character preview, so MemTree budgets every hook to 9,000 bytes and tests that budget with
oversized input.

## 6. Negative assertions need evidence

"X doesn't exist", "we can't do X", "this has to be built" are the claims that travel furthest
unchallenged, and when wrong they always point toward extra work. Before writing one, run
`verify_absence.py`: two independent search methods, the exact commands, hit counts. Zero hits still
means only "not found". Also name the capability state:

| State | Meaning |
|---|---|
| doesn't exist | nothing to find; really has to be built |
| built but not wired | code exists, nothing calls it |
| wired but switched off | called, behind a flag or config that is off |
| live | it runs; claiming this needs runtime evidence (rows, logs, a real run), reading code cannot show it |

And the trap: running but always "unknown". It has rows, logs and counters, so it looks live, but every
result is "can't tell". Check that the output is usable, not just that it exists.

## 7. Ask who reads it

Before changing a shared field, status value or constant, list its consumers (`who_reads.py`). The
group to read line by line is the conditions: `if`, `where`, `filter`, `==`, `in`. Changing what a field
holds can make one of them always true or always false, with no error anywhere.

## 8. A correction only said in chat is not a correction

The next session does not see this chat. When something written down turns out wrong, fix it in the
file it lives in, mark the old claim as superseded, and point to the right one. Close-out
(`memtree-closeout`) is where this happens routinely.

## 9. Cards carry state, never authorization

A handoff card tells the next session what was decided, what is done, what is not verified, and what to
do next. It never says "deploy is approved". Authorization for production, deploys or data changes is
given again, by a person, in the session that acts on it.

## 10. Stay small

Python 3.9 standard library only. No daemon, no database, no network calls, no background indexing.
Everything is a file you can read, diff and commit.

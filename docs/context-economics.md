# Context economics

[中文](context-economics_cn.md)

## The cost model

A Claude Code session is a sequence of model calls. Call *i* sends the whole conversation so far,
`c_i` tokens (system prompt, tool definitions, CLAUDE.md, every message, every tool result still in
context). What a session costs, in money and in rate limits, is roughly `Σ c_i`.

Context grows as work happens. If a session starts at `b` tokens and each call adds about `a`, then
after `N` calls `Σ c_i ≈ N·b + a·N²/2`. The second term is the one that hurts: twice as long a
session pays about four times as much for its growth. Prompt caching makes re-sent tokens cheaper,
not free, and they still fill the context window.

Two consequences:

- Anything that enters the context early is paid for again on every later call. A 20 KB tool result
  read at call 50 of a 400-call session is sent about 350 more times.
- Shortening sessions saves more than trimming individual reads, because it removes the high-context
  calls where most of the tokens are.

## What we measured

Source: one solo developer's local Claude Code transcripts. Every main-session call made in a 21-day
window (2026-10-22 through 2026-11-11, US Eastern, by each call's own timestamp): 147 sessions,
37,529 calls, 17 projects. Subagent and workflow transcripts are counted separately. Context per call
is the real usage recorded in the transcript: `input_tokens + cache_read_input_tokens +
cache_creation_input_tokens`, deduplicated by message id across all transcripts. Only ratios and
counts are published.

| Question | Result |
|---|---|
| How much of the re-sent context came from re-reading the same file in the same session? | about 0.1%, nearly all of it images read again; re-reads that returned identical text: about 0 |
| How much of the re-sent context was in calls with context above 300K? | about 76% |
| ... above 500K? | about 43% |
| How large is a brand-new session before any work? | median about 96K tokens, most between 83K and 121K (tools, system prompt, CLAUDE.md) |
| One common keyword over the knowledge files: grep vs card lookup | about 500 KB vs about 4 KB of output |

The first row surprised us: "don't read the same file twice" is close to irrelevant. The second and
third rows say where the tokens are: in the long tail of big-context calls.

The fixed overhead in row four sets a floor. Handing off too early wastes it, and a fresh session that
reads a card plus a few pointers realistically starts around 150K in that setup.

### Two ways to miscount your own transcripts

The first run of these numbers made two counting mistakes. `token_report.py` now avoids both; watch
for them if you measure some other way.

- Choosing sessions by file modification time mixes in old sessions. Claude Code can append
  metadata lines to a transcript long after its last call, so "transcripts modified in the last three
  weeks" included many sessions that had ended weeks before. About 40% of the main-session calls in
  that first "three weeks" were older than the window, the oldest by about two months. Filter on each
  call's own `timestamp` instead.
- Forked and copied sessions count the same calls twice. A fork starts a new transcript that holds
  the parent's history under the same message ids. In the 21-day window, 7.6% of main-session calls
  were such copies. Deduplicate by message id across all transcripts, not just inside one.

With both fixed the totals fell by almost half, while the ratios barely moved: calls above 300K went
from about 77% of the context to 76%, above 500K from 46% to 43%, and the 450K / 150K handoff saving
below from 31% to 30%.

## The handoff simulation

`scripts/token_report.py` replays each recorded session as if it had handed off to a fresh session
whenever its context passed a threshold `T`, with the fresh session starting at `R`:

```
offset = 0
for each call with real context x:
    y = x - offset                 # simulated context of this call
    if y > T:                      # hand off: the new session starts at R
        offset = x - R; y = R
    floor = min(x, R)
    if y < floor:                  # the real session shrank (compaction): never below a fresh start
        offset = x - floor; y = floor
    simulated_total += y
saving = 1 - simulated_total / real_total
```

After a handoff the simulated session grows exactly as the real one did. With `T = 450K` and
`R ≈ 150K`, the saving on the measured data was about 30%. An earlier version of this simulation
reported 35-40% on the same data: after the original session compacted on its own, it kept the
simulated session flat at `R` instead of letting it grow again, which over-credits the saving. The
`floor` step above is the fix.

What the simulation does not count, so read the number as an upper bound:

- the card itself and the files the new session reads from its pointers (partly inside `R`);
- information lost in the handoff, and any rework it causes;
- that people may work differently when sessions are short.

Run it on your own transcripts:

```bash
python3 scripts/token_report.py --since 2026-10-01
python3 scripts/token_report.py --since 2026-10-01 --until 2026-10-22
python3 scripts/token_report.py --project my-app --simulate 300000:120000 --out report.md
```

`--since` and `--until` are local dates; a call counts if its own timestamp falls between the two
midnights (`--until` excluded). It reads `~/.claude/projects/**/*.jsonl` locally and sends nothing
anywhere. Per-source sizes in the "carry" table are estimates from character counts; the per-call
context numbers are real.

## What MemTree does with this

| Finding | MemTree response |
|---|---|
| Big-context calls dominate | `ctx_handoff_reminder.py` reminds at 45% / 60% / 75% of the window; `memtree-handoff` makes the switch cheap |
| Anything injected stays for the rest of the session | `facts_digest.py` injects the digest once per session, then a one-line pointer; `post_compact.py` re-injects it only after compaction |
| Grep over knowledge returns hundreds of KB | `memq.py` returns one card per entry; then Read with offset/limit |
| Hook output above 10,000 characters becomes a file plus a ~2,000-character preview | every hook stays under 9,000 bytes and truncates visibly |

The digest arithmetic, for a sense of scale: a 1,000-token digest injected on each of 100 prompts in a
session puts 100 copies in the context, and each copy is re-sent on every call after it. Injected once,
there is one copy.

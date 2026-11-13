<div align="center">

# MemTree

Keep Claude Code sessions short and project facts in one place.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-blueviolet)](https://code.claude.com/docs/en/plugins)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)

[English](README.md) | [中文](README_CN.md)

</div>

MemTree is a small kit for [Claude Code](https://code.claude.com): three hooks that only add text to
the context, four skills, six stdlib-only Python scripts, and a convention for where each kind of
project fact lives. Install it as a Claude Code plugin or by copying files. It ships a workflow and
the reasoning behind it, not anyone's project data.

## Why: context is the bill

Every model call re-sends the whole conversation. So the cost of a session grows with how long it
is times how many calls it makes, not with whether you happened to read a file twice.

We measured this on one solo developer's Claude Code transcripts: every main-session call in a
21-day window, 147 sessions and 37,529 calls across 17 projects. Only ratios and counts are given
here; your numbers will differ, and `scripts/token_report.py` computes them for you from your own
local transcripts.

| Observation | Kind |
|---|---|
| Re-reading the same file within one session: about 0.1% of re-sent context, nearly all of it images; re-reads that returned identical text: about 0 | measured |
| About 76% of re-sent context tokens were in calls whose context was above 300K tokens; about 43% above 500K | measured |
| A fresh session already starts at a median of about 96K tokens of fixed overhead (tools, system prompt, CLAUDE.md) | measured |
| Handing off to a fresh session at 450K (restarting at about 150K) would have cut re-sent context by about 30% | simulated, ignores what a handoff loses |
| One common keyword grepped over the knowledge files returned about 500 KB; the same lookup through cards returned about 4 KB | measured once |

What follows from that:

1. Long sessions are where the money goes. Hand off to a fresh session at a clean point, from a
   short card, before the context gets large. MemTree reminds you when it does.
2. Whatever enters the context stays there for every later call. Inject the hard rules once per
   session, not on every prompt, and look knowledge up as small cards instead of grepping big files.
3. A fact kept in two places drifts. Keep each kind of fact in one authoritative file and point to it.

More detail and the simulation method: [docs/context-economics.md](docs/context-economics.md).

## What you get

| Piece | What it does |
|---|---|
| `hooks/facts_digest.py` (UserPromptSubmit) | Injects the hard-invariant digest from `.memory/CRITICAL_FACTS.md` once per session; afterwards a one-line pointer; re-injects in full if the digest changes |
| `hooks/post_compact.py` (SessionStart, `compact`) | After a compaction: the digest again, a "the summary is lossy, trust files" reminder, and the head of the latest open handoff card, all under 9,000 bytes |
| `hooks/ctx_handoff_reminder.py` (UserPromptSubmit) | Reads the real context size from the transcript and reminds you once per step (45% / 60% / 75% of the window) to hand off |
| skill `memtree-init` | Sets up `.memory/` in a project through a short Q&A; never overwrites |
| skill `memtree-handoff` | When and how to write a handoff card and continue in a fresh session |
| skill `memtree-closeout` | Closing a line of work: event, PITFALLS lifecycle, close the card, fix corrections at their source |
| skill `memtree-lookup` | Querying knowledge cheaply, checking negative claims, finding who reads a field |
| `scripts/memq.py` | Card lookup across CRITICAL_FACTS, PITFALLS, the events index and handoff cards |
| `scripts/ctx_usage.py` | Current session context size, read from the transcript |
| `scripts/token_report.py` | Local report of where your context tokens went, plus the handoff simulation |
| `scripts/verify_absence.py` | Evidence for "X doesn't exist" claims: two search methods, exact commands, hit counts |
| `scripts/who_reads.py` | Every reader of a field or status, with the conditions that test it listed separately |
| `templates/` | CRITICAL_FACTS, PITFALLS, event, events index, handoff card, CLAUDE.md snippet |

## Install

### As a Claude Code plugin

```
/plugin marketplace add YXH-GGBOYS/memtree
/plugin install memtree@memtree
```

The plugin registers the three hooks and the four skills (invoked as `/memtree:memtree-init` and so
on). The hooks print nothing in projects that have no MemTree `.memory/` folder, so installing it
for your user account is safe.

### Manual install (no plugin system)

```bash
git clone https://github.com/YXH-GGBOYS/memtree.git ~/memtree
cd ~/memtree
./install.sh            # copies skills to ~/.claude/skills/, hooks + scripts to ~/.claude/memtree/,
                        # then prints the hook JSON to merge into ~/.claude/settings.json
./install.sh --apply    # or: let it merge the hooks for you, after backing up settings.json
```

Requires Python 3.9+ and nothing else. On Windows, if `python3` is not on PATH, change the hook
commands to `python` or `py -3`.

To uninstall: `/plugin uninstall memtree@memtree`, or for a manual install delete
`~/.claude/skills/memtree-*` and `~/.claude/memtree/` and remove the three hook entries from
`settings.json`.

### Set up a project

In Claude Code, inside your project, run the `memtree-init` skill (`/memtree:memtree-init` with the
plugin, `/memtree-init` after a manual install). It asks a few questions (your areas or services,
the facts that cost money or data when gotten wrong) and creates:

```
.memory/
├── CRITICAL_FACTS.md      hard invariants; the DIGEST block is what the hooks inject
├── memtree.json           {"extra_sources": []}  (optional extra files for memq)
├── billing/PITFALLS.md    one per area you named
├── auth/PITFALLS.md
├── events/INDEX.md        one line per incident; files in events/YYYY-MM/
└── threads/               handoff cards, one per line of work
```

Without Claude Code: `python3 scripts/memtree_init.py --areas billing,auth,api --claude-md`.
Commit `.memory/` with your code; it is project knowledge. A small filled-in example lives in
[examples/saas-app/](examples/saas-app/).

## How it works

### One authority per fact

| Kind of fact | Its only authoritative home |
|---|---|
| Hard invariants: money units, data ownership, which environment is which, what needs a human go-ahead | `.memory/CRITICAL_FACTS.md` (the `• ` lines between `<!-- DIGEST-START -->` and `<!-- DIGEST-END -->` are injected) |
| Known traps of one area, with a lifecycle (status ACTIVE / RESOLVED, type, source event, last_seen, how to verify) | `.memory/<area>/PITFALLS.md` |
| Incidents: symptom, root cause, fix, how it was verified | `.memory/events/YYYY-MM/EVT-*.md` plus one line in `.memory/events/INDEX.md` |
| Where a line of work stands | `.memory/threads/<name>.md` handoff card |

Everywhere else holds a pointer (`see billing/PITFALLS.md P003`), not a restatement. If two places
disagree, that is a bug: fix the one that is not the authority. A correction that is only said in
chat is not a correction, because the next session never sees the chat.

### Handoff cards

A card is at most 60 lines with eight fixed sections: goal and acceptance; current step; decisions
with their sources; authorization (always "none"); files and commits touched; not done or not
verified; next step (the first one concrete); read first (at most five pointers with line numbers).
The new session reads only the card and its pointers, checks the state against git, and continues.
A card never carries production or deploy authorization; the new session has to be given it again.
See [skills/memtree-handoff/SKILL.md](skills/memtree-handoff/SKILL.md).

### The hooks only inject

MemTree hooks never block, rewrite or reroute a tool call. They add no PreToolUse handlers, add no
tools of their own, and store no tool output. They always exit 0 and print nothing when the
project has no MemTree `.memory/` (a folder with `CRITICAL_FACTS.md` or `memtree.json`).

This is deliberate. Some context-saving tools add their own shell-execution tools or reroute
commands through them. Any PreToolUse safety hooks you configured for Bash then never see those
commands, and the rerouted output (database query results included) can end up stored on disk in
plaintext. If you use such a tool, check that your guard hooks still fire for the commands it runs.

Two limits shaped the hook design:

- Claude Code caps hook output at 10,000 characters. Above that it saves the output to a file and
  shows the model only a preview of about 2,000 characters, and nothing asks the model to open the
  file. We hit this more than once before adding a budget, so every MemTree hook keeps its output
  under 9,000 bytes and cuts at a UTF-8 boundary with a visible `…truncated` line.
- Check what the model actually receives. For a hook, that means the bytes it prints and its real
  exit code, run with the same stdin Claude Code sends; what a script says about itself is not
  evidence. The `memtree-init` skill ends with exactly that check.

Settings (environment variables, all optional):

| Variable | Effect |
|---|---|
| `MEMTREE_CONTEXT_WINDOW` | Context window in tokens. The reminder guesses 1M unless the model name or the session size says otherwise; set `200000` if you use a 200K model |
| `MEMTREE_HANDOFF_TOKENS` | Absolute reminder steps, e.g. `300000,450000` (overrides the 45/60/75% steps) |
| `MEMTREE_STATE_DIR` | Where per-session markers go (default `~/.claude/state/memtree/`) |

### Negative claims and shared fields

Two habits that the scripts make cheap:

- Before writing "X doesn't exist / can't be done / must be built", run `verify_absence.py X` and
  keep its command and counts next to the claim. Such claims get copied forward unchallenged, and
  when they are wrong the error always points toward extra work. Also say which state a capability
  is in: doesn't exist, built but not wired, wired but switched off, or live. "Live" needs runtime
  evidence, and watch for the trap of a component that runs and logs but always answers "unknown".
- Before changing a shared field or status value, run `who_reads.py <symbol>`. Its "conditions" group
  (if / where / filter / == / in) is the one people forget: change what a field holds and one of
  those can become always true or always false without any error.

## Measured, simulated, untested

- Measured: the ratios in the first table, from one developer's local transcripts over 21 days
  (each call counted once, by its own timestamp). They describe that workload, not yours; run
  `token_report.py` for your own.
- Simulated: the ~30% saving from handing off at 450K. The simulation replays each session's real
  context sizes as if it had restarted at about 150K; it does not count the card, re-reading files in
  the new session, or information lost in the handoff. Read it as an upper bound. An earlier version
  of the simulation reported 35-40% on the same data, because it kept crediting savings after the
  original session had already compacted on its own; the shipped version does not.
- Not measured: how much a handoff loses, and how often the digest prevents a mistake.
- Tested: the hooks and scripts have unit tests (`python3 -m pytest tests` or
  `python3 -m unittest discover -s tests`) and were smoke-tested by feeding them sample stdin.
- Not yet tested: installation through `/plugin` end to end, Windows, and the window-size guess for
  every model name.

## Related projects

Other tools people use alongside or instead of MemTree, by category:

- Session analytics: ccusage reports token usage and cost from Claude Code's local logs.
  `token_report.py` asks a different question (which sessions and content re-send the most context).
- Memory plugins: claude-mem records what happens in sessions and feeds a compressed version into
  later sessions automatically. MemTree keeps hand-curated facts in files you review and commit.
- Output sandboxing: context-mode keeps large tool output out of the context window by running
  commands through its own tools. With any tool of this kind, check that your PreToolUse safety
  hooks still see the commands it runs (see "The hooks only inject" above).
- Code graphs: graphify builds a queryable graph of a codebase. MemTree does not index code; the
  agent reads the source, which is always current.

## Coming from v1

v1 generated an LLM-written summary for every source file and kept them fresh with an edit hook. In
real use about 55% of those summaries sat untouched for six months or more, they were almost never
read over three weeks, and the hook queued updates on every edit anyway. That pipeline now lives in
[legacy/](legacy/README.md) with instructions if you still want it. `PITFALLS.md` and the event log
carry over unchanged in spirit; v2 adds the lifecycle fields and the digest. See
[CHANGELOG.md](CHANGELOG.md).

## Docs

- [Getting started](docs/getting-started.md)
- [Context economics](docs/context-economics.md)
- [Design principles](docs/design-principles.md)
- [CLAUDE.md integration](docs/claude-md-integration.md)

## License

MIT. See [LICENSE](LICENSE).

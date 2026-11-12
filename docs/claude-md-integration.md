# CLAUDE.md integration

[中文](claude-md-integration_cn.md)

The hooks put the hard invariants in front of the model. CLAUDE.md is where you tell it how to use the
rest: where each kind of fact lives, when to hand off, how to look things up.

## Add the snippet

`memtree-init` offers to do this, or run:

```bash
python3 ~/memtree/scripts/memtree_init.py --claude-md
```

It appends [templates/CLAUDE.md.snippet](../templates/CLAUDE.md.snippet) (34 lines) between
`<!-- memtree:begin -->` and `<!-- memtree:end -->`, and does nothing if the marker is already there.
The snippet covers: the authority table, reading PITFALLS before changing an area, memq before Read,
handoff at the reminder, `verify_absence.py` before negative claims (with the capability states),
`who_reads.py` before changing shared fields, verifying what the model actually receives, fixing
corrections at their source, and close-out.

## Keep CLAUDE.md small

CLAUDE.md is part of every session's fixed overhead, re-sent on every call. In the measured setup a
brand-new session already started at about 90K-100K tokens (tools, system prompt and CLAUDE.md
together); every line you add to CLAUDE.md raises that floor.

- Do not copy CRITICAL_FACTS into CLAUDE.md. The digest is injected anyway; a copy in CLAUDE.md is
  paid twice and will drift.
- Rules belong in CLAUDE.md; their history (who decided, when, the incident behind them) belongs in
  an event or a provenance file that CLAUDE.md points to.
- If a section is only needed for one kind of task, move it into a skill, which is loaded only when
  that task comes up.

## Why the snippet and not more

The snippet is guidance, not enforcement. MemTree never adds PreToolUse handlers, so nothing blocks a
tool call when a rule is ignored. If you need hard gates (for deploys, database writes), write them as
your own PreToolUse hooks; MemTree will not reroute commands around them.

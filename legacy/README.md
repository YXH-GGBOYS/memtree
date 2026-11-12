# legacy/ — the v1 per-file summary pipeline

MemTree v1 (April 2026) generated one LLM-written summary file per source file
(`.memory/<service>/<path>.md` with TL;DR, Quick Ref, dependency graph), kept fresh by an
edit hook that queued incremental updates.

## Why it was demoted

In real use on one multi-service project, the summaries went stale and were not read:

- about 55% of the per-file summaries had not been touched for 6+ months;
- over a 3-week window, reads of those files by the agent were close to zero;
- meanwhile the post-edit hook queued an update on every edit, so the pipeline kept costing
  tokens to maintain files nobody opened.

The agent read source code directly, which is always current. The parts of v1 that people
did keep using were the hand-written ones: `PITFALLS.md`, the event log, and the hard
invariants. v2 builds on those. See the top-level `README.md`.

A summary that can be wrong without anyone noticing is worse than no summary: if you use
this pipeline, treat every generated file as a hint to locate code, never as evidence.

## What is in here

| Path | What it was |
|---|---|
| `skills/memtree_init`, `memtree_bootstrap`, `memtree_rebuild` | v1 skills: config Q&A, full build, partial rebuild |
| `scripts/` | scan, skeleton/index generation, incremental update, edit hook, worker-output parser, quality eval, validators, `generate-health.py`, git pre-commit staleness check, shared `memtree_common.py` |
| `prompts/` | coordinator / worker prompts used by the build |
| `templates/` | v1 per-file, PITFALLS and event templates |
| `docs/` | v1 guides (getting started, design principles, depth enrichment, CLAUDE.md integration) |
| `examples/sample-output/` | what a v1 build produced for a sample SaaS app |
| `memtree.config.example.yaml`, `requirements.txt` | v1 config (needs PyYAML) |

## Still want to use it

The files keep their v1 relative layout, so treat `legacy/` as the v1 repo root:

```bash
cd memtree/legacy
pip install -r requirements.txt          # PyYAML
mkdir -p ~/.claude/skills
cp -r skills/memtree_* ~/.claude/skills/
# then follow docs/getting-started.md (paths like scripts/... and prompts/... are relative to legacy/)
```

The v1 skills are named `memtree_init` etc. (underscore). The v2 skills are `memtree-init` etc.
(hyphen), so both can be installed side by side. The v1 edit hook (`scripts/hook-post-edit.sh`)
is a PostToolUse hook that queues work on every edit; v2 deliberately ships nothing like it.

Nothing in `legacy/` is maintained or tested in v2.

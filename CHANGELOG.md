# Changelog

## 2.0.0 (2026-11-12)

v2 changes what MemTree is for. v1 generated an LLM-written summary for every source file; v2 keeps
hand-written project facts in one place, keeps sessions short, and adds hooks that only inject text.

### Added
- Claude Code plugin packaging: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
  (`/plugin marketplace add YXH-GGBOYS/memtree`, then `/plugin install memtree@memtree`), and
  `hooks/hooks.json`.
- Hooks (inject only; never block, rewrite or reroute tool calls; silent outside MemTree projects):
  - `facts_digest.py` (UserPromptSubmit): CRITICAL_FACTS digest once per session, a pointer line
    afterwards, re-injected when the digest changes; a red line when the markers are missing.
  - `post_compact.py` (SessionStart, `compact`): digest, "summary is lossy" reminder and the latest
    open handoff card, under 9,000 bytes, truncated at a UTF-8 boundary.
  - `ctx_handoff_reminder.py` (UserPromptSubmit): one reminder per context step (45 / 60 / 75% of the
    window; `MEMTREE_HANDOFF_TOKENS` and `MEMTREE_CONTEXT_WINDOW` override).
- Skills: `memtree-init`, `memtree-handoff`, `memtree-closeout`, `memtree-lookup`.
- Scripts (Python 3.9+ standard library): `memq.py`, `ctx_usage.py`, `token_report.py`,
  `verify_absence.py`, `who_reads.py`, `memtree_init.py`.
- Templates: CRITICAL_FACTS (with DIGEST markers), PITFALLS (lifecycle fields), event, events index,
  handoff card, CLAUDE.md snippet, `memtree.json`.
- `install.sh` for manual installs (`--apply` merges hooks into settings.json after a backup).
- Docs: context economics, rewritten design principles, getting started, CLAUDE.md integration
  (English and Chinese). Example `.memory/` under `examples/saas-app/`.
- Tests: `tests/` (unittest, also runs under pytest).

### Changed
- `memtree.config.yaml` is replaced by an optional `.memory/memtree.json` with a single key,
  `extra_sources`.
- README rewritten around context economics and authority layers.

### Moved to `legacy/`
- The per-file summary pipeline: skills `memtree_init`, `memtree_bootstrap`, `memtree_rebuild`;
  scripts for scanning, skeletons, indexes, incremental updates, the post-edit hook, worker-output
  parsing, quality eval, validation, HEALTH.md generation and the pre-commit staleness check; build
  prompts; v1 templates, docs and example output; `memtree.config.example.yaml`; `requirements.txt`.
  See `legacy/README.md` for why and how to still use it.

## 1.2 (2026-04)

- Event layer (`events/` + `INDEX.md`), HEALTH.md generation, PITFALL lifecycle, quality eval.
- Audit fixes and Chinese translations of the guides.

## 1.0 (2026-04)

- Per-file code memory: coordinator / worker build, incremental updates via hooks, PITFALLS per service.

# Example: `.memory/` for a small SaaS app

[`saas-app/.memory/`](saas-app/.memory/) is what a project looks like after `memtree-init` and a
few weeks of use. The app is invented: a SaaS product with `billing`, `auth` and `api` services.

| File | Shows |
|---|---|
| `CRITICAL_FACTS.md` | a DIGEST of five one-line invariants, details below it |
| `billing/PITFALLS.md`, `auth/PITFALLS.md` | entries with the lifecycle fields; one RESOLVED, two ACTIVE |
| `events/INDEX.md` and `events/2026-11/EVT-20261103-001.md` | one line per event, one file per event |
| `threads/export-rounding.md` | an open handoff card with all eight sections |
| `memtree.json` | an `extra_sources` entry for memq |

Try the tools on it:

```bash
cd examples/saas-app
python3 ../../scripts/memq.py webhook retry
printf '{"session_id":"demo","cwd":"%s"}' "$PWD" | MEMTREE_STATE_DIR="$(mktemp -d)" python3 ../../hooks/facts_digest.py
printf '{"session_id":"demo","cwd":"%s","source":"compact"}' "$PWD" | MEMTREE_STATE_DIR="$(mktemp -d)" python3 ../../hooks/post_compact.py | wc -c
```

The v1 example (per-file summaries) is in [legacy/examples/](../legacy/examples/).

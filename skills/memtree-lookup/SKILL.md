---
name: memtree-lookup
description: Query MemTree project knowledge cheaply - card lookup with memq across CRITICAL_FACTS, PITFALLS, the events index and handoff cards, then Read with offset/limit only the part needed; also how to check a negative claim (verify_absence) and who consumes a shared field (who_reads), and how to see the current context size (ctx_usage). TRIGGER before reading any .memory file, when looking for a past incident, trap or decision, before claiming something does not exist, and before changing a shared field, status value or constant. SKIP when you already know the exact file and line to read.
---

# memtree-lookup

Every token you pull into context is paid again on every later call of the session. A broad grep
over knowledge files can return hundreds of KB (one measurement over 26 knowledge files: 163 KB and
256 KB for two common keywords, against 3.2 KB and 3.5 KB for the same questions through card lookup).

## 1. Cards first

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memq.py" <word> [<word> ...]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memq.py" webhook retry --only pitfalls,events -n 20
```

All words must appear in the same line. Each hit is one card:
`[kind] path:line  heading` plus a snippet. Add a word to narrow, `--only` to pick sources
(`critical, pitfalls, threads, events, extra`). Exit status 1 means no match.

## 2. Then read only that part

Use Read with `offset` and `limit` around the line from the card (for example 40 lines). Do not cat or
Read a whole large knowledge file, plan or log to find one entry. For long documents, read the status
summary at the top, then `grep -n` for the heading and read that section.

## 3. Before a negative claim

"X doesn't exist / can't be done / must be built" must be checked:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/verify_absence.py" <name> [--roots ../other-repo]
```

Keep the printed command and counts next to the claim. Zero hits means "not found", not "doesn't
exist". Name the capability state: doesn't exist / built but not wired / wired but switched off /
live. "Live" needs runtime evidence (rows, logs, a real run); and something that runs but always
returns "unknown" is not live in any useful sense.

## 4. Before changing a shared field or status

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/who_reads.py" <symbol> [--roots ../web-frontend]
```

Read the "conditions" group line by line: those are the places that can silently become always true or
always false after your change.

## 5. Context size

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ctx_usage.py"          # one turn behind
```

Never state a context percentage you did not just measure.

Script folder for this install: `${CLAUDE_PLUGIN_ROOT}/scripts/`.

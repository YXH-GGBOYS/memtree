# Getting started

[中文](getting-started_cn.md)

## 1. Install

Plugin (recommended):

```
/plugin marketplace add YXH-GGBOYS/memtree
/plugin install memtree@memtree
```

Manual:

```bash
git clone https://github.com/YXH-GGBOYS/memtree.git ~/memtree
cd ~/memtree && ./install.sh          # prints the hook JSON to merge into ~/.claude/settings.json
./install.sh --apply                  # or merge it for you (backs up settings.json first)
```

You need Python 3.9+. Nothing else is installed. Restart Claude Code (or open `/hooks`) afterwards.

## 2. Set up a project

Open Claude Code in the project and run the `memtree-init` skill (`/memtree:memtree-init` for the
plugin, `/memtree-init` for a manual install). Answer its questions; it creates `.memory/` from the
templates and never overwrites a file. Or run the script directly:

```bash
python3 ~/memtree/scripts/memtree_init.py --areas billing,auth,api --claude-md
```

Then write your real hard invariants into the DIGEST block of `.memory/CRITICAL_FACTS.md`, one per
line, each starting with `• `, under about 3,000 characters in total. Good digest lines are rules that
cost money, data or an incident when broken, for example:

```
• Money is stored as integer minor units (cents) everywhere; never floats. See §2.
• Only billing writes the invoices table; other services call its API. See §2.
```

Check what the model will receive:

```bash
printf '{"session_id":"check","cwd":"%s"}' "$PWD" \
  | MEMTREE_STATE_DIR="$(mktemp -d)" python3 ~/memtree/hooks/facts_digest.py; echo "exit=$?"
```

(For a plugin install the hooks live in the plugin folder; the `memtree-init` skill prints the right
path.) Commit `.memory/`.

## 3. Day to day

- New session: the first prompt gets the digest; later prompts get a one-line pointer.
- Before changing code in an area: read `.memory/<area>/PITFALLS.md`.
- Looking for a past incident, trap or decision: `memq.py <words>`, then Read the hit with offset/limit
  (skill `memtree-lookup`).
- About to write "X doesn't exist": `verify_absence.py X` first.
- About to change a shared field or status: `who_reads.py <symbol>` first.
- Reminder fires (context past 45% of the window): finish the step, write a handoff card at the next
  clean point, continue in a fresh session from the card (skill `memtree-handoff`).
- Compaction happens anyway: the digest, a "trust files over the summary" reminder and the latest open
  card are injected right after it.
- Line of work done: skill `memtree-closeout` (event, PITFALLS lifecycle, close the card, fix wrong
  claims at their source).

## 4. Measure

```bash
python3 ~/memtree/scripts/ctx_usage.py                  # this session, one turn behind
python3 ~/memtree/scripts/token_report.py --since 2026-10-01 --out token-report.md
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Hooks print nothing | No `.memory/CRITICAL_FACTS.md` (or `memtree.json`) at or above the session's directory |
| A red line says the DIGEST was not injected | Markers missing or misspelled, or no line inside them starts with `• ` |
| The handoff reminder never fires | You use a 200K-window model and the guess was 1M: set `MEMTREE_CONTEXT_WINDOW=200000` |
| Reminder fires too early or late | Set your own steps: `MEMTREE_HANDOFF_TOKENS=300000,450000,600000` |
| `python3: command not found` (Windows) | Change the hook commands to `python` or `py -3` |

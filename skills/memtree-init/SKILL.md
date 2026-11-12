---
name: memtree-init
description: Set up MemTree project memory in the current project (.memory/ with CRITICAL_FACTS and its injected digest, per-area PITFALLS, events index, handoff-card folder) through a short Q&A, and optionally add the MemTree section to CLAUDE.md. TRIGGER when the user asks to set up / initialize MemTree or project memory, to add CRITICAL_FACTS or PITFALLS files, or when a MemTree hook reports a missing DIGEST. SKIP when .memory/CRITICAL_FACTS.md already holds real facts and the user only wants to add or change one (edit that file directly), or when they ask for the v1 per-file summary build (that lives in legacy/).
---

# memtree-init

Goal: a `.memory/` that holds the project's hard invariants in one place, injected into every
session, plus empty homes for traps, incidents and handoff cards. Never overwrite anything.

## 1. Look before asking

- `ls -la .memory 2>/dev/null` and `git status --short .memory CLAUDE.md`.
- If `.memory/CRITICAL_FACTS.md` exists, show its DIGEST block and say what is already there.
  The script below only creates missing files, so it is safe to run again.

## 2. Ask once, at most five questions

Ask in one message and offer a suggested answer for each, based on what you can see in the repo
(top-level folders, service names, README):

1. Which areas or services should get their own `PITFALLS.md`? (e.g. `billing, auth, api`)
2. Which facts cost money, data or an incident when an agent gets them wrong? (units of money,
   which service owns which table, ID spaces, which environment is which, what must never be automated)
3. Which steps always need a human go-ahead in the current conversation? (deploys, data migrations,
   sending messages)
4. Any traps the team already knows about, for the first PITFALLS entries?
5. Add the MemTree section to `CLAUDE.md`? (it is appended between markers; nothing else is changed)

## 3. Create the files

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memtree_init.py" --areas billing,auth,api --claude-md --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/memtree_init.py" --areas billing,auth,api --claude-md
```

Drop `--claude-md` if the user said no. Use the real area names from the answers.

## 4. Fill the digest

Edit `.memory/CRITICAL_FACTS.md`:

- Replace the placeholder line inside `<!-- DIGEST-START -->` / `<!-- DIGEST-END -->` with the
  answers to questions 2 and 3, one fact per line, each line starting with `• `.
- Keep the digest under about 3,000 characters. Put explanations in the numbered sections and end
  the digest line with a pointer such as `See §2.`
- Write facts the user gave you. Do not invent invariants from reading code; if you noticed a likely
  one, ask.

Seed each named trap as a PITFALLS entry (`status: ACTIVE`, `last_seen` = today, a concrete
`how to verify`).

## 5. Verify what the model will actually receive

Run the hook the way Claude Code runs it and check the bytes and exit code, not just the file:

```bash
printf '{"session_id":"init-check","cwd":"%s"}' "$PWD" \
  | MEMTREE_STATE_DIR="$(mktemp -d)" python3 "${CLAUDE_PLUGIN_ROOT}/hooks/facts_digest.py"; echo "exit=$?"
```

Expect the digest lines, `exit=0`, and well under 9,000 bytes. A red line means the markers or the
`• ` bullets are wrong.

## 6. Finish

Tell the user what was created and that `.memory/` is project knowledge to commit with the code.
Do not commit unless they ask.

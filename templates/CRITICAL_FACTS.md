# CRITICAL_FACTS

Hard invariants of this project: facts that cost money, data or an incident when an agent gets
them wrong. This file is the only authority for them. Other files may point here; they must not
restate these facts. If another file disagrees with this one, the other file has a bug.

## How the digest works

- The lines between the DIGEST markers that start with `• ` are injected by the MemTree hook into
  each session once, and again after compaction. Edit them here only; the hook notices changes.
- One fact per line, a rule rather than a story. Keep the whole digest under about 3,000
  characters: it sits in the context of every call of every session.
- Put the detail in the numbered sections below and end the digest line with a pointer (`see §2`).
- Delete the placeholder line once you have real facts.

Examples of good digest lines (for a SaaS app with `billing`, `auth` and `api` services):

    • Money is stored as integer minor units (cents) everywhere; never floats. See §2.
    • Only `billing` writes the invoices table; other services call its API. See §2.
    • `auth` tokens are validated in `api` middleware only; handlers never re-parse them. See §1.
    • A deploy to production needs an explicit go-ahead in the current conversation. See §3.

<!-- DIGEST-START -->
• (placeholder) No hard invariants recorded yet. Fill this block in .memory/CRITICAL_FACTS.md (or run the memtree-init skill).
<!-- DIGEST-END -->

## 1. Environments and topology

Which environments exist, how to tell them apart, which commands are safe where.

## 2. Data invariants

Units, ownership of tables or fields, ID spaces, ordering guarantees.

## 3. Process rules

What always needs a human go-ahead, what must never be automated.

# <area> PITFALLS

Known traps in `<area>`. Read this before changing code in this area. One entry per trap, newest
first. Search across all areas with `memq.py <words> --only pitfalls`.

Lifecycle: an entry starts `ACTIVE`. When the root cause is fixed and the fix is verified, set it to
`RESOLVED` and keep it (it explains why the code looks the way it does). Move RESOLVED entries that
have not been seen for a few months to `archive/PITFALLS-archive.md`.

Entry format:

    ## P001 <short title>
    - status: ACTIVE                      (ACTIVE | RESOLVED)
    - type: data-shape                    (data-shape | concurrency | config | external-api | ordering | naming | other)
    - source event: events/YYYY-MM/EVT-YYYYMMDD-NNN.md
    - last_seen: YYYY-MM-DD
    - trap: what goes wrong, in one or two sentences
    - rule: what to do instead
    - how to verify: a command, test or query that shows whether the trap is present

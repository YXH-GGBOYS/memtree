# export-rounding (handoff card, 2026-11-12 15:40, from session 3f2a)

## Goal and acceptance
- Invoice export totals equal the sum of integer cents; `--check-totals` passes on the November data.

## Current step
- Fix written in `scripts/export_invoices.py`; unit test added; not yet run against staging data.

## Decisions (each with its source)
- Sum cents as integers, divide once at the end: billing/PITFALLS.md P001 rule.
- Keep the CSV column names unchanged: decided in review, 2026-11-12 (PR comment).

## Authorization
- None. A handoff card never carries production, deploy or data-change authorization.

## Files and commits touched
- app repo, branch `fix/export-rounding`, commit `a1b2c3d` (fix + test).

## Not done or not verified
- Not run against staging data. PITFALLS P001 still ACTIVE.

## Next step
1. `python3 scripts/export_invoices.py --env staging --check-totals`
2. If it passes, set P001 to RESOLVED and run skill memtree-closeout.

## Read first
- .memory/billing/PITFALLS.md P001 (lines 15-22)
- scripts/export_invoices.py lines 40-75

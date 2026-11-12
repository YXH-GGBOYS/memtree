# billing PITFALLS

Known traps in `billing`. Read before changing code here. Newest first.

## P002 Webhook retry creates a duplicate invoice
- status: RESOLVED
- type: external-api
- source event: events/2026-11/EVT-20261103-001.md
- last_seen: 2026-11-03
- trap: the payment provider retries a webhook when our response is slow; each retry used to create an invoice
- rule: look up `webhook_events.event_id` first and return 200 without side effects if it exists
- how to verify: `pytest tests/billing/test_webhooks.py::test_retry_is_idempotent`

## P001 Float rounding on invoice totals
- status: ACTIVE
- type: data-shape
- source event: none (found in review)
- last_seen: 2026-10-21
- trap: the export script still sums `amount_cents / 100` as floats before rounding, so totals can be off by a cent
- rule: sum integer cents, divide once at the end
- how to verify: `python3 scripts/export_invoices.py --check-totals`

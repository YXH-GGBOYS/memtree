# backend — Known Pitfalls

> AI agents: **Read this entire file BEFORE writing any code** in this service.

## 🔴 Critical (data corruption / 500 errors)

### P001: User ID dual namespace
- **Trap**: `billing.customers.customer_id` uses `billing.customers.id`, but `iam.accounts.account_id` uses `iam.accounts.id`. They are different ID spaces.
- **Affected files**: services/billing_service.py, services/iam_service.py
- **Correct approach**: When writing to IAM, use `customer.iam_account_id` (not `customer.id`)
- **Source**: Production incident — admin credit grant created orphaned IAM records

### P002: ORM attribute ≠ DB column name
- **Trap**: `AuditLog.log_data` (Python attribute) maps to `log_metadata` (DB column via `Column("log_metadata")`)
- **Affected files**: models/audit.py, services/audit_service.py
- **Correct approach**: In ORM queries use `.log_data`, in raw SQL use `log_metadata`
- **Source**: Code review — 3 separate PRs made this mistake

### P003: Price unit mismatch
- **Trap**: `plans.price` is in **major units** (Decimal), but `billing.credits_available` is in **minor units** (integer)
- **Affected files**: routes/checkout.py, services/payment_service.py
- **Correct approach**: Always multiply plan price by 100 before comparing with credits. Use `int(price * 100)`
- **Source**: Team knowledge

## 🟡 Warning (logic bugs)

### P010: Flush-only service pattern
- **Trap**: Service methods (payment, settlement) only `flush()`, never `commit()`. The caller must commit.
- **Affected files**: services/payment_service.py, services/settlement_service.py
- **Correct approach**: After calling any service method, the router/handler must call `await session.commit()`
- **Source**: Architecture decision — allows caller to control transaction boundaries

### P011: Cancel subscription requires 3 steps
- **Trap**: Cancelling a subscription requires: (1) set `subscription.cancelled_at`, (2) write `AuditLog(type='cancelled')`, (3) set `log_metadata` with reason. Missing any step leaves data inconsistent.
- **Affected files**: routes/subscriptions.py, services/subscription_service.py
- **Correct approach**: Always use the `cancel_subscription()` service method, never manually update fields
- **Source**: Bug fix — partial cancellation left orphaned payment holds

## References
- DB column mismatches: cross-refs/orm-db-mismatch.md
- Full architecture: backend/INDEX.md

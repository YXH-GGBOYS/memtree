# backend — Known Pitfalls

> AI agents: **Read this entire file BEFORE writing any code** in this service.

## 🔴 Critical (data corruption / 500 errors)

### P001: User ID dual namespace
- **Trap**: `wallet_balances.user_id` uses `trading.users.id`, but `ledger_accounts.owner_id` uses `auth.user_accounts.id`. They are different ID spaces.
- **Affected files**: services/wallet_service.py, services/ledger_service.py
- **Correct approach**: When writing to ledger, use `trading_user.auth_user_id` (not `trading_user.id`)
- **Source**: Production incident — admin top-up created ghost ledger accounts

### P002: ORM attribute ≠ DB column name
- **Trap**: `OrderEvent.event_data` (Python attribute) maps to `event_metadata` (DB column via `Column("event_metadata")`)
- **Affected files**: models/order.py, services/order_service.py
- **Correct approach**: In ORM queries use `.event_data`, in raw SQL use `event_metadata`
- **Source**: Code review — 3 separate PRs made this mistake

### P003: Price unit mismatch
- **Trap**: `listings.price` is in **dollars** (Decimal), but `wallet_balances.available` is in **cents** (integer)
- **Affected files**: routes/trading.py, services/escrow_service.py
- **Correct approach**: Always multiply listing price by 100 before comparing with wallet. Use `int(price * 100)`
- **Source**: Team knowledge

## 🟡 Warning (logic bugs)

### P010: Flush-only service pattern
- **Trap**: Service methods (escrow, settlement) only `flush()`, never `commit()`. The caller must commit.
- **Affected files**: services/escrow_service.py, services/settlement_service.py
- **Correct approach**: After calling any service method, the router/handler must call `await session.commit()`
- **Source**: Architecture decision — allows caller to control transaction boundaries

### P011: Cancel order requires 3 steps
- **Trap**: Cancelling an order requires: (1) set `order.cancelled_at`, (2) write `OrderEvent(type='cancelled')`, (3) set `event_metadata` with reason. Missing any step leaves data inconsistent.
- **Affected files**: routes/orders.py, services/order_service.py
- **Correct approach**: Always use the `cancel_order()` service method, never manually update fields
- **Source**: Bug fix — partial cancellation left orphaned escrow holds

## References
- DB column mismatches: cross-refs/orm-db-mismatch.md
- Full architecture: backend/INDEX.md

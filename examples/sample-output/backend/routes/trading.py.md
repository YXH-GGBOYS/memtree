```yaml
---
source: src/api/routes/trading.py
service: backend
layer: router
last_analyzed: 2026-04-07T10:30:00Z
source_hash: a1b2c3d4
depends_on: [services/escrow_service.py, services/order_service.py, models/order.py, models/listing.py]
depended_by: [../gateway/routes/internal.py, ../frontend/composables/useOrder.ts]
---
```

# backend/routes/trading.py

## TL;DR
Trade order router | calls escrow_service + order_service | price=dollars (not cents), flush-only services

## Quick Ref
| Export | Signature | Constraint |
|--------|-----------|------------|
| create_order | POST /orders (listing_id, idempotency_key) → Order | Locks listing FOR UPDATE, flush-only |
| pay_order | POST /orders/{id}/pay → Order | Deducts wallet (cents), creates escrow hold |
| cancel_order | POST /orders/{id}/cancel (reason) → None | Must set cancelled_at + write OrderEvent |
| confirm_delivery | POST /orders/{id}/confirm-delivery → Order | Starts protection period |

> AI agent: 80% of the time, reading up to here is enough. Full Analysis below.

## Full Analysis

### Node Position
- **Service**: backend
- **Layer**: router
- **Ancestry**: project → backend → routes → **trading.py**

### Relationships

#### Siblings
| File | Role | Relation to this file |
|------|------|-----------------------|
| rental.py | Rental order endpoints | Shares escrow_service, different order model |
| wallet.py | Wallet top-up/balance | Wallet balance checked before pay_order |
| orders.py | Generic order queries | Read-only views of orders this file creates |

#### Children (this file calls)
| Target:function | Signature | Return |
|----------------|-----------|--------|
| escrow_service.create_hold | (session, order, amount_cents) → EscrowHold | flush-only |
| order_service.create_order | (session, listing_id, buyer_id) → Order | flush-only |
| order_service.cancel_order | (session, order_id, reason, actor) → None | flush-only |

#### Callers (who calls this file)
| Source | How | Context |
|--------|-----|---------|
| frontend/composables/useOrder.ts | POST /orders via fetch | User clicks "Buy" button |
| gateway/routes/internal.py | POST /internal/orders | Admin-initiated order |

#### Collaboration Pattern
User clicks Buy → useOrder.ts calls POST /orders → trading.py validates listing + wallet balance → calls escrow_service to lock funds → creates Order → returns order_id. Frontend then calls POST /orders/{id}/pay to finalize.

### Key Constraints
- **Price unit**: listings.price is DOLLARS, wallet is CENTS. Must convert: `int(listing.price * 100)`
- **Transaction**: All service calls are flush-only. This router commits after all operations succeed.
- **Idempotency**: Uses idempotency_key to prevent duplicate orders
- **Concurrency**: SELECT ... FOR UPDATE on listing to prevent double-sell

### Modification Risk
- Changing create_order affects: frontend buy flow, admin order creation, escrow accounting
- Changing cancel_order affects: refund flow, penalty system, notification triggers
- Any price calculation change must be mirrored in rental.py (same escrow pattern)

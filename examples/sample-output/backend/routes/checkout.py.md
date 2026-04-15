```yaml
---
source: src/api/routes/checkout.py
service: backend
layer: router
last_analyzed: 2026-04-07T10:30:00Z
source_hash: a1b2c3d4
depends_on: [services/payment_service.py, services/subscription_service.py, models/subscription.py, models/plan.py]
depended_by: [../gateway/routes/internal.py, ../frontend/composables/useCheckout.ts]
---
```

# backend/routes/checkout.py

## TL;DR
Checkout router | calls payment_service + subscription_service | price=major units (not minor), flush-only services

## Quick Ref
| Export | Signature | Constraint |
|--------|-----------|------------|
| create_subscription | POST /subscriptions (plan_id, idempotency_key) → Subscription | Locks plan FOR UPDATE, flush-only |
| process_payment | POST /subscriptions/{id}/pay → Subscription | Deducts credits (minor units), creates payment hold |
| cancel_subscription | POST /subscriptions/{id}/cancel (reason) → None | Must set cancelled_at + write AuditLog |
| activate_subscription | POST /subscriptions/{id}/activate → Subscription | Starts cooling-off period |

> AI agent: 80% of the time, reading up to here is enough. Full Analysis below.

## Full Analysis

### Node Position
- **Service**: backend
- **Layer**: router
- **Ancestry**: project → backend → routes → **checkout.py**

### Relationships

#### Siblings
| File | Role | Relation to this file |
|------|------|-----------------------|
| subscription.py | Subscription endpoints | Shares payment_service, different subscription model |
| billing.py | Credit top-up/balance | Credit balance checked before process_payment |
| plans.py | Generic plan queries | Read-only views of plans this file creates |

#### Children (this file calls)
| Target:function | Signature | Return |
|----------------|-----------|--------|
| payment_service.create_hold | (session, subscription, amount_minor) → PaymentHold | flush-only |
| subscription_service.create_subscription | (session, plan_id, account_id) → Subscription | flush-only |
| subscription_service.cancel_subscription | (session, subscription_id, reason, actor) → None | flush-only |

#### Callers (who calls this file)
| Source | How | Context |
|--------|-----|---------|
| frontend/composables/useCheckout.ts | POST /subscriptions via fetch | User clicks "Subscribe" button |
| gateway/routes/internal.py | POST /internal/subscriptions | Admin-initiated subscription |

#### Collaboration Pattern
User clicks Subscribe → useCheckout.ts calls POST /subscriptions → checkout.py validates plan + credit balance → calls payment_service to hold funds → creates Subscription → returns subscription_id. Frontend then calls POST /subscriptions/{id}/pay to finalize.

### Key Constraints
- **Price unit**: plans.price is MAJOR UNITS, credits is MINOR UNITS. Must convert: `int(plan.price * 100)`
- **Transaction**: All service calls are flush-only. This router commits after all operations succeed.
- **Idempotency**: Uses idempotency_key to prevent duplicate subscriptions
- **Concurrency**: SELECT ... FOR UPDATE on plan to prevent double-subscribe

### Modification Risk
- Changing create_subscription affects: frontend subscribe flow, admin subscription creation, payment accounting
- Changing cancel_subscription affects: refund flow, penalty system, notification triggers
- Any price calculation change must be mirrored in subscription.py (same payment pattern)

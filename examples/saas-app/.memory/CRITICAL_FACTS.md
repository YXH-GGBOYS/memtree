# CRITICAL_FACTS (example: a SaaS app with billing, auth and api services)

Hard invariants. This file is the only authority for them; other files point here.
The `• ` lines between the DIGEST markers are injected once per session by the MemTree hook.
Keep the digest under about 3,000 characters.

<!-- DIGEST-START -->
• Money is stored as integer minor units (cents) in every service and table; never floats. See §2.
• Only `billing` writes `invoices` and `credits`; `api` and the web app call billing's endpoints. See §2.
• User ids from `auth` (`usr_...`) and customer ids in `billing` (`cus_...`) are different id spaces; map via `billing.customers.user_id`. See §2.
• `staging` and `production` share no database; a command that names `prod` needs an explicit go-ahead in the current conversation. See §1.
• Webhook handlers must be idempotent on the event id; retries are normal. See billing/PITFALLS.md P002.
<!-- DIGEST-END -->

## 1. Environments

- `local` (docker compose), `staging`, `production`. Each has its own database and secrets.
- Deploys and data migrations to production are always run by a person, never from an agent session
  without an explicit go-ahead in that session.

## 2. Data invariants

- Amounts: integer cents (`amount_cents`), currency in a separate column. Display code divides by 100.
- Ownership: `billing` owns `invoices`, `credits`, `customers`; `auth` owns `users`, `sessions`.
- Id spaces: `usr_` ids never appear in billing tables except in `customers.user_id`.

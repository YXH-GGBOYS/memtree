# Example: Trading Platform

This is a sanitized example from a real 913-file trading platform where MemTree was deployed and validated.

## Results
- **912 per-file memory documents** generated
- **128 INDEX.md** directory indexes
- **7 PITFALLS.md** service pitfall guides
- **6 cross-refs/** files
- Quality audit: **14/14 PASS**
- AI agent identified critical user_id pitfall in **2 seconds** with MemTree

## Sample Files

| File | What it shows |
|------|--------------|
| `sample-output/ROOT.md` | Project navigation root — 5 services mapped |
| `sample-output/backend/PITFALLS.md` | Service pitfalls — 🔴 critical + 🟡 warning with affected files |
| `sample-output/backend/routes/trading.py.md` | Per-file memory — TL;DR + Quick Ref + Full Analysis |

## Config Used

```yaml
project:
  name: "Trading Platform"
services:
  - name: backend
    path: src/api/
    lang: python
    framework: fastapi
    entry_pattern: "routes/*.py"
  - name: frontend
    path: src/web/
    lang: vue
    framework: nuxt
    entry_pattern: "pages/**/*.vue"
  - name: admin
    path: admin/src/
    lang: typescript
    framework: react
    entry_pattern: "pages/**/*.tsx"
  - name: gateway
    path: src/gateway/
    lang: python
    framework: fastapi
    entry_pattern: "routes/*.py"
  - name: extension
    path: ext/src/
    lang: typescript
    entry_pattern: "background.ts"
database:
  type: postgresql
  schemas: [auth, trading, admin]
pitfalls:
  - "wallet balance is in cents, listing price is in dollars"
  - "order_events DB column is event_metadata, ORM attribute is event_data"
  - "services use flush-only pattern, caller commits"
  - "wallet user_id uses trading.users.id, ledger owner_id uses auth.user_accounts.id"
```

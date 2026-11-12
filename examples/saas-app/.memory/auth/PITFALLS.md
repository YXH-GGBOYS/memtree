# auth PITFALLS

## P001 Session cookie domain differs between staging and production
- status: ACTIVE
- type: config
- source event: events/2026-11/EVT-20261108-002.md
- last_seen: 2026-11-08
- trap: `SESSION_COOKIE_DOMAIN` is set per environment; copying the staging value to production causes a login loop
- rule: never copy cookie settings between environments; each comes from that environment's config
- how to verify: `curl -sI https://<env-host>/login | grep -i set-cookie`

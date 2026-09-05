# SAM Production Compose

This is the only production Compose topology. It is separate from
`docker-compose.db.yml`, which remains a local two-database development setup
and must never be used on the VPS.

## Topology

| Service | Profile | Network exposure | Purpose |
|---|---|---|---|
| `caddy` | `production` | Host ports 80 and 443 only | TLS, PWA, API proxy |
| `api`, `worker`, `beat` | `production` | Internal only | Application processes (scoped identity/domain stores + Redis) |
| `identity-postgres`, `domain-postgres`, `redis` | `production`, `operations` | Internal only | Scoped persistent stores and broker required by both profiles |
| `migration`, `store-operation` | `operations` | Internal only | Explicit one-shot operations (empty-schema init + greenfield gates) |

`caddy` joins the public and internal networks so it can obtain certificates and
reach the API. Every other service is internal. No database, Redis, API,
worker, beat, migration, or store-operation service has a host port.

The stateful services are in both profiles. This lets an explicit operations
command bring up its healthy PostgreSQL dependency without relying on an
already-running production profile. Redis is included in `operations` as the
same persistent broker topology, though the current one-shot jobs depend only
on the scoped PostgreSQL stores.

There is **no legacy combined `postgres` store**. The identity and domain
stores are separate authorities with distinct volumes, principals, and private
networks; core services route to both scoped stores and never to a combined
store.

## Immutable release artifacts

The application and frontend services resolve **only** digest-pinned image
references of the form `<repository>@sha256:<digest>`. No service builds from
source and no mutable tag is accepted. The following variables are required and
fail closed when unset or empty:

| Variable | Purpose |
|---|---|
| `BACKEND_IMAGE_REPOSITORY`, `BACKEND_IMAGE_DIGEST` | Digest-pinned backend image (api/worker/beat/migration/store-operation). `BACKEND_IMAGE_DIGEST` MUST be the approved `backend_digest` from the deployment plan (64 lowercase hex). |
| `FRONTEND_IMAGE_REPOSITORY`, `FRONTEND_IMAGE_DIGEST` | Digest-pinned frontend image (caddy). `FRONTEND_IMAGE_DIGEST` MUST be the approved `frontend_digest` from the deployment plan. |

A missing/empty digest makes Compose fail closed; a malformed (non-64-hex)
digest is rejected by the `contract_release_digests_ok` gate in
`ops/lib/operation-contract.sh` before any activation.

## Required Environment Categories

Provide these names from a protected VPS-only environment source. Do not add an
environment file to this repository, image context, shell history, or logs.
Compose requires every listed value to be present and non-empty before it starts
or runs a service.

| Category | Names |
|---|---|
| Release artifacts | `BACKEND_IMAGE_REPOSITORY`, `BACKEND_IMAGE_DIGEST`, `FRONTEND_IMAGE_REPOSITORY`, `FRONTEND_IMAGE_DIGEST` |
| Scoped store endpoints | `IDENTITY_DATABASE_URL`, `DOMAIN_DATABASE_URL`, `IDENTITY_DATABASE_RUNTIME_ROLE`, `DOMAIN_DATABASE_RUNTIME_ROLE` |
| Scoped store initialization | `IDENTITY_POSTGRES_USER`, `IDENTITY_POSTGRES_PASSWORD`, `IDENTITY_POSTGRES_DB`, `DOMAIN_POSTGRES_USER`, `DOMAIN_POSTGRES_PASSWORD`, `DOMAIN_POSTGRES_DB` |
| Application security | `ENVIRONMENT`, `SECRET_KEY`, `JWT_SECRET_PROVENANCE_VERSION`, `JWT_SECRET_FILE`, `JWT_SECRET_RECEIPT_FILE`, `JWT_SECRET_REPOSITORY_ROOT` |
| Background services | `REDIS_URL`, `CELERY_BROKER_URL` |
| AI configuration | `AI_PROVIDER`, `GEMINI_API_KEY`, `CLAUDE_API_KEY`, `AI_INTAKE_ENABLED` |

The identity and domain URLs belong only to `api`, `worker`, `beat`, `migration`,
and `store-operation`, each scoped to its store. Credentials exist only in the
protected environment source and MUST NOT appear in evidence.

## Operational Commands

Run from `biohack-ddbb`. Replace `/etc/sam/production.env` with the protected
VPS-only environment source; this path is intentionally outside every Git
repository.

```bash
docker compose --env-file /etc/sam/production.env -f deploy/production/compose.yml --profile production up -d identity-postgres domain-postgres redis
docker compose --env-file /etc/sam/production.env -f deploy/production/compose.yml --profile production --profile operations run --rm migration
docker compose --env-file /etc/sam/production.env -f deploy/production/compose.yml --profile production up -d api worker beat caddy
```

`migration` runs both independent, forward-only Alembic histories against their
scoped stores (`alembic -n identity upgrade head` then
`alembic -n domain upgrade head`) — the greenfield empty-schema initialization.
It never runs against a combined store and never downgrades. Do not run an
Alembic downgrade. If initialization fails, stop before application startup,
retain the receipt, and follow the cross-repository runbook's fix-forward or
verified-restore boundary.

## Controlled Test Users

`tester-provision` is the production-only DDBB entrypoint for the backend's
fixed roster of fifty adjustment-test accounts. It does not contain account
creation logic, accept credentials, or enable public registration.

Run it only after the API is healthy and after the approved backend image that
contains the provisioner is pinned in the protected environment:

```bash
docker compose --env-file /etc/sam/production.env -f deploy/production/compose.yml --profile production --profile operations run --rm tester-provision
```

Expected stdout is a redacted JSON receipt with `requested`, `created`, and
`existing` counts. A successful first run reports `requested: 50`; a rerun
reports the same request count and only existing accounts. It never prints,
logs, writes, or reissues a temporary password. Deliver credentials only through
the authorized orchestration channel after a successful verified run.

The command rejects a non-production environment, a missing explicit production
flag, or every count other than 50. If it reports an incomplete account pair,
stop: do not retry or edit records through SQL. Preserve the redacted receipt
and use the backend incident/repair procedure.

## Isolated-Store Operations (credential-free wrappers)

The `ops/*` wrappers are the operator entrypoints for the identity/domain store
split. They are credential-free: every operation is dry-run-first, idempotent,
checksummed, and rejects credential-like arguments before any Compose call.
Credentials reach the backend adapter only through the protected VPS
environment source; no wrapper embeds or accepts a URL, user, password, token,
or secret-file value.

Run from `biohack-ddbb`. Replace `/etc/sam/production.env` with the protected
VPS-only environment source.

```bash
# Inventory (read-only) — no write is ever performed by the default dry-run.
ops/load --store identity --receipt-dir /var/lib/sam/receipts
ops/load --store domain  --receipt-dir /var/lib/sam/receipts

# Backfill — dry-run first, then explicit apply.
ops/backfill --dry-run --store identity
ops/backfill --apply --store identity

# Reconciliation — blocks (non-zero) on any discrepancy.
ops/reconcile --dry-run --store identity
ops/reconcile --apply --store identity

# Per-store backup and restore (backup profile; restore is approval-gated).
ops/backup --dry-run --store domain
ops/backup --apply --store domain
ops/restore --dry-run --store domain
```

The wrappers emit a redacted JSON receipt to stdout and, when `--receipt-dir`
is given, write `receipt.json` there. Receipts contain action, opaque IDs,
counts, status, and checksums only. See
`../docs/database-isolation-runbook.md` for the full procedure.

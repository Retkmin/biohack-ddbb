# SAM Production Compose

This is the only production Compose topology. It is separate from
`docker-compose.db.yml`, which remains a local two-database development setup
and must never be used on the VPS.

## Topology

| Service | Profile | Network exposure | Purpose |
|---|---|---|---|
| `caddy` | `production` | Host ports 80 and 443 only | TLS, PWA, API proxy |
| `api`, `worker`, `beat` | `production` | Internal only | Application processes |
| `postgres`, `redis` | `production`, `operations` | Internal only | Persistent data and broker required by both profiles |
| `migration-verification`, `migration`, `provisioning` | `operations` | Internal only | Explicit one-shot operations |

`caddy` joins the public and internal networks so it can obtain certificates and
reach the API. Every other service is internal. No database, Redis, API,
worker, beat, migration, verifier, or provisioning service has a host port.

The stateful services are in both profiles. This lets an explicit operations
command bring up its healthy PostgreSQL dependency without relying on an
already-running production profile. Redis is included in `operations` as the
same persistent broker topology, though the current one-shot jobs depend only
on PostgreSQL.

## Required Environment Categories

Provide these names from a protected VPS-only environment source. Do not add an
environment file to this repository, image context, shell history, or logs.
Compose requires every listed value to be present and non-empty before it starts
or runs a service.

| Category | Names |
|---|---|
| PostgreSQL initialization | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| Runtime database identity | `DATABASE_URL`, `DATABASE_RUNTIME_ROLE` |
| Maintenance database identity | `DATABASE_ADMIN_URL`, `DATABASE_LOGIN_PASSWORD` |
| Application security | `ENVIRONMENT`, `SECRET_KEY`, `JWT_SECRET_PROVENANCE_VERSION`, `JWT_SECRET_FILE`, `JWT_SECRET_RECEIPT_FILE`, `JWT_SECRET_REPOSITORY_ROOT` |
| Background services | `REDIS_URL`, `CELERY_BROKER_URL` |
| AI configuration | `AI_PROVIDER`, `GEMINI_API_KEY`, `CLAUDE_API_KEY`, `AI_INTAKE_ENABLED` |
| Disposable verifier | `MIGRATION_DEPLOYMENT_TARGET_KIND`, `MIGRATION_DEPLOYMENT_RECEIPT_PATH`, `MIGRATION_DEPLOYMENT_RECEIPTS_DIR` |

The runtime URL belongs only to `api`, `worker`, and `beat`; the admin URL and
login password belong only to the explicit operations. `MIGRATION_DEPLOYMENT_TARGET_KIND`
must identify a disposable verifier target. The receipt path must be an absolute
path below `/var/lib/sam/migration-verification-receipts`, and the host directory
named by `MIGRATION_DEPLOYMENT_RECEIPTS_DIR` is mounted there only for the
verifier.

Before the verifier runs, the operator creates that host directory outside all
repositories with owner-only access, for example `install -d -m 0700
/var/lib/sam/migration-verification-receipts`. Retain the redacted receipt in
that directory; do not place it in an image, source repository, or a public log.

## Operational Commands

Run from `biohack-ddbb`. Replace `/etc/sam/production.env` with the protected
VPS-only environment source; this path is intentionally outside every Git
repository.

```bash
docker compose --env-file /etc/sam/production.env -f deploy/production/compose.yml --profile production up -d postgres redis
docker compose --env-file /etc/sam/production.env -f deploy/production/compose.yml --profile production --profile operations run --rm migration-verification
docker compose --env-file /etc/sam/production.env -f deploy/production/compose.yml --profile production --profile operations run --rm migration
docker compose --env-file /etc/sam/production.env -f deploy/production/compose.yml --profile production --profile operations run --rm provisioning
docker compose --env-file /etc/sam/production.env -f deploy/production/compose.yml --profile production up -d api worker beat caddy
```

Create and prove a PostgreSQL backup before every migration. The verifier runs
before the migration and writes a retained redacted receipt to the protected
mount. Do not run an Alembic downgrade. If a migration fails, stop before
application startup, retain the receipt, and follow the cross-repository
runbook's fix-forward or verified-restore boundary.

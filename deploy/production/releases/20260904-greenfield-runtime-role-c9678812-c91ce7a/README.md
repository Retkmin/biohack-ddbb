# Release 20260904-greenfield-runtime-role-c9678812

Corrective greenfield VPS release: adds the scoped `0002_*_runtime_role`
Alembic migrations that provision the safe `sam_runtime` NOLOGIN runtime
principal (plus its minimum membership + table/schema grants) on both the
identity and domain stores. Prior releases created only the store tables
(`users`/`sessions` and `account_profiles`) and never the runtime role, so the
production application's `SET ROLE "sam_runtime"` failed with
`role "sam_runtime" does not exist` and blocked `activate` → `start`.

This release ships a no-cache build of the backend source carrying both scoped
runtime-role migrations.

## Contents

| File | Purpose |
|---|---|
| `plan.json` | Immutable, versioned deployment plan. `state` is `preflight` (no traffic). `backend_digest`/`frontend_digest` pin this release's images; `plan_sha256` binds the plan to its canonical content. `dns_names` are the confirmed SAM domains. |
| `compose.yml` | Private greenfield topology (scoped stores, private networks, digest-pinned images, Caddy-only 80/443). |
| `control-manifest.schema.json` | JSON Schema contract for the deployment plan. |
| `SHA256SUMS` | SHA-256 manifest of every artifact above. Verify with `sha256sum -c SHA256SUMS`. |

## Images

| Field | Value |
|---|---|
| Backend repository:tag | `biohack/sam-backend:20260904-greenfield-runtime-role-131114` |
| Backend immutable image ID/digest | `sha256:c967881209071574b2e3dc12f4cd6394b35bc58e54c60289826e61a198d0b156` |
| Frontend repository:tag | `biohack/sam-frontend:20260903-greenfield-9558a93` |
| Frontend digest | `sha256:c91ce7a0a2305cdaf2d1294b4af0b7c532ecaff6f196c2c3cb457c217d560855` |
| `plan.json` `plan_sha256` | `209d601be0be6463943e49234fbc981c1525217a1b62db524e474d670499f363` |

## What changed (runtime-role migration)

Both independent forward-only Alembic histories gain a `0002` revision:

- `alembic/identity/versions/0002_identity_runtime_role.py` — creates/ensures
  `sam_runtime` NOLOGIN, grants the identity connection role membership, and
  grants `SELECT, INSERT, UPDATE, DELETE` on `users`/`sessions` + `USAGE` on
  `public`.
- `alembic/domain/versions/0002_domain_runtime_role.py` — same for the domain
  store, granting on `account_profiles`.

Both fail closed on a pre-existing unsafe role (any of LOGIN / SUPERUSER /
CREATEROLE / CREATEDB / REPLICATION / BYPASSRLS, ownership of the schema or
tables, or privileged membership) and never create a LOGIN role or read admin
secrets.

## Behavior attestation

The exact image `sha256:c9678812...` was behavior-attested locally and against a
disposable fresh PostgreSQL:

- `alembic -n identity upgrade head` and `alembic -n domain upgrade head` apply
  `0001` → `0002` and create `sam_runtime` (`rolcanlogin=f`, `rolsuper=f`,
  `rolcreaterole=f`, `rolcreatedb=f`, `rolreplication=f`, `rolbypassrls=f`).
- The migration connection's role is granted membership in `sam_runtime`.
- `SELECT/INSERT/UPDATE/DELETE` on the store tables and `USAGE` on `public`
  are granted to `sam_runtime`.
- `SET ROLE "sam_runtime"` succeeds and reads the store tables (the exact path
  that previously failed with `role "sam_runtime" does not exist`).
- A pre-existing `sam_runtime` with an unsafe attribute fails closed and is
  left unaltered.
- `17 passed` scoped runtime-role + store-history tests (local Postgres).

## Lifecycle

- `preflight` validates the sealed plan (no write, no DB, no traffic).
- `initialize` runs scoped migrations only after the actual prior gates pass.
- `migration` applies both forward-only histories to head (`0002`).
- `activate` requires initialized evidence and a persisted health attestation.

## Runtime correction (beat scheduler)

`beat` runs as the image default user (uid 1000), not the VPS owner uid 1001,
so its Celery `PersistentScheduler` can write `celerybeat-schedule` to the
image-owned `/app` working directory. `beat` does not read the JWT provenance
secret, so the owner-uid `0600` boundary on `jwt.secret` is preserved (the
read-only JWT mount remains for `api`/`worker`/`beat` consistency).

The prior releases, receipts, and volumes are retained. On a failed new runtime
gate, remove only containers and networks created for this release.

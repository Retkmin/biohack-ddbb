# Release 20260904-greenfield-empty-tables-1e4fc694

Corrective greenfield VPS release: fixes the pre-migration empty-store gate so
a fresh schema (whose ``users``/``account_profiles`` tables do not yet exist) is
treated as empty instead of a blocking missing-table error, while a non-empty
existing store still fails closed.

Prior release `20260904-greenfield-attested-3eed6917` was behavior-attested for
`initialize` but its `verify-empty` queried application tables before migrations
created them, so a real fresh PostgreSQL schema failed closed with
``UndefinedTableError`` (relation "users" does not exist). This release ships a
no-cache build of the corrected backend source.

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
| Backend repository:tag | `biohack/sam-backend:20260904-greenfield-empty-tables-121357` |
| Backend immutable image ID/digest | `sha256:1e4fc694841675d3a2b41d1b7265cacb967bc1d3a4c8e6044218b991903e6f59` |
| Frontend repository:tag | `biohack/sam-frontend:20260903-greenfield-9558a93` |
| Frontend digest | `sha256:c91ce7a0a2305cdaf2d1294b4af0b7c532ecaff6f196c2c3cb457c217d560855` |
| `plan.json` `plan_sha256` | `2da5c112c47e1e9f79b4d203c033ca3a907290bf994f32cb8bb23b6b37e1dff8` |

## Behavior attestation

The exact image `sha256:1e4fc694...` was behavior-attested locally and against a
disposable fresh PostgreSQL:

- `initialize --store identity` without database URLs returns the expected
  fail-closed `missing_identity_url` (accepted, not an unexpected-argument error).
- `verify-empty` against a fresh schema (no `users`/`account_profiles` tables)
  returns `blocked: false`, `stores_empty: true`.
- `verify-empty` against a store with an existing non-empty `users` table
  returns `blocked: true`, `failure_code: store_not_empty`.

## Lifecycle

- `preflight` validates the sealed plan (no write, no DB, no traffic).
- `verify-empty` treats missing pre-migration tables as empty; existing rows
  still block.
- `initialize` runs scoped migrations only after the actual prior gates pass.
- `activate` requires initialized evidence and a persisted health attestation.

The prior releases, receipts, and volumes are retained. On a failed new runtime
gate, remove only containers and networks created for this release.

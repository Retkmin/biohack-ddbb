# Release 20260904-greenfield-lifecycle-9035ac8f

Pre-application lifecycle correction for the greenfield VPS deployment
(`database-isolation-vps-deployment`). This release carries the backend image
that implements the two previously missing fail-closed lifecycle gates —
`initialize` and `activate` — in addition to the already-shipped
`preflight`/`verify-empty`, and binds every artifact digest to its canonical
content.

## Contents

Every artifact this release claims is listed here and covered by `SHA256SUMS`
(verify with `sha256sum -c SHA256SUMS`). The manifest binds each artifact's
digest to its canonical content, so a well-formed-but-wrong digest fails closed.

| File | Purpose |
|---|---|
| `plan.json` | Immutable, versioned deployment plan. `state` is `preflight` (no traffic). `backend_digest`/`frontend_digest` pin this release's images; `plan_sha256` binds the plan to its canonical content. |
| `compose.yml` | Private greenfield topology (scoped stores, private networks, digest-pinned images, Caddy-only 80/443). |
| `control-manifest.schema.json` | JSON Schema contract for the deployment plan (13 required fields, `approval` def). |
| `README.md` | This release description. |
| `SHA256SUMS` | SHA-256 manifest of every artifact above. Verify with `sha256sum -c SHA256SUMS`. |

## Images

| Field | Value |
|---|---|
| Backend repository:tag | `biohack/sam-backend:20260904-greenfield-lifecycle` |
| Backend digest | `sha256:9035ac8f99187215e867aaee3e5718da29a6d207706252f857d7779ce1e61273` |
| Frontend repository:tag | `biohack/sam-frontend:20260903-greenfield-9558a93` |
| Frontend digest | `sha256:c91ce7a0a2305cdaf2d1294b4af0b7c532ecaff6f196c2c3cb457c217d560855` |
| `plan.json` `backend_digest` | `9035ac8f99187215e867aaee3e5718da29a6d207706252f857d7779ce1e61273` |
| `plan.json` `frontend_digest` | `c91ce7a0a2305cdaf2d1294b4af0b7c532ecaff6f196c2c3cb457c217d560855` |
| `plan.json` `plan_sha256` | `6676cf1edb8c6de792ecff330b54ed074b5a62722b44e195dbb01bb28f52120a` |

## Lifecycle gates implemented

- `preflight` — validate the immutable plan (no write, no DB, no traffic).
- `verify-empty` — confirm both scoped stores are empty (read-only, fail closed).
- `initialize` — permitted only after preflight + empty-store verification; runs
  both scoped Alembic migrations atomically or fails closed; persists a redacted
  receipt; **never enables traffic** (`write_enabled:true`, `traffic_enabled:false`).
- `activate` — permitted only after real persisted initialized evidence (both
  scoped `alembic_version` tables stamped) + a persisted health attestation;
  atomically persists active evidence and enables write/traffic flags only when
  safe (`write_enabled:true`, `traffic_enabled:true`).

Every terminal failure — missing store URL, early dependency failure, invalid
action, failed migration, missing evidence — atomically persists a non-empty
redacted receipt through the same fail-closed path.

## Rollback

The prior release and image remain referenced for rollback:

- Prior backend image: `sha256:735826d6e8abdb945c8f3ff43d9818b5eb82a5c32c8a4266c74514f7d8178d9b` (tag `20260904-greenfield-lifecycle`).
- Prior image `sha256:602e341b…` (tag `20260904-greenfield-preflight`) and `sha256:4bc883d…`.

To roll back, restore the prior release dir (`20260904-greenfield-lifecycle-735826d-c91ce7a`)
and repoint `plan.json` `backend_digest` + `config/production.env` `BACKEND_IMAGE_DIGEST`
to the prior digest. No public traffic is enabled by this release: `state` remains
`preflight` and activation is a separate, named-human Phase 4 gate.

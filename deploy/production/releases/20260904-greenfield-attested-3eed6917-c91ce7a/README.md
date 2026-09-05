# Release 20260904-greenfield-attested-3eed6917

This immutable greenfield VPS release replaces the rejected backend image
`sha256:9035ac8f...` with a no-cache build from the current corrected backend
source. Before release creation, the exact image executed the real
`initialize --store identity` dispatch without database URLs. It returned the
expected fail-closed `missing_identity_url` receipt, proving `initialize` is
accepted rather than rejected as an unexpected argument.

## Images

| Field | Value |
|---|---|
| Backend repository:tag | `biohack/sam-backend:20260904-greenfield-attested-115311` |
| Backend immutable Docker image ID/digest | `sha256:3eed691771ccaf6a4b86e250c5da94f3de71324c7118dc0a44127d9e74d18944` |
| Frontend immutable digest | `sha256:c91ce7a0a2305cdaf2d1294b4af0b7c532ecaff6f196c2c3cb457c217d560855` |

`plan.json`, `compose.yml`, `control-manifest.schema.json`, and this document
are all covered by `SHA256SUMS`. The plan stays at `preflight`; only the
runtime lifecycle gates may move the effective state forward.

## Lifecycle

- `preflight` validates the sealed plan without database writes or traffic.
- `verify-empty` checks both scoped stores are empty.
- `initialize` runs scoped migrations only after the actual prior gates pass.
- `activate` requires initialized evidence and a persisted health attestation.

The prior releases, receipts, and volumes are retained. On a failed new runtime
gate, remove only containers and networks created for this release.

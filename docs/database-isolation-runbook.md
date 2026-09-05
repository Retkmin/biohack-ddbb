# Database Isolation Runbook — Greenfield VPS Deployment

Operational runbook for the first greenfield VPS deployment
(`database-isolation-vps-deployment`). It documents the fail-closed greenfield
sequence — immutable plan preflight, empty-store verification, empty-schema
initialization, health gates, Caddy DNS/TLS activation, and HTTPS smoke — plus
the named human approvals, prerequisite attestations, redaction, and retention
rules. All operations are credential-free, dry-run-first, and checksummed.

> Scope boundary: this runbook separates LOCAL PREPARATION (Phases 1–3, run
> locally and credential-free) from RUNTIME APPROVAL (Phase 4, executed only on
> the authorized VPS by a named human after an explicit go/no-go). No
> deployment, schema initialization, traffic change, or credential handling is
> performed by reading this runbook alone.

## 1. Greenfield deployment sequence

The first VPS release is greenfield: the target has no legacy Biohack stack and
no legacy production data, so there is no migration, backfill, reconciliation,
cutover, or rollback. The sequence is:

1. **Preflight** — validate the immutable deployment plan, protected
   configuration, release digests, DNS names, TLS readiness, capacity limits,
   and retention window against the named approvals. Any mismatch blocks before
   any write.
2. **Empty-store verification** — confirm both the identity and domain
   PostgreSQL stores are empty. A non-empty store fails closed and is never
   imported, backfilled, or routed.
3. **Empty-schema initialization** — initialize only empty scoped schemas after
   the initialization go/no-go passes.
4. **Health gates** — verify the required service health internally before any
   public exposure.
5. **DNS/TLS + Caddy activation** — Caddy is the sole 80/443 entrypoint and owns
   DNS/TLS termination; traffic is enabled only in the `active` state.
6. **HTTPS smoke + acceptance** — run the approved user smoke journey and record
   the acceptance go/no-go before traffic enablement.

Failure at any gate disables traffic, fences writers, and retains redacted
diagnostics and receipts for the approved retention window.

## 2. Deployment plan (control manifest)

The deployment is governed by a single, checksummed deployment plan
(`deploy/production/control-manifest.schema.json`) that is the configuration
authority for the greenfield release. The backend adapter validates it
fail-closed before any preflight/initialization/activation decision; no runtime
write happens without a validated plan and its named approvals.

The plan declares, all credential-free:

- `plan_sha256` — the immutable plan checksum;
- `environment` — always `vps-greenfield`;
- `backend_digest` / `frontend_digest` — versioned, immutable release digests;
- `dns_names` — the approved public DNS names;
- `approvals` — named preflight/initialization/activation go/no-go approvals;
- `protected_config_attestation` — opaque attestation of the owner-only
  protected environment source (never a credential);
- `tls_readiness`, `capacity_limits` — attestation objects;
- `retention_window` — the diagnostic-retention window in seconds;
- `state` — `preflight | initialized | healthy | active | blocked`;
- `receipt_ids` — retained redacted receipts this plan depends on;
- `residual_risk_recorded` — the same-host administrative residual risk.

The plan checksum is immutable and deterministic; a changed plan changes the
decision receipt's `plan_checksum`.

## 3. Prerequisite attestations

Before any runtime write, the plan must attest every prerequisite:

| Prerequisite | Attestation field |
|---|---|
| Authorized VPS access + protected configuration | `protected_config_attestation` |
| Capacity limits | `capacity_limits.attested` |
| TLS readiness + DNS/domain control | `tls_readiness.attested` + `dns_names` |
| Versioned release digests | `backend_digest` / `frontend_digest` |
| Immutable plan checksum | `plan_sha256` |
| Diagnostic-retention approval | `retention_window` |
| Same-host residual risk recorded | `residual_risk_recorded` |

Missing evidence blocks; no runtime write proceeds.

## 4. Owners

| Responsibility | Owner |
|---|---|
| Protected environment source + plan publication | Named deployment operator |
| Preflight go/no-go | Named preflight approver |
| Initialization go/no-go | Named initialization approver |
| Activation / acceptance go/no-go | Named activation approver |

Owner identities are recorded in the plan `approver` fields as opaque
principals (role/account name) — never a credential or a shared secret.

## 5. Smoke journey

The approved user-facing smoke journey runs only after internal health passes
and before acceptance. It covers: authenticated HTTPS reachability of the public
endpoint, the primary read path, and one representative write/read round-trip
against the isolated domain store. Any failed step denies acceptance and keeps
traffic disabled.

## 6. Redaction and retention

Every operation emits a redacted JSON receipt containing only:

- `action`, `dry_run`, `plan_checksum`, `counts`, `blocked`;
- opaque plan/state/environment flags and counts — never email, password,
  token, URL, role, or connection value.

Retain every receipt (dry-run, preflight, empty-store, initialization,
health/smoke, activation) in the owner-only receipt directory
(e.g. `install -d -m 0700 /var/lib/sam/receipts`) for the approved
`retention_window`. Credentials exist only in the protected environment source
and MUST NOT appear in evidence.

## 7. Local preparation vs runtime approval boundary

- **Local preparation (Phases 1–3)** is run locally, credential-free, and
  produces the plan schema, the validator, the private topology, the greenfield
  shell gates, and disposable-Compose evidence. It performs no VPS access, no
  schema initialization, and no traffic change.
- **Runtime approval (Phase 4)** is a named-human gate on the VPS. It is the
  only place where the protected environment source is consumed, empty schemas
  are initialized, artifacts are deployed, and traffic is enabled — and only
  after the preflight, initialization, and activation go/no-go decisions pass.

## 8. Failure containment

On any failed prerequisite, initialization, activation, health, or smoke check:
disable public traffic, fence writers, preserve logs/diagnostics and redacted
receipts for the retention window, and remove only the failed activation per the
approved cleanup procedure. Re-enable traffic only after a fresh approval.
There is no legacy store to restore and no cutover/rollback fallback.

## 9. Out of scope for greenfield (source-driven migration tooling)

Because this first release has no source environment, the migration tooling
(`ops/load`, `ops/backfill`, `ops/reconcile`, `ops/cutover`, `ops/rollback`,
`ops/backup`, `ops/restore` and the backend migration adapters) is NOT invoked
here. It remains available only as later work if a source environment is
introduced; a greenfield deployment never imports, backfills, reconciles,
routes, or rolls back legacy data.

## Residual threats

Same-VPS instances do not protect against host-root compromise, shared
administration, deployment-secret compromise, application-memory exposure, or
wrongly scoped export/backup. The identity/domain contract is designed so
either instance can later move to an independently managed resource without
changing the contract.

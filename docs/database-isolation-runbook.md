# Database Isolation Runbook

Operational runbook for the `database-superuser-isolation` change. It covers
inventory, dry-run/apply, discrepancy repair, and restore evidence for the
identity/domain store split. All operations are credential-free, dry-run-first,
idempotent, and checksummed.

> Scope boundary: this runbook documents operations only. No deployment,
> cutover, data movement, or credential change is performed by following it.
> The cutover/rollback controls are implemented in Phase 4.2 (section 7); their
> execution and final verification remain approval-gated in Phase 4.3. See
> `cutover-rollback-rehearsal.md` for the approval-gated rehearsal procedure and
> the exact execution prerequisites.

## Prerequisites

- A protected VPS-only environment source (e.g. `/etc/sam/production.env`)
  that Compose consumes. This file is never committed, imaged, or logged.
- `docker compose` available; the `ops/*` wrappers run from `biohack-ddbb`.
- Owner-only receipt directory, e.g. `install -d -m 0700 /var/lib/sam/receipts`.

## Invariants

1. **Credential-free wrappers.** No wrapper accepts or emits a URL, user,
   password, token, `PGPASSWORD`, or secret-file value. Credential-like
   arguments are rejected before any Compose call.
2. **Dry-run first.** The default mode is `--dry-run`; a write happens only
   with an explicit `--apply`.
3. **Idempotent and checksummed.** Backfill inserts only accepted rows and
   never overwrites a checksum mismatch; every operation emits a deterministic
   `plan_checksum`.
4. **No backend SQL in this repository.** The wrappers invoke the versioned
   backend adapter image through Compose; no SQL or domain logic is copied.
5. **No cross-store join.** Identity and domain stores are queried
   independently; reconciliation compares opaque IDs in the backend.

## 1. Inventory (`ops/load`)

Produces a read-only inventory of the source identity store's profile rows
without writing to any store.

```bash
ops/load --store identity --receipt-dir /var/lib/sam/receipts
```

Interpret the receipt: `counts.inserted` are rows that would be loaded,
`counts.unchanged` are already accepted, and `blocked` is true only if a
checksum mismatch exists.

## 2. Dry-run / apply (`ops/backfill`)

Always dry-run first, then apply the same plan.

```bash
# Plan only — performs no write.
ops/backfill --dry-run --store identity --receipt-dir /var/lib/sam/receipts

# Apply the idempotent, checksummed backfill.
ops/backfill --apply --store identity --receipt-dir /var/lib/sam/receipts
```

Re-running `--apply` over accepted rows changes nothing (idempotent). A
mismatched row is reported, never overwritten, and blocks cutover.

## 3. Reconciliation (`ops/reconcile`)

Detects missing, duplicate, and checksum-mismatched opaque IDs plus a
record-count mismatch. A blocked reconciliation exits non-zero.

```bash
ops/reconcile --dry-run --store identity --receipt-dir /var/lib/sam/receipts
ops/reconcile --apply --store identity --receipt-dir /var/lib/sam/receipts
```

Exit code 0 means clean; any discrepancy returns a non-zero exit and a
`blocked: true` receipt.

## 4. Discrepancy repair

When reconciliation reports a discrepancy:

1. Review the redacted receipt (opaque IDs + counts only).
2. Repair forward in the source of truth; never hand-edit checksums and never
   perform a destructive migration reversal.
3. Re-run `ops/reconcile --apply` until it exits 0.

A dangling reference (a domain record pointing at an unavailable identity) is
reported by ID and repaired through the defined lifecycle, never by a
cross-store join.

## 5. Backup and restore evidence (`ops/backup`, `ops/restore`)

Backups are per-store and network-scoped; a domain backup never traverses the
identity path and never contains identity records.

```bash
# Backup each store independently.
ops/backup --apply --store identity
ops/backup --apply --store domain
```

Restore is approval-gated and never runs automatically. When an approved
restore drill is required:

```bash
ops/restore --dry-run --store domain --receipt-dir /var/lib/sam/receipts
ops/restore --apply --store domain
```

Record the restore target, the dump file identity, and the redacted receipt as
evidence. A domain restore must contain domain data only and use no identity
backup credential.

## 6. Receipts and evidence

Every operation emits a redacted JSON receipt to stdout and, with
`--receipt-dir`, writes `receipt.json`. Retain receipts in the owner-only
directory. Receipts contain only:

- `action`, `dry_run`, `plan_checksum`, `counts`, `blocked`
- opaque IDs, counts, and status — never email, password, token, URL, or role.

## 7. Cutover and rollback controls (`ops/cutover`, `ops/rollback`)

The cutover and rollback controls are credential-free, dry-run-first, and
approval-gated. They delegate to the backend adapter through the
`store-operation` Compose service and never accept or emit a database
credential.

```bash
# Plan only — performs no write and never invokes the backend.
ops/cutover --dry-run --store identity --receipt-dir /var/lib/sam/receipts
ops/rollback --dry-run --store identity --receipt-dir /var/lib/sam/receipts
```

`--apply` runs the decision and exits non-zero when it is blocked:

- Cutover is blocked unless reconciliation is clean and the maintenance window
  is bounded (`authority: isolated`, `bounded: true`,
  `new_store_writes_enabled: true` only when it proceeds).
- Rollback is blocked when reconciliation is unresolved or the legacy copy is
  missing. It always routes to `authority: legacy`, disables new-store writes
  (`new_store_writes_enabled: false`), preserves the legacy copy
  (`legacy_copy_preserved: true`), and is never destructive
  (`destructive: false`).

Execution of `--apply` is approval-gated and runs only inside a declared,
bounded maintenance window after a clean `ops/reconcile --apply` and a passing
restore drill. It is not part of the daily operations here; see
`cutover-rollback-rehearsal.md` for the rehearsal procedure and the exact
execution prerequisites.

## Residual threats

Same-VPS instances do not protect against host-root compromise, shared
administration, deployment-secret compromise, application-memory exposure, or
wrongly scoped export/backup. The identity/domain contract is designed so
either instance can later move to an independently managed resource without
changing the contract.

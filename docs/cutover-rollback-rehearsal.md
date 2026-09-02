# Cutover and Rollback Rehearsal

Preparatory, approval-gated procedure for the `database-superuser-isolation`
Phase 4 cutover/rollback boundary. This document records the rehearsal steps,
success criteria, evidence, and approval prerequisites. It performs nothing by
itself: no deployment, no cutover, no restore, no credential change, and no data
movement.

> **Read me first.** The cutover/rollback controls and final runbooks are
> implemented (task 4.2). The deployment/cutover itself still runs in task 4.3
> only after explicit operator approval and the prerequisites below. Until
> then, this document is the rehearsal contract operators rehearse against — on
> a disposable stack, never on the VPS.

## Purpose

Prove, without touching production, that the staged cutover and the
non-destructive rollback are rehearsable and would not lose data. This directly
serves the proposal success criterion:

> Staged migration and configuration rollback are rehearsable without data
> loss.

## Scope boundary

- **In scope**: dry-run rehearsal of cutover and rollback, evidence recording,
  and the approval checklist.
- **Out of scope**: executing cutover, executing restore, changing credentials,
  moving data, disabling writes, or deleting any copy. Those are Phase 4 task
  4.3 and remain approval-gated.

## Preconditions (rehearsal environment)

A rehearsal runs against the disposable two-PostgreSQL stack described in the
design's testing strategy — never against the VPS. Before any rehearsal:

1. The backend adapter image is built from the versioned `biohack-back` source.
2. A protected, non-committed environment source is available (never in a
   repository, image, shell history, or log).
3. An owner-only receipt directory exists, e.g.
   `install -d -m 0700 /var/lib/sam/receipts`.
4. A named, bounded maintenance window is declared for the eventual cutover.

## Rehearsal success criteria

| # | Criterion | How it is proven |
|---|---|---|
| C1 | Clean reconciliation before cutover | `ops/reconcile --apply` exits 0, `blocked: false` |
| C2 | Per-store restore drill passes | Domain restore contains domain data only; no identity backup credential used |
| C3 | Cutover is bounded and blocked on discrepancy | `ops/cutover --dry-run` reports a bounded window and blocks on any mismatch |
| C4 | Rollback returns routing to legacy | `ops/rollback --dry-run` reports `authority: legacy` |
| C5 | Rollback disables new-store writes | `ops/rollback --dry-run` reports `new_store_writes_enabled: false` |
| C6 | Legacy copy is preserved | Rollback reports `legacy_copy_preserved: true`; no legacy copy is deleted |
| C7 | Rollback is non-destructive | Rollback reports `destructive: false`; no Alembic downgrade is ever run |

## Pre-flight (rehearsal)

Run these dry-run-only steps in order and retain each redacted receipt.

1. **Inventory** — confirm the source is understood without writing.

   ```bash
   ops/load --store identity --receipt-dir /var/lib/sam/receipts
   ```

2. **Backfill dry-run** — confirm the plan is idempotent and checksummed.

   ```bash
   ops/backfill --dry-run --store identity --receipt-dir /var/lib/sam/receipts
   ```

3. **Reconcile** — a clean result is a hard gate for any cutover rehearsal.

   ```bash
   ops/reconcile --apply --store identity --receipt-dir /var/lib/sam/receipts
   ```

   Exit code 0 and `blocked: false` are required. Any discrepancy blocks the
   rehearsal (C1).

4. **Restore drill** — prove a domain backup restores domain data only and uses
   no identity backup credential (C2). Restore is approval-gated; the drill runs
   on the disposable stack and records the restore target and dump identity.

## Cutover rehearsal (dry-run only)

After a clean reconciliation and restore drill:

```bash
ops/cutover --dry-run --store identity --receipt-dir /var/lib/sam/receipts
```

Verify the receipt reports a **bounded** window and `blocked: false` only when
the reconciliation is clean (C3). A `blocked: true` receipt is the expected
outcome when any discrepancy exists and must block the rehearsal, never be
waived.

## Rollback rehearsal (dry-run only)

```bash
ops/rollback --dry-run --store identity --receipt-dir /var/lib/sam/receipts
```

Verify the receipt reports:

- `authority: legacy` — routing returns to the legacy identity authority (C4);
- `new_store_writes_enabled: false` — new-store writes are disabled (C5);
- `legacy_copy_preserved: true` — the legacy copy is retained (C6);
- `destructive: false` — no destructive migration reversal (C7).

A rollback that reports `blocked: true` (e.g. the legacy copy is missing or
reconciliation is unresolved) is the fail-closed behavior and must be treated as
a rehearsal failure to fix forward, never by deleting a copy or running a
downgrade.

## Evidence to record

- Redacted JSON receipts for every step above, retained in the owner-only
  receipt directory. Receipts carry action, opaque IDs, counts, status, and
  checksums only — never a URL, user, password, token, or secret-file value.
- The declared bounded maintenance window and its duration.
- The restore target, dump identity, and the domain-only-content confirmation.

## Approval prerequisites (exact gates)

The following must be true before task 4.3 (execution) proceeds. The controls
(4.2) are already implemented; the remaining gates below are for execution.
None is satisfied by this document:

1. **Operator approval** — explicit, recorded approval to run the
   deployment/cutover (4.3).
2. **Maintenance window** — a named, bounded window is declared and accepted.
3. **Clean reconciliation** — `ops/reconcile --apply` exits 0 on the real
   stores before any cutover.
4. **Restore drill pass** — a domain restore is proven domain-only and a
   rollback drill is rehearsed without data loss.
5. **Residual-threat acceptance** — the same-VPS residual threats and the future
   independently-managed-resource path (below) are documented and accepted.

## Residual threats and future path

Same-VPS instances do not protect against host-root compromise, shared
administration, deployment-secret compromise, application-memory exposure, or
wrongly scoped export/backup. The identity/domain contract is designed so either
instance can later move to an independently managed resource without changing
the contract. These limitations must be re-acknowledged at approval time.

## Relationship to the operational runbook

This document rehearses the cutover/rollback boundary. The day-to-day
inventory/backfill/reconcile/backup/restore procedure lives in
`database-isolation-runbook.md`; the two are complementary and must not be
executed in isolation from each other.

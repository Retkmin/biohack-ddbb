# Private VPS Operator Access Preparation

This scaffold is intentionally nonfunctional until the infrastructure owner
provisions a private operator route. It does not create a tunnel, contact a
VPS, expose PostgreSQL, embed credentials, or select a production target by
default.

## Required Provisioning

1. Copy `ops/operator-access.template` outside Git and set one explicit,
   approved `OPERATOR_TARGET`; `UNSET` is a hard stop.
2. Provision a named, MFA-protected workstation identity and a bastion or
   equivalent private access route. The route must terminate PostgreSQL only on
   `127.0.0.1` at the workstation; never publish a database host port or add a
   public PostgreSQL mapping.
3. Provision a separate least-privilege operator principal for each store. It
   must be time-bound, auditable, scoped to the approved operation, and cannot
   be a superuser, owner, application runtime role, or shared deployment login.
4. Keep connection material in the approved workstation secret manager or
   protected platform configuration. Do not add it to this template, shell
   history, repositories, process arguments, receipts, or tickets.
5. Configure audit collection, pre-operation verified backups for both stores,
   a restore proof, and a named rollback owner before requesting an apply.

## Controlled Operation Contract

Every workstation operation must select `identity` or `domain` explicitly and
begin with the existing credential-free wrapper dry-run. Capture its redacted
receipt, have a second operator confirm the target, store, operation checksum,
backup proof, and rollback point, then use a separately approved platform route
to execute the apply. A dry-run never authorizes a write.

No generic `ssh -L` command is documented here deliberately: host names,
identity files, database endpoints, and access policy are provisioning data.
Once a route is approved, the platform owner must publish a reviewed procedure
that binds only to `127.0.0.1`, names the target, expires the access, and records
the audit session. If any prerequisite, confirmation, backup proof, or receipt
is missing, stop without connecting.

## Rollback Boundary

Do not attempt an automatic schema downgrade or data rollback. Disable the
approved operator route, stop the affected write procedure, preserve receipts,
and restore only from the backup that passed the pre-operation restore proof
under a new explicit incident/change approval.

## exploration: single-postgres-local-topology

### current state
`docker-compose.db.yml` currently exposes two PostgreSQL containers: `db`/`sam_db` on host port 5432 and `users_db` on host port 5433, plus Redis. This contradicts the backend migration contract: `biohack-back` resolves Alembic through its application `DATABASE_URL`, and its migration-ownership documentation identifies backend Alembic as the authoritative owner. The database repository's Alembic metadata is also explicitly scoped to SAM-domain tables and still describes the users schema as separate.

The local documentation is inconsistent. `README.md` invokes a missing root `docker-compose.yml` and claims that the command starts the API and worker. `docs/setup_guide.md` explicitly documents two independent databases. `install_docker.ps1` points at the database compose file but uses the legacy `docker-compose` executable. The tracked ad hoc scripts contain hard-coded `users_db`, host port 5433, split SAM/users engines, direct schema creation, and destructive/reset operations; they are not a supported Alembic path.

Read-only validation of the current file succeeds with `docker compose -f docker-compose.db.yml config`, but Compose emits the obsolete `version` warning and renders both PostgreSQL services and both data volumes.

### affected areas
- `docker-compose.db.yml` — make the only documented local data topology one PostgreSQL service (`sam_db` on 5432) plus Redis; remove the second service, port, volume, and obsolete `version` key.
- `README.md` — replace the missing full-stack Compose claim with the database-compose command, describe the actual services, and point migrations/application startup to the backend repository.
- `docs/setup_guide.md` — document one PostgreSQL instance and the backend-owned Alembic/application sequence; remove the two-database claim.
- `install_docker.ps1` — use `docker compose -f docker-compose.db.yml up -d` consistently.
- `scripts/legacy/README.md` (new) — document quarantine, non-support, historical 5433/`users_db` assumptions, and the migration path for any data that must be preserved.
- `audit_dario.py`, `audit_user.py`, `create_session_table_migration.py`, `find_dario.py`, `find_user.py`, `fix_email.py`, `import_excel.py`, `migrate_dario.py`, `reset_seed_users.py`, `seed_dario.py`, `seed_high_fidelity.py`, `seed_users.py`, `verify_alembic_status.py`, `list_tables.py`, `inspect_legacy_tables.py` — move under `scripts/legacy/`; these encode the retired split topology or the retired 5433 endpoint.
- `drop.py`, `migrate_db.py`, `reset_db.py` — move under `scripts/legacy/` as ad hoc/destructive or non-Alembic schema paths, and explicitly warn against using them for the canonical local database.
- `docs/architecture_decisions.md` — add an ADR recording single PostgreSQL local topology and backend Alembic ownership, including the legacy-script quarantine.
- `alembic/env.py`, `alembic.ini`, `alembic/README` — review for stale ownership declarations; do not make this repository's Alembic history a competing operational migration path.

### approaches
1. **canonical compose plus quarantine** — reduce `docker-compose.db.yml` to `db` and `redis`, correct the two guides and installer, and move all split-topology/ad hoc scripts to `scripts/legacy/` with a clear non-supported notice.
   - pros: preserves historical material for audit/reference; establishes one unambiguous local topology; aligns documentation and operations with backend Alembic ownership.
   - cons: callers of old scripts must migrate to backend-owned commands; moving files changes their paths.
   - effort: medium

2. **delete legacy scripts and only correct compose/docs** — remove obsolete scripts and leave the canonical files at their current paths.
   - pros: smaller tree and less maintenance surface.
   - cons: loses historical recovery context; stale callers fail without an explicit quarantine explanation; does not safely distinguish destructive scripts from supported tooling.
   - effort: low

### recommendation
Use canonical compose plus quarantine. Keep `docker-compose.db.yml` as the sole documented local data topology, with one PostgreSQL service (`sam_db`, host port 5432) and Redis. Update README/setup/installer claims, add the ADR and legacy-runbook, and move split-database/ad hoc scripts under `scripts/legacy/` without silently rewriting them. The runbook should direct schema changes and migration verification to `biohack-back` Alembic, and state that any existing `users_db` data requires an explicit migration decision before removal of old volumes.

### risks
- Existing local `postgres_users_data` contains data that will not be migrated by deleting the service; the implementation must document preservation/export responsibility before operators remove the volume.
- Legacy scripts embed credentials and destructive SQL; quarantine must prevent them from being mistaken for supported commands and should not execute them during validation.
- The repository currently has pre-existing Git changes (including a deleted `docker-compose.yml`, modified `alembic/env.py`, and untracked SDD/bootstrap files); implementation and verification must preserve unrelated worktree state.
- `docker compose config` currently passes with an obsolete-version warning; post-change validation should require a successful config render without that warning and confirm exactly one PostgreSQL service/volume.

### ready for proposal
yes — prepare a proposal limited to this repository's local topology, documentation, ADR, and legacy-script quarantine. Require an explicit data-preservation decision for any existing `users_db` volume before applying destructive cleanup; no `.env` inspection is needed.

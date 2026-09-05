# Local PostgreSQL Development Replica

Daily development uses two persistent, local PostgreSQL 15 stores: identity on
`127.0.0.1:54321` and domain on `127.0.0.1:54322`. They are a local replica of
the production topology, not production and not the disposable
`docker-compose.local-test.yml` test harness. Both ports bind to loopback only.

## Start

From `repos/biohack-ddbb`, create an ignored local configuration from the
tracked non-secret template, then start and validate the stores:

```powershell
Copy-Item config/local-development-postgres.template config/local-development-postgres.env
docker compose --env-file config/local-development-postgres.env -f docker-compose.local-development.yml up -d
docker compose --env-file config/local-development-postgres.env -f docker-compose.local-development.yml ps
```

From `repos/biohack-back`, set the local scoped URLs in the current PowerShell
only, apply both forward-only migration histories, and start the backend in
development mode:

```powershell
$env:ENVIRONMENT = "development"
$env:IDENTITY_DATABASE_URL = "postgresql+asyncpg://biohack_identity_dev:biohack_identity_dev_password@127.0.0.1:54321/biohack_identity_dev"
$env:DOMAIN_DATABASE_URL = "postgresql+asyncpg://biohack_domain_dev:biohack_domain_dev_password@127.0.0.1:54322/biohack_domain_dev"
$env:IDENTITY_DATABASE_RUNTIME_ROLE = "sam_runtime"
$env:DOMAIN_DATABASE_RUNTIME_ROLE = "sam_runtime"
alembic -n identity upgrade head
alembic -n domain upgrade head
.venv\Scripts\python.exe -m uvicorn --factory app.main:create_app --host 127.0.0.1 --port 8000
```

The migration histories create the complete active repository schema for each
store and grant the local `sam_runtime` NOLOGIN role the required per-store
access. The domain history includes profile/onboarding, daily-log, meal,
workout, recipe, history, AI-intake, planning/calendar, weekly-plan lifecycle,
and reconciliation tables. It also grants execute access to the restricted
role for the certification and reconciliation functions. Do not start the
scoped backend before both commands report success. The backend connects
through the local owner logins and enters that restricted role.
`ENVIRONMENT=production` is neither required nor permitted as a local shortcut.

## Stop And Reset

Stop while retaining the local data:

```powershell
docker compose --env-file config/local-development-postgres.env -f docker-compose.local-development.yml down
```

Reset only the local replica after explicitly discarding its data:

```powershell
docker compose --env-file config/local-development-postgres.env -f docker-compose.local-development.yml down --volumes
```

The reset command removes only `biohack-local-development` volumes. It does not
touch the local test harness, production Compose files, VPS resources, or any
remote database.

## Domain Migration Recovery

Store B migrations are forward-only. Before applying a domain migration to a
persistent local store, take a restorable backup. This procedure keeps the
running store intact and restores only into a separate local recovery database;
it is not a substitute for `down --volumes`.

From `repos/biohack-ddbb`:

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
$compose = @("--env-file", "config/local-development-postgres.env", "-f", "docker-compose.local-development.yml")
$domainContainer = docker compose @compose ps -q domain-postgres
docker compose @compose exec -T domain-postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --file /tmp/domain-before-migration.dump'
docker cp "$($domainContainer):/tmp/domain-before-migration.dump" .\backups\domain-before-migration.dump
docker compose @compose exec -T domain-postgres pg_restore --list /tmp/domain-before-migration.dump
```

Keep the resulting dump outside source control. To verify it without replacing
the persistent domain database, copy it back into the container and restore it
to a separate database:

```powershell
docker cp .\backups\domain-before-migration.dump "$($domainContainer):/tmp/domain-before-migration.dump"
docker compose @compose exec -T domain-postgres sh -c 'dropdb -U "$POSTGRES_USER" --if-exists biohack_domain_recovery; createdb -U "$POSTGRES_USER" biohack_domain_recovery; pg_restore -U "$POSTGRES_USER" -d biohack_domain_recovery --clean --if-exists /tmp/domain-before-migration.dump'
docker compose @compose exec -T domain-postgres psql -U "$POSTGRES_USER" -d biohack_domain_recovery -c 'SELECT version_num FROM alembic_version'
```

If `alembic -n domain upgrade head` stops with SQLSTATE `B2003`, revision 0005
found duplicate non-null `ai_intake_controls.reservation_token` values. The
upgrade transaction changes neither rows nor its Alembic revision. Do not pick
or regenerate a token generically: list the collisions, preserve the backup,
and resolve each reservation with the responsible business owner before retrying.

```powershell
docker compose @compose exec -T domain-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'SELECT reservation_token, COUNT(*) FROM ai_intake_controls WHERE reservation_token IS NOT NULL GROUP BY reservation_token HAVING COUNT(*) > 1'
```

After the reviewed correction, rerun `alembic -n domain upgrade head`. Remove
the separate recovery database only after the backup and successful migration
have been verified; it never requires deleting the persistent Compose volumes.

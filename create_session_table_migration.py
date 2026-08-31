"""
Generate B1b session table migration based on approved exploration findings.

Session table schema (from B1b exploration):
- session_id (PK)
- family_id (rotation family identifier)
- rotation_id (generation within family)
- user_id (logical FK to users_db)
- token_hash (HMAC/hash of the token, never raw)
- purpose (access | refresh)
- created_at
- expires_at
- last_seen_at
- revoked_at
- replaced_by (session_id of replacement)
- revocation_reason

Indexes:
- Unique token_hash
- (user_id, revoked_at, expires_at) for active session lookup
- (expires_at, revoked_at) for cleanup
- Unique (family_id, rotation_id) for replay detection
"""

import subprocess
import os

# Set environment variables
env = os.environ.copy()
env["PYTHONPATH"] = r"D:\Trabajo\app-biohack\repos\biohack-back"
env["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/sam_db"
env["ENVIRONMENT"] = "development"

# Generate migration
result = subprocess.run(
    ["python", "-m", "alembic", "revision", "-m", "add_session_table"],
    cwd=r"D:\Trabajo\app-biohack\repos\biohack-ddbb",
    env=env,
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

print("\nMigration file created. You'll need to edit it to add the session table schema.")

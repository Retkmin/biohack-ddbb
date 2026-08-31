from sqlalchemy import create_engine, text

engine = create_engine("postgresql://postgres:postgres@127.0.0.1:5433/sam_db")
conn = engine.connect()

result = conn.execute(text("SELECT version_num FROM alembic_version"))
version = result.scalar()

print(f"Current Alembic version: {version}")
print(f"Expected baseline: 503a05e14a6e")
print(f"Status: {'✓ MATCH' if version == '503a05e14a6e' else '✗ MISMATCH'}")

conn.close()

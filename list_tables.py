from sqlalchemy import create_engine, text

engine = create_engine("postgresql://postgres:postgres@127.0.0.1:5433/sam_db")
conn = engine.connect()
result = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"))
print("Current tables in sam_db:")
for row in result:
    print(f"  - {row[0]}")
conn.close()

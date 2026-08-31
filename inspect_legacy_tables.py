from sqlalchemy import create_engine, text

engine = create_engine("postgresql://postgres:postgres@127.0.0.1:5433/sam_db")
conn = engine.connect()

legacy_tables = ["week_plans", "workout_sessions", "workout_exercises", "workout_sets"]

print("=" * 70)
print("INSPECTING LEGACY TABLES IN sam_db")
print("=" * 70)

for table in legacy_tables:
    # Get row count
    count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
    count = count_result.scalar()
    
    print(f"\n[{table}]")
    print(f"  Total rows: {count}")
    
    if count > 0:
        # Show sample rows (first 3)
        sample_result = conn.execute(text(f"SELECT * FROM {table} LIMIT 3"))
        columns = sample_result.keys()
        print(f"  Columns: {', '.join(columns)}")
        print(f"  Sample rows:")
        for row in sample_result:
            print(f"    {dict(row)}")
    else:
        print(f"  Status: EMPTY")

print("\n" + "=" * 70)
print("INSPECTION COMPLETE")
print("=" * 70)

conn.close()

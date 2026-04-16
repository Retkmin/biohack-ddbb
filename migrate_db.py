import asyncio
from sqlalchemy import text
from app.infrastructure.database.connection import engine

async def run():
    print("Running migration: Adding refresh_token to users...")
    try:
        async with engine.begin() as conn:
            # PostgreSQL syntax: ADD COLUMN IF NOT EXISTS
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS refresh_token VARCHAR(512)"))
        print("Migration completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    asyncio.run(run())

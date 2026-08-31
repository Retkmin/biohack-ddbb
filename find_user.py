import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def find():
    engine = create_async_engine('postgresql+asyncpg://postgres:postgres@localhost:5433/users_db')
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT user_id, email FROM users WHERE email = 'darioalejandre@gmail.com'"))
        for row in res:
            print(f"FOUND: ID={row[0]} | Email={row[1]}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(find())

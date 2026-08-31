import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def fix():
    engine = create_async_engine('postgresql+asyncpg://postgres:postgres@localhost:5433/users_db')
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE users SET email = 'darioalejandre@gmail.com' WHERE user_id = 'usr_dario01'"))
    print("Email updated successfully.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix())

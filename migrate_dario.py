import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def migrate():
    # 1. Update Sam DB (Daily Logs, Recipes)
    sam_engine = create_async_engine('postgresql+asyncpg://postgres:postgres@localhost:5433/sam_db')
    async with sam_engine.begin() as conn:
        # Move logs
        await conn.execute(text("UPDATE daily_logs SET user_id = 'usr_4f2bf9993862' WHERE user_id = 'usr_dario01'"))
        # Move recipes
        await conn.execute(text("UPDATE recipes SET user_id = 'usr_4f2bf9993862' WHERE user_id = 'usr_dario01'"))
    print("Sam DB Migration complete.")

    # 2. Cleanup Users DB
    users_engine = create_async_engine('postgresql+asyncpg://postgres:postgres@localhost:5433/users_db')
    async with users_engine.begin() as conn_u:
        # Delete the temporary seed user if it exists
        await conn_u.execute(text("DELETE FROM users WHERE user_id = 'usr_dario01'"))
        # Update the real user's metadata to match the high-fidelity seed
        await conn_u.execute(text("""
            UPDATE users SET 
                age = 28, height = 182, sex = 'M', activity_level = 'active', 
                current_phase = 'deficit_a', current_weight = 105.5, 
                current_body_fat = 0.22, current_lbm = 82.3, current_bmr = 2150
            WHERE user_id = 'usr_4f2bf9993862'
        """))
    print("Users DB Metadata Sync complete.")

    await sam_engine.dispose()
    await users_engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())

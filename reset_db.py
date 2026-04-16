import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import get_settings
from app.infrastructure.database.models import Base
from app.infrastructure.database.seed import seed_data

async def hard_reset():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False, future=True)
    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Recreating tables...")
        await conn.run_sync(Base.metadata.create_all)
    
    print("Reseeding test users...")
    await seed_data()
    print("Database reset complete.")

if __name__ == "__main__":
    asyncio.run(hard_reset())

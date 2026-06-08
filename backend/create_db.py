import asyncio
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

async def create_db():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/postgres", isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("CREATE DATABASE ai_docs"))
        print("Database 'ai_docs' created successfully.")
    except Exception as e:
        print(f"Database creation result/error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_db())

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base


class Database:
    def __init__(self, url: str):
        if not url.startswith("sqlite+aiosqlite:"):
            raise ValueError("DATABASE_URL deve usar sqlite+aiosqlite")
        self.engine = create_async_engine(url, connect_args={"timeout": 15})

        @event.listens_for(self.engine.sync_engine, "connect")
        def configure_sqlite(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=15000")
            cursor.close()

        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self):
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self):
        await self.engine.dispose()


async def get_session(request: Request):
    async with request.app.state.database.sessions() as session:
        yield session


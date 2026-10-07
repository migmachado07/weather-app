from fastapi import Request
from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import Base


class Database:
    def __init__(self, url: str):
        parsed = make_url(url)
        if parsed.drivername in {"postgres", "postgresql", "postgresql+psycopg"}:
            parsed = parsed.set(drivername="postgresql+psycopg")
            # O pool remoto do Neon gerencia as conexoes entre instancias Vercel.
            self.engine = create_async_engine(
                parsed, poolclass=NullPool,
                connect_args={"connect_timeout": 15, "prepare_threshold": None},
            )
        elif parsed.drivername == "sqlite+aiosqlite":
            self.engine = create_async_engine(parsed, connect_args={"timeout": 15})

            @event.listens_for(self.engine.sync_engine, "connect")
            def configure_sqlite(connection, _):
                cursor = connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=15000")
                cursor.close()
        else:
            raise ValueError("DATABASE_URL deve usar SQLite ou PostgreSQL")

        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self):
        async with self.engine.begin() as connection:
            if self.engine.dialect.name == "postgresql":
                # Serializa a criacao inicial das tabelas entre instancias.
                # A trava e liberada automaticamente no fim da transacao.
                await connection.execute(text("SELECT pg_advisory_xact_lock(731928451)"))
            await connection.run_sync(Base.metadata.create_all)

    async def close(self):
        await self.engine.dispose()


async def get_session(request: Request):
    async with request.app.state.database.sessions() as session:
        yield session

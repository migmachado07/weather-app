from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Favorite, SearchHistory
from app.schemas import City


async def list_favorites(session: AsyncSession):
    return (await session.scalars(select(Favorite).order_by(Favorite.id.desc()))).all()


async def add_favorite(session: AsyncSession, city: City):
    insert = postgres_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    values = city.model_dump()
    values.update(lat=round(city.lat, 4), lon=round(city.lon, 4))
    # Restrição única + ON CONFLICT evita duplicatas mesmo em requisições concorrentes.
    await session.execute(insert(Favorite).values(**values).on_conflict_do_nothing(
        index_elements=["lat", "lon"]
    ))
    await session.commit()
    return await session.scalar(select(Favorite).where(
        Favorite.lat == values["lat"], Favorite.lon == values["lon"]
    ))


async def remove_favorite(session: AsyncSession, favorite_id: int) -> bool:
    result = await session.execute(delete(Favorite).where(Favorite.id == favorite_id))
    await session.commit()
    return result.rowcount > 0


async def add_history(session: AsyncSession, query: str, resolved: str):
    session.add(SearchHistory(query_term=query, city_resolved=resolved))
    await session.commit()


async def list_history(session: AsyncSession):
    return (await session.scalars(select(SearchHistory).order_by(
        SearchHistory.searched_at.desc(), SearchHistory.id.desc()
    ).limit(10))).all()


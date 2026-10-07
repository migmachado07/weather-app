from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import City, WeatherResponse
from app.services import db_service

router = APIRouter(prefix="/api/v1", tags=["Clima"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/search", response_model=list[City])
async def search(request: Request, q: Annotated[str, Query(min_length=2, max_length=150)]):
    query = q.strip()
    if len(query) < 2:
        return []
    return await request.app.state.weather.search(query)


@router.get("/weather", response_model=WeatherResponse)
async def weather(
    request: Request, session: Session,
    lat: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
    lon: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
    city_name: Annotated[str, Query(max_length=150)] = "",
    state: Annotated[str, Query(max_length=150)] = "",
    country: Annotated[str, Query(max_length=100)] = "",
    query: Annotated[str, Query(max_length=200)] = "",
):
    payload = await request.app.state.weather.weather(lat, lon)
    coordinates = f"{lat:.4f}, {lon:.4f}"
    resolved = ", ".join(part.strip() for part in (city_name, state, country) if part.strip())
    # Registra consultas concluídas, incluindo hits de cache. O autocomplete
    # não polui o histórico a cada tecla. Metadados são declarados pelo cliente.
    await db_service.add_history(session, query.strip() or city_name.strip() or coordinates,
                                 resolved or coordinates)
    return payload


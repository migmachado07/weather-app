from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import City, Favorite, History
from app.services import db_service

router = APIRouter(prefix="/api/v1", tags=["Cidades salvas"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/favorites", response_model=list[Favorite])
async def favorites(session: Session):
    return await db_service.list_favorites(session)


@router.post("/favorites", response_model=Favorite)
async def add_favorite(city: City, session: Session):
    return await db_service.add_favorite(session, city)


@router.delete("/favorites/{favorite_id}", status_code=204)
async def delete_favorite(favorite_id: int, session: Session):
    if not await db_service.remove_favorite(session, favorite_id):
        raise HTTPException(status_code=404, detail="Favorito não encontrado.")
    return Response(status_code=204)


@router.get("/history", response_model=list[History])
async def history(session: Session):
    return await db_service.list_history(session)


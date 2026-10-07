from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import BASE_DIR, Settings
from app.database import Database
from app.routes import favorites, weather
from app.services.gemini_service import GeminiService
from app.services.weather_service import WeatherProviderError, WeatherService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database = Database(settings.database_url)
        gemini = GeminiService(settings)
        try:
            await database.initialize()
            async with httpx.AsyncClient(
                timeout=settings.http_timeout_seconds,
                limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            ) as http:
                application.state.database = database
                application.state.weather = WeatherService(settings, http, gemini)
                yield
        finally:
            await gemini.close()
            await database.close()

    application = FastAPI(title="Brisa · Weather API", version="1.0.0", lifespan=lifespan)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    application.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
                "base-uri 'self'; frame-ancestors 'none'"
            )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(WeatherProviderError)
    async def provider_error(_request: Request, exc: WeatherProviderError):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    application.include_router(weather.router)
    application.include_router(favorites.router)
    application.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

    @application.get("/", include_in_schema=False)
    async def index():
        return FileResponse(BASE_DIR / "templates" / "index.html")

    @application.get("/health", tags=["Operação"])
    async def health(request: Request):
        async with request.app.state.database.sessions() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}

    return application


app = create_app()

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)


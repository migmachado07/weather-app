import asyncio
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from cachetools import TTLCache
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.gemini_service import GeminiService
from app.services.weather_service import WeatherProviderError, WeatherService, normalize_hourly


def provider_payload():
    today = date(2026, 10, 6)
    dates = [(today + timedelta(days=i)).isoformat() for i in range(6)]
    return {
        "hourly": {
            "time": [f"{d}T{h:02}:00" for d in dates for h in range(24)],
            "temperature_2m": [24.5] * 144,
            "precipitation_probability": [10 if h < 14 else 80 for _ in dates for h in range(24)],
            "precipitation": [0 if h < 14 else 1.5 for _ in dates for h in range(24)],
            "weather_code": [2] * 144,
            "is_day": [int(6 <= h < 18) for _ in dates for h in range(24)],
        },
        "latitude": -23.55, "longitude": -46.63, "timezone": "America/Sao_Paulo",
        "current": {"time": f"{today}T10:00", "temperature_2m": 24.5,
                    "apparent_temperature": 25, "relative_humidity_2m": 65,
                    "wind_speed_10m": 12, "precipitation": 0,
                    "weather_code": 2, "is_day": 1},
        "daily": {"time": dates, "weather_code": [2, 3, 61, 0, 2, 3],
                  "temperature_2m_max": [28] * 6, "temperature_2m_min": [18] * 6,
                  "precipitation_probability_max": [60] * 6,
                  "precipitation_sum": [3] * 6,
                  "sunrise": [f"{d}T05:40" for d in dates],
                  "sunset": [f"{d}T18:10" for d in dates]},
    }


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, gemini_api_key="", trusted_hosts=["testserver"],
                    database_url=f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        app.state.weather._get = AsyncMock(return_value=provider_payload())
        yield client


CITY = {"city_name": "São Paulo", "state": "São Paulo", "country": "Brasil",
        "lat": -23.5505, "lon": -46.6333}


def test_weather_cache_and_history(client):
    params = {**CITY, "query": "Sao Paulo"}
    first = client.get("/api/v1/weather", params=params)
    second = client.get("/api/v1/weather", params=params)
    assert first.status_code == second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert first.json()["ai_source"] == "fallback"
    assert "guarda-chuva" in first.json()["ai_insight"]
    assert len(first.json()["weather_data"]["forecast"]) == 5
    assert first.json()["weather_data"]["forecast"][0]["date"] == "2026-10-07"
    assert client.app.state.weather._get.await_count == 1
    history = client.get("/api/v1/history").json()
    assert len(history) == 2
    assert history[0]["query_term"] == "Sao Paulo"
    assert history[0]["city_resolved"] == "São Paulo, São Paulo, Brasil"


def test_favorites_idempotence_validation_and_persistence(client, settings):
    saved = client.post("/api/v1/favorites", json=CITY)
    assert saved.status_code == 200
    duplicate = client.post("/api/v1/favorites", json=CITY)
    assert saved.json()["id"] == duplicate.json()["id"]
    assert len(client.get("/api/v1/favorites").json()) == 1
    # Outra instância lê o mesmo arquivo; persistência não depende de memória.
    with TestClient(create_app(settings)) as reopened:
        assert reopened.get("/api/v1/favorites").json()[0]["city_name"] == "São Paulo"
    assert client.post("/api/v1/favorites", json={**CITY, "lat": 95}).status_code == 422
    assert client.post("/api/v1/favorites", json={**CITY, "city_name": "  "}).status_code == 422
    assert client.delete(f"/api/v1/favorites/{saved.json()['id']}").status_code == 204
    assert client.delete(f"/api/v1/favorites/{saved.json()['id']}").status_code == 404


def test_history_is_latest_ten(client):
    for index in range(12):
        assert client.get("/api/v1/weather", params={**CITY, "query": str(index)}).status_code == 200
    history = client.get("/api/v1/history").json()
    assert [h["query_term"] for h in history] == list(map(str, range(11, 1, -1)))


@pytest.mark.parametrize("params", [{"lat": 91, "lon": 0}, {"lat": 0, "lon": 181},
                                     {"lat": "nan", "lon": 0}, {"lat": 0, "lon": "inf"}, {}])
def test_rejects_invalid_coordinates(client, params):
    assert client.get("/api/v1/weather", params=params).status_code == 422
    assert client.app.state.weather._get.await_count == 0


def test_search_limit_cache_and_no_autocomplete_history(client):
    client.app.state.weather._get.return_value = {"results": [
        {"name": f"Cidade {i}", "admin1": "Estado", "country": "Brasil",
         "latitude": i, "longitude": -40} for i in range(7)
    ]}
    result = client.get("/api/v1/search", params={"q": "cidade"})
    assert result.status_code == 200
    assert len(result.json()) == 5
    client.get("/api/v1/search", params={"q": "CIDADE"})
    assert client.app.state.weather._get.await_count == 1
    assert client.get("/api/v1/history").json() == []
    assert client.get("/api/v1/search", params={"q": "a"}).status_code == 422


def test_provider_failure_is_not_cached(client):
    client.app.state.weather._get.side_effect = WeatherProviderError("Indisponível")
    assert client.get("/api/v1/weather", params=CITY).status_code == 502
    assert len(client.app.state.weather.cache) == 0
    assert client.get("/api/v1/history").json() == []
    client.app.state.weather._get.side_effect = None
    assert client.get("/api/v1/weather", params=CITY).status_code == 200


def test_incomplete_weather_rejected(client):
    raw = provider_payload()
    raw["daily"]["temperature_2m_max"][0] = None
    client.app.state.weather._get.return_value = raw
    assert client.get("/api/v1/weather", params=CITY).status_code == 502


def test_hourly_six_days_and_provider_parameters(client):
    response = client.get("/api/v1/weather", params=CITY)
    hours = response.json()["weather_data"]["hourly"]
    assert len(hours) == 144
    assert hours[0]["time"] == "2026-10-06T00:00"
    assert hours[-1]["time"] == "2026-10-11T23:00"
    assert hours[14]["precipitation_probability"] == 80
    assert hours[14]["precipitation"] == 1.5
    assert hours[0]["is_day"] is False
    assert hours[12]["is_day"] is True
    params = client.app.state.weather._get.call_args.args[1]
    assert "precipitation_probability" in params["hourly"]
    assert params["timezone"] == "auto"


def test_missing_hourly_does_not_break_daily_weather(client):
    raw = provider_payload()
    del raw["hourly"]
    client.app.state.weather._get.return_value = raw
    response = client.get("/api/v1/weather", params=CITY)
    assert response.status_code == 200
    assert response.json()["weather_data"]["hourly"] == []
    assert len(response.json()["weather_data"]["forecast"]) == 5


def test_hourly_missing_values_and_invalid_timestamps():
    hours = normalize_hourly({"hourly": {"time": ["2026-10-06T23:00", "invalid", "2026-10-07T00:00"],
                                        "temperature_2m": [22]}})
    assert len(hours) == 2
    assert hours[0]["precipitation_probability"] is None
    assert hours[1]["temperature"] is None
    assert hours[1]["time"] == "2026-10-07T00:00"


def test_assets_and_host_validation(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'lang="pt-BR"' in response.text
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/.env").status_code == 404
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health", headers={"host": "evil.example"}).status_code == 400


@pytest.mark.asyncio
async def test_concurrency_and_ttl(settings):
    now = [0.0]
    gemini = GeminiService(settings)
    async with httpx.AsyncClient() as http:
        service = WeatherService(settings, http, gemini)
        service.cache = TTLCache(maxsize=10, ttl=900, timer=lambda: now[0])
        async def upstream(*_):
            await asyncio.sleep(0.01)
            return provider_payload()
        service._get = AsyncMock(side_effect=upstream)
        results = await asyncio.gather(*(service.weather(-23.55, -46.63) for _ in range(10)))
        assert service._get.await_count == 1
        assert sum(not result["cached"] for result in results) == 1
        now[0] = 901
        assert (await service.weather(-23.55, -46.63))["cached"] is False
        assert service._get.await_count == 2


@pytest.mark.asyncio
async def test_gemini_success_failure_empty_and_timeout(settings):
    service = GeminiService(settings)
    weather = {"current": {"feels_like": 24, "precipitation": 0},
               "today": {"precipitation_probability": 70}, "timezone": "America/Sao_Paulo",
               "units": {"temperature": "°C"}}
    generate = AsyncMock(return_value=SimpleNamespace(text="Leve um guarda-chuva e roupas leves."))
    service.aio = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    assert (await service.insight(weather))[1] == "gemini"
    assert generate.call_args.kwargs["model"] == "gemini-2.5-flash"
    generate.side_effect = RuntimeError("quota")
    assert (await service.insight(weather))[1] == "fallback"
    generate.side_effect = None
    generate.return_value = SimpleNamespace(text="")
    assert (await service.insight(weather))[1] == "fallback"
    async def delayed(**_):
        await asyncio.sleep(1)
    generate.side_effect = delayed
    settings.gemini_timeout_seconds = 0.01
    assert (await service.insight(weather))[1] == "fallback"


@pytest.mark.asyncio
async def test_real_http_adapter_error_handling(settings):
    async def handler(request):
        return httpx.Response(429, json={"error": "quota"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        service = WeatherService(settings, http, GeminiService(settings))
        with pytest.raises(WeatherProviderError):
            await service.weather(0, 0)

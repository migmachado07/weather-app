"""Open-Meteo, normalização e cache com deduplicação de chamadas concorrentes."""
import asyncio
from datetime import datetime, timezone

import httpx
from cachetools import TTLCache
from pydantic import ValidationError

from app.config import Settings
from app.schemas import City, HourlyWeather, WeatherData
from app.services.gemini_service import GeminiService


class WeatherProviderError(Exception):
    pass


def normalize_hourly(raw: dict) -> list[dict]:
    """Uma série horária ausente não invalida o clima atual nem vira chuva zero."""
    hourly = raw.get("hourly") or {}
    if not isinstance(hourly, dict) or not isinstance(hourly.get("time"), list):
        return []
    fields = {"temperature": "temperature_2m", "precipitation_probability": "precipitation_probability",
              "precipitation": "precipitation", "weather_code": "weather_code", "is_day": "is_day"}
    result = []
    for index, timestamp in enumerate(hourly["time"]):
        values = {"time": timestamp}
        for destination, source in fields.items():
            series = hourly.get(source)
            values[destination] = series[index] if isinstance(series, list) and index < len(series) else None
        try:
            datetime.fromisoformat(timestamp)
            result.append(HourlyWeather.model_validate(values).model_dump())
        except (TypeError, ValueError, ValidationError):
            continue
    return result


class WeatherService:
    def __init__(self, settings: Settings, http: httpx.AsyncClient, gemini: GeminiService):
        self.settings, self.http, self.gemini = settings, http, gemini
        self.cache = TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl_seconds)
        self.search_cache = TTLCache(maxsize=settings.cache_maxsize, ttl=settings.cache_ttl_seconds)
        # Faixas fixas limitam memória e impedem solicitações simultâneas da
        # mesma coordenada de consumir várias chamadas meteorológicas/IA.
        self.locks = [asyncio.Lock() for _ in range(64)]
        self.search_locks = [asyncio.Lock() for _ in range(64)]

    async def _get(self, url: str, params: dict) -> dict:
        key = self.settings.open_meteo_api_key.get_secret_value()
        if key:
            params = {**params, "apikey": key}
        try:
            response = await self.http.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("error"):
                raise ValueError("invalid provider payload")
            return data
        except (httpx.HTTPError, ValueError) as exc:
            raise WeatherProviderError("O serviço de clima está indisponível. Tente novamente.") from exc

    async def search(self, query: str) -> list[City]:
        key = query.casefold()
        async with self.search_locks[hash(key) % len(self.search_locks)]:
            if key in self.search_cache:
                return self.search_cache[key]
            data = await self._get(self.settings.geocoding_url, {
                "name": query, "count": 5, "language": "pt", "format": "json"
            })
            try:
                cities = [City(
                    city_name=item["name"], state=item.get("admin1", ""),
                    country=item.get("country", ""), lat=item["latitude"], lon=item["longitude"],
                ) for item in data.get("results", [])[:5]]
            except (KeyError, TypeError, ValidationError) as exc:
                raise WeatherProviderError("Não foi possível interpretar as cidades.") from exc
            self.search_cache[key] = cities
            return cities

    async def weather(self, lat: float, lon: float) -> dict:
        key = (round(lat, 4), round(lon, 4))
        async with self.locks[hash(key) % len(self.locks)]:
            # O booleano pertence a cada resposta, não ao objeto armazenado.
            # O TTL cobre clima + insight; falhas meteorológicas não são cacheadas.
            if key in self.cache:
                return {**self.cache[key], "cached": True}
            raw = await self._get(self.settings.forecast_url, {
                "latitude": key[0], "longitude": key[1], "timezone": "auto",
                "temperature_unit": "celsius", "wind_speed_unit": "kmh",
                "precipitation_unit": "mm", "forecast_days": 6,
                "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code,is_day",
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                           "wind_speed_10m,precipitation,weather_code,is_day",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                         "precipitation_probability_max,precipitation_sum,sunrise,sunset",
            })
            try:
                current, daily = raw["current"], raw["daily"]
                days = [{
                    "date": daily["time"][i], "weather_code": daily["weather_code"][i],
                    "temp_max": daily["temperature_2m_max"][i],
                    "temp_min": daily["temperature_2m_min"][i],
                    "precipitation_probability": daily["precipitation_probability_max"][i],
                    "precipitation_sum": daily["precipitation_sum"][i],
                    "sunrise": daily["sunrise"][i] or None,
                    "sunset": daily["sunset"][i] or None,
                } for i in range(6)]
                data = WeatherData.model_validate({
                    "latitude": raw["latitude"], "longitude": raw["longitude"],
                    "timezone": raw["timezone"], "current": {
                        "time": current["time"], "temperature": current["temperature_2m"],
                        "feels_like": current["apparent_temperature"],
                        "humidity": current["relative_humidity_2m"],
                        "wind_speed": current["wind_speed_10m"],
                        "precipitation": current["precipitation"],
                        "weather_code": current["weather_code"], "is_day": bool(current["is_day"]),
                    }, "today": days[0], "forecast": days[1:6],
                    "hourly": normalize_hourly(raw),
                    "fetched_at": datetime.now(timezone.utc),
                }).model_dump(mode="json")
            except (KeyError, TypeError, IndexError, ValidationError) as exc:
                raise WeatherProviderError("O provedor retornou dados meteorológicos incompletos.") from exc
            insight, source = await self.gemini.insight(data)
            payload = {"weather_data": data, "ai_insight": insight, "ai_source": source}
            self.cache[key] = payload
            return {**payload, "cached": False}

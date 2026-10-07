from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


class City(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    city_name: str = Field(min_length=1, max_length=150)
    state: str = Field(default="", max_length=150)
    country: str = Field(default="", max_length=100)
    lat: Latitude
    lon: Longitude


class Favorite(City):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class History(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    query_term: str
    city_resolved: str
    searched_at: datetime


class CurrentWeather(BaseModel):
    time: str
    temperature: float
    feels_like: float
    humidity: float = Field(ge=0, le=100)
    wind_speed: float = Field(ge=0)
    precipitation: float = Field(ge=0)
    weather_code: int
    is_day: bool


class ForecastDay(BaseModel):
    date: date
    weather_code: int
    temp_max: float
    temp_min: float
    precipitation_probability: float = Field(ge=0, le=100)
    precipitation_sum: float = Field(ge=0)
    sunrise: str | None
    sunset: str | None


class HourlyWeather(BaseModel):
    # Horário local da cidade, preservado sem conversão pelo fuso do servidor.
    time: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
    temperature: float | None = None
    precipitation_probability: float | None = Field(default=None, ge=0, le=100)
    precipitation: float | None = Field(default=None, ge=0)
    weather_code: int | None = None
    is_day: bool | None = None


class WeatherData(BaseModel):
    latitude: Latitude
    longitude: Longitude
    timezone: str
    current: CurrentWeather
    today: ForecastDay
    forecast: list[ForecastDay] = Field(min_length=5, max_length=5)
    hourly: list[HourlyWeather] = Field(default_factory=list)
    fetched_at: datetime
    units: dict[str, str] = Field(default_factory=lambda: {
        "temperature": "°C", "wind_speed": "km/h", "precipitation": "mm", "humidity": "%"
    })


class WeatherResponse(BaseModel):
    weather_data: WeatherData
    ai_insight: str
    ai_source: Literal["gemini", "fallback"]
    cached: bool

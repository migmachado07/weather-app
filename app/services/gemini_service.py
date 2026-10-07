"""Insights assíncronos com um fallback determinístico, sem interromper o clima."""
import asyncio
import json
import logging

from google import genai
from google.genai import types

from app.config import Settings

logger = logging.getLogger(__name__)


def fallback_insight(weather: dict) -> str:
    current = weather["current"]
    today = weather["today"]
    temperature = current["feels_like"]
    clothing = (
        "Leve um casaco mais quente."
        if temperature < 15 else
        "Um casaco leve pode deixar o dia mais confortável."
        if temperature < 23 else
        "Prefira roupas leves e mantenha água por perto."
    )
    probability = today["precipitation_probability"]
    rain = (
        " Leve um guarda-chuva: há possibilidade de chuva hoje."
        if probability >= 40 or current["precipitation"] > 0 else
        " A previsão indica baixa chance de chuva hoje; confira as condições antes de sair."
    )
    return clothing + rain


class GeminiService:
    def __init__(self, settings: Settings):
        self.settings = settings
        key = settings.gemini_api_key.get_secret_value().strip()
        self.client = genai.Client(api_key=key) if key else None
        self.aio = self.client.aio if self.client else None

    async def insight(self, weather: dict) -> tuple[str, str]:
        # Sem chave, quota esgotada, timeout ou resposta vazia: mantém o clima
        # utilizável. A origem explícita impede atribuir dicas locais ao Gemini.
        if self.aio:
            try:
                async with asyncio.timeout(self.settings.gemini_timeout_seconds):
                    response = await self.aio.models.generate_content(
                        model=self.settings.gemini_model,
                        contents=json.dumps({
                            "current": weather["current"],
                            "today": weather["today"],
                            "timezone": weather["timezone"],
                            "units": weather["units"],
                        }, ensure_ascii=False),
                        config=types.GenerateContentConfig(
                            system_instruction=(
                                "Você é um assistente de planejamento climático. Gere em português "
                                "do Brasil 2 frases amigáveis, no máximo 400 caracteres, sobre roupa, "
                                "guarda-chuva e atividades para hoje. Use apenas os dados fornecidos. "
                                "Não invente horários de chuva, alertas oficiais ou dados horários. "
                                "Probabilidades não são certezas. Não use Markdown nem título."
                            ),
                            temperature=0.4,
                            max_output_tokens=200,
                            thinking_config=types.ThinkingConfig(thinking_budget=0),
                        ),
                    )
                    value = (response.text or "").strip()
                    if value and len(value) <= 600:
                        return value, "gemini"
            except Exception as exc:
                # Não registra chave, prompt ou corpo de erro do provedor.
                logger.warning("Gemini indisponível (%s); usando dica local", type(exc).__name__)
        return fallback_insight(weather), "fallback"

    async def close(self) -> None:
        if self.aio:
            await self.aio.aclose()
        if self.client:
            self.client.close()


import re

from openai import OpenAI

from app.config import get_settings
from app.schemas import RecommendationIntent

SYSTEM_PROMPT = """Du wandelst ausschliesslich die manuelle deutsche Musikwunsch-Eingabe
des Nutzers in RecommendationIntent um. Erfinde keine Kuenstler oder Genres. Nutze
plausible Standardwerte. Gib nur Daten gemaess Schema zurueck."""


def parse_local_intent(text: str) -> RecommendationIntent:
    lowered = text.lower()
    duration = 60
    duration_match = re.search(r"(\d+)\s*(?:stunden?|h)\b", lowered)
    minute_match = re.search(r"(\d+)\s*(?:minuten?|min)\b", lowered)
    if duration_match:
        duration = int(duration_match.group(1)) * 60
    elif minute_match:
        duration = int(minute_match.group(1))

    discovery = 20
    discovery_match = re.search(r"(\d+)\s*%\s*(?:neu|entdeckung|discovery)", lowered)
    if discovery_match:
        discovery = int(discovery_match.group(1))
    elif "nur bekannt" in lowered or "keine neuen" in lowered:
        discovery = 0
    elif "viel neues" in lowered or "viele neue" in lowered:
        discovery = 50

    context = "mix"
    context_keywords = {
        "sport": ("sport", "training", "laufen", "gym"),
        "fokus": ("fokus", "arbeiten", "lernen", "konzentration"),
        "abend": ("abend", "entspannen", "ruhig", "chillen"),
        "party": ("party", "feiern", "tanzen"),
        "morgen": ("morgen", "aufstehen", "frueh"),
    }
    for candidate, keywords in context_keywords.items():
        if any(keyword in lowered for keyword in keywords):
            context = candidate
            break

    energy_min = 0.65 if context in {"sport", "party"} else None
    energy_max = 0.5 if context in {"abend", "fokus"} else None
    return RecommendationIntent(
        context=context,
        duration_minutes=max(15, min(duration, 600)),
        energy_min=energy_min,
        energy_max=energy_max,
        discovery_percent=max(0, min(discovery, 100)),
        text=text,
    )


def parse_intent(text: str) -> tuple[RecommendationIntent, str]:
    settings = get_settings()
    if not settings.openai_api_key:
        return parse_local_intent(text), "local"
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.parse(
        model=settings.openai_model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        text_format=RecommendationIntent,
    )
    if response.output_parsed is None:
        return parse_local_intent(text), "local_fallback"
    response.output_parsed.text = text
    return RecommendationIntent.model_validate(response.output_parsed), "openai"

import os

import soundfile as sf
from openai import AzureOpenAI

from app.config import settings

_client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_WHISPER_KEY,
    api_version=settings.AZURE_OPENAI_WHISPER_API_VERSION,
    azure_endpoint=settings.AZURE_OPENAI_WHISPER_ENDPOINT,
)


def _get_audio_duration_minutes(file_path: str) -> float:
    """
    Return the actual audio duration in minutes using soundfile.
    Falls back to a size-based heuristic if reading fails.
    """
    try:
        info = sf.info(file_path)
        duration_sec = info.frames / float(info.samplerate or 1)
        return max(duration_sec / 60.0, 0.01)
    except Exception:
        # Fallback: approximate duration from file size if we cannot read audio metadata.
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        return max(size_mb, 0.1)


def transcribe(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        result = _client.audio.transcriptions.create(
            file=f,
            model=settings.AZURE_OPENAI_WHISPER_DEPLOYMENT,
        )

    duration_min = _get_audio_duration_minutes(file_path)
    price_per_min = settings.AZURE_WHISPER_PRICE_PER_MIN
    cost = duration_min * price_per_min

    return {
        "text": result.text,
        "duration_minutes": round(duration_min, 2),
        "cost_usd": round(cost, 4),
    }

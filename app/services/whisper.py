import os
from openai import AzureOpenAI
from app.config import settings

_client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_WHISPER_KEY,
    api_version=settings.AZURE_OPENAI_WHISPER_API_VERSION,
    azure_endpoint=settings.AZURE_OPENAI_WHISPER_ENDPOINT,
)


def transcribe(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        result = _client.audio.transcriptions.create(
            file=f,
            model=settings.AZURE_OPENAI_WHISPER_DEPLOYMENT,
        )
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    duration_min = max(size_mb, 0.1)
    return {
        "text": result.text,
        "duration_minutes": round(duration_min, 2),
        "cost_usd": round(duration_min * 0.006, 4),
    }

import os
from openai import AzureOpenAI
from app.config import settings

client = AzureOpenAI(api_key=settings.AZURE_OPENAI_WHISPER_KEY, api_version=settings.AZURE_OPENAI_WHISPER_API_VERSION, azure_endpoint=settings.AZURE_OPENAI_WHISPER_ENDPOINT)

def transcribe_audio(file_path):
    with open(file_path, "rb") as audio:
        result = client.audio.transcriptions.create(file=audio, model=settings.AZURE_OPENAI_WHISPER_DEPLOYMENT)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    estimated_minutes = max(file_size_mb, 0.1)
    cost = estimated_minutes * 0.006
    return {
        "text": result.text,
        "duration_minutes": round(estimated_minutes, 2),
        "cost_usd": round(cost, 4)
    }
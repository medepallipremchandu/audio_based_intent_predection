from openai import AzureOpenAI
from app.config import settings

client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_WHISPER_KEY,
    api_version=settings.AZURE_OPENAI_WHISPER_API_VERSION,
    azure_endpoint=settings.AZURE_OPENAI_WHISPER_ENDPOINT
)

def transcribe_audio(file_path):
    with open(file_path, "rb") as audio:
        result = client.audio.transcriptions.create(
            file=audio,
            model=settings.AZURE_OPENAI_WHISPER_DEPLOYMENT
        )
    return result.text
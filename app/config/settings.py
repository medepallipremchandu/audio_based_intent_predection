import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

    # Pricing for GPT (per 1K tokens) – set these from Azure pricing table.
    AZURE_GPT_INPUT_PRICE_PER_1K = float(os.getenv("AZURE_GPT_INPUT_PRICE_PER_1K", "0.0"))
    AZURE_GPT_OUTPUT_PRICE_PER_1K = float(os.getenv("AZURE_GPT_OUTPUT_PRICE_PER_1K", "0.0"))

    AZURE_OPENAI_WHISPER_KEY = os.getenv("AZURE_OPENAI_WHISPER_KEY")
    AZURE_OPENAI_WHISPER_ENDPOINT = os.getenv("AZURE_OPENAI_WHISPER_ENDPOINT")
    AZURE_OPENAI_WHISPER_DEPLOYMENT = os.getenv("AZURE_OPENAI_WHISPER_DEPLOYMENT")
    AZURE_OPENAI_WHISPER_API_VERSION = os.getenv("AZURE_OPENAI_WHISPER_API_VERSION")

    # Pricing for Whisper (per minute) – set from Azure pricing table.
    AZURE_WHISPER_PRICE_PER_MIN = float(os.getenv("AZURE_WHISPER_PRICE_PER_MIN", "0.0"))
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/audio_intent")
    JWT_SECRET = os.getenv("JWT_SECRET", "change-me-super-secret")
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

settings = Settings()

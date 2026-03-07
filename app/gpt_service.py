import json
from openai import AzureOpenAI
from app.config import settings
from app.prompts import FEATURE_PROMPT

client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
)

def analyze_transcript(transcript):
    prompt = FEATURE_PROMPT.format(transcript=transcript)
    response = client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You analyze university admission calls."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    content = response.choices[0].message.content
    return json.loads(content)
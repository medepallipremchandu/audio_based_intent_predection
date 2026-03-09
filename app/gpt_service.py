import json
from openai import AzureOpenAI
from app.config import settings
from app.prompts import FEATURE_PROMPT

client = AzureOpenAI(api_key=settings.AZURE_OPENAI_API_KEY, api_version=settings.AZURE_OPENAI_API_VERSION, azure_endpoint=settings.AZURE_OPENAI_ENDPOINT)

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
    usage = response.usage
    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens
    total_tokens = usage.total_tokens
    input_cost = (prompt_tokens / 1000) * 0.03
    output_cost = (completion_tokens / 1000) * 0.06
    total_cost = input_cost + output_cost
    analysis = json.loads(content)
    analysis["token_usage"] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "input_cost_usd": round(input_cost, 4),
        "output_cost_usd": round(output_cost, 4),
        "total_cost_usd": round(total_cost, 4)
    }
    return analysis
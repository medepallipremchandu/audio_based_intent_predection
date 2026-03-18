import json
from openai import AzureOpenAI
from app.config import settings
from app.prompts import ANALYSIS_PROMPT
from app.services.audio_features import SEGMENT_DURATION

_client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
)


def _build_segment_summary(segments: list) -> list:
    return [
        {
            "segment_index": s["segment_index"],
            "start_sec":     s["start_sec"],
            "end_sec":       s["end_sec"],
            "avg_pitch":     s["avg_pitch"],
            "pitch_trend":   s["pitch_trend"],
            "avg_volume":    s["avg_volume"],
            "volume_spikes": s["volume_spikes"],
            "silence_ratio": s["silence_ratio"],
            "pause_count":   s["pause_count"],
            "tone_label":    s["tone_label"],
            "tone_confidence": s["tone_confidence"],
        }
        for s in segments
    ]


def analyze(transcript: str, audio_features: dict) -> dict:
    segments = audio_features.pop("segments", [])

    af_summary = {k: v for k, v in audio_features.items()}
    af_summary["pause_count"]           = audio_features.get("pause_count", 0)
    af_summary["avg_pause_duration_sec"] = audio_features.get("avg_pause_duration_sec", 0.0)

    prompt = ANALYSIS_PROMPT.format(
        transcript=transcript,
        audio_features_json=json.dumps(af_summary, indent=2),
        segments_json=json.dumps(_build_segment_summary(segments), indent=2),
        segment_duration=SEGMENT_DURATION,
    )

    response = _client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a multimodal voice intelligence system. "
                    "You analyze any type of audio conversation — group discussions, "
                    "feedback sessions, sales calls, interviews, or debates — "
                    "using both transcript text and audio signal features. "
                    "You detect intent, emotion, negativity, conflict, sarcasm, and hesitation."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    usage = response.usage
    input_cost  = (usage.prompt_tokens / 1000) * 0.03
    output_cost = (usage.completion_tokens / 1000) * 0.06

    result = json.loads(raw)
    result["_token_usage"] = {
        "prompt_tokens":    usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens":     usage.total_tokens,
        "input_cost_usd":   round(input_cost, 4),
        "output_cost_usd":  round(output_cost, 4),
        "total_cost_usd":   round(input_cost + output_cost, 4),
    }
    result["_segments"] = segments
    return result

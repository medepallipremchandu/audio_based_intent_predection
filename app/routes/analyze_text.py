import logging
from app.services.gpt import analyze
from app.routes.analyze import _safe_list, _safe_bool, _override_segment_sentiments

logger = logging.getLogger(__name__)


def run_text_pipeline(text: str) -> dict:
    gpt_result = analyze(text, {})

    token_usage = gpt_result.pop("_token_usage", {})
    gpt_result.pop("_segments", None)

    gpt_cost = token_usage.get("total_cost_usd", 0)

    raw_speakers = _safe_list(gpt_result.get("speakers", []))
    speakers_out = [
        {
            "speaker_id":     sp.get("speaker_id", "unknown"),
            "dominant_tone":  sp.get("dominant_tone"),
            "sentiment":      sp.get("sentiment"),
            "sentiment_score": sp.get("sentiment_score"),
            "key_statements": _safe_list(sp.get("key_statements", [])),
        }
        for sp in raw_speakers if isinstance(sp, dict)
    ]

    raw_seg_insights = _safe_list(gpt_result.get("segment_insights", []))
    raw_seg_insights = _override_segment_sentiments(
        raw_seg_insights,
        negative_statements=_safe_list(gpt_result.get("negative_statements", [])),
        positive_statements=_safe_list(gpt_result.get("positive_statements", [])),
        transcript=text,
    )

    return {
        "transcript": text,
        "audio": None,
        "analysis": {
            "overall_sentiment":   gpt_result.get("overall_sentiment", "neutral"),
            "overall_tone":        gpt_result.get("overall_tone", "neutral"),
            "dominant_emotion":    gpt_result.get("dominant_emotion", "neutral"),
            "tone_alignment":      "text-only",
            "confidence_score":    gpt_result.get("confidence_score", 0.0),
            "confidence_label":    gpt_result.get("confidence_label", "Low confidence"),
            "sentiment_score":     gpt_result.get("sentiment_score", 0.0),
            "signal_count":        gpt_result.get("signal_count", 0),
            "conflict_detected":   _safe_bool(gpt_result.get("conflict_detected", False)),
            "negativity_detected": _safe_bool(gpt_result.get("negativity_detected", False)),
            "negativity_sources":  _safe_list(gpt_result.get("negativity_sources", [])),
            "sarcasm_detected":    _safe_bool(gpt_result.get("sarcasm_detected", False)),
            "hesitation_detected": _safe_bool(gpt_result.get("hesitation_detected", False)),
            "positive_statements": _safe_list(gpt_result.get("positive_statements", [])),
            "negative_statements": _safe_list(gpt_result.get("negative_statements", [])),
            "key_topics":          _safe_list(gpt_result.get("key_topics", [])),
            "key_phrases_detected": _safe_list(gpt_result.get("key_phrases_detected", [])),
            "action_items":        _safe_list(gpt_result.get("action_items", [])),
            "unresolved_issues":   _safe_list(gpt_result.get("unresolved_issues", [])),
            "supporting_evidence": _safe_list(gpt_result.get("supporting_evidence", [])),
            "decision_chain":      _safe_list(gpt_result.get("decision_chain", [])),
            "recommended_action":  gpt_result.get("recommended_action", ""),
            "primary_topic":       gpt_result.get("primary_topic", ""),
            "secondary_topic":     gpt_result.get("secondary_topic"),
            "speakers":            speakers_out,
            "segment_insights":    raw_seg_insights,
            "summary":             gpt_result.get("summary", ""),
        },
        "usage": {
            "whisper_duration_minutes": 0,
            "whisper_cost_usd":         0,
            "gpt_prompt_tokens":        token_usage.get("prompt_tokens", 0),
            "gpt_completion_tokens":    token_usage.get("completion_tokens", 0),
            "gpt_total_tokens":         token_usage.get("total_tokens", 0),
            "gpt_cost_usd":             token_usage.get("total_cost_usd", 0),
            "total_cost_usd":           round(gpt_cost, 4),
        },
    }

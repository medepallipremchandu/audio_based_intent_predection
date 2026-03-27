import logging
from app.services.audio_features import extract_audio_features
from app.services.whisper import transcribe
from app.services.gpt import analyze

logger = logging.getLogger(__name__)


def _safe_list(v) -> list:
    if isinstance(v, list): return v
    if v is None:           return []
    if isinstance(v, str):  return [v] if v.strip() else []
    return []


def _safe_bool(v) -> bool:
    if isinstance(v, bool): return v
    if isinstance(v, int):  return bool(v)
    if isinstance(v, str):  return v.lower() in ("true", "1", "yes")
    return False


def _override_segment_sentiments(
    seg_insights: list,
    negative_statements: list,
    positive_statements: list,
    transcript: str,
) -> list:
    """
    GPT often marks all segments neutral even when negative/positive statements exist.
    We fix this by checking whether any negative or positive statement text appears
    in the rough transcript window that corresponds to each segment's time range.

    Strategy: split transcript into equal-length chunks matching segment count,
    then do substring matching against known negative/positive statements.
    """
    if not seg_insights or not transcript:
        return seg_insights

    n = len(seg_insights)
    words = transcript.split()
    chunk = max(1, len(words) // n)

    neg_lower = [s.lower().strip() for s in negative_statements if s]
    pos_lower = [s.lower().strip() for s in positive_statements if s]

    def _contains_any(window_text: str, phrases: list) -> bool:
        wl = window_text.lower()
        for phrase in phrases:
            # match if at least 60% of the phrase words appear in the window
            phrase_words = phrase.split()
            if not phrase_words:
                continue
            hits = sum(1 for w in phrase_words if w in wl)
            if hits / len(phrase_words) >= 0.6:
                return True
        return False

    result = []
    for i, si in enumerate(seg_insights):
        start_w = i * chunk
        end_w   = min(start_w + chunk, len(words))
        window  = " ".join(words[start_w:end_w])

        updated = dict(si)
        if _contains_any(window, neg_lower):
            updated["sentiment_label"]  = "negative"
            updated["negativity_spike"] = True
        elif _contains_any(window, pos_lower):
            # only upgrade to positive if GPT didn't already flag negative
            if updated.get("sentiment_label") != "negative":
                updated["sentiment_label"] = "positive"
        result.append(updated)

    return result


def run_pipeline(audio_path: str) -> dict:
    audio_features = {}
    try:
        audio_features = extract_audio_features(audio_path)
        logger.info(
            f"audio extracted segments={audio_features.get('segment_count')} "
            f"duration={audio_features.get('total_duration')}s "
            f"tone={audio_features.get('tone_label')}"
        )
    except Exception as e:
        logger.warning(f"audio extraction failed (non-fatal): {e}")

    transcription = transcribe(audio_path)
    transcript = transcription["text"]

    if audio_features and not audio_features.get("speech_rate"):
        speaking_dur = audio_features.get("speaking_duration", 0)
        if speaking_dur > 0:
            words = len(transcript.split())
            audio_features["speech_rate"] = round(words / speaking_dur, 2)

    gpt_result = analyze(transcript, audio_features)

    token_usage = gpt_result.pop("_token_usage", {})
    segments    = gpt_result.pop("_segments", [])

    whisper_cost = transcription["cost_usd"]
    gpt_cost     = token_usage.get("total_cost_usd", 0)

    audio_out = {**audio_features, "segments": [
        {
            "segment_index":    s["segment_index"],
            "start_sec":        s["start_sec"],
            "end_sec":          s["end_sec"],
            "avg_pitch":        s["avg_pitch"],
            "pitch_variation":  s["pitch_variation"],
            "pitch_trend":      s["pitch_trend"],
            "avg_volume":       s["avg_volume"],
            "volume_spikes":    s["volume_spikes"],
            "speech_rate":      s.get("speech_rate", 0.0),
            "pause_count":      s["pause_count"],
            "silence_ratio":    s["silence_ratio"],
            "speaking_duration": s["speaking_duration"],
            "tone_label":       s["tone_label"],
            "tone_confidence":  s["tone_confidence"],
        }
        for s in segments
    ]}

    raw_speakers = _safe_list(gpt_result.get("speakers", []))
    speakers_out = [
        {
            "speaker_id":      sp.get("speaker_id", "unknown"),
            "dominant_tone":   sp.get("dominant_tone"),
            "sentiment":       sp.get("sentiment"),
            "sentiment_score": sp.get("sentiment_score"),
            "key_statements":  _safe_list(sp.get("key_statements", [])),
        }
        for sp in raw_speakers if isinstance(sp, dict)
    ]

    raw_seg_insights = _safe_list(gpt_result.get("segment_insights", []))

    # Fix GPT under-labelling: override segment sentiments using known statements
    raw_seg_insights = _override_segment_sentiments(
        raw_seg_insights,
        negative_statements=_safe_list(gpt_result.get("negative_statements", [])),
        positive_statements=_safe_list(gpt_result.get("positive_statements", [])),
        transcript=transcript,
    )

    seg_insights_out = [
        {
            "segment_index":    si.get("segment_index", 0),
            "start_sec":        si.get("start_sec", 0.0),
            "end_sec":          si.get("end_sec", 0.0),
            "tone_shift":       _safe_bool(si.get("tone_shift", False)),
            "negativity_spike": _safe_bool(si.get("negativity_spike", False)),
            "sentiment_label":  si.get("sentiment_label"),
            "key_moment":       si.get("key_moment"),
        }
        for si in raw_seg_insights if isinstance(si, dict)
    ]

    return {
        "transcript": transcript,
        "audio": audio_out,
        "analysis": {
            "overall_sentiment":  gpt_result.get("overall_sentiment", "neutral"),
            "overall_tone":       gpt_result.get("overall_tone", "neutral"),
            "dominant_emotion":   gpt_result.get("dominant_emotion", "neutral"),
            "tone_alignment":     gpt_result.get("tone_alignment", "aligned"),
            "confidence_score":   gpt_result.get("confidence_score", 0.0),
            "confidence_label":   gpt_result.get("confidence_label", "Low confidence"),
            "sentiment_score":    gpt_result.get("sentiment_score", 0.0),
            "signal_count":       gpt_result.get("signal_count", 0),
            "conflict_detected":  _safe_bool(gpt_result.get("conflict_detected", False)),
            "negativity_detected": _safe_bool(gpt_result.get("negativity_detected", False)),
            "negativity_sources": _safe_list(gpt_result.get("negativity_sources", [])),
            "sarcasm_detected":   _safe_bool(gpt_result.get("sarcasm_detected", False)),
            "hesitation_detected": _safe_bool(gpt_result.get("hesitation_detected", False)),
            "positive_statements": _safe_list(gpt_result.get("positive_statements", [])),
            "negative_statements": _safe_list(gpt_result.get("negative_statements", [])),
            "key_topics":         _safe_list(gpt_result.get("key_topics", [])),
            "key_phrases_detected": _safe_list(gpt_result.get("key_phrases_detected", [])),
            "action_items":       _safe_list(gpt_result.get("action_items", [])),
            "unresolved_issues":  _safe_list(gpt_result.get("unresolved_issues", [])),
            "supporting_evidence": _safe_list(gpt_result.get("supporting_evidence", [])),
            "decision_chain":     _safe_list(gpt_result.get("decision_chain", [])),
            "recommended_action": gpt_result.get("recommended_action", ""),
            "primary_topic":      gpt_result.get("primary_topic", ""),
            "secondary_topic":    gpt_result.get("secondary_topic"),
            "speakers":           speakers_out,
            "segment_insights":   seg_insights_out,
            "summary":            gpt_result.get("summary", ""),
        },
        "usage": {
            "whisper_duration_minutes": transcription["duration_minutes"],
            "whisper_cost_usd":         whisper_cost,
            "gpt_prompt_tokens":        token_usage.get("prompt_tokens", 0),
            "gpt_completion_tokens":    token_usage.get("completion_tokens", 0),
            "gpt_total_tokens":         token_usage.get("total_tokens", 0),
            "gpt_cost_usd":             token_usage.get("total_cost_usd", 0),
            "total_cost_usd":           round(whisper_cost + gpt_cost, 4),
        },
    }

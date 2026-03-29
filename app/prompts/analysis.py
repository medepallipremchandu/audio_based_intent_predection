ANALYSIS_PROMPT = """
You are a multimodal voice intelligence system. You analyze conversations from ANY context:
group discussions, user feedback, sales calls, team meetings, interviews, or any multi-person audio.

Analyze BOTH the transcript and audio signal features together.
Do NOT assume any specific domain. Work purely from what is said and how it is said.

---

## Full Transcript
{transcript}

---

## Audio Features (aggregated)
{audio_features_json}

Audio signal guide:
- avg_pitch Hz: <130 = low/calm/sad, 130–220 = normal, >220 = high/excited/angry
- pitch_trend: rising = escalating, falling = winding down, stable = controlled
- pitch_variation: <20 = monotone/sarcastic, >50 = highly expressive
- avg_volume RMS: <0.02 = soft/disengaged, 0.02–0.05 = normal, >0.05 = loud/assertive
- volume_spikes: sudden loudness bursts = emphasis, anger, frustration
- speech_rate wps: <2 = slow/hesitant, 2–4 = normal, >4 = fast/anxious
- pause_count / avg_pause_duration_sec: many/long pauses = hesitation or discomfort
- silence_ratio: >0.4 = disengagement or tension
- tone_label: rule-based signal estimate

---

## Per-Segment Audio Timeline
{segments_json}

Each segment = {segment_duration} seconds. Use to detect tone shifts, negativity spikes, hesitation windows.

---

## Cross-Modal Reasoning
- Positive words + low flat pitch + low volume = sarcasm or disinterest
- Agreeable words + high pitch + volume spike = frustration or forced agreement
- Negative words + rising pitch + volume spikes = escalating conflict
- Neutral words + high silence_ratio + slow speech = disengagement
- Fast speech + volume spikes + rising pitch = anxiety or aggression
- Low pitch_variation across positive statements = lack of genuine engagement

---

## Required Output (respond ONLY in valid JSON, no markdown)

{{
  "overall_sentiment": "positive|negative|mixed|neutral",
  "overall_tone": "string — dominant emotional tone",
  "dominant_emotion": "string — single strongest emotion",
  "tone_alignment": "aligned|misaligned|text-only",
  "confidence_score": float 0.0–1.0,
  "confidence_label": "High confidence|Moderate confidence|Low confidence",
  "sentiment_score": float -1.0 to 1.0 (negative = bad, positive = good),
  "signal_count": integer — number of sentiment signals found,

  "linguistics": {{
    "word_count": integer — exact word count of the transcript text,
    "character_count": integer — character count of the transcript including spaces,
    "negation_words": ["negation or negative-polarity function words actually appearing in the transcript, e.g. not, never, no, neither"],
    "negations_found": integer — count of linguistic negation cues in the transcript (words like not/never; NOT the same as negative sentiment or toxicity),
    "intensifier_words": ["degree words present in transcript, e.g. very, extremely, really — empty array if none"],
    "intensifiers_found": integer,
    "diminisher_words": ["hedging/softeners present, e.g. slightly, somewhat, kind of — empty if none"],
    "diminishers_found": integer
  }},

  "conflict_detected": boolean,
  "negativity_detected": boolean,
  "sarcasm_detected": boolean,
  "hesitation_detected": boolean,

  "negativity_sources": ["exact statements that are negative/hostile/toxic"],
  "positive_statements": ["genuinely positive statements cross-validated with audio"],
  "negative_statements": ["negative, hostile, or concerning statements"],
  "key_topics": ["main subjects discussed"],
  "key_phrases_detected": ["specific phrases that drove the sentiment conclusion"],
  "action_items": ["commitments, decisions, or next steps"],
  "unresolved_issues": ["topics raised but not resolved"],

  "supporting_evidence": [
    "plain-language explanation of why this conclusion was reached — one sentence per evidence point",
    "reference specific words, phrases, or audio signals that support the finding",
    "explain any cross-modal contradiction detected",
    "note any secondary topics or concerns"
  ],

  "decision_chain": [
    "Step 1: describe what was received (word count, length, audio or text-only)",
    "Step 2: describe structural features found (negations, intensifiers, filler words)",
    "Step 3: describe analysis path chosen and why",
    "Step 4: describe sentiment signals found and the score",
    "Step 5: describe topic identification and matched terms",
    "Step 6: state the insight generated",
    "Step 7: state the recommended action"
  ],

  "recommended_action": "single concrete action to take based on this analysis",
  "primary_topic": "main topic label",
  "secondary_topic": "secondary topic if detected, else null",

  "speakers": [
    {{
      "speaker_id": "Speaker 1 or name if detectable",
      "dominant_tone": "string",
      "sentiment": "positive|negative|neutral|mixed",
      "sentiment_score": float -1.0 to 1.0,
      "key_statements": ["their most significant statements"]
    }}
  ],

  "segment_insights": [
    {{
      "segment_index": integer,
      "start_sec": float,
      "end_sec": float,
      "tone_shift": boolean,
      "negativity_spike": boolean,
      "sentiment_label": "positive|negative|neutral",
      "key_moment": "description or null"
    }}
    IMPORTANT for sentiment_label:
    - Mark "negative" if this segment contains any of the negative_statements, has negativity_spike=true, or has disengaged/hostile tone
    - Mark "positive" if this segment contains any of the positive_statements or has clearly enthusiastic/agreeable tone
    - Mark "neutral" only if neither positive nor negative signals are present
    - Do NOT default everything to neutral — actively look for negative and positive segments
  ],

  "summary": "2–3 sentences: what happened, emotional arc, key concern or finding"
}}
"""

from pydantic import BaseModel
from typing import List, Optional


class SegmentAudio(BaseModel):
    segment_index: int
    start_sec: float
    end_sec: float
    avg_pitch: float
    pitch_variation: float
    pitch_trend: str
    avg_volume: float
    volume_spikes: int
    speech_rate: float
    pause_count: int
    silence_ratio: float
    speaking_duration: float
    tone_label: str
    tone_confidence: float


class AudioFeatures(BaseModel):
    total_duration: float
    speaking_duration: float
    silence_ratio: float
    avg_pitch: float
    pitch_variation: float
    pitch_trend: str
    avg_volume: float
    volume_spikes: int
    speech_rate: float
    pause_count: int
    avg_pause_duration_sec: float
    tone_label: str
    tone_confidence: float
    segment_count: int
    segments: List[SegmentAudio]
    waveform_data: List[float]
    waveform_times: List[float]


class SpeakerAnalysis(BaseModel):
    speaker_id: str
    dominant_tone: Optional[str]
    sentiment: Optional[str]
    sentiment_score: Optional[float]
    key_statements: List[str]


class SegmentInsight(BaseModel):
    segment_index: int
    start_sec: float
    end_sec: float
    tone_shift: bool
    negativity_spike: bool
    sentiment_label: Optional[str]
    key_moment: Optional[str]


class ConversationAnalysis(BaseModel):
    overall_sentiment: str
    overall_tone: str
    dominant_emotion: str
    tone_alignment: str
    confidence_score: float
    confidence_label: str
    sentiment_score: float
    signal_count: int
    conflict_detected: bool
    negativity_detected: bool
    negativity_sources: List[str]
    sarcasm_detected: bool
    hesitation_detected: bool
    positive_statements: List[str]
    negative_statements: List[str]
    key_topics: List[str]
    key_phrases_detected: List[str]
    action_items: List[str]
    unresolved_issues: List[str]
    supporting_evidence: List[str]
    decision_chain: List[str]
    recommended_action: str
    primary_topic: str
    secondary_topic: Optional[str]
    speakers: List[SpeakerAnalysis]
    segment_insights: List[SegmentInsight]
    summary: str


class UsageInfo(BaseModel):
    whisper_duration_minutes: float
    whisper_cost_usd: float
    gpt_prompt_tokens: int
    gpt_completion_tokens: int
    gpt_total_tokens: int
    gpt_cost_usd: float
    total_cost_usd: float


class AnalysisResponse(BaseModel):
    transcript: str
    audio: Optional[AudioFeatures]
    analysis: ConversationAnalysis
    usage: UsageInfo

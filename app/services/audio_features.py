import numpy as np
import librosa
import logging

logger = logging.getLogger(__name__)

SEGMENT_DURATION = 7
SILENCE_DB = -40
HOP = 512
SR = 16000


def _load(path: str):
    return librosa.load(path, sr=SR, mono=True)


def _pitch(y: np.ndarray) -> dict:
    try:
        f0, voiced, _ = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=SR,
            hop_length=HOP,
        )
        v = f0[voiced & ~np.isnan(f0)]
        if len(v) < 3:
            return {"avg_pitch": 0.0, "pitch_variation": 0.0, "pitch_trend": "stable"}
        mid = len(v) // 2
        diff = float(np.mean(v[mid:])) - float(np.mean(v[:mid]))
        trend = "rising" if diff > 15 else "falling" if diff < -15 else "stable"
        return {
            "avg_pitch": round(float(np.mean(v)), 2),
            "pitch_variation": round(float(np.std(v)), 2),
            "pitch_trend": trend,
        }
    except Exception as e:
        logger.warning(f"pitch failed: {e}")
        return {"avg_pitch": 0.0, "pitch_variation": 0.0, "pitch_trend": "stable"}


def _volume(y: np.ndarray) -> dict:
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    avg = float(np.mean(rms))
    spikes = int(np.sum(rms > avg + 2.0 * float(np.std(rms))))
    return {"avg_volume": round(avg, 6), "volume_spikes": spikes}


def _pauses(y: np.ndarray) -> dict:
    threshold = librosa.db_to_amplitude(SILENCE_DB)
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    frame_dur = HOP / SR
    is_silent = rms < threshold
    silence_ratio = round(float(np.sum(is_silent)) / max(len(is_silent), 1), 3)

    pauses, in_pause, start = [], False, 0
    min_frames = int(0.3 / frame_dur)
    for i, s in enumerate(is_silent):
        if s and not in_pause:
            in_pause, start = True, i
        elif not s and in_pause:
            in_pause = False
            if (i - start) >= min_frames:
                pauses.append(round((i - start) * frame_dur, 3))
    if in_pause and (len(is_silent) - start) >= min_frames:
        pauses.append(round((len(is_silent) - start) * frame_dur, 3))

    return {"pause_durations": pauses, "silence_ratio": silence_ratio}


def _speaking_dur(y: np.ndarray) -> float:
    threshold = librosa.db_to_amplitude(SILENCE_DB)
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    silence_sec = float(np.sum(rms < threshold)) * (HOP / SR)
    return round(max(len(y) / SR - silence_sec, 0.0), 3)


def _speech_rate(transcript: str, speaking_dur: float) -> float:
    if not transcript or speaking_dur <= 0:
        return 0.0
    return round(len(transcript.split()) / speaking_dur, 2)


_TONE_RULES = [
    (lambda p, v, r, pv: p > 220 and v > 0.05 and r > 3.5,      "excited",    0.75),
    (lambda p, v, r, pv: p > 220 and v > 0.05 and r <= 3.5,     "angry",      0.70),
    (lambda p, v, r, pv: p < 130 and v < 0.02 and r < 2.0,      "disengaged", 0.68),
    (lambda p, v, r, pv: p < 130 and v < 0.02,                   "sad",        0.72),
    (lambda p, v, r, pv: pv < 20 and 130 <= p <= 200,            "sarcastic",  0.60),
    (lambda p, v, r, pv: p > 180 and v < 0.02,                   "frustrated", 0.65),
    (lambda p, v, r, pv: 130 <= p <= 200 and 0.02 <= v <= 0.05,  "neutral",    0.80),
]


def _tone(avg_pitch: float, avg_volume: float, rate: float, pitch_var: float) -> dict:
    for fn, label, conf in _TONE_RULES:
        try:
            if fn(avg_pitch, avg_volume, rate, pitch_var):
                return {"tone_label": label, "tone_confidence": conf}
        except Exception:
            continue
    return {"tone_label": "neutral", "tone_confidence": 0.5}


def _process_segment(seg: np.ndarray, idx: int, start_sec: float) -> dict:
    p  = _pitch(seg)
    v  = _volume(seg)
    pa = _pauses(seg)
    sd = _speaking_dur(seg)
    t  = _tone(p["avg_pitch"], v["avg_volume"], 0.0, p["pitch_variation"])
    end_sec = round(start_sec + len(seg) / SR, 3)

    return {
        "segment_index":    idx,
        "start_sec":        round(start_sec, 3),
        "end_sec":          end_sec,
        "avg_pitch":        p["avg_pitch"],
        "pitch_variation":  p["pitch_variation"],
        "pitch_trend":      p["pitch_trend"],
        "avg_volume":       v["avg_volume"],
        "volume_spikes":    v["volume_spikes"],
        "speech_rate":      0.0,
        "pause_count":      len(pa["pause_durations"]),
        "pause_durations":  pa["pause_durations"],
        "silence_ratio":    pa["silence_ratio"],
        "speaking_duration": sd,
        "tone_label":       t["tone_label"],
        "tone_confidence":  t["tone_confidence"],
    }


def _waveform(y: np.ndarray, points: int = 200) -> dict:
    chunk = max(1, len(y) // points)
    rms_vals = []
    times = []
    for i in range(points):
        s = i * chunk
        e = min(s + chunk, len(y))
        if s >= len(y):
            break
        rms_vals.append(float(np.sqrt(np.mean(y[s:e] ** 2))))
        times.append(round(s / SR, 3))
    if not rms_vals:
        return {"waveform_data": [], "waveform_times": []}
    peak = max(rms_vals) or 1.0
    return {
        "waveform_data": [round(v / peak, 4) for v in rms_vals],
        "waveform_times": times,
    }


def extract_audio_features(audio_path: str, transcript: str = "") -> dict:
    y, _ = _load(audio_path)
    total_duration = round(len(y) / SR, 3)
    seg_len = SEGMENT_DURATION * SR

    segments = []
    start = 0
    idx = 0
    while start < len(y):
        end = min(start + seg_len, len(y))
        seg = y[start:end]
        segments.append(_process_segment(seg, idx, start / SR))
        start = end
        idx += 1

    if not segments:
        return _empty()

    pitches  = [s["avg_pitch"]  for s in segments if s["avg_pitch"] > 0]
    volumes  = [s["avg_volume"] for s in segments]
    all_pauses = [p for s in segments for p in s["pause_durations"]]
    total_speaking = sum(s["speaking_duration"] for s in segments)

    avg_pitch     = round(float(np.mean(pitches)), 2)     if pitches else 0.0
    pitch_var     = round(float(np.std(pitches)), 2)      if len(pitches) > 1 else 0.0
    trends        = [s["pitch_trend"] for s in segments]
    pitch_trend   = max(set(trends), key=trends.count)
    avg_volume    = round(float(np.mean(volumes)), 6)     if volumes else 0.0
    silence_ratio = round(float(np.mean([s["silence_ratio"] for s in segments])), 3)
    rate          = _speech_rate(transcript, total_speaking)
    pause_count   = len(all_pauses)
    avg_pause     = round(sum(all_pauses) / pause_count, 3) if pause_count else 0.0
    t             = _tone(avg_pitch, avg_volume, rate, pitch_var)

    for s in segments:
        s["speech_rate"] = rate

    wf = _waveform(y)

    return {
        "total_duration":       total_duration,
        "speaking_duration":    round(total_speaking, 3),
        "silence_ratio":        silence_ratio,
        "avg_pitch":            avg_pitch,
        "pitch_variation":      pitch_var,
        "pitch_trend":          pitch_trend,
        "avg_volume":           avg_volume,
        "volume_spikes":        sum(s["volume_spikes"] for s in segments),
        "speech_rate":          rate,
        "pause_count":          pause_count,
        "avg_pause_duration_sec": avg_pause,
        "tone_label":           t["tone_label"],
        "tone_confidence":      t["tone_confidence"],
        "segment_count":        len(segments),
        "segments":             segments,
        "waveform_data":        wf["waveform_data"],
        "waveform_times":       wf["waveform_times"],
    }


def _empty() -> dict:
    return {
        "total_duration": 0.0, "speaking_duration": 0.0, "silence_ratio": 0.0,
        "avg_pitch": 0.0, "pitch_variation": 0.0, "pitch_trend": "stable",
        "avg_volume": 0.0, "volume_spikes": 0, "speech_rate": 0.0,
        "pause_count": 0, "avg_pause_duration_sec": 0.0,
        "tone_label": "neutral", "tone_confidence": 0.5,
        "segment_count": 0, "segments": [],
        "waveform_data": [], "waveform_times": [],
    }

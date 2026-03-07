from app.whisper_service import transcribe_audio
from app.gpt_service import analyze_transcript
from app.recommendation_engine import generate_recommendations
from app.ml_model import predict_enrollment

def analyze_call(audio_path: str) -> dict:
    transcript = transcribe_audio(audio_path)
    analysis = analyze_transcript(transcript)
    def to_int(value):
        if isinstance(value, list):
            return len(value)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value.strip()))
            except:
                return 0
        return 0
    def to_float(value):
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except:
                return 0.0
        return 0.0
    def to_list(value):
        if isinstance(value, list):
            return value
        if value is None:
            return []
        if isinstance(value, str):
            v = value.strip()
            return [v] if v else []
        return []
    llm_features = {
        "student_questions_count": to_int(analysis.get("student_questions_count", 0)),
        "student_objections_count": to_int(analysis.get("student_objections_count", 0)),
        "positive_statements": to_int(analysis.get("positive_statements", 0)),
        "negative_statements": to_int(analysis.get("negative_statements", 0)),
        "budget_mentions": to_int(analysis.get("budget_mentions", 0)),
        "parent_mentions": to_int(analysis.get("parent_mentions", 0)),
        "course_mentions": to_int(analysis.get("course_mentions", 0)),
        "deadline_interest": int(bool(analysis.get("deadline_interest", 0)))
    }
    llm_enrollment_probability = to_float(analysis.get("enrollment_probability", 0))
    ml_enrollment_probability = predict_enrollment(llm_features)
    rec_llm = generate_recommendations(llm_features, analysis.get("objections", []))
    rec_ml = generate_recommendations(llm_features, analysis.get("objections", []))
    llm_follow_up = "high" if llm_enrollment_probability > 0.6 else "medium"
    ml_follow_up = "high" if ml_enrollment_probability > 0.6 else "medium"
    return {
        "transcript": transcript,
        "llm": {
            "intent": analysis.get("intent"),
            "confidence_score": to_float(analysis.get("confidence_score", 0)),
            "interest_level": analysis.get("interest_level"),
            "enrollment_probability": llm_enrollment_probability,
            "features": llm_features,
            "positive_statements": to_list(analysis.get("positive_statements", [])),
            "negative_statements": to_list(analysis.get("negative_statements", [])),
            "budget_mentions": to_list(analysis.get("budget_mentions", [])),
            "parent_mentions": to_list(analysis.get("parent_mentions", [])),
            "course_mentions": to_list(analysis.get("course_mentions", [])),
            "reasons": analysis.get("reasons", []),
            "objections": analysis.get("objections", []),
            "summary": analysis.get("summary"),
            "recommendations": rec_llm,
            "follow_up_priority": llm_follow_up,
        },
        "ml": {
            "enrollment_probability": ml_enrollment_probability,
            "recommendations": rec_ml,
            "follow_up_priority": ml_follow_up,
        },
    }

from app.whisper_service import transcribe_audio
from app.gpt_service import analyze_transcript
from app.recommendation_engine import generate_recommendations
from app.ml_model import predict_enrollment

def analyze_call(audio_path: str) -> dict:
    """
    Full analysis pipeline:
    1. Transcribe audio via Whisper
    2. Analyze transcript via GPT-4 for structured features
    3. Predict enrollment probability using ML model
    4. Generate recommendations

    Parameters:
        audio_path (str): Path to audio file

    Returns:
        dict: Combined analysis with features, enrollment probability,
              recommendations, summary, follow-up priority, and transcript
    """
    # Step 1: Transcribe audio
    transcript = transcribe_audio(audio_path)

    # Step 2: GPT-4 feature extraction
    analysis = analyze_transcript(transcript)

    # Step 3: Prepare and sanitize features
    features = {
        "student_questions_count": analysis.get("student_questions_count", 0),
        "student_objections_count": analysis.get("student_objections_count", 0),
        "positive_statements": analysis.get("positive_statements", 0),
        "negative_statements": analysis.get("negative_statements", 0),
        "budget_mentions": analysis.get("budget_mentions", 0),
        "parent_mentions": analysis.get("parent_mentions", 0),
        "course_mentions": analysis.get("course_mentions", 0),
        "deadline_interest": int(analysis.get("deadline_interest", 0))
    }

    # Step 4: Predict enrollment probability
    enrollment_probability = predict_enrollment(features)

    # Step 5: Generate recommendations
    recommendations = generate_recommendations(features, analysis.get("objections", []))

    # Step 6: Compose final response
    analysis["features"] = features
    analysis["enrollment_probability"] = enrollment_probability
    analysis["recommendations"] = recommendations
    analysis["transcript"] = transcript
    analysis["follow_up_priority"] = "high" if enrollment_probability > 0.6 else "medium"

    return analysis
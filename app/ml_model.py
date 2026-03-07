import joblib
import numpy as np

model = joblib.load("training/admission_model.pkl")

def predict_enrollment(features: dict) -> float:
    sanitized = [
        float(features.get("student_questions_count", 0)),
        float(features.get("student_objections_count", 0)),
        float(features.get("positive_statements", 0)),
        float(features.get("negative_statements", 0)),
        float(features.get("budget_mentions", 0)),
        float(features.get("parent_mentions", 0)),
        float(features.get("course_mentions", 0)),
        float(features.get("deadline_interest", 0))
    ]
    values = np.array([sanitized])
    prob = model.predict_proba(values)[0][1]
    return float(prob)
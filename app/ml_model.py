import joblib
import numpy as np

# Load trained XGBoost model
model = joblib.load("training/admission_model.pkl")

def predict_enrollment(features: dict) -> float:
    """
    Predict enrollment probability based on extracted features.

    Parameters:
        features (dict): Dictionary containing all structured features
                         extracted from the transcript.
                         Expected keys:
                         - student_questions_count
                         - student_objections_count
                         - positive_statements
                         - negative_statements
                         - budget_mentions
                         - parent_mentions
                         - course_mentions
                         - deadline_interest (bool)

    Returns:
        float: Probability of enrollment (0.0 - 1.0)
    """
    # Sanitize and convert all features to numeric
    sanitized = [
        float(features.get("student_questions_count", 0)),
        float(features.get("student_objections_count", 0)),
        float(features.get("positive_statements", 0)),
        float(features.get("negative_statements", 0)),
        float(features.get("budget_mentions", 0)),
        float(features.get("parent_mentions", 0)),
        float(features.get("course_mentions", 0)),
        float(features.get("deadline_interest", 0))  # Convert bool to int automatically
    ]

    # XGBoost expects a 2D array: shape (1, n_features)
    values = np.array([sanitized])

    # Predict probability
    prob = model.predict_proba(values)[0][1]
    return float(prob)
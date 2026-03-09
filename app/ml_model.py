import numpy as np

# Try to load model, but make it optional for deployment
try:
    import joblib
    model = joblib.load("training/admission_model.pkl")
    MODEL_AVAILABLE = True
except Exception as e:
    print(f"Warning: ML model not available: {e}")
    MODEL_AVAILABLE = False
    model = None

def predict_enrollment(features: dict) -> float:
    """
    Predict enrollment probability using ML model.
    Falls back to improved rule-based prediction if model is not available.
    """
    if not MODEL_AVAILABLE or model is None:
        # Improved rule-based prediction algorithm
        # Based on conversation analysis patterns
        
        # Extract features
        questions = features.get("student_questions_count", 0)
        objections = features.get("student_objections_count", 0)
        positive = features.get("positive_statements", 0)
        negative = features.get("negative_statements", 0)
        budget = features.get("budget_mentions", 0)
        parents = features.get("parent_mentions", 0)
        course = features.get("course_mentions", 0)
        deadline = features.get("deadline_interest", 0)
        
        # Calculate engagement score with balanced weights
        score = 0.0
        
        # Positive indicators
        score += questions * 3        # 3 points per question
        score += positive * 8         # 8 points per positive statement  
        score += course * 6           # 6 points per course mention
        score += 10 if deadline else 0  # 10 points for deadline interest
        score += parents * 3          # 3 points per parent mention
        
        # Negative indicators
        score -= objections * 12      # -12 points per objection
        score -= negative * 10        # -10 points per negative statement
        
        # Normalize to 0-1 probability
        # Typical score range: -40 to +60
        # Map to probability range: 0.05 to 0.95
        
        # Use a sigmoid-like transformation for realistic probabilities
        # Center point at score=20 (50% probability)
        if score < -20:
            probability = 0.05 + (score + 40) * 0.01  # Very low
        elif score < 0:
            probability = 0.15 + (score + 20) * 0.0175  # Low to medium-low
        elif score < 20:
            probability = 0.50 + score * 0.0125  # Medium to medium-high
        elif score < 40:
            probability = 0.75 + (score - 20) * 0.0075  # High
        else:
            probability = 0.90 + min((score - 40) * 0.0025, 0.05)  # Very high
        
        probability = min(max(probability, 0.0), 1.0)
        
        return float(probability)
    
    # Use ML model if available
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
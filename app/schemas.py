from pydantic import BaseModel

class ConversationFeatures(BaseModel):
    student_questions_count: int
    student_objections_count: int
    positive_statements: int
    negative_statements: int
    budget_mentions: int
    parent_mentions: int
    course_mentions: int
    deadline_interest: bool

class AnalysisResponse(BaseModel):
    intent: str
    confidence_score: float
    interest_level: str
    enrollment_probability: float

    features: ConversationFeatures
    objections: list
    reasons: list
    recommendations: list
    follow_up_priority: str
    summary: str
    transcript: str
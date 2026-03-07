FEATURE_PROMPT = """
You are analyzing a university admission conversation.

Transcript:
{transcript}

Extract structured features:

student_questions_count
student_objections_count
positive_statements
negative_statements
budget_mentions
parent_mentions
course_mentions
deadline_interest

intent
confidence_score
interest_level
reasons
objections
summary

Respond ONLY in JSON.
"""
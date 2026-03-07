import pandas as pd
import random

rows = []

for _ in range(1000):
    student_questions_count = random.randint(0,6)
    student_objections_count = random.randint(0,4)
    positive_statements = random.randint(0,5)
    negative_statements = random.randint(0,4)
    budget_mentions = random.randint(0,2)
    parent_mentions = random.randint(0,2)
    course_mentions = random.randint(0,5)
    deadline_interest = random.randint(0,1)

    score = (student_questions_count*2 + positive_statements*2 + course_mentions + deadline_interest*2
            - student_objections_count*2 - negative_statements - budget_mentions)
    enrolled = 1 if score > 3 else 0

    rows.append({
        "student_questions_count": student_questions_count,
        "student_objections_count": student_objections_count,
        "positive_statements": positive_statements,
        "negative_statements": negative_statements,
        "budget_mentions": budget_mentions,
        "parent_mentions": parent_mentions,
        "course_mentions": course_mentions,
        "deadline_interest": deadline_interest,
        "enrolled": enrolled
    })

df = pd.DataFrame(rows)
df.to_csv("admission_training_data.csv", index=False)
print("Dataset generated")
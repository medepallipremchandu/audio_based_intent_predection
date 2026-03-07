def generate_recommendations(features, objections):
    rec = []

    if features["budget_mentions"] > 0:
        rec.append("Offer scholarship or financial aid options")
    if features["parent_mentions"] > 0:
        rec.append("Arrange call with parents")
    if features["student_questions_count"] > 3:
        rec.append("Send detailed course brochure")
    if features["deadline_interest"]:
        rec.append("Send admission link immediately")
    if len(objections) > 0:
        rec.append("Schedule follow-up counseling session")
    if not rec:
        rec.append("Send general admission information")

    return rec
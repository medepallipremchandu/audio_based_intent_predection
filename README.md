# University Admission Call Analysis AI

## Overview

This project builds an AI system that analyzes recorded conversations between a **university salesperson and a student** to determine whether the student is likely to enroll.

The system processes audio calls, transcribes them, extracts structured features from the conversation, and predicts student intent along with actionable recommendations for the admissions team.

The system is implemented using **FastAPI** and **Azure OpenAI models**.

---

# System Architecture

Audio File
↓
Speech Transcription (Whisper)
↓
Conversation Analysis (GPT-4)
↓
Feature Extraction
↓
Admission Intent Analysis
↓
Recommendation Engine
↓
Structured JSON Output

---

# Technologies Used

Speech Transcription: Whisper via Azure OpenAI
Conversation Analysis: GPT-4 via Azure OpenAI
API Framework: FastAPI
Configuration Management: Python Dotenv

---

# Project Structure

```
admission_call_ai/

├── app/
│
│   ├── main.py
│   ├── config.py
│   ├── analyzer.py
│   ├── whisper_service.py
│   ├── gpt_service.py
│   ├── prompts.py
│   ├── recommendation_engine.py
│   ├── schemas.py
│
├── uploads/
│
├── requirements.txt
├── .env
└── README.md
```

---

# Installation Guide

## 1. Clone or create the project

```
mkdir admission_call_ai
cd admission_call_ai
```

---

## 2. Create Python Virtual Environment

```
python -m venv venv
```

Activate:

Mac/Linux

```
source venv/bin/activate
```

Windows

```
venv\Scripts\activate
```

---

## 3. Install Dependencies

```
pip install -r requirements.txt
```

---

# requirements.txt

```
fastapi
uvicorn
python-multipart
python-dotenv
openai
pydantic
```

---

# Environment Configuration

Create a `.env` file.

```
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT=gpt4

AZURE_OPENAI_WHISPER_KEY=
AZURE_OPENAI_WHISPER_ENDPOINT=
AZURE_OPENAI_WHISPER_DEPLOYMENT=whisper
AZURE_OPENAI_WHISPER_API_VERSION=2024-02-15-preview
```

---

# Features Extracted From Conversation

The system extracts structured features to understand the student’s level of interest.

| Feature                  | Description                              |
| ------------------------ | ---------------------------------------- |
| student_questions_count  | Number of questions asked by the student |
| student_objections_count | Number of objections raised              |
| positive_statements      | Positive responses from student          |
| negative_statements      | Negative responses from student          |
| budget_mentions          | Mentions of fees or affordability        |
| parent_mentions          | References to parents/guardians          |
| course_mentions          | Mentions of course or program            |
| deadline_interest        | Whether student asked about deadlines    |

---

# Output Metrics

The system produces multiple insights:

Intent
Confidence Score
Interest Level
Enrollment Probability
Student Objections
Reasons for Interest
Recommended Actions

---

# Recommendation Engine

The recommendation engine generates suggestions for the admission team.

Examples:

If budget mentions exist
→ Suggest scholarship or financial aid discussion

If parents mentioned
→ Schedule parent counseling call

If many questions asked
→ Send detailed course brochure

If deadline interest detected
→ Send admission link immediately

If objections present
→ Arrange follow-up counseling

---

# Running the Server

Start the FastAPI server.

```
uvicorn app.main:app --reload
```

Server runs at:

```
http://localhost:8000
```

---

# API Documentation

Open interactive API documentation:

```
http://localhost:8000/docs
```

This provides a UI to upload audio files and test the API.

---

# API Endpoint

POST `/analyze-call`

Request Type: multipart/form-data

Input:
Audio File

Supported Formats:
wav
mp3
m4a
aac
ogg

---

# Example API Response

```
{
 "intent": "interested",
 "confidence_score": 0.87,
 "interest_level": "high",

 "enrollment_probability": 0.78,

 "features": {
  "student_questions_count": 4,
  "student_objections_count": 1,
  "positive_statements": 3,
  "negative_statements": 0,
  "budget_mentions": 1,
  "parent_mentions": 1,
  "course_mentions": 2,
  "deadline_interest": true
 },

 "recommendations": [
  "Offer scholarship or financial aid options",
  "Arrange call with parents",
  "Send detailed course brochure",
  "Send admission link immediately"
 ],

 "summary": "Student interested but discussing budget with parents."
}
```

---

# How the System Works

Step 1: Upload audio recording of the call.

Step 2: Whisper model converts speech into text.

Step 3: GPT-4 analyzes the transcript.

Step 4: Conversation features are extracted.

Step 5: Recommendation engine generates admission team suggestions.

Step 6: API returns structured analysis.

---

# Recommended Production Improvements

To improve accuracy and intelligence, the following upgrades can be implemented.

## Speaker Diarization

Identify who is speaking (salesman vs student).

Benefits:

* More accurate intent detection
* Better question tracking
* Improved analytics

---

## Audio Engagement Analysis

Extract behavioral signals from the audio.

Possible metrics:

Talk ratio
Speech rate
Silence duration
Interruptions
Confidence level

---

## Machine Learning Admission Prediction

Use a model trained on historical admissions data.

Example algorithms:

XGBoost
LightGBM

This predicts:

Enrollment probability based on conversation patterns.

---

# Future Enhancements

Real-time call analysis
Agent performance scoring
Lead qualification scoring
Admission dashboard for counselors
Call analytics reporting

---

# Summary

This system allows universities to automatically analyze admission calls and understand:

Student interest level
Likelihood of enrollment
Key objections and concerns
Recommended next actions

The system improves admission team efficiency and enables data-driven follow-ups.

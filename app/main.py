from fastapi import FastAPI, UploadFile, File
import uuid, os, shutil
from app.analyzer import analyze_call

app = FastAPI(title="University Admission Call AI")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/analyze-call")
async def analyze(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    path = f"{UPLOAD_DIR}/{file_id}_{file.filename}"
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = analyze_call(path)
    return result
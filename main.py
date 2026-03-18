import uuid
import os
import shutil
import logging
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes.analyze import run_pipeline
from app.routes.analyze_text import run_text_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("voxintent")

UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="VoxIntent AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://voxintentai.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "VoxIntent AI", "status": "running", "docs": "/docs"}


@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    request_id = str(uuid.uuid4())
    path = f"{UPLOAD_DIR}/{request_id}_{file.filename}"
    try:
        with open(path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)
        logger.info(f"request_id={request_id} file={file.filename} started")
        result = run_pipeline(path)
        logger.info(f"request_id={request_id} completed")
        return result
    except Exception as e:
        logger.exception(f"request_id={request_id} failed")
        return JSONResponse(
            status_code=500,
            content={"error": {"type": e.__class__.__name__, "message": str(e)}, "request_id": request_id},
        )
    finally:
        if os.path.exists(path):
            os.remove(path)


@app.post("/analyze-text")
async def analyze_text(text: str = Form(...)):
    request_id = str(uuid.uuid4())
    try:
        logger.info(f"request_id={request_id} text-analysis started words={len(text.split())}")
        result = run_text_pipeline(text)
        logger.info(f"request_id={request_id} completed")
        return result
    except Exception as e:
        logger.exception(f"request_id={request_id} failed")
        return JSONResponse(
            status_code=500,
            content={"error": {"type": e.__class__.__name__, "message": str(e)}, "request_id": request_id},
        )

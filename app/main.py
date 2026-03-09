from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uuid, os, shutil, logging
from fastapi.responses import JSONResponse
from app.analyzer import analyze_call

app = FastAPI(title="University Admission Call AI")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
logger = logging.getLogger("admission_call_ai")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    fh = logging.FileHandler(os.path.join(LOG_DIR, "app.log"))
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    logger.addHandler(ch)
    logger.addHandler(fh)

@app.post("/analyze-call")
async def analyze(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    path = f"{UPLOAD_DIR}/{file_id}_{file.filename}"
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        logger.info(f"analyze_call start request_id={file_id} filename={file.filename}")
        result = analyze_call(path)
        logger.info(f"analyze_call success request_id={file_id}")
        return result
    except Exception as e:
        logger.exception(f"analyze_call error request_id={file_id}")
        return JSONResponse(
            status_code=500,
            content={
                "error": {"type": e.__class__.__name__, "message": str(e)},
                "request_id": file_id,
            },
        )
    finally:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"upload removed request_id={file_id} path={path}")
        except Exception as de:
            logger.warning(f"upload remove failed request_id={file_id} error={de}")

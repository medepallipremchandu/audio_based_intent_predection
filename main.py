from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uuid, os, shutil, logging
from fastapi.responses import JSONResponse

from app.analyzer import analyze_call

app = FastAPI(title="University Admission Call AI")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://voxintentai.vercel.app",
        "https://*.vercel.app"  # Allow all Vercel preview deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use /tmp for serverless environment
UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Configure logging for serverless
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("admission_call_ai")

@app.get("/")
async def root():
    return {
        "message": "VoxIntent AI - Audio Analysis API",
        "status": "running",
        "endpoints": {
            "analyze": "/analyze-call",
            "docs": "/docs"
        }
    }

@app.post("/analyze-call")
async def analyze(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    path = f"{UPLOAD_DIR}/{file_id}_{file.filename}"
    
    try:
        # Save uploaded file
        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
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
        # Cleanup uploaded file
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"upload removed request_id={file_id} path={path}")
        except Exception as de:
            logger.warning(f"upload remove failed request_id={file_id} error={de}")

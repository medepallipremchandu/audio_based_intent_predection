import datetime
import csv
import difflib
import hashlib
import hmac
import io
import json
import logging
import os
import re
import shutil
import uuid
from typing import Annotated, Any

import jwt
from openai import AzureOpenAI
from fastapi import Depends, FastAPI, File, Form, HTTPException, Header, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, create_engine, func, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from app.config.settings import settings
from app.routes.analyze import run_pipeline
from app.routes.analyze_text import run_text_pipeline
from app.services.linguistics import extract_linguistic_features
from app.services.social_collect import (
    clear_social_probe_cache,
    get_live_social_connection_flags,
    merge_preview,
    parse_keywords_csv,
)

TOPIC_LEXICON_LABEL = "standard"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("voxintent")

UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="VoxIntent AI")
engine = create_engine(settings.DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
_nl_filter_ai_client = AzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    api_version=settings.AZURE_OPENAI_API_VERSION,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
)


class Base(DeclarativeBase):
    pass


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    roles: Mapped[list["Role"]] = relationship(secondary="user_roles", back_populates="users")


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255))
    users: Mapped[list[User]] = relationship(secondary="user_roles", back_populates="roles")
    permissions: Mapped[list["Permission"]] = relationship(secondary="role_permissions", back_populates="roles")


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tab_key: Mapped[str | None] = mapped_column(String(80))
    roles: Mapped[list[Role]] = relationship(secondary="role_permissions", back_populates="permissions")


class Feedback(Base):
    __tablename__ = "feedbacks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    original_message: Mapped[str | None] = mapped_column(Text)
    audio_file: Mapped[str | None] = mapped_column(String(255))
    audio_blob: Mapped[bytes | None] = mapped_column(LargeBinary)
    audio_mime: Mapped[str | None] = mapped_column(String(120))
    input_type: Mapped[str] = mapped_column(String(20), default="text")
    analysis_json: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(80))
    sentiment: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="soon")
    priority: Mapped[str] = mapped_column(String(30), default="medium")
    source_id: Mapped[int | None] = mapped_column(ForeignKey("feedback_sources.id", ondelete="SET NULL"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    course_code: Mapped[str | None] = mapped_column(String(80))
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    whisper_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    gpt_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FeedbackSource(Base):
    __tablename__ = "feedback_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://voxintentai.vercel.app",
    ],
    # Needed for Vercel preview/prod domains; wildcard entries in allow_origins are not matched literally.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_permissions(user: User) -> set[str]:
    permissions: set[str] = set()
    for role in user.roles:
        for permission in role.permissions:
            permissions.add(permission.key)
    return permissions


def get_or_create_anonymous_user(db: Session) -> User:
    anonymous = db.scalar(select(User).where(User.email == "anonymous@local.dev"))
    if anonymous:
        return anonymous
    anonymous = User(
        name="Anonymous User",
        email="anonymous@local.dev",
        password_hash=hash_password(uuid.uuid4().hex),
        is_active=True,
    )
    db.add(anonymous)
    db.commit()
    db.refresh(anonymous)
    return anonymous


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def current_user_from_header(authorization: Annotated[str | None, Header()] = None):
    return authorization


def auth_user(
    authorization: Annotated[str | None, Depends(current_user_from_header)],
    db: Session = Depends(get_db),
) -> User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = authorization.replace("Bearer ", "").strip()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user


def require_permissions(required: set[str]):
    def checker(user: User = Depends(auth_user)) -> User:
        permissions = get_user_permissions(user)
        if "system.superadmin" in permissions:
            return user
        missing = [perm for perm in required if perm not in permissions]
        if missing:
            raise HTTPException(status_code=403, detail=f"Missing permissions: {', '.join(missing)}")
        return user

    return checker


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CreateUserRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role_ids: list[int]


class CreateRoleRequest(BaseModel):
    name: str
    description: str | None = None
    permission_ids: list[int] = []


class UpdateRolePermissionsRequest(BaseModel):
    permission_ids: list[int]


class CreatePermissionRequest(BaseModel):
    key: str
    label: str
    description: str | None = None
    tab_key: str | None = None


class CreateFeedbackRequest(BaseModel):
    message: str
    source_id: int | None = None
    department_id: int | None = None
    course_code: str | None = None


class SocialPreviewRequest(BaseModel):
    start_date: datetime.date
    end_date: datetime.date
    platforms: list[str]
    keywords: str = Field(..., min_length=1, max_length=8000)
    include_reddit_comments: bool = False
    limit_per_subreddit: int = 30
    consent_fetch_public_data: bool = False

    @field_validator("platforms")
    @classmethod
    def _platforms(cls, v: list[str]) -> list[str]:
        allowed = {"reddit", "bluesky", "facebook"}
        out = sorted({p.lower().strip() for p in v if p.lower().strip() in allowed})
        if not out:
            raise ValueError("Select at least one platform: reddit, bluesky, facebook")
        return list(out)

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("Date range too wide (max 366 days)")
        lim = int(self.limit_per_subreddit)
        if lim < 5 or lim > 100:
            raise ValueError("limit_per_subreddit must be between 5 and 100")
        return self


class SocialImportItem(BaseModel):
    import_key: str
    platform: str
    post_id: str
    channel: str
    university_matched: str
    post_type: str
    title: str | None = None
    content: str
    timestamp_utc: str
    url: str
    author: str = ""
    run_ai_analysis: bool = Field(
        default=False,
        description="If true, run Azure text sentiment on this row only (uses quota).",
    )


class SocialImportRequest(BaseModel):
    items: list[SocialImportItem]
    source_id: int | None = None
    department_id: int | None = None

    @field_validator("items")
    @classmethod
    def _cap(cls, v: list[SocialImportItem]) -> list[SocialImportItem]:
        if len(v) > 50:
            raise ValueError("Maximum 50 items per import batch")
        return v


class UpdateFeedbackRequest(BaseModel):
    status: str | None = None
    assigned_to: int | None = None
    priority: str | None = None


class UpdateUserRequest(BaseModel):
    is_active: bool | None = None
    role_ids: list[int] | None = None
    password: str | None = None


class NaturalLanguageFilterRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1200)


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    iterations = 390000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash.startswith("pbkdf2_sha256$"):
        return False
    try:
        _, iterations_str, salt, stored_digest = stored_hash.split("$", 3)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations_str),
        ).hex()
        return hmac.compare_digest(digest, stored_digest)
    except Exception:
        return False


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


@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Backward-compatibility for the initial bcrypt seed that can fail with newer bcrypt packages.
    if user.password_hash.startswith("$2") and user.email == "superadmin@local.dev" and payload.password == "SuperAdmin@123":
        user.password_hash = hash_password(payload.password)
        db.commit()
        db.refresh(user)

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user)
    return {"token": token}


@app.get("/auth/me")
def me(user: User = Depends(auth_user)):
    permissions = sorted(get_user_permissions(user))
    roles = [{"id": role.id, "name": role.name} for role in user.roles]
    tabs = sorted({perm.tab_key for role in user.roles for perm in role.permissions if perm.tab_key})
    return {"id": user.id, "name": user.name, "email": user.email, "roles": roles, "permissions": permissions, "tabs": tabs}


@app.get("/admin/permissions")
def list_permissions(_: User = Depends(require_permissions({"permissions.view"})), db: Session = Depends(get_db)):
    perms = db.scalars(select(Permission).order_by(Permission.key)).all()
    return [{"id": p.id, "key": p.key, "label": p.label, "description": p.description, "tab_key": p.tab_key} for p in perms]


@app.post("/admin/permissions")
def create_permission(payload: CreatePermissionRequest, _: User = Depends(require_permissions({"permissions.manage"})), db: Session = Depends(get_db)):
    permission = Permission(
        key=payload.key.strip(),
        label=payload.label.strip(),
        description=(payload.description or "").strip() or None,
        tab_key=payload.tab_key,
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return {"id": permission.id}


@app.get("/admin/roles")
def list_roles(_: User = Depends(require_permissions({"roles.view"})), db: Session = Depends(get_db)):
    roles = db.scalars(select(Role).order_by(Role.name)).all()
    out = []
    for role in roles:
        out.append({
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "permissions": [{"id": p.id, "key": p.key, "label": p.label} for p in role.permissions],
        })
    return out


@app.post("/admin/roles")
def create_role(payload: CreateRoleRequest, _: User = Depends(require_permissions({"roles.manage"})), db: Session = Depends(get_db)):
    role = Role(name=payload.name.strip(), description=payload.description)
    if payload.permission_ids:
        role.permissions = db.scalars(select(Permission).where(Permission.id.in_(payload.permission_ids))).all()
    db.add(role)
    db.commit()
    db.refresh(role)
    return {"id": role.id}


@app.patch("/admin/roles/{role_id}")
def update_role(role_id: int, payload: CreateRoleRequest, _: User = Depends(require_permissions({"roles.manage"})), db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    role.name = payload.name.strip()
    role.description = payload.description
    role.permissions = db.scalars(select(Permission).where(Permission.id.in_(payload.permission_ids))).all()
    db.commit()
    db.refresh(role)
    return {"id": role.id}


@app.delete("/admin/roles/{role_id}")
def delete_role(role_id: int, _: User = Depends(require_permissions({"roles.delete"})), db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.name == "superadmin":
        raise HTTPException(status_code=400, detail="Superadmin role cannot be deleted")
    db.delete(role)
    db.commit()
    return {"success": True}


@app.put("/admin/roles/{role_id}/permissions")
def update_role_permissions(role_id: int, payload: UpdateRolePermissionsRequest, _: User = Depends(require_permissions({"roles.manage"})), db: Session = Depends(get_db)):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    permissions = db.scalars(select(Permission).where(Permission.id.in_(payload.permission_ids))).all()
    role.permissions = permissions
    db.commit()
    return {"success": True}


@app.get("/admin/users")
def list_users(
    search: str = "",
    page: int = 1,
    page_size: int = 10,
    _: User = Depends(require_permissions({"users.view"})),
    db: Session = Depends(get_db),
):
    stmt = select(User).order_by(User.created_at.desc())
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(User.name.ilike(like), User.email.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    users = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [{
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "roles": [{"id": role.id, "name": role.name} for role in user.roles],
            "active": user.is_active,
        } for user in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.post("/admin/users")
def create_user(payload: CreateUserRequest, _: User = Depends(require_permissions({"users.manage"})), db: Session = Depends(get_db)):
    hashed = hash_password(payload.password)
    user = User(name=payload.name.strip(), email=payload.email, password_hash=hashed, is_active=True)
    roles = db.scalars(select(Role).where(Role.id.in_(payload.role_ids))).all()
    user.roles = roles
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id}


@app.patch("/admin/users/{user_id}")
def update_user(user_id: int, payload: UpdateUserRequest, _: User = Depends(require_permissions({"users.manage"})), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.password_hash = hash_password(payload.password)
    if payload.role_ids is not None:
        roles = db.scalars(select(Role).where(Role.id.in_(payload.role_ids))).all()
        user.roles = roles
    db.commit()
    db.refresh(user)
    return {"id": user.id, "active": user.is_active, "roles": [role.name for role in user.roles]}


@app.delete("/admin/users/{user_id}")
def delete_user(user_id: int, current: User = Depends(require_permissions({"users.delete"})), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if user.email == "superadmin@local.dev":
        raise HTTPException(status_code=400, detail="Default superadmin account cannot be deleted")
    db.delete(user)
    db.commit()
    return {"success": True}


@app.post("/feedback")
def create_feedback(payload: CreateFeedbackRequest, user: User = Depends(require_permissions({"feedback.create"})), db: Session = Depends(get_db)):
    intent = None
    sentiment = None
    analysis_payload = {}
    try:
        analysis = run_text_pipeline(payload.message)
        analysis_block = analysis.get("analysis", {})
        intent = analysis_block.get("primary_topic")
        sentiment = analysis_block.get("overall_sentiment")
        usage = analysis.get("usage", {})
        transcript = analysis.get("transcript", payload.message)
        analysis_payload = {
            "transcript": redact_sensitive_text(transcript),
            "transcript_original": transcript,
            "analysis": redact_analysis_obj(analysis_block),
            "analysis_original": analysis_block,
            "usage": usage,
        }
        priority = derive_priority(analysis_block)
    except Exception:
        usage = {}
        priority = "medium"
        logger.warning("Text analysis failed, feedback created without intent/sentiment")
    feedback = Feedback(
        title=make_title(payload.message),
        message=redact_sensitive_text(payload.message),
        original_message=payload.message,
        input_type="text",
        analysis_json=json.dumps(analysis_payload) if analysis_payload else None,
        priority=priority,
        source_id=payload.source_id,
        department_id=payload.department_id,
        course_code=normalize_course_code(payload.course_code),
        submitted_by=user.id,
        intent=intent,
        sentiment=sentiment,
        whisper_cost_usd=float(usage.get("whisper_cost_usd", 0) or 0),
        gpt_cost_usd=float(usage.get("gpt_cost_usd", 0) or 0),
        total_cost_usd=float(usage.get("total_cost_usd", 0) or 0),
        status="soon",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"id": feedback.id, "message": "Feedback submitted successfully"}


@app.post("/feedback/bulk-csv")
async def create_feedback_bulk_csv(
    file: UploadFile = File(...),
    source_id: int | None = Form(default=None),
    department_id: int | None = Form(default=None),
    course_code: str | None = Form(default=None),
    user: User = Depends(require_permissions({"feedback.create", "feedback.bulk_csv"})),
    db: Session = Depends(get_db),
):
    name = (file.filename or "").lower()
    if not name.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV uploads are supported.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    try:
        decoded = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.")

    reader = csv.DictReader(io.StringIO(decoded))
    headers = [h.strip().lower() for h in (reader.fieldnames or []) if h]
    if "text" not in headers:
        raise HTTPException(status_code=400, detail='CSV must include a "text" column.')

    sources = db.scalars(select(FeedbackSource)).all()
    departments = db.scalars(select(Department)).all()
    source_by_name = {s.name.strip().lower(): s.id for s in sources if s.name}
    department_by_name = {d.name.strip().lower(): d.id for d in departments if d.name}

    def _parse_id(raw, by_name: dict[str, int], fallback: int | None):
        if raw is None:
            return fallback
        val = str(raw).strip()
        if not val:
            return fallback
        if val.isdigit():
            return int(val)
        return by_name.get(val.lower(), fallback)

    created = 0
    for i, row in enumerate(reader, start=1):
        if i > 500:
            raise HTTPException(status_code=400, detail="CSV row limit exceeded (max 500 rows).")
        row_lc = {(k or "").strip().lower(): v for k, v in row.items()}
        text_value = (row_lc.get("text") or "").strip()
        if not text_value:
            continue
        if len(text_value) < 10:
            raise HTTPException(status_code=400, detail=f"Row {i}: text must be at least 10 characters.")

        row_source_id = _parse_id(row_lc.get("source_id") or row_lc.get("source"), source_by_name, source_id)
        row_department_id = _parse_id(row_lc.get("department_id") or row_lc.get("department"), department_by_name, department_id)
        row_course_code = (row_lc.get("course_code") or "").strip() or course_code

        intent = None
        sentiment = None
        analysis_payload = {}
        try:
            analysis = run_text_pipeline(text_value)
            analysis_block = analysis.get("analysis", {})
            intent = analysis_block.get("primary_topic")
            sentiment = analysis_block.get("overall_sentiment")
            usage = analysis.get("usage", {})
            transcript = analysis.get("transcript", text_value)
            analysis_payload = {
                "transcript": redact_sensitive_text(transcript),
                "transcript_original": transcript,
                "analysis": redact_analysis_obj(analysis_block),
                "analysis_original": analysis_block,
                "usage": usage,
            }
            priority = derive_priority(analysis_block)
        except Exception:
            usage = {}
            priority = "medium"
            logger.warning("Bulk text analysis failed for row %s; continuing with fallback values", i)

        feedback = Feedback(
            title=make_title(text_value),
            message=redact_sensitive_text(text_value),
            original_message=text_value,
            input_type="text",
            analysis_json=json.dumps(analysis_payload) if analysis_payload else None,
            priority=priority,
            source_id=row_source_id,
            department_id=row_department_id,
            course_code=normalize_course_code(row_course_code),
            submitted_by=user.id,
            intent=intent,
            sentiment=sentiment,
            whisper_cost_usd=float(usage.get("whisper_cost_usd", 0) or 0),
            gpt_cost_usd=float(usage.get("gpt_cost_usd", 0) or 0),
            total_cost_usd=float(usage.get("total_cost_usd", 0) or 0),
            status="soon",
        )
        db.add(feedback)
        created += 1

    if created == 0:
        raise HTTPException(status_code=400, detail='No valid rows found. Ensure CSV has non-empty "text" values.')

    db.commit()
    return {"imported": created, "message": "Bulk CSV feedback imported successfully"}


@app.post("/feedback/public")
def create_public_feedback(payload: CreateFeedbackRequest, db: Session = Depends(get_db)):
    anonymous_user = get_or_create_anonymous_user(db)
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    normalized_source_id = payload.source_id
    if normalized_source_id is None:
        anonymous_source = db.scalar(select(FeedbackSource).where(FeedbackSource.name == "Anonymous Submission"))
        normalized_source_id = anonymous_source.id if anonymous_source else None
    intent = None
    sentiment = None
    analysis_payload = {}
    try:
        analysis = run_text_pipeline(payload.message)
        analysis_block = analysis.get("analysis", {})
        intent = analysis_block.get("primary_topic")
        sentiment = analysis_block.get("overall_sentiment")
        usage = analysis.get("usage", {})
        transcript = analysis.get("transcript", payload.message)
        analysis_payload = {
            "transcript": redact_sensitive_text(transcript),
            "transcript_original": transcript,
            "analysis": redact_analysis_obj(analysis_block),
            "analysis_original": analysis_block,
            "usage": usage,
        }
        priority = derive_priority(analysis_block)
    except Exception:
        usage = {}
        priority = "medium"
        logger.warning("Public text analysis failed, feedback created without intent/sentiment")
    feedback = Feedback(
        title=make_title(payload.message),
        message=redact_sensitive_text(payload.message),
        original_message=payload.message,
        input_type="text",
        analysis_json=json.dumps(analysis_payload) if analysis_payload else None,
        priority=priority,
        source_id=normalized_source_id,
        department_id=payload.department_id,
        course_code=normalize_course_code(payload.course_code),
        submitted_by=anonymous_user.id,
        intent=intent,
        sentiment=sentiment,
        whisper_cost_usd=float(usage.get("whisper_cost_usd", 0) or 0),
        gpt_cost_usd=float(usage.get("gpt_cost_usd", 0) or 0),
        total_cost_usd=float(usage.get("total_cost_usd", 0) or 0),
        status="soon",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"id": feedback.id, "message": "Feedback submitted successfully"}


@app.post("/feedback/audio")
async def create_audio_feedback(
    message: str = Form(""),
    source_id: int | None = Form(default=None),
    department_id: int | None = Form(default=None),
    course_code: str | None = Form(default=None),
    file: UploadFile = File(...),
    user: User = Depends(require_permissions({"feedback.create"})),
    db: Session = Depends(get_db),
):
    request_id = str(uuid.uuid4())
    path = f"{UPLOAD_DIR}/{request_id}_{file.filename}"
    audio_bytes = await file.read()
    intent = None
    sentiment = None
    transcript = message
    usage: dict = {}
    analysis_payload = {}
    try:
        with open(path, "wb") as buf:
            buf.write(audio_bytes)
        result = run_pipeline(path)
        analysis = result.get("analysis", {})
        intent = analysis.get("primary_topic")
        sentiment = analysis.get("overall_sentiment")
        transcript = transcript or result.get("transcript", "")
        usage = result.get("usage", {})
        priority = derive_priority(analysis)
        analysis_payload = {
            "transcript": redact_sensitive_text(transcript),
            "transcript_original": transcript,
            "analysis": redact_analysis_obj(analysis),
            "analysis_original": analysis,
            "usage": usage,
            "audio": result.get("audio"),
        }
    except Exception:
        logger.warning("Audio analysis failed, feedback created with fallback values")
        priority = "medium"
    finally:
        if os.path.exists(path):
            os.remove(path)

    feedback = Feedback(
        title=make_title(transcript or "Audio feedback"),
        message=redact_sensitive_text(transcript or "Audio feedback submitted"),
        original_message=transcript or "Audio feedback submitted",
        audio_file=file.filename,
        audio_blob=audio_bytes,
        audio_mime=file.content_type or "audio/mpeg",
        input_type="audio",
        analysis_json=json.dumps(analysis_payload) if analysis_payload else None,
        priority=priority,
        source_id=source_id,
        department_id=department_id,
        course_code=normalize_course_code(course_code),
        submitted_by=user.id,
        intent=intent,
        sentiment=sentiment,
        whisper_cost_usd=float(usage.get("whisper_cost_usd", 0) or 0),
        gpt_cost_usd=float(usage.get("gpt_cost_usd", 0) or 0),
        total_cost_usd=float(usage.get("total_cost_usd", 0) or 0),
        status="soon",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"id": feedback.id, "message": "Audio feedback submitted successfully"}


@app.post("/feedback/public/audio")
async def create_public_audio_feedback(
    message: str = Form(""),
    source_id: int | None = Form(default=None),
    department_id: int | None = Form(default=None),
    course_code: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    anonymous_user = get_or_create_anonymous_user(db)
    normalized_source_id = source_id
    if normalized_source_id is None:
        anonymous_source = db.scalar(select(FeedbackSource).where(FeedbackSource.name == "Anonymous Submission"))
        normalized_source_id = anonymous_source.id if anonymous_source else None
    request_id = str(uuid.uuid4())
    path = f"{UPLOAD_DIR}/{request_id}_{file.filename}"
    audio_bytes = await file.read()
    intent = None
    sentiment = None
    transcript = message
    usage: dict = {}
    analysis_payload = {}
    try:
        with open(path, "wb") as buf:
            buf.write(audio_bytes)
        result = run_pipeline(path)
        analysis = result.get("analysis", {})
        intent = analysis.get("primary_topic")
        sentiment = analysis.get("overall_sentiment")
        transcript = transcript or result.get("transcript", "")
        usage = result.get("usage", {})
        priority = derive_priority(analysis)
        analysis_payload = {
            "transcript": redact_sensitive_text(transcript),
            "transcript_original": transcript,
            "analysis": redact_analysis_obj(analysis),
            "analysis_original": analysis,
            "usage": usage,
            "audio": result.get("audio"),
        }
    except Exception:
        logger.warning("Public audio analysis failed, feedback created with fallback values")
        priority = "medium"
    finally:
        if os.path.exists(path):
            os.remove(path)

    feedback = Feedback(
        title=make_title(transcript or "Audio feedback"),
        message=redact_sensitive_text(transcript or "Audio feedback submitted"),
        original_message=transcript or "Audio feedback submitted",
        audio_file=file.filename,
        audio_blob=audio_bytes,
        audio_mime=file.content_type or "audio/mpeg",
        input_type="audio",
        analysis_json=json.dumps(analysis_payload) if analysis_payload else None,
        priority=priority,
        source_id=normalized_source_id,
        department_id=department_id,
        course_code=normalize_course_code(course_code),
        submitted_by=anonymous_user.id,
        intent=intent,
        sentiment=sentiment,
        whisper_cost_usd=float(usage.get("whisper_cost_usd", 0) or 0),
        gpt_cost_usd=float(usage.get("gpt_cost_usd", 0) or 0),
        total_cost_usd=float(usage.get("total_cost_usd", 0) or 0),
        status="soon",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {"id": feedback.id, "message": "Audio feedback submitted successfully"}


def _safe_audio_filename(name: str | None, feedback_id: int) -> str:
    raw = (name or "").strip() or f"feedback-{feedback_id}.audio"
    raw = re.sub(r"[^\w.\-() ]+", "_", raw)
    raw = raw.replace("..", "_").strip() or f"feedback-{feedback_id}.audio"
    return raw[:200]


@app.get("/feedback/{feedback_id}/audio")
def get_feedback_audio(feedback_id: int, user: User = Depends(auth_user), db: Session = Depends(get_db)):
    feedback = db.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    permissions = get_user_permissions(user)
    can_read_all = "feedback.read_all" in permissions or "system.superadmin" in permissions
    can_read_own = feedback.submitted_by == user.id and "feedback.read_own" in permissions
    can_read_assigned = feedback.assigned_to == user.id and "feedback.read_assigned" in permissions
    if not (can_read_all or can_read_own or can_read_assigned):
        raise HTTPException(status_code=403, detail="Not allowed to access this audio")
    if not feedback.audio_blob:
        raise HTTPException(status_code=404, detail="Audio not available")
    return Response(content=feedback.audio_blob, media_type=feedback.audio_mime or "audio/mpeg")


@app.get("/feedback/{feedback_id}/audio/download")
def download_feedback_audio(feedback_id: int, user: User = Depends(auth_user), db: Session = Depends(get_db)):
    """Same read scope as playback, plus `feedback.audio.download` (or superadmin)."""
    feedback = db.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    permissions = get_user_permissions(user)
    can_read_all = "feedback.read_all" in permissions or "system.superadmin" in permissions
    can_read_own = feedback.submitted_by == user.id and "feedback.read_own" in permissions
    can_read_assigned = feedback.assigned_to == user.id and "feedback.read_assigned" in permissions
    if not (can_read_all or can_read_own or can_read_assigned):
        raise HTTPException(status_code=403, detail="Not allowed to access this audio")
    if "feedback.audio.download" not in permissions and "system.superadmin" not in permissions:
        raise HTTPException(status_code=403, detail="Missing permission to download audio")
    if not feedback.audio_blob:
        raise HTTPException(status_code=404, detail="Audio not available")
    filename = _safe_audio_filename(feedback.audio_file, feedback_id)
    return Response(
        content=feedback.audio_blob,
        media_type=feedback.audio_mime or "audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/feedback/natural-language-filters")
def feedback_natural_language_filters(
    payload: NaturalLanguageFilterRequest,
    _: User = Depends(require_permissions({"feedbackboard.naturallanguagesearch"})),
    db: Session = Depends(get_db),
):
    sources = db.scalars(select(FeedbackSource).where(FeedbackSource.is_active == True).order_by(FeedbackSource.name)).all()  # noqa: E712
    departments = db.scalars(select(Department).where(Department.is_active == True).order_by(Department.name)).all()  # noqa: E712
    source_options = [{"id": str(s.id), "name": s.name or ""} for s in sources]
    department_options = [{"id": str(d.id), "name": d.name or ""} for d in departments]
    source_name_to_id = {str(x["name"]).strip().lower(): str(x["id"]) for x in source_options if str(x["name"]).strip()}
    department_name_to_id = {str(x["name"]).strip().lower(): str(x["id"]) for x in department_options if str(x["name"]).strip()}

    raw_filters = _parse_natural_language_filters_with_ai(payload.query, source_options, department_options)
    normalized = _normalize_nl_filters(
        raw_filters=raw_filters,
        source_ids={x["id"] for x in source_options},
        department_ids={x["id"] for x in department_options},
        source_name_to_id=source_name_to_id,
        department_name_to_id=department_name_to_id,
    )
    return {"filters": normalized}


@app.get("/feedback/mine")
def my_feedback(
    search: str = "",
    status: str | None = None,
    sentiment: str | None = None,
    input_type: str | None = None,
    source_id: int | None = None,
    department_id: int | None = None,
    course_code: str | None = None,
    priority: str | None = None,
    page: int = 1,
    page_size: int = 10,
    user: User = Depends(require_permissions({"feedback.read_own"})),
    db: Session = Depends(get_db),
):
    permissions = get_user_permissions(user)
    stmt = select(Feedback).where(Feedback.submitted_by == user.id).order_by(Feedback.created_at.desc())
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Feedback.title.ilike(like), Feedback.message.ilike(like)))
    if status:
        stmt = stmt.where(Feedback.status == status)
    if sentiment:
        stmt = stmt.where(Feedback.sentiment == sentiment)
    if input_type:
        stmt = stmt.where(Feedback.input_type == input_type)
    if source_id is not None:
        stmt = stmt.where(Feedback.source_id == source_id)
    if department_id is not None:
        stmt = stmt.where(Feedback.department_id == department_id)
    if course_code:
        stmt = stmt.where(Feedback.course_code.ilike(f"%{course_code}%"))
    if priority:
        stmt = stmt.where(Feedback.priority == priority)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    # page_size<=0 means "no limit" (fetch all matching rows).
    items = (
        db.scalars(stmt).all()
        if page_size <= 0
        else db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    )
    if "feedback.sensitive.mask" not in permissions and "system.superadmin" not in permissions:
        changed = False
        for item in items:
            changed = maybe_backfill_unmasked_analysis(item) or changed
        if changed:
            db.commit()
    name_map = submitter_name_map_for_items(db, items, permissions)
    return {"items": [serialize_feedback(it, permissions, submitter_names=name_map) for it in items], "total": total, "page": page, "page_size": page_size}


@app.get("/feedback")
def list_feedback(
    search: str = "",
    status: str | None = None,
    sentiment: str | None = None,
    input_type: str | None = None,
    source_id: int | None = None,
    department_id: int | None = None,
    course_code: str | None = None,
    priority: str | None = None,
    page: int = 1,
    page_size: int = 10,
    user: User = Depends(require_permissions({"feedback.read_all"})),
    db: Session = Depends(get_db),
):
    permissions = get_user_permissions(user)
    stmt = select(Feedback).order_by(Feedback.created_at.desc())
    if "feedback.read_assigned" in get_user_permissions(user) and "feedback.read_all" not in get_user_permissions(user):
        stmt = stmt.where(Feedback.assigned_to == user.id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Feedback.title.ilike(like), Feedback.message.ilike(like)))
    if status:
        stmt = stmt.where(Feedback.status == status)
    if sentiment:
        stmt = stmt.where(Feedback.sentiment == sentiment)
    if input_type:
        stmt = stmt.where(Feedback.input_type == input_type)
    if source_id is not None:
        stmt = stmt.where(Feedback.source_id == source_id)
    if department_id is not None:
        stmt = stmt.where(Feedback.department_id == department_id)
    if course_code:
        stmt = stmt.where(Feedback.course_code.ilike(f"%{course_code}%"))
    if priority:
        stmt = stmt.where(Feedback.priority == priority)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    # page_size<=0 means "no limit" (fetch all matching rows).
    items = (
        db.scalars(stmt).all()
        if page_size <= 0
        else db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    )
    if "feedback.sensitive.mask" not in permissions and "system.superadmin" not in permissions:
        changed = False
        for item in items:
            changed = maybe_backfill_unmasked_analysis(item) or changed
        if changed:
            db.commit()
    name_map = submitter_name_map_for_items(db, items, permissions)
    return {"items": [serialize_feedback(it, permissions, submitter_names=name_map) for it in items], "total": total, "page": page, "page_size": page_size}


@app.patch("/feedback/{feedback_id}")
def update_feedback(feedback_id: int, payload: UpdateFeedbackRequest, user: User = Depends(require_permissions({"feedback.update"})), db: Session = Depends(get_db)):
    feedback = db.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    perms = get_user_permissions(user)
    if payload.assigned_to is not None and "feedback.assign" not in perms and "system.superadmin" not in perms:
        raise HTTPException(status_code=403, detail="Missing feedback.assign")
    if payload.status:
        feedback.status = payload.status
    if payload.priority:
        feedback.priority = payload.priority
    if payload.assigned_to is not None:
        feedback.assigned_to = payload.assigned_to
    db.commit()
    db.refresh(feedback)
    perms = get_user_permissions(user)
    name_map = submitter_name_map_for_items(db, [feedback], perms)
    return serialize_feedback(feedback, perms, submitter_names=name_map)


@app.get("/dashboard/summary")
def dashboard_summary(
    status: str | None = None,
    sentiment: str | None = None,
    input_type: str | None = None,
    source_id: int | None = None,
    department_id: int | None = None,
    priority: str | None = None,
    user: User = Depends(auth_user),
    db: Session = Depends(get_db),
):
    permissions = get_user_permissions(user)
    base = select(Feedback)
    if "feedback.read_all" not in permissions:
        base = base.where(Feedback.submitted_by == user.id)
    if status:
        base = base.where(Feedback.status == status)
    if sentiment:
        base = base.where(Feedback.sentiment == sentiment)
    if input_type:
        base = base.where(Feedback.input_type == input_type)
    if source_id is not None:
        base = base.where(Feedback.source_id == source_id)
    if department_id is not None:
        base = base.where(Feedback.department_id == department_id)
    if priority:
        base = base.where(Feedback.priority == priority)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    completed = db.scalar(select(func.count()).select_from(base.where(Feedback.status == "completed").subquery())) or 0
    inprogress = db.scalar(select(func.count()).select_from(base.where(Feedback.status == "inprogress").subquery())) or 0
    soon = db.scalar(select(func.count()).select_from(base.where(Feedback.status == "soon").subquery())) or 0
    high_priority = db.scalar(select(func.count()).select_from(base.where(Feedback.priority == "high").subquery())) or 0
    text_count = db.scalar(select(func.count()).select_from(base.where(Feedback.input_type == "text").subquery())) or 0
    audio_count = db.scalar(select(func.count()).select_from(base.where(Feedback.input_type == "audio").subquery())) or 0
    resolve_rate = round((completed / total) * 100, 2) if total else 0
    response = {
        "total_feedback": total,
        "completed": completed,
        "inprogress": inprogress,
        "soon": soon,
        "high_priority": high_priority,
        "text_feedback": text_count,
        "audio_feedback": audio_count,
        "resolve_rate": resolve_rate,
    }
    if "ai.cost.view" in permissions or "system.superadmin" in permissions:
        base_sq = base.subquery()
        response["whisper_cost_usd"] = float(db.scalar(select(func.coalesce(func.sum(base_sq.c.whisper_cost_usd), 0)).select_from(base_sq)) or 0)
        response["gpt_cost_usd"] = float(db.scalar(select(func.coalesce(func.sum(base_sq.c.gpt_cost_usd), 0)).select_from(base_sq)) or 0)
        response["total_ai_cost_usd"] = float(db.scalar(select(func.coalesce(func.sum(base_sq.c.total_cost_usd), 0)).select_from(base_sq)) or 0)
    return response


@app.get("/dashboard/aggregates")
def dashboard_aggregates(
    status: str | None = None,
    sentiment: str | None = None,
    input_type: str | None = None,
    source_id: int | None = None,
    department_id: int | None = None,
    priority: str | None = None,
    user: User = Depends(auth_user),
    db: Session = Depends(get_db),
):
    """
    Small aggregate payload for dashboards (sentiment mix + top topics).
    This prevents the frontend from downloading *all* feedback rows.
    """
    permissions = get_user_permissions(user)
    base = select(Feedback)
    if "feedback.read_all" not in permissions:
        base = base.where(Feedback.submitted_by == user.id)
    if status:
        base = base.where(Feedback.status == status)
    if sentiment:
        base = base.where(Feedback.sentiment == sentiment)
    if input_type:
        base = base.where(Feedback.input_type == input_type)
    if source_id is not None:
        base = base.where(Feedback.source_id == source_id)
    if department_id is not None:
        base = base.where(Feedback.department_id == department_id)
    if priority:
        base = base.where(Feedback.priority == priority)

    base_sq = base.subquery()

    # Sentiment counts (null/empty sentiment => neutral)
    sentiment_key = func.lower(func.coalesce(func.nullif(base_sq.c.sentiment, ""), "neutral"))
    total = db.scalar(select(func.count()).select_from(base_sq)) or 0

    sentiment_rows = db.execute(
        select(sentiment_key, func.count()).select_from(base_sq).group_by(sentiment_key)
    ).all()
    sentiment_counts: dict[str, int] = {str(k): int(v) for k, v in sentiment_rows}

    # Top topics: parse analysis_json to extract analysis.analysis.primary_topic (fallback to intent).
    topic_counts: dict[str, int] = {}
    topic_rows = db.execute(select(base_sq.c.analysis_json, base_sq.c.intent).select_from(base_sq)).all()
    for analysis_json, intent in topic_rows:
        topic = None
        if analysis_json:
            try:
                payload = json.loads(analysis_json)
                analysis_block = payload.get("analysis") if isinstance(payload, dict) else {}
                if isinstance(analysis_block, dict):
                    topic = analysis_block.get("primary_topic")
                if not topic:
                    analysis_original = payload.get("analysis_original") if isinstance(payload, dict) else {}
                    if isinstance(analysis_original, dict):
                        topic = analysis_original.get("primary_topic")
            except Exception:
                topic = None
        if not topic:
            topic = intent
        if topic:
            topic_counts[str(topic)] = topic_counts.get(str(topic), 0) + 1

    # Sort by count desc, then topic asc (case-insensitive) for stable ordering.
    top_topics_sorted = sorted(topic_counts.items(), key=lambda kv: (-kv[1], str(kv[0]).lower()))
    top_topics = [{"topic": t, "count": int(c)} for t, c in top_topics_sorted[:8]]

    primary_topic = top_topics_sorted[0][0] if top_topics_sorted else "general feedback trends"
    mixed_like_count = (sentiment_counts.get("mixed", 0) + sentiment_counts.get("neutral", 0) + sentiment_counts.get("inconclusive", 0))
    mixed_like_pct = round((mixed_like_count / total) * 100) if total else 0

    return {
        "total_rows": int(total),
        "sentiment_counts": sentiment_counts,
        "top_topics": top_topics,
        "primary_topic": primary_topic,
        "mixed_like_pct": mixed_like_pct,
    }


@app.get("/dashboard/recent")
def dashboard_recent(
    status: str | None = None,
    sentiment: str | None = None,
    input_type: str | None = None,
    source_id: int | None = None,
    department_id: int | None = None,
    priority: str | None = None,
    page: int = 1,
    page_size: int = 10,
    user: User = Depends(auth_user),
    db: Session = Depends(get_db),
):
    """
    Paginated recent feedback list for dashboard "Latest activity".
    Used by infinite scroll so we don't load the entire dataset.
    """
    permissions = get_user_permissions(user)
    page = max(1, int(page))
    page_size = max(1, int(page_size))

    base = select(Feedback).order_by(Feedback.created_at.desc())
    if "feedback.read_all" not in permissions:
        base = base.where(Feedback.submitted_by == user.id)
    if status:
        base = base.where(Feedback.status == status)
    if sentiment:
        base = base.where(Feedback.sentiment == sentiment)
    if input_type:
        base = base.where(Feedback.input_type == input_type)
    if source_id is not None:
        base = base.where(Feedback.source_id == source_id)
    if department_id is not None:
        base = base.where(Feedback.department_id == department_id)
    if priority:
        base = base.where(Feedback.priority == priority)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    stmt = base.offset((page - 1) * page_size).limit(page_size)
    items = db.scalars(stmt).all()

    if "feedback.sensitive.mask" not in permissions and "system.superadmin" not in permissions:
        changed = False
        for item in items:
            changed = maybe_backfill_unmasked_analysis(item) or changed
        if changed:
            db.commit()

    name_map = submitter_name_map_for_items(db, items, permissions)
    return {
        "items": [serialize_feedback(it, permissions, submitter_names=name_map) for it in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def submitter_name_map_for_items(db: Session, items: list[Feedback], permissions: set[str]) -> dict[int, str] | None:
    """Load submitter display names when the viewer has feedback.submitter.view (or superadmin)."""
    if not ("feedback.submitter.view" in permissions or "system.superadmin" in permissions):
        return None
    ids = {it.submitted_by for it in items if it.submitted_by}
    if not ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(ids))).all()
    return {u.id: u.name for u in users}


def _safe_list_serialize(v):
    if isinstance(v, list):
        return v
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    return []


def enrich_analysis_dict(analysis: dict | None, raw_text: str) -> None:
    """Ensure linguistics (legacy rows only), topic lexicon label, and action_items backfill for API responses."""
    if not isinstance(analysis, dict):
        return
    text = (raw_text or "").strip()
    if text and "linguistics" not in analysis:
        analysis["linguistics"] = extract_linguistic_features(text)
        analysis["linguistics"]["source"] = "heuristic_fallback"
    if "topic_lexicon" not in analysis:
        analysis["topic_lexicon"] = TOPIC_LEXICON_LABEL
    items = _safe_list_serialize(analysis.get("action_items"))
    rec = (analysis.get("recommended_action") or "").strip()
    if not items and rec:
        analysis["action_items"] = [rec]


@app.get("/meta/feedback-form")
def feedback_form_meta(db: Session = Depends(get_db)):
    sources = db.scalars(select(FeedbackSource).where(FeedbackSource.is_active == True).order_by(FeedbackSource.name)).all()  # noqa: E712
    departments = db.scalars(select(Department).where(Department.is_active == True).order_by(Department.name)).all()  # noqa: E712
    return {
        "sources": [{"id": source.id, "name": source.name} for source in sources],
        "departments": [{"id": department.id, "name": department.name} for department in departments],
    }


@app.get("/integrations/social/status")
def social_integration_status(
    refresh: bool = Query(False, description="Bypass cached live probes (forces new network checks)."),
    _: User = Depends(require_permissions({"social_feed.demo"})),
):
    if refresh:
        clear_social_probe_cache()
    live = get_live_social_connection_flags()
    reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    reddit_oauth_configured = bool(reddit_client_id and reddit_client_secret)
    reddit_ua_configured = bool((os.getenv("REDDIT_USER_AGENT") or "").strip())
    bsky_ident = (
        os.getenv("BSKY_IDENTIFIER")
        or os.getenv("BLUESKY_IDENTIFIER")
        or os.getenv("BSKY_HANDLE")
        or os.getenv("BLUESKY_HANDLE")
    )
    bsky_pw = os.getenv("BSKY_APP_PASSWORD") or os.getenv("BLUESKY_APP_PASSWORD")
    bluesky_auth_configured = bool((bsky_ident or "").strip() and (bsky_pw or "").strip())
    fb_token = (os.getenv("FACEBOOK_ACCESS_TOKEN") or "").strip()
    fb_page = (os.getenv("FACEBOOK_PAGE_ID") or "").strip()
    facebook_configured = bool(fb_token and fb_page)
    rs = live["reddit_search_connected"]
    ro = live["reddit_oauth_connected"]
    return {
        "bluesky_available": True,
        "bluesky_auth_configured": bluesky_auth_configured,
        "bluesky_connected": live["bluesky_connected"],
        "reddit_oauth_configured": reddit_oauth_configured,
        "reddit_search_connected": rs,
        "reddit_oauth_connected": ro,
        "reddit_connected": live["reddit_connected"],
        "reddit_public_ready": rs,
        "reddit_user_agent_configured": reddit_ua_configured,
        "facebook_available": True,
        "facebook_configured": facebook_configured,
        "facebook_connected": live["facebook_connected"],
        "facebook_note": (
            "Meta Graph API does not offer public global keyword search. "
            "With FACEBOOK_ACCESS_TOKEN + FACEBOOK_PAGE_ID this demo can fetch posts from that Page only, "
            "filtered by your keywords in the post text."
        ),
        "hint": (
            "Keywords are comma-separated in the UI. Connection badges reflect live checks (cached ~45s; use refresh=1 to retest). "
            "Bluesky: public search may return HTTP 403; BSKY_IDENTIFIER + BSKY_APP_PASSWORD often fixes it. "
            "Reddit search uses a default browser-style User-Agent; set REDDIT_USER_AGENT to override. Comments need OAuth + praw. "
            "Facebook: Page token + Page id only."
        ),
    }


@app.post("/integrations/social/preview")
def social_preview(
    payload: SocialPreviewRequest,
    _: User = Depends(require_permissions({"social_feed.demo"})),
):
    if not payload.consent_fetch_public_data:
        raise HTTPException(
            status_code=400,
            detail="Consent required: set consent_fetch_public_data to true after acknowledging public-data use.",
        )
    try:
        keywords_list = parse_keywords_csv(payload.keywords)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    rows, warnings = merge_preview(
        payload.start_date,
        payload.end_date,
        payload.platforms,
        payload.include_reddit_comments,
        payload.limit_per_subreddit,
        keywords_list,
    )
    return {"rows": rows, "warnings": warnings, "count": len(rows)}


def _social_import_text_for_ai(item: SocialImportItem) -> str:
    """Single text block for GPT: table columns the operator sees in the preview."""
    author = (item.author or "").strip() or "unknown"
    title = (item.title or "").strip()
    content = (item.content or "").strip()
    lines = [
        f"Platform: {(item.platform or '').strip()}",
        f"Channel: {(item.channel or '').strip()}",
        f"Type: {(item.post_type or '').strip()}",
        f"University: {(item.university_matched or '').strip()}",
        f"Author: {author}",
        f"When (UTC): {(item.timestamp_utc or '').strip()}",
        "",
    ]
    if title:
        lines.extend([f"Title: {title}", ""])
    lines.extend(["Content:", content if content else "(empty)", ""])
    lines.append(f"Link: {(item.url or '').strip()}")
    lines.append(f"External post id: {(item.post_id or '').strip()}")
    return "\n".join(lines)


def _persist_social_import(
    db: Session,
    user: User,
    item: SocialImportItem,
    source_id: int | None,
    department_id: int | None,
) -> Feedback:
    plat = (item.platform or "").strip().lower()
    if "reddit" in plat:
        input_type = "reddit"
    elif "facebook" in plat or "meta" in plat:
        input_type = "facebook"
    else:
        input_type = "bluesky"
    raw_title = (item.title or "").strip()
    body = (item.content or "").strip()
    if len(body) < 3:
        raise HTTPException(status_code=400, detail="Each item must include content (min 3 characters).")
    combined = body[:12000]
    footer = (
        f"\n\n— Imported ({item.platform}) · {item.university_matched} · {item.timestamp_utc}\n"
        f"Link: {item.url}\nExternal post id: {item.post_id}"
    )
    message = (combined + footer)[:20000]
    head = raw_title if raw_title else f"{item.channel} · {item.university_matched}"
    display_title = f"[{item.platform}] {head}"[:175]

    if item.run_ai_analysis:
        structured = _social_import_text_for_ai(item)
        pipeline_message = (structured + footer)[:19000]
        message = (structured + footer)[:20000]
        intent = None
        sentiment = None
        analysis_payload: dict = {}
        usage: dict = {}
        priority = "medium"
        try:
            analysis = run_text_pipeline(pipeline_message)
            analysis_block = analysis.get("analysis", {})
            intent = analysis_block.get("primary_topic")
            sentiment = analysis_block.get("overall_sentiment")
            usage = analysis.get("usage", {})
            transcript = analysis.get("transcript", pipeline_message)
            analysis_payload = {
                "transcript": redact_sensitive_text(transcript),
                "transcript_original": transcript,
                "analysis": redact_analysis_obj(analysis_block),
                "analysis_original": analysis_block,
                "usage": usage,
                "social_import": {
                    "import_key": item.import_key,
                    "url": item.url,
                    "channel": item.channel,
                    "post_type": item.post_type,
                    "university_matched": item.university_matched,
                },
            }
            priority = derive_priority(analysis_block)
        except Exception:
            logger.warning("Social import AI analysis failed; saving row without intent/sentiment")
            analysis_payload = {
                "transcript": redact_sensitive_text(message),
                "transcript_original": message,
                "analysis": None,
                "usage": {},
                "social_import": {
                    "import_key": item.import_key,
                    "url": item.url,
                    "channel": item.channel,
                    "post_type": item.post_type,
                    "university_matched": item.university_matched,
                },
            }
        feedback = Feedback(
            title=make_title(display_title),
            message=redact_sensitive_text(message),
            original_message=message,
            input_type=input_type[:20],
            analysis_json=json.dumps(analysis_payload) if analysis_payload else None,
            priority=priority,
            source_id=source_id,
            department_id=department_id,
            course_code=None,
            submitted_by=user.id,
            intent=intent,
            sentiment=sentiment,
            whisper_cost_usd=float(usage.get("whisper_cost_usd", 0) or 0),
            gpt_cost_usd=float(usage.get("gpt_cost_usd", 0) or 0),
            total_cost_usd=float(usage.get("total_cost_usd", 0) or 0),
            status="soon",
        )
        db.add(feedback)
        return feedback

    analysis_payload = {
        "transcript": redact_sensitive_text(message),
        "transcript_original": message,
        "analysis": None,
        "usage": {},
        "social_import": {
            "import_key": item.import_key,
            "url": item.url,
            "channel": item.channel,
            "post_type": item.post_type,
            "university_matched": item.university_matched,
        },
    }
    feedback = Feedback(
        title=make_title(display_title),
        message=redact_sensitive_text(message),
        original_message=message,
        input_type=input_type[:20],
        analysis_json=json.dumps(analysis_payload),
        priority="medium",
        source_id=source_id,
        department_id=department_id,
        course_code=None,
        submitted_by=user.id,
        intent=None,
        sentiment=None,
        whisper_cost_usd=0.0,
        gpt_cost_usd=0.0,
        total_cost_usd=0.0,
        status="soon",
    )
    db.add(feedback)
    return feedback


@app.post("/integrations/social/import")
def social_import(
    payload: SocialImportRequest,
    user: User = Depends(require_permissions({"social_feed.demo", "feedback.create"})),
    db: Session = Depends(get_db),
):
    ids: list[int] = []
    for item in payload.items:
        fb = _persist_social_import(
            db,
            user,
            item,
            payload.source_id,
            payload.department_id,
        )
        db.commit()
        db.refresh(fb)
        ids.append(fb.id)
    return {"imported": len(ids), "feedback_ids": ids}


def serialize_feedback(it: Feedback, permissions: set[str], submitter_names: dict[int, str] | None = None):
    mask_sensitive = "feedback.sensitive.mask" in permissions and "system.superadmin" not in permissions
    can_view_sensitive = not mask_sensitive or "system.superadmin" in permissions
    can_view_analysis = "feedback.analysis.view" in permissions or "system.superadmin" in permissions
    can_view_original_transcript = not mask_sensitive or "system.superadmin" in permissions
    analysis_payload = None
    if it.analysis_json:
        try:
            analysis_payload = json.loads(it.analysis_json)
        except Exception:
            analysis_payload = None
    if analysis_payload and isinstance(analysis_payload, dict):
        raw_for_features = (
            str(analysis_payload.get("transcript_original") or "").strip()
            or str(it.original_message or "").strip()
            or str(it.message or "").strip()
        )
        # transcript selection
        if can_view_original_transcript and analysis_payload.get("transcript_original"):
            analysis_payload["transcript"] = analysis_payload.get("transcript_original")
        else:
            analysis_payload["transcript"] = redact_sensitive_text(str(analysis_payload.get("transcript") or ""))

        # analysis selection (controls positive/negative/evidence/speakers/etc)
        if can_view_sensitive and analysis_payload.get("analysis_original") is not None:
            analysis_payload["analysis"] = analysis_payload.get("analysis_original")
        else:
            analysis_payload["analysis"] = redact_analysis_obj(analysis_payload.get("analysis"))

        if can_view_analysis:
            an = analysis_payload.get("analysis")
            usage_obj = analysis_payload.get("usage") if isinstance(analysis_payload.get("usage"), dict) else {}
            if isinstance(an, dict) and usage_obj:
                gu = an.get("gpt_usage")
                need_backfill = not isinstance(gu, dict) or (
                    int(gu.get("total_tokens") or 0) == 0
                    and int(gu.get("prompt_tokens") or 0) == 0
                )
                if need_backfill and (
                    usage_obj.get("gpt_prompt_tokens") is not None
                    or usage_obj.get("gpt_completion_tokens") is not None
                    or usage_obj.get("gpt_total_tokens") is not None
                ):
                    an["gpt_usage"] = {
                        "prompt_tokens": int(usage_obj.get("gpt_prompt_tokens") or 0),
                        "completion_tokens": int(usage_obj.get("gpt_completion_tokens") or 0),
                        "total_tokens": int(usage_obj.get("gpt_total_tokens") or 0),
                    }
            enrich_analysis_dict(analysis_payload.get("analysis"), raw_for_features)

        viewer_saw_unredacted = bool(can_view_original_transcript and analysis_payload.get("transcript_original"))
        analysis_payload["transcript_privacy"] = build_transcript_privacy_meta(
            str(analysis_payload.get("transcript") or ""),
            viewer_saw_unredacted,
        )

        analysis_payload.pop("transcript_original", None)
        analysis_payload.pop("analysis_original", None)
    submitter_name = None
    if submitter_names is not None and it.submitted_by in submitter_names:
        submitter_name = submitter_names[it.submitted_by]
    return {
        "id": it.id,
        "title": it.title,
        "message": it.original_message if can_view_sensitive and it.original_message else it.message,
        "intent": it.intent,
        "sentiment": it.sentiment,
        "status": it.status,
        "priority": it.priority,
        "input_type": it.input_type,
        "source_id": it.source_id,
        "department_id": it.department_id,
        "course_code": it.course_code,
        "analysis": analysis_payload if can_view_analysis else None,
        "audio_file": it.audio_file,
        "has_audio_blob": bool(it.audio_blob),
        "whisper_cost_usd": it.whisper_cost_usd,
        "gpt_cost_usd": it.gpt_cost_usd,
        "total_cost_usd": it.total_cost_usd,
        "submitted_by": it.submitted_by,
        "submitter_name": submitter_name,
        "assigned_to": it.assigned_to,
        "created_at": it.created_at.isoformat() if it.created_at else None,
        "updated_at": it.updated_at.isoformat() if it.updated_at else None,
    }


def make_title(text: str) -> str:
    clean = " ".join((text or "Feedback").split())
    return clean[:80] if clean else "Feedback"


def normalize_course_code(value: str | None) -> str | None:
    """Normalize and bound course_code to DB-safe length."""
    if value is None:
        return None
    clean = " ".join(str(value).split()).strip()
    if not clean:
        return None
    return clean[:80]


def derive_priority(analysis: dict) -> str:
    if analysis.get("negativity_detected") or analysis.get("conflict_detected"):
        return "high"
    if analysis.get("overall_sentiment") == "negative":
        return "high"
    if analysis.get("overall_sentiment") == "neutral":
        return "medium"
    return "low"


def _extract_first_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {}
    try:
        parsed = json.loads(m.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _coerce_string(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _parse_natural_language_filters_with_ai(
    query: str,
    source_options: list[dict[str, str]],
    department_options: list[dict[str, str]],
) -> dict[str, str]:
    source_text = "\n".join([f'- "{it["name"]}" => "{it["id"]}"' for it in source_options]) or "- none"
    dept_text = "\n".join([f'- "{it["name"]}" => "{it["id"]}"' for it in department_options]) or "- none"
    prompt = f"""
Convert this natural-language query into filter key/value pairs.

FILTER KEYS (allowed):
- status
- sentiment
- input_type
- source_id
- department_id
- priority
- course_code
- search

ALLOWED VALUES:
- status: soon | inprogress | completed
- sentiment: positive | neutral | negative | mixed
- input_type: audio | text | reddit | bluesky | facebook
- priority: high | medium | low
- source_id: use one id from Source options below
- department_id: use one id from Department options below
- course_code/search: plain string only when clearly intended

SOURCE OPTIONS (name => id):
{source_text}

DEPARTMENT OPTIONS (name => id):
{dept_text}

TYPO RULE:
- Correct user spelling mistakes/typos to closest valid values or closest source/department name.
- If confidence is low, omit that key (do not invent).

OUTPUT RULES:
- Return strict JSON only with this shape: {{"filters":{{...}}}}.
- Use only allowed keys and values.
- Omit keys user did not request.
- If user intent says "all" / "any", omit that filter key.

User query:
{query}
"""

    response = _nl_filter_ai_client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You extract structured filter values from user search text."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    raw = (response.choices[0].message.content or "").strip()
    parsed = _extract_first_json_object(raw)
    filters = parsed.get("filters") if isinstance(parsed, dict) else {}
    return filters if isinstance(filters, dict) else {}


def _normalize_nl_filters(
    raw_filters: dict[str, Any],
    source_ids: set[str],
    department_ids: set[str],
    source_name_to_id: dict[str, str],
    department_name_to_id: dict[str, str],
) -> dict[str, str]:
    def _closest_from_allowed(value: str, allowed: set[str]) -> str:
        v = (value or "").strip().lower()
        if not v:
            return ""
        if v in allowed:
            return v
        match = difflib.get_close_matches(v, list(allowed), n=1, cutoff=0.75)
        return match[0] if match else ""

    def _resolve_lookup_value(value: Any, id_set: set[str], name_to_id: dict[str, str]) -> str:
        raw = _coerce_string(value)
        if not raw:
            return ""
        if raw in id_set:
            return raw
        lowered = raw.lower()
        if lowered in name_to_id:
            return name_to_id[lowered]
        # typo-tolerant name mapping
        match = difflib.get_close_matches(lowered, list(name_to_id.keys()), n=1, cutoff=0.75)
        return name_to_id[match[0]] if match else ""

    out: dict[str, str] = {}

    status = _closest_from_allowed(_coerce_string(raw_filters.get("status")), {"soon", "inprogress", "completed"})
    if status:
        out["status"] = status

    sentiment = _closest_from_allowed(_coerce_string(raw_filters.get("sentiment")), {"positive", "neutral", "negative", "mixed"})
    if sentiment:
        out["sentiment"] = sentiment

    input_type = _closest_from_allowed(_coerce_string(raw_filters.get("input_type")), {"audio", "text", "reddit", "bluesky", "facebook"})
    if input_type:
        out["input_type"] = input_type

    priority = _closest_from_allowed(_coerce_string(raw_filters.get("priority")), {"high", "medium", "low"})
    if priority:
        out["priority"] = priority

    source_id = _resolve_lookup_value(raw_filters.get("source_id"), source_ids, source_name_to_id)
    if not source_id:
        source_id = _resolve_lookup_value(raw_filters.get("source"), source_ids, source_name_to_id)
    if source_id:
        out["source_id"] = source_id

    department_id = _resolve_lookup_value(raw_filters.get("department_id"), department_ids, department_name_to_id)
    if not department_id:
        department_id = _resolve_lookup_value(raw_filters.get("department"), department_ids, department_name_to_id)
    if department_id:
        out["department_id"] = department_id

    course_code = _coerce_string(raw_filters.get("course_code"))
    if course_code:
        out["course_code"] = course_code[:80]

    search = _coerce_string(raw_filters.get("search"))
    if search:
        out["search"] = search[:200]

    return out


def redact_sensitive_text(text: str) -> str:
    if not text:
        return ""
    out = text
    out = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[EMAIL]", out)
    out = re.sub(r"\b(?:\+?\d[\d\-\s]{8,}\d)\b", "[PHONE]", out)
    out = re.sub(r"\b(Professor|Dr|Mr|Mrs|Ms)\s+[A-Z][a-zA-Z]+\b", r"\1 [REDACTED]", out)
    out = re.sub(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b", "[NAME]", out)
    return out


_PRIVACY_MARKERS = ("[REDACTED]", "[EMAIL]", "[PHONE]", "[NAME]")


def build_transcript_privacy_meta(shown_transcript: str, viewer_received_unredacted: bool) -> dict:
    """
    Describe privacy masking visible in the transcript string served to the client.
    Masking is applied at persistence (see ingest) and/or in serialize_feedback for role-based display.
    """
    shown = shown_transcript or ""
    total = sum(shown.count(m) for m in _PRIVACY_MARKERS)
    types: list[str] = []
    if "[EMAIL]" in shown:
        types.append("email")
    if "[PHONE]" in shown:
        types.append("phone")
    if "[REDACTED]" in shown:
        types.append("salutation_or_placeholder")
    if "[NAME]" in shown:
        types.append("capitalized_name_pattern")
    return {
        "identifiers_visible_as_masked": total > 0,
        "approx_masking_tokens": total,
        "masking_token_types": types,
        "viewer_received_unredacted_transcript": viewer_received_unredacted,
        "explanation": (
            "Privacy masking is applied when saving feedback and/or when serving text to viewers without access to "
            "unredacted content. Placeholders such as [REDACTED] or [NAME] are not produced by the LLM analysis step itself."
        ),
    }


def redact_analysis_obj(obj):
    if obj is None:
        return None
    if isinstance(obj, str):
        return redact_sensitive_text(obj)
    if isinstance(obj, list):
        return [redact_analysis_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact_analysis_obj(v) for k, v in obj.items()}
    return obj


def maybe_backfill_unmasked_analysis(feedback: Feedback) -> bool:
    """Backfill analysis_original for legacy rows that only stored redacted analysis."""
    if not feedback.analysis_json or not feedback.original_message:
        return False
    try:
        payload = json.loads(feedback.analysis_json)
    except Exception:
        return False
    if not isinstance(payload, dict):
        return False
    # Already has original analysis
    if payload.get("analysis_original") is not None and payload.get("transcript_original"):
        return False
    try:
        regenerated = run_text_pipeline(feedback.original_message)
    except Exception:
        return False
    analysis_block = regenerated.get("analysis", {}) or {}
    transcript = regenerated.get("transcript", feedback.original_message) or feedback.original_message
    usage = payload.get("usage", regenerated.get("usage", {}))
    payload["transcript_original"] = transcript
    payload["transcript"] = redact_sensitive_text(transcript)
    payload["analysis_original"] = analysis_block
    payload["analysis"] = redact_analysis_obj(analysis_block)
    payload["usage"] = usage
    feedback.analysis_json = json.dumps(payload)
    return True

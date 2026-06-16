from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import os
import cv2
import csv
import io
import hashlib
import hmac
import base64
import json
import math
import secrets
import time
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, func, or_
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import date, datetime, timedelta
try:
    from ultralytics import YOLO
except ImportError as exc:
    YOLO = None
    YOLO_IMPORT_ERROR = str(exc)
else:
    YOLO_IMPORT_ERROR = None

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError as exc:
    BackgroundScheduler = None
    SCHEDULER_IMPORT_ERROR = str(exc)
else:
    SCHEDULER_IMPORT_ERROR = None

# 数据库配置
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./traffic_system.db")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
MODEL_PATH = Path(os.getenv("MODEL_PATH", "best.pt"))
DETECTOR_MODE = os.getenv("DETECTOR_MODE", "auto").lower()
MOCK_SIGN_ID = int(os.getenv("MOCK_SIGN_ID", "28"))
DETECTION_CONFIDENCE = float(os.getenv("DETECTION_CONFIDENCE", "0.25"))
STATIC_DIR = Path(os.getenv("STATIC_DIR", "static"))
TOKEN_SECRET = os.getenv("TOKEN_SECRET", "dev-only-change-me-before-deploy")
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", str(24 * 60 * 60)))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/bmp", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/avi", "video/x-msvideo", "video/quicktime", "video/webm"}
ALLOWED_ACTIONS = {"直行", "掉头", "鸣笛", "停车"}
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

engine_kwargs = {"pool_pre_ping": True}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 新增：补充两张新表的 ORM 模型 ---

class User(Base):
    """用户表：存储系统账号，支持 admin（管理员）和 driver（驾驶员）两种角色"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="driver")  # admin | driver
    create_time = Column(DateTime, default=datetime.now)

class SignDict(Base):
    __tablename__ = "sign_dict"
    id = Column(Integer, primary_key=True, index=True)
    sign_code = Column(String(50), unique=True, index=True, nullable=False)
    meaning = Column(String(100), nullable=False)
    sign_type = Column(String(50), nullable=False)
    limit_value = Column(Float, nullable=True)
    road_section = Column(String(100), nullable=True, index=True)
    direction = Column(String(50), nullable=True)
    position_desc = Column(String(200), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    recommended_speed = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(50), nullable=True, index=True)
    summary = Column(String(255), nullable=False)
    detail_json = Column(String(4000), nullable=True)
    create_time = Column(DateTime, default=datetime.now, index=True)

class DetectRecord(Base):
    __tablename__ = "detect_records"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=True, index=True)   # 提交检测的用户
    original_image_url = Column(String(255))
    result_image_url = Column(String(255))
    detected_signs = Column(String(255))
    source_type = Column(String(20), default="image")
    detected_details_json = Column(String(4000), nullable=True)
    location_text = Column(String(200), nullable=True)
    create_time = Column(DateTime, default=datetime.now)

class ViolationRecord(Base):
    __tablename__ = "violation_records"
    id = Column(Integer, primary_key=True, index=True)
    detect_id = Column(Integer)
    violation_msg = Column(String(255))
    violation_type = Column(String(50), nullable=True, index=True)
    severity = Column(String(20), nullable=True, index=True)
    status = Column(String(20), default="pending", index=True)
    handled_by = Column(String(50), nullable=True)
    handled_at = Column(DateTime, nullable=True)
    create_time = Column(DateTime, default=datetime.now)

class StatsDaily(Base):
    """每日预聚合统计表，由定时任务在 00:00 写入"""
    __tablename__ = "stats_daily"
    id = Column(Integer, primary_key=True, index=True)
    stat_date = Column(Date, unique=True, index=True)   # 统计日期（唯一）
    total_detections = Column(Integer, default=0)
    total_violations = Column(Integer, default=0)
    top_signs_json = Column(String(2000))               # JSON 字符串，存 TOP10
    violation_pie_json = Column(String(2000))           # JSON 字符串，存违规占比
    created_at = Column(DateTime, default=datetime.now)

# ────────────────────────────────────────────────
# 每日统计与报告生成
# ────────────────────────────────────────────────

def _date_range(target_date: date):
    start_dt = datetime.combine(target_date, datetime.min.time())
    return start_dt, start_dt + timedelta(days=1)


def _safe_json_loads(value: Optional[str], default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _classify_violation(message: str) -> str:
    if "超速" in message:
        return "超速行驶"
    if "停车" in message:
        return "违规停车"
    if "违规操作" in message or "掉头" in message or "鸣" in message:
        return "违章操作(掉头/鸣笛)"
    return "其他违规"


def _violation_type_label(violation_type: Optional[str], message: str = "") -> str:
    labels = {
        "speeding": "超速行驶",
        "illegal_u_turn": "违规掉头",
        "illegal_honking": "违规鸣笛",
        "illegal_parking": "违规停车",
    }
    if violation_type in labels:
        return labels[violation_type]
    return _classify_violation(message or "")


def _build_daily_payload(record: StatsDaily):
    return {
        "stat_date": str(record.stat_date),
        "total_detections": record.total_detections or 0,
        "total_violations": record.total_violations or 0,
        "top_signs": _safe_json_loads(record.top_signs_json, []),
        "violation_pie": _safe_json_loads(record.violation_pie_json, []),
        "created_at": record.created_at.isoformat(sep=" ", timespec="seconds") if record.created_at else None,
    }


def generate_daily_stats(target_date: date, db: Session, force: bool = False):
    """生成或刷新指定日期日报，供定时任务和管理员手动重建共用。"""
    existing = db.query(StatsDaily).filter(StatsDaily.stat_date == target_date).first()
    if existing and not force:
        return existing

    start_dt, end_dt = _date_range(target_date)
    records = db.query(DetectRecord).filter(
        DetectRecord.create_time >= start_dt,
        DetectRecord.create_time < end_dt,
    ).all()
    record_ids = [record.id for record in records]

    sign_counter = {}
    for record in records:
        signs = [
            item.strip()
            for item in (record.detected_signs or "").split(",")
            if item.strip() and item.strip() != "未检测到标志"
        ]
        for sign in signs:
            sign_counter[sign] = sign_counter.get(sign, 0) + 1
    top_signs = [
        {"name": name, "value": count}
        for name, count in sorted(sign_counter.items(), key=lambda item: item[1], reverse=True)[:10]
    ]

    violations = []
    if record_ids:
        violations = db.query(ViolationRecord).filter(ViolationRecord.detect_id.in_(record_ids)).all()
    violation_counter = {}
    for violation in violations:
        category = _violation_type_label(violation.violation_type, violation.violation_msg or "")
        violation_counter[category] = violation_counter.get(category, 0) + 1
    violation_pie = [
        {"name": name, "value": count}
        for name, count in sorted(violation_counter.items(), key=lambda item: item[1], reverse=True)
    ]
    if not violation_pie:
        violation_pie = [{"name": "暂无违规数据", "value": 0}]

    payload = {
        "stat_date": target_date,
        "total_detections": len(records),
        "total_violations": len(violations),
        "top_signs_json": json.dumps(top_signs, ensure_ascii=False),
        "violation_pie_json": json.dumps(violation_pie, ensure_ascii=False),
        "created_at": datetime.now(),
    }

    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        daily = existing
    else:
        daily = StatsDaily(**payload)
        db.add(daily)
    db.commit()
    db.refresh(daily)
    return daily


def run_daily_stats():
    """聚合昨天的检测量、违规量、TOP10标志、违规占比，写入 stats_daily 表"""
    db = SessionLocal()
    try:
        yesterday = (datetime.now() - timedelta(days=1)).date()
        daily = generate_daily_stats(yesterday, db, force=False)
        print(
            f"[定时任务] {daily.stat_date} 统计完成："
            f"检测 {daily.total_detections} 次，违规 {daily.total_violations} 起"
        )
    except Exception as e:
        print(f"[定时任务] 统计失败: {e}")
        db.rollback()
    finally:
        db.close()


scheduler = None
if BackgroundScheduler is not None:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(run_daily_stats, "cron", hour=0, minute=0)


@asynccontextmanager
async def lifespan(app):
    if scheduler is not None:
        scheduler.start()
        print("[定时任务] APScheduler 已启动，每天 00:00 自动聚合统计数据")
    else:
        print(f"[定时任务] APScheduler 不可用，已跳过定时统计: {SCHEDULER_IMPORT_ERROR}")
    yield
    if scheduler is not None:
        scheduler.shutdown()


app = FastAPI(
    title="高速公路交通标志检测与管理系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 新增：将 static 文件夹挂载到网络上，前端才能通过网址访问图片 ---
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

model = None
model_load_error: Optional[str] = None


def get_model():
    """按需加载模型，避免缺少 best.pt 时整个后端无法启动。"""
    global model, model_load_error
    if model is not None:
        return model
    if YOLO is None:
        model_load_error = f"ultralytics 未安装: {YOLO_IMPORT_ERROR}"
        raise HTTPException(status_code=503, detail=model_load_error)
    if not MODEL_PATH.exists():
        model_load_error = f"模型文件不存在: {MODEL_PATH}"
        raise HTTPException(status_code=503, detail=model_load_error)
    try:
        model = YOLO(str(MODEL_PATH))
        model_load_error = None
        return model
    except Exception as exc:
        model_load_error = str(exc)
        raise HTTPException(status_code=503, detail=f"模型加载失败: {model_load_error}")


def file_url(relative_path: str) -> str:
    return f"{APP_BASE_URL}/{relative_path.replace(os.sep, '/')}"


def static_path_from_reference(reference: Optional[str]) -> Optional[Path]:
    if not reference:
        return None
    value = str(reference).strip().replace("\\", "/")
    if value.startswith(APP_BASE_URL):
        value = value[len(APP_BASE_URL):].lstrip("/")
    value = value.lstrip("/")
    if not value.startswith("static/"):
        return None

    relative = value[len("static/"):]
    if not relative or ".." in Path(relative).parts:
        return None

    root = STATIC_DIR.resolve()
    candidate = (STATIC_DIR / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def static_reference_from_path(path: Path) -> str:
    return f"static/{path.resolve().relative_to(STATIC_DIR.resolve()).as_posix()}"


def collect_record_artifact_paths(record: DetectRecord) -> set[Path]:
    paths = set()
    for reference in (record.original_image_url, record.result_image_url):
        path = static_path_from_reference(reference)
        if path:
            paths.add(path)

    details = _safe_json_loads(record.detected_details_json, [])
    for item in details if isinstance(details, list) else []:
        if not isinstance(item, dict):
            continue
        for key in ("image_path", "result_path", "frame_path", "frame_result_path"):
            path = static_path_from_reference(item.get(key))
            if path:
                paths.add(path)

    original_path = static_path_from_reference(record.original_image_url)
    if original_path and original_path.name.startswith("video_"):
        timestamp = original_path.stem.removeprefix("video_")
        for pattern in (f"video_frame_{timestamp}_*.jpg", f"video_res_{timestamp}_*.jpg"):
            paths.update(path.resolve() for path in STATIC_DIR.glob(pattern) if path.is_file())
    return paths


def list_static_files() -> list[Path]:
    if not STATIC_DIR.exists():
        return []
    return [path.resolve() for path in STATIC_DIR.rglob("*") if path.is_file()]


def remove_static_files(paths) -> list[str]:
    removed = []
    root = STATIC_DIR.resolve()
    for path in sorted({Path(p).resolve() for p in paths}):
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.exists() and path.is_file():
            path.unlink()
            removed.append(static_reference_from_path(path))
    return removed


def build_storage_status(db: Session, sample_limit: int = 20):
    all_files, referenced, orphaned = collect_storage_inventory(db)

    def total_size(paths):
        return sum(path.stat().st_size for path in paths if path.exists())

    return {
        "static_dir": str(STATIC_DIR),
        "total_files": len(all_files),
        "total_bytes": total_size(all_files),
        "referenced_files": len(referenced),
        "referenced_bytes": total_size(referenced),
        "orphaned_files": len(orphaned),
        "orphaned_bytes": total_size(orphaned),
        "orphaned_samples": [
            {
                "path": static_reference_from_path(path),
                "size": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(sep=" ", timespec="seconds"),
            }
            for path in orphaned[:sample_limit]
            if path.exists()
        ],
    }


def collect_storage_inventory(db: Session):
    all_files = set(list_static_files())
    referenced = set()
    for record in db.query(DetectRecord).all():
        referenced.update(path for path in collect_record_artifact_paths(record) if path.exists())
    orphaned = sorted(all_files - referenced, key=lambda path: path.stat().st_mtime if path.exists() else 0)
    return all_files, referenced, orphaned


def draw_chinese_box(cv2_img, box_coords, text, conf):
    x1, y1, x2, y2 = map(int, box_coords)
    
    # 1. 用 OpenCV 画绿色的矩形框
    cv2.rectangle(cv2_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
    
    # 2. 因为 OpenCV 不支持中文，需要转换成 PIL 图像
    pil_img = Image.fromarray(cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    
    # 3. 加载 Windows 系统自带的黑体 (simhei.ttf)
    try:
        font = ImageFont.truetype("simhei.ttf", 20, encoding="utf-8")
    except:
        font = ImageFont.load_default() # 如果没找到就退回默认字体
        
    display_text = f"{text} {conf:.2f}" # 例如: "限制速度60 0.95"
    
    # 4. 画一个绿色背景条，让文字更清晰可见
    try:
        # 新版 Pillow
        left, top, right, bottom = draw.textbbox((x1, y1 - 25), display_text, font=font)
        draw.rectangle([left, top, right, bottom], fill=(0, 255, 0))
    except AttributeError:
        # 兼容老版 Pillow
        w, h = draw.textsize(display_text, font=font)
        draw.rectangle([x1, y1 - 25, x1 + w, y1 - 25 + h], fill=(0, 255, 0))
    
    # 5. 画上黑色的中文文字
    draw.text((x1, y1 - 25), display_text, font=font, fill=(0, 0, 0))
    
    # 6. 转换回 OpenCV 格式并返回
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "database_url": SQLALCHEMY_DATABASE_URL.split("@")[-1],
        "detector_mode": DETECTOR_MODE,
        "detection_confidence": DETECTION_CONFIDENCE,
        "model_available": MODEL_PATH.exists(),
        "model_path": str(MODEL_PATH),
    }


@app.get("/api/model/status")
def model_status():
    return {
        "mode": DETECTOR_MODE,
        "available": MODEL_PATH.exists(),
        "loaded": model is not None,
        "path": str(MODEL_PATH),
        "confidence": DETECTION_CONFIDENCE,
        "error": model_load_error,
        "ready": DETECTOR_MODE == "mock" or MODEL_PATH.exists(),
        "mock_sign_id": MOCK_SIGN_ID if DETECTOR_MODE == "mock" else None,
    }


def _normalize_model_names(raw_names):
    if raw_names is None:
        return {}
    if isinstance(raw_names, dict):
        return {
            int(key): str(value)
            for key, value in raw_names.items()
            if str(key).isdigit() or isinstance(key, int)
        }
    if isinstance(raw_names, (list, tuple)):
        return {idx: str(value) for idx, value in enumerate(raw_names)}
    return {}


# ────────────────────────────────────────────────
# 工具函数：密码哈希 & 权限校验
# ────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, digest = stored_hash.split("$", 3)
            candidate = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), salt.encode(), int(iterations)
            ).hex()
            return hmac.compare_digest(candidate, digest)
        except Exception:
            return False
    # 兼容旧数据：原项目使用无盐 SHA-256。
    return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), stored_hash)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def make_token(username: str, role: str) -> str:
    issued_at = int(time.time())
    payload = json.dumps(
        {"sub": username, "role": role, "iat": issued_at, "exp": issued_at + TOKEN_TTL_SECONDS},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()
    encoded_payload = _b64url(payload)
    signature = hmac.new(TOKEN_SECRET.encode(), encoded_payload.encode(), hashlib.sha256).digest()
    return f"{encoded_payload}.{_b64url(signature)}"

def parse_token(token: str):
    """返回 (role, username)，无效则返回 (None, None)"""
    try:
        encoded_payload, signature = token.split(".", 1)
        expected = _b64url(
            hmac.new(TOKEN_SECRET.encode(), encoded_payload.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            return None, None
        payload = json.loads(_b64url_decode(encoded_payload))
        exp = payload.get("exp")
        if not isinstance(exp, int) or exp < int(time.time()):
            return None, None
        return payload.get("role"), payload.get("sub")
    except Exception:
        return None, None

def require_login(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """依赖注入：要求已登录（任意角色）"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    token = authorization.replace("Bearer ", "")
    role, username = parse_token(token)
    if not role or not username:
        raise HTTPException(status_code=401, detail="Token 无效，请重新登录")
    user = db.query(User).filter(User.username == username).first()
    if not user or user.role != role:
        raise HTTPException(status_code=401, detail="登录状态已失效，请重新登录")
    return {"role": role, "username": username}


def require_admin(current_user: dict = Depends(require_login)):
    """依赖注入：要求请求方携带管理员 token"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="权限不足，该操作仅限管理员")
    return current_user


@app.get("/api/model/mapping-check")
def model_mapping_check(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    signs = db.query(SignDict).order_by(SignDict.id.asc()).all()
    sign_ids = [sign.id for sign in signs]
    signs_by_id = {sign.id: sign for sign in signs}
    duplicate_codes = [
        code for code, count in db.query(SignDict.sign_code, func.count(SignDict.id))
        .group_by(SignDict.sign_code)
        .having(func.count(SignDict.id) > 1)
        .all()
    ]
    expected_ids = list(range(len(signs)))
    missing_dictionary_ids = sorted(set(expected_ids) - set(sign_ids))
    extra_dictionary_ids = sorted(set(sign_ids) - set(expected_ids))
    limit_rule_issues = [
        sign_to_dict(sign)
        for sign in signs
        if sign.sign_code.startswith("pl") and sign.limit_value is None
    ]

    model_names = {}
    model_error = None
    if MODEL_PATH.exists():
        try:
            detector = get_model()
            model_names = _normalize_model_names(getattr(detector, "names", None))
        except HTTPException as exc:
            model_error = exc.detail
        except Exception as exc:
            model_error = str(exc)
    elif DETECTOR_MODE != "mock":
        model_error = f"模型文件不存在: {MODEL_PATH}"

    model_ids = sorted(model_names.keys())
    dictionary_id_set = set(sign_ids)
    model_id_set = set(model_ids)
    missing_in_dictionary = sorted(model_id_set - dictionary_id_set)
    dictionary_not_in_model = sorted(dictionary_id_set - model_id_set) if model_names else []

    mismatched_names = []
    for class_id in sorted(model_id_set & dictionary_id_set):
        model_name = model_names[class_id]
        sign = signs_by_id.get(class_id)
        if sign and model_name not in {sign.sign_code, sign.meaning}:
            mismatched_names.append({
                "class_id": class_id,
                "model_name": model_name,
                "sign_code": sign.sign_code,
                "meaning": sign.meaning,
            })

    blocking_issues = []
    if missing_dictionary_ids:
        blocking_issues.append("字典 class id 不连续")
    if duplicate_codes:
        blocking_issues.append("存在重复 sign_code")
    if limit_rule_issues:
        blocking_issues.append("限速类标志缺少 limit_value")
    if model_names and missing_in_dictionary:
        blocking_issues.append("模型类别缺少字典映射")

    warnings = []
    if model_error:
        warnings.append(model_error)
    if model_names and dictionary_not_in_model:
        warnings.append("字典中存在超出当前模型类别范围的标志")
    if mismatched_names:
        warnings.append("模型类别名称与字典 sign_code/meaning 不完全一致，请确认训练标签顺序")

    return {
        "ready": not blocking_issues and not model_error,
        "mode": DETECTOR_MODE,
        "dictionary": {
            "total": len(signs),
            "min_id": min(sign_ids) if sign_ids else None,
            "max_id": max(sign_ids) if sign_ids else None,
            "missing_ids": missing_dictionary_ids,
            "extra_ids": extra_dictionary_ids,
            "duplicate_codes": duplicate_codes,
            "limit_rule_issues": limit_rule_issues,
        },
        "model": {
            "path": str(MODEL_PATH),
            "available": MODEL_PATH.exists(),
            "loaded": model is not None,
            "class_count": len(model_names) if model_names else None,
            "ids": model_ids[:200],
            "error": model_error,
        },
        "comparison": {
            "missing_in_dictionary": missing_in_dictionary,
            "dictionary_not_in_model": dictionary_not_in_model,
            "mismatched_names": mismatched_names[:100],
        },
        "blocking_issues": blocking_issues,
        "warnings": warnings,
    }


def parse_datetime_param(value: Optional[str], field_name: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"{field_name} 时间格式错误，应为 YYYY-MM-DD HH:mm:ss")


def parse_date_param(value: Optional[str], field_name: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} 日期格式错误，应为 YYYY-MM-DD")


def build_violation_events(sign_info: SignDict, current_speed: float, current_action: str):
    events = []
    if sign_info.limit_value is not None and sign_info.sign_code.startswith("pl") and current_speed > sign_info.limit_value:
        events.append({
            "type": "speeding",
            "label": "超速行驶",
            "severity": "high",
            "message": f"超速警报！当前车速 {current_speed}km/h，该路段 {sign_info.meaning}。",
            "sign_code": sign_info.sign_code,
            "limit_value": sign_info.limit_value,
            "current_speed": current_speed,
            "action": current_action,
        })
    if sign_info.sign_type == "禁止标志":
        if current_action == "掉头" and "掉头" in sign_info.meaning:
            events.append({
                "type": "illegal_u_turn",
                "label": "违规掉头",
                "severity": "high",
                "message": f"违规操作！前方 {sign_info.meaning}。",
                "sign_code": sign_info.sign_code,
                "limit_value": sign_info.limit_value,
                "current_speed": current_speed,
                "action": current_action,
            })
        elif current_action == "鸣笛" and ("鸣喇叭" in sign_info.meaning or "鸣笛" in sign_info.meaning):
            events.append({
                "type": "illegal_honking",
                "label": "违规鸣笛",
                "severity": "medium",
                "message": f"违规操作！前方 {sign_info.meaning}。",
                "sign_code": sign_info.sign_code,
                "limit_value": sign_info.limit_value,
                "current_speed": current_speed,
                "action": current_action,
            })
        elif current_action == "停车" and "停车" in sign_info.meaning:
            events.append({
                "type": "illegal_parking",
                "label": "违规停车",
                "severity": "medium",
                "message": f"违规操作！前方 {sign_info.meaning}，禁止停车。",
                "sign_code": sign_info.sign_code,
                "limit_value": sign_info.limit_value,
                "current_speed": current_speed,
                "action": current_action,
            })
    return events


def dedupe_violation_events(events):
    unique = {}
    for event in events:
        key = (event.get("type"), event.get("message"), event.get("sign_code"))
        unique[key] = event
    return list(unique.values())


def persist_violation_events(db: Session, detect_id: int, events):
    for event in events:
        msg = event.get("message")
        if not msg:
            continue
        db.add(ViolationRecord(
            detect_id=detect_id,
            violation_msg=msg,
            violation_type=event.get("type"),
            severity=event.get("severity"),
        ))


def build_location_text(details) -> Optional[str]:
    locations = []
    for item in details or []:
        if not item.get("matched"):
            continue
        location = item.get("position_desc")
        if not location:
            parts = [item.get("road_section"), item.get("direction")]
            location = " ".join(part for part in parts if part)
        if not location and item.get("latitude") is not None and item.get("longitude") is not None:
            location = f"{item['latitude']:.6f},{item['longitude']:.6f}"
        if location and location not in locations:
            locations.append(location)
    if not locations:
        return None
    return " / ".join(locations)[:200]


def analyze_image_file(
    image_path: Path,
    result_path: Optional[Path],
    db: Session,
    current_speed: float,
    current_action: str,
    min_confidence: float,
):
    res_img = cv2.imread(str(image_path))
    if res_img is None:
        raise HTTPException(status_code=400, detail="图片解码失败，请上传有效图片")

    if DETECTOR_MODE == "mock":
        sign_info = db.query(SignDict).filter(SignDict.id == MOCK_SIGN_ID).first()
        if not sign_info:
            sign_info = db.query(SignDict).first()
        if not sign_info:
            raise HTTPException(status_code=503, detail="演示检测器缺少标志字典数据")

        height, width = res_img.shape[:2]
        box_coords = [width * 0.25, height * 0.2, width * 0.75, height * 0.8]

        if min_confidence > 0.99:
            if result_path is not None:
                cv2.imwrite(str(result_path), res_img)
            return {
                "detected_signs": [],
                "violation_alerts": [],
                "violation_events": [],
                "details": [],
            }

        res_img = draw_chinese_box(res_img, box_coords, f"演示-{sign_info.meaning}", 0.99)
        sign_violation_events = build_violation_events(sign_info, current_speed, current_action)
        sign_violations = [event["message"] for event in sign_violation_events]

        if result_path is not None:
            cv2.imwrite(str(result_path), res_img)

        return {
            "detected_signs": [sign_info.meaning],
            "violation_alerts": sign_violations,
            "violation_events": sign_violation_events,
            "details": [{
                "class_id": sign_info.id,
                "sign_code": sign_info.sign_code,
                "meaning": sign_info.meaning,
                "sign_type": sign_info.sign_type,
                "limit_value": sign_info.limit_value,
                "recommended_speed": sign_info.recommended_speed or sign_info.limit_value,
                "road_section": sign_info.road_section,
                "direction": sign_info.direction,
                "position_desc": sign_info.position_desc,
                "latitude": sign_info.latitude,
                "longitude": sign_info.longitude,
                "confidence": 0.99,
                "min_confidence": min_confidence,
                "bbox": box_coords,
                "violations": sign_violations,
                "violation_events": sign_violation_events,
                "matched": True,
                "mock": True,
            }],
        }

    detector = get_model()
    try:
        results = detector.predict(source=str(image_path), conf=min_confidence)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"模型推理失败: {exc}")

    detected_signs = []
    violation_alerts = []
    violation_events = []
    details = []

    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            if conf < min_confidence:
                continue
            box_coords = [float(v) for v in box.xyxy[0].tolist()]
            sign_info = db.query(SignDict).filter(SignDict.id == cls_id).first()
            if not sign_info:
                details.append({
                    "class_id": cls_id,
                    "confidence": round(conf, 4),
                    "min_confidence": min_confidence,
                    "bbox": box_coords,
                    "matched": False,
                })
                continue

            meaning = sign_info.meaning
            detected_signs.append(meaning)
            res_img = draw_chinese_box(res_img, box_coords, meaning, conf)

            sign_violation_events = build_violation_events(sign_info, current_speed, current_action)
            sign_violations = [event["message"] for event in sign_violation_events]

            violation_alerts.extend(sign_violations)
            violation_events.extend(sign_violation_events)
            details.append({
                "class_id": cls_id,
                "sign_code": sign_info.sign_code,
                "meaning": meaning,
                "sign_type": sign_info.sign_type,
                "limit_value": sign_info.limit_value,
                "recommended_speed": sign_info.recommended_speed or sign_info.limit_value,
                "road_section": sign_info.road_section,
                "direction": sign_info.direction,
                "position_desc": sign_info.position_desc,
                "latitude": sign_info.latitude,
                "longitude": sign_info.longitude,
                "confidence": round(conf, 4),
                "min_confidence": min_confidence,
                "bbox": box_coords,
                "violations": sign_violations,
                "violation_events": sign_violation_events,
                "matched": True,
            })

    if result_path is not None:
        cv2.imwrite(str(result_path), res_img)

    return {
        "detected_signs": list(dict.fromkeys(detected_signs)),
        "violation_alerts": list(dict.fromkeys(violation_alerts)),
        "violation_events": dedupe_violation_events(violation_events),
        "details": details,
    }


@app.post("/api/detect")
async def detect_sign(
    file: UploadFile = File(...),
    current_speed: float = Form(..., ge=0, le=200),
    current_action: str = Form(default="直行"),
    min_confidence: float = Form(default=DETECTION_CONFIDENCE, ge=0, le=1),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_login)
):
    if current_action not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=422, detail="current_action 只能是 直行、掉头、鸣笛 或 停车")
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPEG、PNG、BMP、WEBP 图片")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"图片不能超过 {MAX_UPLOAD_BYTES // 1024 // 1024}MB")

    # 按时间戳规则命名：orig_YYYYMMDD_HHMMSS_ffffff.jpg
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    orig_filename = f"orig_{timestamp}.jpg"
    res_filename = f"res_{timestamp}.jpg"
    orig_disk_path = STATIC_DIR / orig_filename
    res_disk_path = STATIC_DIR / res_filename
    orig_img_path = f"static/{orig_filename}"
    res_img_path = f"static/{res_filename}"
    
    # 1. 保存前端传来的原图
    with open(orig_disk_path, "wb") as buffer:
        buffer.write(image_bytes)
    
    analysis = analyze_image_file(orig_disk_path, res_disk_path, db, current_speed, current_action, min_confidence)
    detected_signs = analysis["detected_signs"]
    violation_alerts = analysis["violation_alerts"]
    violation_events = analysis.get("violation_events", [])
    location_text = build_location_text(analysis["details"])
    
    # --- 新增：将记录插入 MySQL 数据库 ---
    signs_str = ",".join(detected_signs) if detected_signs else "未检测到标志"
    
    # 写入识别主表
    new_record = DetectRecord(
        username=current_user["username"],
        original_image_url=orig_img_path,
        result_image_url=res_img_path,
        detected_signs=signs_str,
        source_type="image",
        detected_details_json=json.dumps(analysis["details"], ensure_ascii=False),
        location_text=location_text,
    )
    db.add(new_record)
    db.flush() # 生成了 new_record.id，方便下面关联
    
    # 写入违规子表（含5分钟抑制：同一违规消息5分钟内不重复写入）
    if len(violation_alerts) > 0:
        persist_violation_events(db, new_record.id, violation_events)
            
    db.commit() # 真正提交保存到数据库

    # 4. 返回完整数据和图片网络地址给前端
    # 注意：这里的 127.0.0.1 如果你们是局域网联调，需要换成同学 A 的真实局域网 IP
    return {
        "status": "success",
        "id": new_record.id,
        "detected_signs": detected_signs,
        "is_violation": len(violation_alerts) > 0,
        "violation_msgs": violation_alerts,
        "violation_events": violation_events,
        "min_confidence": min_confidence,
        "details": analysis["details"],
        "original_image": file_url(orig_img_path), # 传给前端的原图地址
        "result_image": file_url(res_img_path)     # 传给前端的带框结果图地址
    }


@app.post("/api/detect/video")
async def detect_video(
    file: UploadFile = File(...),
    current_speed: float = Form(..., ge=0, le=200),
    current_action: str = Form(default="直行"),
    min_confidence: float = Form(default=DETECTION_CONFIDENCE, ge=0, le=1),
    frame_interval: int = Form(default=30, ge=1, le=300),
    max_frames: int = Form(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_login),
):
    if current_action not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=422, detail="current_action 只能是 直行、掉头、鸣笛 或 停车")
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 MP4、AVI、MOV、WEBM 视频")

    video_bytes = await file.read()
    if not video_bytes:
        raise HTTPException(status_code=400, detail="上传视频为空")
    if len(video_bytes) > MAX_UPLOAD_BYTES * 5:
        raise HTTPException(status_code=413, detail=f"视频不能超过 {MAX_UPLOAD_BYTES * 5 // 1024 // 1024}MB")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    video_filename = f"video_{timestamp}.mp4"
    video_disk_path = STATIC_DIR / video_filename
    video_path = f"static/{video_filename}"
    with open(video_disk_path, "wb") as buffer:
        buffer.write(video_bytes)

    cap = cv2.VideoCapture(str(video_disk_path))
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="视频解码失败，请上传有效视频")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    frame_index = 0
    sampled = 0
    detected_signs = []
    violation_alerts = []
    violation_events = []
    details = []
    first_frame_path = None
    first_result_path = None

    try:
        while sampled < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % frame_interval != 0:
                frame_index += 1
                continue

            frame_filename = f"video_frame_{timestamp}_{frame_index}.jpg"
            result_filename = f"video_res_{timestamp}_{frame_index}.jpg"
            frame_disk_path = STATIC_DIR / frame_filename
            result_disk_path = STATIC_DIR / result_filename
            cv2.imwrite(str(frame_disk_path), frame)
            analysis = analyze_image_file(frame_disk_path, result_disk_path, db, current_speed, current_action, min_confidence)

            if first_frame_path is None:
                first_frame_path = f"static/{frame_filename}"
                first_result_path = f"static/{result_filename}"

            frame_time = round(frame_index / fps, 2) if fps else None
            for item in analysis["details"]:
                item["frame_index"] = frame_index
                item["time_sec"] = frame_time
                item["frame_path"] = f"static/{frame_filename}"
                item["frame_result_path"] = f"static/{result_filename}"
                details.append(item)
            detected_signs.extend(analysis["detected_signs"])
            violation_alerts.extend(analysis["violation_alerts"])
            violation_events.extend(analysis.get("violation_events", []))

            sampled += 1
            frame_index += 1
    finally:
        cap.release()

    detected_signs = list(dict.fromkeys(detected_signs))
    violation_alerts = list(dict.fromkeys(violation_alerts))
    violation_events = dedupe_violation_events(violation_events)
    location_text = build_location_text(details)
    signs_str = ",".join(detected_signs) if detected_signs else "未检测到标志"

    new_record = DetectRecord(
        username=current_user["username"],
        original_image_url=video_path,
        result_image_url=first_result_path or video_path,
        detected_signs=signs_str,
        source_type="video",
        detected_details_json=json.dumps(details, ensure_ascii=False),
        location_text=location_text,
    )
    db.add(new_record)
    db.flush()

    if violation_alerts:
        persist_violation_events(db, new_record.id, violation_events)

    db.commit()
    return {
        "status": "success",
        "id": new_record.id,
        "source_type": "video",
        "sampled_frames": sampled,
        "detected_signs": detected_signs,
        "is_violation": len(violation_alerts) > 0,
        "violation_msgs": violation_alerts,
        "violation_events": violation_events,
        "min_confidence": min_confidence,
        "details": details,
        "video_url": file_url(video_path),
        "original_image": file_url(first_frame_path or video_path),
        "result_image": file_url(first_result_path or video_path),
    }


# ────────────────────────────────────────────────
# 历史记录接口
# ────────────────────────────────────────────────

@app.get("/api/records")
def get_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sign_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    has_violation: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_login)
):
    start_dt = parse_datetime_param(start_time, "start_time")
    end_dt = parse_datetime_param(end_time, "end_time")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="开始时间不能晚于结束时间")

    query = db.query(DetectRecord)
    # 驾驶员只能看自己的记录
    if current_user["role"] != "admin":
        query = query.filter(DetectRecord.username == current_user["username"])
    if sign_type:
        query = query.filter(DetectRecord.detected_signs.contains(sign_type))
    if start_dt:
        query = query.filter(DetectRecord.create_time >= start_dt)
    if end_dt:
        query = query.filter(DetectRecord.create_time <= end_dt)
    if has_violation == "true":
        violation_ids = db.query(ViolationRecord.detect_id).distinct()
        query = query.filter(DetectRecord.id.in_(violation_ids))
    elif has_violation == "false":
        violation_ids = db.query(ViolationRecord.detect_id).distinct()
        query = query.filter(DetectRecord.id.notin_(violation_ids))
    total = query.count()
    records = query.order_by(DetectRecord.create_time.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "data": [
            {
                "id": r.id,
                "detected_signs": r.detected_signs,
                "original_image": file_url(r.original_image_url),
                "result_image": file_url(r.result_image_url),
                "source_type": r.source_type or "image",
                "location_text": r.location_text,
                "create_time": r.create_time,
                "has_violation": db.query(ViolationRecord).filter(ViolationRecord.detect_id == r.id).count() > 0
            }
            for r in records
        ]
    }


@app.get("/api/records/{record_id}")
def get_record_detail(record_id: int, db: Session = Depends(get_db), current_user: dict = Depends(require_login)):
    r = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 驾驶员只能查看自己的记录
    if current_user["role"] != "admin" and r.username != current_user["username"]:
        raise HTTPException(status_code=403, detail="无权查看该记录")
    violations = db.query(ViolationRecord).filter(ViolationRecord.detect_id == record_id).all()
    return {
        "id": r.id,
        "detected_signs": r.detected_signs,
        "original_image": file_url(r.original_image_url),
        "result_image": file_url(r.result_image_url),
        "source_type": r.source_type or "image",
        "location_text": r.location_text,
        "details": json.loads(r.detected_details_json) if r.detected_details_json else [],
        "create_time": r.create_time,
        "violations": [
            {
                "id": v.id,
                "violation_msg": v.violation_msg,
                "violation_type": v.violation_type,
                "violation_label": _violation_type_label(v.violation_type, v.violation_msg or ""),
                "severity": v.severity,
                "status": v.status or "pending",
                "handled_by": v.handled_by,
                "handled_at": v.handled_at,
                "create_time": v.create_time,
            }
            for v in violations
        ]
    }


# ────────────────────────────────────────────────
# 违规记录接口
# ────────────────────────────────────────────────

def build_violation_query(
    db: Session,
    current_user: dict,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: Optional[str] = None,
    violation_type: Optional[str] = None,
    severity: Optional[str] = None,
):
    start_dt = parse_datetime_param(start_time, "start_time")
    end_dt = parse_datetime_param(end_time, "end_time")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="开始时间不能晚于结束时间")

    query = db.query(ViolationRecord)
    if current_user["role"] != "admin":
        my_ids = db.query(DetectRecord.id).filter(DetectRecord.username == current_user["username"])
        query = query.filter(ViolationRecord.detect_id.in_(my_ids))
    if start_dt:
        query = query.filter(ViolationRecord.create_time >= start_dt)
    if end_dt:
        query = query.filter(ViolationRecord.create_time <= end_dt)
    if status == "pending":
        query = query.filter(or_(ViolationRecord.status.is_(None), ViolationRecord.status == "pending"))
    elif status == "handled":
        query = query.filter(ViolationRecord.status == "handled")
    if violation_type:
        query = query.filter(ViolationRecord.violation_type == violation_type)
    if severity:
        query = query.filter(ViolationRecord.severity == severity)
    return query


@app.get("/api/violations")
def get_violations(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: Optional[str] = Query(None, pattern="^(pending|handled)$"),
    violation_type: Optional[str] = Query(None, pattern="^(speeding|illegal_u_turn|illegal_honking|illegal_parking)$"),
    severity: Optional[str] = Query(None, pattern="^(high|medium|low)$"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_login)
):
    query = build_violation_query(db, current_user, start_time, end_time, status, violation_type, severity)
    total = query.count()
    records = query.order_by(ViolationRecord.create_time.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "data": [
            {
                "id": v.id,
                "detect_id": v.detect_id,
                "violation_msg": v.violation_msg,
                "violation_type": v.violation_type,
                "violation_label": _violation_type_label(v.violation_type, v.violation_msg or ""),
                "severity": v.severity,
                "status": v.status or "pending",
                "handled_by": v.handled_by,
                "handled_at": v.handled_at,
                "create_time": v.create_time,
            }
            for v in records
        ]
    }


@app.get("/api/violations/export")
def export_violations(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: Optional[str] = Query(None, pattern="^(pending|handled)$"),
    violation_type: Optional[str] = Query(None, pattern="^(speeding|illegal_u_turn|illegal_honking|illegal_parking)$"),
    severity: Optional[str] = Query(None, pattern="^(high|medium|low)$"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_login),
):
    query = build_violation_query(db, current_user, start_time, end_time, status, violation_type, severity)
    violations = query.order_by(ViolationRecord.create_time.desc()).all()
    detect_ids = [v.detect_id for v in violations if v.detect_id is not None]
    detect_map = {
        record.id: record
        for record in db.query(DetectRecord).filter(DetectRecord.id.in_(detect_ids)).all()
    } if detect_ids else {}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "违规ID",
        "检测记录ID",
        "驾驶员",
        "检测来源",
        "位置",
        "识别标志",
        "违规类型",
        "风险级别",
        "处理状态",
        "处理人",
        "处理时间",
        "违规时间",
        "违规说明",
    ])
    for violation in violations:
        detect = detect_map.get(violation.detect_id)
        writer.writerow([
            violation.id,
            violation.detect_id,
            detect.username if detect else "",
            (detect.source_type or "image") if detect else "",
            detect.location_text or "" if detect else "",
            detect.detected_signs or "" if detect else "",
            _violation_type_label(violation.violation_type, violation.violation_msg or ""),
            violation.severity or "unknown",
            violation.status or "pending",
            violation.handled_by or "",
            violation.handled_at or "",
            violation.create_time,
            violation.violation_msg,
        ])
    output.seek(0)
    filename = f"violation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


class ViolationStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|handled)$")


@app.put("/api/violations/{violation_id}/status")
def update_violation_status(
    violation_id: int,
    body: ViolationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    violation = db.query(ViolationRecord).filter(ViolationRecord.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="违规记录不存在")
    old_status = violation.status or "pending"
    violation.status = body.status
    if body.status == "handled":
        violation.handled_by = current_user["username"]
        violation.handled_at = datetime.now()
    else:
        violation.handled_by = None
        violation.handled_at = None
    add_audit_log(
        db,
        current_user,
        action="update_status",
        resource_type="violation",
        resource_id=violation.id,
        summary=f"违规记录状态由 {old_status} 更新为 {body.status}",
        detail={
            "detect_id": violation.detect_id,
            "old_status": old_status,
            "new_status": body.status,
            "violation_type": violation.violation_type,
            "severity": violation.severity,
        },
    )
    db.commit()
    db.refresh(violation)
    return {
        "id": violation.id,
        "detect_id": violation.detect_id,
        "violation_msg": violation.violation_msg,
        "violation_type": violation.violation_type,
        "violation_label": _violation_type_label(violation.violation_type, violation.violation_msg or ""),
        "severity": violation.severity,
        "status": violation.status or "pending",
        "handled_by": violation.handled_by,
        "handled_at": violation.handled_at,
        "create_time": violation.create_time,
    }


# ────────────────────────────────────────────────
# 标志字典管理接口（CRUD）
# ────────────────────────────────────────────────

class SignCreate(BaseModel):
    sign_code: str = Field(..., min_length=1, max_length=50)
    meaning: str = Field(..., min_length=1, max_length=100)
    sign_type: str
    limit_value: Optional[float] = Field(default=None, ge=0)
    road_section: Optional[str] = Field(default=None, max_length=100)
    direction: Optional[str] = Field(default=None, max_length=50)
    position_desc: Optional[str] = Field(default=None, max_length=200)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    recommended_speed: Optional[float] = Field(default=None, ge=0, le=200)

    @field_validator("sign_code", "meaning", "sign_type")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("sign_type")
    @classmethod
    def validate_sign_type(cls, value: str) -> str:
        if value not in {"指示标志", "警告标志", "禁止标志"}:
            raise ValueError("标志类型只能是 指示标志、警告标志 或 禁止标志")
        return value

class SignUpdate(BaseModel):
    sign_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    meaning: Optional[str] = Field(default=None, min_length=1, max_length=100)
    sign_type: Optional[str] = None
    limit_value: Optional[float] = Field(default=None, ge=0)
    road_section: Optional[str] = Field(default=None, max_length=100)
    direction: Optional[str] = Field(default=None, max_length=50)
    position_desc: Optional[str] = Field(default=None, max_length=200)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    recommended_speed: Optional[float] = Field(default=None, ge=0, le=200)

    @field_validator("sign_code", "meaning", "sign_type", "road_section", "direction", "position_desc")
    @classmethod
    def strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value and value is not None:
            raise ValueError("不能为空")
        return value

    @field_validator("sign_type")
    @classmethod
    def validate_optional_sign_type(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in {"指示标志", "警告标志", "禁止标志"}:
            raise ValueError("标志类型只能是 指示标志、警告标志 或 禁止标志")
        return value


def sign_to_dict(sign: SignDict):
    return {
        "id": sign.id,
        "sign_code": sign.sign_code,
        "meaning": sign.meaning,
        "sign_type": sign.sign_type,
        "limit_value": sign.limit_value,
        "road_section": sign.road_section,
        "direction": sign.direction,
        "position_desc": sign.position_desc,
        "latitude": sign.latitude,
        "longitude": sign.longitude,
        "recommended_speed": sign.recommended_speed,
        "created_at": sign.created_at,
        "updated_at": sign.updated_at,
    }


SIGN_CSV_FIELDS = [
    "sign_code",
    "meaning",
    "sign_type",
    "limit_value",
    "road_section",
    "direction",
    "position_desc",
    "latitude",
    "longitude",
    "recommended_speed",
]


def _optional_float(value, field_name: str):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        raise ValueError(f"{field_name} 必须是数字")


def _text_or_none(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_sign_csv_rows(csv_text: str):
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV 缺少表头")

    missing_fields = [field for field in ("sign_code", "meaning", "sign_type") if field not in reader.fieldnames]
    if missing_fields:
        raise HTTPException(status_code=400, detail=f"CSV 缺少必填列: {', '.join(missing_fields)}")

    payloads = []
    errors = []
    seen_codes = set()
    for row_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values() if value is not None):
            continue
        try:
            payload = {
                "sign_code": _text_or_none(row.get("sign_code")),
                "meaning": _text_or_none(row.get("meaning")),
                "sign_type": _text_or_none(row.get("sign_type")),
                "limit_value": _optional_float(row.get("limit_value"), "limit_value"),
                "road_section": _text_or_none(row.get("road_section")),
                "direction": _text_or_none(row.get("direction")),
                "position_desc": _text_or_none(row.get("position_desc")),
                "latitude": _optional_float(row.get("latitude"), "latitude"),
                "longitude": _optional_float(row.get("longitude"), "longitude"),
                "recommended_speed": _optional_float(row.get("recommended_speed"), "recommended_speed"),
            }
            sign = SignCreate(**payload)
            normalized = sign.model_dump()
            if normalized["sign_code"] in seen_codes:
                raise ValueError(f"CSV 内 sign_code 重复: {normalized['sign_code']}")
            seen_codes.add(normalized["sign_code"])
            payloads.append(normalized)
        except Exception as exc:
            errors.append({"row": row_number, "error": str(exc)})

    if errors:
        raise HTTPException(status_code=400, detail={"message": "CSV 校验失败", "errors": errors[:20]})
    if not payloads:
        raise HTTPException(status_code=400, detail="CSV 没有可导入的数据行")
    return payloads


def audit_to_dict(log: AuditLog):
    return {
        "id": log.id,
        "username": log.username,
        "role": log.role,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "summary": log.summary,
        "detail": _safe_json_loads(log.detail_json, {}),
        "create_time": log.create_time,
    }


def add_audit_log(
    db: Session,
    current_user: dict,
    action: str,
    resource_type: str,
    resource_id,
    summary: str,
    detail: Optional[dict] = None,
):
    db.add(AuditLog(
        username=current_user["username"],
        role=current_user["role"],
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        summary=summary[:255],
        detail_json=json.dumps(detail or {}, ensure_ascii=False, default=str),
    ))


def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@app.get("/api/signs")
def get_signs(db: Session = Depends(get_db), _=Depends(require_login)):
    signs = db.query(SignDict).order_by(SignDict.id.asc()).all()
    return [sign_to_dict(s) for s in signs]


@app.get("/api/signs/export")
def export_signs(
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    signs = db.query(SignDict).order_by(SignDict.id.asc()).all()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["id", *SIGN_CSV_FIELDS, "created_at", "updated_at"])
    writer.writeheader()
    for sign in signs:
        row = sign_to_dict(sign)
        writer.writerow({key: row.get(key, "") for key in ["id", *SIGN_CSV_FIELDS, "created_at", "updated_at"]})
    output.seek(0)
    filename = f"sign_dictionary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/api/signs/import")
async def import_signs(
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="仅支持 CSV 文件")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="CSV 文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"CSV 文件不能超过 {MAX_UPLOAD_BYTES // 1024 // 1024}MB")

    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_text = content.decode("gbk")

    payloads = parse_sign_csv_rows(csv_text)
    created = 0
    updated = 0
    previews = []
    now = datetime.now()

    for payload in payloads:
        sign = db.query(SignDict).filter(SignDict.sign_code == payload["sign_code"]).first()
        if sign:
            updated += 1
            previews.append({"action": "update", "sign_code": payload["sign_code"], "meaning": payload["meaning"]})
            if not dry_run:
                for field, value in payload.items():
                    setattr(sign, field, value)
                sign.updated_at = now
        else:
            created += 1
            previews.append({"action": "create", "sign_code": payload["sign_code"], "meaning": payload["meaning"]})
            if not dry_run:
                db.add(SignDict(**payload, created_at=now, updated_at=now))

    if not dry_run:
        add_audit_log(
            db,
            current_user,
            action="import",
            resource_type="sign",
            resource_id=None,
            summary=f"批量导入标志字典：新增 {created} 条，更新 {updated} 条",
            detail={"created": created, "updated": updated, "rows": len(payloads), "preview": previews[:100]},
        )
        db.commit()

    return {
        "dry_run": dry_run,
        "total_rows": len(payloads),
        "created": created,
        "updated": updated,
        "preview": previews[:100],
    }


@app.get("/api/signs/search")
def search_signs(
    keyword: Optional[str] = None,
    road_section: Optional[str] = None,
    direction: Optional[str] = None,
    sign_type: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(require_login),
):
    query = db.query(SignDict)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            SignDict.meaning.like(pattern)
            | SignDict.sign_code.like(pattern)
            | SignDict.position_desc.like(pattern)
        )
    if road_section:
        query = query.filter(SignDict.road_section.contains(road_section.strip()))
    if direction:
        query = query.filter(SignDict.direction.contains(direction.strip()))
    if sign_type:
        query = query.filter(SignDict.sign_type == sign_type)
    signs = query.order_by(SignDict.road_section.asc(), SignDict.id.asc()).limit(100).all()
    return {
        "total": len(signs),
        "data": [sign_to_dict(s) for s in signs],
    }


@app.get("/api/signs/nearby")
def nearby_signs(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5, gt=0, le=500),
    limit: int = Query(20, ge=1, le=100),
    sign_type: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(require_login),
):
    query = db.query(SignDict).filter(
        SignDict.latitude.isnot(None),
        SignDict.longitude.isnot(None),
    )
    if sign_type:
        query = query.filter(SignDict.sign_type == sign_type)

    rows = []
    for sign in query.all():
        distance_km = calculate_distance_km(latitude, longitude, sign.latitude, sign.longitude)
        if distance_km <= radius_km:
            item = sign_to_dict(sign)
            item["distance_km"] = round(distance_km, 3)
            rows.append(item)

    rows.sort(key=lambda item: (item["distance_km"], item["id"]))
    rows = rows[:limit]
    return {
        "query": {
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km,
            "limit": limit,
            "sign_type": sign_type,
        },
        "total": len(rows),
        "data": rows,
    }


@app.post("/api/signs")
def create_sign(body: SignCreate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    # 唯一性校验：sign_code 不能重复
    existing = db.query(SignDict).filter(SignDict.sign_code == body.sign_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"标签编码 '{body.sign_code}' 已存在，请勿重复添加")
    now = datetime.now()
    sign = SignDict(**body.model_dump(), created_at=now, updated_at=now)
    db.add(sign)
    db.flush()
    add_audit_log(
        db,
        current_user,
        action="create",
        resource_type="sign",
        resource_id=sign.id,
        summary=f"新增标志 {sign.sign_code}（{sign.meaning}）",
        detail={"sign": sign_to_dict(sign)},
    )
    db.commit()
    db.refresh(sign)
    return sign_to_dict(sign)


@app.delete("/api/signs/{sign_id}")
def delete_sign(sign_id: int, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    sign = db.query(SignDict).filter(SignDict.id == sign_id).first()
    if not sign:
        raise HTTPException(status_code=404, detail="标志不存在")
    used = db.query(DetectRecord).filter(DetectRecord.detected_signs.contains(sign.meaning)).first()
    if used:
        raise HTTPException(status_code=409, detail="该标志已被检测记录引用，不能直接删除")
    sign_snapshot = sign_to_dict(sign)
    db.delete(sign)
    add_audit_log(
        db,
        current_user,
        action="delete",
        resource_type="sign",
        resource_id=sign_id,
        summary=f"删除标志 {sign.sign_code}（{sign.meaning}）",
        detail={"sign": sign_snapshot},
    )
    db.commit()
    return {"status": "success"}


@app.put("/api/signs/{sign_id}")
def update_sign(sign_id: int, body: SignUpdate, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    sign = db.query(SignDict).filter(SignDict.id == sign_id).first()
    if not sign:
        raise HTTPException(status_code=404, detail="标志不存在")
    payload = body.model_dump(exclude_none=True)
    if "sign_code" in payload:
        existing = db.query(SignDict).filter(
            SignDict.sign_code == payload["sign_code"],
            SignDict.id != sign_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"标签编码 '{payload['sign_code']}' 已存在，请勿重复使用")
    before = sign_to_dict(sign)
    for field, value in payload.items():
        setattr(sign, field, value)
    sign.updated_at = datetime.now()
    after = sign_to_dict(sign)
    changes = {
        field: {"before": before.get(field), "after": after.get(field)}
        for field in payload
        if before.get(field) != after.get(field)
    }
    add_audit_log(
        db,
        current_user,
        action="update",
        resource_type="sign",
        resource_id=sign_id,
        summary=f"更新标志 {sign.sign_code}（{sign.meaning}）",
        detail={"changes": changes},
    )
    db.commit()
    return {"status": "success", "id": sign_id}


@app.delete("/api/records/{record_id}")
def delete_record(record_id: int, db: Session = Depends(get_db), current_user: dict = Depends(require_admin)):
    record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    violation_count = db.query(ViolationRecord).filter(ViolationRecord.detect_id == record_id).count()
    artifact_paths = collect_record_artifact_paths(record)
    artifact_references = [static_reference_from_path(path) for path in sorted(artifact_paths)]
    record_snapshot = {
        "id": record.id,
        "username": record.username,
        "source_type": record.source_type,
        "detected_signs": record.detected_signs,
        "location_text": record.location_text,
        "create_time": str(record.create_time) if record.create_time else None,
        "violation_count": violation_count,
        "artifact_count": len(artifact_references),
        "artifacts": artifact_references,
    }
    
    # 删除主记录
    db.delete(record)
    
    # 级联删除相关的违规记录
    db.query(ViolationRecord).filter(ViolationRecord.detect_id == record_id).delete()
    add_audit_log(
        db,
        current_user,
        action="delete",
        resource_type="detect_record",
        resource_id=record_id,
        summary=f"删除检测记录 #{record_id}",
        detail=record_snapshot,
    )
    db.commit()
    removed_files = remove_static_files(artifact_paths)
    return {"status": "success", "removed_files": removed_files, "removed_file_count": len(removed_files)}

# ────────────────────────────────────────────────
# 数据统计接口
# ────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db), current_user: dict = Depends(require_login)):
    is_admin = current_user["role"] == "admin"
    username = current_user["username"]
    cache_date = None
    cached = None

    # 近30天检测趋势
    det_q = db.query(func.date(DetectRecord.create_time).label("date"), func.count(DetectRecord.id).label("count"))
    if not is_admin:
        det_q = det_q.filter(DetectRecord.username == username)
    daily_detects = det_q.group_by(func.date(DetectRecord.create_time)).order_by(func.date(DetectRecord.create_time).desc()).limit(30).all()

    # 近30天违规趋势（驾驶员：只统计自己检测产生的违规）
    if is_admin:
        vio_q = db.query(func.date(ViolationRecord.create_time).label("date"), func.count(ViolationRecord.id).label("count"))
    else:
        my_ids = db.query(DetectRecord.id).filter(DetectRecord.username == username)
        vio_q = db.query(func.date(ViolationRecord.create_time).label("date"), func.count(ViolationRecord.id).label("count")).filter(ViolationRecord.detect_id.in_(my_ids))
    daily_violations = vio_q.group_by(func.date(ViolationRecord.create_time)).order_by(func.date(ViolationRecord.create_time).desc()).limit(30).all()

    sign_updates = db.query(
        func.date(SignDict.updated_at).label("date"),
        func.count(SignDict.id).label("count"),
    ).filter(SignDict.updated_at.isnot(None)).group_by(
        func.date(SignDict.updated_at)
    ).order_by(func.date(SignDict.updated_at).desc()).limit(30).all()

    # 管理员优先读预聚合缓存；驾驶员实时计算自己的数据
    if is_admin:
        yesterday = (datetime.now() - timedelta(days=1)).date()
        cached = db.query(StatsDaily).filter(StatsDaily.stat_date == yesterday).first()
        if cached and cached.top_signs_json:
            top_signs_data = json.loads(cached.top_signs_json)
            violation_pie = json.loads(cached.violation_pie_json)
            cache_date = str(cached.stat_date)
        else:
            cached = None

    if not is_admin or not cached:
        base_q = db.query(DetectRecord)
        if not is_admin:
            base_q = base_q.filter(DetectRecord.username == username)
        sign_counts = base_q.with_entities(
            DetectRecord.detected_signs, func.count(DetectRecord.id).label("count")
        ).filter(DetectRecord.detected_signs != '未检测到标志').group_by(DetectRecord.detected_signs).order_by(func.count(DetectRecord.id).desc()).limit(10).all()
        top_signs_data = [{"name": s[0], "value": s[1]} for s in sign_counts]

        violation_query = db.query(ViolationRecord)
        if not is_admin:
            my_ids = db.query(DetectRecord.id).filter(DetectRecord.username == username)
            violation_query = violation_query.filter(ViolationRecord.detect_id.in_(my_ids))
        violation_counter = {}
        for violation in violation_query.all():
            category = _violation_type_label(violation.violation_type, violation.violation_msg or "")
            violation_counter[category] = violation_counter.get(category, 0) + 1
        violation_pie = [
            {"name": name, "value": count}
            for name, count in sorted(violation_counter.items(), key=lambda item: item[1], reverse=True)
        ]
        if not violation_pie:
            violation_pie = [{"name": "暂无违规数据", "value": 0}]

    total_det_q = db.query(func.count(DetectRecord.id))
    if not is_admin:
        total_det_q = total_det_q.filter(DetectRecord.username == username)

    if is_admin:
        total_vio = db.query(func.count(ViolationRecord.id)).scalar()
        pending_vio = db.query(func.count(ViolationRecord.id)).filter(
            or_(ViolationRecord.status.is_(None), ViolationRecord.status == "pending")
        ).scalar()
    else:
        my_ids = db.query(DetectRecord.id).filter(DetectRecord.username == username)
        total_vio = db.query(func.count(ViolationRecord.id)).filter(ViolationRecord.detect_id.in_(my_ids)).scalar()
        pending_vio = db.query(func.count(ViolationRecord.id)).filter(
            ViolationRecord.detect_id.in_(my_ids),
            or_(ViolationRecord.status.is_(None), ViolationRecord.status == "pending"),
        ).scalar()

    return {
        "top_signs": top_signs_data,
        "violation_pie": violation_pie,
        "detect_trend": [{"date": str(d.date), "count": d.count} for d in daily_detects],
        "violation_trend": [{"date": str(d.date), "count": d.count} for d in daily_violations],
        "sign_update_trend": [{"date": str(d.date), "count": d.count} for d in sign_updates],
        "total_detections": total_det_q.scalar(),
        "total_violations": total_vio,
        "pending_violations": pending_vio,
        "cache_date": cache_date,
    }


# ────────────────────────────────────────────────
# 日报与报告导出接口
# ────────────────────────────────────────────────

@app.get("/api/reports/daily")
def list_daily_reports(
    limit: int = Query(30, ge=1, le=366),
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    reports = db.query(StatsDaily).order_by(StatsDaily.stat_date.desc()).limit(limit).all()
    return [_build_daily_payload(report) for report in reports]


@app.post("/api/reports/daily/rebuild")
def rebuild_daily_report(
    stat_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    target_date = parse_date_param(stat_date, "stat_date") if stat_date else (datetime.now() - timedelta(days=1)).date()
    if target_date > datetime.now().date():
        raise HTTPException(status_code=400, detail="不能生成未来日期的日报")
    report = generate_daily_stats(target_date, db, force=True)
    add_audit_log(
        db,
        current_user,
        action="rebuild",
        resource_type="daily_report",
        resource_id=target_date,
        summary=f"重建日报 {target_date}",
        detail=_build_daily_payload(report),
    )
    db.commit()
    return _build_daily_payload(report)


@app.get("/api/reports/daily/{stat_date}")
def get_daily_report(
    stat_date: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    target_date = parse_date_param(stat_date, "stat_date")
    report = db.query(StatsDaily).filter(StatsDaily.stat_date == target_date).first()
    if not report:
        raise HTTPException(status_code=404, detail="日报不存在，请先手动生成")
    return _build_daily_payload(report)


@app.get("/api/reports/daily/{stat_date}/export")
def export_daily_report(
    stat_date: str,
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    target_date = parse_date_param(stat_date, "stat_date")
    report = db.query(StatsDaily).filter(StatsDaily.stat_date == target_date).first()
    if not report:
        raise HTTPException(status_code=404, detail="日报不存在，请先手动生成")
    payload = _build_daily_payload(report)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["统计日期", "检测总数", "违规总数", "生成时间"])
    writer.writerow([
        payload["stat_date"],
        payload["total_detections"],
        payload["total_violations"],
        payload["created_at"] or "",
    ])
    writer.writerow([])
    writer.writerow(["高频标志", "次数"])
    for item in payload["top_signs"]:
        writer.writerow([item.get("name", ""), item.get("value", 0)])
    writer.writerow([])
    writer.writerow(["违规类型", "次数"])
    for item in payload["violation_pie"]:
        writer.writerow([item.get("name", ""), item.get("value", 0)])
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=daily_report_{payload['stat_date']}.csv"}
    )

# ────────────────────────────────────────────────
# 登录 & 注册接口
# ────────────────────────────────────────────────

class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)

class RegisterBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = "driver"   # 默认注册为驾驶员；管理员由超级管理员在数据库中手动设置

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("用户名不能为空")
        return value

@app.post("/api/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = make_token(body.username, user.role)
    return {"token": token, "username": user.username, "role": user.role}

@app.post("/api/register")
def register(body: RegisterBody, db: Session = Depends(get_db)):
    # 用户名唯一性校验
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在，请换一个")
    # 角色只允许注册为 driver（防止前端绕过注册 admin）
    if body.role not in ("driver",):
        raise HTTPException(status_code=400, detail="注册角色非法，只能注册为驾驶员")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role="driver"
    )
    db.add(user)
    db.commit()
    return {"message": "注册成功，请登录", "username": user.username, "role": user.role}


@app.get("/api/me")
def get_current_user(current_user: dict = Depends(require_login)):
    return current_user


@app.get("/api/audit-logs")
def get_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    start_dt = parse_datetime_param(start_time, "start_time")
    end_dt = parse_datetime_param(end_time, "end_time")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="开始时间不能晚于结束时间")

    query = db.query(AuditLog)
    if username:
        query = query.filter(AuditLog.username.contains(username.strip()))
    if action:
        query = query.filter(AuditLog.action == action.strip())
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type.strip())
    if start_dt:
        query = query.filter(AuditLog.create_time >= start_dt)
    if end_dt:
        query = query.filter(AuditLog.create_time <= end_dt)

    total = query.count()
    logs = query.order_by(AuditLog.create_time.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "data": [audit_to_dict(log) for log in logs],
    }


@app.get("/api/storage/status")
def get_storage_status(
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    return build_storage_status(db)


@app.post("/api/storage/cleanup")
def cleanup_storage(
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    _, _, orphaned = collect_storage_inventory(db)
    orphan_refs = [static_reference_from_path(path) for path in orphaned]
    removed_files = [] if dry_run else remove_static_files(orphaned)

    if not dry_run:
        add_audit_log(
            db,
            current_user,
            action="cleanup",
            resource_type="storage",
            resource_id=None,
            summary=f"清理孤儿静态文件 {len(removed_files)} 个",
            detail={
                "orphaned_file_count": len(orphan_refs),
                "removed_file_count": len(removed_files),
                "removed_files": removed_files[:100],
            },
        )
        db.commit()

    return {
        "dry_run": dry_run,
        "orphaned_file_count": len(orphan_refs),
        "orphaned_files": orphan_refs[:100],
        "removed_file_count": len(removed_files),
        "removed_files": removed_files,
        "status": build_storage_status(db),
    }


@app.get("/api/report")
def export_report(
    sign_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    start_dt = parse_datetime_param(start_time, "start_time")
    end_dt = parse_datetime_param(end_time, "end_time")
    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(status_code=400, detail="开始时间不能晚于结束时间")

    query = db.query(DetectRecord)
    if sign_type:
        query = query.filter(DetectRecord.detected_signs.contains(sign_type))
    if start_dt:
        query = query.filter(DetectRecord.create_time >= start_dt)
    if end_dt:
        query = query.filter(DetectRecord.create_time <= end_dt)
    records = query.order_by(DetectRecord.create_time.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "检测时间", "来源类型", "位置", "识别标志", "原图/视频路径", "结果图路径", "违规类型", "风险级别", "违规信息"])
    for r in records:
        violations = db.query(ViolationRecord).filter(ViolationRecord.detect_id == r.id).all()
        violation_str = " | ".join(v.violation_msg for v in violations) if violations else "无"
        violation_type_str = " | ".join(_violation_type_label(v.violation_type, v.violation_msg or "") for v in violations) if violations else "无"
        severity_str = " | ".join(v.severity or "unknown" for v in violations) if violations else "无"
        writer.writerow([
            r.id,
            r.create_time,
            r.source_type or "image",
            r.location_text or "",
            r.detected_signs,
            r.original_image_url,
            r.result_image_url,
            violation_type_str,
            severity_str,
            violation_str,
        ])
    output.seek(0)
    filename = f"traffic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

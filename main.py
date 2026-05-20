from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from ultralytics import YOLO
import shutil
import os
import cv2
import csv
import io
import hashlib
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, func
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

# 数据库配置
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:wh051116@localhost:3306/traffic_system"
engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 新增：补充两张新表的 ORM 模型 ---

class User(Base):
    """用户表：存储系统账号，支持 admin（管理员）和 driver（驾驶员）两种角色"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(64), nullable=False)   # SHA-256 哈希
    role = Column(String(20), nullable=False, default="driver")  # admin | driver
    create_time = Column(DateTime, default=datetime.now)

class SignDict(Base):
    __tablename__ = "sign_dict"
    id = Column(Integer, primary_key=True, index=True)
    sign_code = Column(String(50))
    meaning = Column(String(100))
    sign_type = Column(String(50))
    limit_value = Column(Float, nullable=True)

class DetectRecord(Base):
    __tablename__ = "detect_records"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=True, index=True)   # 提交检测的用户
    original_image_url = Column(String(255))
    result_image_url = Column(String(255))
    detected_signs = Column(String(255))
    create_time = Column(DateTime, default=datetime.now)

class ViolationRecord(Base):
    __tablename__ = "violation_records"
    id = Column(Integer, primary_key=True, index=True)
    detect_id = Column(Integer)
    violation_msg = Column(String(255))
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

import json

# ────────────────────────────────────────────────
# 定时统计任务：每天 00:00 聚合前一天数据写入 stats_daily
# ────────────────────────────────────────────────

def run_daily_stats():
    """聚合昨天的检测量、违规量、TOP10标志、违规占比，写入 stats_daily 表"""
    db = SessionLocal()
    try:
        yesterday = (datetime.now() - timedelta(days=1)).date()

        # 幂等：已有则跳过
        exists = db.query(StatsDaily).filter(StatsDaily.stat_date == yesterday).first()
        if exists:
            return

        # 昨天检测总量
        total_det = db.query(func.count(DetectRecord.id)).filter(
            func.date(DetectRecord.create_time) == yesterday
        ).scalar() or 0

        # 昨天违规总量
        total_vio = db.query(func.count(ViolationRecord.id)).filter(
            func.date(ViolationRecord.create_time) == yesterday
        ).scalar() or 0

        # TOP10 标志（全量，不限昨天，保持与实时一致）
        top_raw = db.query(
            DetectRecord.detected_signs, func.count(DetectRecord.id).label("cnt")
        ).group_by(DetectRecord.detected_signs).order_by(func.count(DetectRecord.id).desc()).limit(10).all()
        top_signs = [{"name": r.detected_signs, "value": r.cnt} for r in top_raw]

        # 违规占比（全量）
        pie_raw = db.query(
            ViolationRecord.violation_msg, func.count(ViolationRecord.id).label("cnt")
        ).group_by(ViolationRecord.violation_msg).all()
        violation_pie = [{"name": r.violation_msg, "value": r.cnt} for r in pie_raw]

        db.add(StatsDaily(
            stat_date=yesterday,
            total_detections=total_det,
            total_violations=total_vio,
            top_signs_json=json.dumps(top_signs, ensure_ascii=False),
            violation_pie_json=json.dumps(violation_pie, ensure_ascii=False),
        ))
        db.commit()
        print(f"[定时任务] {yesterday} 统计完成：检测 {total_det} 次，违规 {total_vio} 起")
    except Exception as e:
        print(f"[定时任务] 统计失败: {e}")
        db.rollback()
    finally:
        db.close()


scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
scheduler.add_job(run_daily_stats, "cron", hour=0, minute=0)


@asynccontextmanager
async def lifespan(app):
    scheduler.start()
    print("[定时任务] APScheduler 已启动，每天 00:00 自动聚合统计数据")
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 新增：将 static 文件夹挂载到网络上，前端才能通过网址访问图片 ---
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

print("正在加载 YOLO 模型...")
model = YOLO('best.pt')

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

# ────────────────────────────────────────────────
# 工具函数：密码哈希 & 权限校验
# ────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# 简单 token 规则：role:username（生产环境应换 JWT）
def make_token(username: str, role: str) -> str:
    return f"{role}:{username}"

def parse_token(token: str):
    """返回 (role, username)，无效则返回 (None, None)"""
    try:
        role, username = token.split(":", 1)
        return role, username
    except Exception:
        return None, None

def require_admin(authorization: Optional[str] = Header(None)):
    """依赖注入：要求请求方携带管理员 token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    token = authorization.replace("Bearer ", "")
    role, _ = parse_token(token)
    if role != "admin":
        raise HTTPException(status_code=403, detail="权限不足，该操作仅限管理员")

def require_login(authorization: Optional[str] = Header(None)):
    """依赖注入：要求已登录（任意角色）"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录，请先登录")
    token = authorization.replace("Bearer ", "")
    role, username = parse_token(token)
    if not role:
        raise HTTPException(status_code=401, detail="Token 无效，请重新登录")
    return {"role": role, "username": username}


@app.post("/api/detect")
async def detect_sign(
    file: UploadFile = File(...),
    current_speed: float = Form(...),
    current_action: str = Form(default="直行"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_login)
):
    # 按时间戳规则命名：orig_YYYYMMDD_HHMMSS_ffffff.jpg
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    orig_img_path = f"static/orig_{timestamp}.jpg"
    res_img_path = f"static/res_{timestamp}.jpg"
    
    # 1. 保存前端传来的原图
    with open(orig_img_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. 执行模型推理
    results = model.predict(source=orig_img_path)
    
    # --- 新增：自己读取原图，作为画板准备画框 ---
    res_img = cv2.imread(orig_img_path)
    
    detected_signs = []
    violation_alerts = []
    
    # 3. 解析结果并比对字典，顺便把中文画上去
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            box_coords = box.xyxy[0] # 获取框的四个角坐标
            
            sign_info = db.query(SignDict).filter(SignDict.id == cls_id).first()
            if sign_info:
                meaning = sign_info.meaning # 这里就是中文含义了！
                detected_signs.append(meaning)
                
                # --- 核心：调用我们刚才写的函数，把中文和框画到 res_img 上 ---
                res_img = draw_chinese_box(res_img, box_coords, meaning, conf)
                
                # --- 下面的违规判断保持原样 ---
                if sign_info.limit_value is not None:
                    if sign_info.sign_code.startswith("pl") and current_speed > sign_info.limit_value:
                        violation_alerts.append(f"超速警报！当前车速 {current_speed}km/h，该路段 {sign_info.meaning}。")
                if sign_info.sign_type == "禁止标志":
                    if current_action == "掉头" and "掉头" in sign_info.meaning:
                        violation_alerts.append(f"违规操作！前方 {sign_info.meaning}。")
                    elif current_action == "鸣笛" and "鸣喇叭" in sign_info.meaning:
                        violation_alerts.append(f"违规操作！前方 {sign_info.meaning}。")

    # --- 循环结束后，把我们自己画好中文的图保存下来 ---
    cv2.imwrite(res_img_path, res_img)

    detected_signs = list(set(detected_signs)) # 去重
    
    # --- 新增：将记录插入 MySQL 数据库 ---
    signs_str = ",".join(detected_signs) if detected_signs else "未检测到标志"
    
    # 写入识别主表
    new_record = DetectRecord(
        username=current_user["username"],
        original_image_url=orig_img_path,
        result_image_url=res_img_path,
        detected_signs=signs_str
    )
    db.add(new_record)
    db.flush() # 生成了 new_record.id，方便下面关联
    
    # 写入违规子表（含5分钟抑制：同一违规消息5分钟内不重复写入）
    if len(violation_alerts) > 0:
        suppress_window = datetime.now() - timedelta(minutes=5)
        for msg in violation_alerts:
            recent = db.query(ViolationRecord).filter(
                ViolationRecord.violation_msg == msg,
                ViolationRecord.create_time >= suppress_window
            ).first()
            if recent:
                print(f"[违规抑制] 5分钟内已有相同违规记录，跳过写入: {msg}")
            else:
                db.add(ViolationRecord(detect_id=new_record.id, violation_msg=msg))
            
    db.commit() # 真正提交保存到数据库

    # 4. 返回完整数据和图片网络地址给前端
    # 注意：这里的 127.0.0.1 如果你们是局域网联调，需要换成同学 A 的真实局域网 IP
    base_url = "http://localhost:8000/"
    return {
        "status": "success",
        "detected_signs": detected_signs,
        "is_violation": len(violation_alerts) > 0,
        "violation_msgs": violation_alerts,
        "original_image": base_url + orig_img_path, # 传给前端的原图地址
        "result_image": base_url + res_img_path     # 传给前端的带框结果图地址
    }


# ────────────────────────────────────────────────
# 历史记录接口
# ────────────────────────────────────────────────

@app.get("/api/records")
def get_records(
    page: int = 1,
    size: int = 20,
    sign_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    has_violation: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_login)
):
    query = db.query(DetectRecord)
    # 驾驶员只能看自己的记录
    if current_user["role"] != "admin":
        query = query.filter(DetectRecord.username == current_user["username"])
    if sign_type:
        query = query.filter(DetectRecord.detected_signs.contains(sign_type))
    if start_time:
        query = query.filter(DetectRecord.create_time >= start_time)
    if end_time:
        query = query.filter(DetectRecord.create_time <= end_time)
    if has_violation == "true":
        violation_ids = db.query(ViolationRecord.detect_id).distinct()
        query = query.filter(DetectRecord.id.in_(violation_ids))
    elif has_violation == "false":
        violation_ids = db.query(ViolationRecord.detect_id).distinct()
        query = query.filter(DetectRecord.id.notin_(violation_ids))
    total = query.count()
    records = query.order_by(DetectRecord.create_time.desc()).offset((page - 1) * size).limit(size).all()
    base_url = "http://localhost:8000/"
    return {
        "total": total,
        "page": page,
        "size": size,
        "data": [
            {
                "id": r.id,
                "detected_signs": r.detected_signs,
                "original_image": base_url + r.original_image_url,
                "result_image": base_url + r.result_image_url,
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
    base_url = "http://localhost:8000/"
    return {
        "id": r.id,
        "detected_signs": r.detected_signs,
        "original_image": base_url + r.original_image_url,
        "result_image": base_url + r.result_image_url,
        "create_time": r.create_time,
        "violations": [{"id": v.id, "violation_msg": v.violation_msg, "create_time": v.create_time} for v in violations]
    }


# ────────────────────────────────────────────────
# 违规记录接口
# ────────────────────────────────────────────────

@app.get("/api/violations")
def get_violations(
    page: int = 1,
    size: int = 20,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ViolationRecord)
    if start_time:
        query = query.filter(ViolationRecord.create_time >= start_time)
    if end_time:
        query = query.filter(ViolationRecord.create_time <= end_time)
    total = query.count()
    records = query.order_by(ViolationRecord.create_time.desc()).offset((page - 1) * size).limit(size).all()
    return {
        "total": total,
        "page": page,
        "size": size,
        "data": [
            {"id": v.id, "detect_id": v.detect_id, "violation_msg": v.violation_msg, "create_time": v.create_time}
            for v in records
        ]
    }


# ────────────────────────────────────────────────
# 标志字典管理接口（CRUD）
# ────────────────────────────────────────────────

class SignCreate(BaseModel):
    sign_code: str
    meaning: str
    sign_type: str
    limit_value: Optional[float] = None

class SignUpdate(BaseModel):
    sign_code: Optional[str] = None
    meaning: Optional[str] = None
    sign_type: Optional[str] = None
    limit_value: Optional[float] = None


@app.get("/api/signs")
def get_signs(db: Session = Depends(get_db)):
    signs = db.query(SignDict).all()
    return [
        {"id": s.id, "sign_code": s.sign_code, "meaning": s.meaning, "sign_type": s.sign_type, "limit_value": s.limit_value}
        for s in signs
    ]


@app.post("/api/signs")
def create_sign(body: SignCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    # 唯一性校验：sign_code 不能重复
    existing = db.query(SignDict).filter(SignDict.sign_code == body.sign_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"标签编码 '{body.sign_code}' 已存在，请勿重复添加")
    sign = SignDict(**body.model_dump())
    db.add(sign)
    db.commit()
    db.refresh(sign)
    return {"id": sign.id, "sign_code": sign.sign_code, "meaning": sign.meaning}


@app.delete("/api/signs/{sign_id}")
def delete_sign(sign_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    sign = db.query(SignDict).filter(SignDict.id == sign_id).first()
    if not sign:
        raise HTTPException(status_code=404, detail="标志不存在")
    db.delete(sign)
    db.commit()
    return {"status": "success"}


@app.put("/api/signs/{sign_id}")
def update_sign(sign_id: int, body: SignUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    sign = db.query(SignDict).filter(SignDict.id == sign_id).first()
    if not sign:
        raise HTTPException(status_code=404, detail="标志不存在")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(sign, field, value)
    db.commit()
    return {"status": "success", "id": sign_id}


@app.delete("/api/records/{record_id}")
def delete_record(record_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    record = db.query(DetectRecord).filter(DetectRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    
    # 删除主记录
    db.delete(record)
    
    # 级联删除相关的违规记录
    db.query(ViolationRecord).filter(ViolationRecord.detect_id == record_id).delete()
    db.commit()
    return {"status": "success"}

# ────────────────────────────────────────────────
# 数据统计接口
# ────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db), current_user: dict = Depends(require_login)):
    is_admin = current_user["role"] == "admin"
    username = current_user["username"]

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

    # 管理员优先读预聚合缓存；驾驶员实时计算自己的数据
    if is_admin:
        yesterday = (datetime.now() - timedelta(days=1)).date()
        cached = db.query(StatsDaily).filter(StatsDaily.stat_date == yesterday).first()
        if cached and cached.top_signs_json:
            top_signs_data = json.loads(cached.top_signs_json)
            violation_pie = json.loads(cached.violation_pie_json)
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

        if is_admin:
            all_violations = db.query(ViolationRecord.violation_msg).all()
        else:
            my_ids = db.query(DetectRecord.id).filter(DetectRecord.username == username)
            all_violations = db.query(ViolationRecord.violation_msg).filter(ViolationRecord.detect_id.in_(my_ids)).all()
        speeding = sum(1 for v in all_violations if "超速" in v[0])
        action = sum(1 for v in all_violations if "违规操作" in v[0])
        violation_pie = [{"name": "超速行驶", "value": speeding}, {"name": "违章操作(掉头/鸣笛)", "value": action}]
        if speeding == 0 and action == 0:
            violation_pie = [{"name": "暂无违规数据", "value": 0}]

    total_det_q = db.query(func.count(DetectRecord.id))
    if not is_admin:
        total_det_q = total_det_q.filter(DetectRecord.username == username)

    if is_admin:
        total_vio = db.query(func.count(ViolationRecord.id)).scalar()
    else:
        my_ids = db.query(DetectRecord.id).filter(DetectRecord.username == username)
        total_vio = db.query(func.count(ViolationRecord.id)).filter(ViolationRecord.detect_id.in_(my_ids)).scalar()

    return {
        "top_signs": top_signs_data,
        "violation_pie": violation_pie,
        "detect_trend": [{"date": str(d.date), "count": d.count} for d in daily_detects],
        "violation_trend": [{"date": str(d.date), "count": d.count} for d in daily_violations],
        "total_detections": total_det_q.scalar(),
        "total_violations": total_vio,
    }


# ────────────────────────────────────────────────
# 报告导出接口（CSV）
# ────────────────────────────────────────────────

# ────────────────────────────────────────────────
# 登录 & 注册接口
# ────────────────────────────────────────────────

class LoginBody(BaseModel):
    username: str
    password: str

class RegisterBody(BaseModel):
    username: str
    password: str
    role: str = "driver"   # 默认注册为驾驶员；管理员由超级管理员在数据库中手动设置

@app.post("/api/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or user.password_hash != hash_password(body.password):
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


@app.get("/api/report")
def export_report(
    sign_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(require_admin)
):
    query = db.query(DetectRecord)
    if sign_type:
        query = query.filter(DetectRecord.detected_signs.contains(sign_type))
    if start_time:
        query = query.filter(DetectRecord.create_time >= start_time)
    if end_time:
        query = query.filter(DetectRecord.create_time <= end_time)
    records = query.order_by(DetectRecord.create_time.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "检测时间", "识别标志", "原图路径", "结果图路径", "违规信息"])
    for r in records:
        violations = db.query(ViolationRecord).filter(ViolationRecord.detect_id == r.id).all()
        violation_str = " | ".join(v.violation_msg for v in violations) if violations else "无"
        writer.writerow([r.id, r.create_time, r.detected_signs, r.original_image_url, r.result_image_url, violation_str])
    output.seek(0)
    filename = f"traffic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
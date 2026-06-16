"""
数据库初始化脚本
运行一次即可：python init_db.py
"""
from datetime import datetime
from sqlalchemy import inspect, text
from main import Base, SignDict, User, engine, SessionLocal, hash_password

# 建表（如果不存在）
Base.metadata.create_all(bind=engine)
print("[OK] 数据表创建完成")

# ── 自动迁移：给已有表补加新列 ──────────────────────────
inspector = inspect(engine)


def add_column_if_missing(table_name, column_name, column_sql):
    columns = {col["name"] for col in inspect(engine).get_columns(table_name)}
    if column_name in columns:
        print(f"[SKIP] {table_name}.{column_name} 列已存在，跳过")
        return
    with engine.connect() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))
        conn.commit()
    print(f"[OK] {table_name}.{column_name} 列已添加")


add_column_if_missing("detect_records", "username", "username VARCHAR(50) NULL")
add_column_if_missing("detect_records", "source_type", "source_type VARCHAR(20) DEFAULT 'image'")
add_column_if_missing("detect_records", "detected_details_json", "detected_details_json VARCHAR(4000) NULL")
add_column_if_missing("detect_records", "location_text", "location_text VARCHAR(200) NULL")

add_column_if_missing("violation_records", "status", "status VARCHAR(20) DEFAULT 'pending'")
add_column_if_missing("violation_records", "handled_by", "handled_by VARCHAR(50) NULL")
add_column_if_missing("violation_records", "handled_at", "handled_at DATETIME NULL")
add_column_if_missing("violation_records", "violation_type", "violation_type VARCHAR(50) NULL")
add_column_if_missing("violation_records", "severity", "severity VARCHAR(20) NULL")

add_column_if_missing("sign_dict", "road_section", "road_section VARCHAR(100) NULL")
add_column_if_missing("sign_dict", "direction", "direction VARCHAR(50) NULL")
add_column_if_missing("sign_dict", "position_desc", "position_desc VARCHAR(200) NULL")
add_column_if_missing("sign_dict", "latitude", "latitude FLOAT NULL")
add_column_if_missing("sign_dict", "longitude", "longitude FLOAT NULL")
add_column_if_missing("sign_dict", "recommended_speed", "recommended_speed FLOAT NULL")
add_column_if_missing("sign_dict", "created_at", "created_at DATETIME NULL")
add_column_if_missing("sign_dict", "updated_at", "updated_at DATETIME NULL")

if not str(engine.url).startswith("sqlite"):
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users MODIFY COLUMN password_hash VARCHAR(255) NOT NULL"))
        conn.commit()
    print("[OK] users.password_hash 已确认支持 PBKDF2 长度")

with engine.connect() as conn:
    conn.execute(text(
        "UPDATE violation_records SET violation_type='speeding', severity='high' "
        "WHERE violation_type IS NULL AND violation_msg LIKE '%超速%'"
    ))
    conn.execute(text(
        "UPDATE violation_records SET violation_type='illegal_u_turn', severity='high' "
        "WHERE violation_type IS NULL AND violation_msg LIKE '%掉头%'"
    ))
    conn.execute(text(
        "UPDATE violation_records SET violation_type='illegal_honking', severity='medium' "
        "WHERE violation_type IS NULL AND (violation_msg LIKE '%鸣笛%' OR violation_msg LIKE '%鸣喇叭%')"
    ))
    conn.execute(text(
        "UPDATE violation_records SET violation_type='illegal_parking', severity='medium' "
        "WHERE violation_type IS NULL AND violation_msg LIKE '%停车%'"
    ))
    conn.commit()
print("[OK] violation_records 结构化违规字段已回填")

db = SessionLocal()

# ── 初始化默认管理员账号 ──────────────────────────────
try:
    if not db.query(User).filter(User.username == "admin").first():
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            role="admin"
        )
        db.add(admin)
        db.commit()
        print("[OK] 默认管理员账号创建完成 (admin / admin123)")
    else:
        print("[SKIP] 管理员账号已存在，跳过")
except Exception as e:
    db.rollback()
    print(f"[ERROR] 创建管理员账号失败: {e}")

# 42 种交通标志初始数据
SIGNS = [
    # (sign_code, meaning, sign_type, limit_value)
    ("i2",    "非机动车行驶",           "指示标志", None),
    ("i4",    "机动车行驶",             "指示标志", None),
    ("i5",    "靠右侧道路行驶",         "指示标志", None),
    ("il100", "最低限速100",            "指示标志", 100.0),
    ("il60",  "最低限速60",             "指示标志", 60.0),
    ("il80",  "最低限速80",             "指示标志", 80.0),
    ("io",    "其他指示标志",           "指示标志", None),
    ("ip",    "人行横道",               "指示标志", None),
    ("p10",   "禁止机动车驶入",         "禁止标志", None),
    ("p11",   "禁止鸣喇叭",             "禁止标志", None),
    ("p12",   "禁止二轮摩托车驶入",     "禁止标志", None),
    ("p19",   "禁止向右转弯",           "禁止标志", None),
    ("p23",   "禁止向左转弯",           "禁止标志", None),
    ("p26",   "禁止载货汽车驶入",       "禁止标志", None),
    ("p27",   "禁止运输危险物品车辆驶入","禁止标志", None),
    ("p3",    "禁止大型客车驶入",       "禁止标志", None),
    ("p5",    "禁止掉头",               "禁止标志", None),
    ("p6",    "禁止非机动车进入",       "禁止标志", None),
    ("pg",    "减速让行",               "禁止标志", None),
    ("ph4",   "限制高度4m",             "禁止标志", 4.0),
    ("ph4.5", "限制高度3.5m",           "禁止标志", 3.5),
    ("pl100", "限制速度100",            "禁止标志", 100.0),
    ("pl120", "限制速度120",            "禁止标志", 120.0),
    ("pl20",  "限制速度20",             "禁止标志", 20.0),
    ("pl30",  "限制速度30",             "禁止标志", 30.0),
    ("pl40",  "限制速度40",             "禁止标志", 40.0),
    ("pl5",   "限制速度5",              "禁止标志", 5.0),
    ("pl50",  "限制速度50",             "禁止标志", 50.0),
    ("pl60",  "限制速度60",             "禁止标志", 60.0),
    ("pl70",  "限制速度70",             "禁止标志", 70.0),
    ("pl80",  "限制速度80",             "禁止标志", 80.0),
    ("pm20",  "限制质量20t",            "禁止标志", 20.0),
    ("pm30",  "限制质量30t",            "禁止标志", 30.0),
    ("pm55",  "限制质量55t",            "禁止标志", 55.0),
    ("pn",    "禁止停车",               "禁止标志", None),
    ("pne",   "禁止驶入",               "禁止标志", None),
    ("po",    "其他禁止标志",           "禁止标志", None),
    ("pr40",  "解除限制速度40",         "禁止标志", None),
    ("w13",   "十字交叉路口",           "警告标志", None),
    ("w55",   "注意儿童",               "警告标志", None),
    ("w57",   "注意行人",               "警告标志", None),
    ("w59",   "注意合流",               "警告标志", None),
]

db = SessionLocal()
try:
    existing = db.query(SignDict).count()
    if existing > 0:
        print(f"[SKIP] sign_dict 表已有 {existing} 条数据，跳过初始化（避免重复插入）")
    else:
        for idx, (code, meaning, stype, limit) in enumerate(SIGNS):
            db.add(SignDict(
                id=idx,          # YOLO class id 从 0 开始，与模型对齐
                sign_code=code,
                meaning=meaning,
                sign_type=stype,
                limit_value=limit
            ))
        db.commit()
        print(f"[OK] 成功插入 {len(SIGNS)} 条标志字典数据")
    location_updated = 0
    timestamp_updated = 0
    for sign in db.query(SignDict).all():
        if not sign.road_section:
            sign.road_section = f"G5京昆高速 K{100 + sign.id}"
            sign.direction = "成都方向" if sign.id % 2 == 0 else "西安方向"
            sign.position_desc = f"{sign.road_section} {sign.direction} 路侧标志"
            sign.latitude = 30.0 + (sign.id * 0.01)
            sign.longitude = 103.0 + (sign.id * 0.01)
            if sign.sign_code.startswith("pl") and sign.limit_value is not None:
                sign.recommended_speed = sign.limit_value
            location_updated += 1
        if not sign.created_at:
            sign.created_at = datetime.now()
            timestamp_updated += 1
        if not sign.updated_at:
            sign.updated_at = sign.created_at or datetime.now()
            timestamp_updated += 1
    if location_updated or timestamp_updated:
        db.commit()
        if location_updated:
            print(f"[OK] 已为 {location_updated} 条标志补充示例位置数据")
        if timestamp_updated:
            print(f"[OK] 已补齐 {timestamp_updated} 个标志时间戳字段")
finally:
    db.close()

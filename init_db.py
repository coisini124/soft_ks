"""
数据库初始化脚本
运行一次即可：python init_db.py
"""
import hashlib
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from main import Base, SignDict, User, engine, SessionLocal

# 建表（如果不存在）
Base.metadata.create_all(bind=engine)
print("✅ 数据表创建完成")

# ── 自动迁移：给已有表补加新列 ──────────────────────────
with engine.connect() as conn:
    # 检查 detect_records.username 列是否存在
    result = conn.execute(text(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() "
        "AND TABLE_NAME = 'detect_records' "
        "AND COLUMN_NAME = 'username'"
    ))
    if result.scalar() == 0:
        conn.execute(text(
            "ALTER TABLE detect_records "
            "ADD COLUMN username VARCHAR(50) NULL AFTER id, "
            "ADD INDEX idx_dr_username (username)"
        ))
        conn.commit()
        print("✅ detect_records.username 列已添加")
    else:
        print("⚠️  detect_records.username 列已存在，跳过")

db = SessionLocal()

# ── 初始化默认管理员账号 ──────────────────────────────
try:
    if not db.query(User).filter(User.username == "admin").first():
        admin = User(
            username="admin",
            password_hash=hashlib.sha256("admin123".encode()).hexdigest(),
            role="admin"
        )
        db.add(admin)
        db.commit()
        print("✅ 默认管理员账号创建完成 (admin / admin123)")
    else:
        print("⚠️  管理员账号已存在，跳过")
except Exception as e:
    db.rollback()
    print(f"❌ 创建管理员账号失败: {e}")

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
        print(f"⚠️  sign_dict 表已有 {existing} 条数据，跳过初始化（避免重复插入）")
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
        print(f"✅ 成功插入 {len(SIGNS)} 条标志字典数据")
finally:
    db.close()

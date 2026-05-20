# 高速公路交通标志检测与管理系统

基于 YOLOv8 + FastAPI + MySQL 的交通标志检测、识别、违规提醒与数据管理后端服务。

## 项目结构

```
soft_ks/
├── main.py        # FastAPI 后端主程序
├── best.pt        # YOLOv8 训练好的检测模型
├── static/        # 图片存储目录（自动创建）
└── README.md
```

## 环境依赖

Python 3.8+，安装以下依赖：

```bash
pip install fastapi uvicorn ultralytics opencv-python pillow numpy sqlalchemy pymysql pydantic
```

## 数据库配置

使用 MySQL，默认连接信息：

```
host: localhost
port: 3306
database: traffic_system
user: root
password: wh051116
```

需提前创建以下三张表：

```sql
CREATE TABLE sign_dict (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    sign_code   VARCHAR(50),
    meaning     VARCHAR(100),
    sign_type   VARCHAR(50),
    limit_value FLOAT
);

CREATE TABLE detect_records (
    id                 INT PRIMARY KEY AUTO_INCREMENT,
    original_image_url VARCHAR(255),
    result_image_url   VARCHAR(255),
    detected_signs     VARCHAR(255),
    create_time        DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE violation_records (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    detect_id     INT,
    violation_msg VARCHAR(255),
    create_time   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 启动服务

```bash
# 开发模式（自动热重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000
```

启动后访问 `http://localhost:8000/docs` 查看 Swagger 交互文档。

> 局域网联调时，将 `main.py` 中的 `base_url` 改为本机实际 IP，例如 `http://192.168.x.x:8000/`

## API 接口一览

### 检测

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/detect` | 上传图片，执行标志检测与违规判断 |

**请求参数（multipart/form-data）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 待检测图片 |
| current_speed | float | 是 | 当前车速（km/h） |
| current_action | string | 否 | 当前行为，默认"直行"，可选"掉头"/"鸣笛" |

**返回示例：**
```json
{
  "status": "success",
  "detected_signs": ["限制速度60", "禁止掉头"],
  "is_violation": true,
  "violation_msgs": ["超速警报！当前车速80km/h，该路段限制速度60。"],
  "original_image": "http://192.168.72.70:8000/static/orig_20260318_143022_123456.jpg",
  "result_image":   "http://192.168.72.70:8000/static/res_20260318_143022_123456.jpg"
}
```

### 历史记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/records` | 分页查询检测记录 |
| GET | `/api/records/{id}` | 查询单条记录详情（含违规子记录） |

**`/api/records` 查询参数：**

| 参数 | 说明 |
|------|------|
| page | 页码，默认 1 |
| size | 每页条数，默认 20 |
| sign_type | 按标志名称模糊过滤 |
| start_time | 开始时间，格式 `2026-01-01 00:00:00` |
| end_time | 结束时间 |

### 违规记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/violations` | 分页查询违规记录，支持时间过滤 |

### 标志字典管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/signs` | 获取全部标志 |
| POST | `/api/signs` | 新增标志 |
| PUT | `/api/signs/{id}` | 编辑标志 |
| DELETE | `/api/signs/{id}` | 删除标志 |

**新增/编辑请求体（JSON）：**
```json
{
  "sign_code": "pl60",
  "meaning": "限制速度60",
  "sign_type": "禁止标志",
  "limit_value": 60.0
}
```

### 统计与报告

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats` | 返回标志类型分布、每日检测趋势、违规总数 |
| GET | `/api/report` | 导出全量检测数据为 CSV 文件（UTF-8 BOM，Excel 可直接打开） |

## 图片命名规则

所有图片按时间戳命名，存放于 `static/` 目录：

```
static/orig_YYYYMMDD_HHMMSS_ffffff.jpg   # 原始上传图片
static/res_YYYYMMDD_HHMMSS_ffffff.jpg    # 带检测框的结果图片
```

## 违规判断逻辑

| 违规类型 | 触发条件 |
|----------|----------|
| 超速 | `sign_code` 以 `pl` 开头，且 `current_speed > limit_value` |
| 违规掉头 | `sign_type` 为禁止标志，且标志含义含"掉头"，且 `current_action == "掉头"` |
| 违规鸣笛 | `sign_type` 为禁止标志，且标志含义含"鸣喇叭"，且 `current_action == "鸣笛"` |

# 高速公路交通标志检测与管理系统

基于 YOLOv8 + FastAPI + SQLite/MySQL + Vue 3 的交通标志检测、识别、违规提醒与数据管理系统。

## 交付状态说明

当前版本已做基础交付化加固：

- 后端配置通过环境变量管理，默认使用 `sqlite:///./traffic_system.db` 便于本地启动，也可通过 `DATABASE_URL` 切换 MySQL。
- `best.pt` 与 `ultralytics` 改为检测接口按需加载，缺失时 `/api/detect` 返回 503，其他登录、字典、记录、统计接口仍可运行。
- 登录 token 已改为 HMAC 签名格式并带有效期，避免原先 `role:username` 被伪造和长期滥用。
- 上传图片、车速范围、动作枚举、时间范围、字典字段和重复编码都增加了服务端校验。
- 支持图片检测 `/api/detect` 和视频抽帧检测 `/api/detect/video`，并保存结构化解析详情（类别、置信度、框位置、道路位置、建议速度）。
- 真实 YOLO 推理支持可配置置信度阈值，默认读取 `DETECTION_CONFIDENCE`，前端工作台也可按本次检测临时调节识别灵敏度。
- 检测记录会从识别详情中提取 `location_text` 位置摘要，供历史记录、详情页和 CSV 报表直接展示。
- 前端工作台支持图片上传、视频上传、摄像头单帧抓拍和摄像头按间隔连续监控；连续监控复用检测接口并在识别到违规时弹出告警。
- 支持显式演示检测模式：设置 `DETECTOR_MODE=mock` 后，即使没有 `best.pt` 也能跑通图片/视频识别、结构化解析、违规写入和前端展示；默认 `auto` 不会伪装真实模型。
- 标志字典支持维护路段、方向、位置说明、经纬度和建议速度，并提供 `/api/signs/search` 与 `/api/signs/nearby` 给前端按位置查询展示。
- 统计分析包含识别趋势、违规趋势、日报和近 30 天标志字典更新频率。
- 前端统一使用 `VITE_API_BASE_URL` 和 `src/api/client.js` 访问 API，报表导出会携带 Authorization。
- 前端路由与菜单按角色控制，驾驶员无法直接进入管理员字典和分析页面；后端仍作为最终权限边界。
- 违规预警台账支持待处理/已处理状态，管理员可以确认处理或重新打开警报；每次检测产生的违规都会关联当前检测记录落库，违规类型和风险级别会结构化保存并进入 CSV 报表。
- 关键管理操作会写入审计日志，覆盖标志字典增删改、违规处理状态变更、检测记录删除和日报重建，管理员可在前端“操作审计日志”页面追踪操作人、动作、对象和详情。
- 检测结果文件支持存储巡检和孤儿文件清理；删除检测记录会同步清理关联的原图、结果图、视频和抽帧文件，避免长期运行后磁盘堆积。

复制 `.env.example` 为 `.env` 后按需修改：

```bash
DATABASE_URL=sqlite:///./traffic_system.db
APP_BASE_URL=http://localhost:8000
MODEL_PATH=best.pt
DETECTOR_MODE=auto
MOCK_SIGN_ID=28
DETECTION_CONFIDENCE=0.25
TOKEN_SECRET=replace-with-a-long-random-secret
TOKEN_TTL_SECONDS=86400
```

如果只是课堂演示或验收流程联调、暂时没有真实模型，可临时设置：

```bash
DETECTOR_MODE=mock
MOCK_SIGN_ID=28   # 默认对应“限制速度60”，车速大于 60 会触发超速提醒
```

前端可复制 `traffic-sign-ui/.env.example` 为 `traffic-sign-ui/.env`：

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## 项目结构

```
soft_ks/
├── main.py                  # FastAPI 后端主程序
├── init_db.py               # 建表、轻量迁移与初始化种子数据
├── scripts/                 # smoke、模型验收脚本
├── traffic-sign-ui/         # Vue 3 前端
├── Dockerfile.backend       # 后端容器构建
├── docker-compose.yml       # 本地/演示一键部署
├── models/best.pt           # 可选：真实 YOLOv8 模型权重（不提交）
├── static/                  # 检测图片/视频结果目录（自动创建，不提交）
└── README.md
```

## 环境依赖

Python 3.11 推荐；本地开发可安装以下依赖：

```bash
pip install -r requirements.txt
```

## 数据库配置

默认使用 SQLite，首次启动前运行 `python init_db.py` 会自动建表、轻量迁移并初始化默认管理员与 42 种交通标志。需要 MySQL 时只需切换环境变量：

```bash
DATABASE_URL=mysql+pymysql://user:password@host:3306/traffic_system
```

## 启动服务

```bash
# 初始化本地数据库并写入默认管理员与 42 种标志
python init_db.py

# 开发模式（自动热重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000
```

启动后访问 `http://localhost:8000/docs` 查看 Swagger 交互文档。

局域网联调时，设置 `APP_BASE_URL=http://192.168.x.x:8000`，无需修改源码。

## Docker Compose 部署

默认 compose 使用 SQLite 数据卷与 `DETECTOR_MODE=mock`，适合课堂演示和验收流程联调：

```bash
docker compose up --build
```

访问：

- 前端：`http://localhost:5173`
- 后端 API：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`

如果要启用真实模型，将权重放到 `models/best.pt`，并把 `docker-compose.yml` 中 `DETECTOR_MODE` 改为 `auto`。生产部署前必须修改 `TOKEN_SECRET`，并按实际域名/IP 调整 `APP_BASE_URL`、`VITE_API_BASE_URL` 和 `CORS_ORIGINS`。

## 验证命令

```bash
# 后端基础 smoke：不需要真实模型，会验证鉴权、字典、时间校验和缺模型 503
python -B scripts/smoke_backend.py

# 前端生产构建
cd traffic-sign-ui
npm install
npm run build
```

### 真实模型准确率验收

工程 smoke 只验证系统链路，不代表真实识别准确率。交付时应提供训练好的 `best.pt` 与标注测试集 `data.yaml`，运行：

```bash
python -B scripts/evaluate_model.py --model best.pt --data path/to/data.yaml --split test --output reports/model_eval.json
```

脚本会调用 Ultralytics YOLO 验证流程并输出 `precision`、`recall`、`mAP50`、`mAP50-95` 到 JSON 报告。缺少模型、缺少数据集或缺少 `ultralytics` 时脚本会失败退出，避免把演示模式误当成真实准确率验收。

真实模型上线前还应使用管理员账号调用 `GET /api/model/mapping-check`，确认 YOLO class id、模型 `names` 与 `sign_dict.id/sign_code/meaning` 对齐。该接口会检查字典 id 是否连续、`sign_code` 是否重复、限速类标志是否缺少 `limit_value`，并在模型文件存在时对比模型类别与字典映射。

## API 接口一览

### 检测

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/detect` | 上传图片，执行标志检测与违规判断 |
| POST | `/api/detect/video` | 上传视频，按 `frame_interval` 抽帧检测并汇总标志和违规 |

**请求参数（multipart/form-data）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 待检测图片或视频；摄像头连续监控会按间隔抓取 JPEG 帧上传 |
| current_speed | float | 是 | 当前车速（km/h） |
| current_action | string | 否 | 当前行为，默认"直行"，可选"掉头"/"鸣笛"/"停车" |
| min_confidence | float | 否 | 本次识别置信度阈值，范围 `0..1`，默认读取 `DETECTION_CONFIDENCE` |

**返回示例：**
```json
{
  "status": "success",
  "detected_signs": ["限制速度60", "禁止掉头"],
  "is_violation": true,
  "violation_msgs": ["超速警报！当前车速80km/h，该路段限制速度60。"],
  "violation_events": [
    {
      "type": "speeding",
      "label": "超速行驶",
      "severity": "high",
      "sign_code": "pl60",
      "limit_value": 60.0,
      "current_speed": 80.0,
      "message": "超速警报！当前车速80km/h，该路段限制速度60。"
    }
  ],
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
| GET | `/api/violations` | 分页查询违规记录，支持时间、`status=pending|handled`、`violation_type`、`severity` 过滤 |
| GET | `/api/violations/export` | 按同一套筛选条件导出违规预警台账 CSV；管理员导出全量，驾驶员导出本人记录 |
| PUT | `/api/violations/{id}/status` | 管理员确认处理或重新打开违规警报 |

`/api/violations` 会返回 `violation_type`、`violation_label`、`severity` 和原始 `violation_msg`，便于前端台账展示和后续统计分析。`violation_type` 可选 `speeding`、`illegal_u_turn`、`illegal_honking`、`illegal_parking`；`severity` 可选 `high`、`medium`、`low`。

### 用户与权限

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | 登录并返回带有效期的 HMAC 签名 token，默认 24 小时 |
| POST | `/api/register` | 注册驾驶员账号 |
| GET | `/api/me` | 返回当前 token 对应的服务端身份与角色 |

### 审计日志

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/audit-logs` | 管理员分页查询关键操作日志，支持按操作人、动作、对象类型和时间范围过滤 |

当前审计动作包括 `create`、`update`、`delete`、`update_status` 和 `rebuild`；对象类型包括 `sign`、`violation`、`detect_record` 和 `daily_report`。

### 模型与字典运维

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/model/status` | 查看检测模式、模型文件是否存在、模型是否已加载 |
| GET | `/api/model/mapping-check` | 管理员检查 YOLO 类别 id、模型 names 与标志字典映射是否一致 |

### 标志字典管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/signs` | 获取全部标志 |
| GET | `/api/signs/export` | 管理员导出标志字典 CSV |
| POST | `/api/signs/import?dry_run=true|false` | 管理员批量导入/更新标志字典 CSV；默认 dry-run 只校验不落库 |
| GET | `/api/signs/search` | 按关键词、路段、方向、类型查询标志位置与建议速度 |
| GET | `/api/signs/nearby` | 按经纬度和半径查询附近交通标志，返回距离、含义和建议速度 |
| POST | `/api/signs` | 新增标志 |
| PUT | `/api/signs/{id}` | 编辑标志 |
| DELETE | `/api/signs/{id}` | 删除标志 |

**`/api/signs/nearby` 查询参数：**

| 参数 | 说明 |
|------|------|
| latitude | 当前纬度，范围 `-90..90` |
| longitude | 当前经度，范围 `-180..180` |
| radius_km | 查询半径，默认 `5`，最大 `500` |
| limit | 返回条数，默认 `20`，最大 `100` |
| sign_type | 可选，按标志类型过滤 |

**新增/编辑请求体（JSON）：**
```json
{
  "sign_code": "pl60",
  "meaning": "限制速度60",
  "sign_type": "禁止标志",
  "limit_value": 60.0,
  "road_section": "G5京昆高速 K120",
  "direction": "成都方向",
  "position_desc": "K120+300 路侧标志",
  "latitude": 30.123456,
  "longitude": 103.123456,
  "recommended_speed": 60.0
}
```

**CSV 导入/导出列：**

```csv
sign_code,meaning,sign_type,limit_value,road_section,direction,position_desc,latitude,longitude,recommended_speed
pl60,限制速度60,禁止标志,60,G5京昆高速 K120,成都方向,K120+300 路侧标志,30.123456,103.123456,60
```

导入按 `sign_code` upsert：编码已存在则更新，不存在则新增。建议先调用 `dry_run=true` 预校验行数和新增/更新数量，再执行 `dry_run=false`。

### 统计与报告

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats` | 返回标志类型分布、每日检测趋势、违规总数、待处理预警数、标志字典更新频率；管理员命中预聚合日报时返回 `cache_date` |
| GET | `/api/report` | 导出全量检测数据为 CSV 文件（UTF-8 BOM，Excel 可直接打开） |
| GET | `/api/reports/daily` | 管理员查询最近日报列表 |
| POST | `/api/reports/daily/rebuild?stat_date=YYYY-MM-DD` | 管理员手动生成/重算指定日期日报；不传日期时默认生成昨天 |
| GET | `/api/reports/daily/{stat_date}` | 管理员查看指定日期日报详情 |
| GET | `/api/reports/daily/{stat_date}/export` | 管理员导出指定日期日报 CSV |

日报由 `StatsDaily` 预聚合表承载，APScheduler 会在每天 00:00 自动生成昨天的数据；管理员也可以在“数据分析可视化”页面手动生成并下载单日 CSV。

### 存储运维

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/storage/status` | 管理员查看 `static/` 文件总量、已引用文件和孤儿文件占用 |
| POST | `/api/storage/cleanup?dry_run=true|false` | 管理员试运行或执行孤儿静态文件清理；实际清理会写入审计日志 |

## 图片命名规则

所有检测产物按时间戳命名，存放于 `static/` 目录：

```
static/orig_YYYYMMDD_HHMMSS_ffffff.jpg   # 原始上传图片
static/res_YYYYMMDD_HHMMSS_ffffff.jpg    # 带检测框的结果图片
static/video_YYYYMMDD_HHMMSS_ffffff.mp4  # 原始上传视频
static/video_frame_YYYYMMDD_HHMMSS_ffffff_N.jpg # 视频抽帧原图
static/video_res_YYYYMMDD_HHMMSS_ffffff_N.jpg   # 视频抽帧结果图
```

## 违规判断逻辑

| 违规类型 | 触发条件 |
|----------|----------|
| 超速 | `sign_code` 以 `pl` 开头，且 `current_speed > limit_value` |
| 违规掉头 | `sign_type` 为禁止标志，且标志含义含"掉头"，且 `current_action == "掉头"` |
| 违规鸣笛 | `sign_type` 为禁止标志，且标志含义含"鸣喇叭"，且 `current_action == "鸣笛"` |
| 违规停车 | `sign_type` 为禁止标志，且标志含义含"停车"，且 `current_action == "停车"` |

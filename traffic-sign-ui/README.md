# 交通标志智能管理系统

基于 YOLO + FastAPI + Vue3 的交通标志实时识别与违规预警平台。

## 功能概览

| 模块 | 功能 |
|------|------|
| 实时监控工作台 | 上传路面抓拍图片，AI 自动识别标志并判断是否违规，返回标注结果图 |
| 识别与违规记录 | 分页查询全量检测记录和违规记录，支持时间/标志名称过滤，可导出 CSV |
| 标志字典管理 | 增删改查系统支持的 42 种交通标志（编码、含义、类型、限制数值） |
| 数据分析可视化 | ECharts 展示高频标志 TOP10、违规占比、近30天检测/违规趋势 |

## 技术栈

- **后端**：Python 3.10+、FastAPI、SQLAlchemy、YOLO (ultralytics)、MySQL
- **前端**：Vue 3、Vite、Element Plus、ECharts、Axios、Vue Router

## 项目结构

```
soft_ks/
├── main.py              # FastAPI 后端主程序（所有接口）
├── init_db.py           # 数据库初始化脚本（建表 + 插入42种标志数据）
├── requirements.txt     # Python 依赖
├── best.pt              # YOLO 训练好的模型权重
├── static/              # 运行时自动生成，存放原图和识别结果图
└── traffic-sign-ui/     # Vue3 前端项目
    ├── src/
    │   ├── layout/index.vue      # 侧边栏 + 顶栏布局
    │   ├── views/
    │   │   ├── Dashboard.vue     # 实时监控工作台
    │   │   ├── Records.vue       # 历史记录查询
    │   │   ├── Signs.vue         # 标志字典管理
    │   │   └── Analysis.vue      # 数据分析可视化
    │   └── router/index.js
    └── package.json
```

## 快速启动

### 1. 准备数据库

在 MySQL 中创建数据库：

```sql
CREATE DATABASE traffic_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

修改 `main.py` 第 20 行的数据库连接字符串（用户名/密码/IP）：

```python
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:你的密码@localhost:3306/traffic_system"
```

### 2. 启动后端

```bash
# 激活 conda 环境
conda activate <你的环境名>

# 安装依赖
pip install -r requirements.txt

# 初始化数据库（只需运行一次）
python init_db.py

# 启动后端服务
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

后端启动后访问 `http://localhost:8000/docs` 可查看所有接口文档。

### 3. 修改前端 IP 配置

如果前后端不在同一台机器，需要将以下文件中的 IP 改为后端服务器的局域网 IP：

- `traffic-sign-ui/src/views/Dashboard.vue` 第 168 行
- `traffic-sign-ui/src/views/Records.vue`（baseURL 变量）
- `traffic-sign-ui/src/views/Signs.vue` 第 123 行
- `traffic-sign-ui/src/views/Analysis.vue` 第 43 行
- `main.py` 中所有 `base_url = "http://192.168.18.70:8000/"` 处

### 4. 启动前端

```bash
cd traffic-sign-ui
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`

## 接口说明

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/detect` | 上传图片 + 车速 + 动作，返回识别结果和违规判定 |
| GET  | `/api/records` | 分页查询检测记录，支持 sign_type/start_time/end_time 过滤 |
| GET  | `/api/records/{id}` | 查询单条记录详情（含违规信息） |
| GET  | `/api/violations` | 分页查询违规记录 |
| GET  | `/api/signs` | 获取全部标志字典 |
| POST | `/api/signs` | 新增标志 |
| PUT  | `/api/signs/{id}` | 修改标志 |
| DELETE | `/api/signs/{id}` | 删除标志 |
| GET  | `/api/stats` | 获取统计数据（用于可视化页面） |
| GET  | `/api/report` | 导出全量检测记录为 CSV |

## 支持的交通标志（42种）

模型可识别的标志类别见 `说明.txt`，涵盖指示标志、禁止标志、警告标志三大类，包括各类限速（pl5~pl120）、限高（ph4/ph4.5）、禁止掉头（p5）、禁止鸣笛（p11）等。

## 违规判定逻辑

- **超速**：识别到限速标志（pl 系列），当前车速 > 限制值 → 触发超速警报
- **禁止掉头**：识别到 p5，当前动作为"掉头" → 触发违规
- **禁止鸣笛**：识别到 p11，当前动作为"鸣笛" → 触发违规

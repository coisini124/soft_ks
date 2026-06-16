# 交通标志识别系统

- 顶部题注：软件综合课程设计答辩
- 组员：罗祥瑞、文焕、闫硕、吉昌兆
- 指导老师：李威、殷成凤
- 时间：2026.6.17
- 答辩逻辑：先讲产品与系统设计，最后打开前端演示。

## Slide 1: 交通标志识别系统
- Subtitle: 软件综合课程设计答辩
- Key labels:
  - 组员：罗祥瑞、文焕、闫硕、吉昌兆
  - 指导老师：李威、殷成凤
  - 时间：2026.6.17
- Visual: cover slide, small course caption on top, dominant main title, road perspective, traffic signs, subtle AI detection box and dashboard preview

## Slide 2: 答辩内容安排
- Subtitle: 先讲系统方案，再进行前端演示
- Key labels:
  - 项目背景
  - 需求目标
  - 系统设计
  - 实现与测试
  - 前端演示
- Visual: agenda roadmap, five-section horizontal journey from background to final demo, with traffic-sign and system icons

## Slide 3: 项目背景与问题
- Subtitle: 高速道路标志信息需要被及时识别、记录和利用
- Key labels:
  - 道路标志类型多
  - 人工巡检效率低
  - 驾驶员容易漏看
  - 数据难以沉淀
- Visual: realistic road scene with multiple traffic signs, inspector tablet, alert card, problem callouts

## Slide 4: 课设目标与功能需求
- Subtitle: 围绕识别、解析、查询、分析和提醒形成闭环
- Key labels:
  - 检测与识别
  - 信息解析
  - 查询展示
  - 统计报告
  - 违规提醒
- Visual: requirements matrix with five functional modules connected as a closed loop

## Slide 5: 系统总体方案
- Subtitle: 从图像输入到业务结果输出的完整链路
- Key labels:
  - 输入采集
  - 模型识别
  - 业务解析
  - 数据入库
  - 前端展示
- Visual: end-to-end solution pipeline, camera/image/video input, AI model, database, web app dashboard

## Slide 6: 核心业务流程
- Subtitle: 识别流程与违规检测流程协同工作
- Key labels:
  - 采集图像
  - 识别标志
  - 解析含义
  - 判定违规
  - 记录分析
- Visual: two-lane workflow diagram: recognition flow and violation flow, merged into record and analysis

## Slide 7: 技术架构设计
- Subtitle: Vue 前端、FastAPI 后端、SQLite 数据层与模型模块
- Key labels:
  - Vue3 + Element Plus
  - FastAPI
  - SQLite
  - YOLOv8 / mock
- Visual: layered software architecture diagram with frontend, API, data, model, storage and authentication

## Slide 8: 识别模块设计
- Subtitle: 真实模型与演示模式兼容，保证答辩可稳定演示
- Key labels:
  - 图片检测
  - 视频抽帧
  - 摄像头抓拍
  - best.pt 可切换
- Visual: AI recognition module design: image/video/camera inputs into detection model, bounding boxes and confidence output

## Slide 9: 数据结构与信息解析
- Subtitle: 把识别结果转换成可查询、可统计的业务数据
- Key labels:
  - 标志字典
  - 检测记录
  - 违规记录
  - 审计日志
- Visual: database schema infographic, entities connected with arrows, traffic sign dictionary and detection record cards

## Slide 10: 违规判定与提醒逻辑
- Subtitle: 根据标志含义、车速和驾驶动作生成风险提醒
- Key labels:
  - 超速判定
  - 违停判定
  - 风险等级
  - 处理状态
- Visual: rule engine style diagram, speed limit sign plus vehicle speed, orange warning notification, violation ledger

## Slide 11: 前端功能模块
- Subtitle: 面向管理员和驾驶员提供完整操作界面
- Key labels:
  - 检测工作台
  - 历史记录
  - 标志查询
  - 字典管理
  - 统计分析
- Visual: high-fidelity web product module overview, five UI panels, sidebar navigation, clean dashboard style

## Slide 12: 后端接口与文件存储
- Subtitle: 统一支撑检测上传、记录查询、统计导出和权限控制
- Key labels:
  - 登录鉴权
  - 检测接口
  - 查询接口
  - 导出接口
  - 文件清理
- Visual: backend API map, endpoints connected to database and uploaded/result image storage folders

## Slide 13: 测试验证与完成情况
- Subtitle: 通过功能链路、构建和安全检查验证可演示性
- Key labels:
  - 后端 smoke 通过
  - 前端 build 通过
  - npm audit 通过
  - 核心链路可演示
- Visual: verification dashboard with check marks, test pipeline, build artifact and product readiness checklist

## Slide 14: 前端演示路线
- Subtitle: 讲完系统设计后，再打开最终前端进行操作展示
- Key labels:
  - 登录系统
  - 图片检测
  - 视频/摄像头
  - 历史与查询
  - 统计与字典
- Visual: demo route map with numbered screens, browser window mockups and arrows, restrained presentation style

## Slide 15: 总结与答辩收束
- Subtitle: 系统覆盖课设要求，形成从识别到管理的闭环
- Key labels:
  - 功能完整
  - 链路清晰
  - 数据可追溯
  - 演示稳定
- Visual: closing summary with completion checklist, traffic sign recognition product collage, light academic defense style

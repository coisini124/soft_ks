from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "defense_materials"
DECK_NAME = "traffic_sign_product_defense_imagegen"
DECK_DIR = BASE / DECK_NAME
ORIGIN = DECK_DIR / "origin_image"
PROMPTS = DECK_DIR / "prompts"
RAW = DECK_DIR / "generated_raw"

STYLE = (
    "16:9 full-slide PowerPoint image, formal but not over-designed Chinese university software course-design defense, "
    "light background, refined blue and teal palette, small orange only for warning/risk, realistic product and technical presentation style, "
    "traffic sign recognition system theme, high-quality visual hierarchy, moderate information density, no cyberpunk, no dark stage, "
    "no neon, no excessive decoration, no childish cartoon, no watermark, no fake brand."
)

CONSTRAINTS = (
    "Render Chinese text exactly as provided where possible. Use large readable Chinese sans-serif typography. "
    "Do not add plus signs near titles, random symbols, fake logos, QR codes, page numbers, watermarks, or English filler. "
    "Keep the slide clean and suitable for a classroom defense projector."
)

SLIDES = [
    {
        "id": "slide_01",
        "title": "交通标志识别系统",
        "subtitle": "软件综合课程设计答辩",
        "labels": ["组员：罗祥瑞、文焕、闫硕、吉昌兆", "指导老师：李威、殷成凤", "时间：2026.6.17"],
        "visual": "cover slide, small course caption on top, dominant main title, road perspective, traffic signs, subtle AI detection box and dashboard preview",
    },
    {
        "id": "slide_02",
        "title": "答辩内容安排",
        "subtitle": "先讲系统方案，再进行前端演示",
        "labels": ["项目背景", "需求目标", "系统设计", "实现与测试", "前端演示"],
        "visual": "agenda roadmap, five-section horizontal journey from background to final demo, with traffic-sign and system icons",
    },
    {
        "id": "slide_03",
        "title": "项目背景与问题",
        "subtitle": "高速道路标志信息需要被及时识别、记录和利用",
        "labels": ["道路标志类型多", "人工巡检效率低", "驾驶员容易漏看", "数据难以沉淀"],
        "visual": "realistic road scene with multiple traffic signs, inspector tablet, alert card, problem callouts",
    },
    {
        "id": "slide_04",
        "title": "课设目标与功能需求",
        "subtitle": "围绕识别、解析、查询、分析和提醒形成闭环",
        "labels": ["检测与识别", "信息解析", "查询展示", "统计报告", "违规提醒"],
        "visual": "requirements matrix with five functional modules connected as a closed loop",
    },
    {
        "id": "slide_05",
        "title": "系统总体方案",
        "subtitle": "从图像输入到业务结果输出的完整链路",
        "labels": ["输入采集", "模型识别", "业务解析", "数据入库", "前端展示"],
        "visual": "end-to-end solution pipeline, camera/image/video input, AI model, database, web app dashboard",
    },
    {
        "id": "slide_06",
        "title": "核心业务流程",
        "subtitle": "识别流程与违规检测流程协同工作",
        "labels": ["采集图像", "识别标志", "解析含义", "判定违规", "记录分析"],
        "visual": "two-lane workflow diagram: recognition flow and violation flow, merged into record and analysis",
    },
    {
        "id": "slide_07",
        "title": "技术架构设计",
        "subtitle": "Vue 前端、FastAPI 后端、SQLite 数据层与模型模块",
        "labels": ["Vue3 + Element Plus", "FastAPI", "SQLite", "YOLOv8 / mock"],
        "visual": "layered software architecture diagram with frontend, API, data, model, storage and authentication",
    },
    {
        "id": "slide_08",
        "title": "识别模块设计",
        "subtitle": "真实模型与演示模式兼容，保证答辩可稳定演示",
        "labels": ["图片检测", "视频抽帧", "摄像头抓拍", "best.pt 可切换"],
        "visual": "AI recognition module design: image/video/camera inputs into detection model, bounding boxes and confidence output",
    },
    {
        "id": "slide_09",
        "title": "数据结构与信息解析",
        "subtitle": "把识别结果转换成可查询、可统计的业务数据",
        "labels": ["标志字典", "检测记录", "违规记录", "审计日志"],
        "visual": "database schema infographic, entities connected with arrows, traffic sign dictionary and detection record cards",
    },
    {
        "id": "slide_10",
        "title": "违规判定与提醒逻辑",
        "subtitle": "根据标志含义、车速和驾驶动作生成风险提醒",
        "labels": ["超速判定", "违停判定", "风险等级", "处理状态"],
        "visual": "rule engine style diagram, speed limit sign plus vehicle speed, orange warning notification, violation ledger",
    },
    {
        "id": "slide_11",
        "title": "前端功能模块",
        "subtitle": "面向管理员和驾驶员提供完整操作界面",
        "labels": ["检测工作台", "历史记录", "标志查询", "字典管理", "统计分析"],
        "visual": "high-fidelity web product module overview, five UI panels, sidebar navigation, clean dashboard style",
    },
    {
        "id": "slide_12",
        "title": "后端接口与文件存储",
        "subtitle": "统一支撑检测上传、记录查询、统计导出和权限控制",
        "labels": ["登录鉴权", "检测接口", "查询接口", "导出接口", "文件清理"],
        "visual": "backend API map, endpoints connected to database and uploaded/result image storage folders",
    },
    {
        "id": "slide_13",
        "title": "测试验证与完成情况",
        "subtitle": "通过功能链路、构建和安全检查验证可演示性",
        "labels": ["后端 smoke 通过", "前端 build 通过", "npm audit 通过", "核心链路可演示"],
        "visual": "verification dashboard with check marks, test pipeline, build artifact and product readiness checklist",
    },
    {
        "id": "slide_14",
        "title": "前端演示路线",
        "subtitle": "讲完系统设计后，再打开最终前端进行操作展示",
        "labels": ["登录系统", "图片检测", "视频/摄像头", "历史与查询", "统计与字典"],
        "visual": "demo route map with numbered screens, browser window mockups and arrows, restrained presentation style",
    },
    {
        "id": "slide_15",
        "title": "总结与答辩收束",
        "subtitle": "系统覆盖课设要求，形成从识别到管理的闭环",
        "labels": ["功能完整", "链路清晰", "数据可追溯", "演示稳定"],
        "visual": "closing summary with completion checklist, traffic sign recognition product collage, light academic defense style",
    },
]


def prompt_for(slide: dict) -> str:
    labels = "\n".join(f"- \"{x}\"" for x in slide["labels"])
    return f"""Use case: productivity-visual
Asset type: 16:9 full-slide PowerPoint slide image
Primary request: Generate one complete PPT slide for a Chinese software course-design defense. The topic is a traffic sign recognition system. The slide should focus on product/system explanation, not only frontend operation.
Style/medium: {STYLE}
Slide title text (verbatim, plain text only): "{slide['title']}"
Subtitle text (verbatim): "{slide['subtitle']}"
Key text labels (verbatim, render as readable short bullets/cards):
{labels}
Visual composition: {slide['visual']}.
Layout: formal defense slide, strong title hierarchy, polished body visual, moderate information density, suitable for projector.
Constraints: {CONSTRAINTS}
Output: one finished 16:9 slide image generated by the image model, not a template and not a local diagram."""


def main() -> None:
    ORIGIN.mkdir(parents=True, exist_ok=True)
    PROMPTS.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)

    spec = {
        "title": "交通标志识别系统",
        "caption": "软件综合课程设计答辩",
        "members": "罗祥瑞、文焕、闫硕、吉昌兆",
        "teachers": "李威、殷成凤",
        "date": "2026.6.17",
        "slide_count": 15,
        "selected_backend": "built-in image_gen tool",
        "style": STYLE,
        "slides": SLIDES,
        "sample_generation_method": {
            "backend_used": "built-in image_gen tool",
            "tool_name": "image_gen",
            "mode": "generate",
            "prompt_source": "prompts/slide_XX.json",
            "size": "16:9 landscape",
            "handoff_rule": "All final slides must be generated by the built-in image_gen tool.",
        },
    }
    (DECK_DIR / "deck_spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

    outline = [
        "# 交通标志识别系统",
        "",
        "- 顶部题注：软件综合课程设计答辩",
        "- 组员：罗祥瑞、文焕、闫硕、吉昌兆",
        "- 指导老师：李威、殷成凤",
        "- 时间：2026.6.17",
        "- 答辩逻辑：先讲产品与系统设计，最后打开前端演示。",
        "",
    ]
    notes = []
    jobs = {
        "deck": str(DECK_DIR),
        "selected_backend": "built-in image_gen tool",
        "sample_generation_method": spec["sample_generation_method"],
        "run_status": "jobs_prepared",
        "slides": [],
    }
    for i, slide in enumerate(SLIDES, 1):
        payload = {
            "slide_id": slide["id"],
            "slide_number": i,
            "title": slide["title"],
            "out": f"origin_image/{slide['id']}.png",
            "expected_backend": "built-in image_gen tool",
            "sample_generation_method": spec["sample_generation_method"],
            "prompt": prompt_for(slide),
            "input_images": [],
        }
        (PROMPTS / f"{slide['id']}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        jobs["slides"].append(
            {
                "slide_id": slide["id"],
                "title": slide["title"],
                "job": f"prompts/{slide['id']}.json",
                "out": f"origin_image/{slide['id']}.png",
                "status": "pending",
            }
        )
        outline.extend(
            [
                f"## Slide {i}: {slide['title']}",
                f"- Subtitle: {slide['subtitle']}",
                "- Key labels:",
                *[f"  - {x}" for x in slide["labels"]],
                f"- Visual: {slide['visual']}",
                "",
            ]
        )
        notes.append(f"## Slide {i}: {slide['title']}\n")
        notes.append(f"本页讲解重点：{slide['subtitle']}。围绕页面中的关键标签展开说明。\n")

    (DECK_DIR / "outline.md").write_text("\n".join(outline), encoding="utf-8")
    (DECK_DIR / "speech.md").write_text("\n".join(notes), encoding="utf-8")
    (DECK_DIR / "slide_jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    (DECK_DIR / "slide_run_state.json").write_text(json.dumps({"status": "jobs_prepared"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(DECK_DIR)


if __name__ == "__main__":
    main()

import argparse
import json
from datetime import datetime
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate a YOLO traffic-sign model and write an acceptance metrics report."
    )
    parser.add_argument("--model", default="best.pt", help="Path to trained YOLO model, default: best.pt")
    parser.add_argument("--data", required=True, help="Path to YOLO data.yaml containing validation/test split")
    parser.add_argument("--imgsz", type=int, default=640, help="Evaluation image size")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.7, help="IoU threshold")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"], help="Dataset split to evaluate")
    parser.add_argument("--output", default="reports/model_eval.json", help="JSON report path")
    return parser.parse_args()


def fail(message: str, code: int = 2):
    print(f"[FAIL] {message}")
    raise SystemExit(code)


def metric_value(metrics, name, default=None):
    value = getattr(metrics, name, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main():
    args = parse_args()
    model_path = Path(args.model)
    data_path = Path(args.data)
    output_path = Path(args.output)

    if not model_path.exists():
        fail(f"model file not found: {model_path}")
    if not data_path.exists():
        fail(f"dataset config not found: {data_path}")

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        fail(f"ultralytics is not installed: {exc}")

    model = YOLO(str(model_path))
    results = model.val(
        data=str(data_path),
        imgsz=args.imgsz,
        conf=args.conf,
        iou=args.iou,
        split=args.split,
        verbose=False,
    )

    box = getattr(results, "box", None)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": str(model_path),
        "data": str(data_path),
        "split": args.split,
        "imgsz": args.imgsz,
        "conf": args.conf,
        "iou": args.iou,
        "metrics": {
            "precision": metric_value(box, "mp"),
            "recall": metric_value(box, "mr"),
            "map50": metric_value(box, "map50"),
            "map50_95": metric_value(box, "map"),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[OK] model evaluation completed")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    print(f"[OK] report written to {output_path}")


if __name__ == "__main__":
    main()

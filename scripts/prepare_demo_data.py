from io import BytesIO
from pathlib import Path
from datetime import datetime
import os
import sys
import tempfile

import cv2
from fastapi.testclient import TestClient
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DETECTOR_MODE", "mock")

import init_db  # noqa: F401 - ensure database and seed dictionary exist
import main


def assert_ok(response, label):
    if response.status_code >= 400:
        raise RuntimeError(f"{label} failed: {response.status_code} {response.text}")
    return response


def make_sample_png():
    buffer = BytesIO()
    Image.new("RGB", (640, 360), color=(245, 247, 250)).save(buffer, format="PNG")
    return buffer.getvalue()


def make_sample_video():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        video_path = Path(tmp.name)
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        5,
        (320, 180),
    )
    for idx in range(6):
        frame = np.full((180, 320, 3), 245 - idx * 5, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return video_path


def detect_image(client, headers, image_bytes, speed, action, label):
    response = client.post(
        "/api/detect",
        headers=headers,
        data={
            "current_speed": str(speed),
            "current_action": action,
            "min_confidence": "0.25",
        },
        files={"file": (f"{label}.png", image_bytes, "image/png")},
    )
    return assert_ok(response, label).json()


def detect_video(client, headers, video_path):
    response = client.post(
        "/api/detect/video",
        headers=headers,
        data={
            "current_speed": "80",
            "current_action": "\u76f4\u884c",
            "min_confidence": "0.25",
            "frame_interval": "2",
            "max_frames": "3",
        },
        files={"file": ("demo.mp4", video_path.read_bytes(), "video/mp4")},
    )
    return assert_ok(response, "demo video detection").json()


def main_entry():
    main.DETECTOR_MODE = "mock"
    client = TestClient(main.app)

    login = assert_ok(
        client.post("/api/login", json={"username": "admin", "password": "admin123"}),
        "admin login",
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}

    signs = assert_ok(client.get("/api/signs", headers=headers), "load signs").json()
    speed_limit = next((item for item in signs if item["sign_code"] == "pl60"), None)
    no_parking = next((item for item in signs if item["sign_code"] == "pn"), None)
    if not speed_limit or not no_parking:
        raise RuntimeError("seed dictionary should include pl60 and pn")

    image_bytes = make_sample_png()

    main.MOCK_SIGN_ID = speed_limit["id"]
    speed_payload = detect_image(
        client,
        headers,
        image_bytes,
        speed=80,
        action="\u76f4\u884c",
        label="demo_speeding",
    )

    main.MOCK_SIGN_ID = no_parking["id"]
    parking_payload = detect_image(
        client,
        headers,
        image_bytes,
        speed=0,
        action="\u505c\u8f66",
        label="demo_parking",
    )

    main.MOCK_SIGN_ID = speed_limit["id"]
    video_path = make_sample_video()
    try:
        video_payload = detect_video(client, headers, video_path)
    finally:
        video_path.unlink(missing_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    daily = assert_ok(
        client.post("/api/reports/daily/rebuild", params={"stat_date": today}, headers=headers),
        "daily report rebuild",
    ).json()
    stats = assert_ok(client.get("/api/stats", headers=headers), "stats").json()

    print("Demo data prepared.")
    print("- Login: admin / admin123")
    print(f"- Image speeding record: {speed_payload.get('id')}")
    print(f"- Image parking record: {parking_payload.get('id')}")
    print(f"- Video record: {video_payload.get('id')}")
    print(f"- Today report: {daily.get('stat_date')} detections={daily.get('total_detections')} violations={daily.get('total_violations')}")
    print(f"- Current stats: detections={stats.get('total_detections')} violations={stats.get('total_violations')} pending={stats.get('pending_violations')}")
    print("- Open the frontend and check Dashboard, Records, Analysis, and Sign Query.")


if __name__ == "__main__":
    main_entry()

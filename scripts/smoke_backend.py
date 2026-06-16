from io import BytesIO
from pathlib import Path
from datetime import datetime
import hashlib
import hmac
import json
import sys
import tempfile

import cv2
from fastapi.testclient import TestClient
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import init_db  # noqa: F401 - ensure local database and seed data exist
import main


def assert_status(response, expected, label):
    if response.status_code != expected:
        raise AssertionError(f"{label}: expected {expected}, got {response.status_code}: {response.text}")


client = TestClient(main.app)

health = client.get("/api/health")
assert_status(health, 200, "health")
if "detection_confidence" not in health.json():
    raise AssertionError("health should expose detection_confidence")

model_status = client.get("/api/model/status")
assert_status(model_status, 200, "model status")
if "confidence" not in model_status.json():
    raise AssertionError("model status should expose confidence threshold")

unauthorized = client.get("/api/violations")
assert_status(unauthorized, 401, "violations require login")

forged = client.get("/api/signs", headers={"Authorization": "Bearer admin:anyone"})
assert_status(forged, 401, "forged legacy token should be rejected")

expired_payload = main._b64url(json.dumps({
    "sub": "admin",
    "role": "admin",
    "iat": 1,
    "exp": 2,
}, separators=(",", ":")).encode())
expired_signature = main._b64url(
    hmac.new(main.TOKEN_SECRET.encode(), expired_payload.encode(), hashlib.sha256).digest()
)
expired = client.get("/api/signs", headers={"Authorization": f"Bearer {expired_payload}.{expired_signature}"})
assert_status(expired, 401, "expired token should be rejected")

login = client.post("/api/login", json={"username": "admin", "password": "admin123"})
assert_status(login, 200, "admin login")
token = login.json()["token"]
if "." not in token:
    raise AssertionError("token should be signed and contain a payload/signature separator")
headers = {"Authorization": f"Bearer {token}"}

me = client.get("/api/me", headers=headers)
assert_status(me, 200, "current admin profile")
if me.json() != {"role": "admin", "username": "admin"}:
    raise AssertionError(f"unexpected admin profile payload: {me.json()}")

signs = client.get("/api/signs", headers=headers)
assert_status(signs, 200, "sign list")
if len(signs.json()) != 42:
    raise AssertionError(f"expected 42 seeded signs, got {len(signs.json())}")

mapping_check = client.get("/api/model/mapping-check", headers=headers)
assert_status(mapping_check, 200, "admin model mapping check")
mapping_payload = mapping_check.json()
if mapping_payload["dictionary"]["total"] != 42:
    raise AssertionError(f"expected 42 mapped signs, got {mapping_payload['dictionary']['total']}")
if mapping_payload["dictionary"]["missing_ids"]:
    raise AssertionError(f"dictionary class ids should be contiguous: {mapping_payload['dictionary']['missing_ids']}")
if mapping_payload["dictionary"]["duplicate_codes"]:
    raise AssertionError(f"sign_code values should be unique: {mapping_payload['dictionary']['duplicate_codes']}")
if mapping_payload["dictionary"]["limit_rule_issues"]:
    raise AssertionError("speed-limit signs should have limit_value values")
if not main.MODEL_PATH.exists() and "模型文件不存在" not in "".join(mapping_payload["warnings"]):
    raise AssertionError("mapping check should explain that real model mapping cannot be compared without best.pt")

search = client.get("/api/signs/search", params={"road_section": "G5京昆高速"}, headers=headers)
assert_status(search, 200, "location sign search")
if search.json()["total"] == 0:
    raise AssertionError("expected seeded signs to be searchable by road_section")

nearby = client.get(
    "/api/signs/nearby",
    params={"latitude": 30.0, "longitude": 103.0, "radius_km": 2, "limit": 5},
    headers=headers,
)
assert_status(nearby, 200, "nearby sign search")
nearby_payload = nearby.json()
if nearby_payload["total"] == 0:
    raise AssertionError("expected seeded signs to be searchable by nearby coordinates")
if "distance_km" not in nearby_payload["data"][0]:
    raise AssertionError("nearby sign search should return distance_km")

bad_nearby = client.get(
    "/api/signs/nearby",
    params={"latitude": 91, "longitude": 103.0},
    headers=headers,
)
assert_status(bad_nearby, 422, "nearby latitude validation")

sign_export = client.get("/api/signs/export", headers=headers)
assert_status(sign_export, 200, "admin sign dictionary export")
if "text/csv" not in sign_export.headers.get("content-type", ""):
    raise AssertionError("sign dictionary export should be csv")
if b"sign_code" not in sign_export.content:
    raise AssertionError("sign dictionary export should include sign_code header")

import_code = f"import_{int(datetime.now().timestamp())}"
import_csv = (
    "sign_code,meaning,sign_type,limit_value,road_section,direction,position_desc,latitude,longitude,recommended_speed\n"
    f"{import_code},导入测试标志,警告标志,,导入路段 K1,导入方向,导入点位,30.123456,103.123456,60\n"
).encode("utf-8-sig")
import_preview = client.post(
    "/api/signs/import",
    params={"dry_run": "true"},
    headers=headers,
    files={"file": ("signs.csv", import_csv, "text/csv")},
)
assert_status(import_preview, 200, "admin sign dictionary import dry-run")
if not import_preview.json()["dry_run"] or import_preview.json()["created"] != 1:
    raise AssertionError(f"sign import dry-run should preview one creation: {import_preview.json()}")
if client.get("/api/signs/search", params={"keyword": import_code}, headers=headers).json()["total"] != 0:
    raise AssertionError("sign import dry-run should not persist rows")

import_apply = client.post(
    "/api/signs/import",
    params={"dry_run": "false"},
    headers=headers,
    files={"file": ("signs.csv", import_csv, "text/csv")},
)
assert_status(import_apply, 200, "admin sign dictionary import apply")
if import_apply.json()["created"] != 1:
    raise AssertionError("sign import apply should create one row")
imported_search = client.get("/api/signs/search", params={"keyword": import_code}, headers=headers)
assert_status(imported_search, 200, "imported sign search")
if imported_search.json()["total"] != 1:
    raise AssertionError("imported sign should be searchable")
imported_sign_id = imported_search.json()["data"][0]["id"]

update_csv = (
    "sign_code,meaning,sign_type,limit_value,road_section,direction,position_desc,latitude,longitude,recommended_speed\n"
    f"{import_code},导入测试标志-更新,警告标志,,导入路段 K2,导入方向,导入点位,30.123456,103.123456,70\n"
).encode("utf-8-sig")
import_update = client.post(
    "/api/signs/import",
    params={"dry_run": "false"},
    headers=headers,
    files={"file": ("signs.csv", update_csv, "text/csv")},
)
assert_status(import_update, 200, "admin sign dictionary import update")
if import_update.json()["updated"] != 1:
    raise AssertionError("sign import update should update one row")
updated_imported = client.get("/api/signs/search", params={"keyword": "导入测试标志-更新"}, headers=headers)
assert_status(updated_imported, 200, "updated imported sign search")
if updated_imported.json()["total"] != 1:
    raise AssertionError("updated imported sign should be searchable by new meaning")
delete_imported_sign = client.delete(f"/api/signs/{imported_sign_id}", headers=headers)
assert_status(delete_imported_sign, 200, "delete imported sign")

temp_code = f"tmp_{int(datetime.now().timestamp())}"
created_sign = client.post(
    "/api/signs",
    headers=headers,
    json={
        "sign_code": temp_code,
        "meaning": "临时测试标志",
        "sign_type": "警告标志",
        "road_section": "测试路段 K1",
        "direction": "测试方向",
        "position_desc": "测试路段 K1 测试方向 路侧标志",
        "recommended_speed": 60,
    },
)
assert_status(created_sign, 200, "create temp sign")
temp_sign_id = created_sign.json()["id"]
if not created_sign.json().get("updated_at"):
    raise AssertionError("created sign should expose updated_at")

updated_sign = client.put(
    f"/api/signs/{temp_sign_id}",
    headers=headers,
    json={"meaning": "临时测试标志-已更新"},
)
assert_status(updated_sign, 200, "update temp sign")

stats_after_sign_update = client.get("/api/stats", headers=headers)
assert_status(stats_after_sign_update, 200, "stats after sign update")
if "sign_update_trend" not in stats_after_sign_update.json():
    raise AssertionError("stats should expose sign_update_trend")
if not stats_after_sign_update.json()["sign_update_trend"]:
    raise AssertionError("sign_update_trend should include at least one update day")

delete_temp_sign = client.delete(f"/api/signs/{temp_sign_id}", headers=headers)
assert_status(delete_temp_sign, 200, "delete temp sign")

sign_audit_logs = client.get(
    "/api/audit-logs",
    params={"resource_type": "sign", "size": 100},
    headers=headers,
)
assert_status(sign_audit_logs, 200, "admin can list audit logs")
sign_audit_actions = {
    item["action"]
    for item in sign_audit_logs.json()["data"]
    if item["resource_id"] == str(temp_sign_id)
}
if not {"create", "update", "delete"}.issubset(sign_audit_actions):
    raise AssertionError(f"sign create/update/delete should be audited, got {sign_audit_actions}")

bad_range = client.get(
    "/api/records",
    params={"start_time": "2026-06-16 12:00:00", "end_time": "2026-06-15 12:00:00"},
    headers=headers,
)
assert_status(bad_range, 400, "bad time range")

report = client.get("/api/report", headers=headers)
assert_status(report, 200, "admin report export")
content_type = report.headers.get("content-type", "")
if "text/csv" not in content_type:
    raise AssertionError(f"expected csv response, got {content_type}")

negative_speed = client.post(
    "/api/detect",
    headers=headers,
    data={"current_speed": "-1", "current_action": "\u76f4\u884c"},
    files={"file": ("sample.png", b"not-used", "image/png")},
)
assert_status(negative_speed, 422, "negative speed validation")

bad_confidence = client.post(
    "/api/detect",
    headers=headers,
    data={"current_speed": "80", "current_action": "\u76f4\u884c", "min_confidence": "1.5"},
    files={"file": ("sample.png", b"not-used", "image/png")},
)
assert_status(bad_confidence, 422, "confidence threshold validation")

buf = BytesIO()
Image.new("RGB", (16, 16), color="white").save(buf, format="PNG")
detect_without_model = client.post(
    "/api/detect",
    headers=headers,
    data={"current_speed": "80", "current_action": "\u76f4\u884c"},
    files={"file": ("sample.png", buf.getvalue(), "image/png")},
)
assert_status(detect_without_model, 503, "missing model should be reported")

main.DETECTOR_MODE = "mock"
mock_high_threshold = client.post(
    "/api/detect",
    headers=headers,
    data={"current_speed": "80", "current_action": "\u76f4\u884c", "min_confidence": "1"},
    files={"file": ("sample.png", buf.getvalue(), "image/png")},
)
assert_status(mock_high_threshold, 200, "mock image detection respects high confidence threshold")
if mock_high_threshold.json()["detected_signs"]:
    raise AssertionError("mock detection should return no signs when min_confidence is higher than mock confidence")

mock_image = client.post(
    "/api/detect",
    headers=headers,
    data={"current_speed": "80", "current_action": "\u76f4\u884c", "min_confidence": "0.25"},
    files={"file": ("sample.png", buf.getvalue(), "image/png")},
)
assert_status(mock_image, 200, "mock image detection")
mock_payload = mock_image.json()
if mock_payload.get("min_confidence") != 0.25:
    raise AssertionError("mock image detection should echo min_confidence")
if not mock_payload.get("id"):
    raise AssertionError("mock image detection should return the saved record id")
if not mock_payload["detected_signs"] or not mock_payload["details"]:
    raise AssertionError("mock image detection should return detected signs and structured details")
if mock_payload["details"][0].get("min_confidence") != 0.25:
    raise AssertionError("detected sign detail should include min_confidence")
if not mock_payload["is_violation"]:
    raise AssertionError("mock pl60 detection at 80km/h should trigger speeding violation")
if not mock_payload.get("violation_events"):
    raise AssertionError("mock image detection should return structured violation_events")
if mock_payload["violation_events"][0]["type"] != "speeding":
    raise AssertionError(f"expected speeding violation event, got {mock_payload['violation_events']}")
if mock_payload["violation_events"][0]["severity"] != "high":
    raise AssertionError("speeding violation event should be high severity")
if not mock_payload["details"][0].get("violation_events"):
    raise AssertionError("detected sign detail should include structured violation_events")

records_after_image = client.get("/api/records", headers=headers)
assert_status(records_after_image, 200, "records after mock image detection")
latest_image_record = records_after_image.json()["data"][0]
if not latest_image_record.get("has_violation"):
    raise AssertionError("mock image detection record should be linked to a violation")
if not latest_image_record.get("location_text"):
    raise AssertionError("mock image detection record should include location_text")
image_detail = client.get(f"/api/records/{latest_image_record['id']}", headers=headers)
assert_status(image_detail, 200, "image record detail includes location")
if not image_detail.json().get("location_text"):
    raise AssertionError("image record detail should include location_text")
if not image_detail.json().get("violations"):
    raise AssertionError("image record detail should include linked violations")

image_artifacts = [
    main.static_path_from_reference(latest_image_record.get("original_image")),
    main.static_path_from_reference(latest_image_record.get("result_image")),
]
if not all(path and path.exists() for path in image_artifacts):
    raise AssertionError("mock image detection should create static artifacts")
delete_image_record = client.delete(f"/api/records/{latest_image_record['id']}", headers=headers)
assert_status(delete_image_record, 200, "delete image record removes static artifacts")
if delete_image_record.json()["removed_file_count"] < 2:
    raise AssertionError("deleting a detection record should remove its static artifacts")
if any(path.exists() for path in image_artifacts if path):
    raise AssertionError("static artifacts should be deleted with the detection record")

parking_sign = next((item for item in signs.json() if item["sign_code"] == "pn"), None)
if not parking_sign:
    raise AssertionError("seed signs should include pn no-parking sign")
main.MOCK_SIGN_ID = parking_sign["id"]
mock_parking = client.post(
    "/api/detect",
    headers=headers,
    data={"current_speed": "0", "current_action": "\u505c\u8f66", "min_confidence": "0.25"},
    files={"file": ("sample.png", buf.getvalue(), "image/png")},
)
assert_status(mock_parking, 200, "mock no-parking violation")
parking_payload = mock_parking.json()
if not parking_payload.get("violation_events"):
    raise AssertionError("mock no-parking detection should return violation_events")
if parking_payload["violation_events"][0]["type"] != "illegal_parking":
    raise AssertionError(f"expected illegal_parking violation event, got {parking_payload['violation_events']}")
if parking_payload["violation_events"][0]["severity"] != "medium":
    raise AssertionError("illegal_parking violation should be medium severity")
main.MOCK_SIGN_ID = 28

with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
    video_path = Path(tmp.name)
writer = cv2.VideoWriter(
    str(video_path),
    cv2.VideoWriter_fourcc(*"mp4v"),
    5,
    (16, 16),
)
writer.write(np.full((16, 16, 3), 255, dtype=np.uint8))
writer.release()
video_response = client.post(
    "/api/detect/video",
    headers=headers,
    data={"current_speed": "80", "current_action": "\u76f4\u884c", "min_confidence": "0.25", "frame_interval": "1", "max_frames": "1"},
    files={"file": ("sample.mp4", video_path.read_bytes(), "video/mp4")},
)
video_path.unlink(missing_ok=True)
assert_status(video_response, 200, "mock video detection")
if video_response.json()["sampled_frames"] != 1:
    raise AssertionError("mock video detection should process one sampled frame")
if video_response.json().get("min_confidence") != 0.25:
    raise AssertionError("mock video detection should echo min_confidence")
if not video_response.json().get("id"):
    raise AssertionError("mock video detection should return the saved record id")
if not video_response.json().get("violation_events"):
    raise AssertionError("mock video detection should return structured violation_events")
records_after_video = client.get("/api/records", headers=headers)
assert_status(records_after_video, 200, "records after mock video detection")
latest_video_record = records_after_video.json()["data"][0]
if latest_video_record.get("source_type") != "video":
    raise AssertionError("latest record after video detection should be source_type=video")
if not latest_video_record.get("has_violation"):
    raise AssertionError("mock video detection record should be linked to a violation")
if not latest_video_record.get("location_text"):
    raise AssertionError("mock video detection record should include location_text")

storage_status = client.get("/api/storage/status", headers=headers)
assert_status(storage_status, 200, "admin can inspect static storage")
for field in ("total_files", "total_bytes", "referenced_files", "orphaned_files"):
    if field not in storage_status.json():
        raise AssertionError(f"storage status should include {field}")

orphan_path = main.STATIC_DIR / f"orphan_smoke_{int(datetime.now().timestamp())}.txt"
orphan_path.write_text("orphan", encoding="utf-8")
storage_dry_run = client.post("/api/storage/cleanup", params={"dry_run": "true"}, headers=headers)
assert_status(storage_dry_run, 200, "admin can dry-run static storage cleanup")
if storage_dry_run.json()["removed_file_count"] != 0:
    raise AssertionError("dry-run storage cleanup should not remove files")
if not orphan_path.exists():
    raise AssertionError("dry-run storage cleanup should keep orphan file")
storage_cleanup = client.post("/api/storage/cleanup", params={"dry_run": "false"}, headers=headers)
assert_status(storage_cleanup, 200, "admin can cleanup orphan static files")
if not any(item.endswith(orphan_path.name) for item in storage_cleanup.json()["removed_files"]):
    raise AssertionError("storage cleanup response should include the smoke orphan file")
if orphan_path.exists():
    raise AssertionError("storage cleanup should remove orphan file")

violations_after_detection = client.get("/api/violations", headers=headers)
assert_status(violations_after_detection, 200, "violation list after mock detection")
violation_rows = violations_after_detection.json()["data"]
if not violation_rows:
    raise AssertionError("mock detection should leave at least one violation record")
violation_id = violation_rows[0]["id"]
if not violation_rows[0].get("violation_type"):
    raise AssertionError("violation ledger should expose violation_type")
if not violation_rows[0].get("severity"):
    raise AssertionError("violation ledger should expose severity")
if not violation_rows[0].get("violation_label"):
    raise AssertionError("violation ledger should expose violation_label")

speeding_filter = client.get(
    "/api/violations",
    params={"violation_type": "speeding", "severity": "high"},
    headers=headers,
)
assert_status(speeding_filter, 200, "structured violation filters")
if not speeding_filter.json()["data"]:
    raise AssertionError("speeding/high filter should include mock speeding violations")

parking_filter = client.get(
    "/api/violations",
    params={"violation_type": "illegal_parking", "severity": "medium"},
    headers=headers,
)
assert_status(parking_filter, 200, "structured parking violation filters")
if not parking_filter.json()["data"]:
    raise AssertionError("illegal_parking/medium filter should include mock parking violations")

violation_export = client.get(
    "/api/violations/export",
    params={"violation_type": "illegal_parking", "severity": "medium"},
    headers=headers,
)
assert_status(violation_export, 200, "admin violation ledger export")
if "text/csv" not in violation_export.headers.get("content-type", ""):
    raise AssertionError("violation ledger export should be csv")
if "违规停车".encode("utf-8") not in violation_export.content:
    raise AssertionError("violation ledger export should include parking violation label")

bad_violation_filter = client.get(
    "/api/violations",
    params={"violation_type": "unknown"},
    headers=headers,
)
assert_status(bad_violation_filter, 422, "invalid violation_type filter")

stats_before_handle = client.get("/api/stats", headers=headers)
assert_status(stats_before_handle, 200, "stats include pending violations")
if "pending_violations" not in stats_before_handle.json():
    raise AssertionError("stats should expose pending_violations")
pending_before = stats_before_handle.json()["pending_violations"]

handled = client.put(
    f"/api/violations/{violation_id}/status",
    headers=headers,
    json={"status": "handled"},
)
assert_status(handled, 200, "admin handles violation")
if handled.json()["status"] != "handled" or handled.json()["handled_by"] != "admin":
    raise AssertionError("handled violation should include status and handler")

stats_after_handle = client.get("/api/stats", headers=headers)
assert_status(stats_after_handle, 200, "stats after handling violation")
if stats_after_handle.json()["pending_violations"] > pending_before:
    raise AssertionError("handling a violation should not increase pending_violations")

handled_list = client.get("/api/violations", params={"status": "handled"}, headers=headers)
assert_status(handled_list, 200, "handled violation filter")
if not any(item["id"] == violation_id for item in handled_list.json()["data"]):
    raise AssertionError("handled filter should include handled violation")

reopened = client.put(
    f"/api/violations/{violation_id}/status",
    headers=headers,
    json={"status": "pending"},
)
assert_status(reopened, 200, "admin reopens violation")
if reopened.json()["status"] != "pending" or reopened.json()["handled_by"] is not None:
    raise AssertionError("pending violation should clear handler fields")

stats_after_reopen = client.get("/api/stats", headers=headers)
assert_status(stats_after_reopen, 200, "stats after reopening violation")
if stats_after_reopen.json()["pending_violations"] < stats_after_handle.json()["pending_violations"]:
    raise AssertionError("reopening a violation should not reduce pending_violations")

daily_date = datetime.now().strftime("%Y-%m-%d")
daily_rebuild = client.post(
    "/api/reports/daily/rebuild",
    params={"stat_date": daily_date},
    headers=headers,
)
assert_status(daily_rebuild, 200, "admin rebuild daily report")
daily_payload = daily_rebuild.json()
if daily_payload["stat_date"] != daily_date:
    raise AssertionError("rebuilt daily report should use requested date")
if daily_payload["total_detections"] < 1:
    raise AssertionError("daily report should include smoke detection records")

daily_list = client.get("/api/reports/daily", headers=headers)
assert_status(daily_list, 200, "admin daily report list")
if not any(item["stat_date"] == daily_date for item in daily_list.json()):
    raise AssertionError("daily report list should include rebuilt report")

daily_detail = client.get(f"/api/reports/daily/{daily_date}", headers=headers)
assert_status(daily_detail, 200, "admin daily report detail")

daily_export = client.get(f"/api/reports/daily/{daily_date}/export", headers=headers)
assert_status(daily_export, 200, "admin daily report export")
if "text/csv" not in daily_export.headers.get("content-type", ""):
    raise AssertionError("daily report export should be csv")

driver_name = f"driver_{int(datetime.now().timestamp())}"
driver_register = client.post("/api/register", json={"username": driver_name, "password": "driver123"})
if driver_register.status_code not in (200, 400):
    raise AssertionError(f"driver register failed unexpectedly: {driver_register.text}")
driver_login = client.post("/api/login", json={"username": driver_name, "password": "driver123"})
assert_status(driver_login, 200, "driver login")
driver_headers = {"Authorization": f"Bearer {driver_login.json()['token']}"}
driver_me = client.get("/api/me", headers=driver_headers)
assert_status(driver_me, 200, "current driver profile")
if driver_me.json()["role"] != "driver":
    raise AssertionError("driver profile should report driver role")
driver_nearby = client.get(
    "/api/signs/nearby",
    params={"latitude": 30.0, "longitude": 103.0, "radius_km": 2, "limit": 5},
    headers=driver_headers,
)
assert_status(driver_nearby, 200, "driver can query nearby signs")
driver_violation_filter = client.get(
    "/api/violations",
    params={"violation_type": "speeding", "severity": "high"},
    headers=driver_headers,
)
assert_status(driver_violation_filter, 200, "driver can filter own violation ledger")
driver_violation_export = client.get("/api/violations/export", headers=driver_headers)
assert_status(driver_violation_export, 200, "driver can export own violation ledger")
if "text/csv" not in driver_violation_export.headers.get("content-type", ""):
    raise AssertionError("driver violation ledger export should be csv")
driver_reports = client.get("/api/reports/daily", headers=driver_headers)
assert_status(driver_reports, 403, "driver cannot access admin daily reports")
driver_mapping_check = client.get("/api/model/mapping-check", headers=driver_headers)
assert_status(driver_mapping_check, 403, "driver cannot access model mapping check")
driver_audit_logs = client.get("/api/audit-logs", headers=driver_headers)
assert_status(driver_audit_logs, 403, "driver cannot access audit logs")
driver_storage_status = client.get("/api/storage/status", headers=driver_headers)
assert_status(driver_storage_status, 403, "driver cannot access storage status")
driver_storage_cleanup = client.post("/api/storage/cleanup", headers=driver_headers)
assert_status(driver_storage_cleanup, 403, "driver cannot cleanup static storage")
driver_handle = client.put(
    f"/api/violations/{violation_id}/status",
    headers=driver_headers,
    json={"status": "handled"},
)
assert_status(driver_handle, 403, "driver cannot handle violation")

main.DETECTOR_MODE = "auto"

print("[OK] backend smoke checks passed")

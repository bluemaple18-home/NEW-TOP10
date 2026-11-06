#!/usr/bin/env python3
"""記錄每日報牌頻道 publish 結果。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from build_top10_agent_status_rollup import build_rollup
    from top10_agent_status import DEFAULT_MANIFEST_PATH, build_event, event_record_complete, owns_latest_run, read_manifest, rollup_lock, write_agent_event
    from openclaw_gateway_sender import normalize_message_id, receipt_lock, stable_idempotency_key
except ModuleNotFoundError:
    from scripts.build_top10_agent_status_rollup import build_rollup
    from scripts.top10_agent_status import DEFAULT_MANIFEST_PATH, build_event, event_record_complete, owns_latest_run, read_manifest, rollup_lock, write_agent_event
    from scripts.openclaw_gateway_sender import normalize_message_id, receipt_lock, stable_idempotency_key


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="record top10 daily publish event")
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--status", required=True, choices=["ok", "skipped", "failed", "degraded"])
    parser.add_argument("--decision", default=None, choices=["pass", "stop", "not_applicable"])
    parser.add_argument("--reason", default=None)
    parser.add_argument("--started-at", default=None, help="早期 Daily 失敗時可驗證的 wrapper 啟動時間")
    parser.add_argument("--message", default=None, type=Path)
    parser.add_argument("--send-exit-code", default=None, type=int)
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH, type=Path)
    parser.add_argument("--skip-rollup", action="store_true")
    parser.add_argument("--recover-confirmed-send", action="store_true", help="只根據同內容成功收據補齊缺失事件，不送出")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts_dir = resolve_path(args.artifacts_dir)
    manifest_path = resolve_path(args.manifest)
    run_id = args.run_id or f"daily-{args.run_date}"
    receipt_path = artifacts_dir / f"clawd_send_status_{args.run_date}.json"
    with receipt_lock(receipt_path):
        with rollup_lock(artifacts_dir, args.run_date, run_id):
            return _record_event_locked(args, artifacts_dir, manifest_path, run_id, receipt_path)


def _record_event_locked(
    args: argparse.Namespace, artifacts_dir: Path, manifest_path: Path, run_id: str, receipt_path: Path,
) -> int:
    try:
        send_status = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    except (OSError, UnicodeError, ValueError):
        print("TOP10_EVENT_BLOCKED: send receipt unreadable")
        return 2
    if not isinstance(send_status, dict):
        print("TOP10_EVENT_BLOCKED: send receipt invalid")
        return 2
    if args.status != "ok" and confirmed_delivery_exists(artifacts_dir, args.run_date):
        print("TOP10_EVENT_BLOCKED: successful send receipt protects prior delivery event")
        return 2
    if send_status.get("status") in {"DELIVERY_PENDING", "DELIVERY_UNKNOWN"} and args.status != "degraded":
        print("TOP10_EVENT_BLOCKED: delivery outcome unresolved; preserve degraded state")
        return 2
    if (args.status == "ok" or args.recover_confirmed_send) and (not args.message or not confirmed_send_matches(
        artifacts_dir, args.run_date, resolve_path(args.message), run_id=run_id
    )):
        print("TOP10_EVENT_BLOCKED: success requires matching confirmed live receipt")
        return 2
    if args.recover_confirmed_send:
        if event_record_complete(artifacts_dir, args.run_date, run_id, "daily_push"):
            print("TOP10_EVENT_ALREADY_COMPLETE")
            return 0
        args.status = "ok"
        args.decision = "pass"
        args.send_exit_code = 0
    now = datetime.now(timezone.utc).isoformat()
    decision = args.decision or default_decision(args.status)
    artifact_paths: list[str | Path] = [artifacts_dir / "automation_status.json"]
    if args.message:
        artifact_paths.append(resolve_path(args.message))

    event = build_event(
        run_id=run_id,
        run_date=args.run_date,
        agent_id="daily_push",
        status=args.status,
        decision=decision,
        started_at=args.started_at or now,
        finished_at=now,
        input_refs=[safe_ref(path, artifacts_dir) for path in artifact_paths],
        artifact_paths=[safe_ref(path, artifacts_dir) for path in artifact_paths],
        failure_reason=args.reason if args.status in {"failed", "skipped", "degraded"} else None,
        next_action=next_action(args.status, args.reason),
        metrics={"send_exit_code": args.send_exit_code},
        discord_channel="daily_pick_channel",
        message_type="daily_top10",
    )
    write_agent_event(event, artifacts_dir=artifacts_dir, manifest_path=manifest_path, lock_held=True)

    if not args.skip_rollup:
        manifest = read_manifest(manifest_path)
        rollup = build_rollup(artifacts_dir, args.run_date, run_id, manifest)
        write_rollup(artifacts_dir, args.run_date, run_id, rollup)

    print(json.dumps({"status": "ok", "run_id": run_id, "agent_id": "daily_push"}, ensure_ascii=False))
    return 0


def confirmed_send_matches(
    artifacts_dir: Path, run_date: str, message_path: Path, *, run_id: str | None = None,
) -> bool:
    """恢復事件前核對收據、payload 與當前訊息的同一性。"""
    try:
        status = json.loads((artifacts_dir / f"clawd_send_status_{run_date}.json").read_text(encoding="utf-8"))
        payload = json.loads((artifacts_dir / f"clawd_publish_payload_{run_date}.json").read_text(encoding="utf-8"))
        message = message_path.read_text(encoding="utf-8")
        receipt = status.get("receipt")
        delivery = payload.get("delivery", {})
        key = stable_idempotency_key(
            f"daily-publish:{run_date}", channel=str(status.get("channel") or ""),
            target=str(status.get("target") or ""), message=message,
        )
        return (status.get("schema_version") == "clawd-send-status.v2"
            and status.get("status") == "OK" and status.get("message_date") == run_date
            and status.get("run_id") == (run_id or f"daily-{run_date}")
            and status.get("dry_run") is False and status.get("send_attempted") is True
            and status.get("message_path") == str(message_path)
            and status.get("message_sha256") == hashlib.sha256(message.encode("utf-8")).hexdigest()
            and status.get("channel") == delivery.get("channel")
            and status.get("target") == delivery.get("to")
            and payload.get("ranking_date") == run_date
            and status.get("idempotency_key") == key
            and isinstance(receipt, dict) and receipt.get("idempotency_key") == key
            and normalize_message_id(receipt.get("message_id")) is not None)
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError):
        return False


def confirmed_delivery_exists(artifacts_dir: Path, run_date: str) -> bool:
    """成功收據落地後，較慢的失敗分支不得覆寫送達事件。"""
    try:
        status = json.loads((artifacts_dir / f"clawd_send_status_{run_date}.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return False
    return (isinstance(status, dict) and status.get("status") == "OK"
            and status.get("message_date") == run_date
            and status.get("dry_run") is False and status.get("send_attempted") is True
            and isinstance(status.get("receipt"), dict)
            and normalize_message_id(status["receipt"].get("message_id")) is not None)


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def default_decision(status: str) -> str:
    if status == "ok":
        return "pass"
    if status in {"failed", "degraded"}:
        return "stop"
    return "not_applicable"


def next_action(status: str, reason: str | None) -> str | None:
    if status == "ok":
        return "daily pick message sent to report channel"
    if status in {"failed", "degraded"}:
        return "先唯讀核對 Discord 送達與 send status；結果不明時禁止重送"
    if reason:
        return "record skip reason in ops progress channel"
    return None


def safe_ref(path: str | Path, artifacts_dir: Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        return str(value)
    try:
        return str(value.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        pass
    try:
        return str(value.resolve().relative_to(artifacts_dir.resolve()))
    except ValueError:
        return f"local_artifact/{value.name}"


def write_rollup(artifacts_dir: Path, run_date: str, run_id: str, rollup: dict[str, Any]) -> None:
    output = artifacts_dir / "harness_status" / run_date / run_id / "rollup.json"
    latest = artifacts_dir / "harness_status" / run_date / "latest_rollup.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rollup, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(payload, encoding="utf-8")
    if owns_latest_run(artifacts_dir, run_date, run_id):
        latest.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""發送 TOP10 工作進度訊息到 ops Discord 頻道。"""

from __future__ import annotations

import argparse
import os
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from app.automation.status_contract import daily_status_snapshot_path

try:
    from openclaw_gateway_sender import DeliveryOutcomeUnknownError, GatewayPreflightError, adapter_command, gateway_health, gateway_send, normalize_message_id, protected_delivery_receipt, receipt_lock, stable_idempotency_key, write_non_send_status, write_send_status
    from daily_publish_lock import exclusive_publish_access
except ModuleNotFoundError:
    from scripts.openclaw_gateway_sender import DeliveryOutcomeUnknownError, GatewayPreflightError, adapter_command, gateway_health, gateway_send, normalize_message_id, protected_delivery_receipt, receipt_lock, stable_idempotency_key, write_non_send_status, write_send_status
    from scripts.daily_publish_lock import exclusive_publish_access

try:
    from build_top10_agent_status_rollup import build_rollup
    from build_top10_ops_progress_message import resolve_rollup_path, safe_ref
    from top10_agent_status import DEFAULT_MANIFEST_PATH, build_event, event_record_complete, owns_latest_run, read_manifest, rollup_lock, write_agent_event
except ModuleNotFoundError:
    from scripts.build_top10_agent_status_rollup import build_rollup
    from scripts.build_top10_ops_progress_message import resolve_rollup_path, safe_ref
    from scripts.top10_agent_status import DEFAULT_MANIFEST_PATH, build_event, event_record_complete, owns_latest_run, read_manifest, rollup_lock, write_agent_event


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
STATUS_SCHEMA_VERSION = "top10-ops-report-send-status.v2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="send TOP10 ops progress report")
    parser.add_argument("--run-date", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--artifacts-dir", default=ARTIFACTS_DIR, type=Path)
    parser.add_argument("--config", default=Path("config/automation.yaml"), type=Path)
    parser.add_argument("--message", default=None, type=Path)
    parser.add_argument("--presentation", default=None, type=Path, help="可選的 Clawd presentation JSON 檔，用於 Discord 審核按鈕")
    parser.add_argument("--send", action="store_true", help="正式送出；仍需 notify.ops_clawd_enabled=true 且 ops_clawd_dry_run=false")
    parser.add_argument("--allow-stale-send", action="store_true", help="允許補送非今日 ops 訊息")
    parser.add_argument("--output", default=None, type=Path)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST_PATH, type=Path)
    return parser.parse_args()


def main() -> int:
    if os.environ.get("TOP10_BACKFILL") == "1":
        print("BACKFILL_SEND_BLOCKED: 補跑禁止訊號與 ops 送達，保留既有收據")
        return 2
    with exclusive_publish_access(PROJECT_ROOT):
        return _main_locked()


def _main_locked() -> int:
    if os.environ.get("TOP10_BACKFILL") == "1":
        print("BACKFILL_SEND_BLOCKED: 補跑禁止訊號與 ops 送達，保留既有收據")
        return 2
    args = parse_args()
    if args.run_id is not None and args.run_date is None:
        print("TOP10_OPS_SEND_BLOCKED --run-id requires --run-date")
        return 2
    artifacts_dir = resolve_path(args.artifacts_dir)
    run_date = args.run_date or datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
    if args.run_date is None:
        selected = resolve_rollup_path(artifacts_dir, None, args.run_id)
        if selected is not None:
            selected_date = read_json(selected).get("run_date")
            if isinstance(selected_date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", selected_date):
                run_date = selected_date
    invocation = ARTIFACTS_DIR / f"ops_progress_send_status_{run_date}.json.invocation"
    with receipt_lock(invocation):
        if artifacts_dir == ARTIFACTS_DIR:
            recover_historical_ops_receipts(run_date, artifacts_dir=artifacts_dir,
                                             manifest_path=resolve_path(args.manifest))
        if artifacts_dir == ARTIFACTS_DIR and recover_protected_ops_event(
            ARTIFACTS_DIR / f"ops_progress_send_status_{run_date}.json", run_date,
            artifacts_dir=artifacts_dir, manifest_path=resolve_path(args.manifest),
        ):
            return 2
        config_path = resolve_path(args.config)
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        notify = config.get("notify") if isinstance(config.get("notify"), dict) else {}
        rollup_path = resolve_rollup_path(artifacts_dir, args.run_date, args.run_id)
        if rollup_path is None:
            raise SystemExit("missing TOP10 harness rollup; cannot send ops report")
        rollup = read_json(rollup_path)
        if rollup.get("run_date") != run_date or not isinstance(rollup.get("run_id"), str):
            print("TOP10_OPS_SEND_BLOCKED selected rollup date/run identity mismatch")
            return 2
        run_id = rollup["run_id"]
        if (re.fullmatch(r"\d{4}-\d{2}-\d{2}", run_date) is None
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_id) is None):
            print("TOP10_OPS_SEND_BLOCKED invalid rollup identity")
            return 2
        if args.run_id is not None and args.run_id != run_id:
            print("TOP10_OPS_SEND_BLOCKED selected rollup run_id mismatch")
            return 2
        send_allowed = bool(args.send and notify.get("ops_clawd_enabled") is True
                            and notify.get("ops_clawd_dry_run") is False)
        if send_allowed and not selected_rollup_is_canonical(
            rollup_path, artifacts_dir, run_date, run_id, explicit_run=args.run_id is not None,
        ):
            print("TOP10_OPS_SEND_BLOCKED selected rollup path/latest owner mismatch")
            return 2
        message_path = resolve_message(args.message, artifacts_dir, run_date)
        return _run_locked(args, artifacts_dir, config, notify, rollup_path, run_date, run_id, message_path, rollup)


def selected_rollup_is_canonical(
    path: Path, artifacts_dir: Path, run_date: str, run_id: str, *, explicit_run: bool,
) -> bool:
    """正式送出只接受標準 rollup，指定輪也必須是同日 latest owner。"""
    root = artifacts_dir / "harness_status" / run_date
    expected = root / run_id / "rollup.json" if explicit_run else root / "latest_rollup.json"
    if (path.absolute() != expected.absolute()
        or path.resolve() != path.absolute()
        or not path.resolve().is_relative_to(artifacts_dir.resolve())
        or path.is_symlink() or root.is_symlink()):
        return False
    try:
        owner_path = root / "latest_run_id.txt"
        return (not owner_path.is_symlink() and owner_path.resolve() == owner_path.absolute()
                and owner_path.read_text(encoding="utf-8").strip() == run_id)
    except (OSError, UnicodeError):
        return False


def recover_historical_ops_receipts(
    selected_date: str, *, artifacts_dir: Path, manifest_path: Path,
) -> None:
    """先補齊其他日期的受保護收據，再處理本輪。"""
    receipts = sorted(artifacts_dir.glob("ops_progress_send_status_*.json"))
    for path in receipts:
        match = re.fullmatch(r"ops_progress_send_status_(\d{4}-\d{2}-\d{2})\.json", path.name)
        if match and match.group(1) != selected_date and not path.is_symlink():
            try:
                status = read_json(path)
            except (OSError, UnicodeError, ValueError, TypeError):
                continue
            if status.get("status") in {"DELIVERY_PENDING", "DELIVERY_UNKNOWN"} and unresolved_ops_event_complete(
                artifacts_dir, match.group(1), status.get("run_id")
            ):
                continue
            if status.get("status") in {"OK", "DELIVERY_PENDING", "DELIVERY_UNKNOWN"}:
                recover_protected_ops_event(path, match.group(1), artifacts_dir=artifacts_dir,
                                            manifest_path=manifest_path)


def unresolved_ops_event_complete(artifacts_dir: Path, run_date: str, run_id: object) -> bool:
    """重入掃描已完成的 degraded 事件不再追加 JSONL。"""
    if not isinstance(run_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_id) is None:
        return False
    root = artifacts_dir / "harness_status" / run_date / run_id
    try:
        event = read_json(root / "events" / "ops_reporter.json")
        rollup = read_json(root / "rollup.json")
        history = [json.loads(line) for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
    except (OSError, UnicodeError, ValueError, TypeError):
        return False
    agents = rollup.get("agents")
    if not isinstance(agents, list):
        return False
    return (event.get("run_date") == run_date and event.get("run_id") == run_id
            and event.get("status") == "degraded"
            and rollup.get("run_date") == run_date and rollup.get("run_id") == run_id
            and any(row.get("agent_id") == "ops_reporter" and row.get("status") == "degraded"
                    for row in agents if isinstance(row, dict))
            and any(isinstance(row, dict) and row.get("agent_id") == "ops_reporter"
                    and row.get("status") == "degraded" for row in history))


def recover_protected_ops_event(
    path: Path, run_date: str, *, artifacts_dir: Path, manifest_path: Path,
) -> bool:
    """在選取 latest rollup 前，由原收據唯讀補記確認或未決事件。"""
    if not protected_delivery_receipt(path):
        return False
    try:
        prior = read_json(path)
    except (OSError, UnicodeError, ValueError, TypeError):
        return False
    if prior.get("status") == "OK":
        message_path = recorded_artifact(prior.get("message_path"), artifacts_dir)
        presentation_ref = prior.get("presentation_path")
        presentation_path = recorded_artifact(presentation_ref, artifacts_dir) if presentation_ref else None
        if (prior.get("run_date") == run_date and message_path is not None
            and (not presentation_ref or presentation_path is not None)):
            try:
                presentation = read_presentation_payload(presentation_path) if presentation_path else None
                current = {key: prior.get(key) for key in
                           ("run_date", "run_id", "message_path", "channel", "target")}
                if recover_confirmed_ops_event(
                    path, current, message_path.read_text(encoding="utf-8"), presentation,
                    artifacts_dir=artifacts_dir, manifest_path=manifest_path,
                ):
                    print(f"TOP10_OPS_EVENT_RECOVERED confirmed run_id={prior.get('run_id')}")
            except (OSError, UnicodeError, ValueError, TypeError):
                print("TOP10_OPS_SEND_BLOCKED confirmed event recovery failed")
        return True
    if prior.get("status") not in {"DELIVERY_PENDING", "DELIVERY_UNKNOWN"}:
        return False
    if (prior.get("schema_version") != STATUS_SCHEMA_VERSION or prior.get("run_date") != run_date
        or not isinstance(prior.get("run_id"), str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", prior["run_id"]) is None
        or prior.get("send_attempted") is not True or prior.get("dry_run") is not False
        or prior.get("output_path") != safe_ref(path, artifacts_dir)
        or not all(isinstance(prior.get(key), str) and prior[key] for key in
                   ("generated_at", "message_path", "output_path", "rollup_path"))):
        print(f"TOP10_OPS_SEND_BLOCKED unresolved receipt invalid={path}")
        return True
    try:
        with rollup_lock(artifacts_dir, run_date, prior["run_id"]):
            # 不同日期的入口可能同時掃到此收據，完成檢查須在同輪鎖內。
            if unresolved_ops_event_complete(artifacts_dir, run_date, prior["run_id"]):
                print(f"TOP10_OPS_EVENT_ALREADY_COMPLETE unresolved run_id={prior['run_id']}")
                return True
            _write_ops_event_locked(prior, artifacts_dir=artifacts_dir, manifest_path=manifest_path)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f"TOP10_OPS_SEND_BLOCKED unresolved event recovery failed: {type(exc).__name__}")
    else:
        print(f"TOP10_OPS_EVENT_RECOVERED unresolved run_id={prior['run_id']}")
    return True


def recorded_artifact(reference: object, artifacts_dir: Path) -> Path | None:
    """收據引用只可解析到本專案 artifacts 的既有檔案。"""
    if not isinstance(reference, str) or not reference or Path(reference).is_absolute():
        return None
    root = artifacts_dir.resolve()
    for base in (PROJECT_ROOT, artifacts_dir):
        candidate = (base / reference).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return candidate
    return None


def _run_locked(
    args: argparse.Namespace, artifacts_dir: Path, config: dict[str, Any], notify: dict[str, Any],
    rollup_path: Path, run_date: str, run_id: str, message_path: Path, selected_rollup: dict[str, Any],
) -> int:
    canonical_output = ARTIFACTS_DIR / f"ops_progress_send_status_{run_date}.json"
    send_allowed = bool(args.send and notify.get("ops_clawd_enabled") is True and notify.get("ops_clawd_dry_run") is False)
    if send_allowed and (artifacts_dir != ARTIFACTS_DIR or
                         (args.output is not None and resolve_path(args.output) != canonical_output) or
                         canonical_output.is_symlink() or canonical_output.parent.is_symlink()):
        print(f"TOP10_OPS_SEND_BLOCKED live send requires canonical receipt={canonical_output}")
        return 2
    if protected_delivery_receipt(canonical_output):
        prior = read_json(canonical_output)
        if (prior.get("status") in {"DELIVERY_PENDING", "DELIVERY_UNKNOWN"}
            and prior.get("run_date") == run_date and prior.get("run_id") == run_id
            and prior.get("send_attempted") is True and prior.get("dry_run") is False
            and prior.get("message_path") == safe_ref(message_path, artifacts_dir)):
            # 程序可能在持久化 claim 後中斷；只補 degraded event，絕不重送。
            write_ops_event(prior, artifacts_dir=artifacts_dir, manifest_path=resolve_path(args.manifest))
        # Ops 頻道同日期僅送一次；不同 run_id 不可用新收據繞過舊輪去重。
        if prior.get("status") == "OK" and prior.get("run_id") != run_id:
            print(f"TOP10_OPS_SEND_BLOCKED same-date delivery belongs to run_id={prior.get('run_id')}")
            return 2
        if message_path.is_file():
            presentation_path = resolve_path(args.presentation) if args.presentation else None
            presentation = read_presentation_payload(presentation_path) if presentation_path else None
            current = {
                "run_date": run_date, "run_id": run_id,
                "message_path": safe_ref(message_path, artifacts_dir),
                "channel": str(notify.get("ops_clawd_channel") or notify.get("clawd_channel") or ""),
                "target": str(notify.get("ops_clawd_to") or ""),
            }
            recover_confirmed_ops_event(
                canonical_output, current, message_path.read_text(encoding="utf-8"), presentation,
                artifacts_dir=artifacts_dir, manifest_path=resolve_path(args.manifest),
            )
        print(f"TOP10_OPS_SEND_BLOCKED protected delivery receipt={canonical_output}")
        return 2
    build_strategy_archetype_evidence_map(run_date=run_date, artifacts_dir=artifacts_dir)
    build_research_decision_brief(run_date=run_date, artifacts_dir=artifacts_dir)
    if args.message is None or not message_path.exists():
        run_checked(
            [
                python_bin(),
                "scripts/build_top10_ops_progress_message.py",
                "--run-date",
                run_date,
                "--run-id",
                run_id,
                "--artifacts-dir",
                str(artifacts_dir),
            ]
        )
    message_path = resolve_message(args.message, artifacts_dir, run_date)
    presentation_path = resolve_path(args.presentation) if args.presentation else None
    presentation: dict[str, Any] | None = None
    output_path = resolve_path(args.output) if args.output else artifacts_dir / f"ops_progress_send_status_{run_date}.json"
    canonical_output = ARTIFACTS_DIR / f"ops_progress_send_status_{run_date}.json"

    send_allowed = bool(args.send and notify.get("ops_clawd_enabled") is True and notify.get("ops_clawd_dry_run") is False)
    dry_run = not send_allowed
    node_bin = str(notify.get("clawd_cli_node") or "/opt/homebrew/opt/node/bin/node")
    cli_entry = str(notify.get("clawd_cli_entry") or "/Users/mattkuo/new clawd/dist/index.js")
    channel = str(notify.get("ops_clawd_channel") or notify.get("clawd_channel") or "")
    target = str(notify.get("ops_clawd_to") or "")
    status = initial_status(
        run_date=run_date,
        run_id=run_id,
        artifacts_dir=artifacts_dir,
        message_path=message_path,
        presentation_path=presentation_path,
        rollup_path=rollup_path,
        output_path=output_path,
        channel=channel,
        target=target,
        dry_run=dry_run,
        send_allowed=send_allowed,
        notify=notify,
        node_bin=node_bin,
        cli_entry=cli_entry,
    )
    if send_allowed and (artifacts_dir != ARTIFACTS_DIR or output_path != canonical_output or output_path.is_symlink() or output_path.parent.is_symlink()):
        print(f"TOP10_OPS_SEND_BLOCKED live send requires canonical receipt={canonical_output}")
        return 2
    annotate_rewrite_degraded_message(message_path, artifacts_dir, status["llm_rewrite_degraded_signal"])
    claimed = False
    try:
        presentation = read_presentation_payload(presentation_path) if presentation_path is not None else None
        if send_allowed and (not selected_rollup_is_canonical(
                rollup_path, artifacts_dir, run_date, run_id, explicit_run=args.run_id is not None)
            or read_json(rollup_path) != selected_rollup):
            print("TOP10_OPS_SEND_BLOCKED rollup changed before send claim")
            return 2
        validate_preflight(
            node_bin=node_bin,
            cli_entry=cli_entry,
            channel=channel,
            target=target,
            message_path=message_path,
            presentation_path=presentation_path,
            run_date=run_date,
            send_allowed=send_allowed,
            allow_stale_send=args.allow_stale_send,
            timezone_name=str(config.get("timezone") or "Asia/Taipei"),
            artifacts_dir=artifacts_dir,
        )
        status["command"] = adapter_command(node_bin)
        if dry_run:
            gateway_health(node_bin=node_bin, cli_entry=cli_entry)
            status["transport_method"] = "health"
        else:
            # 產生訊息可能跨程序讀檔；claim 前重核最新 owner 與所選內容。
            if (not selected_rollup_is_canonical(
                    rollup_path, artifacts_dir, run_date, run_id, explicit_run=args.run_id is not None)
                or read_json(rollup_path) != selected_rollup):
                print("TOP10_OPS_SEND_BLOCKED rollup changed before send claim")
                return 2
            message_text = message_path.read_text(encoding="utf-8")
            status["message_sha256"] = hashlib.sha256(message_text.encode("utf-8")).hexdigest()
            status["idempotency_key"] = stable_idempotency_key(
                f"ops-report:{run_date}:{run_id}", channel=channel, target=target,
                message=message_text, presentation=presentation,
            )
            status["status"] = "DELIVERY_PENDING"
            status["delivery_outcome"] = "UNKNOWN"
            status["retry_allowed"] = False
            status["send_attempted"] = True
            # 收據鎖→日期鎖是既有順序；持日期鎖完成 owner 核對、claim、dispatch。
            with receipt_lock(output_path):
                with rollup_lock(artifacts_dir, run_date, run_id):
                    if protected_delivery_receipt(output_path):
                        print(f"TOP10_OPS_SEND_BLOCKED protected delivery receipt={output_path}")
                        return 2
                    if (not selected_rollup_is_canonical(
                            rollup_path, artifacts_dir, run_date, run_id,
                            explicit_run=args.run_id is not None)
                        or read_json(rollup_path) != selected_rollup):
                        print("TOP10_OPS_SEND_BLOCKED owner changed before send claim")
                        return 2
                    write_send_status(output_path, status)
                    claimed = True
                    receipt = gateway_send(
                        node_bin=node_bin,
                        cli_entry=cli_entry,
                        channel=channel,
                        target=target,
                        message=message_text,
                        presentation=presentation,
                        namespace=f"ops-report:{run_date}:{run_id}",
                    )
            status["transport_method"] = receipt["method"]
            status["receipt"] = receipt
        status["exit_code"] = 0
        status["status"] = "OK" if not dry_run else "DRY_RUN"
        if not dry_run:
            status["delivery_outcome"] = "CONFIRMED"
    except DeliveryOutcomeUnknownError as exc:
        status["status"] = "DELIVERY_UNKNOWN"
        status["delivery_outcome"] = "UNKNOWN"
        status["retry_allowed"] = False
        status["idempotency_key"] = exc.idempotency_key
        status["exit_code"] = 1
        status["errors"].append(redact_output(str(exc)))
    except GatewayPreflightError as exc:
        status["status"] = "FAILED"
        status["delivery_outcome"] = "NOT_SENT"
        status["preflight_failed"] = True
        status["send_attempted"] = False
        status["exit_code"] = 1
        status["errors"].append(redact_output(str(exc)))
    except Exception as exc:
        status["status"] = "DELIVERY_UNKNOWN" if status["status"] == "DELIVERY_PENDING" else "FAILED"
        if not claimed:
            status["preflight_failed"] = True
        status["exit_code"] = 1
        status["errors"].append(redact_output(str(exc)))

    if claimed:
        with receipt_lock(output_path):
            write_send_status(output_path, status)
            write_ops_event(status, artifacts_dir=artifacts_dir, manifest_path=resolve_path(args.manifest))
    else:
        if not write_non_send_status(output_path, status):
            print(f"TOP10_OPS_SEND_BLOCKED protected delivery receipt={output_path}")
            return 2
        with receipt_lock(output_path):
            if read_json(output_path) == status:
                write_ops_event(status, artifacts_dir=artifacts_dir, manifest_path=resolve_path(args.manifest))
    print(f"TOP10_OPS_REPORT_SEND status={status['status']} dry_run={dry_run} output={output_path}")
    return 0 if status["status"] == "OK" or (status["status"] == "DRY_RUN" and not args.send) else 1


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return payload


def resolve_message(path: Path | None, artifacts_dir: Path, run_date: str) -> Path:
    if path is not None:
        return resolve_path(path)
    return artifacts_dir / f"ops_progress_message_{run_date}.md"


def daily_rewrite_degraded_signal(artifacts_dir: Path, run_date: str) -> dict[str, Any]:
    """只取同日正式 Daily snapshot；缺資料不阻斷 ops report。"""
    path = daily_status_snapshot_path(artifacts_dir / "automation_status.json", run_date=run_date, dry_run=False)
    signal: dict[str, Any] = {
        "status": "NONE",
        "reason": "MISSING_SAME_DAY_DAILY_STATUS",
        "consecutive_fallback_days": None,
        "daily_status_ref": safe_ref(path, artifacts_dir),
    }
    try:
        daily = read_json(path)
    except (OSError, UnicodeError, ValueError, TypeError):
        return signal
    if daily.get("run_date") != run_date or daily.get("mode") != "daily":
        signal["reason"] = "DAILY_STATUS_IDENTITY_MISMATCH"
        return signal
    metadata = daily.get("metadata")
    if not isinstance(metadata, dict) or "clawd_llm_rewrite_degraded" not in metadata:
        signal["reason"] = "MISSING_DEGRADED_FIELD"
        return signal
    degraded = metadata["clawd_llm_rewrite_degraded"]
    streak = metadata.get("clawd_llm_rewrite_consecutive_fallback_days")
    if type(degraded) is not bool or type(streak) is not int or streak < 0:
        signal["reason"] = "INVALID_DEGRADED_FIELD_TYPE"
        return signal
    signal["consecutive_fallback_days"] = streak
    if degraded and streak >= 2:
        signal.update(status="DEGRADED", reason="CONSECUTIVE_FALLBACK")
    elif degraded:
        signal["reason"] = "INCONSISTENT_DEGRADED_STREAK"
    else:
        signal["reason"] = "NOT_DEGRADED"
    return signal


def annotate_rewrite_degraded_message(message_path: Path, artifacts_dir: Path, signal: dict[str, Any]) -> None:
    """沿用既有 ops 訊息檔；重入不重複加註，失敗不阻斷報告。"""
    if signal.get("status") != "DEGRADED":
        return
    marker = "### Gemini 文案改寫降級"
    try:
        if message_path.is_symlink() or not message_path.resolve().is_relative_to(artifacts_dir.resolve()):
            signal["message_annotation"] = "SKIPPED_UNSAFE_PATH"
            return
        content = message_path.read_text(encoding="utf-8")
        if marker not in content:
            with message_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"\n\n{marker}\n"
                    f"連續 {signal['consecutive_fallback_days']} 個 Daily 執行日 FALLBACK；"
                    "請檢查 Gemini 文案改寫，Daily 仍照原判定執行。\n"
                )
        signal["message_annotation"] = "PRESENT"
    except (OSError, UnicodeError):
        signal["message_annotation"] = "FAILED"


def initial_status(
    *,
    run_date: str,
    run_id: str,
    artifacts_dir: Path,
    message_path: Path,
    presentation_path: Path | None,
    rollup_path: Path,
    output_path: Path,
    channel: str,
    target: str,
    dry_run: bool,
    send_allowed: bool,
    notify: dict[str, Any],
    node_bin: str,
    cli_entry: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "run_id": run_id,
        "message_path": safe_ref(message_path, artifacts_dir),
        "presentation_path": safe_ref(presentation_path, artifacts_dir) if presentation_path else None,
        "rollup_path": safe_ref(rollup_path, artifacts_dir),
        "output_path": safe_ref(output_path, artifacts_dir),
        "channel": channel,
        "target": target,
        "dry_run": dry_run,
        "send_attempted": False,
        "preflight": {
            "ops_clawd_enabled": bool(notify.get("ops_clawd_enabled")),
            "ops_clawd_dry_run": bool(notify.get("ops_clawd_dry_run", True)),
            "node_bin": node_bin,
            "cli_entry": cli_entry,
        },
        "status": "RUNNING",
        "command": None,
        "transport_method": None,
        "receipt": None,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "errors": [],
        "llm_rewrite_degraded_signal": daily_rewrite_degraded_signal(artifacts_dir, run_date),
    }


def validate_preflight(
    *,
    node_bin: str,
    cli_entry: str,
    channel: str,
    target: str,
    message_path: Path,
    presentation_path: Path | None,
    run_date: str,
    send_allowed: bool,
    allow_stale_send: bool,
    timezone_name: str,
    artifacts_dir: Path | None = None,
) -> None:
    missing = []
    if not Path(node_bin).exists():
        missing.append(f"node_bin={node_bin}")
    if not Path(cli_entry).exists():
        missing.append(f"cli_entry={cli_entry}")
    if not channel:
        missing.append("notify.ops_clawd_channel")
    if not target:
        missing.append("notify.ops_clawd_to")
    if not message_path.exists():
        missing.append(f"message_path={message_path}")
    if presentation_path is not None and not presentation_path.exists():
        missing.append(f"presentation_path={presentation_path}")
    if missing:
        raise RuntimeError("Ops Clawd send preflight failed: " + ", ".join(missing))
    if send_allowed:
        recovery_root = (artifacts_dir or PROJECT_ROOT / "artifacts").resolve()
        if not message_path.resolve().is_relative_to(recovery_root):
            raise RuntimeError("Ops live message must remain inside artifacts for receipt recovery")
        if presentation_path is not None and not presentation_path.resolve().is_relative_to(recovery_root):
            raise RuntimeError("Ops live presentation must remain inside artifacts for receipt recovery")
    if presentation_path is not None:
        read_presentation_payload(presentation_path)
        if channel != "discord":
            raise RuntimeError("Ops presentation requires Discord channel before send claim")
    local_today = datetime.now(ZoneInfo(timezone_name)).date().isoformat()
    if send_allowed and run_date != local_today and not allow_stale_send:
        raise RuntimeError(
            f"stale ops message blocked: run_date={run_date} today={local_today}; "
            "use --allow-stale-send only for explicit manual catch-up"
        )


def recover_confirmed_ops_event(
    path: Path, current: dict[str, Any], message: str, presentation: dict[str, Any] | None,
    *, artifacts_dir: Path, manifest_path: Path,
) -> bool:
    """只依同輪、同內容的已確認收據補齊本地事件；不觸發送出。"""
    try:
        previous = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    expected_key = stable_idempotency_key(
        f"ops-report:{current['run_date']}:{current['run_id']}",
        channel=str(current["channel"]), target=str(current["target"]),
        message=message, presentation=presentation,
    )
    receipt = previous.get("receipt")
    expected = ("run_date", "run_id", "message_path", "channel", "target")
    if (previous.get("schema_version") != STATUS_SCHEMA_VERSION
        or previous.get("status") != "OK" or previous.get("dry_run") is not False
        or previous.get("send_attempted") is not True
        or any(previous.get(key) != current.get(key) for key in expected)
        or previous.get("message_sha256") != hashlib.sha256(message.encode("utf-8")).hexdigest()
        or previous.get("idempotency_key") != expected_key
        or not isinstance(receipt, dict) or receipt.get("idempotency_key") != expected_key
        or normalize_message_id(receipt.get("message_id")) is None):
        return False
    with rollup_lock(artifacts_dir, str(current["run_date"]), str(current["run_id"])):
        if not event_record_complete(artifacts_dir, str(current["run_date"]), str(current["run_id"]), "ops_reporter"):
            _write_ops_event_locked(previous, artifacts_dir=artifacts_dir, manifest_path=manifest_path)
    return True


def write_ops_event(status: dict[str, Any], *, artifacts_dir: Path, manifest_path: Path) -> None:
    with rollup_lock(artifacts_dir, str(status["run_date"]), str(status["run_id"])):
        _write_ops_event_locked(status, artifacts_dir=artifacts_dir, manifest_path=manifest_path)


def _write_ops_event_locked(status: dict[str, Any], *, artifacts_dir: Path, manifest_path: Path) -> None:
    rewrite_signal = status.get("llm_rewrite_degraded_signal")
    rewrite_signal = rewrite_signal if isinstance(rewrite_signal, dict) else {}
    rewrite_degraded = rewrite_signal.get("status") == "DEGRADED"
    event_status = (
        "degraded" if status.get("status") in {"DELIVERY_PENDING", "DELIVERY_UNKNOWN"} or (
            rewrite_degraded and status.get("status") in {"OK", "DRY_RUN"}
        )
        else "ok" if status.get("status") == "OK" and status.get("send_attempted") is True and status.get("dry_run") is False
        else "skipped" if status.get("status") == "DRY_RUN"
        else "failed"
    )
    if event_status == "degraded" and unresolved_ops_event_complete(
        artifacts_dir, str(status["run_date"]), str(status["run_id"])
    ):
        return
    decision = "pass" if event_status == "ok" else "not_applicable" if event_status == "skipped" else "stop"
    if event_status == "ok":
        next_action = None
    elif event_status == "degraded":
        next_action = (
            "遠端唯讀核對送達狀態；結果不明時禁止重送"
            if status.get("status") in {"DELIVERY_PENDING", "DELIVERY_UNKNOWN"}
            else "檢查 Gemini 文案改寫連續 FALLBACK；Daily 成敗判定維持原狀"
        )
    elif event_status == "skipped":
        next_action = "dry-run 未送出；正式送出仍須通過設定與收據閘門"
    else:
        next_action = "check ops Clawd config or CLI before next unattended run"
    event = build_event(
        run_id=str(status["run_id"]),
        run_date=str(status["run_date"]),
        agent_id="ops_reporter",
        status=event_status,
        decision=decision,
        started_at=str(status["generated_at"]),
        finished_at=datetime.now(timezone.utc).isoformat(),
        input_refs=[
            str(status["rollup_path"]),
            *([str(rewrite_signal["daily_status_ref"])] if rewrite_degraded else []),
        ],
        artifact_paths=[str(status["message_path"]), str(status["output_path"])],
        failure_reason=(
            "; ".join([
                *(status.get("errors") or []),
                *([f"Gemini 文案改寫連續 {rewrite_signal['consecutive_fallback_days']} 日 FALLBACK"] if rewrite_degraded else []),
            ]) or None
        ) if event_status != "ok" else None,
        next_action=next_action,
        metrics={
            "dry_run": status.get("dry_run"), "send_attempted": status.get("send_attempted"),
            "exit_code": status.get("exit_code"),
            "llm_rewrite_degraded": rewrite_degraded,
            "llm_rewrite_consecutive_fallback_days": rewrite_signal.get("consecutive_fallback_days"),
        },
        discord_channel="ops_progress_channel",
        message_type="run_status" if event_status == "ok" else "blocker",
    )
    write_agent_event(event, artifacts_dir=artifacts_dir, manifest_path=manifest_path, lock_held=True)
    manifest = read_manifest(manifest_path)
    rollup = build_rollup(artifacts_dir, str(status["run_date"]), str(status["run_id"]), manifest)
    write_rollup(artifacts_dir, str(status["run_date"]), str(status["run_id"]), rollup)


def write_rollup(artifacts_dir: Path, run_date: str, run_id: str, rollup: dict[str, Any]) -> None:
    output = artifacts_dir / "harness_status" / run_date / run_id / "rollup.json"
    latest = artifacts_dir / "harness_status" / run_date / "latest_rollup.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(rollup, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.write_text(payload, encoding="utf-8")
    if owns_latest_run(artifacts_dir, run_date, run_id):
        latest.write_text(payload, encoding="utf-8")


def run_checked(command: list[str]) -> None:
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed exit_code={completed.returncode}: {' '.join(command)}")


def build_research_decision_brief(*, run_date: str, artifacts_dir: Path) -> None:
    run_checked(
        [
            python_bin(),
            "scripts/build_research_decision_brief.py",
            "--run-date",
            run_date,
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )


def build_strategy_archetype_evidence_map(*, run_date: str, artifacts_dir: Path) -> None:
    run_checked(
        [
            python_bin(),
            "scripts/build_strategy_archetype_evidence_map.py",
            "--date",
            run_date,
            "--artifacts-dir",
            str(artifacts_dir),
        ]
    )


def python_bin() -> str:
    candidate = PROJECT_ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else "python3"


def read_presentation_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"presentation JSON root must be object: {path}")
    blocks = payload.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError(f"presentation JSON must contain non-empty blocks: {path}")
    return payload


def redact_output(text: str) -> str:
    if not text:
        return ""
    patterns = [
        (r"(?i)(token|webhook|password|secret|authorization)([\"'\s:=]+)([^\"'\s,}]+)", r"\1\2<redacted>"),
        (r"https://discord(?:app)?\.com/api/webhooks/[^\s\"']+", "https://discord.com/api/webhooks/<redacted>"),
    ]
    redacted = text
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted)
    return redacted


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""隔離補送 ChatGPT / Gemini 外部審查的 packet 與 ledger 工具。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_external_review_packet import build_packet, render_markdown  # noqa: E402
from verify_external_review_packet import validate_packet  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "top10-isolated-external-review-backfill.v1"
PROVIDERS = ("chatgpt", "gemini")
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "isolated_external_review_backfill" / "2026-08-03_2026-08-26"
DEFAULT_CHATGPT_MARKER = "chatgpt.com/g/g-p-6a27bb719e708191bd6eefae64c7c08c/c/6a27bb97-8f80-8324-ab52-3f861a006ee3"
DEFAULT_GEMINI_MARKER = "gemini.google.com/app/ea58b54eef550ded"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and verify isolated external review backfill packets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="建立安全 packet、dry-run manifest 與 36-slot ledger")
    prepare.add_argument("--source-root", required=True, type=Path)
    prepare.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, type=Path)
    prepare.add_argument("--chatgpt-marker", default=os.environ.get("TOP10_CHATGPT_URL_PART", DEFAULT_CHATGPT_MARKER))
    prepare.add_argument("--gemini-marker", default=os.environ.get("TOP10_GEMINI_URL_PART", DEFAULT_GEMINI_MARKER))
    prepare.add_argument("--chatgpt-account-hint", default="account19/bluemaple19@gmail.com")
    prepare.add_argument("--gemini-target-hint", default="canonical_existing_gemini_conversation")

    verify = subparsers.add_parser("verify", help="驗證 packet/ledger 唯一性與隔離邊界")
    verify.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, type=Path)
    verify.add_argument("--require-complete", action="store_true")

    sync = subparsers.add_parser("sync-ledger", help="從隔離 external_review 回覆目錄同步 slot 狀態")
    sync.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, type=Path)

    next_slot = subparsers.add_parser("next-slot", help="輸出下一個可送 slot；遇到失敗或不確定即 BLOCKED")
    next_slot.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, type=Path)

    args = parser.parse_args(argv)
    if args.command == "prepare":
        return prepare_packets(args)
    if args.command == "verify":
        return verify_output(args.output_root, require_complete=args.require_complete)
    if args.command == "sync-ledger":
        return sync_ledger(args.output_root)
    if args.command == "next-slot":
        return print_next_slot(args.output_root)
    raise AssertionError(args.command)


def prepare_packets(args: argparse.Namespace) -> int:
    source_root = args.source_root.resolve()
    output_root = resolve_output_root(args.output_root)
    source_artifacts = source_root / "artifacts"
    features_path = source_root / "data" / "clean" / "features.parquet"
    dates = discover_dates(source_root)
    if len(dates) != 18:
        raise SystemExit(f"expected 18 trading dates, got {len(dates)}: {dates}")
    if not features_path.exists():
        raise SystemExit(f"features parquet missing: {features_path}")

    packet_dir = output_root / "packets"
    manifest_dir = output_root / "manifest"
    external_review_dir = output_root / "external_review"
    packet_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    external_review_dir.mkdir(parents=True, exist_ok=True)

    packets: list[dict[str, Any]] = []
    for date_text in dates:
        packet = build_packet(
            packet_date=date_text,
            ranking_path=source_artifacts / f"ranking_{date_text}.csv",
            daily_report_path=source_artifacts / f"daily_report_{date_text}.json",
            daily_report_md_path=source_artifacts / f"daily_report_{date_text}.md",
            features_path=features_path,
        )
        errors = validate_packet(packet)
        if errors:
            raise SystemExit(f"{date_text} packet failed safety validation: {errors}")
        per_day = packet_dir / date_text
        per_day.mkdir(parents=True, exist_ok=True)
        packet_path = per_day / f"review_packet_{date_text}.json"
        markdown_path = per_day / f"review_packet_{date_text}.md"
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_markdown(packet) + "\n", encoding="utf-8")
        packets.append(
            {
                "date": date_text,
                "packet_path": repo_path(packet_path),
                "markdown_path": repo_path(markdown_path),
                "packet_sha256": sha256(packet_path),
                "packet_bytes": packet_path.stat().st_size,
            }
        )

    ledger = build_ledger(
        output_root=output_root,
        source_root=source_root,
        packets=packets,
        chatgpt_marker=args.chatgpt_marker,
        gemini_marker=args.gemini_marker,
        chatgpt_account_hint=args.chatgpt_account_hint,
        gemini_target_hint=args.gemini_target_hint,
    )
    ledger_path(output_root).write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "top10-isolated-external-review-backfill-manifest.v1",
        "generated_at": now(),
        "source_root": str(source_root),
        "output_root": repo_path(output_root),
        "trading_dates": dates,
        "packet_count": len(packets),
        "slot_count": len(ledger["slots"]),
        "external_review_output_root": repo_path(external_review_dir),
        "packets": packets,
        "source_digests": source_digests(source_root, dates),
        "dry_run_packet_only": True,
        "review_packet_sent": False,
    }
    (manifest_dir / "dry_run_packet_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PREPARED", "output_root": repo_path(output_root), "slots": len(ledger["slots"])}, ensure_ascii=False))
    return 0


def build_ledger(
    *,
    output_root: Path,
    source_root: Path,
    packets: list[dict[str, Any]],
    chatgpt_marker: str,
    gemini_marker: str,
    chatgpt_account_hint: str,
    gemini_target_hint: str,
) -> dict[str, Any]:
    packet_by_date = {row["date"]: row for row in packets}
    slots = []
    for date_text in packet_by_date:
        for provider in PROVIDERS:
            marker = chatgpt_marker if provider == "chatgpt" else gemini_marker
            target_hint = chatgpt_account_hint if provider == "chatgpt" else gemini_target_hint
            slots.append(
                {
                    "slot_id": f"{date_text}:{provider}",
                    "date": date_text,
                    "provider": provider,
                    "status": "PENDING",
                    "attempt_count": 0,
                    "max_attempts": 1,
                    "packet_path": packet_by_date[date_text]["packet_path"],
                    "packet_sha256": packet_by_date[date_text]["packet_sha256"],
                    "target_marker": marker,
                    "target_hint": target_hint,
                    "started_at": None,
                    "finished_at": None,
                    "raw_path": None,
                    "response_path": None,
                    "collect_status_path": None,
                    "result_status": None,
                    "notes": [],
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now(),
        "source_root": str(source_root),
        "output_root": repo_path(output_root),
        "provider_order": list(PROVIDERS),
        "canary_date": packets[0]["date"],
        "external_review_output_root": repo_path(output_root / "external_review"),
        "write_policy": {
            "authorized_max_writes": 36,
            "max_attempts_per_slot": 1,
            "uncertain_write_policy": "stop_without_retry",
            "production_change_allowed": False,
            "scheduler_change_allowed": False,
        },
        "slots": slots,
    }


def verify_output(output_root_raw: Path, *, require_complete: bool) -> int:
    output_root = resolve_output_root(output_root_raw, must_exist=True)
    ledger = read_ledger(output_root)
    errors = validate_ledger(ledger, output_root=output_root, require_complete=require_complete)
    packet_errors = []
    for slot in ledger["slots"]:
        packet_path = resolve_repo_path(slot["packet_path"])
        if not packet_path.exists():
            packet_errors.append(f"{slot['slot_id']}: packet missing")
            continue
        payload = json.loads(packet_path.read_text(encoding="utf-8"))
        packet_errors.extend(f"{slot['slot_id']}: {error}" for error in validate_packet(payload))
        if sha256(packet_path) != slot["packet_sha256"]:
            packet_errors.append(f"{slot['slot_id']}: packet digest changed")
    errors.extend(packet_errors)
    status = "PASS" if not errors else "FAILED"
    print(json.dumps({"status": status, "errors": errors[:50], "slot_count": len(ledger.get("slots", []))}, ensure_ascii=False))
    return 0 if status == "PASS" else 1


def sync_ledger(output_root_raw: Path) -> int:
    output_root = resolve_output_root(output_root_raw, must_exist=True)
    ledger = read_ledger(output_root)
    changed = 0
    for slot in ledger["slots"]:
        provider = slot["provider"]
        date_text = slot["date"]
        review_dir = output_root / "external_review" / date_text
        raw_path = review_dir / f"{provider}_raw_{date_text}.txt"
        response_path = review_dir / f"{provider}_response_{date_text}.json"
        status_path = review_dir / f"{provider}_collect_status_{date_text}.json"
        if not any(path.exists() for path in (raw_path, response_path, status_path)):
            continue
        status_payload = read_json(status_path) if status_path.exists() else {}
        new_status = "OK" if response_path.exists() and status_payload.get("ok") is True else "UNCERTAIN"
        if new_status != slot["status"]:
            changed += 1
        slot["status"] = new_status
        slot["attempt_count"] = max(int(slot.get("attempt_count") or 0), 1)
        slot["raw_path"] = repo_path(raw_path) if raw_path.exists() else None
        slot["response_path"] = repo_path(response_path) if response_path.exists() else None
        slot["collect_status_path"] = repo_path(status_path) if status_path.exists() else None
        slot["result_status"] = status_payload.get("reason") or status_payload.get("status")
        slot["finished_at"] = now()
    ledger["updated_at"] = now()
    ledger_path(output_root).write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "SYNCED", "changed": changed}, ensure_ascii=False))
    return 0


def print_next_slot(output_root_raw: Path) -> int:
    output_root = resolve_output_root(output_root_raw, must_exist=True)
    ledger = read_ledger(output_root)
    blocked = [slot for slot in ledger["slots"] if slot["status"] in {"FAILED", "UNCERTAIN"}]
    if blocked:
        print(json.dumps({"status": "BLOCKED", "blocked_slot": blocked[0]}, ensure_ascii=False))
        return 2
    canary_date = ledger["canary_date"]
    canary_slots = [slot for slot in ledger["slots"] if slot["date"] == canary_date]
    pending_canary = [slot for slot in canary_slots if slot["status"] == "PENDING"]
    if pending_canary:
        print(json.dumps({"status": "NEXT", "slot": pending_canary[0]}, ensure_ascii=False))
        return 0
    if any(slot["status"] != "OK" for slot in canary_slots):
        print(json.dumps({"status": "BLOCKED", "reason": "canary_not_pass"}, ensure_ascii=False))
        return 2
    for slot in ledger["slots"]:
        if slot["status"] == "PENDING":
            print(json.dumps({"status": "NEXT", "slot": slot}, ensure_ascii=False))
            return 0
    print(json.dumps({"status": "COMPLETE"}, ensure_ascii=False))
    return 0


def validate_ledger(ledger: dict[str, Any], *, output_root: Path, require_complete: bool) -> list[str]:
    errors: list[str] = []
    if ledger.get("schema_version") != SCHEMA_VERSION:
        errors.append("ledger schema mismatch")
    slots = ledger.get("slots")
    if not isinstance(slots, list) or len(slots) != 36:
        errors.append(f"expected 36 slots, got {len(slots) if isinstance(slots, list) else 'non-list'}")
        return errors
    seen = set()
    for slot in slots:
        slot_id = slot.get("slot_id")
        if slot_id in seen:
            errors.append(f"duplicate slot_id {slot_id}")
        seen.add(slot_id)
        if slot.get("provider") not in PROVIDERS:
            errors.append(f"{slot_id}: invalid provider")
        if slot.get("max_attempts") != 1:
            errors.append(f"{slot_id}: max_attempts must be 1")
        packet_path = resolve_repo_path(str(slot.get("packet_path") or ""))
        if not path_under(packet_path, output_root / "packets"):
            errors.append(f"{slot_id}: packet outside isolated packet root")
        if require_complete and slot.get("status") != "OK":
            errors.append(f"{slot_id}: incomplete status {slot.get('status')}")
    return errors


def discover_dates(source_root: Path) -> list[str]:
    daily_dir = source_root / "manifest" / "daily"
    dates = sorted(path.stem for path in daily_dir.glob("*.json"))
    if not dates:
        raise SystemExit(f"no daily manifest found under {daily_dir}")
    return dates


def source_digests(source_root: Path, dates: list[str]) -> dict[str, Any]:
    artifacts = source_root / "artifacts"
    rows = {}
    for date_text in dates:
        rows[date_text] = {
            "ranking": digest_if_exists(artifacts / f"ranking_{date_text}.csv"),
            "daily_report": digest_if_exists(artifacts / f"daily_report_{date_text}.json"),
            "daily_run_summary": digest_if_exists(artifacts / f"daily_run_summary_{date_text}.json"),
        }
    return rows


def digest_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    return {"exists": True, "path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def ledger_path(output_root: Path) -> Path:
    return output_root / "ledger.json"


def read_ledger(output_root: Path) -> dict[str, Any]:
    path = ledger_path(output_root)
    if not path.exists():
        raise SystemExit(f"ledger missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_output_root(path: Path, *, must_exist: bool = False) -> Path:
    resolved = (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    allowed_root = (PROJECT_ROOT / "artifacts" / "isolated_external_review_backfill").resolve()
    if not path_under(resolved, allowed_root):
        raise SystemExit(f"output root must stay under {allowed_root}: {resolved}")
    if must_exist and not resolved.exists():
        raise SystemExit(f"output root missing: {resolved}")
    return resolved


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def path_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""壓縮或清理 weekend training 可重建的大型 full JSON artifacts。"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEEKEND_DIR = Path("artifacts/weekend_training")
SCHEMA_VERSION = "weekend-training-full-artifact-cleanup.v1"
OWNER_AGENT_ID = "fog_map"
EXECUTOR_ID = "controlled_grid_drain_host_runner"
TARGET_PATTERNS = {
    "weekend_universe_inventory": re.compile(r"^weekend_universe_inventory_(\d{4}-\d{2}-\d{2})\.json$"),
    "weekend_frontier_queue": re.compile(r"^weekend_frontier_queue_(\d{4}-\d{2}-\d{2})\.json$"),
}
ARCHIVE_PATTERNS = {
    "weekend_universe_inventory": re.compile(r"^weekend_universe_inventory_(\d{4}-\d{2}-\d{2})\.json\.(?:zst|gz)$"),
    "weekend_frontier_queue": re.compile(r"^weekend_frontier_queue_(\d{4}-\d{2}-\d{2})\.json\.(?:zst|gz)$"),
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="compress or cleanup rebuildable weekend training full JSON artifacts")
    parser.add_argument("--root", default=str(PROJECT_ROOT), help="repo root; mainly for fixture verification")
    parser.add_argument("--keep-latest-dates", type=int, default=2, help="保留最近 N 個 artifact 日期")
    parser.add_argument("--keep-date", action="append", default=[], help="額外保留指定日期，可重複傳入")
    parser.add_argument("--action", choices=["compress", "delete"], default="compress", help="候選檔案處理方式")
    parser.add_argument("--execute", action="store_true", help="真的刪除；未指定時只 dry-run")
    parser.add_argument("--compression", choices=["zstd", "gzip"], default="zstd", help="壓縮格式")
    parser.add_argument("--archive-retention-days", type=int, default=30, help="壓縮冷存檔保留天數")
    parser.add_argument("--archive-keep-latest-dates", type=int, default=7, help="壓縮冷存檔至少保留最近 N 個日期")
    parser.add_argument("--no-delete-expired-archives", action="store_true", help="只壓縮，不刪除過期冷存檔")
    parser.add_argument("--today", default=None, help="覆寫今日日期，格式 YYYY-MM-DD；主要給測試用")
    parser.add_argument("--no-require-rollup-ok", action="store_true", help="允許未完成 rollup 的日期被列為候選")
    parser.add_argument("--no-require-summary-md", action="store_true", help="允許同名 .md 摘要不存在的 full JSON 被列為候選")
    parser.add_argument(
        "--report",
        default="artifacts/weekend_training/weekend_full_artifact_cleanup_latest.json",
        help="清理報告輸出路徑；可傳空字串停用",
    )
    return parser.parse_args()


def classify(path: Path) -> tuple[str, str] | None:
    for family, pattern in TARGET_PATTERNS.items():
        match = pattern.match(path.name)
        if match:
            return family, match.group(1)
    return None


def classify_archive(path: Path) -> tuple[str, str] | None:
    for family, pattern in ARCHIVE_PATTERNS.items():
        match = pattern.match(path.name)
        if match:
            return family, match.group(1)
    return None


def rollup_ok(root: Path, date: str) -> tuple[bool, str]:
    path = root / WEEKEND_DIR / f"weekend_training_rollup_{date}.json"
    if not path.exists():
        return False, "missing_rollup"
    payload = read_json(path)
    if payload.get("status") != "OK":
        return False, f"rollup_status={payload.get('status')}"
    return True, "rollup_ok"


def has_keep_marker(path: Path) -> bool:
    return (path.with_suffix(path.suffix + ".keep")).exists() or (path.with_suffix(".keep")).exists()


def collect_candidates(root: Path) -> list[dict[str, Any]]:
    weekend_dir = root / WEEKEND_DIR
    rows: list[dict[str, Any]] = []
    if not weekend_dir.exists():
        return rows
    for path in sorted(weekend_dir.glob("weekend_*_*.json")):
        classified = classify(path)
        if not classified:
            continue
        family, date = classified
        stat = path.stat()
        rows.append(
            {
                "family": family,
                "date": date,
                "path": path,
                "size_bytes": stat.st_size,
                "summary_md": path.with_suffix(".md"),
            }
        )
    return rows


def archive_path(path: Path, compression: str) -> Path:
    suffix = ".zst" if compression == "zstd" else ".gz"
    return Path(str(path) + suffix)


def archive_source_path(path: Path) -> Path:
    if path.name.endswith(".zst") or path.name.endswith(".gz"):
        return Path(str(path).rsplit(".", 1)[0])
    return path


def parse_date(value: str) -> date_type | None:
    try:
        return date_type.fromisoformat(value)
    except ValueError:
        return None


def latest_values(values: list[str], count: int) -> set[str]:
    if count <= 0:
        return set()
    return set(values[-count:])


def collect_archives(root: Path) -> list[dict[str, Any]]:
    weekend_dir = root / WEEKEND_DIR
    rows: list[dict[str, Any]] = []
    if not weekend_dir.exists():
        return rows
    for path in sorted([*weekend_dir.glob("weekend_*_*.json.zst"), *weekend_dir.glob("weekend_*_*.json.gz")]):
        classified = classify_archive(path)
        if not classified:
            continue
        family, date = classified
        stat = path.stat()
        source_path = archive_source_path(path)
        rows.append(
            {
                "family": family,
                "date": date,
                "path": path,
                "size_bytes": stat.st_size,
                "summary_md": source_path.with_suffix(".md"),
            }
        )
    return rows


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    candidates = collect_candidates(root)
    archives = collect_archives(root)
    dates = sorted({row["date"] for row in candidates})
    protected_dates = latest_values(dates, args.keep_latest_dates)
    protected_dates.update(str(date) for date in args.keep_date)
    archive_dates = sorted({row["date"] for row in archives})
    protected_archive_dates = latest_values(archive_dates, args.archive_keep_latest_dates)
    protected_archive_dates.update(str(date) for date in args.keep_date)
    today = parse_date(str(args.today)) if args.today else date_type.today()
    archive_cutoff = today - timedelta(days=max(0, args.archive_retention_days))

    actions: list[dict[str, Any]] = []
    for row in candidates:
        path = row["path"]
        date = str(row["date"])
        keep_reasons: list[str] = []
        delete_reasons: list[str] = []

        if date in protected_dates:
            keep_reasons.append("protected_recent_or_keep_date")
        if has_keep_marker(path):
            keep_reasons.append("has_keep_marker")
        if not args.no_require_summary_md and not row["summary_md"].exists():
            keep_reasons.append("missing_summary_md")
        if not args.no_require_rollup_ok:
            ok, reason = rollup_ok(root, date)
            if ok:
                delete_reasons.append(reason)
            else:
                keep_reasons.append(reason)

        action = "keep" if keep_reasons else args.action
        archive = archive_path(path, args.compression)
        if action == "compress" and archive.exists():
            action = "delete"
            delete_reasons.append("archive_exists")
        actions.append(
            {
                "action": action,
                "archive": repo_path(root, archive),
                "date": date,
                "family": row["family"],
                "path": repo_path(root, path),
                "size_bytes": row["size_bytes"],
                "keep_reasons": keep_reasons,
                "delete_reasons": delete_reasons,
            }
        )

    if not args.no_delete_expired_archives:
        for row in archives:
            path = row["path"]
            date = str(row["date"])
            artifact_date = parse_date(date)
            keep_reasons: list[str] = []
            delete_reasons: list[str] = []

            if date in protected_archive_dates:
                keep_reasons.append("protected_recent_archive_or_keep_date")
            if has_keep_marker(path):
                keep_reasons.append("has_keep_marker")
            if artifact_date is None:
                keep_reasons.append("invalid_artifact_date")
            elif artifact_date > archive_cutoff:
                keep_reasons.append("within_archive_retention_days")
            else:
                delete_reasons.append("archive_retention_expired")
            if not args.no_require_summary_md and not row["summary_md"].exists():
                keep_reasons.append("missing_summary_md")
            if not args.no_require_rollup_ok:
                ok, reason = rollup_ok(root, date)
                if ok:
                    delete_reasons.append(reason)
                else:
                    keep_reasons.append(reason)

            actions.append(
                {
                    "action": "keep" if keep_reasons else "delete_archive",
                    "archive": repo_path(root, path),
                    "date": date,
                    "family": row["family"],
                    "path": repo_path(root, path),
                    "size_bytes": row["size_bytes"],
                    "keep_reasons": keep_reasons,
                    "delete_reasons": delete_reasons,
                }
            )

    reclaim_bytes = sum(int(row["size_bytes"]) for row in actions if row["action"] in {"compress", "delete"})
    archive_delete_bytes = sum(int(row["size_bytes"]) for row in actions if row["action"] == "delete_archive")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "mode": "execute" if args.execute else "dry_run",
        "owner_agent_id": OWNER_AGENT_ID,
        "executor_id": EXECUTOR_ID,
        "policy": {
            "action": args.action,
            "archive_keep_latest_dates": args.archive_keep_latest_dates,
            "archive_retention_days": args.archive_retention_days,
            "archive_retention_cutoff": archive_cutoff.isoformat(),
            "compression": args.compression,
            "delete_expired_archives": not args.no_delete_expired_archives,
            "target_families": sorted(TARGET_PATTERNS),
            "keep_latest_dates": args.keep_latest_dates,
            "keep_dates": sorted(protected_dates),
            "require_rollup_ok": not args.no_require_rollup_ok,
            "require_summary_md": not args.no_require_summary_md,
            "keep_marker_suffixes": [".json.keep", ".keep"],
        },
        "summary": {
            "candidate_count": len(actions),
            "archive_delete_count": sum(1 for row in actions if row["action"] == "delete_archive"),
            "archive_delete_bytes": archive_delete_bytes,
            "archive_delete_gib": round(archive_delete_bytes / 1024 / 1024 / 1024, 3),
            "compress_count": sum(1 for row in actions if row["action"] == "compress"),
            "delete_count": sum(1 for row in actions if row["action"] == "delete"),
            "keep_count": sum(1 for row in actions if row["action"] == "keep"),
            "reclaimable_source_bytes": reclaim_bytes,
            "reclaimable_source_gib": round(reclaim_bytes / 1024 / 1024 / 1024, 3),
        },
        "actions": actions,
    }


def compress_file(path: Path, archive: Path, compression: str) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    if compression == "zstd":
        zstd = shutil.which("zstd")
        if not zstd:
            raise RuntimeError("zstd not found")
        subprocess.run([zstd, "-T0", "-q", "-f", "--rm", str(path), "-o", str(archive)], check=True)
        return
    gzip = shutil.which("gzip")
    if not gzip:
        raise RuntimeError("gzip not found")
    subprocess.run([gzip, "-f", str(path)], check=True)
    gz_path = Path(str(path) + ".gz")
    if gz_path != archive and gz_path.exists():
        gz_path.replace(archive)


def execute_plan(root: Path, plan: dict[str, Any]) -> None:
    for row in plan["actions"]:
        if row["action"] not in {"compress", "delete", "delete_archive"}:
            continue
        path = (root / row["path"]).resolve()
        if not path.is_file():
            row["applied"] = False
            row["error"] = "not_file"
            continue
        if row["action"] == "compress":
            archive = (root / row["archive"]).resolve()
            compress_file(path, archive, str(plan["policy"]["compression"]))
            row["applied"] = True
            row["archive_size_bytes"] = archive.stat().st_size if archive.exists() else None
            continue
        path.unlink()
        row["applied"] = True


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    plan = build_plan(args)
    if args.execute:
        execute_plan(root, plan)
    report = args.report.strip()
    if report:
        report_path = Path(report)
        if not report_path.is_absolute():
            report_path = root / report_path
        write_json(report_path, plan)
    print(
        json.dumps(
            {
                "status": "OK",
                "mode": plan["mode"],
                "archive_delete_count": plan["summary"]["archive_delete_count"],
                "compress_count": plan["summary"]["compress_count"],
                "delete_count": plan["summary"]["delete_count"],
                "reclaimable_source_gib": plan["summary"]["reclaimable_source_gib"],
                "report": report if report else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

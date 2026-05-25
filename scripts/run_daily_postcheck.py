#!/usr/bin/env python3
"""每日流程後驗收：核對 ranking artifact、API 與前端 smoke。

這支腳本只讀 daily 產物與本機服務，不重跑 ETL、ranking 或模型。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
DEFAULT_STATUS_PATH = ARTIFACTS_DIR / "automation_status.json"
FRONTEND_SMOKE_JSON = ARTIFACTS_DIR / "top10_ops02_frontend_smoke_2026-05-19.json"
POSTCHECK_SCHEMA_VERSION = "daily-postcheck.v1"
WEEKLY_CANDIDATES_QUERY = (
    "/api/weekly-candidates?"
    "risk_style=balanced&target_type=stocks&holding_period=swing&"
    "entry_preference=mixed&risk_limit=excludeThemes&limit=10"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="daily 後驗收：ranking / API / frontend smoke")
    parser.add_argument("--date", default=None, help="postcheck run_date；未指定時使用 automation_status.run_date")
    parser.add_argument("--status", default=str(DEFAULT_STATUS_PATH), help="automation_status.json 路徑")
    parser.add_argument("--ranking", default=None, help="指定 ranking CSV；未指定時使用 status metadata")
    parser.add_argument(
        "--allow-expected-ranking",
        action="store_true",
        help="允許使用 dry-run expected_ranking_artifact；只適合 reference smoke，不視為正式 daily acceptance",
    )
    parser.add_argument("--api-base-url", default=os.environ.get("VITE_API_BASE_URL", "http://127.0.0.1:8001"))
    parser.add_argument(
        "--frontend-url",
        default=os.environ.get("TOP10_FRONTEND_URL", f"http://127.0.0.1:{os.environ.get('TOP10_FRONTEND_PORT', '5173')}/"),
    )
    parser.add_argument("--skip-api", action="store_true", help="略過 API consistency check")
    parser.add_argument("--include-frontend", action="store_true", help="執行既有 frontend smoke")
    parser.add_argument("--output", default=None, help="輸出 JSON 路徑；未指定時使用 artifacts/daily_postcheck_YYYY-MM-DD.json")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_step(steps: list[dict[str, Any]], name: str, status: str, **extra: Any) -> None:
    steps.append({"name": name, "status": status, **{k: v for k, v in extra.items() if v is not None}})


def resolve_ranking_path(args: argparse.Namespace, status_payload: dict[str, Any]) -> tuple[Path | None, str]:
    if args.ranking:
        return Path(args.ranking).expanduser().resolve(), "arg"

    metadata = status_payload.get("metadata", {})
    ranking_artifact = metadata.get("ranking_artifact")
    if ranking_artifact:
        return Path(ranking_artifact).expanduser().resolve(), "status.metadata.ranking_artifact"

    expected_artifact = metadata.get("expected_ranking_artifact")
    if args.allow_expected_ranking and expected_artifact and Path(expected_artifact).exists():
        return Path(expected_artifact).expanduser().resolve(), "status.metadata.expected_ranking_artifact"

    run_date = args.date or status_payload.get("run_date")
    if run_date:
        dated_path = ARTIFACTS_DIR / f"ranking_{run_date}.csv"
        if dated_path.exists():
            return dated_path.resolve(), "date"

    return None, "unresolved"


def read_ranking(path: Path) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        for row in reader:
            rows.append(row)

    required = {"stock_id", "stock_name", "risk_adjusted_score"}
    missing = sorted(required.difference(fieldnames))
    if missing:
        raise RuntimeError(f"ranking artifact 缺少欄位：{', '.join(missing)}")
    if not rows:
        raise RuntimeError("ranking artifact 沒有資料列")

    top10 = rows[:10]
    return {
        "path": str(path),
        "row_count": len(rows),
        "columns": fieldnames,
        "top_stock_id": top10[0].get("stock_id"),
        "top_stock_name": top10[0].get("stock_name"),
        "top10_stock_ids": [row.get("stock_id") for row in top10],
        "top10": [
            {
                "rank": index + 1,
                "stock_id": row.get("stock_id"),
                "stock_name": row.get("stock_name"),
                "risk_adjusted_score": row.get("risk_adjusted_score"),
                "gross_exposure": row.get("gross_exposure"),
                "allocated_exposure": row.get("allocated_exposure"),
            }
            for index, row in enumerate(top10)
        ],
    }


def fetch_json(url: str, timeout: float = 10.0) -> tuple[int, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{url} HTTP {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url} 無法連線：{exc.reason}") from exc


def extract_candidates(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("stock_candidates", "candidates", "items", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = extract_candidates(value)
            if nested:
                return nested
    return []


def normalize_stock_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def check_api(api_base_url: str, ranking: dict[str, Any]) -> dict[str, Any]:
    api_base_url = api_base_url.rstrip("/")
    health_status, health_payload = fetch_json(f"{api_base_url}/api/health")
    weekly_status, weekly_payload = fetch_json(f"{api_base_url}{WEEKLY_CANDIDATES_QUERY}")
    candidates = extract_candidates(weekly_payload)
    api_ids = [
        normalize_stock_id(candidate.get("stock_id") or candidate.get("symbol") or candidate.get("ticker"))
        for candidate in candidates
    ]
    api_ids = [stock_id for stock_id in api_ids if stock_id]
    ranking_ids = ranking["top10_stock_ids"]
    overlap = [stock_id for stock_id in ranking_ids if stock_id in api_ids]
    required_overlap = min(10, len(ranking_ids), len(api_ids))

    checks = {
        "health_ok": health_status == 200,
        "weekly_candidates_ok": weekly_status == 200 and len(candidates) > 0,
        "top_stock_consistent": bool(api_ids) and api_ids[0] == ranking["top_stock_id"],
        "top10_overlap_count": len(overlap),
        "top10_required_overlap": required_overlap,
        "top10_overlap_ok": len(overlap) >= required_overlap and required_overlap > 0,
    }
    return {
        "api_base_url": api_base_url,
        "health_status": health_status,
        "weekly_status": weekly_status,
        "candidate_count": len(candidates),
        "api_top_stock_id": api_ids[0] if api_ids else None,
        "ranking_top_stock_id": ranking["top_stock_id"],
        "top10_overlap": overlap,
        "checks": checks,
        "health_payload": health_payload,
    }


def run_frontend_smoke(frontend_url: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["TOP10_FRONTEND_URL"] = frontend_url
    env["TOP10_ARTIFACT_DIR"] = str(ARTIFACTS_DIR)
    completed = subprocess.run(
        ["node", "scripts/verify_frontend_smoke.mjs"],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    smoke_payload = read_json(FRONTEND_SMOKE_JSON)
    return {
        "command": ["node", "scripts/verify_frontend_smoke.mjs"],
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
        "evidence_json": str(FRONTEND_SMOKE_JSON),
        "evidence": smoke_payload,
    }


def main() -> int:
    args = parse_args()
    status_path = Path(args.status).expanduser().resolve()
    status_payload = read_json(status_path)
    run_date = args.date or status_payload.get("run_date") or datetime.now(timezone.utc).date().isoformat()
    output_path = Path(args.output).expanduser().resolve() if args.output else ARTIFACTS_DIR / f"daily_postcheck_{run_date}.json"
    steps: list[dict[str, Any]] = []
    errors: list[str] = []

    payload: dict[str, Any] = {
        "schema_version": POSTCHECK_SCHEMA_VERSION,
        "run_date": run_date,
        "status": "RUNNING",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "automation_status_path": str(status_path),
        "automation_status": {
            "schema_version": status_payload.get("schema_version"),
            "mode": status_payload.get("mode"),
            "status": status_payload.get("status"),
            "dry_run": status_payload.get("dry_run"),
            "run_date": status_payload.get("run_date"),
            "skip_reason": status_payload.get("skip_reason"),
        },
        "steps": steps,
        "errors": errors,
    }

    try:
        ranking_path, ranking_source = resolve_ranking_path(args, status_payload)
        if ranking_path is None:
            raise RuntimeError("找不到可驗收的 ranking artifact")
        if not ranking_path.exists():
            raise RuntimeError(f"ranking artifact 不存在：{ranking_path}")
        ranking = read_ranking(ranking_path)
        ranking["source"] = ranking_source
        if ranking_source == "status.metadata.expected_ranking_artifact":
            payload["acceptance_mode"] = "reference"
        else:
            payload["acceptance_mode"] = "official"
        payload["ranking"] = ranking
        mark_step(steps, "ranking.artifact", "OK", message=str(ranking_path), source=ranking_source)

        if args.skip_api:
            mark_step(steps, "api.consistency", "SKIPPED", message="--skip-api")
        else:
            api_result = check_api(args.api_base_url, ranking)
            payload["api"] = api_result
            api_ok = (
                api_result["checks"]["health_ok"]
                and api_result["checks"]["weekly_candidates_ok"]
                and api_result["checks"]["top_stock_consistent"]
                and api_result["checks"]["top10_overlap_ok"]
            )
            mark_step(
                steps,
                "api.consistency",
                "OK" if api_ok else "FAILED",
                message=(
                    f"api_top={api_result['api_top_stock_id']} ranking_top={ranking['top_stock_id']} "
                    f"overlap={api_result['checks']['top10_overlap_count']}/"
                    f"{api_result['checks']['top10_required_overlap']}"
                ),
            )
            if not api_ok:
                raise RuntimeError("API weekly candidates 與 ranking artifact 不一致")

        if args.include_frontend:
            frontend_result = run_frontend_smoke(args.frontend_url)
            payload["frontend"] = frontend_result
            smoke_checks = frontend_result.get("evidence", {}).get("checks", {})
            smoke_ok = frontend_result["exit_code"] == 0 and all(smoke_checks.values())
            mark_step(
                steps,
                "frontend.smoke",
                "OK" if smoke_ok else "FAILED",
                message=f"exit_code={frontend_result['exit_code']}",
            )
            if not smoke_ok:
                raise RuntimeError("frontend smoke 未通過")
        else:
            mark_step(steps, "frontend.smoke", "SKIPPED", message="未指定 --include-frontend")

        payload["status"] = "REFERENCE" if payload.get("acceptance_mode") == "reference" else "OK"
        return_code = 0
    except Exception as exc:
        payload["status"] = "FAILED"
        errors.append(str(exc))
        return_code = 1
    finally:
        payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(output_path, payload)
        print(json.dumps({"status": payload["status"], "output": str(output_path), "errors": errors}, ensure_ascii=False))

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())

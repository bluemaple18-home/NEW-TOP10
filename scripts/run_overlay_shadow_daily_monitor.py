#!/usr/bin/env python3
"""每日更新 regime history，並執行 Chip／Event／量價警示 append-only shadow。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCHEMA_VERSION = "overlay-shadow-daily-monitor.v1"


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root 必須是 object：{path}")
    return payload


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = handle.name
    os.replace(temporary, path)


def atomic_write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = handle.name
    os.replace(temporary, path)


def run_json_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    parsed: dict[str, Any] | None = None
    if stdout_lines:
        try:
            candidate = json.loads(stdout_lines[-1])
            parsed = candidate if isinstance(candidate, dict) else None
        except json.JSONDecodeError:
            parsed = None
    return {
        "exit_code": completed.returncode,
        "result": parsed,
        "stderr_tail": completed.stderr.splitlines()[-5:],
    }


def update_regime_history(
    *,
    features: Path,
    industry_map: Path,
    regime_history: Path,
    extension: Path,
) -> dict[str, Any]:
    extension_run = run_json_command(
        [
            sys.executable,
            "scripts/build_market_regime_history.py",
            "--features",
            str(features),
            "--industry-map",
            str(industry_map),
            "--output",
            str(extension),
        ]
    )
    if extension_run["exit_code"] != 0:
        raise RuntimeError(f"regime extension build failed：{extension_run}")

    base = read_json(regime_history)
    latest = read_json(extension)
    if (base.get("contract") or {}).get("append_only") is not True:
        raise ValueError("regime history 必須為 append-only")
    base_rows = base.get("rows") or []
    extension_rows = latest.get("rows") or []
    if not base_rows or not extension_rows:
        raise ValueError("regime base／extension 不得為空")
    base_end = max(str(row["trade_date"]) for row in base_rows)
    extension_end = max(str(row["trade_date"]) for row in extension_rows)
    if extension_end < base_end:
        raise ValueError(f"regime extension 落後 base：{extension_end} < {base_end}")

    from scripts.build_append_only_market_regime_history import merge_histories, render_markdown

    if extension_end == base_end:
        atomic_write_text(regime_history.with_suffix(".md"), render_markdown(base))
        return {
            "status": "NO_NEW_REGIME_DATES",
            "base_end_before": base_end,
            "extension_end": extension_end,
            "appended_days": 0,
        }

    merged = merge_histories(base, latest)
    merged["inputs"] = {
        "base": repo_path(regime_history),
        "extension": repo_path(extension),
    }
    atomic_write(regime_history, merged)
    atomic_write_text(regime_history.with_suffix(".md"), render_markdown(merged))
    return {
        "status": "APPENDED",
        "base_end_before": base_end,
        "extension_end": extension_end,
        "appended_days": int(merged["summary"]["appended_days"]),
        "drift_days_preserved": int(merged["summary"]["overlap_label_drift_days"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run daily append-only overlay shadow monitor")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument(
        "--regime-history",
        default="artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json",
    )
    parser.add_argument(
        "--regime-extension",
        default="artifacts/model_experiments/market_regime_history_shadow_extension_latest.json",
    )
    parser.add_argument("--chip-config", default="config/chip_liquidity_overlay_shadow_v1.json")
    parser.add_argument(
        "--chip-ledger",
        default="artifacts/model_experiments/chip_overlay_shadow_ledger_v1.json",
    )
    parser.add_argument("--event-config", default="config/event_liquidity_overlay_shadow_v1.json")
    parser.add_argument(
        "--event-ledger",
        default="artifacts/model_experiments/event_overlay_shadow_ledger_v1.json",
    )
    parser.add_argument("--volume-climax-config", default="config/volume_climax_warning_shadow_v1.json")
    parser.add_argument(
        "--volume-climax-ledger",
        default="artifacts/model_experiments/volume_climax_warning_shadow_ledger_v1.json",
    )
    parser.add_argument(
        "--status-output",
        default="artifacts/model_experiments/overlay_shadow_daily_status.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status_path = resolve_path(args.status_output)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "RUNNING",
        "promotion_allowed": False,
        "changes_production_ranking": False,
        "components": {},
    }
    try:
        regime_path = resolve_path(args.regime_history)
        payload["components"]["regime_history"] = update_regime_history(
            features=resolve_path(args.features),
            industry_map=resolve_path(args.industry_map),
            regime_history=regime_path,
            extension=resolve_path(args.regime_extension),
        )
        commands = {
            "chip": [
                sys.executable,
                "scripts/run_chip_overlay_append_only_shadow.py",
                "--config",
                str(resolve_path(args.chip_config)),
                "--ledger",
                str(resolve_path(args.chip_ledger)),
                "--market-regime-history",
                str(regime_path),
            ],
            "event": [
                sys.executable,
                "scripts/run_feature_group_overlay_append_only_shadow.py",
                "--config",
                str(resolve_path(args.event_config)),
                "--ledger",
                str(resolve_path(args.event_ledger)),
                "--market-regime-history",
                str(regime_path),
            ],
            "volume_climax": [
                sys.executable,
                "scripts/run_volume_climax_warning_append_only_shadow.py",
                "--config",
                str(resolve_path(args.volume_climax_config)),
                "--ledger",
                str(resolve_path(args.volume_climax_ledger)),
                "--features",
                str(resolve_path(args.features)),
            ],
        }
        for name, command in commands.items():
            payload["components"][name] = run_json_command(command)
        failed = [
            name
            for name in ("chip", "event", "volume_climax")
            if int(payload["components"][name]["exit_code"]) != 0
        ]
        payload["status"] = "OK" if not failed else "PARTIAL"
        payload["failed_components"] = failed
    except Exception as exc:
        payload["status"] = "FAILED"
        payload["error"] = str(exc)

    atomic_write(status_path, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "status_output": repo_path(status_path),
                "chip": (payload["components"].get("chip") or {}).get("result"),
                "event": (payload["components"].get("event") or {}).get("result"),
                "volume_climax": (payload["components"].get("volume_climax") or {}).get("result"),
                "promotion_allowed": False,
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())

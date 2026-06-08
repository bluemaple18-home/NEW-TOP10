#!/usr/bin/env python3
"""建立 M4 factor run manifest。

只讀取既有 feature frame 並輸出因子來源與洩漏檢查結果；不訓練模型、不改排名。
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modeling import build_factor_run_manifest, load_m4_feature_frame


ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build M4 factor run manifest")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def render_markdown(payload: dict) -> str:
    lines = [
        "# M4 Factor Run Manifest",
        "",
        f"- status：`{payload['status']}`",
        f"- factor_count：`{payload['summary']['factor_count']}`",
        f"- trainable_factor_count：`{payload['summary']['trainable_factor_count']}`",
        f"- issue_count：`{payload['summary']['issue_count']}`",
        f"- does_not_change_production_ranking：`{payload['contract']['does_not_change_production_ranking']}`",
        "",
        "| Group | Source | Availability | Training |",
        "|---|---|---|---|",
    ]
    for group in payload["groups"].values():
        lines.append(
            f"| {group['group_id']} | {group['source_layer']} | "
            f"{group['availability_rule']} | {group['training_allowed']} |"
        )
    if payload["issues"]:
        lines.extend(["", "| Severity | Factor | Message |", "|---|---|---|"])
        for issue in payload["issues"]:
            lines.append(f"| {issue['severity']} | {issue['factor_id']} | {issue['message']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    frame, metadata = load_m4_feature_frame(data_dir=resolve_path(args.data_dir) or PROJECT_ROOT / "data" / "clean", project_root=PROJECT_ROOT)
    payload = build_factor_run_manifest(frame, metadata)
    output = resolve_path(args.output) or ARTIFACTS_DIR / f"factor_run_manifest_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())

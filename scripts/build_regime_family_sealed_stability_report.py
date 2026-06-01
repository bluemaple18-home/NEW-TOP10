#!/usr/bin/env python3
"""彙整 regime family sealed replay 多視窗穩定性。

用途是把多個 sealed replay artifact 收斂成機器可讀結論；
此腳本只讀 research artifacts，不訓練模型、不改 production ranking。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "regime-family-sealed-stability.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build regime family sealed stability report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--artifact", action="append", required=True, help="格式 label=path/to/artifact.json")
    parser.add_argument("--family", default="BIG_BULL")
    parser.add_argument("--min-windows", type=int, default=3)
    parser.add_argument("--min-positive-topn-uplift-ratio", type=float, default=1.0)
    parser.add_argument("--min-positive-topn-delta-ratio", type=float, default=0.75)
    parser.add_argument("--min-nonnegative-auc-delta-ratio", type=float, default=0.75)
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


def parse_artifact_arg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"--artifact 需為 label=path：{value}")
    label, raw_path = value.split("=", 1)
    path = resolve_path(raw_path.strip())
    if path is None:
        raise RuntimeError("path resolution failed")
    return label.strip(), path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def family_row(payload: dict[str, Any], family: str) -> dict[str, Any]:
    for row in payload.get("families", []):
        if str(row.get("family")).upper() == family.upper():
            return row
    raise ValueError(f"artifact 缺少 family={family}")


def window_row(label: str, path: Path, payload: dict[str, Any], family: str) -> dict[str, Any]:
    row = family_row(payload, family)
    selected_name = row.get("selected_candidate_variant")
    variants = row.get("variants") if isinstance(row.get("variants"), dict) else {}
    selected = variants.get(selected_name, {}) if selected_name else {}
    baseline = variants.get("global_baseline", {})
    diag = row.get("diagnostics") if isinstance(row.get("diagnostics"), dict) else {}
    return {
        "label": label,
        "artifact": repo_path(path),
        "decision": row.get("decision"),
        "selected_candidate_variant": selected_name,
        "sealed_start_date": (payload.get("split") or {}).get("sealed_start_date"),
        "sealed_end_date": (payload.get("split") or {}).get("sealed_end_date"),
        "sealed_trade_days": (payload.get("split") or {}).get("sealed_trade_days"),
        "sealed_family_date_count": row.get("sealed_family_date_count"),
        "selected_auc": selected.get("auc"),
        "baseline_auc": baseline.get("auc"),
        "auc_delta_vs_global": diag.get("auc_delta_vs_global"),
        "selected_topn_return": (selected.get("topn_proxy") or {}).get("avg_topn_future_return"),
        "baseline_topn_return": (baseline.get("topn_proxy") or {}).get("avg_topn_future_return"),
        "topn_return_delta_vs_global": diag.get("topn_return_delta_vs_global"),
        "topn_uplift": diag.get("topn_uplift"),
    }


def ratio(values: list[bool]) -> float | None:
    if not values:
        return None
    return round(sum(1 for value in values if value) / len(values), 6)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    artifacts = [parse_artifact_arg(value) for value in args.artifact]
    windows = [window_row(label, path, load_json(path), args.family) for label, path in artifacts]
    frame = pd.DataFrame(windows)
    topn_uplift_positive = [float(value) > 0 for value in frame["topn_uplift"].dropna().tolist()]
    topn_delta_positive = [float(value) > 0 for value in frame["topn_return_delta_vs_global"].dropna().tolist()]
    auc_delta_nonnegative = [float(value) >= 0 for value in frame["auc_delta_vs_global"].dropna().tolist()]
    metrics = {
        "window_count": int(len(windows)),
        "positive_topn_uplift_ratio": ratio(topn_uplift_positive),
        "positive_topn_delta_ratio": ratio(topn_delta_positive),
        "nonnegative_auc_delta_ratio": ratio(auc_delta_nonnegative),
        "avg_topn_uplift": round(float(frame["topn_uplift"].dropna().mean()), 6) if frame["topn_uplift"].notna().any() else None,
        "avg_topn_return_delta_vs_global": round(float(frame["topn_return_delta_vs_global"].dropna().mean()), 6)
        if frame["topn_return_delta_vs_global"].notna().any()
        else None,
        "avg_auc_delta_vs_global": round(float(frame["auc_delta_vs_global"].dropna().mean()), 6)
        if frame["auc_delta_vs_global"].notna().any()
        else None,
    }
    model_failures = []
    ranking_failures = []
    if metrics["window_count"] < args.min_windows:
        model_failures.append(f"window_count<{args.min_windows}")
        ranking_failures.append(f"window_count<{args.min_windows}")
    if metrics["nonnegative_auc_delta_ratio"] is None or metrics["nonnegative_auc_delta_ratio"] < args.min_nonnegative_auc_delta_ratio:
        model_failures.append(f"nonnegative_auc_delta_ratio<{args.min_nonnegative_auc_delta_ratio}")
    if metrics["positive_topn_uplift_ratio"] is None or metrics["positive_topn_uplift_ratio"] < args.min_positive_topn_uplift_ratio:
        ranking_failures.append(f"positive_topn_uplift_ratio<{args.min_positive_topn_uplift_ratio}")
    if metrics["positive_topn_delta_ratio"] is None or metrics["positive_topn_delta_ratio"] < args.min_positive_topn_delta_ratio:
        ranking_failures.append(f"positive_topn_delta_ratio<{args.min_positive_topn_delta_ratio}")
    model_decision = "MODEL_PROMOTION_BLOCKED" if model_failures else "MODEL_STABILITY_PASS"
    ranking_decision = "RANKING_FOLLOWUP_CANDIDATE" if not ranking_failures else "RANKING_MONITOR_ONLY"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "family": args.family.upper(),
        "decision": model_decision,
        "ranking_decision": ranking_decision,
        "decision_rationale": "多視窗 stability 只用於收斂下一輪假設，不允許 production promotion。",
        "contract": {
            "research_only": True,
            "reads_research_artifacts_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "decision_policy": {
            "min_windows": args.min_windows,
            "min_positive_topn_uplift_ratio": args.min_positive_topn_uplift_ratio,
            "min_positive_topn_delta_ratio": args.min_positive_topn_delta_ratio,
            "min_nonnegative_auc_delta_ratio": args.min_nonnegative_auc_delta_ratio,
        },
        "metrics": metrics,
        "failures": {
            "model": model_failures,
            "ranking": ranking_failures,
        },
        "windows": windows,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# Regime Family Sealed Stability",
        "",
        f"- family: {payload['family']}",
        f"- model_decision: {payload['decision']}",
        f"- ranking_decision: {payload['ranking_decision']}",
        f"- avg_auc_delta_vs_global: {payload['metrics']['avg_auc_delta_vs_global']}",
        f"- avg_topn_return_delta_vs_global: {payload['metrics']['avg_topn_return_delta_vs_global']}",
        f"- avg_topn_uplift: {payload['metrics']['avg_topn_uplift']}",
        "",
        "## Windows",
    ]
    for row in payload.get("windows", []):
        lines.append(
            "- "
            f"{row['label']}: decision={row['decision']}, "
            f"auc_delta={row['auc_delta_vs_global']}, "
            f"topn_delta={row['topn_return_delta_vs_global']}, "
            f"topn_uplift={row['topn_uplift']}"
        )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or OUTPUT_DIR / f"regime_family_sealed_stability_{args.date}.json"
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_markdown(payload, output)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "ranking_decision": payload["ranking_decision"], "output": repo_path(output), "metrics": payload["metrics"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

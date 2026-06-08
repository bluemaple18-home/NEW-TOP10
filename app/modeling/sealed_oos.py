"""封閉 OOS 測試切分與評估工具。

此模組的邊界是：sealed period 只可用於 promotion gate 與報告，
不可用於訓練、調參、校準或 PSI baseline 建立。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import pickle

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score


SCHEMA_VERSION = "sealed-oos-report.v1"
SPLIT_SCHEMA_VERSION = "sealed-oos-split.v1"


@dataclass(frozen=True)
class SealedOOSConfig:
    enabled: bool = True
    sealed_trade_days: int = 60
    embargo_trade_days: int | None = None
    min_train_trade_days: int = 252
    min_sealed_trade_days: int = 40
    min_sealed_samples: int = 500
    min_positive_labels: int = 20
    min_negative_labels: int = 20
    min_auc: float = 0.50
    min_top_n_return_uplift: float = 0.0
    min_top_n_hit_rate_uplift: float = 0.0
    top_n: int = 10
    require_model_split_metadata: bool = True

    @classmethod
    def from_mapping(cls, values: dict[str, Any] | None, horizon: int) -> "SealedOOSConfig":
        values = values or {}
        embargo = values.get("embargo_trade_days")
        return cls(
            enabled=_bool_value(values.get("enabled", True)),
            sealed_trade_days=int(values.get("sealed_trade_days", cls.sealed_trade_days)),
            embargo_trade_days=int(embargo) if embargo is not None else horizon,
            min_train_trade_days=int(values.get("min_train_trade_days", cls.min_train_trade_days)),
            min_sealed_trade_days=int(values.get("min_sealed_trade_days", cls.min_sealed_trade_days)),
            min_sealed_samples=int(values.get("min_sealed_samples", cls.min_sealed_samples)),
            min_positive_labels=int(values.get("min_positive_labels", cls.min_positive_labels)),
            min_negative_labels=int(values.get("min_negative_labels", cls.min_negative_labels)),
            min_auc=float(values.get("min_auc", cls.min_auc)),
            min_top_n_return_uplift=float(
                values.get("min_top_n_return_uplift", cls.min_top_n_return_uplift)
            ),
            min_top_n_hit_rate_uplift=float(
                values.get("min_top_n_hit_rate_uplift", cls.min_top_n_hit_rate_uplift)
            ),
            top_n=int(values.get("top_n", cls.top_n)),
            require_model_split_metadata=_bool_value(values.get("require_model_split_metadata", True)),
        )


@dataclass(frozen=True)
class SealedOOSSplit:
    development: pd.DataFrame
    embargo: pd.DataFrame
    sealed: pd.DataFrame
    metadata: dict[str, Any]


def build_sealed_oos_split(
    frame: pd.DataFrame,
    config: SealedOOSConfig,
    *,
    horizon: int,
    threshold: float,
) -> SealedOOSSplit:
    """依交易日建立 development / embargo / sealed 三段。

    development 可用於 train/tune/calibration；embargo 與 sealed 都不可用於訓練。
    embargo 的目的，是避免 development 尾端標籤 horizon 穿越 sealed 開始日。
    """

    if not config.enabled:
        normalized = _with_trade_date(frame)
        return SealedOOSSplit(
            development=normalized,
            embargo=normalized.iloc[0:0].copy(),
            sealed=normalized.iloc[0:0].copy(),
            metadata={"schema_version": SPLIT_SCHEMA_VERSION, "enabled": False},
        )

    normalized = _with_trade_date(frame)
    dates = _unique_trade_dates(normalized)
    embargo_days = config.embargo_trade_days if config.embargo_trade_days is not None else horizon
    required_days = config.min_train_trade_days + embargo_days + config.min_sealed_trade_days
    if len(dates) < required_days:
        raise ValueError(
            "sealed OOS 交易日不足："
            f"available={len(dates)} required={required_days} "
            f"(train={config.min_train_trade_days}, embargo={embargo_days}, sealed={config.min_sealed_trade_days})"
        )

    sealed_days = max(config.sealed_trade_days, config.min_sealed_trade_days)
    if len(dates) < config.min_train_trade_days + embargo_days + sealed_days:
        raise ValueError(
            "sealed OOS 指定視窗過長："
            f"available={len(dates)} train_min={config.min_train_trade_days} "
            f"embargo={embargo_days} sealed={sealed_days}"
        )

    sealed_start_idx = len(dates) - sealed_days
    train_end_idx = sealed_start_idx - embargo_days - 1
    if train_end_idx < config.min_train_trade_days - 1:
        raise ValueError(
            "sealed OOS development 視窗不足："
            f"train_days={train_end_idx + 1} min={config.min_train_trade_days}"
        )

    train_dates = dates[: train_end_idx + 1]
    embargo_dates = dates[train_end_idx + 1 : sealed_start_idx]
    sealed_dates = dates[sealed_start_idx:]

    development = normalized[normalized["trade_date"].isin(train_dates)].copy()
    embargo = normalized[normalized["trade_date"].isin(embargo_dates)].copy()
    sealed = normalized[normalized["trade_date"].isin(sealed_dates)].copy()
    if len(sealed) < config.min_sealed_samples:
        raise ValueError(f"sealed OOS 樣本不足：sealed_rows={len(sealed)} min={config.min_sealed_samples}")

    positives = int(pd.to_numeric(sealed["target"], errors="coerce").fillna(0).sum())
    negatives = int(len(sealed) - positives)
    if positives < config.min_positive_labels or negatives < config.min_negative_labels:
        raise ValueError(
            "sealed OOS 類別樣本不足："
            f"positive={positives} min_positive={config.min_positive_labels}, "
            f"negative={negatives} min_negative={config.min_negative_labels}"
        )

    metadata = {
        "schema_version": SPLIT_SCHEMA_VERSION,
        "enabled": True,
        "horizon": horizon,
        "threshold": threshold,
        "sealed_trade_days": int(len(sealed_dates)),
        "embargo_trade_days": int(len(embargo_dates)),
        "development_trade_days": int(len(train_dates)),
        "development_rows": int(len(development)),
        "embargo_rows": int(len(embargo)),
        "sealed_rows": int(len(sealed)),
        "positive_labels": positives,
        "negative_labels": negatives,
        "train_start_date": _date_text(train_dates[0]),
        "train_end_date": _date_text(train_dates[-1]),
        "embargo_start_date": _date_text(embargo_dates[0]) if len(embargo_dates) else None,
        "embargo_end_date": _date_text(embargo_dates[-1]) if len(embargo_dates) else None,
        "sealed_start_date": _date_text(sealed_dates[0]),
        "sealed_end_date": _date_text(sealed_dates[-1]),
        "latest_label_date": _date_text(dates[-1]),
        "notes": [
            "development 可用於 train/tune/calibration。",
            "embargo 與 sealed 不可用於訓練、調參、校準或 PSI baseline。",
        ],
    }
    return SealedOOSSplit(development=development, embargo=embargo, sealed=sealed, metadata=metadata)


def evaluate_sealed_oos_model(
    *,
    model_payload: Any,
    labeled_frame: pd.DataFrame,
    config: SealedOOSConfig,
    horizon: int,
    threshold: float,
    model_path: Path | None = None,
) -> dict[str, Any]:
    """在 sealed OOS 視窗上評估候選模型，回傳可落檔的 gate report。"""

    generated_at = datetime.now(timezone.utc).isoformat()
    failures: list[str] = []
    split = build_sealed_oos_split(labeled_frame, config, horizon=horizon, threshold=threshold)
    model, feature_names, model_metadata, has_calibrator = _unpack_model(model_payload)
    leakage_checks = _leakage_checks(model_metadata, split.metadata, config)
    failures.extend(check["message"] for check in leakage_checks if check["status"] == "FAILED")

    missing_features = [feature for feature in feature_names if feature not in split.sealed.columns]
    if model is None:
        failures.append("model payload 缺少 model")
        metrics: dict[str, Any] = {}
    elif not feature_names:
        failures.append("model payload 缺少 feature_names")
        metrics = {}
    elif missing_features:
        failures.append(f"sealed frame 缺少模型特徵：{missing_features[:10]}")
        metrics = {}
    else:
        scored = _score_sealed_frame(model_payload, model, feature_names, split.sealed)
        metrics = _sealed_metrics(scored, config=config, threshold=threshold)
        failures.extend(_threshold_failures(metrics, config))

    status = "OK" if not failures else "FAILED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "failures": failures,
        "model": {
            "path": str(model_path) if model_path else None,
            "sha256": sha256(model_path) if model_path and model_path.exists() else None,
            "payload_type": type(model_payload).__name__,
            "feature_count": len(feature_names),
            "has_metadata": bool(model_metadata),
            "has_calibrator": has_calibrator,
        },
        "split": split.metadata,
        "config": asdict(config),
        "leakage_checks": leakage_checks,
        "metrics": metrics,
        "notes": [
            "此報告是 promotion gate；sealed period 不得被用於訓練、調參或校準。",
            "若 status=FAILED，retrain flow 必須 rollback 候選模型與 baseline。",
        ],
    }


def load_model_payload(path: Path) -> Any:
    with path.open("rb") as handle:
        return pickle.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _score_sealed_frame(model_payload: Any, model: Any, feature_names: list[str], sealed: pd.DataFrame) -> pd.DataFrame:
    scored = sealed.copy()
    X = scored[feature_names].apply(pd.to_numeric, errors="coerce")
    raw_prob = np.asarray(model.predict(X), dtype=float)
    calibrator = model_payload.get("calibrator") if isinstance(model_payload, dict) else None
    if calibrator is not None:
        model_prob = np.asarray(calibrator.predict(raw_prob), dtype=float)
    else:
        model_prob = raw_prob
    scored["raw_prob"] = np.clip(raw_prob, 0.0, 1.0)
    scored["model_prob"] = np.clip(model_prob, 0.0, 1.0)
    scored["target"] = pd.to_numeric(scored["target"], errors="coerce").astype(int)
    scored["future_return"] = pd.to_numeric(scored["future_return"], errors="coerce")
    return scored


def _sealed_metrics(scored: pd.DataFrame, *, config: SealedOOSConfig, threshold: float) -> dict[str, Any]:
    y = scored["target"].astype(int)
    prob = scored["model_prob"].astype(float)
    auc = None
    if y.nunique() > 1:
        auc = float(roc_auc_score(y, prob))
    metrics: dict[str, Any] = {
        "rows": int(len(scored)),
        "trade_days": int(scored["trade_date"].nunique()),
        "positive_rate": float(y.mean()),
        "auc": auc,
        "logloss": float(log_loss(y, np.clip(prob, 1e-6, 1 - 1e-6), labels=[0, 1])) if y.nunique() > 1 else None,
        "brier": float(brier_score_loss(y, prob)),
        "mean_future_return": _round_or_none(scored["future_return"].mean()),
    }
    metrics.update(_top_n_metrics(scored, config=config, threshold=threshold))
    return metrics


def _top_n_metrics(scored: pd.DataFrame, *, config: SealedOOSConfig, threshold: float) -> dict[str, Any]:
    daily_rows: list[dict[str, float]] = []
    for trade_date, group in scored.groupby("trade_date"):
        if len(group) < config.top_n:
            continue
        top = group.nlargest(config.top_n, "model_prob")
        daily_rows.append(
            {
                "trade_date": trade_date,
                "top_n_return": float(top["future_return"].mean()),
                "universe_return": float(group["future_return"].mean()),
                "top_n_hit_rate": float((top["future_return"] > threshold).mean()),
                "universe_hit_rate": float((group["future_return"] > threshold).mean()),
                "top_n_avg_prob": float(top["model_prob"].mean()),
                "universe_avg_prob": float(group["model_prob"].mean()),
            }
        )
    if not daily_rows:
        return {
            "top_n": config.top_n,
            "top_n_days": 0,
            "top_n_mean_return": None,
            "universe_daily_mean_return": None,
            "top_n_return_uplift": None,
            "top_n_hit_rate": None,
            "universe_hit_rate": None,
            "top_n_hit_rate_uplift": None,
        }

    daily = pd.DataFrame(daily_rows)
    top_n_return = float(daily["top_n_return"].mean())
    universe_return = float(daily["universe_return"].mean())
    top_n_hit = float(daily["top_n_hit_rate"].mean())
    universe_hit = float(daily["universe_hit_rate"].mean())
    return {
        "top_n": config.top_n,
        "top_n_days": int(len(daily)),
        "top_n_mean_return": _round_or_none(top_n_return),
        "universe_daily_mean_return": _round_or_none(universe_return),
        "top_n_return_uplift": _round_or_none(top_n_return - universe_return),
        "top_n_hit_rate": _round_or_none(top_n_hit),
        "universe_hit_rate": _round_or_none(universe_hit),
        "top_n_hit_rate_uplift": _round_or_none(top_n_hit - universe_hit),
        "top_n_avg_prob": _round_or_none(daily["top_n_avg_prob"].mean()),
        "universe_avg_prob": _round_or_none(daily["universe_avg_prob"].mean()),
    }


def _threshold_failures(metrics: dict[str, Any], config: SealedOOSConfig) -> list[str]:
    failures: list[str] = []
    auc = metrics.get("auc")
    if auc is None:
        failures.append("sealed AUC 無法計算：sealed target 只有單一類別")
    elif auc < config.min_auc:
        failures.append(f"sealed AUC={auc:.4f} < min_auc={config.min_auc:.4f}")

    return_uplift = metrics.get("top_n_return_uplift")
    if return_uplift is None:
        failures.append("sealed top_n_return_uplift 無法計算")
    elif return_uplift < config.min_top_n_return_uplift:
        failures.append(
            f"sealed top_n_return_uplift={return_uplift:.4f} "
            f"< min={config.min_top_n_return_uplift:.4f}"
        )

    hit_uplift = metrics.get("top_n_hit_rate_uplift")
    if hit_uplift is None:
        failures.append("sealed top_n_hit_rate_uplift 無法計算")
    elif hit_uplift < config.min_top_n_hit_rate_uplift:
        failures.append(
            f"sealed top_n_hit_rate_uplift={hit_uplift:.4f} "
            f"< min={config.min_top_n_hit_rate_uplift:.4f}"
        )
    return failures


def _leakage_checks(
    model_metadata: dict[str, Any],
    split_metadata: dict[str, Any],
    config: SealedOOSConfig,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    sealed_meta = model_metadata.get("sealed_oos") if isinstance(model_metadata, dict) else None
    if not sealed_meta:
        status = "FAILED" if config.require_model_split_metadata else "WARN"
        checks.append(
            {
                "name": "model.sealed_oos_metadata",
                "status": status,
                "message": "model metadata 缺少 sealed_oos",
                "actual": None,
                "expected": "sealed_oos",
            }
        )
        return checks

    checks.append(
        {
            "name": "model.sealed_oos_metadata",
            "status": "OK",
            "message": "present",
            "actual": sealed_meta.get("schema_version"),
            "expected": split_metadata.get("schema_version"),
        }
    )
    expected_pairs = {
        "train_end_date": split_metadata.get("train_end_date"),
        "sealed_start_date": split_metadata.get("sealed_start_date"),
        "sealed_end_date": split_metadata.get("sealed_end_date"),
        "embargo_trade_days": split_metadata.get("embargo_trade_days"),
        "sealed_trade_days": split_metadata.get("sealed_trade_days"),
    }
    for key, expected in expected_pairs.items():
        actual = sealed_meta.get(key)
        status = "OK" if actual == expected else "FAILED"
        checks.append(
            {
                "name": f"model.sealed_oos.{key}",
                "status": status,
                "message": f"actual={actual} expected={expected}",
                "actual": actual,
                "expected": expected,
                "contract": {
                    "model_metadata_path": f"metadata.sealed_oos.{key}",
                    "fixed_split_path": f"split.{key}",
                    "split_schema_version": split_metadata.get("schema_version"),
                },
            }
        )

    train_end = pd.to_datetime(sealed_meta.get("train_end_date"), errors="coerce")
    sealed_start = pd.to_datetime(split_metadata.get("sealed_start_date"), errors="coerce")
    status = "OK" if pd.notna(train_end) and pd.notna(sealed_start) and train_end < sealed_start else "FAILED"
    train_text = train_end.date().isoformat() if pd.notna(train_end) else None
    sealed_text = sealed_start.date().isoformat() if pd.notna(sealed_start) else None
    checks.append(
        {
            "name": "model.sealed_oos.no_train_overlap",
            "status": status,
            "message": f"train_end={train_text} sealed_start={sealed_text}",
            "actual": train_text,
            "expected": f"< {sealed_text}" if sealed_text else None,
            "contract": {
                "model_metadata_path": "metadata.sealed_oos.train_end_date",
                "fixed_split_path": "split.sealed_start_date",
                "split_schema_version": split_metadata.get("schema_version"),
            },
        }
    )
    return checks


def _unpack_model(model_payload: Any) -> tuple[Any, list[str], dict[str, Any], bool]:
    if isinstance(model_payload, dict):
        model = model_payload.get("model")
        metadata = model_payload.get("metadata") if isinstance(model_payload.get("metadata"), dict) else {}
        feature_names = model_payload.get("feature_names")
        if not feature_names and hasattr(model, "feature_name"):
            feature_names = model.feature_name()
        return model, [str(name) for name in feature_names or []], metadata, model_payload.get("calibrator") is not None
    feature_names = model_payload.feature_name() if hasattr(model_payload, "feature_name") else []
    return model_payload, [str(name) for name in feature_names], {}, False


def _with_trade_date(frame: pd.DataFrame) -> pd.DataFrame:
    if "trade_date" not in frame.columns and "date" not in frame.columns:
        raise ValueError("sealed OOS frame 缺少 date/trade_date 欄位")
    result = frame.copy()
    source = "trade_date" if "trade_date" in result.columns else "date"
    result["trade_date"] = pd.to_datetime(result[source], errors="coerce").dt.normalize()
    if result["trade_date"].isna().any():
        raise ValueError("sealed OOS frame 含不可解析交易日")
    sort_cols = ["trade_date", "stock_id"] if "stock_id" in result.columns else ["trade_date"]
    return result.sort_values(sort_cols).copy()


def _unique_trade_dates(frame: pd.DataFrame) -> np.ndarray:
    return frame["trade_date"].drop_duplicates().sort_values().to_numpy()


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _round_or_none(value: Any, digits: int = 6) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text not in {"0", "false", "no", "off"}

"""TOP10 研究稽核器：只讀檢查 ranking 與研究 artifact。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


AUDIT_SCHEMA_VERSION = "top10.research-audit.v1"
CORE_SCORE_COLUMNS = (
    "final_score",
    "model_prob",
    "prediction_score",
    "quality_score",
)


@dataclass(frozen=True)
class AuditInputs:
    """稽核輸入路徑；所有路徑均為唯讀來源。"""

    ranking: Path
    features: Path | None = None
    fundamentals: Path | None = None
    backtest: Path | None = None


def build_audit(inputs: AuditInputs) -> dict[str, Any]:
    """建立 deterministic 稽核報告，不修改任何輸入或 production artifact。"""

    ranking = _read_table(inputs.ranking)
    checks: list[dict[str, Any]] = []
    checks.extend(_ranking_checks(ranking))
    checks.append(_reasons_evidence_check(ranking))

    optional_sources: dict[str, Any] = {}
    for label, path in (
        ("features", inputs.features),
        ("fundamentals", inputs.fundamentals),
        ("backtest", inputs.backtest),
    ):
        if path is None:
            optional_sources[label] = {"provided": False}
            continue
        snapshot = _snapshot(path)
        optional_sources[label] = {"provided": True, **snapshot}
        if label in {"features", "fundamentals"}:
            frame = _read_table(path)
            checks.append(_stock_id_coverage_check(ranking, frame, label))

    blocking = [item for item in checks if item["severity"] == "blocking" and not item["ok"]]
    warnings = [item for item in checks if item["severity"] == "warning" and not item["ok"]]
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "status": "NO-GO" if blocking else "GO",
        "contract": {
            "research_only": True,
            "production_mutation": False,
            "changes_model": False,
            "changes_production_ranking": False,
        },
        "inputs": {
            "ranking": _snapshot(inputs.ranking),
            **optional_sources,
        },
        "summary": {
            "blocking_count": len(blocking),
            "warning_count": len(warnings),
            "ranking_rows": int(len(ranking)),
            "ranking_stock_count": int(ranking["stock_id"].nunique()) if "stock_id" in ranking else 0,
        },
        "checks": checks,
        "conclusion": {
            "status": "NO-GO" if blocking else "GO",
            "blocking_reasons": [item["name"] for item in blocking],
            "warnings": [item["name"] for item in warnings],
        },
    }


def write_audit(payload: dict[str, Any], output: Path) -> None:
    """寫入研究稽核 artifact；拒絕寫入輸入檔。"""

    output = Path(output)
    input_paths = {
        Path(value["path"]).resolve()
        for value in payload["inputs"].values()
        if value.get("provided", True) and value.get("path")
    }
    if output.resolve() in input_paths:
        raise ValueError("audit output must not overwrite an input artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _read_table(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"audit input not found: {path}")
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"stock_id": "string"})


def _ranking_checks(frame: pd.DataFrame) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    required = ["stock_id"]
    missing = [column for column in required if column not in frame.columns]
    checks.append(_check("ranking_required_columns", not missing, "blocking", {"missing": missing}))
    if missing:
        return checks

    ids = frame["stock_id"].fillna("").astype(str).str.strip()
    checks.append(_check("ranking_stock_id_nonempty", bool(ids.ne("").all()), "blocking", {"empty_count": int(ids.eq("").sum())}))
    checks.append(_check("ranking_stock_id_unique", bool(ids.is_unique), "blocking", {"duplicate_count": int(ids.duplicated().sum())}))
    if "rank" in frame.columns:
        ranks = pd.to_numeric(frame["rank"], errors="coerce")
        valid = not ranks.isna().any() and ranks.tolist() == list(range(1, len(frame) + 1))
        checks.append(_check("ranking_rank_sequence", valid, "blocking", {"expected": list(range(1, len(frame) + 1)), "actual": ranks.tolist()}))
    else:
        checks.append(_check("ranking_rank_column", False, "warning", {"missing": ["rank"]}))
    for column in CORE_SCORE_COLUMNS:
        if column not in frame.columns:
            checks.append(_check(f"score_column_{column}", False, "warning", {"missing": [column]}))
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        checks.append(_check(f"score_finite_{column}", bool(values.notna().all()), "blocking", {"invalid_count": int(values.isna().sum())}))
    return checks


def _reasons_evidence_check(frame: pd.DataFrame) -> dict[str, Any]:
    if "reasons" not in frame.columns:
        return _check("reasons_evidence_coverage", False, "warning", {"missing": ["reasons"]})
    reasons = frame["reasons"].fillna("").astype(str).str.strip()
    evidence_columns = [column for column in CORE_SCORE_COLUMNS if column in frame.columns]
    covered = reasons.ne("") & frame[evidence_columns].notna().any(axis=1) if evidence_columns else pd.Series(False, index=frame.index)
    return _check(
        "reasons_evidence_coverage",
        bool(covered.all()),
        "warning",
        {"uncovered_count": int((~covered).sum()), "evidence_columns": evidence_columns},
    )


def _stock_id_coverage_check(ranking: pd.DataFrame, source: pd.DataFrame, label: str) -> dict[str, Any]:
    if "stock_id" not in source.columns:
        return _check(f"{label}_stock_id_column", False, "warning", {"missing": ["stock_id"]})
    ranking_ids = set(ranking["stock_id"].fillna("").astype(str).str.strip())
    source_ids = set(source["stock_id"].fillna("").astype(str).str.strip())
    missing = sorted(item for item in ranking_ids - source_ids if item)
    return _check(f"{label}_ranking_coverage", not missing, "warning", {"missing_stock_ids": missing[:20], "missing_count": len(missing)})


def _check(name: str, ok: bool, severity: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "severity": severity, "details": details}


def _snapshot(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"audit input not found: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"provided": True, "path": str(path), "size_bytes": path.stat().st_size, "sha256": digest}


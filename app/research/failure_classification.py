"""Versioned research failure projection；不推論參數方向。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from app.research.contracts import content_hash
from app.research.eligibility import DEFAULT_POLICY as DEFAULT_ELIGIBILITY_POLICY, build_projection as build_eligibility
from app.research.observation_ingest import DEFAULT_LEDGER_PATH
from app.research.receipt_store import write_immutable_json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = PROJECT_ROOT / "config/research_failure_policy_v1.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "artifacts/autonomous_research/projections/failure"


DDL = """
CREATE TABLE IF NOT EXISTS failure_projection_runs (
 projection_id VARCHAR PRIMARY KEY, eligibility_projection_id VARCHAR NOT NULL,
 policy_version VARCHAR NOT NULL, policy_hash VARCHAR NOT NULL, status VARCHAR NOT NULL,
 output_artifact_path VARCHAR NOT NULL, canonical_payload_hash VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS failure_classifications (
 projection_id VARCHAR NOT NULL, subject_type VARCHAR NOT NULL, subject_id VARCHAR NOT NULL,
 classification_type VARCHAR NOT NULL, reason_code VARCHAR NOT NULL,
 threshold_id VARCHAR, observed_value DOUBLE, threshold_value DOUBLE, comparator VARCHAR,
 decision_input_hash VARCHAR NOT NULL,
 PRIMARY KEY (projection_id, subject_type, subject_id, reason_code)
);
"""


def load_policy(path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version", "policy_version", "negative_return_threshold",
        "max_drawdown_limit", "low_win_rate_threshold", "min_trade_count",
        "familywise_alpha", "min_robust_neighbor_pass_count",
        "robustness_requires_explicit_complete_evaluation",
    }
    if set(policy) != required or policy["schema_version"] != "research-failure-policy.v1":
        raise ValueError("INVALID_FAILURE_POLICY")
    numeric = {
        "negative_return_threshold": (-1.0, 1.0),
        "max_drawdown_limit": (-1.0, 0.0),
        "low_win_rate_threshold": (0.0, 1.0),
        "min_trade_count": (1, 1_000_000),
        "familywise_alpha": (0.0, 1.0),
        "min_robust_neighbor_pass_count": (0, 1_000_000),
    }
    for field, (lower, upper) in numeric.items():
        value = policy[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not lower <= value <= upper:
            raise ValueError(f"INVALID_FAILURE_POLICY_{field.upper()}")
    if policy["negative_return_threshold"] != 0.0 or policy["max_drawdown_limit"] >= 0:
        raise ValueError("INVALID_FAILURE_DIRECTION_SEMANTICS")
    if policy["robustness_requires_explicit_complete_evaluation"] is not True:
        raise ValueError("ROBUSTNESS_MUST_REQUIRE_COMPLETE_EVALUATION")
    return policy


def classify_metrics(row: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    def add(kind: str, reason: str, field: str | None = None, threshold: float | None = None, comparator: str | None = None) -> None:
        findings.append({
            "classification_type": kind, "reason_code": reason,
            "threshold_id": field, "observed_value": row.get(field) if field else None,
            "threshold_value": threshold, "comparator": comparator,
        })
    if row.get("total_return") is not None and row["total_return"] < policy["negative_return_threshold"]:
        add("STRATEGY_FAILURE", "NEGATIVE_RETURN", "total_return", policy["negative_return_threshold"], "LT")
    if row.get("max_drawdown") is not None and row["max_drawdown"] < policy["max_drawdown_limit"]:
        add("STRATEGY_FAILURE", "EXCESS_DRAWDOWN", "max_drawdown", policy["max_drawdown_limit"], "LT")
    trade_count = row.get("trade_count")
    if trade_count is not None and trade_count < policy["min_trade_count"]:
        add("EVIDENCE_STATE", "LOW_SAMPLE_SIZE", "trade_count", policy["min_trade_count"], "LT")
    elif row.get("win_rate") is not None and row["win_rate"] < policy["low_win_rate_threshold"]:
        add("STRATEGY_FAILURE", "LOW_WIN_RATE", "win_rate", policy["low_win_rate_threshold"], "LT")
    if row.get("p_value") is None:
        add("EVIDENCE_STATE", "STATISTICAL_EVIDENCE_UNAVAILABLE")
    elif row.get("research_stage") == "DEVELOPMENT_SCREEN":
        add("EVIDENCE_STATE", "FORMAL_SIGNIFICANCE_NOT_APPLICABLE")
    elif row["p_value"] > policy["familywise_alpha"]:
        add("STRATEGY_FAILURE", "STATISTICALLY_WEAK", "p_value", policy["familywise_alpha"], "GT")
    return findings


def _validator(payload: dict[str, Any]) -> list[str]:
    return [] if payload.get("schema_version") == "research-failure-projection.v1" else ["invalid schema"]


def build_projection(
    *, ledger_path: Path = DEFAULT_LEDGER_PATH, policy_path: Path = DEFAULT_POLICY,
    eligibility_policy_path: Path = DEFAULT_ELIGIBILITY_POLICY,
    eligibility_output_root: Path | None = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    eligibility = build_eligibility(
        ledger_path=ledger_path, policy_path=eligibility_policy_path,
        output_root=eligibility_output_root or output_root.parent / "eligibility",
    )
    policy = load_policy(policy_path)
    policy_hash = content_hash(policy)
    connection = duckdb.connect(str(ledger_path))
    try:
        connection.execute(DDL)
        findings: list[dict[str, Any]] = []
        for row in connection.execute(
            """
            SELECT o.observation_id,o.total_return,o.max_drawdown,o.win_rate,o.trade_count,
                   o.p_value,t.research_stage
            FROM observations o JOIN trial_specs t ON t.trial_spec_id=o.executed_trial_spec_id
            JOIN eligibility_decisions e ON e.subject_id=o.observation_id
             AND e.subject_type='OBSERVATION' AND e.projection_id=?
            WHERE e.eligibility_status='ADAPTIVE_ELIGIBLE'
            ORDER BY o.observation_id
            """, [eligibility["projection_id"]]
        ).fetchall():
            record = dict(zip(
                ("observation_id", "total_return", "max_drawdown", "win_rate", "trade_count", "p_value", "research_stage"), row
            ))
            for finding in classify_metrics(record, policy):
                findings.append({"subject_type": "OBSERVATION", "subject_id": record["observation_id"], **finding})
        for receipt_id, terminal, observation in connection.execute(
            "SELECT receipt_id,terminal_status,observation_status FROM run_receipts "
            "WHERE terminal_status!='SUCCEEDED' ORDER BY receipt_id"
        ).fetchall():
            reason = (
                "EXECUTION_CANCELLED" if terminal == "CANCELLED" else
                "EXECUTION_REJECTED" if terminal == "REJECTED_BEFORE_EXECUTION" else
                "PARTIAL_EXECUTION_FAILURE" if observation == "PARTIALLY_OBSERVED" else
                "EXECUTION_FACTS_UNKNOWN"
            )
            findings.append({
                "subject_type": "RUN_RECEIPT", "subject_id": receipt_id,
                "classification_type": "EXECUTION_FAILURE", "reason_code": reason,
                "threshold_id": None, "observed_value": None, "threshold_value": None,
                "comparator": None,
            })
        for finding in findings:
            finding["decision_input_hash"] = content_hash(finding)
        identity = {
            "projection_schema_version": "research-failure-projection.v1",
            "eligibility_projection_id": eligibility["projection_id"],
            "policy_version": policy["policy_version"], "policy_hash": policy_hash,
        }
        projection_id = content_hash(identity)
        counts = Counter(item["reason_code"] for item in findings)
        payload = {
            "schema_version": "research-failure-projection.v1", "projection_id": projection_id,
            **identity, "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "OK", "counts": dict(sorted(counts.items())), "classifications": findings,
        }
        target = output_root / f"{projection_id[7:]}.json"
        if target.is_file():
            payload = json.loads(target.read_text(encoding="utf-8"))
        result = write_immutable_json(target, payload, validator=_validator)
        connection.execute(
            "INSERT OR IGNORE INTO failure_projection_runs VALUES (?,?,?,?,?,?,?)",
            [projection_id, eligibility["projection_id"], policy["policy_version"], policy_hash,
             payload["status"], str(result.path), content_hash(payload)],
        )
        for finding in findings:
            connection.execute(
                "INSERT OR IGNORE INTO failure_classifications VALUES (?,?,?,?,?,?,?,?,?,?)",
                [projection_id, finding["subject_type"], finding["subject_id"],
                 finding["classification_type"], finding["reason_code"], finding["threshold_id"],
                 finding["observed_value"], finding["threshold_value"], finding["comparator"],
                 finding["decision_input_hash"]],
            )
        return payload
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    result = build_projection(ledger_path=args.ledger, policy_path=args.policy, output_root=args.output_root)
    print(json.dumps({key: result[key] for key in ("projection_id", "status", "counts")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

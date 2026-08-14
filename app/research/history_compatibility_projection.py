"""由 Research Ledger 重建 Fog Map 既有 run_history JSONL 相容投影。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from app.research.contracts import content_hash
from app.research.map_contract import combo_id
from app.research.observation_ingest import DEFAULT_CORPUS_ROOT, DEFAULT_LEDGER_PATH, ledger_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts/autonomous_research/run_history.jsonl"
POLICY_VERSION = "research-ledger-run-history-compatibility.v1"
LATEST_SELECTION_POLICY = "latest-finished-at-semantic-tiebreak.v1"


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return (
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n"
    ).encode("utf-8")


def _atomic_replace(path: Path, encoded: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


def _value(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value)


def _legacy_rows(connection: duckdb.DuckDBPyConnection, corpus_root: Path) -> list[dict[str, Any]]:
    artifact_ids = {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT source_artifact_id FROM migration_sources "
            "WHERE source_type='RUN_HISTORY_JSONL'"
        ).fetchall()
    }
    rows: list[dict[str, Any]] = []
    for artifact_id in sorted(artifact_ids):
        path = corpus_root / "source_corpus" / "sha256" / artifact_id.removeprefix("sha256:")
        if not path.is_file() or "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() != artifact_id:
            raise ValueError("LEGACY_HISTORY_CAS_MISMATCH")
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def _native_rows(connection: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    records = connection.execute(
        """
        SELECT o.receipt_id, o.scenario_id, o.total_return, o.max_drawdown, o.score,
               t.topic_id, t.parameters_json, t.execution_profile_json,
               r.completed_at, p.source_corpus_path, o.observation_id
        FROM observations o
        JOIN trial_specs t ON t.trial_spec_id = o.executed_trial_spec_id
        JOIN run_receipts r ON r.receipt_id = o.receipt_id
        LEFT JOIN observation_provenance p ON p.observation_id = o.observation_id
        ORDER BY o.receipt_id, t.topic_id, t.parameters_json, o.observation_id
        """
    ).fetchall()
    grouped: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = {}
    for record in records:
        parameters = json.loads(record[6])
        profile = json.loads(record[7])
        role = str(profile.get("variant_role") or "")
        key = (record[0], record[5], json.dumps(parameters, sort_keys=True))
        grouped.setdefault(key, {})[role] = {
            "scenario_id": record[1], "total_return": record[2], "max_drawdown": record[3],
            "score": record[4], "completed_at": record[8], "artifact_path": record[9],
            "observation_id": record[10], "parameters": parameters,
        }
    rows: list[dict[str, Any]] = []
    for (_, topic_id, _), roles in grouped.items():
        if set(roles) != {"baseline", "candidate"}:
            continue
        baseline, candidate = roles["baseline"], roles["candidate"]
        parameters = candidate["parameters"]
        dimensions = {
            "horizon": _value(parameters["horizon"]),
            "stop_loss": _value(parameters["stop_loss_pct"]),
            "take_profit": _value(parameters["take_profit_pct"]),
            "group_exposure": _value(parameters["max_group_exposure"]),
        }
        score_delta = float(candidate["score"] or 0) - float(baseline["score"] or 0)
        return_delta = float(candidate["total_return"] or 0) - float(baseline["total_return"] or 0)
        drawdown_delta = float(candidate["max_drawdown"] or 0) - float(baseline["max_drawdown"] or 0)
        decision = "KEEP_FOR_COMPONENT_FOLLOWUP" if score_delta > 0 and return_delta > 0 else "REJECT_FOR_NOW"
        rows.append({
            "schema_version": "research-run-history-jsonl.v1",
            "source": "research_ledger_compatibility_projection",
            "evidence_level": "scenario_exact",
            "combo_id": combo_id({"topic_id": topic_id}, dimensions),
            "topic_id": topic_id,
            "dimensions": dimensions,
            "status": "OK",
            "score_delta": round(score_delta, 6),
            "return_delta": round(return_delta, 6),
            "drawdown_delta": round(drawdown_delta, 6),
            "decision": decision,
            "insight_level": "next_stage" if decision.startswith("KEEP") else "rejected",
            "artifact_path": candidate["artifact_path"],
            "source_artifact_path": candidate["artifact_path"],
            "scenario_id": candidate["scenario_id"],
            "finished_at": candidate["completed_at"],
            "canonical_observation_id": candidate["observation_id"],
            "evidence_authority": "RESEARCH_LEDGER",
        })
    return rows


def _select_latest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同combo只保留最新完成事實；identity僅作同時間deterministic tie-break。"""
    selected: dict[str, tuple[tuple[str, str], dict[str, Any]]] = {}
    for row in rows:
        combo = str(row.get("combo_id") or "")
        if not combo:
            continue
        order = (
            str(row.get("finished_at") or ""),
            str(row.get("canonical_observation_id") or content_hash(row)),
        )
        if combo not in selected or order > selected[combo][0]:
            selected[combo] = (order, row)
    return [selected[key][1] for key in sorted(selected)]


def build_projection(
    *, ledger_path: Path, corpus_root: Path, output: Path, manifest_output: Path,
) -> dict[str, Any]:
    connection = duckdb.connect(str(ledger_path), read_only=True)
    try:
        snapshot = ledger_snapshot(connection)
        rows = _legacy_rows(connection, corpus_root)
        native = _native_rows(connection)
    finally:
        connection.close()
    final_rows = _select_latest_rows([*rows, *native])
    encoded = _jsonl_bytes(final_rows)
    _atomic_replace(output, encoded)
    manifest_identity = {
        "schema_version": "research-history-compatibility-projection.v1",
        "projection_policy_version": POLICY_VERSION,
        "latest_selection_policy_version": LATEST_SELECTION_POLICY,
        "ledger_snapshot_hash": snapshot["snapshot_hash"],
        "output_hash": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        "row_count": len(final_rows),
        "native_row_count": len(native),
    }
    manifest = {
        **manifest_identity,
        "projection_id": content_hash(manifest_identity),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_replace(
        manifest_output,
        (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER_PATH)
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--manifest-output", type=Path,
        default=DEFAULT_OUTPUT.with_name("run_history_projection_manifest.json"),
    )
    args = parser.parse_args()
    result = build_projection(
        ledger_path=args.ledger, corpus_root=args.corpus_root,
        output=args.output, manifest_output=args.manifest_output,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

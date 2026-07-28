#!/usr/bin/env python3
"""產生並獨立驗證 closed-regime runtime receipt v3。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.fog_authority_contracts import (
    AuthorityContractError,
    canonical_json_hash,
    read_json_authority,
    resolve_repo_path,
    sha256_file,
    validate_receipt_schema,
)
from scripts.fog_runtime_time_authority import (
    TimeAuthorityError,
    canonical_json_hash as time_contract_hash,
    derive_market_run_date,
    format_market_datetime,
    format_utc_z,
    load_policy,
    parse_utc_z,
    validate_run_context,
    verify_date_lineage,
    verify_freshness,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_AUTHORITY_PATH = "docs/architecture/fog_runtime_receipt_v3.schema.json"
REGIME_HISTORY_PATH = "artifacts/market_regime_history.json"
RESEARCH_CONTRACT_PATH = "config/regime_research_contract.json"
DAILY_ARTIFACT_TEMPLATE = (
    "artifacts/autonomous_research/autonomous_research_daily_quota_{run_date}.json"
)


class ClosedRegimeRuntimeError(ValueError):
    """Receipt producer 的 fail-closed 錯誤。"""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code


def _canonical_history(
    payload: dict[str, Any],
    *,
    market_run_date: str,
) -> dict[str, Any]:
    if payload.get("schema_version") != "market-regime-history.v2":
        raise ClosedRegimeRuntimeError(
            "REGIME_HISTORY_SCHEMA_REJECT",
            "schema_version 必須是 market-regime-history.v2",
        )
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ClosedRegimeRuntimeError("REGIME_HISTORY_SCHEMA_REJECT", "缺少 rows")
    eligible: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ClosedRegimeRuntimeError("REGIME_HISTORY_SCHEMA_REJECT", "row 非 object")
        trade_date = row.get("trade_date")
        as_of_date = row.get("as_of_date")
        if (
            not isinstance(trade_date, str)
            or as_of_date != trade_date
            or not isinstance(row.get("base_regime"), str)
            or not row["base_regime"]
            or not isinstance(row.get("family_tags"), list)
            or any(not isinstance(item, str) or not item for item in row["family_tags"])
            or len(row["family_tags"]) != len(set(row["family_tags"]))
        ):
            raise ClosedRegimeRuntimeError(
                "REGIME_HISTORY_SCHEMA_REJECT",
                "row 不符合 exact regime/as_of authority",
            )
        if trade_date <= market_run_date:
            eligible.append(row)
    if not eligible:
        raise ClosedRegimeRuntimeError(
            "REGIME_HISTORY_SOURCE_UNAVAILABLE",
            market_run_date,
        )
    row = sorted(eligible, key=lambda item: item["trade_date"])[-1]
    family_tags = sorted(row["family_tags"])
    return {
        "source_trade_date": row["trade_date"],
        "exact_regime": {
            "base_regime": row["base_regime"],
            "family_tags": family_tags,
            "identity_id": f"{row['base_regime']}|{'+'.join(family_tags)}",
        },
    }


def _canonical_daily(
    payload: dict[str, Any],
    *,
    market_run_date: str,
    canonical_source_trade_date: str,
) -> dict[str, Any]:
    if payload.get("schema_version") != "autonomous-research-run.v1":
        raise ClosedRegimeRuntimeError(
            "DAILY_ARTIFACT_SCHEMA_REJECT",
            "schema_version 必須是 autonomous-research-run.v1",
        )
    artifact_run_date = payload.get("run_date", payload.get("date"))
    if not isinstance(artifact_run_date, str):
        raise ClosedRegimeRuntimeError(
            "DAILY_ARTIFACT_SCHEMA_REJECT",
            "缺少 run_date/date identity",
        )
    source_lineage = (
        payload.get("source_lineage")
        if isinstance(payload.get("source_lineage"), dict)
        else {}
    )
    daily_source_date = payload.get(
        "source_date",
        payload.get(
            "daily_source_date",
            source_lineage.get("daily_source_date", canonical_source_trade_date),
        ),
    )
    if not isinstance(daily_source_date, str):
        raise ClosedRegimeRuntimeError(
            "DAILY_ARTIFACT_SCHEMA_REJECT",
            "缺少 daily source lineage",
        )
    topic_runs = payload.get("topic_runs")
    if not isinstance(topic_runs, list):
        raise ClosedRegimeRuntimeError(
            "DAILY_ARTIFACT_SCHEMA_REJECT",
            "topic_runs 非 array",
        )
    lineage: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for run in topic_runs:
        topic = run.get("topic") if isinstance(run, dict) else None
        outcome = run.get("outcome") if isinstance(run, dict) else None
        topic_id = topic.get("topic_id") if isinstance(topic, dict) else None
        status = run.get("status") if isinstance(run, dict) else None
        decision = outcome.get("decision") if isinstance(outcome, dict) else None
        if (
            not isinstance(topic_id, str)
            or not topic_id
            or topic_id in seen_ids
            or not isinstance(status, str)
            or not status
            or (decision is not None and not isinstance(decision, str))
        ):
            raise ClosedRegimeRuntimeError(
                "DAILY_ARTIFACT_SCHEMA_REJECT",
                "topic run lineage 無法 canonicalize",
            )
        seen_ids.add(topic_id)
        lineage.append(
            {"topic_id": topic_id, "status": status, "decision": decision}
        )
    lineage.sort(key=lambda item: item["topic_id"])
    return {
        "artifact_run_date": artifact_run_date,
        "daily_source_date": daily_source_date,
        "topic_run_lineage": lineage,
        "topic_run_lineage_sha256": canonical_json_hash(lineage),
        "market_run_date": market_run_date,
    }


def _authority_paths(
    *,
    market_run_date: str,
    regime_history_path: str | None,
    daily_artifact_path: str | None,
    research_contract_path: str | None,
) -> tuple[str, str, str]:
    return (
        regime_history_path or REGIME_HISTORY_PATH,
        daily_artifact_path
        or DAILY_ARTIFACT_TEMPLATE.format(run_date=market_run_date),
        research_contract_path or RESEARCH_CONTRACT_PATH,
    )


def build_receipt(
    *,
    run_context: dict[str, Any],
    generated_at_utc: str | datetime,
    project_root: str | Path = PROJECT_ROOT,
    regime_history_path: str | None = None,
    daily_artifact_path: str | None = None,
    research_contract_path: str | None = None,
) -> dict[str, Any]:
    context_result = validate_run_context(run_context, project_root=project_root)
    if not context_result["ok"]:
        raise ClosedRegimeRuntimeError(
            "RUN_CONTEXT_AUTHORITY_MISMATCH",
            str(context_result["reason_codes"]),
        )
    generated = parse_utc_z(generated_at_utc)
    market_run_date = run_context["market_run_date"]
    generated_market_run_date = derive_market_run_date(generated)
    if generated_market_run_date != market_run_date:
        raise ClosedRegimeRuntimeError(
            "MARKET_DATE_ROLLOVER",
            f"{market_run_date} -> {generated_market_run_date}",
        )
    history_path, daily_path, contract_path = _authority_paths(
        market_run_date=market_run_date,
        regime_history_path=regime_history_path,
        daily_artifact_path=daily_artifact_path,
        research_contract_path=research_contract_path,
    )
    try:
        history_payload = read_json_authority(project_root, history_path)
        daily_payload = read_json_authority(project_root, daily_path)
        contract_payload = read_json_authority(project_root, contract_path)
        history_file = resolve_repo_path(project_root, history_path)
        daily_file = resolve_repo_path(project_root, daily_path)
        contract_file = resolve_repo_path(project_root, contract_path)
    except AuthorityContractError as error:
        raise ClosedRegimeRuntimeError(error.reason_code, str(error)) from error
    history = _canonical_history(history_payload, market_run_date=market_run_date)
    daily = _canonical_daily(
        daily_payload,
        market_run_date=market_run_date,
        canonical_source_trade_date=history["source_trade_date"],
    )
    lineage = verify_date_lineage(
        market_run_date=market_run_date,
        artifact_run_date=daily["artifact_run_date"],
        daily_source_date=daily["daily_source_date"],
        source_trade_date=history["source_trade_date"],
        canonical_artifact_run_date=market_run_date,
        canonical_daily_source_date=daily["daily_source_date"],
        canonical_source_trade_date=history["source_trade_date"],
    )
    if not lineage["ok"]:
        raise ClosedRegimeRuntimeError(
            lineage["reason_codes"][0],
            str(lineage["reason_codes"]),
        )
    contract_schema = contract_payload.get("schema_version")
    if not isinstance(contract_schema, str) or not contract_schema:
        raise ClosedRegimeRuntimeError(
            "RESEARCH_CONTRACT_SCHEMA_REJECT",
            contract_path,
        )
    policy = load_policy(project_root=project_root)
    receipt = {
        "schema_version": "closed-regime-runtime-receipt.v3",
        "status": "OK",
        "closed_regime_research": True,
        "schema_authority": {
            "path": SCHEMA_AUTHORITY_PATH,
            "schema_version": "closed-regime-runtime-receipt.v3",
        },
        "time_authority": {
            "schema_version": policy["schema_version"],
            "contract_hash": time_contract_hash(policy),
            "market_id": policy["market_id"],
            "market_timezone": policy["market_timezone"],
            "run_context_created_at_utc": run_context[
                "run_context_created_at_utc"
            ],
            "run_context_market_datetime": run_context[
                "run_context_market_datetime"
            ],
            "market_run_date": market_run_date,
            "generated_at_utc": format_utc_z(generated),
            "generated_market_datetime": format_market_datetime(generated),
        },
        "market_regime_history": {
            "path": history_path,
            "schema_version": "market-regime-history.v2",
            "sha256": sha256_file(history_file),
            "source_trade_date": history["source_trade_date"],
        },
        "daily_research_artifact": {
            "path": daily_path,
            "schema_version": "autonomous-research-run.v1",
            "sha256": sha256_file(daily_file),
            "artifact_run_date": daily["artifact_run_date"],
            "daily_source_date": daily["daily_source_date"],
        },
        "queue_owner": "fog_worker",
        "runner_identity": "scripts/run_daily_research_quota.sh",
        "research_contract": {
            "path": contract_path,
            "schema_version": contract_schema,
            "sha256": sha256_file(contract_file),
        },
        "exact_regime": history["exact_regime"],
        "state_transition": {
            "from": "VERIFIED_HISTORY",
            "to": "CLOSED_RESEARCH_COMPLETED",
        },
        "topic_run_lineage": daily["topic_run_lineage"],
        "topic_run_lineage_sha256": daily["topic_run_lineage_sha256"],
        "production_impact": "NO_PRODUCTION_CHANGE",
    }
    schema_result = validate_receipt_schema(receipt, root=project_root)
    if not schema_result["ok"]:
        raise ClosedRegimeRuntimeError(
            "RECEIPT_SCHEMA_REJECT",
            str(schema_result["errors"]),
        )
    return receipt


def verify_receipt(
    receipt: object,
    *,
    project_root: str | Path = PROJECT_ROOT,
    verification_time_utc: str | datetime | None = None,
) -> dict[str, Any]:
    verification = verification_time_utc or format_utc_z(datetime.now(UTC))
    result: dict[str, Any] = {
        "ok": False,
        "reason_codes": [],
        "verification_time_utc": None,
        "receipt_age_seconds": None,
        "computed_market_run_date": None,
        "contract_hash_expected": None,
        "contract_hash_observed": None,
        "scheduler_host_timezone_diagnostic": datetime.now().astimezone().tzname()
        or "UNKNOWN",
    }
    schema_result = validate_receipt_schema(receipt, root=project_root)
    if not schema_result["ok"]:
        result["reason_codes"] = schema_result["reason_codes"]
        return result
    assert isinstance(receipt, dict)
    reason_codes: list[str] = []
    try:
        policy = load_policy(project_root=project_root)
        time_claim = receipt["time_authority"]
        result["contract_hash_expected"] = time_contract_hash(policy)
        result["contract_hash_observed"] = time_claim["contract_hash"]
        if result["contract_hash_observed"] != result["contract_hash_expected"]:
            reason_codes.append("TIME_CONTRACT_HASH_MISMATCH")
        context_market_date = derive_market_run_date(
            time_claim["run_context_created_at_utc"],
            policy,
        )
        generated_market_date = derive_market_run_date(
            time_claim["generated_at_utc"],
            policy,
        )
        result["computed_market_run_date"] = generated_market_date
        if (
            context_market_date != time_claim["market_run_date"]
            or generated_market_date != time_claim["market_run_date"]
            or time_claim["run_context_market_datetime"]
            != format_market_datetime(time_claim["run_context_created_at_utc"])
            or time_claim["generated_market_datetime"]
            != format_market_datetime(time_claim["generated_at_utc"])
        ):
            reason_codes.append("MARKET_DATE_MISMATCH")
        freshness = verify_freshness(
            time_claim["generated_at_utc"],
            verification,
            policy=policy,
        )
        result["verification_time_utc"] = freshness["verification_time_utc"]
        result["receipt_age_seconds"] = freshness["receipt_age_seconds"]
        reason_codes.extend(freshness["reason_codes"])
        market_run_date = time_claim["market_run_date"]
        expected_history, expected_daily, expected_contract = _authority_paths(
            market_run_date=market_run_date,
            regime_history_path=None,
            daily_artifact_path=None,
            research_contract_path=None,
        )
        observed_paths = (
            receipt["market_regime_history"]["path"],
            receipt["daily_research_artifact"]["path"],
            receipt["research_contract"]["path"],
        )
        if observed_paths != (
            expected_history,
            expected_daily,
            expected_contract,
        ):
            reason_codes.append("SOURCE_PATH_DRIFT")
        else:
            history_payload = read_json_authority(project_root, expected_history)
            daily_payload = read_json_authority(project_root, expected_daily)
            contract_payload = read_json_authority(project_root, expected_contract)
            history_file = resolve_repo_path(project_root, expected_history)
            daily_file = resolve_repo_path(project_root, expected_daily)
            contract_file = resolve_repo_path(project_root, expected_contract)
            history = _canonical_history(
                history_payload,
                market_run_date=market_run_date,
            )
            daily = _canonical_daily(
                daily_payload,
                market_run_date=market_run_date,
                canonical_source_trade_date=history["source_trade_date"],
            )
            hashes = {
                "market_regime_history": sha256_file(history_file),
                "daily_research_artifact": sha256_file(daily_file),
                "research_contract": sha256_file(contract_file),
            }
            for section, expected_hash in hashes.items():
                if receipt[section]["sha256"] != expected_hash:
                    reason_codes.append("SOURCE_HASH_DRIFT")
            if receipt["market_regime_history"]["schema_version"] != (
                history_payload.get("schema_version")
            ):
                reason_codes.append("SOURCE_SCHEMA_DRIFT")
            if receipt["daily_research_artifact"]["schema_version"] != (
                daily_payload.get("schema_version")
            ):
                reason_codes.append("SOURCE_SCHEMA_DRIFT")
            if receipt["research_contract"]["schema_version"] != (
                contract_payload.get("schema_version")
            ):
                reason_codes.append("SOURCE_SCHEMA_DRIFT")
            lineage = verify_date_lineage(
                market_run_date=market_run_date,
                artifact_run_date=receipt["daily_research_artifact"][
                    "artifact_run_date"
                ],
                daily_source_date=receipt["daily_research_artifact"][
                    "daily_source_date"
                ],
                source_trade_date=receipt["market_regime_history"][
                    "source_trade_date"
                ],
                canonical_artifact_run_date=daily["artifact_run_date"],
                canonical_daily_source_date=daily["daily_source_date"],
                canonical_source_trade_date=history["source_trade_date"],
            )
            reason_codes.extend(lineage["reason_codes"])
            if receipt["exact_regime"] != history["exact_regime"]:
                reason_codes.append("EXACT_REGIME_MISMATCH")
            if receipt["topic_run_lineage"] != daily["topic_run_lineage"]:
                reason_codes.append("TOPIC_RUN_LINEAGE_MISMATCH")
            if receipt["topic_run_lineage_sha256"] != daily[
                "topic_run_lineage_sha256"
            ]:
                reason_codes.append("TOPIC_RUN_LINEAGE_HASH_MISMATCH")
    except (
        AuthorityContractError,
        ClosedRegimeRuntimeError,
        TimeAuthorityError,
        KeyError,
        TypeError,
    ) as error:
        reason_codes.append(
            error.reason_code
            if hasattr(error, "reason_code")
            else "RECEIPT_AUTHORITY_REJECT"
        )
    result["reason_codes"] = sorted(set(reason_codes))
    result["ok"] = not result["reason_codes"]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="build or verify closed-regime runtime receipt v3"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--receipt", help="要驗證的 receipt repo-relative path")
    mode.add_argument(
        "--build-receipt",
        action="store_true",
        help="以 canonical artifacts 產生 deterministic v3 receipt",
    )
    parser.add_argument("--run-context", help="immutable run context repo-relative path")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = resolve_repo_path(PROJECT_ROOT, args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.build_receipt:
        if not args.run_context:
            raise SystemExit("--build-receipt 必須提供 --run-context")
        context = read_json_authority(PROJECT_ROOT, args.run_context)
        receipt = build_receipt(
            run_context=context,
            generated_at_utc=datetime.now(UTC),
        )
        encoded = json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False)
        output.write_text(encoded + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": "OK",
                    "schema_version": receipt["schema_version"],
                    "output": args.output,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    receipt_path = resolve_repo_path(PROJECT_ROOT, str(args.receipt))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    result = verify_receipt(receipt)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

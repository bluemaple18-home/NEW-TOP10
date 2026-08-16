"""稽核歷史 ranking 是否具備同一 artifact identity 的同期 provenance。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from app.research.contracts import canonical_json_bytes, content_hash


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "ranking-provenance-admission.v1"
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-RANKING-PROVENANCE-ADMISSION-AUDIT-V1/admission.json"
)
FEASIBILITY_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1/feasibility.json"
)
AVAILABILITY_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1/availability_audit.json"
)
ALLOWED_STATUSES = {
    "ADMITTED_RANKING_PROVENANCE_COMPLETE",
    "NO_GO_RANKING_PROVENANCE_INCOMPLETE",
    "BLOCKED_EVIDENCE_CONFLICT",
}
LINEAGE_FIELDS = (
    "ranking_artifact",
    "producer",
    "model",
    "config",
    "universe",
    "top_n_policy",
)
FORBIDDEN_KEY_TOKENS = (
    "outcome",
    "return",
    "price",
    "ohlc",
    "pnl",
    "win_rate",
    "winrate",
    "sharpe",
    "alpha",
    "target",
)
FALLBACK_TOKENS = ("latest", "default", "fallback")


class RankingProvenanceAdmissionError(RuntimeError):
    """ranking provenance 的輸入、authority 或 evidence 不合法。"""


def _safe_path(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in PurePosixPath(relative.as_posix()).parts:
        raise RankingProvenanceAdmissionError("PATH_ESCAPE")
    lexical_root = root.absolute()
    if lexical_root.is_symlink() or lexical_root.resolve(strict=True) != lexical_root:
        raise RankingProvenanceAdmissionError("ROOT_SYMLINK")
    cursor = lexical_root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise RankingProvenanceAdmissionError("PATH_SYMLINK")
    try:
        cursor.resolve(strict=False).relative_to(lexical_root)
    except ValueError as error:
        raise RankingProvenanceAdmissionError("PATH_ESCAPE") from error
    return cursor


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _committed_json(root: Path, relative: Path) -> tuple[dict[str, Any], dict[str, str]]:
    path = _safe_path(root, relative)
    try:
        working = path.read_bytes()
    except OSError as error:
        raise RankingProvenanceAdmissionError(
            f"SOURCE_UNREADABLE:{relative.as_posix()}"
        ) from error
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{relative.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RankingProvenanceAdmissionError(
            f"SOURCE_NOT_COMMITTED:{relative.as_posix()}"
        )
    if result.stdout != working:
        raise RankingProvenanceAdmissionError(
            f"SOURCE_WORKTREE_DRIFT:{relative.as_posix()}"
        )
    try:
        payload = json.loads(working)
    except json.JSONDecodeError as error:
        raise RankingProvenanceAdmissionError(
            f"SOURCE_INVALID_JSON:{relative.as_posix()}"
        ) from error
    if not isinstance(payload, dict):
        raise RankingProvenanceAdmissionError(
            f"SOURCE_NOT_OBJECT:{relative.as_posix()}"
        )
    return payload, {
        "path": relative.as_posix(),
        "sha256": _sha256(working),
        "commit_status": "MATCHED",
    }


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_").replace(" ", "_")
            if normalized in {
                "outcome_access_allowed",
                "sealed_outcome_access_allowed",
                "outcome_accessed",
            } and child is False:
                continue
            if any(token in normalized for token in FORBIDDEN_KEY_TOKENS):
                return True
            if _contains_forbidden_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 71 and value.startswith("sha256:") and all(
        character in "0123456789abcdef" for character in value[7:]
    )


def _safe_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not value.startswith("/")


def _availability_artifacts(payload: Mapping[str, Any]) -> tuple[dict[tuple[str, str], dict[str, str]], list[str]]:
    sources = payload.get("sources")
    roots = sources.get("ranking_roots") if isinstance(sources, Mapping) else None
    if not isinstance(roots, Mapping) or not roots:
        raise RankingProvenanceAdmissionError("RANKING_ROOTS_MISSING")
    artifacts: dict[tuple[str, str], dict[str, str]] = {}
    errors: list[str] = []
    for scenario, root in sorted(roots.items()):
        if not isinstance(root, Mapping) or root.get("status") != "AVAILABLE":
            raise RankingProvenanceAdmissionError("RANKING_ROOT_INVALID")
        base_path = root.get("path")
        dates = root.get("ranking_dates")
        files = root.get("files")
        if not _safe_text(base_path) or not isinstance(dates, list) or not isinstance(files, list):
            raise RankingProvenanceAdmissionError("RANKING_ROOT_INVALID")
        by_date: dict[str, str] = {}
        for file_record in files:
            if not isinstance(file_record, Mapping):
                continue
            filename = file_record.get("path")
            digest = file_record.get("sha256")
            if not isinstance(filename, str) or not filename.startswith("ranking_") or not filename.endswith(".csv"):
                continue
            date = filename.removeprefix("ranking_").removesuffix(".csv")
            if date in by_date or not _hash(digest):
                errors.append("AVAILABILITY_ARTIFACT_ALIAS_OR_HASH_CONFLICT")
                continue
            by_date[date] = digest
        if sorted(by_date) != sorted(str(item) for item in dates):
            errors.append("AVAILABILITY_ARTIFACT_DATE_CONFLICT")
        for date, digest in by_date.items():
            key = (str(scenario), date)
            if key in artifacts:
                errors.append("AVAILABILITY_SCENARIO_DATE_ALIAS")
                continue
            artifacts[key] = {"path": f"{base_path}/{('ranking_' + date + '.csv')}", "sha256": digest}
    return artifacts, sorted(set(errors))


def _missing_field(reason_code: str) -> dict[str, str]:
    return {"status": "MISSING", "reason_code": reason_code}


def _proven_field(value: Mapping[str, Any]) -> dict[str, Any]:
    return {"status": "PROVEN", "evidence": dict(value)}


def _receipt_fields(receipt: Mapping[str, Any], artifact: Mapping[str, str]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """只接受明示為同期、同 artifact identity 的 immutable per-date receipt。"""

    if _contains_forbidden_key(receipt):
        return {}, ["OUTCOME_KEY_FORBIDDEN"]
    if receipt.get("contemporaneous_at_generation") is not True:
        return {}, ["RECEIPT_NOT_CONTEMPORANEOUS"]
    if receipt.get("immutable_committed_receipt") is not True:
        return {}, ["RECEIPT_NOT_IMMUTABLE"]
    if not _safe_text(receipt.get("receipt_identity")) or not _safe_text(receipt.get("receipt_commit")):
        return {}, ["RECEIPT_IDENTITY_OR_COMMIT_MISSING"]
    observed_artifact = receipt.get("ranking_artifact")
    if not isinstance(observed_artifact, Mapping):
        return {}, ["RANKING_ARTIFACT_RECEIPT_MISSING"]
    if observed_artifact.get("path") != artifact["path"] or observed_artifact.get("sha256") != artifact["sha256"]:
        return {}, ["RECEIPT_ARTIFACT_IDENTITY_CONFLICT"]
    values: dict[str, Mapping[str, Any]] = {
        "ranking_artifact": observed_artifact,
        "producer": receipt.get("producer") if isinstance(receipt.get("producer"), Mapping) else {},
        "model": receipt.get("model") if isinstance(receipt.get("model"), Mapping) else {},
        "config": receipt.get("config") if isinstance(receipt.get("config"), Mapping) else {},
        "universe": receipt.get("universe") if isinstance(receipt.get("universe"), Mapping) else {},
        "top_n_policy": receipt.get("top_n_policy") if isinstance(receipt.get("top_n_policy"), Mapping) else {},
    }
    required = {
        "ranking_artifact": ("path", "sha256"),
        "producer": ("entrypoint", "source_commit", "source_sha256"),
        "model": ("artifact_path", "version", "sha256"),
        "config": ("sha256",),
        "universe": ("snapshot_path", "sha256"),
        "top_n_policy": ("top_n", "sort_policy", "tie_break_policy"),
    }
    fields: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for name in LINEAGE_FIELDS:
        value = values[name]
        if not value or any(not _safe_text(value.get(key)) and not isinstance(value.get(key), int) for key in required[name]):
            fields[name] = _missing_field(f"{name.upper()}_RECEIPT_FIELD_MISSING")
            continue
        if name in {"ranking_artifact", "producer", "model", "config", "universe"}:
            for key, item in value.items():
                if key.endswith("sha256") or key == "sha256":
                    if not _hash(item):
                        errors.append(f"{name.upper()}_HASH_INVALID")
        fields[name] = _proven_field(value)
    return fields, errors


def evaluate_admission(
    availability_payload: Mapping[str, Any],
    feasibility_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """將現有 committed evidence 轉為逐 scenario/date 的 fail-closed admission。"""

    if _contains_forbidden_key(availability_payload) or _contains_forbidden_key(feasibility_payload):
        raise RankingProvenanceAdmissionError("OUTCOME_KEY_FORBIDDEN")
    artifacts, conflicts = _availability_artifacts(availability_payload)
    feasibility_sources = feasibility_payload.get("sources")
    manifest = feasibility_sources.get("ranking_manifest") if isinstance(feasibility_sources, Mapping) else None
    if not isinstance(manifest, Mapping):
        raise RankingProvenanceAdmissionError("FEASIBILITY_RANKING_MANIFEST_MISSING")
    scenario_manifest = manifest.get("scenarios")
    if not isinstance(scenario_manifest, Mapping):
        raise RankingProvenanceAdmissionError("FEASIBILITY_SCENARIOS_MISSING")
    available_scenarios = {scenario for scenario, _ in artifacts}
    if set(str(item) for item in scenario_manifest) != available_scenarios:
        conflicts.append("FEASIBILITY_AVAILABILITY_SCENARIO_CONFLICT")

    raw_receipts = availability_payload.get("contemporaneous_ranking_provenance_receipts", [])
    if raw_receipts is None:
        raw_receipts = []
    if not isinstance(raw_receipts, list) or not all(isinstance(item, Mapping) for item in raw_receipts):
        conflicts.append("RECEIPT_COLLECTION_INVALID")
        raw_receipts = []
    receipt_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    for receipt in raw_receipts:
        scenario = receipt.get("scenario")
        date = receipt.get("ranking_date")
        key = (str(scenario), str(date))
        if not _safe_text(scenario) or not _safe_text(date) or key not in artifacts or key in receipt_by_key:
            conflicts.append("RECEIPT_SCENARIO_DATE_ALIAS_OR_UNKNOWN")
            continue
        receipt_by_key[key] = receipt

    records: list[dict[str, Any]] = []
    missing_count = 0
    for scenario, date in sorted(artifacts):
        artifact = artifacts[(scenario, date)]
        receipt = receipt_by_key.get((scenario, date))
        if receipt is None:
            fields = {
                name: _missing_field(
                    "CURRENT_AVAILABILITY_HASH_NOT_CONTEMPORANEOUS_PROVENANCE"
                    if name == "ranking_artifact"
                    else "CONTEMPORANEOUS_IMMUTABLE_PER_DATE_RECEIPT_MISSING"
                )
                for name in LINEAGE_FIELDS
            }
        else:
            fields, receipt_errors = _receipt_fields(receipt, artifact)
            if receipt_errors:
                conflicts.extend(receipt_errors)
                fields = {
                    name: _missing_field("RECEIPT_CONFLICT_OR_INVALID")
                    for name in LINEAGE_FIELDS
                }
        missing_count += sum(field["status"] != "PROVEN" for field in fields.values())
        records.append(
            {
                "scenario": scenario,
                "ranking_date": date,
                "artifact_identity": artifact,
                "lineage": fields,
                "admission": "ADMIT" if all(field["status"] == "PROVEN" for field in fields.values()) else "REJECT",
            }
        )
    if conflicts:
        status = "BLOCKED_EVIDENCE_CONFLICT"
    elif missing_count:
        status = "NO_GO_RANKING_PROVENANCE_INCOMPLETE"
    else:
        status = "ADMITTED_RANKING_PROVENANCE_COMPLETE"
    return {
        "status": status,
        "reason_codes": sorted(set(conflicts)) if conflicts else (
            [] if not missing_count else ["CONTEMPORANEOUS_RANKING_PROVENANCE_MISSING"]
        ),
        "record_count": len(records),
        "missing_lineage_field_count": missing_count,
        "records": records,
    }


def build_audit(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    root = project_root.resolve()
    availability, availability_source = _committed_json(root, AVAILABILITY_RELATIVE)
    feasibility, feasibility_source = _committed_json(root, FEASIBILITY_RELATIVE)
    decision = evaluate_admission(availability, feasibility)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "audit_id": "",
        **decision,
        "contract": {
            "research_only": True,
            "network_requests": 0,
            "raw_data_writes": 0,
            "outcome_access_allowed": False,
            "replay_allowed": False,
            "runtime_change_allowed": False,
            "current_hash_backfill_allowed": False,
            "latest_or_default_fallback_allowed": False,
        },
        "sources": {
            "availability": availability_source,
            "feasibility": feasibility_source,
        },
    }
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})
    return payload


def _strings(value: Any):
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)
    elif isinstance(value, str):
        yield value


def _contains_fallback_reference(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_").replace(" ", "_")
            if normalized == "latest_or_default_fallback_allowed" and child is False:
                continue
            if any(token in normalized for token in FALLBACK_TOKENS):
                return True
            if _contains_fallback_reference(child):
                return True
    elif isinstance(value, list):
        return any(_contains_fallback_reference(item) for item in value)
    elif isinstance(value, str):
        normalized = value.lower().replace("-", "_").replace(" ", "_")
        return normalized in {"latest", "default", "fallback"} or normalized.startswith("latest_")
    return False


def validate_audit(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_INVALID")
    status = payload.get("status")
    if status not in ALLOWED_STATUSES:
        errors.append("STATUS_INVALID")
    if payload.get("audit_id") != content_hash(payload, omit={"audit_id"}):
        errors.append("AUDIT_ID_MISMATCH")
    contract = payload.get("contract")
    expected_contract = {
        "research_only": True,
        "network_requests": 0,
        "raw_data_writes": 0,
        "outcome_access_allowed": False,
        "replay_allowed": False,
        "runtime_change_allowed": False,
        "current_hash_backfill_allowed": False,
        "latest_or_default_fallback_allowed": False,
    }
    if contract != expected_contract:
        errors.append("CONTRACT_INVALID")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        errors.append("RECORDS_INVALID")
        records = []
    identities: set[tuple[str, str]] = set()
    missing = 0
    conflicts = False
    for record in records:
        if not isinstance(record, Mapping):
            errors.append("RECORD_INVALID")
            continue
        key = (str(record.get("scenario") or ""), str(record.get("ranking_date") or ""))
        if not all(key) or key in identities:
            errors.append("SCENARIO_DATE_ALIAS")
        identities.add(key)
        artifact = record.get("artifact_identity")
        lineage = record.get("lineage")
        if not isinstance(artifact, Mapping) or not _safe_text(artifact.get("path")) or not _hash(artifact.get("sha256")):
            errors.append("ARTIFACT_IDENTITY_INVALID")
        if not isinstance(lineage, Mapping) or set(lineage) != set(LINEAGE_FIELDS):
            errors.append("LINEAGE_FIELDS_INVALID")
            continue
        proven = True
        for field in LINEAGE_FIELDS:
            item = lineage.get(field)
            if not isinstance(item, Mapping) or item.get("status") not in {"PROVEN", "MISSING", "CONFLICT"}:
                errors.append("LINEAGE_STATUS_INVALID")
                proven = False
                continue
            if item.get("status") != "PROVEN":
                missing += 1
                proven = False
                conflicts = conflicts or item.get("status") == "CONFLICT"
        if record.get("admission") != ("ADMIT" if proven else "REJECT"):
            errors.append("FALSE_ADMISSION")
    if payload.get("record_count") != len(records) or payload.get("missing_lineage_field_count") != missing:
        errors.append("RECORD_COUNT_MISMATCH")
    if status == "ADMITTED_RANKING_PROVENANCE_COMPLETE" and (missing or conflicts):
        errors.append("FALSE_ADMISSION")
    if status == "NO_GO_RANKING_PROVENANCE_INCOMPLETE" and not missing:
        errors.append("FALSE_NO_GO")
    if status == "BLOCKED_EVIDENCE_CONFLICT" and not (conflicts or payload.get("reason_codes")):
        errors.append("FALSE_BLOCKED")
    if _contains_fallback_reference(payload):
        errors.append("LATEST_OR_DEFAULT_FALLBACK_FORBIDDEN")
    if _contains_forbidden_key(payload):
        errors.append("OUTCOME_KEY_FORBIDDEN")
    if any(value.startswith("/") for value in _strings(payload)):
        errors.append("ABSOLUTE_PATH_FORBIDDEN")
    if any(value in {"generated_at", "timestamp", "mtime"} for value in _strings(payload)):
        errors.append("NONDETERMINISTIC_FIELD_FORBIDDEN")
    return sorted(set(errors))


def encode_audit(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _evidence_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute() or path.as_posix() != EVIDENCE_RELATIVE.as_posix():
        raise RankingProvenanceAdmissionError("EVIDENCE_PATH_NOT_CANONICAL")
    return _safe_path(project_root, path)


def write_audit(path: Path) -> dict[str, Any]:
    payload = build_audit()
    errors = validate_audit(payload)
    if errors:
        raise RankingProvenanceAdmissionError("AUDIT_VALIDATION_FAILED:" + ",".join(errors))
    target = _evidence_path(path, PROJECT_ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode_audit(payload))
    return payload


def verify_audit(path: Path) -> dict[str, Any]:
    try:
        target = _evidence_path(path, PROJECT_ROOT)
        raw = target.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RankingProvenanceAdmissionError("EVIDENCE_NOT_OBJECT")
        errors = validate_audit(payload)
        if raw != encode_audit(payload):
            errors.append("NON_CANONICAL_BYTES")
        if payload != build_audit():
            errors.append("AUDIT_RECOMPUTE_MISMATCH")
    except (OSError, json.JSONDecodeError, RankingProvenanceAdmissionError) as error:
        return {"status": "FAIL", "errors": [str(error)]}
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors))}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="audit ranking provenance admission")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = verify_audit(args.verify) if args.verify else write_audit(args.output)
    except RankingProvenanceAdmissionError as error:
        print(json.dumps({"status": "FAIL", "errors": [str(error)]}, sort_keys=True))
        return 2
    print(json.dumps(result if args.verify else {"status": result["status"], "audit_id": result["audit_id"]}, sort_keys=True))
    return 0 if not args.verify or result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

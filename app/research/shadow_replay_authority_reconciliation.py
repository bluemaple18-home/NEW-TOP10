"""以 committed evidence chain 驗證 ignored replay authority snapshot。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from app.research import shadow_replay_availability as availability
from app.research import shadow_replay_coverage_plan as coverage
from app.research.contracts import canonical_json_bytes, content_hash
from app.research.shadow_plan_proposal import snapshot_protected_surfaces


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "shadow-replay-authority-reconciliation.v1"
EVIDENCE_RELATIVE = Path(
    "docs/evidence/CARD-NEW-TOP10-AUTHORITY-SNAPSHOT-RECONCILIATION-V1/"
    "reconciliation.json"
)
PLAN_RELATIVE = coverage.EVIDENCE_RELATIVE
AUDIT_RELATIVE = availability.EVIDENCE_RELATIVE
ALLOWED_STATUSES = {
    "READY_FOR_FEASIBILITY_AUDIT",
    "BLOCKED_AUTHORITY_CONFLICT",
}


class AuthorityReconciliationError(RuntimeError):
    """表示 committed chain 或 runtime snapshot 不合法。"""


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise AuthorityReconciliationError("SOURCE_MISSING_OR_SYMLINK")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _safe_path(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in PurePosixPath(relative.as_posix()).parts:
        raise AuthorityReconciliationError("PATH_ESCAPE")
    lexical_root = root.absolute()
    if lexical_root.is_symlink() or lexical_root.resolve(strict=True) != lexical_root:
        raise AuthorityReconciliationError("SOURCE_SYMLINK")
    cursor = lexical_root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise AuthorityReconciliationError("SOURCE_SYMLINK")
    try:
        cursor.resolve(strict=False).relative_to(lexical_root)
    except ValueError as error:
        raise AuthorityReconciliationError("PATH_ESCAPE") from error
    return cursor


def _committed_json(root: Path, relative: Path) -> tuple[dict[str, Any], dict[str, str]]:
    path = _safe_path(root, relative)
    try:
        working_bytes = path.read_bytes()
        result = subprocess.run(
            ["git", "-C", str(root), "show", f"HEAD:{relative.as_posix()}"],
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise AuthorityReconciliationError("COMMITTED_SOURCE_UNREADABLE") from error
    if result.returncode != 0 or result.stdout != working_bytes:
        raise AuthorityReconciliationError("COMMITTED_SOURCE_DRIFT")
    try:
        payload = json.loads(working_bytes)
    except json.JSONDecodeError as error:
        raise AuthorityReconciliationError("COMMITTED_SOURCE_INVALID_JSON") from error
    if not isinstance(payload, dict):
        raise AuthorityReconciliationError("COMMITTED_SOURCE_NOT_OBJECT")
    return payload, {
        "path": relative.as_posix(),
        "sha256": _sha256_bytes(working_bytes),
        "commit_status": "MATCHED",
    }


def _hash_value(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def _manifest_sources(audit: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    parity = audit.get("parity")
    if not isinstance(parity, Mapping):
        raise AuthorityReconciliationError("AUDIT_PARITY_MISSING")
    before = parity.get("fixed_sources_before")
    after = parity.get("fixed_sources_after")
    if not isinstance(before, Mapping) or before != after:
        raise AuthorityReconciliationError("AUDIT_SOURCE_PARITY_CONFLICT")
    result: dict[str, Mapping[str, Any]] = {}
    for key, expected_path in {
        "features": availability.FEATURES_RELATIVE,
        "regime": availability.REGIME_RELATIVE,
    }.items():
        record = before.get(key)
        if (
            not isinstance(record, Mapping)
            or record.get("status") != "AVAILABLE"
            or record.get("path") != expected_path.as_posix()
            or not _hash_value(record.get("sha256"))
        ):
            raise AuthorityReconciliationError(f"AUDIT_{key.upper()}_AUTHORITY_CONFLICT")
        if key == "features":
            date_coverage = record.get("date_coverage")
            if (
                not isinstance(date_coverage, Mapping)
                or set(date_coverage) != {"count", "first", "last"}
                or not isinstance(date_coverage.get("count"), int)
                or date_coverage.get("count", 0) <= 0
                or not isinstance(date_coverage.get("first"), str)
                or not isinstance(date_coverage.get("last"), str)
            ):
                raise AuthorityReconciliationError("AUDIT_FEATURES_DATE_COVERAGE_CONFLICT")
        result[key] = record
    return result


def _source_record(root: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    relative = Path(str(record["path"]))
    digest = _sha256_file(_safe_path(root, relative))
    if digest != record["sha256"]:
        raise AuthorityReconciliationError("RUNTIME_SOURCE_HASH_MISMATCH")
    result: dict[str, Any] = {
        "path": relative.as_posix(),
        "sha256": digest,
        "commit_status": "IGNORED_HASH_BOUND",
    }
    if isinstance(record.get("date_coverage"), Mapping):
        result["date_coverage"] = dict(record["date_coverage"])
    return result


def _with_receipt_id(payload: dict[str, Any]) -> dict[str, Any]:
    payload["receipt_id"] = content_hash(payload, omit={"receipt_id"})
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


def build_receipt(
    *, project_root: Path = PROJECT_ROOT, authority_root: Path | None = None
) -> dict[str, Any]:
    project_root = project_root.resolve()
    try:
        authority_root = coverage.authorize_explicit_authority_root(
            project_root, authority_root or coverage.discover_authority_root(project_root)
        )
    except coverage.CoveragePlanError as error:
        raise AuthorityReconciliationError("AUTHORITY_ROOT_INVALID") from error

    plan, plan_record = _committed_json(project_root, PLAN_RELATIVE)
    if (
        plan.get("schema_version") != coverage.SCHEMA_VERSION
        or plan.get("status") != "NO-GO_PLAN_UNAVAILABLE"
    ):
        raise AuthorityReconciliationError("COVERAGE_PLAN_AUTHORITY_CONFLICT")
    audit_ref = plan.get("audit")
    if (
        not isinstance(audit_ref, Mapping)
        or audit_ref.get("path") != AUDIT_RELATIVE.as_posix()
        or not _hash_value(audit_ref.get("sha256"))
        or not _hash_value(audit_ref.get("audit_id"))
    ):
        raise AuthorityReconciliationError("COVERAGE_PLAN_AUDIT_REF_CONFLICT")

    audit, audit_record = _committed_json(project_root, AUDIT_RELATIVE)
    if audit_record["sha256"] != audit_ref["sha256"]:
        raise AuthorityReconciliationError("AVAILABILITY_AUDIT_HASH_MISMATCH")
    if (
        audit.get("schema_version") != availability.SCHEMA_VERSION
        or audit.get("verdict") != "NO-GO_EVIDENCE_UNAVAILABLE"
        or audit.get("audit_id") != audit_ref["audit_id"]
        or audit.get("audit_id") != content_hash(audit, omit={"audit_id"})
    ):
        raise AuthorityReconciliationError("AVAILABILITY_AUDIT_AUTHORITY_CONFLICT")

    manifests = _manifest_sources(audit)
    before_protected = content_hash(snapshot_protected_surfaces(project_root=authority_root))
    before_runtime = {
        key: _source_record(authority_root, record)
        for key, record in sorted(manifests.items())
    }
    after_runtime = {
        key: _source_record(authority_root, record)
        for key, record in sorted(manifests.items())
    }
    after_protected = content_hash(snapshot_protected_surfaces(project_root=authority_root))
    parity = {
        "runtime_sources_unchanged": before_runtime == after_runtime,
        "protected_surfaces_before_hash": before_protected,
        "protected_surfaces_after_hash": after_protected,
        "protected_surfaces_unchanged": before_protected == after_protected,
    }
    if not parity["runtime_sources_unchanged"] or not parity["protected_surfaces_unchanged"]:
        raise AuthorityReconciliationError("AUTHORITY_DRIFT_DURING_RECONCILIATION")

    return _with_receipt_id(
        {
            "schema_version": SCHEMA_VERSION,
            "receipt_id": "",
            "status": "READY_FOR_FEASIBILITY_AUDIT",
            "reason_codes": [],
            "lineage_authority_status": "UNPROVEN",
            "chain": {
                "coverage_plan": plan_record,
                "availability_audit": {
                    **audit_record,
                    "audit_id": str(audit["audit_id"]),
                },
            },
            "runtime_sources": before_runtime,
            "parity": parity,
        }
    )


def validate_receipt(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if set(payload) != {
        "schema_version",
        "receipt_id",
        "status",
        "reason_codes",
        "lineage_authority_status",
        "chain",
        "runtime_sources",
        "parity",
    }:
        errors.append("RECEIPT_FIELDS_INVALID")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("SCHEMA_VERSION_INVALID")
    if payload.get("status") not in ALLOWED_STATUSES:
        errors.append("STATUS_INVALID")
    if payload.get("receipt_id") != content_hash(payload, omit={"receipt_id"}):
        errors.append("RECEIPT_ID_MISMATCH")
    if payload.get("lineage_authority_status") != "UNPROVEN":
        errors.append("LINEAGE_AUTHORITY_MUST_REMAIN_UNPROVEN")
    reason_codes = payload.get("reason_codes")
    if not isinstance(reason_codes, list) or any(not isinstance(item, str) for item in reason_codes):
        errors.append("REASON_CODES_INVALID")
    elif payload.get("status") == "READY_FOR_FEASIBILITY_AUDIT" and reason_codes:
        errors.append("FALSE_READY_STATUS")
    for value in _strings(payload):
        if value.startswith("/"):
            errors.append("ABSOLUTE_PATH_FORBIDDEN")
    sources = payload.get("runtime_sources")
    if not isinstance(sources, Mapping) or set(sources) != {"features", "regime"} or any(
        not isinstance(record, Mapping)
        or record.get("commit_status") != "IGNORED_HASH_BOUND"
        for record in sources.values()
    ):
        errors.append("RUNTIME_SOURCE_STATUS_INVALID")
    elif (
        sources["features"].get("path") != availability.FEATURES_RELATIVE.as_posix()
        or sources["regime"].get("path") != availability.REGIME_RELATIVE.as_posix()
        or any(not _hash_value(record.get("sha256")) for record in sources.values())
    ):
        errors.append("RUNTIME_SOURCE_IDENTITY_INVALID")
    chain = payload.get("chain")
    expected_chain = {
        "coverage_plan": PLAN_RELATIVE.as_posix(),
        "availability_audit": AUDIT_RELATIVE.as_posix(),
    }
    if not isinstance(chain, Mapping) or set(chain) != set(expected_chain) or any(
        not isinstance(chain.get(key), Mapping)
        or chain[key].get("path") != path
        or chain[key].get("commit_status") != "MATCHED"
        or not _hash_value(chain[key].get("sha256"))
        for key, path in expected_chain.items()
    ):
        errors.append("CHAIN_IDENTITY_INVALID")
    parity = payload.get("parity")
    if (
        not isinstance(parity, Mapping)
        or parity.get("runtime_sources_unchanged") is not True
        or parity.get("protected_surfaces_unchanged") is not True
        or not _hash_value(parity.get("protected_surfaces_before_hash"))
        or parity.get("protected_surfaces_before_hash")
        != parity.get("protected_surfaces_after_hash")
    ):
        errors.append("PARITY_INVALID")
    return sorted(set(errors))


def encode_receipt(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _evidence_path(path: Path) -> Path:
    if path.is_absolute() or path.as_posix() != EVIDENCE_RELATIVE.as_posix():
        raise AuthorityReconciliationError("EVIDENCE_PATH_NOT_CANONICAL")
    return _safe_path(PROJECT_ROOT, path)


def write_receipt(path: Path, *, authority_root: Path | None = None) -> dict[str, Any]:
    target = _evidence_path(path)
    payload = build_receipt(authority_root=authority_root)
    errors = validate_receipt(payload)
    if errors:
        raise AuthorityReconciliationError("RECEIPT_VALIDATION_FAILED:" + ",".join(errors))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encode_receipt(payload))
    return payload


def verify_receipt(path: Path, *, authority_root: Path | None = None) -> dict[str, Any]:
    try:
        target = _evidence_path(path)
        raw = target.read_bytes()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise AuthorityReconciliationError("EVIDENCE_NOT_OBJECT")
        errors = validate_receipt(payload)
        if raw != encode_receipt(payload):
            errors.append("NON_CANONICAL_BYTES")
        if payload != build_receipt(authority_root=authority_root):
            errors.append("RECEIPT_RECOMPUTE_MISMATCH")
    except AuthorityReconciliationError as error:
        return {"status": "FAIL", "errors": [str(error)]}
    except OSError:
        return {"status": "FAIL", "errors": ["IO_ERROR"]}
    except json.JSONDecodeError:
        return {"status": "FAIL", "errors": ["EVIDENCE_INVALID_JSON"]}
    return {"status": "PASS" if not errors else "FAIL", "errors": sorted(set(errors))}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="reconcile ignored replay authority snapshot")
    parser.add_argument("--authority-root", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = (
            verify_receipt(args.verify, authority_root=args.authority_root)
            if args.verify
            else write_receipt(args.output, authority_root=args.authority_root)
        )
    except AuthorityReconciliationError as error:
        print(json.dumps({"status": "FAIL", "errors": [str(error)]}, sort_keys=True))
        return 2
    except OSError:
        print(json.dumps({"status": "FAIL", "errors": ["IO_ERROR"]}, sort_keys=True))
        return 2
    print(
        json.dumps(
            result if args.verify else {"status": result["status"], "receipt_id": result["receipt_id"]},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if not args.verify or result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

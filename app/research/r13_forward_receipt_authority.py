"""R13-R2 forward receipt 的 committed-bundle authority reader。

此模組只驗證單一已固定的 R13-R2 bundle。它不探索 latest、不接受 caller
指定 path、不寫 registration artifact，也不授予任何 downstream authority。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from app.research import ranking_provenance_receipt as receipt_verifier


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "ranking-provenance-forward-authority-verification.v1"
STATUS_REGISTERED = "REGISTERED_FORWARD_BUNDLE_VERIFIED"
STATUS_REJECTED = "REJECTED"
AUTHORITY_SCOPE = "R13_R2_COMMITTED_EVIDENCE_ONLY"
DOWNSTREAM_AUTHORITY = "NONE"


@dataclass(frozen=True)
class _ExpectedFile:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class _AuthorityContract:
    output_root: str
    manifest_path: str
    scenario: str
    ranking_date: str
    run_identity: str
    batch_plan_id: str
    manifest_identity: str
    receipt_identity: str
    capture_mode: str
    admission_eligible: str
    expected_files: tuple[_ExpectedFile, ...]


_OUTPUT_ROOT = "artifacts/backtest/r13-r2-20260901-af9c32b/output"
_RUN_ROOT = (
    _OUTPUT_ROOT
    + "/.ranking-provenance-v1/runs/r13-r2-20260901-af9c32b"
)
_MANIFEST_PATH = _RUN_ROOT + "/COMPLETE.manifest.json"
_RECEIPT_PATH = _RUN_ROOT + "/receipts/ranking_2026-09-01.receipt.json"
_MODEL_PATH = (
    _RUN_ROOT
    + "/model_snapshots/model-ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d.pkl"
)
_RANKING_PATH = _OUTPUT_ROOT + "/ranking_2026-09-01.csv"

R13_CONTRACT = _AuthorityContract(
    output_root=_OUTPUT_ROOT,
    manifest_path=_MANIFEST_PATH,
    scenario="regime_shadow_research",
    ranking_date="2026-09-01",
    run_identity="r13-r2-20260901-af9c32b",
    batch_plan_id="sha256:7cb4ab0fc61758085f71a865de79e022633327894807322bea66a0535aef46aa",
    manifest_identity="sha256:a493c793a34a4598e0500de8dd3e80c8252033e5ab85d8f620b50d5fc63411cb",
    receipt_identity="sha256:c2487b57395f83ff3d266aab4fd0349784d6fa892701ba7235aa8ec3b7bf527f",
    capture_mode=receipt_verifier.FORWARD_CAPTURE,
    admission_eligible="pending_registration",
    expected_files=(
        _ExpectedFile(
            path=_MANIFEST_PATH,
            size=4263,
            sha256="144777c9ea1aa8dcd944917820640a77866e3e4280549854549a98e3b90189c9",
        ),
        _ExpectedFile(
            path=_RECEIPT_PATH,
            size=8074,
            sha256="dff85cb7028f3a664a5d96a0884f4f7e6d334c29ef2f8c23bd85e42cdcbc76ee",
        ),
        _ExpectedFile(
            path=_MODEL_PATH,
            size=2798697,
            sha256="ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d",
        ),
        _ExpectedFile(
            path=_RANKING_PATH,
            size=4546,
            sha256="d17cf9202b83f626023a8ee18aff423b1508540e6c54f294c7253021350046b2",
        ),
    ),
)


def _prefixed(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _expected_by_path(contract: _AuthorityContract) -> dict[str, _ExpectedFile]:
    return {item.path: item for item in contract.expected_files}


def _safe_project_path(project_root: Path, relative: str) -> Path:
    parsed = PurePosixPath(relative)
    if not relative or parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError("PATH_ESCAPE")
    root = project_root.resolve(strict=True)
    if root.is_symlink():
        raise ValueError("ROOT_SYMLINK")
    cursor = root
    for part in parsed.parts:
        cursor /= part
        if cursor.exists() and cursor.is_symlink():
            raise ValueError("PATH_SYMLINK")
    try:
        cursor.resolve(strict=False).relative_to(root)
    except ValueError as error:
        raise ValueError("PATH_ESCAPE") from error
    return cursor


def _git_bytes(project_root: Path, args: Sequence[str]) -> tuple[int, bytes]:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *args],
        capture_output=True,
        check=False,
    )
    return completed.returncode, completed.stdout


def _git_lines(project_root: Path, args: Sequence[str]) -> tuple[int, list[str]]:
    code, raw = _git_bytes(project_root, args)
    return code, raw.decode("utf-8", errors="replace").splitlines()


def _resolve_project_root(project_root: Path) -> tuple[Path | None, list[str]]:
    lexical = project_root.absolute()
    try:
        resolved = lexical.resolve(strict=True)
    except OSError:
        return None, ["ROOT_UNAVAILABLE"]
    if lexical.is_symlink() or lexical != resolved:
        return None, ["ROOT_SYMLINK"]
    return resolved, []


def _pin_head(project_root: Path) -> tuple[str | None, list[str]]:
    code, raw = _git_bytes(project_root, ["rev-parse", "--verify", "HEAD^{commit}"])
    if code != 0:
        return None, ["GIT_HEAD_PIN_UNAVAILABLE"]
    commit = raw.decode("utf-8", errors="replace").strip()
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        return None, ["GIT_HEAD_PIN_INVALID"]
    return commit, []


def _base_result(contract: _AuthorityContract) -> dict[str, Any]:
    manifest = _expected_by_path(contract)[contract.manifest_path]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS_REJECTED,
        "authority_scope": AUTHORITY_SCOPE,
        "manifest": {
            "path": contract.manifest_path,
            "sha256": _prefixed(manifest.sha256),
            "commit_status": "UNVERIFIED",
        },
        "identity": {
            "scenario": contract.scenario,
            "ranking_date": contract.ranking_date,
            "run_identity": contract.run_identity,
            "batch_plan_id": contract.batch_plan_id,
            "manifest_identity": contract.manifest_identity,
            "receipt_identity": contract.receipt_identity,
        },
        "bundle_files": [
            {
                "path": item.path,
                "sha256": _prefixed(item.sha256),
                "commit_status": "UNVERIFIED",
            }
            for item in sorted(contract.expected_files, key=lambda row: row.path)
        ],
        "downstream_authority": DOWNSTREAM_AUTHORITY,
        "errors": [],
    }


def _set_file_status(result: dict[str, Any], path: str, status: str) -> None:
    for item in result["bundle_files"]:
        if item["path"] == path:
            item["commit_status"] = status
            break
    if path == result["manifest"]["path"]:
        result["manifest"]["commit_status"] = status


def _load_json(raw: bytes, code: str) -> tuple[Mapping[str, Any] | None, list[str]]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, [code]
    if not isinstance(value, Mapping):
        return None, [code]
    return value, []


def _verify_head_file_set(
    project_root: Path,
    contract: _AuthorityContract,
    commit: str,
) -> list[str]:
    expected = set(_expected_by_path(contract))
    errors: list[str] = []
    code, head_files = _git_lines(
        project_root,
        ["ls-tree", "-r", "--name-only", commit, "--", contract.output_root],
    )
    if code != 0:
        errors.append("GIT_HEAD_FILE_SET_UNAVAILABLE")
        head_files = []
    actual_head = {item for item in head_files if item}
    for path in sorted(expected - actual_head):
        errors.append(f"SOURCE_NOT_COMMITTED:{path}")
    for path in sorted(actual_head - expected):
        errors.append(f"EXTRA_TRACKED_FILE:{path}")
    code, staged = _git_lines(
        project_root,
        ["diff", "--cached", "--name-only", "--", contract.output_root],
    )
    if code != 0:
        errors.append("GIT_STAGED_STATE_UNAVAILABLE")
    else:
        for path in sorted(item for item in staged if item):
            errors.append(f"SOURCE_STAGED_NOT_HEAD:{path}")
    code, staged_added = _git_lines(
        project_root,
        ["diff", "--cached", "--name-only", "--diff-filter=A", "--", contract.output_root],
    )
    if code != 0:
        errors.append("GIT_STAGED_STATE_UNAVAILABLE")
    else:
        for path in sorted(item for item in staged_added if item and item not in expected):
            errors.append(f"SOURCE_STAGED_NOT_HEAD:{path}")
    return errors


def _verify_expected_bytes(
    project_root: Path,
    contract: _AuthorityContract,
    result: dict[str, Any],
    commit: str,
) -> tuple[list[str], dict[str, bytes]]:
    errors: list[str] = []
    committed: dict[str, bytes] = {}
    for path, expected in sorted(_expected_by_path(contract).items()):
        try:
            working_path = _safe_project_path(project_root, path)
        except ValueError as error:
            _set_file_status(result, path, str(error))
            errors.append(f"{error}:{path}")
            continue
        code, head_raw = _git_bytes(project_root, ["show", f"{commit}:{path}"])
        if code != 0:
            _set_file_status(result, path, "SOURCE_NOT_COMMITTED")
            errors.append(f"SOURCE_NOT_COMMITTED:{path}")
            continue
        try:
            working_raw = working_path.read_bytes()
        except OSError:
            _set_file_status(result, path, "SOURCE_UNREADABLE")
            errors.append(f"SOURCE_UNREADABLE:{path}")
            continue
        if head_raw != working_raw:
            _set_file_status(result, path, "SOURCE_WORKTREE_DRIFT")
            errors.append(f"SOURCE_WORKTREE_DRIFT:{path}")
            continue
        status = "MATCHED"
        if len(head_raw) != expected.size:
            errors.append(f"SOURCE_SIZE_MISMATCH:{path}")
            status = "SOURCE_SIZE_MISMATCH"
        if _sha256(head_raw) != expected.sha256:
            errors.append(f"SOURCE_HASH_MISMATCH:{path}")
            status = "SOURCE_HASH_MISMATCH"
        _set_file_status(result, path, status)
        committed[path] = head_raw
    return errors, committed


def _verify_identity(
    contract: _AuthorityContract,
    committed: Mapping[str, bytes],
) -> list[str]:
    errors: list[str] = []
    manifest_raw = committed.get(contract.manifest_path)
    if manifest_raw is None:
        return ["MANIFEST_UNAVAILABLE"]
    manifest, manifest_errors = _load_json(manifest_raw, "MANIFEST_JSON_INVALID")
    errors.extend(manifest_errors)
    if manifest is None:
        return errors
    errors.extend(
        f"BUNDLE_VERIFIER_{item.upper()}"
        for item in receipt_verifier.validate_complete_manifest(manifest)
    )
    if manifest.get("scenario") != contract.scenario:
        errors.append("SCENARIO_MISMATCH")
    if manifest.get("run_identity") != contract.run_identity:
        errors.append("RUN_IDENTITY_MISMATCH")
    if manifest.get("batch_plan_id") != contract.batch_plan_id:
        errors.append("BATCH_PLAN_ID_MISMATCH")
    if manifest.get("manifest_identity") != contract.manifest_identity:
        errors.append("MANIFEST_IDENTITY_MISMATCH")
    if manifest.get("capture_mode") != contract.capture_mode:
        errors.append("CAPTURE_MODE_MISMATCH")
    if manifest.get("planned_rankings") != [f"ranking_{contract.ranking_date}.csv"]:
        errors.append("PLANNED_RANKINGS_MISMATCH")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != 1:
        errors.append("MANIFEST_ENTRY_COUNT_MISMATCH")
    else:
        entry = entries[0]
        receipt_info = entry.get("receipt") if isinstance(entry, Mapping) else None
        if not isinstance(entry, Mapping):
            errors.append("MANIFEST_ENTRY_SCHEMA_INVALID")
        elif (
            entry.get("ranking_date") != contract.ranking_date
            or entry.get("ranking_artifact", {}).get("path") not in _expected_by_path(contract)
            or not isinstance(receipt_info, Mapping)
            or receipt_info.get("path") not in _expected_by_path(contract)
            or receipt_info.get("receipt_identity") != contract.receipt_identity
        ):
            errors.append("MANIFEST_ENTRY_IDENTITY_MISMATCH")
    receipt_path = None
    for path in _expected_by_path(contract):
        if path.endswith(f"ranking_{contract.ranking_date}.receipt.json"):
            receipt_path = path
            break
    receipt_raw = committed.get(receipt_path or "")
    if receipt_raw is None:
        errors.append("RECEIPT_UNAVAILABLE")
        return errors
    receipt, receipt_errors = _load_json(receipt_raw, "RECEIPT_JSON_INVALID")
    errors.extend(receipt_errors)
    if receipt is None:
        return errors
    if receipt.get("scenario") != contract.scenario:
        errors.append("RECEIPT_SCENARIO_MISMATCH")
    if receipt.get("ranking_date") != contract.ranking_date:
        errors.append("RECEIPT_RANKING_DATE_MISMATCH")
    if receipt.get("run_identity") != contract.run_identity:
        errors.append("RECEIPT_RUN_IDENTITY_MISMATCH")
    if receipt.get("batch_plan_id") != contract.batch_plan_id:
        errors.append("RECEIPT_BATCH_PLAN_ID_MISMATCH")
    if receipt.get("receipt_identity") != contract.receipt_identity:
        errors.append("RECEIPT_IDENTITY_MISMATCH")
    if receipt.get("capture_mode") != contract.capture_mode:
        errors.append("RECEIPT_CAPTURE_MODE_MISMATCH")
    if receipt.get("admission_eligible") != contract.admission_eligible:
        errors.append("RECEIPT_ADMISSION_ELIGIBLE_MISMATCH")
    return errors


def _verify_with_contract(
    *,
    project_root: Path,
    contract: _AuthorityContract,
) -> dict[str, Any]:
    result = _base_result(contract)
    errors: list[str] = []
    root, root_errors = _resolve_project_root(project_root)
    errors.extend(root_errors)
    if root is None:
        result["errors"] = sorted(set(errors))
        return result
    commit, commit_errors = _pin_head(root)
    errors.extend(commit_errors)
    if commit is None:
        result["errors"] = sorted(set(errors))
        return result
    errors.extend(_verify_head_file_set(root, contract, commit))
    byte_errors, committed = _verify_expected_bytes(root, contract, result, commit)
    errors.extend(byte_errors)
    errors.extend(_verify_identity(contract, committed))
    manifest_path = root / contract.manifest_path
    if manifest_path.is_file():
        try:
            errors.extend(
                f"BUNDLE_VERIFIER_{item.upper()}"
                for item in receipt_verifier.verify_complete_bundle(root, manifest_path)
            )
        except Exception:
            errors.append("BUNDLE_VERIFIER_EXCEPTION")
    else:
        errors.append("MANIFEST_UNAVAILABLE")
    final_commit, final_commit_errors = _pin_head(root)
    errors.extend(final_commit_errors)
    if final_commit is not None and final_commit != commit:
        errors.append("HEAD_CHANGED_DURING_VERIFICATION")
    result["errors"] = sorted(set(errors))
    result["status"] = STATUS_REGISTERED if not result["errors"] else STATUS_REJECTED
    return result


def verify_registered_r13_bundle(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """驗證固定 R13-R2 bundle 是否已成為 Git HEAD 的 committed evidence。"""

    return _verify_with_contract(project_root=project_root, contract=R13_CONTRACT)


def _encode_result(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="verify fixed R13-R2 committed forward receipt bundle"
    )
    parser.add_argument("--verify", action="store_true", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    parse_args(argv)
    result = verify_registered_r13_bundle()
    print(_encode_result(result))
    return 0 if result["status"] == STATUS_REGISTERED else 1


if __name__ == "__main__":
    raise SystemExit(main())

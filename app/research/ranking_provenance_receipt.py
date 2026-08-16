"""Research ranking 的 forward-only provenance receipt 契約。

此模組刻意不讀取報酬、價格路徑或任何 outcome。它只負責把 ranking
產生當下的輸入、producer 與輸出 bytes 鎖成可供日後 registration 審查的
bundle；receipt 本身不授予 admission。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import pandas as pd

from app.research.contracts import canonical_json_bytes, content_hash


SCHEMA_VERSION = "ranking-provenance-receipt.v1"
MANIFEST_SCHEMA_VERSION = "ranking-provenance-batch-manifest.v1"
FORWARD_CAPTURE = "FORWARD_CAPTURE"
REPLAY_GENERATED = "REPLAY_GENERATED"
_CAPTURE_MODES = {FORWARD_CAPTURE, REPLAY_GENERATED}
_FORBIDDEN_TOKENS = (
    "outcome", "return", "pnl", "win_rate", "winrate", "sharpe", "alpha",
    "profit", "roi", "performance", "target", "future", "price", "ohlc",
)
_RECEIPT_FIELDS = {
    "schema_version", "scenario", "ranking_date", "run_identity", "batch_plan_id",
    "capture_mode", "admission_eligible", "ranking_artifact", "producer", "model",
    "config", "universe", "feature_calendar", "top_n_policy", "strict_inputs",
    "receipt_identity",
}
_MANIFEST_FIELDS = {
    "schema_version", "status", "run_identity", "batch_plan_id", "scenario",
    "producer_entrypoint", "capture_mode", "entries", "input_hashes_before",
    "input_hashes_after", "planned_rankings", "manifest_identity",
}
_STRICT_INPUT_NAMES = {"market_regime_history", "industry_map", "calendar_schedule_source"}


class RankingProvenanceError(RuntimeError):
    """Receipt 或 bundle 違反 immutable／forward-only 契約。"""


def sha256_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise RankingProvenanceError(f"檔案不存在：{path}")
    return sha256_bytes(path.read_bytes())


def canonical_encode(payload: Mapping[str, Any]) -> bytes:
    return canonical_json_bytes(payload) + b"\n"


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in _FORBIDDEN_TOKENS) or _contains_forbidden_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _repo_relative(project_root: Path, path: Path) -> str:
    resolved_root = project_root.resolve(strict=True)
    if resolved_root.is_symlink():
        raise RankingProvenanceError("專案根目錄不可為 symlink")
    lexical = path.absolute()
    cursor = project_root.absolute()
    try:
        relative_lexical = lexical.relative_to(cursor)
    except ValueError as error:
        raise RankingProvenanceError(f"路徑不可離開專案：{path}") from error
    for part in relative_lexical.parts:
        cursor /= part
        if cursor.exists() and cursor.is_symlink():
            raise RankingProvenanceError(f"不接受 symlink：{cursor}")
    try:
        relative = path.resolve(strict=False).relative_to(resolved_root)
    except ValueError as error:
        raise RankingProvenanceError(f"路徑不可離開專案：{path}") from error
    value = relative.as_posix()
    if not value or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
        raise RankingProvenanceError(f"不合法 repo-relative path：{path}")
    return value


def _safe_repo_path(project_root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise RankingProvenanceError("path 必須是非空 repo-relative string")
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise RankingProvenanceError("path 不可為絕對路徑或包含 ..")
    path = project_root.joinpath(*relative.parts)
    _repo_relative(project_root, path)
    return path


def _valid_relative_path(value: object) -> bool:
    try:
        relative = PurePosixPath(str(value))
    except TypeError:
        return False
    return isinstance(value, str) and bool(value) and not relative.is_absolute() and ".." not in relative.parts


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and len(value) == 71 and value.startswith("sha256:") and all(
        char in "0123456789abcdef" for char in value[7:]
    )


def _exact_keys(payload: object, fields: set[str]) -> bool:
    return isinstance(payload, Mapping) and set(payload) == fields


def _git(project_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(project_root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RankingProvenanceError(f"git 無法解析 producer source：{' '.join(args)}")
    return completed.stdout.strip()


def producer_source_lineage(project_root: Path, dependencies: Sequence[Path]) -> dict[str, Any]:
    """拒絕 dirty 或與 HEAD bytes 不一致的 producer dependency。"""

    commit = _git(project_root, "rev-parse", "HEAD")
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    expanded: list[Path] = []
    for path in dependencies:
        relative = _repo_relative(project_root, path)
        if path.is_dir():
            tracked = _git(project_root, "ls-files", "--", relative).splitlines()
            selected = [item for item in tracked if item.endswith(".py")]
            if not selected:
                raise RankingProvenanceError(f"producer dependency 目錄沒有 tracked Python：{relative}")
            expanded.extend(project_root / item for item in selected)
        else:
            expanded.append(path)
    for path in expanded:
        relative = _repo_relative(project_root, path)
        if relative in seen:
            continue
        seen.add(relative)
        if not path.is_file():
            raise RankingProvenanceError(f"producer dependency 不存在：{relative}")
        head_bytes = subprocess.run(
            ["git", "-C", str(project_root), "show", f"HEAD:{relative}"],
            capture_output=True,
            check=False,
        )
        if head_bytes.returncode != 0 or head_bytes.stdout != path.read_bytes():
            raise RankingProvenanceError(f"producer dependency 非 HEAD bytes：{relative}")
        files.append({"path": relative, "sha256": sha256_bytes(head_bytes.stdout)})
    if not files:
        raise RankingProvenanceError("producer dependency 不可為空")
    return {"source_commit": commit, "dependencies": sorted(files, key=lambda item: item["path"])}


def snapshot_inputs(project_root: Path, inputs: Mapping[str, Path]) -> dict[str, dict[str, str]]:
    snapshot: dict[str, dict[str, str]] = {}
    for name, path in sorted(inputs.items()):
        if not isinstance(name, str) or not name or path is None:
            raise RankingProvenanceError("strict input 名稱或 path 不合法")
        snapshot[name] = {"path": _repo_relative(project_root, path), "sha256": sha256_file(path)}
    return snapshot


def assert_same_inputs(before: Mapping[str, Any], after: Mapping[str, Any]) -> None:
    if dict(before) != dict(after):
        raise RankingProvenanceError("strict input 在 run 前後發生漂移")


def ensure_capture_mode(
    *, capture_mode: str, ranking_dates: Sequence[str], capture_trade_date: str | None,
    trusted_capture_trade_date: str | None = None,
) -> tuple[bool, str | bool]:
    if capture_mode not in _CAPTURE_MODES:
        raise RankingProvenanceError("capture_mode 僅允許 FORWARD_CAPTURE 或 REPLAY_GENERATED")
    if capture_mode == REPLAY_GENERATED:
        return False, False
    if (
        len(ranking_dates) != 1
        or not capture_trade_date
        or not trusted_capture_trade_date
        or ranking_dates[0] != capture_trade_date
        or capture_trade_date != trusted_capture_trade_date
    ):
        raise RankingProvenanceError("FORWARD_CAPTURE 必須是 trusted capture trade date 的單一 ranking date")
    return True, "pending_registration"


def stable_ranked_top_n(frame: pd.DataFrame, *, score_column: str, top_n: int) -> pd.DataFrame:
    """輸出唯一 stock_id、穩定 score DESC / stock_id ASC 的完整 Top-N。"""

    if top_n < 1 or score_column not in frame.columns or "stock_id" not in frame.columns:
        raise RankingProvenanceError("top-N、score 或 stock_id 不完整")
    prepared = frame.copy()
    prepared["stock_id"] = prepared["stock_id"].astype(str).str.strip()
    if prepared["stock_id"].eq("").any() or prepared["stock_id"].duplicated().any():
        raise RankingProvenanceError("ranking stock_id 必須非空且唯一")
    scores = pd.to_numeric(prepared[score_column], errors="coerce")
    if scores.isna().any():
        raise RankingProvenanceError("ranking score 不可為空")
    prepared[score_column] = scores
    selected = prepared.sort_values(
        [score_column, "stock_id"], ascending=[False, True], kind="mergesort"
    ).head(top_n).copy()
    if len(selected) != top_n:
        raise RankingProvenanceError("ranking row count 必須恰等於 top-N")
    selected.insert(0, "rank", range(1, top_n + 1))
    return selected


def verify_ranking_semantics(path: Path, policy: Mapping[str, Any]) -> list[str]:
    """驗證 CSV 的 row/rank/stock/score 排序，不能只相信 receipt 宣告。"""

    errors: list[str] = []
    if not isinstance(policy, Mapping):
        return ["ranking_policy"]
    top_n = policy.get("top_n")
    score_column = policy.get("score_column")
    if not isinstance(top_n, int) or top_n < 1 or not isinstance(score_column, str) or not score_column:
        return ["ranking_policy"]
    try:
        frame = pd.read_csv(path, dtype={"stock_id": str}, encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError, pd.errors.ParserError):
        return ["ranking_csv_unreadable"]
    if len(frame) != top_n:
        errors.append("ranking_row_count")
    if not {"rank", "stock_id", score_column}.issubset(frame.columns):
        return errors + ["ranking_required_columns"]
    ranks = pd.to_numeric(frame["rank"], errors="coerce")
    if ranks.isna().any() or ranks.astype(int).tolist() != list(range(1, len(frame) + 1)):
        errors.append("ranking_rank_sequence")
    stock_ids = frame["stock_id"].astype(str).str.strip()
    if stock_ids.eq("").any() or stock_ids.duplicated().any():
        errors.append("ranking_stock_id")
    scores = pd.to_numeric(frame[score_column], errors="coerce")
    if scores.isna().any():
        errors.append("ranking_score")
    else:
        ordered = frame.assign(__stock=stock_ids, __score=scores).sort_values(
            ["__score", "__stock"], ascending=[False, True], kind="mergesort"
        )
        if ordered.index.tolist() != frame.index.tolist():
            errors.append("ranking_sort_policy")
    return errors


def _atomic_create(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise RankingProvenanceError(f"create-only 目標已存在：{path}") from error
    finally:
        if fd is not None:
            os.close(fd)


def create_content_addressed_model_snapshot(
    *, project_root: Path, source_model: Path, staging_dir: Path,
) -> tuple[Path, dict[str, str]]:
    source_hash = sha256_file(source_model)
    suffix = source_model.suffix or ".bin"
    destination = staging_dir / "model_snapshots" / f"model-{source_hash.removeprefix('sha256:')}{suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    _atomic_create(destination, source_model.read_bytes())
    if sha256_file(destination) != source_hash:
        raise RankingProvenanceError("model snapshot bytes 不一致")
    return destination, {"path": _repo_relative(project_root, destination), "sha256": source_hash}


def batch_plan_id(*, run_identity: str, scenario: str, producer_entrypoint: str, planned_rankings: Sequence[str]) -> str:
    if not run_identity or not scenario or not producer_entrypoint or not planned_rankings:
        raise RankingProvenanceError("batch plan identity 不完整")
    return content_hash({
        "schema_version": "ranking-provenance-batch-plan.v1",
        "run_identity": run_identity,
        "scenario": scenario,
        "producer_entrypoint": producer_entrypoint,
        "planned_rankings": list(planned_rankings),
    })


def _ranking_basename(date_text: str) -> str:
    return f"ranking_{date_text}.csv"


def _receipt_basename(date_text: str) -> str:
    return f"ranking_{date_text}.receipt.json"


def build_receipt(
    *, project_root: Path, scenario: str, ranking_date: str, run_identity: str,
    batch_plan: str, ranking_path: Path, producer_entrypoint: str,
    producer_lineage: Mapping[str, Any], model: Mapping[str, str], config: Mapping[str, str],
    universe: Mapping[str, str], feature_calendar: Mapping[str, str], top_n: int,
    capture_mode: str, admission_eligible: bool | str, extra_inputs: Mapping[str, Mapping[str, str]] | None = None,
    published_ranking_path: Path | None = None, score_column: str = "",
) -> dict[str, Any]:
    if not scenario or not ranking_date or not run_identity or not batch_plan:
        raise RankingProvenanceError("receipt identity 不完整")
    if capture_mode == REPLAY_GENERATED and admission_eligible is not False:
        raise RankingProvenanceError("REPLAY_GENERATED 永遠不可 admission")
    if capture_mode == FORWARD_CAPTURE and admission_eligible != "pending_registration":
        raise RankingProvenanceError("FORWARD_CAPTURE 必須為 pending_registration")
    if not score_column:
        raise RankingProvenanceError("top-N score column 不可為空")
    artifact = {
        "path": _repo_relative(project_root, published_ranking_path or ranking_path),
        "sha256": sha256_file(ranking_path),
    }
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "scenario": scenario,
        "ranking_date": ranking_date,
        "run_identity": run_identity,
        "batch_plan_id": batch_plan,
        "capture_mode": capture_mode,
        "admission_eligible": admission_eligible,
        "ranking_artifact": artifact,
        "producer": {
            "entrypoint": producer_entrypoint,
            "source_commit": producer_lineage["source_commit"],
            "dependencies": producer_lineage["dependencies"],
        },
        "model": dict(model),
        "config": dict(config),
        "universe": dict(universe),
        "feature_calendar": dict(feature_calendar),
        "top_n_policy": {
            "top_n": top_n,
            "sort_policy": "score_desc",
            "tie_break_policy": "stock_id_asc",
            "rank_policy": "continuous_1_based",
            "score_column": score_column,
        },
        "strict_inputs": dict(extra_inputs or {}),
    }
    if _contains_forbidden_key(receipt):
        raise RankingProvenanceError("receipt 不可包含 outcome key")
    receipt["receipt_identity"] = content_hash(receipt)
    errors = validate_receipt(receipt)
    if errors:
        raise RankingProvenanceError("receipt 不合法：" + ", ".join(errors))
    return receipt


def validate_receipt(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not _exact_keys(payload, _RECEIPT_FIELDS):
        errors.append("receipt_fields")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version")
    if payload.get("capture_mode") not in _CAPTURE_MODES:
        errors.append("capture_mode")
    if payload.get("capture_mode") == REPLAY_GENERATED and payload.get("admission_eligible") is not False:
        errors.append("replay_admission")
    if payload.get("capture_mode") == FORWARD_CAPTURE and payload.get("admission_eligible") != "pending_registration":
        errors.append("forward_admission")
    for field in ("scenario", "ranking_date", "run_identity", "batch_plan_id", "receipt_identity"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            errors.append(field)
    artifact = payload.get("ranking_artifact")
    if not _exact_keys(artifact, {"path", "sha256"}) or not _valid_relative_path(artifact.get("path")) or not _valid_hash(artifact.get("sha256")):
        errors.append("ranking_artifact")
    policy = payload.get("top_n_policy")
    if (
        not _exact_keys(policy, {"top_n", "sort_policy", "tie_break_policy", "rank_policy", "score_column"})
        or not isinstance(policy.get("top_n"), int)
        or policy.get("top_n", 0) < 1
        or policy.get("sort_policy") != "score_desc"
        or policy.get("tie_break_policy") != "stock_id_asc"
        or policy.get("rank_policy") != "continuous_1_based"
        or not isinstance(policy.get("score_column"), str)
        or not policy.get("score_column")
    ):
        errors.append("top_n_policy")
    model = payload.get("model")
    if (
        not _exact_keys(model, {"path", "version", "sha256"})
        or not _valid_relative_path(model.get("path"))
        or "latest" in str(model.get("path")).lower()
        or not isinstance(model.get("version"), str)
        or not model.get("version")
        or not _valid_hash(model.get("sha256"))
    ):
        errors.append("model")
    for name in ("config", "universe", "feature_calendar"):
        item = payload.get(name)
        if not _exact_keys(item, {"path", "sha256"}) or not _valid_relative_path(item.get("path")) or not _valid_hash(item.get("sha256")):
            errors.append(name)
    producer = payload.get("producer")
    if (
        not _exact_keys(producer, {"entrypoint", "source_commit", "dependencies"})
        or not _valid_relative_path(producer.get("entrypoint"))
        or not isinstance(producer.get("source_commit"), str)
        or len(str(producer.get("source_commit"))) != 40
        or not isinstance(producer.get("dependencies"), list)
        or not producer["dependencies"]
    ):
        errors.append("producer")
    elif any(
        not _exact_keys(item, {"path", "sha256"})
        or not _valid_relative_path(item.get("path"))
        or not _valid_hash(item.get("sha256"))
        for item in producer["dependencies"]
    ):
        errors.append("producer_dependencies")
    strict_inputs = payload.get("strict_inputs")
    if not isinstance(strict_inputs, Mapping) or set(strict_inputs) - _STRICT_INPUT_NAMES:
        errors.append("strict_inputs")
    else:
        for name, item in strict_inputs.items():
            if not isinstance(name, str) or not _exact_keys(item, {"path", "sha256"}) or not _valid_relative_path(item.get("path")) or not _valid_hash(item.get("sha256")):
                errors.append("strict_inputs")
                break
    if _contains_forbidden_key(payload):
        errors.append("outcome_key")
    expected = content_hash({key: value for key, value in payload.items() if key != "receipt_identity"})
    if payload.get("receipt_identity") != expected:
        errors.append("receipt_identity")
    return errors


@dataclass
class BundleRun:
    """run-unique staging；只有 create-only COMPLETE manifest 是發布邊界。"""

    project_root: Path
    output_dir: Path
    scenario: str
    producer_entrypoint: str
    planned_dates: Sequence[str]
    capture_mode: str
    capture_trade_date: str | None
    trusted_capture_trade_date: str | None = None
    run_identity: str = field(default_factory=lambda: uuid.uuid4().hex)
    staging_dir: Path = field(init=False)
    final_dir: Path = field(init=False)
    plan_id: str = field(init=False)
    _receipts: list[tuple[Path, dict[str, Any]]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        eligible, _ = ensure_capture_mode(
            capture_mode=self.capture_mode,
            ranking_dates=list(self.planned_dates),
            capture_trade_date=self.capture_trade_date,
            trusted_capture_trade_date=self.trusted_capture_trade_date,
        )
        del eligible
        if len(set(self.planned_dates)) != len(self.planned_dates):
            raise RankingProvenanceError("scenario/date 不可重複")
        self.staging_dir = self.output_dir / ".ranking-provenance-staging" / self.run_identity
        self.final_dir = self.output_dir / ".ranking-provenance-v1" / "runs" / self.run_identity
        if self.staging_dir.exists() or self.final_dir.exists():
            raise RankingProvenanceError("run identity 已存在")
        planned = [f"ranking_{date_text}.csv" for date_text in self.planned_dates]
        self.plan_id = batch_plan_id(
            run_identity=self.run_identity, scenario=self.scenario,
            producer_entrypoint=self.producer_entrypoint, planned_rankings=planned,
        )
        self.staging_dir.mkdir(parents=True, exist_ok=False)

    @property
    def ranking_dir(self) -> Path:
        path = self.staging_dir / "rankings"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _published_ranking_path(self, date_text: str) -> Path:
        return self.output_dir / _ranking_basename(date_text)

    def _published_receipt_path(self, date_text: str) -> Path:
        return self.final_dir / "receipts" / _receipt_basename(date_text)

    def _validate_receipt_binding(self, date_text: str, receipt: Mapping[str, Any]) -> None:
        expected_artifact = _repo_relative(self.project_root, self._published_ranking_path(date_text))
        if (
            date_text not in self.planned_dates
            or receipt.get("ranking_date") != date_text
            or receipt.get("ranking_artifact", {}).get("path") != expected_artifact
            or Path(str(receipt.get("ranking_artifact", {}).get("path", ""))).name != _ranking_basename(date_text)
            or receipt.get("scenario") != self.scenario
            or receipt.get("run_identity") != self.run_identity
            or receipt.get("capture_mode") != self.capture_mode
            or receipt.get("batch_plan_id") != self.plan_id
            or receipt.get("producer", {}).get("entrypoint") != self.producer_entrypoint
        ):
            raise RankingProvenanceError("receipt 與 planned ranking identity 不一致")

    def add_receipt(self, date_text: str, receipt: dict[str, Any]) -> Path:
        errors = validate_receipt(receipt)
        if errors:
            raise RankingProvenanceError("receipt 不合法：" + ", ".join(errors))
        self._validate_receipt_binding(date_text, receipt)
        if any(existing.get("ranking_date") == date_text for _, existing in self._receipts):
            raise RankingProvenanceError("planned ranking receipt 不可重複")
        path = self.staging_dir / "receipts" / _receipt_basename(date_text)
        _atomic_create(path, canonical_encode(receipt))
        self._receipts.append((path, receipt))
        return path

    def fail(self, reason: str) -> None:
        marker = self.staging_dir / "FAILED.json"
        if not marker.exists():
            _atomic_create(marker, canonical_encode({"status": "FAILED", "reason": reason, "run_identity": self.run_identity}))

    def complete(self, *, before_inputs: Mapping[str, Any], after_inputs: Mapping[str, Any]) -> Path:
        assert_same_inputs(before_inputs, after_inputs)
        if len(self._receipts) != len(self.planned_dates):
            raise RankingProvenanceError("receipt 數量與預定日期不一致")
        if (self.staging_dir / "FAILED.json").exists():
            raise RankingProvenanceError("FAILED run 不可完成")
        receipt_by_date = {str(receipt.get("ranking_date")): (path, receipt) for path, receipt in self._receipts}
        if set(receipt_by_date) != set(self.planned_dates):
            raise RankingProvenanceError("planned ranking 與 receipt date 集合不一致")
        planned_rankings = [_ranking_basename(date_text) for date_text in self.planned_dates]
        manifest_entries = []
        for date_text in self.planned_dates:
            receipt_path, receipt = receipt_by_date[date_text]
            errors = validate_receipt(receipt)
            if errors:
                raise RankingProvenanceError("receipt 不合法：" + ", ".join(errors))
            self._validate_receipt_binding(date_text, receipt)
            artifact_path = _safe_repo_path(self.project_root, receipt["ranking_artifact"]["path"])
            staged_artifact = self.staging_dir / "rankings" / Path(str(receipt["ranking_artifact"]["path"])).name
            if artifact_path.exists():
                raise RankingProvenanceError("最終 ranking artifact 已存在，不可覆寫")
            if not staged_artifact.is_file() or sha256_file(staged_artifact) != receipt["ranking_artifact"]["sha256"]:
                raise RankingProvenanceError("staged ranking artifact hash 不一致")
            semantic_errors = verify_ranking_semantics(staged_artifact, receipt["top_n_policy"])
            if semantic_errors:
                raise RankingProvenanceError("staged ranking semantic 不一致：" + ", ".join(semantic_errors))
            manifest_entries.append({
                "ranking_date": receipt["ranking_date"], "ranking_artifact": receipt["ranking_artifact"],
                "receipt": {
                    "path": _repo_relative(
                        self.project_root, self._published_receipt_path(date_text)
                    ),
                    "sha256": sha256_file(receipt_path),
                    "receipt_identity": receipt["receipt_identity"],
                },
            })
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION, "status": "COMPLETE", "run_identity": self.run_identity,
            "batch_plan_id": self.plan_id, "scenario": self.scenario, "producer_entrypoint": self.producer_entrypoint,
            "capture_mode": self.capture_mode, "planned_rankings": planned_rankings, "entries": manifest_entries,
            "input_hashes_before": dict(before_inputs), "input_hashes_after": dict(after_inputs),
        }
        manifest["manifest_identity"] = content_hash(manifest)
        errors = validate_complete_manifest(manifest)
        if errors:
            raise RankingProvenanceError("manifest 不合法：" + ", ".join(errors))
        self.final_dir.parent.mkdir(parents=True, exist_ok=True)
        if self.final_dir.exists():
            raise RankingProvenanceError("final run 目錄已存在")
        created_rankings: list[Path] = []
        try:
            # 先發布不可覆寫 ranking；若後續失敗，清掉本 run 的全部硬連結。
            for entry in manifest_entries:
                staged = self.staging_dir / "rankings" / Path(entry["ranking_artifact"]["path"]).name
                final = _safe_repo_path(self.project_root, entry["ranking_artifact"]["path"])
                final.parent.mkdir(parents=True, exist_ok=True)
                os.link(staged, final)
                created_rankings.append(final)
            shutil.copytree(self.staging_dir / "model_snapshots", self.final_dir / "model_snapshots", dirs_exist_ok=False)
            shutil.copytree(self.staging_dir / "receipts", self.final_dir / "receipts", dirs_exist_ok=False)
            manifest_path = self.final_dir / "COMPLETE.manifest.json"
            _atomic_create(manifest_path, canonical_encode(manifest))
        except Exception as error:
            for path in reversed(created_rankings):
                path.unlink(missing_ok=True)
            if self.final_dir.exists():
                shutil.rmtree(self.final_dir)
            self.fail("publish_failed")
            raise RankingProvenanceError("bundle publish failed and rolled back") from error
        shutil.rmtree(self.staging_dir)
        return manifest_path


def validate_complete_manifest(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not _exact_keys(payload, _MANIFEST_FIELDS):
        errors.append("manifest_fields")
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION or payload.get("status") != "COMPLETE":
        errors.append("manifest_status")
    planned_rankings = payload.get("planned_rankings")
    if (
        not isinstance(planned_rankings, list)
        or not planned_rankings
        or any(not isinstance(item, str) or not item.startswith("ranking_") or not item.endswith(".csv") for item in planned_rankings)
        or len(set(planned_rankings)) != len(planned_rankings)
    ):
        errors.append("planned_rankings")
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries")
    else:
        dates: set[str] = set()
        artifacts: set[str] = set()
        receipts: set[str] = set()
        for entry in entries:
            if not isinstance(entry, Mapping):
                errors.append("entry")
                continue
            date_text = entry.get("ranking_date")
            artifact = entry.get("ranking_artifact")
            receipt = entry.get("receipt")
            if not isinstance(date_text, str) or date_text in dates:
                errors.append("duplicate_date")
            dates.add(str(date_text))
            if not _exact_keys(artifact, {"path", "sha256"}) or not _valid_relative_path(artifact.get("path")) or artifact["path"] in artifacts:
                errors.append("artifact")
            elif not _valid_hash(artifact.get("sha256")):
                errors.append("artifact_hash")
            artifacts.add(str(artifact.get("path")))
            if (
                not _exact_keys(receipt, {"path", "sha256", "receipt_identity"})
                or not _valid_relative_path(receipt.get("path"))
                or receipt["path"] in receipts
                or not _valid_hash(receipt.get("sha256"))
                or not _valid_hash(receipt.get("receipt_identity"))
            ):
                errors.append("receipt")
            receipts.add(str(receipt.get("path")))
    expected = content_hash({key: value for key, value in payload.items() if key != "manifest_identity"})
    if payload.get("manifest_identity") != expected:
        errors.append("manifest_identity")
    if not isinstance(payload.get("input_hashes_before"), Mapping) or payload.get("input_hashes_before") != payload.get("input_hashes_after"):
        errors.append("input_hash_drift")
    if isinstance(planned_rankings, list) and isinstance(entries, list):
        if [str(item.get("ranking_artifact", {}).get("path", "")).split("/")[-1] if isinstance(item, Mapping) else "" for item in entries] != planned_rankings:
            errors.append("planned_ranking_entry_mismatch")
    return errors


def verify_complete_bundle(project_root: Path, manifest_path: Path) -> list[str]:
    """讀取已 COMPLETE 的 bundle，逐一驗證 receipt/manifest/artifact bytes。"""

    errors: list[str] = []
    try:
        raw = manifest_path.read_bytes()
        if raw != canonical_encode(json.loads(raw.decode("utf-8"))):
            return ["manifest_noncanonical"]
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ["manifest_unreadable"]
    errors.extend(validate_complete_manifest(manifest))
    try:
        if (
            manifest_path.name != "COMPLETE.manifest.json"
            or manifest_path.parent.parent.name != "runs"
            or manifest_path.parent.parent.parent.name != ".ranking-provenance-v1"
        ):
            raise RankingProvenanceError("manifest path 不符合 bundle layout")
        output_dir = manifest_path.parent.parent.parent.parent
        planned_rankings = list(manifest["planned_rankings"])
        expected_plan = batch_plan_id(
            run_identity=str(manifest["run_identity"]),
            scenario=str(manifest["scenario"]),
            producer_entrypoint=str(manifest["producer_entrypoint"]),
            planned_rankings=planned_rankings,
        )
        if manifest.get("batch_plan_id") != expected_plan:
            errors.append("batch_plan_recompute_mismatch")
    except (KeyError, RankingProvenanceError):
        return sorted(set(errors + ["manifest_bundle_layout"]))
    for index, entry in enumerate(manifest.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        try:
            expected_basename = planned_rankings[index]
            expected_date = expected_basename.removeprefix("ranking_").removesuffix(".csv")
            expected_artifact = _repo_relative(project_root, output_dir / expected_basename)
            expected_receipt = _repo_relative(
                project_root, manifest_path.parent / "receipts" / _receipt_basename(expected_date)
            )
            if (
                entry.get("ranking_date") != expected_date
                or entry.get("ranking_artifact", {}).get("path") != expected_artifact
                or entry.get("receipt", {}).get("path") != expected_receipt
            ):
                errors.append("manifest_planned_binding_mismatch")
            artifact_path = _safe_repo_path(project_root, entry["ranking_artifact"]["path"])
            receipt_path = _safe_repo_path(project_root, entry["receipt"]["path"])
            if sha256_file(artifact_path) != entry["ranking_artifact"]["sha256"]:
                errors.append("artifact_hash_drift")
            if sha256_file(receipt_path) != entry["receipt"]["sha256"]:
                errors.append("receipt_hash_drift")
            receipt_raw = receipt_path.read_bytes()
            if receipt_raw != canonical_encode(json.loads(receipt_raw.decode("utf-8"))):
                errors.append("receipt_noncanonical")
                continue
            receipt = json.loads(receipt_raw.decode("utf-8"))
            errors.extend(validate_receipt(receipt))
            if (
                receipt.get("batch_plan_id") != manifest.get("batch_plan_id")
                or receipt.get("run_identity") != manifest.get("run_identity")
                or receipt.get("scenario") != manifest.get("scenario")
                or receipt.get("capture_mode") != manifest.get("capture_mode")
                or receipt.get("ranking_date") != expected_date
                or receipt.get("ranking_artifact", {}).get("path") != expected_artifact
                or receipt.get("producer", {}).get("entrypoint") != manifest.get("producer_entrypoint")
            ):
                errors.append("receipt_manifest_identity_mismatch")
            model_path = _safe_repo_path(project_root, receipt.get("model", {}).get("path", ""))
            if not model_path.is_file() or sha256_file(model_path) != receipt.get("model", {}).get("sha256"):
                errors.append("model_snapshot_hash_drift")
            errors.extend(verify_ranking_semantics(artifact_path, receipt.get("top_n_policy", {})))
            if receipt.get("ranking_artifact") != entry.get("ranking_artifact") or receipt.get("receipt_identity") != entry["receipt"].get("receipt_identity"):
                errors.append("manifest_receipt_mismatch")
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError, RankingProvenanceError):
            errors.append("bundle_entry_unreadable")
    return sorted(set(errors))


def main() -> int:
    """只驗證既有 COMPLETE bundle；不重跑 ranking、也不寫入資料。"""

    parser = argparse.ArgumentParser(description="verify a ranking provenance COMPLETE bundle")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--verify-complete-bundle", required=True)
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()
    manifest = Path(args.verify_complete_bundle)
    if not manifest.is_absolute():
        manifest = project_root / manifest
    errors = verify_complete_bundle(project_root, manifest)
    print(json.dumps({"status": "OK" if not errors else "INVALID", "errors": errors}, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

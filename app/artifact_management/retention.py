"""建立 artifact inventory，並以明確 policy 做 retention dry-run。

本模組只讀取檔案 metadata 與 manifest 內容，不提供刪除、搬移或壓縮 API。
所有輸出路徑都是 inventory root-relative，避免把本機絕對路徑寫進共享 artifact。
"""

from __future__ import annotations

import fnmatch
import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:  # pragma: no cover - requirements.txt 提供 PyYAML，保留 read-only fallback
    yaml = None


SCHEMA_VERSION = "artifact-retention-inventory.v1"
POLICY_SCHEMA_VERSION = "artifact-retention-policy.v1"


@dataclass(frozen=True)
class RetentionPolicy:
    """控制分類的 policy；policy 不包含任何 mutation 行為。"""

    recent_days: int = 7
    archive_after_days: int = 30
    delete_after_days: int = 90
    protected_globs: tuple[str, ...] = (
        "latest*",
        "*latest*",
        "ranking_????-??-??.*",
        "daily_report_????-??-??.*",
        "ranking.*",
        "daily_report.*",
        "*baseline*",
        "models/*",
        "*/models/*",
    )
    protected_directories: tuple[str, ...] = ("models",)
    manifest_globs: tuple[str, ...] = (
        "*manifest*.json",
        "*manifest*.yaml",
        "*manifest*.yml",
    )

    def __post_init__(self) -> None:
        if self.recent_days < 0:
            raise ValueError("recent_days 不可小於 0")
        if self.archive_after_days < self.recent_days:
            raise ValueError("archive_after_days 不可早於 recent_days")
        if self.delete_after_days < self.archive_after_days:
            raise ValueError("delete_after_days 不可早於 archive_after_days")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RetentionPolicy":
        """從 policy schema 建立 policy，未知欄位拒絕以避免拼字錯誤靜默失效。"""
        schema_version = value.get("schema_version", POLICY_SCHEMA_VERSION)
        if schema_version != POLICY_SCHEMA_VERSION:
            raise ValueError(f"不支援的 policy schema: {schema_version}")
        allowed = {
            "schema_version",
            "recent_days",
            "archive_after_days",
            "delete_after_days",
            "protected_globs",
            "protected_directories",
            "manifest_globs",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"policy 含未知欄位: {', '.join(unknown)}")

        def string_tuple(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
            raw = value.get(key, default)
            if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
                raise ValueError(f"policy.{key} 必須是字串陣列")
            return tuple(raw)

        return cls(
            recent_days=int(value.get("recent_days", cls.recent_days)),
            archive_after_days=int(value.get("archive_after_days", cls.archive_after_days)),
            delete_after_days=int(value.get("delete_after_days", cls.delete_after_days)),
            protected_globs=string_tuple("protected_globs", cls.protected_globs),
            protected_directories=string_tuple("protected_directories", cls.protected_directories),
            manifest_globs=string_tuple("manifest_globs", cls.manifest_globs),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = POLICY_SCHEMA_VERSION
        return payload


DEFAULT_POLICY = RetentionPolicy()


@dataclass(frozen=True)
class _FileRecord:
    path: str
    directory: str
    size_bytes: int
    modified_at: str
    date: str
    age_days: int
    retention_reason: str
    retention_reasons: tuple[str, ...]
    candidate_action: str


def load_policy(path: Path | None) -> RetentionPolicy:
    """讀取 JSON policy；未指定時使用程式內建的明確預設 policy。"""
    if path is None:
        return DEFAULT_POLICY
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"policy 不是有效 JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("policy JSON 頂層必須是 object")
    return RetentionPolicy.from_dict(payload)


def _parse_as_of(value: date | str | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() or "."


def _iter_files(root: Path) -> list[Path]:
    """只走訪 root 內的實體檔案，不追蹤 symlink directory。"""
    paths: list[Path] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if not (Path(directory) / name).is_symlink())
        paths.extend(
            Path(directory) / name
            for name in sorted(filenames)
            if not (Path(directory) / name).is_symlink()
        )
    return sorted(paths, key=lambda item: _relative_path(item, root))


def _matches_glob(relative_path: str, name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(name, pattern) for pattern in patterns)


def _manifest_paths(files: list[Path], root: Path, policy: RetentionPolicy) -> set[str]:
    """找出 manifest 本身與其 JSON 內引用的 root-relative artifact。"""
    protected: set[str] = set()
    for manifest in files:
        relative = _relative_path(manifest, root)
        if not _matches_glob(relative, manifest.name, policy.manifest_globs):
            continue
        protected.add(relative)
        try:
            content = manifest.read_text(encoding="utf-8")
            if manifest.suffix.lower() == ".json":
                payload = json.loads(content)
            elif yaml is not None:
                payload = yaml.safe_load(content)
            else:
                continue
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            continue
        except Exception as exc:
            if yaml is None or not isinstance(exc, yaml.YAMLError):
                raise
            continue
        for value in _string_values(payload):
            referenced = _resolve_reference(value, manifest, root)
            if referenced is None:
                continue
            if referenced.is_file():
                protected.add(_relative_path(referenced, root))
            elif referenced.is_dir():
                protected.update(_relative_path(item, root) for item in _iter_files(referenced))
    return protected


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _string_values(child)


def _resolve_reference(value: str, manifest: Path, root: Path) -> Path | None:
    candidate = value.strip()
    if not candidate or "\n" in candidate or "\r" in candidate:
        return None
    candidate_path = Path(candidate).expanduser()
    root_resolved = root.resolve()
    options: list[Path] = []
    if candidate_path.is_absolute():
        options.append(candidate_path)
    else:
        options.extend((manifest.parent / candidate_path, root / candidate_path))
        parts = candidate_path.parts
        if parts and parts[0] == root.name:
            options.append(root.joinpath(*parts[1:]))
    for option in options:
        try:
            resolved = option.resolve()
            resolved.relative_to(root_resolved)
        except (OSError, ValueError):
            continue
        if resolved.exists():
            return resolved
    return None


def _protection_reasons(relative: str, policy: RetentionPolicy, manifest_paths: set[str]) -> list[str]:
    name = Path(relative).name
    parts = Path(relative).parts
    reasons: list[str] = []
    if relative in manifest_paths:
        reasons.append("manifest 或 manifest 引用檔")
    if any(part.lower() in {item.lower() for item in policy.protected_directories} for part in parts[:-1]):
        reasons.append("模型目錄保護")
    if _matches_glob(relative, name, policy.protected_globs):
        reasons.append("policy 保護 pattern")
    return reasons


def _classify(age_days: int, reasons: list[str], policy: RetentionPolicy) -> tuple[str, str]:
    if reasons:
        return "keep", "; ".join(reasons)
    if age_days <= policy.recent_days:
        return "keep", f"最近 {policy.recent_days} 日內"
    if age_days <= policy.archive_after_days:
        return "keep", f"尚未超過 {policy.archive_after_days} 日 archive 閾值"
    if age_days <= policy.delete_after_days:
        return "archive_candidate", f"超過 {policy.archive_after_days} 日 archive 閾值"
    return "delete_candidate", f"超過 {policy.delete_after_days} 日 delete 閾值"


def _record_file(path: Path, root: Path, as_of: date, policy: RetentionPolicy, manifest_paths: set[str]) -> _FileRecord:
    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    modified_date = modified.date()
    age_days = max(0, (as_of - modified_date).days)
    relative = _relative_path(path, root)
    reasons = _protection_reasons(relative, policy, manifest_paths)
    action, reason = _classify(age_days, reasons, policy)
    return _FileRecord(
        path=relative,
        directory=_relative_path(path.parent, root),
        size_bytes=stat.st_size,
        modified_at=modified.isoformat(),
        date=modified_date.isoformat(),
        age_days=age_days,
        retention_reason=reason,
        retention_reasons=tuple(reasons) if reasons else (reason,),
        candidate_action=action,
    )


def build_inventory(
    root: Path,
    policy: RetentionPolicy = DEFAULT_POLICY,
    as_of: date | str | None = None,
) -> dict[str, Any]:
    """建立 deterministic inventory；此函式不會寫入 root，也不會改變任何檔案。"""
    root = root.expanduser()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"artifact root 不存在或不是目錄: {root}")
    root = root.resolve()
    observed_date = _parse_as_of(as_of)
    paths = _iter_files(root)
    manifest_paths = _manifest_paths(paths, root, policy)
    records = [_record_file(path, root, observed_date, policy, manifest_paths) for path in paths]

    action_counts = Counter(record.candidate_action for record in records)
    bytes_by_action: Counter[str] = Counter()
    for record in records:
        bytes_by_action[record.candidate_action] += record.size_bytes

    directory_records: dict[str, list[_FileRecord]] = defaultdict(list)
    for record in records:
        directory_records[record.directory].append(record)
    directories: list[dict[str, Any]] = []
    for directory in sorted(directory_records):
        items = directory_records[directory]
        dates = [item.date for item in items]
        directory_actions = Counter(item.candidate_action for item in items)
        directories.append(
            {
                "directory": directory,
                "file_count": len(items),
                "bytes": sum(item.size_bytes for item in items),
                "oldest_date": min(dates),
                "newest_date": max(dates),
                "retention_reasons": sorted({reason for item in items for reason in item.retention_reasons}),
                "candidate_actions": dict(sorted(directory_actions.items())),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "dry_run": True,
        "root": root.name,
        "as_of": observed_date.isoformat(),
        "policy": policy.to_dict(),
        "summary": {
            "file_count": len(records),
            "bytes": sum(record.size_bytes for record in records),
            "action_counts": dict(sorted(action_counts.items())),
            "bytes_by_action": dict(sorted(bytes_by_action.items())),
            "protected_file_count": action_counts.get("keep", 0),
            "archive_candidate_bytes": bytes_by_action.get("archive_candidate", 0),
            "reclaimable_bytes": bytes_by_action.get("delete_candidate", 0),
        },
        "directories": directories,
        "files": [
            {
                **asdict(record),
                "retention_reasons": list(record.retention_reasons),
            }
            for record in records
        ],
    }


def render_summary(inventory: dict[str, Any]) -> str:
    """產生精簡人類摘要，不列出可能很長的檔案清單。"""
    summary = inventory["summary"]
    counts = summary["action_counts"]
    bytes_by_action = summary["bytes_by_action"]
    lines = [
        f"Artifact retention dry-run｜root={inventory['root']}｜as_of={inventory['as_of']}",
        f"檔案={summary['file_count']}｜bytes={summary['bytes']}｜保護={summary['protected_file_count']}",
        (
            "分類："
            f"keep={counts.get('keep', 0)} ({bytes_by_action.get('keep', 0)} bytes)，"
            f"archive_candidate={counts.get('archive_candidate', 0)} "
            f"({bytes_by_action.get('archive_candidate', 0)} bytes)，"
            f"delete_candidate={counts.get('delete_candidate', 0)} "
            f"({bytes_by_action.get('delete_candidate', 0)} bytes)"
        ),
        f"可回收估算（僅 delete candidates）={summary['reclaimable_bytes']} bytes",
        "本次未刪除、搬移或壓縮任何檔案。",
    ]
    return "\n".join(lines)

"""Automation pipeline 的 deterministic 純政策。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Mapping


VALID_RESOURCE_PROFILES = frozenset({"local_safe", "standard", "host_full"})


@dataclass(frozen=True)
class PipelineWindowPolicy:
    """保留日期窗口順序，方便與既有 status／command 契約比較。"""

    window_items: tuple[tuple[str, str], ...]
    source: str | None = None
    lookback_days: int | None = None

    def as_dict(self) -> dict[str, str]:
        return dict(self.window_items)


@dataclass(frozen=True)
class ResourceProfilePolicy:
    """資源模式對 daily／retrain／monitor 的純判定結果。"""

    profile: str
    block_daily: bool
    block_retrain: bool
    skip_heavy_monitor: bool


def pipeline_window_override(*, start_date: str | None, end_date: str | None) -> PipelineWindowPolicy:
    window: dict[str, str] = {}
    if start_date:
        window["start_date"] = start_date
    if end_date:
        window["end_date"] = end_date
    return PipelineWindowPolicy(tuple(window.items()))


def apply_daily_default_pipeline_window(
    window: Mapping[str, str],
    *,
    lookback_days_value: Any,
    today: date,
) -> PipelineWindowPolicy:
    lookback_days = int(lookback_days_value or 0)
    if lookback_days <= 0:
        return PipelineWindowPolicy(tuple(window.items()))

    result = dict(window)
    end_text = result.get("end_date") or today.isoformat()
    if "end_date" not in result:
        result["end_date"] = end_text
    if "start_date" not in result:
        end_date = datetime.strptime(end_text, "%Y-%m-%d").date()
        result["start_date"] = (end_date - timedelta(days=lookback_days)).isoformat()
    return PipelineWindowPolicy(
        tuple(result.items()),
        source="daily.pipeline_lookback_days",
        lookback_days=lookback_days,
    )


def pipeline_run_command(window: Mapping[str, str]) -> tuple[str, ...]:
    command = ["python", "-m", "app.pipeline_cli", "run"]
    if "start_date" in window:
        command.extend(["--start-date", window["start_date"]])
    if "end_date" in window:
        command.extend(["--end-date", window["end_date"]])
    return tuple(command)


def resolve_resource_profile(
    *,
    explicit_profile: str | None,
    env_profile: str | None,
    config_profile: Any,
) -> str:
    profile = explicit_profile or env_profile or config_profile or "standard"
    normalized = str(profile).strip().lower()
    if normalized not in VALID_RESOURCE_PROFILES:
        raise ValueError(f"未知 resource profile：{normalized}")
    return normalized


def evaluate_resource_profile(
    *,
    profile: str,
    dry_run: bool,
    has_pipeline_window_override: bool,
    allow_full_etl: bool,
    allow_heavy_retrain: bool,
    allow_heavy_monitor: bool,
) -> ResourceProfilePolicy:
    normalized = resolve_resource_profile(
        explicit_profile=profile,
        env_profile=None,
        config_profile=None,
    )
    is_local_safe = normalized == "local_safe"
    return ResourceProfilePolicy(
        profile=normalized,
        block_daily=(
            not dry_run
            and is_local_safe
            and not allow_full_etl
            and not has_pipeline_window_override
        ),
        block_retrain=not dry_run and is_local_safe and not allow_heavy_retrain,
        skip_heavy_monitor=is_local_safe and not allow_heavy_monitor,
    )

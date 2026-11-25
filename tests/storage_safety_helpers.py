"""容量 guard 的共用健康內建卷 fixture；不改產品缺值即拒絕的契約。"""

from dataclasses import dataclass
import sys
import time

from app.storage_safety import Sample


@dataclass(frozen=True)
class HealthySample(Sample):
    """測試明確提供健康內建卷，保留呼叫端覆寫與缺值反例。"""

    boot_volume_path: str | None = "/System/Volumes/Data" if sys.platform == "darwin" else "/"
    boot_volume_total_bytes: int | None = 256 * 1024**3
    boot_volume_free_bytes: int | None = 64 * 1024**3
    boot_volume_raw_free_bytes: int | None = 60 * 1024**3
    boot_volume_capacity_source: str | None = (
        "macos_foundation_important_usage" if sys.platform == "darwin" else "shutil.disk_usage"
    )
    host_boot_shared_container: bool | None = False


def healthy_sample() -> HealthySample:
    """沿既有 cache／temp 測試的 workload 卷基線，只補內建卷。"""

    return HealthySample(time.time(), 0, 0, 10_000_000, 9_000_000, 0, 0)

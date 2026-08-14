from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_RESEARCH_SPINE = (
    PROJECT_ROOT / "artifacts" / "autonomous_research" / "research_spine"
)


def _research_spine_inventory(root: Path = CANONICAL_RESEARCH_SPINE) -> dict[str, str]:
    """保存完整path set與file bytes；symlink只記link本身，不追出repo。"""
    if not root.exists():
        return {".": "missing"}
    inventory: dict[str, str] = {".": "directory"}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            inventory[relative] = "symlink:" + os.readlink(path)
        elif path.is_dir():
            inventory[relative + "/"] = "directory"
        elif path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            inventory[relative] = "sha256:" + digest.hexdigest()
    return inventory


@pytest.fixture(scope="session", autouse=True)
def preserve_canonical_research_spine() -> None:
    """即使測試失敗，session finalizer仍拒絕canonical Research Spine污染。"""
    before = _research_spine_inventory()
    yield
    after = _research_spine_inventory()
    assert after == before, {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": sorted(
            path for path in set(before) & set(after) if before[path] != after[path]
        ),
    }

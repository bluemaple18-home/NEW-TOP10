from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from app.research import shadow_replay_regime_feasibility as feasibility
from app.research.contracts import content_hash


def _row(trade_date: str, regime: str, tags: list[str]) -> dict[str, object]:
    return {"trade_date": trade_date, "as_of_date": trade_date, "base_regime": regime, "family_tags": tags}


def test_episode_matrix_reuses_canonical_helper_and_never_merges_episodes(monkeypatch) -> None:
    calls: list[tuple[int, set[str]]] = []

    def fake_helper(allowed_dates, episode_by_date, trade_dates, *, horizon, entry_delay_trade_days):
        calls.append((horizon, set(allowed_dates)))
        assert entry_delay_trade_days == 1
        return {min(allowed_dates)}

    monkeypatch.setattr(feasibility.strategy_matrix, "exact_horizon_safe_ranking_dates", fake_helper)
    rows = [
        _row("2026-01-02", "NARROW_LEADER", ["BIG_BULL"]),
        _row("2026-01-05", "NARROW_LEADER", ["BIG_BULL"]),
        _row("2026-01-06", "RISK_OFF", []),
        _row("2026-01-07", "NARROW_LEADER", ["BIG_BULL"]),
    ]

    matrix = feasibility.episode_matrix(rows, [date(2026, 1, day) for day in (2, 5, 6, 7)])

    fixed = [item for item in matrix if item["identity"] == "NARROW_LEADER|BIG_BULL"]
    assert [item["trade_date_count"] for item in fixed] == [2, 1]
    assert all(item["shared_dates"] for item in fixed)
    assert calls == [(10, {"2026-01-02", "2026-01-05"}), (20, {"2026-01-02", "2026-01-05"}), (10, {"2026-01-06"}), (20, {"2026-01-06"}), (10, {"2026-01-07"}), (20, {"2026-01-07"})]


def test_validation_rejects_false_lineage_and_absolute_path() -> None:
    payload = {
        "schema_version": feasibility.SCHEMA_VERSION,
        "audit_id": "",
        "status": "NO-GO_NO_ELIGIBLE_REGIME",
        "lineage_authority_status": "PROVEN",
        "episodes": [],
        "source": "/tmp/forbidden",
    }
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})

    errors = feasibility.validate_audit(payload)

    assert "LINEAGE_AUTHORITY_MUST_REMAIN_UNPROVEN" in errors
    assert "ABSOLUTE_PATH_FORBIDDEN:/tmp/forbidden" in errors


def test_canonical_encoder_is_byte_deterministic() -> None:
    payload = {
        "schema_version": feasibility.SCHEMA_VERSION,
        "audit_id": "",
        "status": "NO-GO_NO_ELIGIBLE_REGIME",
        "lineage_authority_status": "UNPROVEN",
        "episodes": [],
    }
    payload["audit_id"] = content_hash(payload, omit={"audit_id"})

    assert feasibility.encode_audit(payload) == feasibility.encode_audit(dict(payload))


def _git(root: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def _nested_committed_symlink(
    tmp_path: Path,
    *,
    external: bool,
) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    nested = root / "nested"
    nested.mkdir(parents=True)
    relative = Path("nested/source.json")
    (root / relative).write_text('{"status":"committed"}\n', encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", relative.as_posix())
    _git(
        root,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    target = (
        tmp_path / "external-target"
        if external
        else root / "internal-target"
    )
    target.mkdir()
    (target / "source.json").write_text(
        '{"status":"committed"}\n',
        encoding="utf-8",
    )
    shutil.rmtree(nested)
    nested.symlink_to(target, target_is_directory=True)
    return root, relative


@pytest.mark.parametrize("external", [False, True])
def test_committed_record_rejects_nested_symlink(
    tmp_path: Path,
    external: bool,
) -> None:
    root, relative = _nested_committed_symlink(tmp_path, external=external)

    with pytest.raises(feasibility.RegimeFeasibilityError, match="SOURCE_SYMLINK"):
        feasibility._committed_record(root, relative)


@pytest.mark.parametrize("external", [False, True])
def test_authority_record_rejects_nested_symlink(
    tmp_path: Path,
    external: bool,
) -> None:
    root, relative = _nested_committed_symlink(tmp_path, external=external)

    with pytest.raises(feasibility.RegimeFeasibilityError, match="SOURCE_SYMLINK"):
        feasibility._authority_record(root, relative)


@pytest.mark.parametrize("external", [False, True])
def test_authorized_evidence_rejects_nested_symlink(
    tmp_path: Path,
    external: bool,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = (
        tmp_path / "external-docs"
        if external
        else root / "internal-docs"
    )
    evidence = target / feasibility.EVIDENCE_RELATIVE.relative_to("docs")
    evidence.parent.mkdir(parents=True)
    evidence.write_text("{}\n", encoding="utf-8")
    (root / "docs").symlink_to(target, target_is_directory=True)

    with pytest.raises(feasibility.RegimeFeasibilityError, match="SOURCE_SYMLINK"):
        feasibility._authorized_evidence(feasibility.EVIDENCE_RELATIVE, root)


def test_cli_invalid_authority_root_is_structured_and_path_free(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.research.shadow_replay_regime_feasibility",
            "--authority-root",
            str(tmp_path),
            "--verify",
            feasibility.EVIDENCE_RELATIVE.as_posix(),
        ],
        cwd=feasibility.PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    result = json.loads(completed.stdout)
    assert result == {"errors": ["AUTHORITY_ROOT_INVALID"], "status": "FAIL"}
    combined = completed.stdout + completed.stderr
    assert "Traceback" not in combined
    assert str(tmp_path) not in combined

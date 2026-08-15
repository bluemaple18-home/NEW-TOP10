from __future__ import annotations

from datetime import date

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

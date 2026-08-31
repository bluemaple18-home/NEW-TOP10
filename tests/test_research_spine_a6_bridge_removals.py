"""A6 bridge-specific removal evidence：每條 bridge 的 consumer seam 必須仍可定位。"""

from pathlib import Path

from app.research.a6_closure import PROJECT_ROOT, SOURCE_DERIVED_BRIDGE_SURFACES


def _assert_surface(bridge_id: str) -> None:
    relative_path, marker = SOURCE_DERIVED_BRIDGE_SURFACES[bridge_id]
    source = PROJECT_ROOT / relative_path
    assert source.is_file()
    assert marker in source.read_text(encoding="utf-8")


def test_history_compatibility_projection_removal_evidence() -> None:
    _assert_surface("history_compatibility_projection")


def test_legacy_run_history_jsonl_migration_removal_evidence() -> None:
    _assert_surface("legacy_run_history_jsonl_migration")


def test_legacy_run_history_json_migration_removal_evidence() -> None:
    _assert_surface("legacy_run_history_json_migration")


def test_research_map_run_history_backfill_removal_evidence() -> None:
    _assert_surface("research_map_run_history_backfill")


def test_research_map_backfill_verifier_removal_evidence() -> None:
    _assert_surface("research_map_backfill_verifier")


def test_fog_map_run_history_reader_removal_evidence() -> None:
    _assert_surface("fog_map_run_history_reader")


def test_campaign_progress_run_history_reader_removal_evidence() -> None:
    _assert_surface("campaign_progress_run_history_reader")


def test_weekend_training_run_history_reader_removal_evidence() -> None:
    _assert_surface("weekend_training_run_history_reader")


def test_liquidity_v2_run_history_reader_removal_evidence() -> None:
    _assert_surface("liquidity_v2_run_history_reader")


def test_legacy_run_history_appenders_removal_evidence() -> None:
    _assert_surface("legacy_run_history_appenders")


def test_liquidity_v2_batch_run_history_bridge_removal_evidence() -> None:
    _assert_surface("liquidity_v2_batch_run_history_bridge")


def test_research_fog_map_verifier_reader_removal_evidence() -> None:
    _assert_surface("research_fog_map_verifier_reader")


def test_combo_effectiveness_run_history_reader_removal_evidence() -> None:
    _assert_surface("combo_effectiveness_run_history_reader")

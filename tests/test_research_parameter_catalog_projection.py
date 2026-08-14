from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app.research import map_contract
from app.research.parameter_catalog import (
    assert_legacy_parameter_projection,
    base_scenario_dimension_grid,
    entrypoint_cli_defaults,
    executable_parameter_dimensions,
    load_parameter_catalog,
    parameter_catalog_hash,
    validate_executable_parameters,
    v2_default_coordinates,
    v2_dimension_values,
    validation_profiles_compatibility,
)
from scripts import run_autonomous_research as research
from scripts import run_backtest_strategy_matrix as matrix


def contract() -> dict:
    return json.loads(
        (research.PROJECT_ROOT / "config/regime_research_contract.json").read_text(encoding="utf-8")
    )


def test_catalog_projections_preserve_coverage_public_contract() -> None:
    assert load_parameter_catalog()["authority_mode"] == "SOLE_AUTHORING_AUTHORITY"
    assert base_scenario_dimension_grid() == map_contract.SCENARIO_DIMENSION_GRID
    assert v2_dimension_values() == map_contract.V2_DIMENSION_VALUES
    assert v2_default_coordinates() == map_contract.V2_DEFAULT_COORDINATES
    assert len(map_contract.SCENARIO_DIMENSION_GRID) == 81
    assert map_contract.expansion_multiplier() == 112
    assert map_contract.expanded_scenarios_per_topic() == 9_072
    assert parameter_catalog_hash() == parameter_catalog_hash()


def test_ordered_coverage_combo_identities_do_not_drift() -> None:
    topic = {"topic_id": "research:alpha"}
    base_ids = [
        map_contract.combo_id(topic, dimensions)
        for dimensions in map_contract.SCENARIO_DIMENSION_GRID
    ]
    assert research.canonical_json_hash(base_ids) == (
        "sha256:95ea78094da5b1def9133bc98cc347c7e439175418d881b573595dc9447807fc"
    )
    assert base_ids[0] == "alpha|horizon_3|stop_none|take_profit_none|group_exposure_none"
    assert base_ids[-1] == "alpha|horizon_10|stop_0.12|take_profit_0.25|group_exposure_0.55"


def test_formal_universe_and_statistical_family_identities_do_not_drift() -> None:
    summary = research.parameter_universe_summary(contract())
    authority = research.statistical_family_contract(contract())
    assert len(executable_parameter_dimensions()) == 4
    assert summary["legal_combination_count"] == 720
    assert summary["combination_id_hash"] == (
        "sha256:78cd9b8b6fa39935f9037d5b4c8dde3fcc2ae39955414aa51bda96dafb69f6b4"
    )
    assert summary["parameter_space_hash"] == (
        "sha256:bcf2e751de5b0cef85eb2513eda044d3d063594c4a6197c1cea689f330b5fd0e"
    )
    assert authority["global_family_id"] == (
        "sha256:79899da01ead21b31ebd48571e2e3b6460f65946dad86bab7e5a1d546a0b4baa"
    )
    assert authority["parameter_catalog_hash"] == parameter_catalog_hash()


def test_legacy_parameter_projection_is_cache_not_authority() -> None:
    current = contract()
    assert_legacy_parameter_projection(current)
    drifted = deepcopy(current)
    drifted["parameter_universe"]["dimensions"][0]["allowed_values"].append(99)
    with pytest.raises(ValueError, match="canonical catalog"):
        research.parameter_universe_summary(drifted)


def test_formal_contract_dimensions_are_generated_catalog_projection() -> None:
    current = contract()
    provenance = current["parameter_universe"]["dimensions_projection"]
    assert provenance == {
        "source": "config/research_parameter_catalog.json",
        "generator": "app.research.parameter_catalog.executable_parameter_dimensions",
        "status": "GENERATED_COMPATIBILITY_PROJECTION",
    }
    assert current["parameter_universe"]["dimensions"] == executable_parameter_dimensions()
    assert current["parameter_universe"]["inventory_source"] == [
        "config/research_parameter_catalog.json"
    ]


def test_out_of_catalog_execution_values_fail_closed() -> None:
    with pytest.raises(ValueError, match="take_profit_pct 包含 catalog 外值"):
        validate_executable_parameters(
            {
                "horizon": [3],
                "stop_loss_pct": [None, 0.08],
                "take_profit_pct": [None, 0.12],
                "max_group_exposure": [None, 0.35],
            }
        )


def test_profiles_and_cli_defaults_are_catalog_projections() -> None:
    profiles = validation_profiles_compatibility()
    assert profiles == research.VALIDATION_PROFILES
    assert [len(research.validation_profile_combinations(
        row["horizons"], row["stop_loss_pcts"], row["take_profit_pcts"], row["max_group_exposures"]
    )) for row in profiles] == [81, 81, 81, 36]
    assert entrypoint_cli_defaults("autonomous_research") == {
        "horizon": "3,5,10",
        "stop_loss_pct": "none,0.08,0.12",
        "take_profit_pct": "none,0.15,0.25",
        "max_group_exposure": "none,0.35,0.55",
    }
    assert entrypoint_cli_defaults("strategy_matrix") == {
        "horizon": "3,5,10",
        "stop_loss_pct": "none,0.08",
        "take_profit_pct": "none,0.15",
        "max_group_exposure": "none,0.35",
    }
    assert matrix.MATRIX_CLI_DEFAULTS == entrypoint_cli_defaults("strategy_matrix")

"""Research Parameter Catalog 的唯一 authoring reader 與相容 projection。"""

from __future__ import annotations

import json
from functools import lru_cache
from itertools import product
from pathlib import Path
from typing import Any

from app.research.contracts import content_hash, validate_parameter_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = PROJECT_ROOT / "config" / "research_parameter_catalog.json"
CANONICAL_EXECUTABLE_PARAMETER_ORDER = (
    "horizon",
    "stop_loss_pct",
    "take_profit_pct",
    "max_group_exposure",
)


@lru_cache(maxsize=1)
def load_parameter_catalog() -> dict[str, Any]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    errors = validate_parameter_catalog(payload)
    if errors:
        raise ValueError("Research Parameter Catalog 無效：" + "; ".join(errors))
    return payload


def parameter_catalog_hash() -> str:
    return content_hash(load_parameter_catalog())


def _dimensions_by_id() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in load_parameter_catalog()["dimensions"]}


def _legacy_token(value: Any) -> str:
    return "none" if value is None else str(value)


def _runtime_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value


def base_scenario_dimension_grid() -> list[dict[str, str]]:
    dimensions = _dimensions_by_id()
    mappings = (
        ("horizon", "horizon"),
        ("stop_loss_pct", "stop_loss"),
        ("take_profit_pct", "take_profit"),
        ("max_group_exposure", "group_exposure"),
    )
    values = [dimensions[catalog_id]["coverage_values"] for catalog_id, _ in mappings]
    return [
        {legacy_id: _legacy_token(value) for (_, legacy_id), value in zip(mappings, items, strict=True)}
        for items in product(*values)
    ]


def v2_dimension_values() -> dict[str, list[str]]:
    dimensions = _dimensions_by_id()
    return {
        key: list(dimensions[key]["coverage_values"])
        for key in ("regime_gate", "risk_guard", "entry_filter")
    }


def v2_default_coordinates() -> dict[str, str]:
    dimensions = _dimensions_by_id()
    return {
        key: str(dimensions[key]["default_value"])
        for key in ("regime_gate", "risk_guard", "entry_filter")
    }


def executable_parameter_dimensions() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dimensions = _dimensions_by_id()
    for dimension_id in CANONICAL_EXECUTABLE_PARAMETER_ORDER:
        dimension = dimensions[dimension_id]
        if dimension["execution_support"] != "SUPPORTED":
            continue
        rows.append(
            {
                "id": dimension["id"],
                "name": dimension["name"],
                "research_level": dimension["research_level"],
                "product_semantics": dimension["product_semantics"],
                "data_type": (
                    "number_or_null" if dimension["data_type"] == "decimal" else dimension["data_type"]
                ),
                "allowed_values": [_runtime_value(value) for value in dimension["executable_values"]],
                "default_value": _runtime_value(dimension["default_value"]),
                "baseline_value": _runtime_value(dimension["default_value"]),
                "dependencies": [],
                "execution_status": "EXECUTABLE",
            }
        )
    return rows


def legacy_parameter_universe_projection(metadata: dict[str, Any]) -> dict[str, Any]:
    """由 catalog 生成舊 formal block；只保留 legacy hash 所需形狀。"""
    return {
        "inventory_status": metadata.get("inventory_status"),
        "declared_complete": bool(metadata.get("declared_complete")),
        "inventory_source": [
            "scripts/run_backtest_strategy_matrix.py",
            "scripts/run_autonomous_research.py::VALIDATION_PROFILES",
        ],
        "dimensions": executable_parameter_dimensions(),
        "invalid_combination_rules": list(metadata.get("invalid_combination_rules") or []),
        "expected_executable_legal_combination_count": int(
            metadata.get("expected_executable_legal_combination_count") or 0
        ),
        "blocked_dimensions": list(metadata.get("blocked_dimensions") or []),
    }


def assert_legacy_parameter_projection(contract: dict[str, Any]) -> None:
    """舊 regime block 只可作 generated cache；值域漂移立即拒絕。"""
    observed = contract.get("parameter_universe", {}).get("dimensions", [])
    expected = executable_parameter_dimensions()
    observed_projection = [
        {
            "id": row.get("id"),
            "allowed_values": row.get("allowed_values"),
            "default_value": row.get("default_value"),
            "baseline_value": row.get("baseline_value"),
            "execution_status": row.get("execution_status"),
        }
        for row in observed
    ]
    expected_projection = [
        {
            "id": row["id"],
            "allowed_values": row["allowed_values"],
            "default_value": row["default_value"],
            "baseline_value": row["baseline_value"],
            "execution_status": row["execution_status"],
        }
        for row in expected
    ]
    if observed_projection != expected_projection:
        raise ValueError("legacy parameter_universe projection 與 canonical catalog 不一致")


def validate_executable_parameters(parameters: dict[str, list[Any]]) -> None:
    dimensions = _dimensions_by_id()
    for parameter in CANONICAL_EXECUTABLE_PARAMETER_ORDER:
        values = parameters.get(parameter)
        if not isinstance(values, list) or not values:
            raise ValueError(f"{parameter} executable values 不可為空")
        allowed = {_runtime_value(value) for value in dimensions[parameter]["executable_values"]}
        unsupported = [value for value in values if value not in allowed]
        if unsupported:
            raise ValueError(f"{parameter} 包含 catalog 外值：{unsupported}")


def entrypoint_cli_defaults(entrypoint: str) -> dict[str, str]:
    defaults = load_parameter_catalog()["entrypoint_defaults"].get(entrypoint)
    if not isinstance(defaults, dict):
        raise ValueError(f"未知 research entrypoint：{entrypoint}")
    return {
        parameter: ",".join(_legacy_token(value) for value in values)
        for parameter, values in defaults.items()
    }


def validation_profiles_compatibility() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for profile in load_parameter_catalog()["validation_profiles"]:
        profiles.append(
            {
                "name": profile["id"],
                "title_suffix": profile["title_suffix"],
                "hypothesis_suffix": profile["hypothesis_suffix"],
                "score_bonus": float(profile["score_bonus"]),
                "horizons": ",".join(_legacy_token(value) for value in profile["horizon"]),
                "stop_loss_pcts": ",".join(_legacy_token(value) for value in profile["stop_loss_pct"]),
                "take_profit_pcts": ",".join(_legacy_token(value) for value in profile["take_profit_pct"]),
                "max_group_exposures": ",".join(
                    _legacy_token(value) for value in profile["max_group_exposure"]
                ),
            }
        )
    return profiles

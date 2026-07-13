from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import build_odd_lot_decision_suite as suite_builder
from scripts import verify_odd_lot_candidate_decision_report as candidate_verifier
from scripts import verify_odd_lot_exit_horizon_sensitivity_report as horizon_verifier
from scripts import verify_odd_lot_exit_strategy_report as strategy_verifier
from scripts import verify_odd_lot_regime_throttle_report as throttle_verifier


FIXTURE_DATE = "2026-07-13"
CAPITAL_LEVELS = "100000,300000,500000"
PROFILES = ("exit_horizon", "exit_strategy", "regime_throttle", "candidate_decision")
LEGACY_GOLDEN = {
    "exit_horizon": {
        "builder": {
            "valid": "320acfefce2175ea2888abffee0833055655d8c01241da69fca1ef5d053d47e7",
            "invalid": "15e5753258e2f074a449d7a439095864d2ed30926d4097f0a194b066892c2bc9",
        },
        "markdown": "58f59076b0b608c7713b50f4a7ed7076270c27c54371177a122d88541ac8a06a",
    },
    "exit_strategy": {
        "builder": {
            "valid": "542ae9e3142896ba6a9cf58a833c9c684dbc2a96ce27e643f43fc68ec094bd6e",
            "invalid": "bdd45c41046dc873d3e2a0d87b5492898bf2b51bb4d9589b094125be636d585d",
        },
        "markdown": "e174d89582149d74799d5e3433ac2922a4b6984d4e24a33c1e580d6a9240be55",
    },
    "regime_throttle": {
        "builder": {
            "valid": "8e144aaffb72cd1daa2c6bbe9130652e89abac1839cb0ca8e3ea94efd37aa283",
            "invalid": "564e7843d870371653a749fc3c7b03df799ed2052243c0a95d900cd14dcbe9e0",
        },
        "markdown": "0153e31e7c08c5bbb7ad3088fc96482d5acb2e6c634a464240ef027b0470ad73",
    },
    "candidate_decision": {
        "builder": {
            "valid": "1d5a4e09ed47214d574119550cc13ca9ad5c66ca688fe91bdcffb271979cf3c0",
            "invalid": "0eec384f7995e5382bb2d0c834bdc792f911a9bbe9585aeeee9949d1d6a51aca",
        },
        "markdown": "619bf1d2275972eb5ebe9576d8b49f7fbfe33385fa7da76169185ea33ab27bc8",
    },
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def normalized(payload: dict[str, Any], fixture_root: Path) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    result.pop("generated_at", None)

    def replace_fixture_root(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: replace_fixture_root(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace_fixture_root(item) for item in value]
        if isinstance(value, str):
            return value.replace(str(fixture_root), "<fixture-root>")
        return value

    return replace_fixture_root(result)


def fingerprint(payload: dict[str, Any], fixture_root: Path) -> str:
    encoded = json.dumps(
        normalized(payload, fixture_root),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_exit_strategy_fixture(root: Path) -> None:
    summaries = {
        "production_baseline": (0.10, -0.30),
        "production_ptp25_third": (0.12, -0.25),
        "candidate_baseline": (0.20, -0.40),
        "candidate_ptp25_third": (0.18, -0.20),
        "candidate_ptp25_half": (0.15, -0.22),
    }
    for capital in (100_000, 300_000, 500_000):
        for variant, (total_return, max_drawdown) in summaries.items():
            path = suite_builder.exit_strategy_artifact_path(variant, capital, FIXTURE_DATE)
            write_json(
                path,
                {
                    "summary": {
                        "total_return": total_return,
                        "max_drawdown": max_drawdown,
                        "trade_count": 12,
                        "win_rate": 0.6,
                        "avg_cash_weight": 0.25,
                        "below_minimum_odd_lot_count": 0,
                    }
                },
            )


def build_horizon_fixture(root: Path) -> None:
    candidate_exit = {20: (0.20, -0.20), 40: (0.30, -0.20), 60: (0.25, -0.25)}
    for horizon in suite_builder.HORIZONS:
        for kind in ("candidate_baseline", "candidate_exit", "production_exit"):
            total_return, max_drawdown = candidate_exit[horizon]
            if kind == "candidate_baseline":
                total_return += 0.02
                max_drawdown -= 0.05
            elif kind == "production_exit":
                total_return -= 0.02
            write_json(
                suite_builder.exit_horizon_artifact_path(kind, horizon, 300_000, FIXTURE_DATE),
                {
                    "summary": {
                        "total_return": total_return,
                        "max_drawdown": max_drawdown,
                        "trade_count": 12,
                        "skipped_count": 1,
                        "avg_cash_weight": 0.25,
                    }
                },
            )


def build_throttle_fixture(root: Path) -> None:
    summaries = {
        "baseline": (0.20, -0.30),
        "hc45": (0.21, -0.35),
        "hc55": (0.19, -0.35),
        "hc65": (0.18, -0.40),
    }
    for name, (total_return, max_drawdown) in summaries.items():
        write_json(
            suite_builder.regime_throttle_artifact_path(name, 300_000, FIXTURE_DATE),
            {
                "summary": {
                    "total_return": total_return,
                    "max_drawdown": max_drawdown,
                    "trade_count": 12,
                    "avg_gross_exposure": 0.6,
                    "avg_cash_weight": 0.4,
                },
                "daily": [
                    {
                        "entry_gross_exposure_limit": 0.45 if name == "hc45" else 0.75,
                        "entries": 2,
                    }
                ],
            },
        )


def build_source_reports(root: Path) -> dict[str, Path]:
    build_exit_strategy_fixture(root)
    build_horizon_fixture(root)
    build_throttle_fixture(root)
    reports = {
        "exit_strategy": root / "reports" / "exit_strategy.json",
        "exit_horizon": root / "reports" / "exit_horizon.json",
        "regime_throttle": root / "reports" / "regime_throttle.json",
    }
    write_json(
        reports["exit_strategy"],
        suite_builder.build_section(
            "exit_strategy", date_text=FIXTURE_DATE, capital_levels=CAPITAL_LEVELS
        ),
    )
    write_json(
        reports["exit_horizon"],
        suite_builder.build_section("exit_horizon", date_text=FIXTURE_DATE, capital=300_000),
    )
    write_json(
        reports["regime_throttle"],
        suite_builder.build_section(
            "regime_throttle",
            date_text=FIXTURE_DATE,
            capital=300_000,
            variant="candidate_top7_sl12_min5",
            setting="gross75_pos12",
        ),
    )
    return reports


def patch_project_roots(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(suite_builder, "PROJECT_ROOT", root)


def suite_payload(profile: str, root: Path, valid: bool) -> dict[str, Any]:
    if valid and profile == "exit_strategy":
        build_exit_strategy_fixture(root)
    elif valid and profile == "exit_horizon":
        build_horizon_fixture(root)
    elif valid and profile == "regime_throttle":
        build_throttle_fixture(root)
    reports = None
    if profile == "candidate_decision":
        reports = build_source_reports(root) if valid else {
            name: root / "missing" / f"{name}.json"
            for name in ("exit_strategy", "exit_horizon", "regime_throttle")
        }
    return suite_builder.build_section(
        profile,
        date_text=FIXTURE_DATE,
        capital_levels=CAPITAL_LEVELS,
        capital=300_000,
        variant="candidate_top7_sl12_min5",
        setting="gross75_pos12",
        exit_strategy_report=str(reports["exit_strategy"]) if reports else None,
        horizon_sensitivity_report=str(reports["exit_horizon"]) if reports else None,
        regime_throttle_report=str(reports["regime_throttle"]) if reports else None,
    )


@pytest.mark.parametrize("valid", (True, False), ids=("valid", "invalid"))
@pytest.mark.parametrize("profile", PROFILES)
def test_profile_matches_legacy_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, valid: bool, profile: str
) -> None:
    patch_project_roots(monkeypatch, tmp_path)
    actual = suite_payload(profile, tmp_path, valid)

    case = "valid" if valid else "invalid"
    assert fingerprint(actual, tmp_path) == LEGACY_GOLDEN[profile]["builder"][case]
    assert actual["status"] == ("OK" if valid else "FAILED")


@pytest.mark.parametrize("profile", PROFILES)
def test_profile_markdown_matches_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str
) -> None:
    patch_project_roots(monkeypatch, tmp_path)
    payload = suite_payload(profile, tmp_path, True)
    markdown = suite_builder.SECTION_RENDERERS[profile](payload)

    assert hashlib.sha256(markdown.encode("utf-8")).hexdigest() == LEGACY_GOLDEN[profile]["markdown"]


@pytest.mark.parametrize("valid", (True, False), ids=("valid", "invalid"))
def test_candidate_profile_preserves_existing_verifier_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, valid: bool
) -> None:
    patch_project_roots(monkeypatch, tmp_path)
    monkeypatch.setattr(candidate_verifier, "PROJECT_ROOT", tmp_path)
    payload = suite_payload("candidate_decision", tmp_path, valid)
    artifact = tmp_path / "reports" / "candidate_decision.json"
    write_json(artifact, payload)

    verification = candidate_verifier.build_payload(artifact)

    failed = {check["name"] for check in verification["checks"] if not check["ok"]}
    assert verification["status"] == ("OK" if valid else "FAILED")
    assert failed == (
        set()
        if valid
        else {"status_ok", "exit_source_ok", "horizon_source_ok", "throttle_source_safe", "missing_empty"}
    )
    assert {check["name"] for check in verification["checks"]} == {
        "schema",
        "status_ok",
        "research_only",
        "model_changes_false",
        "production_ranking_changes_false",
        "promotion_ready_false",
        "decision_promotion_false",
        "model_promotion_false",
        "production_change_false",
        "shadow_ready_or_blocked",
        "exit_source_ok",
        "horizon_source_ok",
        "throttle_source_safe",
        "candidate_spec_present",
        "missing_empty",
    }


@pytest.mark.parametrize(
    ("profile", "verifier"),
    (
        ("exit_horizon", horizon_verifier),
        ("exit_strategy", strategy_verifier),
        ("regime_throttle", throttle_verifier),
    ),
)
@pytest.mark.parametrize("valid", (True, False), ids=("valid", "invalid"))
def test_analysis_profiles_remain_compatible_with_existing_verifiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    verifier: Any,
    valid: bool,
) -> None:
    patch_project_roots(monkeypatch, tmp_path)
    monkeypatch.setattr(verifier, "PROJECT_ROOT", tmp_path)
    payload = suite_payload(profile, tmp_path, valid)
    artifact = tmp_path / "reports" / f"{profile}.json"
    write_json(artifact, payload)

    verification = verifier.build_payload(artifact)

    assert verification["status"] == ("OK" if valid else "FAILED")
    if valid:
        assert verification["summary"]["failed_count"] == 0
    else:
        assert verification["summary"]["failed_count"] > 0


def test_suite_keeps_four_named_sections() -> None:
    sections = {
        profile: {
            "schema_version": f"fixture-{profile}.v1",
            "status": "OK",
            "decision": {"status": f"{profile.upper()}_OK"},
            "inputs": {"fixture": profile},
        }
        for profile in PROFILES
    }

    payload = suite_builder.build_suite(FIXTURE_DATE, sections)

    assert tuple(payload["sections"]) == PROFILES
    assert payload["status"] == "OK"
    assert payload["manifest"]["date"] == FIXTURE_DATE
    assert tuple(payload["manifest"]["results"]) == PROFILES

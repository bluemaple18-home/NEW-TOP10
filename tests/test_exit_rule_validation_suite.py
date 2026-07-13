from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import build_exit_rule_validation_suite as suite_builder
from scripts import verify_exit_rule_validation_suite as suite_verifier


PROFILES = ("half_year_decision", "portfolio_level", "rolling_regime")
FIXTURE_DATE = "2026-07-13"
FIXTURE_MODEL_SHA256 = "fixture-model-sha256"

LEGACY_GOLDEN = {
    "half_year_decision": {
        "decision": "EXIT_RULE_RESEARCH_SELECTS_BALANCED_CANDIDATE",
        "builder": {
            "valid": "34f06571fc833c38aba54c8e8d142d86203d01609f33c873a0220aad279400a6",
            "invalid": "d33d955d1db968b7135fa3cd0a5c0655544bc0b522937cb2836c8a930ee257ca",
        },
        "verifier": {
            "valid": "0e515c3663c40c5369441e79f1b0e6e1b7e0a7a96479799736fb0337b93f2f06",
            "invalid": "cb3881c4f9ddc584e4755262063f5af14dcc462dee8763f3e5408906716246d8",
        },
        "invalid_failed": ["primary_candidate_expected"],
        "markdown": "5462b546ad926d59d7a0ec5d8d5a0f4ff7c4545fdd7442c34d34e5f5b3849fb7",
    },
    "portfolio_level": {
        "decision": "PORTFOLIO_LEVEL_SUPPORTS_EXIT_RULE_SHADOW",
        "builder": {
            "valid": "03b8eb6871c62d04c684e2eb4ee81a235317f6b49aeefedd5f973af3fec239fa",
            "invalid": "9fc90180270510d194d89e8f2fb411fb307374a060709ecf125a36c7ee901494",
        },
        "verifier": {
            "valid": "89c58d0f0b7095101c7e34cb97657db37b81183931c01ae09dce68cc015b03c9",
            "invalid": "fac93cf47bc13dd67d11c6894ed53bbe33c49f294b4eb2abaa5cacbf02067fb3",
        },
        "invalid_failed": ["event_exits_present"],
        "markdown": "f0c192fd8b2bca643709ee150f2d6364ddb9397150baa033910d5e662f1b09ac",
    },
    "rolling_regime": {
        "decision": "EXIT_RULE_CONTEXTUAL_ROUTING_CANDIDATE",
        "builder": {
            "valid": "46e1e5d320f60973d71c4733b849bb78c434fd5e956055cdc685b3011aa30f9f",
            "invalid": "9f18550376dd261c85fb2b89063cebfb7f5c72e8e3e46d6f3cb10d4c03cffc6b",
        },
        "verifier": {
            "valid": "7c9977d48402a14c94497ac738d84c40f0e5834aa73c601cff4b7c7011dd0247",
            "invalid": "e19496734fea7d50bc1be4ce1dd3b3874e3254f918bef36111c6144c710ad8d7",
        },
        "invalid_failed": ["high_choppy_prefers_stop_take"],
        "markdown": "6f755766b1b024625a1fbab865dd389df6f2bc88695b0426ec98f96485fd55c5",
    },
}


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


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


def policy_row(return_value: float, win_rate: float, avg_mae: float, worst_mae: float, giveback: float) -> dict[str, Any]:
    return {
        "trade_count": 10,
        "ranking_day_count": 4,
        "return_on_buy_cash": return_value,
        "win_rate": win_rate,
        "avg_trade_net_return": return_value / 10,
        "median_trade_net_return": return_value / 12,
        "avg_mae": avg_mae,
        "worst_mae": worst_mae,
        "avg_mfe": return_value / 2,
        "avg_giveback": giveback / 2,
        "p90_giveback": giveback,
    }


def regime_row(date_text: str, regime_label: str) -> dict[str, Any]:
    return {
        "trade_date": date_text,
        "regime_label": regime_label,
        "equal_weight_return": 0.001,
        "value_weight_return": 0.001,
        "breadth_ma20": 0.5,
        "breadth_ma60": 0.5,
        "advance_ratio": 0.5,
        "breakout_ratio": 0.05,
        "breakdown_ratio": 0.03,
        "volume_spike_ratio": 0.1,
        "long_upper_shadow_ratio": 0.05,
        "avg_rsi": 50.0,
        "top_sector_value_share": 0.5,
        "top_strong_sector_value_share": 0.5,
    }


def build_fixture(root: Path) -> dict[str, Any]:
    policies = {
        key: policy_row(0.1 + index / 100, 0.5, -0.2, -0.4, 0.2)
        for index, key in enumerate(suite_builder.WATCH_POLICIES)
    }
    policies.update(
        {
            "fixed_40d": policy_row(0.5, 0.5, -0.2, -0.6, 0.4),
            "h40_early_tp07": policy_row(0.2, 0.7, -0.15, -0.45, 0.25),
            "h40_early_tp15": policy_row(0.3, 0.6, -0.12, -0.4, 0.2),
            "h30_tp25_sl10": policy_row(0.25, 0.55, -0.1, -0.3, 0.18),
        }
    )
    matrix = write_json(
        root / "matrix.json",
        {"contract": {"fixture": True}, "matrix": {"exit_policy": policies}},
    )
    manifest = write_json(
        root / "manifest.json",
        {
            "status": "OK",
            "outputs": {
                "ranking_count": 100,
                "rankings": [{"date": "2026-01-02"}, {"date": "2026-06-30"}],
            },
            "failures": [],
        },
    )

    summaries = {
        "h40_fixed65": (0.5, -0.3, 0.5, 0.65),
        "h40_gross55": (0.4, -0.2, 0.52, 0.55),
        "h40_tp15_fixed65": (0.3, -0.2, 0.6, 0.65),
        "h40_tp15_gross55": (0.25, -0.1, 0.61, 0.55),
        "h30_tp25_sl10_fixed65": (0.2, -0.15, 0.55, 0.65),
        "h30_tp25_sl10_gross55": (0.15, -0.08, 0.56, 0.55),
    }
    variant_paths: dict[str, str] = {}
    dates = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]
    for label, (total_return, max_drawdown, win_rate, gross) in summaries.items():
        daily = [
            {
                "date": date_text,
                "daily_return": 0.001 * index,
                "equity": 100.0 + index,
                "scheduled_exits": 1 if label == "h40_fixed65" else 0,
                "take_profit_exits": 1 if label == "h40_tp15_fixed65" else 0,
                "stop_loss_exits": 1 if label == "h30_tp25_sl10_fixed65" else 0,
                "trailing_stop_exits": 0,
            }
            for index, date_text in enumerate(dates, start=1)
        ]
        path = write_json(
            root / f"{label}.json",
            {
                "summary": {
                    "total_return": total_return,
                    "max_drawdown": max_drawdown,
                    "trade_count": 40,
                    "win_rate": win_rate,
                    "avg_trade_return": total_return / 40,
                    "avg_gross_exposure": gross,
                },
                "daily": daily,
                "inputs": {"fixture": label},
            },
        )
        variant_paths[label] = str(path)

    regime_history = write_json(
        root / "market_regime_history.json",
        {
            "rows": [
                regime_row("2026-01-02", "BROAD_RISK_ON"),
                regime_row("2026-01-05", "RISK_OFF"),
                regime_row("2026-01-06", "CHOPPY_RANGE"),
                regime_row("2026-01-07", "MIXED_NEUTRAL"),
            ]
        },
    )
    return {
        "matrix": matrix,
        "manifest": manifest,
        "variants": variant_paths,
        "regime_history": regime_history,
        "missing_variants": {label: str(root / "missing" / f"{label}.json") for label in summaries},
    }


def suite_build(profile: str, fixture: dict[str, Any], *, valid: bool) -> dict[str, Any]:
    variants = fixture["variants"] if valid else fixture["missing_variants"]
    return suite_builder.build_section(
        profile,
        date_text=FIXTURE_DATE,
        matrix_path=fixture["matrix"] if valid else fixture["matrix"].with_name("missing-matrix.json"),
        manifest_path=fixture["manifest"] if valid else fixture["manifest"].with_name("missing-manifest.json"),
        market_regime_history=fixture["regime_history"],
        portfolio_variants=variants,
        rolling_variants={key: variants[key] for key in suite_builder.ROLLING_VARIANTS},
    )


def verifier_payload(profile: str, *, valid: bool) -> dict[str, Any]:
    contract = {
        "research_only": True,
        "production_default_allowed": False,
        "does_not_train_model": True,
        "does_not_change_production_ranking": True,
        "does_not_change_risk_adjusted_score": True,
    }
    if profile == "half_year_decision":
        payload = {
            "status": "OK",
            "contract": contract,
            "inputs": {"manifest": {"ranking_count": 100, "failure_count": 0}},
            "summary": {
                "primary_candidate": "h40_early_tp15",
                "defensive_candidate": "h30_tp25_sl10",
                "rejected": ["h40_early_tp07"],
            },
            "candidate_decision": {"reject_early_tp07": True},
            "policies": {
                "fixed_40d": {"return_on_buy_cash": 0.5, "worst_mae": -0.6, "avg_mae": -0.2, "p90_giveback": 0.4},
                "h40_early_tp07": {"return_on_buy_cash": 0.2},
                "h40_early_tp15": {"return_on_buy_cash": 0.3, "worst_mae": -0.4, "p90_giveback": 0.2},
                "h30_tp25_sl10": {"return_on_buy_cash": 0.25, "worst_mae": -0.3, "avg_mae": -0.1},
            },
        }
        if not valid:
            payload["summary"]["primary_candidate"] = "unexpected"
        return payload
    if profile == "portfolio_level":
        payload = {
            "status": "OK",
            "contract": contract,
            "summary": {
                "primary_shadow_candidate": "h40_tp15_fixed65",
                "defensive_shadow_candidate": "h30_tp25_sl10_fixed65",
            },
            "rows": {
                "h40_fixed65": {"total_return": 0.5},
                "h40_tp15_fixed65": {"total_return": 0.3, "exit_counts": {"take_profit": 2}},
                "h30_tp25_sl10_fixed65": {"total_return": 0.2, "exit_counts": {"stop_loss": 2}},
            },
            "comparisons_vs_h40_fixed65": {
                "h40_tp15_fixed65": {"max_drawdown_delta": 0.1, "win_rate_delta": 0.1},
                "h30_tp25_sl10_fixed65": {"max_drawdown_delta": 0.15},
            },
        }
        if not valid:
            payload["rows"]["h40_tp15_fixed65"]["exit_counts"]["take_profit"] = 0
        return payload
    payload = {
        "status": "OK",
        "contract": contract,
        "contextual_rules": {
            "big_bull_preference": "h40_fixed65",
            "high_choppy_preference": "h30_tp25_sl10_fixed65",
            "risk_off_preference": "h40_tp15_fixed65",
        },
        "rolling_vs_h40_fixed65": {
            "h40_tp15_fixed65": {"20d": {"drawdown_improves_rate": 0.8}, "40d": {"drawdown_improves_rate": 0.8}},
            "h40_tp15_gross55": {"20d": {"drawdown_improves_rate": 0.95}, "40d": {"drawdown_improves_rate": 0.95}},
        },
        "regime_vs_h40_fixed65": {
            "h40_tp15_fixed65": {
                "HIGH_CHOPPY_CONTEXT": {"return_delta": 0.01, "drawdown_delta": 0.02},
                "RISK_OFF": {"drawdown_delta": 0.03},
            },
            "h30_tp25_sl10_fixed65": {
                "HIGH_CHOPPY_CONTEXT": {"daily_count": 30, "return_delta": 0.03, "drawdown_delta": 0.04}
            },
        },
    }
    if not valid:
        payload["contextual_rules"]["high_choppy_preference"] = "h40_tp15_fixed65"
    return payload


def suite_verify(profile: str, payload: dict[str, Any], root: Path) -> dict[str, Any]:
    artifact = write_json(root / f"{profile}.json", payload)
    return suite_verifier.verify_profile(
        profile,
        payload,
        artifact=artifact,
        expected_model_sha256=FIXTURE_MODEL_SHA256,
        actual_model_sha256=FIXTURE_MODEL_SHA256,
    )


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("valid", (True, False), ids=("valid", "invalid"))
def test_builder_profile_matches_legacy_field_golden(tmp_path: Path, profile: str, valid: bool) -> None:
    fixture = build_fixture(tmp_path)
    actual = suite_build(profile, fixture, valid=valid)
    case = "valid" if valid else "invalid"
    assert fingerprint(actual, tmp_path) == LEGACY_GOLDEN[profile]["builder"][case]
    assert actual["status"] == ("OK" if valid else "MISSING_INPUT")
    assert actual["summary"]["decision"] == LEGACY_GOLDEN[profile]["decision"]


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("valid", (True, False), ids=("valid", "invalid"))
def test_verifier_profile_matches_legacy_checks_and_failures(tmp_path: Path, profile: str, valid: bool) -> None:
    actual = suite_verify(profile, verifier_payload(profile, valid=valid), tmp_path)
    case = "valid" if valid else "invalid"
    assert fingerprint(actual, tmp_path) == LEGACY_GOLDEN[profile]["verifier"][case]
    assert actual["status"] == ("OK" if valid else "FAILED")
    assert actual["failed"] == ([] if valid else LEGACY_GOLDEN[profile]["invalid_failed"])


@pytest.mark.parametrize("profile", PROFILES)
def test_profile_markdown_matches_legacy_golden(tmp_path: Path, profile: str) -> None:
    fixture = build_fixture(tmp_path)
    section = suite_build(profile, fixture, valid=True)
    markdown = suite_builder.SECTION_RENDERERS[profile](section)
    assert hashlib.sha256(markdown.encode("utf-8")).hexdigest() == LEGACY_GOLDEN[profile]["markdown"]


def test_suite_keeps_three_named_sections(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path)
    sections = {profile: suite_build(profile, fixture, valid=True) for profile in PROFILES}
    payload = suite_builder.build_suite(FIXTURE_DATE, sections)
    assert tuple(payload["sections"]) == PROFILES
    assert payload["status"] == "OK"
    assert payload["summary"]["decisions"] == {
        profile: section["summary"]["decision"] for profile, section in sections.items()
    }

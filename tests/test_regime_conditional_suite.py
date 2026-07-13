from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from scripts import build_regime_conditional_suite as suite_builder
from scripts import verify_regime_conditional_hybrid_report as hybrid_verifier
from scripts import verify_regime_conditional_shadow_rankings as shadow_verifier


FIXTURE_DATE_COUNT = 12
SHADOW_VALID_GOLDEN = {
    "payload_sha256": "72d1591098d507c056e67841975c89c9fe17020cdd3c5f56f74788697608a97a",
    "csv_sha256": {
        "ranking_2026-01-02.csv": "563c5c00c47ad2d65d56f0e1498725b222d1ff5401b53f4254aca6c7034eec34",
        "ranking_2026-01-03.csv": "0c3aa98f6606aa245350ebedb7e0a0603215b5a0db70d2d4c1dfb755f183a1ce",
        "ranking_2026-01-04.csv": "e164b4d71bc61eb1f07c7951a322e4a23fce9314582475b35a2531131868ec67",
        "ranking_2026-01-05.csv": "6badf7a60135adad0b3fcfbf1e613030487f8f7c2952a9ba17ae964959680c80",
        "ranking_2026-01-06.csv": "92628ad4fc7efb509b4b87b738c91c80957b8d2a46bd73d4e1968e3f3de40207",
        "ranking_2026-01-07.csv": "54c4df8e1d22a7836a5f9a94e3895d8aea06fa3a1e7052714a353d49180791e0",
        "ranking_2026-01-08.csv": "6ea350ef573088d2f3ab1aee1c531ead8bf135e4e1c7b708973404f3a3e3955c",
        "ranking_2026-01-09.csv": "adf42f7e585b7af02e71c877922e68b0cf57f0ba31a0acf3effdae1bb7a1361c",
        "ranking_2026-01-10.csv": "abc6adae2eb438ac959ff543c899c0e2a15f94bdbb134da0cb0b763d935e621d",
        "ranking_2026-01-11.csv": "0fbe220657549e33c1080898a56cbe3fc10cfb16e9a580375479752b911ac09c",
        "ranking_2026-01-12.csv": "debafd9111b045946a42e0a10e206f8cddd1cca4d3583ee2264fb45e53e67611",
        "ranking_2026-01-13.csv": "815675f2c858a0ef22d1bd0545339784b35dfe1534945270ea794a424192acac",
    },
    "console": {
        "status": "OK",
        "summary": "<fixture-root>/output/regime_conditional_shadow_ranking.json",
        "date_count": 12,
        "shadow_active_family_count": 6,
        "production_inactive_family_count": 6,
    },
    "exit_code": 0,
}

HYBRID_GOLDEN = {
    "valid": {
        "payload_sha256": "c2c47bf396ef1ebaf0e79436840a1b7e414c6b7441668fbedfdd257dc0cd1821",
        "markdown_sha256": "0b74719bf2a5760fad026ee341c823cdb0f1b6344b8d081b38c75a4dbf11a30b",
        "console": {
            "status": "OK",
            "decision": "HYBRID_CANDIDATE",
            "output": "output/hybrid.json",
        },
        "exit_code": 0,
    },
    "missing": {
        "payload_sha256": "8211008f48e28872c93c711fb13183dcc4c85073510ba9d8d1eded17a80a3252",
        "markdown_sha256": "fce7373c77fb8eb195277d6cfc7d9cb0c80a6045f65cd46dd8f843371e5154f5",
        "console": {
            "status": "FAILED",
            "decision": "HYBRID_REJECTED",
            "output": "output/hybrid.json",
        },
        "exit_code": 1,
    },
}


def write_shadow_fixture(root: Path) -> dict[str, Path]:
    production = root / "production"
    shadow = root / "shadow"
    output = root / "output"
    production.mkdir()
    shadow.mkdir()
    dates = [f"2026-01-{day:02d}" for day in range(2, 14)]
    for index, date_text in enumerate(dates):
        (production / f"ranking_{date_text}.csv").write_text(
            f"stock_id,score,note\n1101,{100 - index},production-{index}\n1102,{90 - index},production-b-{index}\n",
            encoding="utf-8-sig",
        )
        (shadow / f"ranking_{date_text}.csv").write_text(
            f"stock_id,score,note\n2201,{200 - index},shadow-{index}\n2202,{190 - index},shadow-b-{index}\n",
            encoding="utf-8-sig",
        )
    regime = root / "market_regime_history.json"
    regime.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "trade_date": date_text,
                        "regime_label": "BROAD_RISK_ON" if index % 2 == 0 else "RISK_OFF",
                        "equal_weight_return": 0.01,
                        "value_weight_return": 0.01,
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
                    for index, date_text in enumerate(dates)
                ]
            }
        ),
        encoding="utf-8",
    )
    return {"production": production, "shadow": shadow, "output": output, "regime": regime}


def normalized_hash(payload: dict[str, object], root: Path) -> str:
    normalized = dict(payload)
    normalized.pop("generated_at", None)
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    encoded = encoded.replace(str(root), "<fixture-root>").replace(str(root.resolve()), "<fixture-root>")
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def write_hybrid_fixture(root: Path) -> None:
    artifact_dir = root / "artifacts" / "model_experiments"
    artifact_dir.mkdir(parents=True)
    for capital in (100_000, 300_000, 500_000):
        k = capital // 1000
        scale = capital / 1_000_000
        artifacts = {
            f"odd_lot_portfolio_production_top7_sl12_min5_{k}k_gross75_pos12_2026-07-13.json": (0.10 + scale, -0.20, 100),
            f"odd_lot_portfolio_candidate_top7_sl12_min5_{k}k_gross75_pos12_2026-07-13.json": (0.12 + scale, -0.18, 110),
            f"odd_lot_portfolio_hybrid_big_bull_candidate_top7_sl12_min5_{k}k_g75_pos12_2026-07-13.json": (0.13 + scale, -0.16, 120),
        }
        for name, (total_return, max_drawdown, trade_count) in artifacts.items():
            (artifact_dir / name).write_text(
                json.dumps(
                    {
                        "summary": {
                            "total_return": total_return,
                            "max_drawdown": max_drawdown,
                            "total_pnl": capital * total_return,
                            "trade_count": trade_count,
                            "win_rate": 0.55,
                            "avg_cash_weight": 0.2,
                        }
                    }
                ),
                encoding="utf-8",
            )


def test_shadow_rankings_valid_cli_matches_frozen_legacy_contract(tmp_path: Path) -> None:
    fixture = write_shadow_fixture(tmp_path)
    command = [
        sys.executable,
        str(Path(suite_builder.__file__)),
        "--profile",
        "shadow_rankings",
        "--production-dir",
        str(fixture["production"]),
        "--shadow-dir",
        str(fixture["shadow"]),
        "--market-regime-history",
        str(fixture["regime"]),
        "--output-dir",
        str(fixture["output"]),
        "--top-n",
        "2",
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)

    summary_path = fixture["output"] / "regime_conditional_shadow_ranking.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    actual_csv_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(fixture["output"].glob("ranking_*.csv"))
    }
    console = json.loads(result.stdout)
    console["summary"] = console["summary"].replace(str(tmp_path), "<fixture-root>")

    assert normalized_hash(payload, tmp_path) == SHADOW_VALID_GOLDEN["payload_sha256"]
    assert actual_csv_hashes == SHADOW_VALID_GOLDEN["csv_sha256"]
    assert console == SHADOW_VALID_GOLDEN["console"]
    assert result.returncode == SHADOW_VALID_GOLDEN["exit_code"]
    assert len(payload["rows"]) == FIXTURE_DATE_COUNT


def test_hybrid_report_valid_cli_matches_frozen_legacy_contract(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    write_hybrid_fixture(tmp_path)
    output = tmp_path / "output" / "hybrid.json"
    monkeypatch.setattr(suite_builder, "PROJECT_ROOT", tmp_path.resolve())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "suite",
            "--profile",
            "hybrid_report",
            "--date",
            "2026-07-13",
            "--output",
            str(output),
        ],
    )

    exit_code = suite_builder.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    console = json.loads(capsys.readouterr().out)
    console["output"] = console["output"].replace(str(tmp_path), "<fixture-root>").replace(
        str(tmp_path.resolve()), "<fixture-root>"
    )

    assert normalized_hash(payload, tmp_path) == HYBRID_GOLDEN["valid"]["payload_sha256"]
    assert hashlib.sha256(output.with_suffix(".md").read_bytes()).hexdigest() == HYBRID_GOLDEN["valid"]["markdown_sha256"]
    assert console == HYBRID_GOLDEN["valid"]["console"]
    assert exit_code == HYBRID_GOLDEN["valid"]["exit_code"]


def test_hybrid_report_missing_inputs_preserves_failed_contract(tmp_path: Path, monkeypatch, capsys) -> None:
    output = tmp_path / "output" / "hybrid.json"
    monkeypatch.setattr(suite_builder, "PROJECT_ROOT", tmp_path.resolve())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "suite",
            "--profile",
            "hybrid_report",
            "--date",
            "2026-07-13",
            "--output",
            str(output),
        ],
    )

    exit_code = suite_builder.main()
    payload = json.loads(output.read_text(encoding="utf-8"))
    console = json.loads(capsys.readouterr().out)
    console["output"] = console["output"].replace(str(tmp_path), "<fixture-root>").replace(
        str(tmp_path.resolve()), "<fixture-root>"
    )

    assert normalized_hash(payload, tmp_path) == HYBRID_GOLDEN["missing"]["payload_sha256"]
    assert hashlib.sha256(output.with_suffix(".md").read_bytes()).hexdigest() == HYBRID_GOLDEN["missing"]["markdown_sha256"]
    assert console == HYBRID_GOLDEN["missing"]["console"]
    assert exit_code == HYBRID_GOLDEN["missing"]["exit_code"]


def test_shadow_rankings_unsupported_family_keeps_legacy_exception_contract(tmp_path: Path) -> None:
    fixture = write_shadow_fixture(tmp_path)
    args = Namespace(
        production_dir=str(fixture["production"]),
        shadow_dir=str(fixture["shadow"]),
        output_dir=str(fixture["output"]),
        market_regime_history=str(fixture["regime"]),
        active_family="HIGH_CHOPPY",
        top_n=2,
    )

    with pytest.raises(ValueError, match="unsupported active family: HIGH_CHOPPY"):
        suite_builder.build_shadow_rankings(args)


def test_shadow_rankings_empty_date_intersection_stays_successful(tmp_path: Path) -> None:
    fixture = write_shadow_fixture(tmp_path)
    for path in fixture["shadow"].glob("ranking_*.csv"):
        path.rename(path.with_name(path.name.replace("2026-01", "2025-12")))
    result = subprocess.run(
        [
            sys.executable,
            str(Path(suite_builder.__file__)),
            "--profile",
            "shadow_rankings",
            "--production-dir",
            str(fixture["production"]),
            "--shadow-dir",
            str(fixture["shadow"]),
            "--market-regime-history",
            str(fixture["regime"]),
            "--output-dir",
            str(fixture["output"]),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads((fixture["output"] / "regime_conditional_shadow_ranking.json").read_text(encoding="utf-8"))
    assert payload["summary"] == {
        "date_count": 0,
        "shadow_active_family_count": 0,
        "production_inactive_family_count": 0,
    }
    assert payload["rows"] == []
    assert payload["outputs"] == []
    assert json.loads(result.stdout)["status"] == "OK"
    assert result.returncode == 0


def test_hybrid_report_default_output_and_existing_verifier_consumer_gate(tmp_path: Path, monkeypatch, capsys) -> None:
    write_hybrid_fixture(tmp_path)
    monkeypatch.setattr(suite_builder, "PROJECT_ROOT", tmp_path.resolve())
    monkeypatch.setattr(hybrid_verifier, "PROJECT_ROOT", tmp_path.resolve())
    monkeypatch.setattr(sys, "argv", ["suite", "--profile", "hybrid_report", "--date", "2026-07-13"])

    assert suite_builder.main() == 0
    output = tmp_path / "artifacts" / "model_experiments" / "regime_conditional_hybrid_report_2026-07-13.json"
    verification = hybrid_verifier.build_payload(output)

    assert json.loads(capsys.readouterr().out)["output"] == "artifacts/model_experiments/regime_conditional_hybrid_report_2026-07-13.json"
    assert verification["status"] == "OK"
    assert verification["summary"]["failed_count"] == 0


def test_shadow_rankings_existing_verifier_consumer_gate(tmp_path: Path, monkeypatch) -> None:
    fixture = write_shadow_fixture(tmp_path)
    monkeypatch.setattr(suite_builder, "PROJECT_ROOT", tmp_path.resolve())
    monkeypatch.setattr(shadow_verifier, "PROJECT_ROOT", tmp_path.resolve())
    payload = suite_builder.build_shadow_rankings(
        Namespace(
            production_dir=str(fixture["production"]),
            shadow_dir=str(fixture["shadow"]),
            output_dir=str(fixture["output"]),
            market_regime_history=str(fixture["regime"]),
            active_family="BIG_BULL",
            top_n=2,
        )
    )
    summary_path = fixture["output"] / "regime_conditional_shadow_ranking.json"
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    verification = shadow_verifier.build_payload(summary_path)

    assert verification["status"] == "OK"
    assert verification["summary"]["failed_count"] == 0

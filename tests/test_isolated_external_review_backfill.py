from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts import isolated_external_review_backfill as backfill


DATES = [
    "2026-08-03",
    "2026-08-04",
    "2026-08-05",
    "2026-08-06",
    "2026-08-07",
    "2026-08-10",
    "2026-08-11",
    "2026-08-12",
    "2026-08-13",
    "2026-08-14",
    "2026-08-17",
    "2026-08-18",
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
    "2026-08-24",
    "2026-08-25",
    "2026-08-26",
]


def test_prepare_builds_safe_packets_and_36_slot_ledger(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    source_root = tmp_path / "source"
    output_root = project_root / "artifacts" / "isolated_external_review_backfill" / "2026-08-03_2026-08-26"
    project_root.mkdir()
    _write_source_fixture(source_root)
    monkeypatch.setattr(backfill, "PROJECT_ROOT", project_root)

    exit_code = backfill.main(
        [
            "prepare",
            "--source-root",
            str(source_root),
            "--output-root",
            str(output_root),
            "--chatgpt-marker",
            "chatgpt.local/project/c/exact",
            "--gemini-marker",
            "gemini.local/app/exact",
        ]
    )

    assert exit_code == 0
    ledger = json.loads((output_root / "ledger.json").read_text(encoding="utf-8"))
    assert len(ledger["slots"]) == 36
    assert ledger["slots"][0]["slot_id"] == "2026-08-03:chatgpt"
    assert ledger["slots"][1]["slot_id"] == "2026-08-03:gemini"
    assert ledger["write_policy"]["max_attempts_per_slot"] == 1
    packet_path = project_root / ledger["slots"][0]["packet_path"]
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    assert backfill.validate_packet(packet) == []
    packet_text = packet_path.read_text(encoding="utf-8")
    assert "model_prob" not in packet_text
    assert "AI:" not in packet_text
    assert "features.parquet" not in packet_text
    assert backfill.verify_output(output_root, require_complete=False) == 0


def test_prepare_requires_explicit_local_provider_markers(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "repo"
    source_root = tmp_path / "source"
    output_root = project_root / "artifacts" / "isolated_external_review_backfill" / "2026-08-03_2026-08-26"
    project_root.mkdir()
    _write_source_fixture(source_root)
    monkeypatch.setattr(backfill, "PROJECT_ROOT", project_root)

    try:
        backfill.main(["prepare", "--source-root", str(source_root), "--output-root", str(output_root)])
    except SystemExit as exc:
        assert "provider target config missing" in str(exc)
    else:
        raise AssertionError("missing provider markers must fail closed")


def test_next_slot_blocks_after_uncertain_canary(monkeypatch, tmp_path: Path, capsys) -> None:
    project_root = tmp_path / "repo"
    output_root = project_root / "artifacts" / "isolated_external_review_backfill" / "2026-08-03_2026-08-26"
    output_root.mkdir(parents=True)
    monkeypatch.setattr(backfill, "PROJECT_ROOT", project_root)
    slots = []
    for date_text in DATES:
        for provider in backfill.PROVIDERS:
            slots.append(
                {
                    "slot_id": f"{date_text}:{provider}",
                    "date": date_text,
                    "provider": provider,
                    "status": "PENDING",
                    "max_attempts": 1,
                    "packet_path": f"artifacts/isolated_external_review_backfill/2026-08-03_2026-08-26/packets/{date_text}/review_packet_{date_text}.json",
                    "packet_sha256": "sha",
                }
            )
    slots[0]["status"] = "UNCERTAIN"
    (output_root / "ledger.json").write_text(
        json.dumps(
            {
                "schema_version": backfill.SCHEMA_VERSION,
                "canary_date": DATES[0],
                "slots": slots,
            }
        ),
        encoding="utf-8",
    )

    exit_code = backfill.print_next_slot(output_root)

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"


def _write_source_fixture(root: Path) -> None:
    artifacts = root / "artifacts"
    daily_manifest = root / "manifest" / "daily"
    data_clean = root / "data" / "clean"
    artifacts.mkdir(parents=True)
    daily_manifest.mkdir(parents=True)
    data_clean.mkdir(parents=True)
    feature_rows = []
    for index, date_text in enumerate(DATES, start=1):
        stock_id = f"{index:04d}"
        (daily_manifest / f"{date_text}.json").write_text("{}", encoding="utf-8")
        pd.DataFrame(
            [
                {
                    "stock_id": stock_id,
                    "stock_name": f"測試{index}",
                    "reasons": "站上布林中軌\nRSI 40 反彈 | AI: macd(+0.5)",
                }
            ]
        ).to_csv(artifacts / f"ranking_{date_text}.csv", index=False)
        (artifacts / f"daily_report_{date_text}.json").write_text(
            json.dumps(
                {
                    "summary": {
                        "market_regime": "RISK_OFF",
                        "top_count": 1,
                        "gross_exposure": 0.35,
                        "allocated_exposure": 0.35,
                        "cash_weight": 0.65,
                    },
                    "risk": {"notes": ["測試風險"]},
                    "top10": [
                        {
                            "rank": 1,
                            "stock_id": stock_id,
                            "stock_name": f"測試{index}",
                            "close": 10 + index,
                            "market_regime": "RISK_OFF",
                            "reference": {"industry_name": "電子", "theme_tags": ["測試題材"]},
                            "trade_plan": {
                                "entry": 10 + index,
                                "stop_loss": 9 + index,
                                "target_price": 12 + index,
                                "risk_reward": 2.0,
                            },
                            "persistence": {"available": False},
                            "reasons": ["站上布林中軌", "AI: macd(+0.5)", "RSI 40 反彈"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        feature_rows.append(
            {
                "date": date_text,
                "stock_id": stock_id,
                "open": 10 + index,
                "high": 11 + index,
                "low": 9 + index,
                "close": 10.5 + index,
                "volume": 1000 + index,
                "value": 10000 + index,
                "transactions": 100 + index,
            }
        )
    pd.DataFrame(feature_rows).to_parquet(data_clean / "features.parquet")

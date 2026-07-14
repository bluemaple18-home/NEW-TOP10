from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_weekend_readiness_audit as builder
import weekend_training_common as common
import verify_weekend_overnight_campaign_summary as campaign_verifier
import verify_weekend_ranking_dir_unlock_smoke as ranking_verifier
import verify_weekend_unsupported_unlock_audit as unsupported_verifier


RUN_DATE = "2026-06-18"
EXPECTED = {
    "valid": {
        "campaign": {
            "exit_code": 0,
            "console": {
                "status": "OK",
                "date": RUN_DATE,
                "training_date": RUN_DATE,
                "actual_replay_count": 0,
                "smoke_replay_status": "SKIPPED_GATE_NOT_PASSED",
                "outputs": [
                    f"artifacts/weekend_training/weekend_production_baseline_provenance_design_{RUN_DATE}.json",
                    f"artifacts/weekend_training/weekend_topic_default_entry_filter_contract_audit_{RUN_DATE}.json",
                    f"artifacts/weekend_training/weekend_regime_slice_data_adequacy_audit_{RUN_DATE}.json",
                    f"artifacts/weekend_training/overnight_campaign_summary_{RUN_DATE}.json",
                ],
            },
            "files": {
                "weekend_production_baseline_provenance_design": {"json": "5132c60d1643d66841cedcc2b1998cb393ca85bdc2f7dd042314e86b3237e77c", "markdown": "516320031304cfd44b4eb75166ea289e44e68d49429942b5734ddd5758547671"},
                "weekend_topic_default_entry_filter_contract_audit": {"json": "47f412fefc76c6a04a1ee52b8458001af3da592ee35fabf6a7d6137fbc84d4be", "markdown": "e267ee794839820cfa1c23f158f773bd5927b112ccee0e82954d1f18e629ccee"},
                "weekend_regime_slice_data_adequacy_audit": {"json": "d721e8257914d79336c3fe0097335954cb4cf09c583be7bd843c3234fdd2ec75", "markdown": "e50e3767221c5dd93ab2bcc88ce1586d66cf3a9488614ab9b626cdae607e5f08"},
                "overnight_campaign_summary": {"json": "1b19face024b4abaa72214da5ed4856733a5308fc3a371141ae2543f69e911a4", "markdown": "6fcbf0548ef6ebd7771c5d7de9636ac0fe8ceafb0844d766e1041884cea9c42d"},
            },
        },
        "ranking-dir-smoke": {
            "exit_code": 0,
            "console": {"status": "OK", "output": f"artifacts/weekend_training/weekend_ranking_dir_unlock_smoke_{RUN_DATE}.json", "decision": "SMOKE_DONE_ARTIFACT_REQUIRED"},
            "files": {"weekend_ranking_dir_unlock_smoke": {"json": "30d06f5fefca0ebc3547c6198a09ad221a9750a7abc14fe4aafe2716b58b5b2c", "markdown": "fe427420c50ffa42f1dc5aabfa557cbb234ea2c0969fe93435102fc7d54d96c3"}},
        },
        "unsupported-unlock": {
            "exit_code": 0,
            "console": {"status": "OK", "output": f"artifacts/weekend_training/weekend_unsupported_unlock_audit_{RUN_DATE}.json", "first_unlock_candidate": "UNSUPPORTED_RANKING_DIR_MISSING", "unsupported_count": 3},
            "files": {"weekend_unsupported_unlock_audit": {"json": "2959f0f0f122b51cc7f6f015576f1b491f6b4058e5923391a8313957c246f246", "markdown": "23008d09539824f0003e53497d4c9de21624fed29894cf46f5e99816d00b535d"}},
        },
    },
    "missing": {
        "campaign": {
            "exit_code": 0,
            "console": {
                "status": "OK",
                "date": RUN_DATE,
                "training_date": RUN_DATE,
                "actual_replay_count": 0,
                "smoke_replay_status": "SKIPPED_GATE_NOT_PASSED",
                "outputs": [
                    f"artifacts/weekend_training/weekend_production_baseline_provenance_design_{RUN_DATE}.json",
                    f"artifacts/weekend_training/weekend_topic_default_entry_filter_contract_audit_{RUN_DATE}.json",
                    f"artifacts/weekend_training/weekend_regime_slice_data_adequacy_audit_{RUN_DATE}.json",
                    f"artifacts/weekend_training/overnight_campaign_summary_{RUN_DATE}.json",
                ],
            },
            "files": {
                "weekend_production_baseline_provenance_design": {"json": "c7acdbe17777b08183e5f9ffce409802a764d75decf7ee7a8fc2a130b2cca80f", "markdown": "57ca6485cfd61fc487c0f086e0fbbd9e45fb67b9fa16f3d0945f801b0d7b972d"},
                "weekend_topic_default_entry_filter_contract_audit": {"json": "a6c94bcf04f4ca134b7b4bc4ce7d97ce0d9fab6215a224ff43649d470f2a8624", "markdown": "a31dafd79bf88f923f3b5204f23e5a390188bb0525421d1d06fdff3848d1fc1f"},
                "weekend_regime_slice_data_adequacy_audit": {"json": "06e9fb549ac3764e23875b068c40f783c97d8b9acf7e65865af3d600c08761d9", "markdown": "09d552dde58cad620f81b4de3138d8ce6f8e0806f3b4920d343ba8e036136aea"},
                "overnight_campaign_summary": {"json": "488c4eec3ff1633a65218ddb4b2359530c06c775fa820b7ce7d9e6e37ed1c1bb", "markdown": "6dad87d823aaa7bd6116c720eeaf1be31bde956e53414d2133e94cc0e787ee7a"},
            },
        },
        "ranking-dir-smoke": {
            "exit_code": 0,
            "console": {"status": "OK", "output": f"artifacts/weekend_training/weekend_ranking_dir_unlock_smoke_{RUN_DATE}.json", "decision": "SMOKE_DONE_ARTIFACT_REQUIRED"},
            "files": {"weekend_ranking_dir_unlock_smoke": {"json": "398a24e585ffe328585a636e0ee7ac0635d8860347e48914e1c790b700a827e9", "markdown": "dfc9a6dbd1f2953085c2c16e7264d4034c19d0caa4ce408c99470de10edbabaa"}},
        },
        "unsupported-unlock": {
            "exit_code": 0,
            "console": {"status": "OK", "output": f"artifacts/weekend_training/weekend_unsupported_unlock_audit_{RUN_DATE}.json", "first_unlock_candidate": None, "unsupported_count": 0},
            "files": {"weekend_unsupported_unlock_audit": {"json": "6ea3a64a1fdbee2fb819bdf5cb26f5eb843c842e54c56fc229734d74d0e55ced", "markdown": "2878e81f93d6e7bf56da074342f2c9b7321f498e773701575b154f798604d2d4"}},
        },
    },
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def setup_root(root: Path, *, valid: bool) -> None:
    weekend_dir = root / "artifacts" / "weekend_training"
    if not valid:
        return
    candidate_dir = root / "artifacts" / "backtest" / "candidate"
    candidate_dir.mkdir(parents=True)
    (candidate_dir / "ranking_2026-01-02.csv").write_text("stock_id\n2330\n", encoding="utf-8")
    write_json(
        weekend_dir / f"weekend_universe_inventory_{RUN_DATE}.json",
        {
            "records": [
                {
                    "combo_id": "combo-ranking-missing",
                    "topic_id": "topic-1",
                    "candidate_dir": "artifacts/backtest/candidate",
                    "dimensions": {"entry_filter": "LOG_GATE", "horizon": "3"},
                    "burn_down_status": "UNSUPPORTED_INPUT",
                    "unsupported_category": "UNSUPPORTED_RANKING_DIR_MISSING",
                    "unsupported_reason": "MISSING_BASELINE_RANKINGS_DIR:artifacts/backtest/production",
                }
            ]
        },
    )
    write_json(
        weekend_dir / f"weekend_training_rollup_{RUN_DATE}.json",
        {
            "summary": {
                "unsupported_count": 3,
                "unsupported_category_counts": {
                    "UNSUPPORTED_RANKING_DIR_MISSING": 1,
                    "UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE": 1,
                    "UNSUPPORTED_REGIME_SLICE_NO_DATA": 1,
                },
                "unsupported_reason_top_counts": {
                    "MISSING_BASELINE_RANKINGS_DIR:artifacts/backtest/production": 1,
                    "UNSUPPORTED_ENTRY_FILTER:TOPIC_DEFAULT": 1,
                    "UNSUPPORTED_REGIME_GATE:NEUTRAL_ONLY": 1,
                },
                "artifact_blocker_count": 7,
                "next_stage_count": 2,
                "low_information_count": 3,
                "processed_before": 4,
                "processed_after": 4,
                "map_expanded_processed": 4,
                "full_universe_total": 10,
                "rollup_classified_total": 10,
            }
        },
    )
    write_json(
        weekend_dir / f"weekend_production_baseline_source_audit_{RUN_DATE}.json",
        {
            "status": "BLOCKED",
            "can_materialize_artifacts_backtest_production": False,
            "required_columns": ["stock_id", "rank"],
            "candidate_sources": [
                {
                    "path": "artifacts/backtest/candidate",
                    "minimum_smoke_candidate": True,
                    "ranking_file_count": 1,
                    "date_coverage": {"start_date": "2026-01-02", "end_date": "2026-01-02"},
                }
            ],
            "summary": {"missing_baseline_rows": 7},
            "unlockable_combo_count_estimate": 1,
        },
    )
    write_json(
        root / "artifacts" / "market_regime_history_2026-06-01.json",
        {
            "summary": {"trade_days": 3},
            "rows": [
                {"trade_date": "2026-01-02", "regime_label": "MIXED_NEUTRAL"},
                {"trade_date": "2026-01-03", "regime_label": "PANIC_SELLING"},
                {"trade_date": "2026-01-04", "regime_label": "RISK_OFF"},
            ],
        },
    )
    write_json(
        root / "artifacts" / "research_map" / "research_fog_map_latest.json",
        {"burn_down_progress": {"executed_progress_count": 4}},
    )


def configure_modules(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    weekend_dir = root / "artifacts" / "weekend_training"
    monkeypatch.setattr(common, "PROJECT_ROOT", root)
    monkeypatch.setattr(common, "WEEKEND_DIR", weekend_dir)
    monkeypatch.setattr(builder, "PROJECT_ROOT", root)
    monkeypatch.setattr(builder, "WEEKEND_DIR", weekend_dir)
    monkeypatch.setattr(builder, "REGIME_HISTORY_PATH", root / "artifacts" / "market_regime_history_2026-06-01.json")
    monkeypatch.setattr(builder, "RESEARCH_MAP_PATH", root / "artifacts" / "research_map" / "research_fog_map_latest.json")


def normalized_json_sha(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["production_impact"] == common.PRODUCTION_IMPACT
    payload.pop("generated_at", None)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_contracts(root: Path, stems: list[str]) -> dict[str, dict[str, str]]:
    weekend_dir = root / "artifacts" / "weekend_training"
    return {
        stem: {
            "json": normalized_json_sha(weekend_dir / f"{stem}_{RUN_DATE}.json"),
            "markdown": hashlib.sha256((weekend_dir / f"{stem}_{RUN_DATE}.md").read_bytes()).hexdigest(),
        }
        for stem in stems
    }


def run_profile(
    profile: str,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> dict[str, Any]:
    if profile == "campaign":
        exit_code = builder.main(["--profile", profile, "--date", RUN_DATE, "--training-date", RUN_DATE])
        stems = [
            "weekend_production_baseline_provenance_design",
            "weekend_topic_default_entry_filter_contract_audit",
            "weekend_regime_slice_data_adequacy_audit",
            "overnight_campaign_summary",
        ]
    elif profile == "ranking-dir-smoke":
        exit_code = builder.main(["--profile", profile, "--date", RUN_DATE, "--sample-size", "1"])
        stems = ["weekend_ranking_dir_unlock_smoke"]
    else:
        exit_code = builder.main(["--profile", profile, "--date", RUN_DATE])
        stems = ["weekend_unsupported_unlock_audit"]
    return {
        "exit_code": exit_code,
        "console": json.loads(capsys.readouterr().out),
        "files": file_contracts(root, stems),
    }


@pytest.mark.parametrize("valid", [True, False], ids=["valid", "missing"])
def test_profiles_preserve_legacy_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    valid: bool,
) -> None:
    fixture = "valid" if valid else "missing"
    for profile in ("campaign", "ranking-dir-smoke", "unsupported-unlock"):
        root = tmp_path / profile
        setup_root(root, valid=valid)
        configure_modules(root, monkeypatch)
        assert run_profile(profile, root, monkeypatch, capsys) == EXPECTED[fixture][profile]


def test_verifier_consumers_accept_all_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "consumer-gates"
    setup_root(root, valid=True)
    weekend_dir = root / "artifacts" / "weekend_training"
    rollup_path = weekend_dir / f"weekend_training_rollup_{RUN_DATE}.json"
    rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
    rollup["summary"].update(
        {
            "unsupported_count": 574695,
            "unsupported_category_counts": {
                "UNSUPPORTED_RANKING_DIR_MISSING": 202176,
                "UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE": 88695,
                "UNSUPPORTED_REGIME_SLICE_NO_DATA": 283824,
            },
            "unsupported_reason_top_counts": {
                "MISSING_BASELINE_RANKINGS_DIR:artifacts/backtest/production": 202176,
                "UNSUPPORTED_ENTRY_FILTER:TOPIC_DEFAULT": 88695,
                "UNSUPPORTED_REGIME_GATE:NEUTRAL_ONLY": 283824,
            },
            "artifact_blocker_count": 202176,
        }
    )
    write_json(rollup_path, rollup)
    source_path = weekend_dir / f"weekend_production_baseline_source_audit_{RUN_DATE}.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["summary"]["missing_baseline_rows"] = 202176
    write_json(source_path, source)
    configure_modules(root, monkeypatch)
    monkeypatch.setattr(campaign_verifier, "WEEKEND_DIR", weekend_dir)
    monkeypatch.setattr(
        campaign_verifier,
        "VERIFICATION_PATH",
        weekend_dir / "overnight_campaign_summary_verification_latest.json",
    )

    for profile in ("campaign", "ranking-dir-smoke", "unsupported-unlock"):
        run_profile(profile, root, monkeypatch, capsys)

    campaign = campaign_verifier.build_verification(RUN_DATE, RUN_DATE)
    ranking = ranking_verifier.build_payload(RUN_DATE, builder.smoke_paths(RUN_DATE)[0])
    unsupported = unsupported_verifier.build_payload(RUN_DATE, builder.audit_paths(RUN_DATE)[0])

    assert campaign["status"] == "OK", campaign["errors"]
    assert ranking["status"] == "OK", ranking["errors"]
    assert unsupported["status"] == "OK", unsupported["errors"]

    monkeypatch.setattr(
        sys,
        "argv",
        ["verify_weekend_overnight_campaign_summary.py", "--date", RUN_DATE, "--training-date", RUN_DATE],
    )
    assert campaign_verifier.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "OK"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_weekend_ranking_dir_unlock_smoke.py",
            "--date",
            RUN_DATE,
            "--output",
            "artifacts/weekend_training/ranking_verification.json",
        ],
    )
    assert ranking_verifier.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "status": "OK",
        "failed_count": 0,
        "output": "artifacts/weekend_training/ranking_verification.json",
    }

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_weekend_unsupported_unlock_audit.py",
            "--date",
            RUN_DATE,
            "--output",
            "artifacts/weekend_training/unsupported_verification.json",
        ],
    )
    assert unsupported_verifier.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "status": "OK",
        "failed_count": 0,
        "output": "artifacts/weekend_training/unsupported_verification.json",
    }

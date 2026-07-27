from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import verify_closed_regime_runtime as runtime_verifier


RUN_DATE = "2099-01-05"


def write_history(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "market-regime-history.v2",
                "contract": {"research_only": True},
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )


def write_contract(path: Path) -> None:
    path.write_text('{"contract":"fixture"}\n', encoding="utf-8")


def regime_row(
    trade_date: str,
    *,
    base_regime: str = "RISK_OFF",
    is_transition: bool = False,
) -> dict[str, object]:
    return {
        "trade_date": trade_date,
        "as_of_date": trade_date,
        "base_regime": base_regime,
        "family_tags": [],
        "is_transition": is_transition,
    }


def test_daily_public_path_enables_closed_regime_with_verified_history() -> None:
    script = (PROJECT_ROOT / "scripts" / "run_daily_research_quota.sh").read_text(
        encoding="utf-8"
    )

    assert "--closed-regime-research" in script
    assert "--market-regime-history" in script
    assert "closed_regime_research=true" in script


def test_daily_public_command_emits_closed_regime_receipt(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    shutil.copy(
        PROJECT_ROOT / "scripts" / "run_daily_research_quota.sh",
        scripts_dir / "run_daily_research_quota.sh",
    )
    history = tmp_path / "history.json"
    contract = tmp_path / "contract.json"
    fake_python = tmp_path / "fake_python.py"
    command_capture = tmp_path / "command.json"
    write_history(history, [regime_row(RUN_DATE)])
    write_contract(contract)
    fake_python.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

script = sys.argv[1]
args = sys.argv[2:]
root = Path.cwd()
def value(flag):
    return args[args.index(flag) + 1]

if script.endswith("verify_closed_regime_runtime.py"):
    output = root / value("--output")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "status": "OK",
        "closed_regime_research": True,
        "exact_regime": {"identity_id": "RISK_OFF|"},
        "market_regime_history": {"path": value("--market-regime-history"), "sha256": "fixture"},
        "research_contract": {"sha256": "fixture"},
        "production_impact": "NO_PRODUCTION_CHANGE",
    }))
elif script.endswith("run_autonomous_research.py"):
    assert "--closed-regime-research" in args
    assert "--market-regime-history" in args
    Path(os.environ["COMMAND_CAPTURE"]).write_text(json.dumps(args))
    output = root / value("--output")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        "schema_version": "autonomous-research-run.v1",
        "status": "OK",
        "contract": {"closed_regime_research": True},
        "inputs": {
            "closed_regime_research": True,
            "market_regime_history": value("--market-regime-history"),
            "from_queue": True,
        },
        "selected_topics": [],
        "topic_runs": [],
        "outcome": {"decision": "NO_EXECUTABLE_TOPIC"},
    }))
elif script.endswith("verify_daily_research_quota.py"):
    output = root / "artifacts/autonomous_research/daily_research_quota_verification_latest.json"
    output.write_text('{"status":"PARTIAL_NO_MORE_WORK"}')
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    env = {
        **os.environ,
        "TOP10_RESEARCH_PYTHON": str(fake_python),
        "TOP10_RESEARCH_DATE": RUN_DATE,
        "TOP10_MARKET_REGIME_HISTORY": str(history),
        "TOP10_REGIME_RESEARCH_CONTRACT": str(contract),
        "TOP10_REFRESH_RESEARCH_MAP": "0",
        "COMMAND_CAPTURE": str(command_capture),
    }

    completed = subprocess.run(
        ["bash", str(scripts_dir / "run_daily_research_quota.sh")],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    command = json.loads(command_capture.read_text(encoding="utf-8"))
    assert command[command.index("--market-regime-history") + 1] == str(history)
    receipt = json.loads(
        (
            tmp_path
            / f"artifacts/autonomous_research/closed_regime_runtime_{RUN_DATE}.json"
        ).read_text(encoding="utf-8")
    )
    assert receipt["closed_regime_research"] is True
    assert receipt["exact_regime"]["identity_id"] == "RISK_OFF|"


def test_missing_regime_history_fails_closed(tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    write_contract(contract)

    with pytest.raises(FileNotFoundError):
        runtime_verifier.verify_runtime(
            RUN_DATE,
            tmp_path / "missing.json",
            contract,
        )


def test_future_only_regime_history_fails_closed(tmp_path: Path) -> None:
    history = tmp_path / "future.json"
    contract = tmp_path / "contract.json"
    write_history(history, [regime_row("2099-01-06")])
    write_contract(contract)

    with pytest.raises(ValueError, match="找不到具有 as_of_date"):
        runtime_verifier.verify_runtime(RUN_DATE, history, contract)


@pytest.mark.parametrize(
    ("base_regime", "is_transition"),
    [("UNKNOWN", False), ("RISK_OFF", True)],
)
def test_unknown_or_transition_current_regime_fails_closed(
    tmp_path: Path,
    base_regime: str,
    is_transition: bool,
) -> None:
    history = tmp_path / "blocked.json"
    contract = tmp_path / "contract.json"
    write_history(
        history,
        [
            regime_row(
                RUN_DATE,
                base_regime=base_regime,
                is_transition=is_transition,
            )
        ],
    )
    write_contract(contract)

    with pytest.raises(ValueError, match="UNKNOWN/transition"):
        runtime_verifier.verify_runtime(RUN_DATE, history, contract)

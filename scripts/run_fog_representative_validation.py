#!/usr/bin/env python3
"""只在 storage validation sandbox 執行歷史 exact-regime 代表性 topic。"""

from __future__ import annotations

import json
import contextlib
import hashlib
import importlib
import io
import os
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DATE = "2026-08-31"
FIXTURE_IDENTITY = {
    "base_regime": "NARROW_LEADER",
    "family_tags": ["BIG_BULL", "HIGH_CHOPPY"],
}
CANDIDATE_DIR = (
    "artifacts/research_rankings/"
    "vwap_narrow_only_balanced_top10_long_2025-01-02_2026-05-15"
)
BASELINE_DIR = (
    "artifacts/backtest/"
    "historical_rankings_current_model_fog_2025-06-03_2026-07-28_ce643797"
)
FIXTURE_ROOT = Path("artifacts/autonomous_research/validation_fixture")
NOFORK_PLAN_NAME = "fog_nofork_plan_v1.json"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def run_inprocess(
    command: list[str],
    *,
    project_head: str | None = None,
    step_runner: Any | None = None,
) -> subprocess.CompletedProcess[str]:
    """固定三階段的開發候選；下游 git／run_step 仍須獨立證明停止。"""
    if os.environ.get("TOP10_STORAGE_VALIDATION_MODE") != "1":
        raise ValueError("VALIDATION_MODE_REQUIRED")
    if len(command) < 2 or command[0] != str(PROJECT_ROOT / ".venv/bin/python"):
        raise ValueError("FIXED_FOG_PHASE_REQUIRED")
    script = command[1]
    allowed = {str(PROJECT_ROOT / "scripts" / name) for name in (
        "publish_research_batch_intent.py", "run_autonomous_research.py",
        "verify_research_spine_batch.py",
    )}
    if script not in allowed:
        raise ValueError("FIXED_FOG_PHASE_REQUIRED")
    stdout, stderr = io.StringIO(), io.StringIO()
    # 僅顯式接既有三個 callable；不執行任意路徑、不改 sys.argv。
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        if script == str(PROJECT_ROOT / "scripts/publish_research_batch_intent.py"):
            from scripts.publish_research_batch_intent import main as publish_main
            entry = publish_main
            restore = None
            entry_kwargs = (
                {"project_head": project_head} if project_head is not None else {}
            )
        elif script == str(PROJECT_ROOT / "scripts/verify_research_spine_batch.py"):
            from scripts.verify_research_spine_batch import main as verify_main
            entry = verify_main
            restore = None
            entry_kwargs = {}
        else:
            from scripts import run_autonomous_research as research
            entry = research.main
            restore = (research.OUTPUT_DIR, research.RESEARCH_LEDGER_PATH, research.RESEARCH_SPINE_ROOT)
            entry_kwargs = {}
            if project_head is not None:
                entry_kwargs["project_head"] = project_head
            if step_runner is not None:
                entry_kwargs["step_runner"] = step_runner
        try:
            try:
                code = entry(command[2:], **entry_kwargs)
            except SystemExit as error:
                if error.code is None:
                    code = 0
                elif isinstance(error.code, int):
                    code = error.code
                else:
                    print(error.code, file=sys.stderr)
                    code = 1
            except Exception:
                # 子程序原會非零退出並留下 traceback；同程序候選保留此失敗語意。
                traceback.print_exc()
                code = 1
        finally:
            if restore is not None:
                research.OUTPUT_DIR, research.RESEARCH_LEDGER_PATH, research.RESEARCH_SPINE_ROOT = restore
    return subprocess.CompletedProcess(command, code, stdout.getvalue(), stderr.getvalue())


def run_research_step_inprocess(name: str, command: list[str]) -> dict[str, Any]:
    """只執行固定 matrix／compare callable，保留原 step receipt 語意。"""

    started = datetime.now(timezone.utc)
    fixed_scripts = {
        "baseline.strategy_matrix": "scripts/run_backtest_strategy_matrix.py",
        "candidate.strategy_matrix": "scripts/run_backtest_strategy_matrix.py",
        "compare.strategy_matrices": "scripts/compare_strategy_matrices.py",
    }
    script = command[1] if len(command) >= 2 else ""
    interpreter_ok = bool(command) and Path(command[0]).resolve() == Path(sys.executable).resolve()
    if not interpreter_ok or fixed_scripts.get(name) != script:
        ended = datetime.now(timezone.utc)
        return {
            "name": name,
            "status": "BLOCKED",
            "returncode": None,
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "command": command,
            "stdout_tail": "",
            "stderr_tail": "fixed no-fork runner is not allowlisted",
        }
    module_name = (
        "scripts.run_backtest_strategy_matrix"
        if script == "scripts/run_backtest_strategy_matrix.py"
        else "scripts.compare_strategy_matrices"
    )
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            module = importlib.import_module(module_name)
            try:
                code = module.main(command[2:])
            except SystemExit as error:
                if error.code is None:
                    code = 0
                elif isinstance(error.code, int):
                    code = error.code
                else:
                    print(error.code, file=sys.stderr)
                    code = 1
            except Exception:
                traceback.print_exc()
                code = 1
        except Exception:
            traceback.print_exc()
            code = 1
    ended = datetime.now(timezone.utc)
    return {
        "name": name,
        "status": "OK" if code == 0 else "FAILED",
        "returncode": code,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "command": command,
        "stdout_tail": stdout.getvalue()[-3000:],
        "stderr_tail": stderr.getvalue()[-3000:],
    }


def fail(reason: str, completed: subprocess.CompletedProcess[str] | None = None) -> int:
    payload: dict[str, Any] = {"status": "FAIL", "reason_code": reason}
    if completed is not None:
        payload.update(
            {
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
            }
        )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    return 1


def build_commands(source_root: Path, fixture_root: Path, batch_id: str) -> dict[str, Any]:
    """FOG-IO-001：只建構絕對路徑與 argv，不建立目錄或執行 workload。"""
    source_root = source_root.resolve()
    fixture_root = fixture_root.resolve()
    python_bin = source_root / ".venv" / "bin" / "python"
    source_history = source_root / "artifacts" / "market_regime_history.json"
    fixture_history = fixture_root / "market_regime_history.json"
    corpus_root = fixture_root / "research_spine"
    ledger = fixture_root / "research_ledger.duckdb"
    output = fixture_root / f"fog_representative_validation_{FIXTURE_DATE}.json"
    verification = fixture_root / f"fog_representative_batch_verification_{FIXTURE_DATE}.json"
    runner_args = [
        str(source_root / "scripts/run_autonomous_research.py"),
        "--date",
        FIXTURE_DATE,
        "--research-batch-id",
        batch_id,
        "--execute",
        "--closed-regime-research",
        "--market-regime-history",
        str(fixture_history),
        "--research-contract",
        str(source_root / "config/regime_research_contract.json"),
        "--candidate-dir",
        str(source_root / CANDIDATE_DIR),
        "--baseline-dir",
        str(source_root / BASELINE_DIR),
        "--max-topics",
        "12",
        "--execute-topic-count",
        "1",
        "--development-screen-topic-count",
        "1",
        "--max-ranking-files",
        "8",
        "--development-screen-on-sealed-exhaustion",
        "--output",
        str(output),
    ]
    publish = [
        str(python_bin),
        str(source_root / "scripts/publish_research_batch_intent.py"),
        "--batch-id",
        batch_id,
        "--execution-epoch",
        FIXTURE_DATE,
        "--requested-research-stage",
        "DEVELOPMENT_SCREEN",
        "--allowed-research-stage",
        "DEVELOPMENT_SCREEN",
        "--output",
        str(output),
        "--corpus-root",
        str(corpus_root),
        "--ledger",
        str(ledger),
        "--manager-root",
        str(fixture_root),
        "--",
        *runner_args,
    ]
    verify = [
        str(python_bin),
        str(source_root / "scripts/verify_research_spine_batch.py"),
        "--batch-id",
        batch_id,
        "--corpus-root",
        str(corpus_root),
        "--run-artifact",
        str(output),
        "--output",
        str(verification),
    ]
    return {
        "source_history": source_history, "fixture_history": fixture_history,
        "corpus_root": corpus_root, "output": output,
        "publish": publish, "execute": [str(python_bin), *runner_args], "verify": verify,
    }


def _validation_root(validation_root: Path) -> Path:
    root = Path(os.path.abspath(validation_root))
    if root.resolve(strict=True) != root or not root.is_dir():
        raise ValueError("INVALID_SHARED_VALIDATION_ROOT")
    source = PROJECT_ROOT.resolve(strict=True)
    if root.is_relative_to(source) or source.is_relative_to(root):
        raise ValueError("OVERLAPPING_SHARED_VALIDATION_ROOT")
    if (root / ".git").exists() or (root / ".git").is_symlink():
        raise ValueError("NO_GIT_VALIDATION_ROOT_REQUIRED")
    return root


def _require_pinned_source_commit(source_commit: str) -> None:
    if (
        os.environ.get("TOP10_STORAGE_VALIDATION_MODE") != "1"
        or not re.fullmatch(r"[0-9a-f]{40,64}", source_commit)
        or source_commit != os.environ.get("TOP10_VALIDATION_SOURCE_COMMIT")
    ):
        raise ValueError("NOFORK_SOURCE_COMMIT_NOT_PINNED")


def _validate_fixture_history(path: Path) -> None:
    history = json.loads(path.read_text(encoding="utf-8"))
    rows = history.get("rows") if isinstance(history.get("rows"), list) else []
    matching = [row for row in rows if row.get("trade_date") == FIXTURE_DATE]
    if len(matching) != 1 or {
        "base_regime": matching[0].get("base_regime"),
        "family_tags": sorted(matching[0].get("family_tags") or []),
    } != FIXTURE_IDENTITY:
        raise ValueError("FIXTURE_REGIME_IDENTITY_MISMATCH")


def _prepare_fixture_commands(root: Path, batch_id: str) -> dict[str, Any]:
    commands = build_commands(PROJECT_ROOT, root / FIXTURE_ROOT, batch_id)
    fixture_history = commands["fixture_history"]
    fixture_history.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(commands["source_history"], fixture_history)
    _validate_fixture_history(fixture_history)
    return commands


def _command_plan_sha256(commands: dict[str, Any]) -> str:
    encoded = json.dumps(
        {
            key: commands[key]
            for key in ("publish", "execute", "verify")
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".tmp")
    staging.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(staging, path)


def _finalize_representative(
    *,
    commands: dict[str, Any],
    batch_id: str,
    intent_id: str,
) -> int:
    output = commands["output"]
    payload = json.loads(output.read_text(encoding="utf-8"))
    topic_runs = payload.get("topic_runs") if isinstance(payload.get("topic_runs"), list) else []
    if not topic_runs:
        return fail("REPRESENTATIVE_WORKLOAD_EMPTY")
    result = {
        "schema_version": "fog-representative-validation.v1",
        "status": "PASS",
        "fixture_date": FIXTURE_DATE,
        "fixture_identity": FIXTURE_IDENTITY,
        "batch_id": batch_id,
        "batch_intent_id": intent_id,
        "topic_runs": topic_runs,
        "production_promotion_allowed": False,
    }
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "topic_run_count": len(topic_runs),
                "output": str(output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def prepare_nofork_candidate(
    *,
    validation_root: Path,
    source_commit: str,
    batch_id: str | None = None,
) -> int:
    """第一葉：準備固定 fixture 並發布 intent；不啟研究或其他程序。"""

    _require_pinned_source_commit(source_commit)
    root = _validation_root(validation_root)
    resolved_batch_id = batch_id or (
        f"research-{FIXTURE_DATE}-{datetime.now().strftime('%H%M%S')}-{os.getpid()}"
    )
    commands = _prepare_fixture_commands(root, resolved_batch_id)
    publish = run_inprocess(
        commands["publish"],
        project_head=source_commit,
    )
    if publish.returncode != 0:
        return fail("BATCH_INTENT_PUBLICATION_FAILED", publish)
    intent_id = publish.stdout.strip().splitlines()[-1]
    plan = {
        "schema_version": "fog-nofork-plan.v1",
        "source_root": str(PROJECT_ROOT.resolve(strict=True)),
        "source_commit": source_commit,
        "validation_root": str(root),
        "batch_id": resolved_batch_id,
        "batch_intent_id": intent_id,
        "command_plan_sha256": _command_plan_sha256(commands),
    }
    _atomic_json(commands["output"].parent / NOFORK_PLAN_NAME, plan)
    print(
        json.dumps(
            {
                "status": "PREPARED",
                "batch_id": resolved_batch_id,
                "batch_intent_id": intent_id,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def execute_nofork_candidate(
    *,
    validation_root: Path,
    source_commit: str,
) -> int:
    """第二葉：同程序執行 matrix／compare／verify，沿既有輸出契約收尾。"""

    _require_pinned_source_commit(source_commit)
    root = _validation_root(validation_root)
    plan_path = root / FIXTURE_ROOT / NOFORK_PLAN_NAME
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if (
        plan.get("schema_version") != "fog-nofork-plan.v1"
        or plan.get("source_root") != str(PROJECT_ROOT.resolve(strict=True))
        or plan.get("source_commit") != source_commit
        or plan.get("validation_root") != str(root)
    ):
        raise ValueError("NOFORK_PLAN_SOURCE_IDENTITY_MISMATCH")
    batch_id = str(plan.get("batch_id") or "")
    intent_id = str(plan.get("batch_intent_id") or "")
    commands = build_commands(PROJECT_ROOT, root / FIXTURE_ROOT, batch_id)
    _validate_fixture_history(commands["fixture_history"])
    if plan.get("command_plan_sha256") != _command_plan_sha256(commands):
        raise ValueError("NOFORK_PLAN_COMMAND_MISMATCH")
    intent_path = (
        commands["corpus_root"]
        / "batch_intents"
        / f"{intent_id.removeprefix('sha256:')}.json"
    )
    execute = run_inprocess(
        [*commands["execute"], "--research-batch-intent", str(intent_path)],
        project_head=source_commit,
        step_runner=run_research_step_inprocess,
    )
    if execute.returncode != 0:
        return fail("REPRESENTATIVE_TOPIC_EXECUTION_FAILED", execute)
    verify = run_inprocess(commands["verify"])
    if verify.returncode != 0:
        return fail("REPRESENTATIVE_BATCH_VERIFICATION_FAILED", verify)
    return _finalize_representative(
        commands=commands,
        batch_id=batch_id,
        intent_id=intent_id,
    )


def main(*, validation_root: Path | None = None, inprocess: bool = False) -> int:
    if os.environ.get("TOP10_STORAGE_VALIDATION_MODE") != "1":
        return fail("VALIDATION_MODE_REQUIRED")
    root = PROJECT_ROOT
    if validation_root is not None:
        # 僅 pinned shared helper 傳入；不新增 CLI 或環境變數啟動旁路。
        root = Path(os.path.abspath(validation_root))
        if root.resolve(strict=True) != root or not root.is_dir():
            return fail("INVALID_SHARED_VALIDATION_ROOT")
        if root.is_relative_to(PROJECT_ROOT.resolve()) or PROJECT_ROOT.resolve().is_relative_to(root):
            return fail("OVERLAPPING_SHARED_VALIDATION_ROOT")
    if (root / ".git").exists() or (root / ".git").is_symlink():
        return fail("NO_GIT_VALIDATION_ROOT_REQUIRED")

    batch_id = (
        f"research-{FIXTURE_DATE}-{datetime.now().strftime('%H%M%S')}-{os.getpid()}"
    )
    commands = build_commands(PROJECT_ROOT, root / FIXTURE_ROOT, batch_id)
    fixture_history = commands["fixture_history"]
    output = commands["output"]
    fixture_history.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(commands["source_history"], fixture_history)
    history = json.loads(fixture_history.read_text(encoding="utf-8"))
    rows = history.get("rows") if isinstance(history.get("rows"), list) else []
    matching = [row for row in rows if row.get("trade_date") == FIXTURE_DATE]
    if len(matching) != 1 or {
        "base_regime": matching[0].get("base_regime"),
        "family_tags": sorted(matching[0].get("family_tags") or []),
    } != FIXTURE_IDENTITY:
        return fail("FIXTURE_REGIME_IDENTITY_MISMATCH")

    # 候選只由明示 callable 啟用；既有 helper／CLI 預設仍走原入口。
    execute_phase = run_inprocess if inprocess else run
    publish = execute_phase(commands["publish"])
    if publish.returncode != 0:
        return fail("BATCH_INTENT_PUBLICATION_FAILED", publish)
    intent_id = publish.stdout.strip().splitlines()[-1]
    intent_path = commands["corpus_root"] / "batch_intents" / f"{intent_id.removeprefix('sha256:')}.json"
    execute = execute_phase([*commands["execute"], "--research-batch-intent", str(intent_path)])
    if execute.returncode != 0:
        return fail("REPRESENTATIVE_TOPIC_EXECUTION_FAILED", execute)
    verify = execute_phase(commands["verify"])
    if verify.returncode != 0:
        return fail("REPRESENTATIVE_BATCH_VERIFICATION_FAILED", verify)
    payload = json.loads(output.read_text(encoding="utf-8"))
    topic_runs = payload.get("topic_runs") if isinstance(payload.get("topic_runs"), list) else []
    if not topic_runs:
        return fail("REPRESENTATIVE_WORKLOAD_EMPTY")
    result = {
        "schema_version": "fog-representative-validation.v1",
        "status": "PASS",
        "fixture_date": FIXTURE_DATE,
        "fixture_identity": FIXTURE_IDENTITY,
        "batch_id": batch_id,
        "batch_intent_id": intent_id,
        "topic_runs": topic_runs,
        "production_promotion_allowed": False,
    }
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "topic_run_count": len(topic_runs),
                "output": str(output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

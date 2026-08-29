#!/usr/bin/env python3
"""驗證 production canary capability receipt 是否完整且 fail closed。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_STEPS = ("create", "run", "select", "publish", "transaction", "tag", "push")
REQUIRED_STEP_FIELDS = (
    "entrypoint",
    "inputs",
    "outputs",
    "identity",
    "correlation_id",
    "positive_evidence",
    "negative_evidence",
)


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not value.strip().startswith("<")


def validate_evidence(
    evidence: Any,
    expected_outcome: str,
    receipt_dir: Path,
    label: str,
) -> tuple[list[str], Path | None]:
    failures: list[str] = []
    if not isinstance(evidence, dict):
        return [f"{label} 必須是 object"], None
    artifact = evidence.get("artifact")
    outcome = evidence.get("outcome")
    if not nonempty_string(artifact):
        failures.append(f"{label}.artifact 缺失或仍是 placeholder")
        return failures, None
    artifact_path = Path(artifact)
    if artifact_path.is_absolute():
        failures.append(f"{label}.artifact 必須是 receipt-relative path")
        return failures, None
    resolved = (receipt_dir / artifact_path).resolve()
    if not resolved.is_relative_to(receipt_dir.resolve()):
        failures.append(f"{label}.artifact 不得離開 receipt 目錄：{artifact}")
        return failures, None
    if not resolved.is_file():
        failures.append(f"{label}.artifact 不存在：{artifact}")
    elif resolved.stat().st_size == 0:
        failures.append(f"{label}.artifact 不得為空：{artifact}")
    if outcome != expected_outcome:
        failures.append(f"{label}.outcome 必須是 {expected_outcome}")
    return failures, resolved


def validate_receipt(receipt: Any, receipt_dir: Path) -> list[str]:
    failures: list[str] = []
    if not isinstance(receipt, dict):
        return ["receipt 必須是 JSON object"]
    if receipt.get("schema_version") != 1:
        failures.append("schema_version 必須是 1")
    for field in ("execution_line_id", "production_target", "correlation_id"):
        if not nonempty_string(receipt.get(field)):
            failures.append(f"{field} 缺失或仍是 placeholder")
    if receipt.get("canary_created") is not False:
        failures.append("canary_created 必須是 false")

    steps = receipt.get("steps")
    if not isinstance(steps, dict):
        failures.append("steps 必須是 object")
        return failures
    if set(steps) != set(REQUIRED_STEPS):
        missing = sorted(set(REQUIRED_STEPS) - set(steps))
        unknown = sorted(set(steps) - set(REQUIRED_STEPS))
        failures.append(f"steps 不完整：missing={missing or 'none'} unknown={unknown or 'none'}")

    receipt_correlation = receipt.get("correlation_id")
    evidence_paths: set[Path] = set()
    for step_name in REQUIRED_STEPS:
        step = steps.get(step_name)
        if not isinstance(step, dict):
            failures.append(f"steps.{step_name} 必須是 object")
            continue
        for field in REQUIRED_STEP_FIELDS:
            if field not in step:
                failures.append(f"steps.{step_name}.{field} 缺失")
        for field in ("entrypoint", "identity"):
            if not nonempty_string(step.get(field)):
                failures.append(f"steps.{step_name}.{field} 缺失或仍是 placeholder")
        for field in ("inputs", "outputs"):
            value = step.get(field)
            if not isinstance(value, list) or not value or not all(nonempty_string(item) for item in value):
                failures.append(f"steps.{step_name}.{field} 必須是非空字串陣列且不得含 placeholder")
        if step.get("correlation_id") != receipt_correlation:
            failures.append(f"steps.{step_name}.correlation_id 未與全鏈一致")

        positive_failures, positive_path = validate_evidence(
            step.get("positive_evidence"), "PASS", receipt_dir, f"steps.{step_name}.positive_evidence"
        )
        negative_failures, negative_path = validate_evidence(
            step.get("negative_evidence"), "BLOCKED", receipt_dir, f"steps.{step_name}.negative_evidence"
        )
        failures.extend(positive_failures)
        failures.extend(negative_failures)
        if positive_path is not None and positive_path == negative_path:
            failures.append(f"steps.{step_name} 正向與負向證據不得共用 artifact")
        for evidence_path in (positive_path, negative_path):
            if evidence_path is None:
                continue
            if evidence_path in evidence_paths:
                failures.append(f"steps.{step_name} evidence artifact 不得跨步驟重用")
            evidence_paths.add(evidence_path)
    return failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "failures": [str(exc)]}, ensure_ascii=False))
        return 1

    failures = validate_receipt(receipt, args.receipt.parent)
    status = "BLOCKED" if failures else "READY"
    result = {
        "status": status,
        "execution_line_id": receipt.get("execution_line_id"),
        "failures": failures,
    }
    if failures:
        result["next_action"] = "在同一 execution_line_id 建立入口修補卡；不得建立 canary 或平行 selector/canary 線"
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

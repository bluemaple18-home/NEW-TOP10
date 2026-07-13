"""每日報牌 v2 shadow-only 可續跑工作流程。"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pickle
import subprocess
import time
from typing import Any
from uuid import uuid4

from app.contracts.daily_v2 import (
    MANIFEST_SCHEMA_VERSION,
    DailyStep,
    StepSpec,
    validate_run_identity,
    validate_step_order,
)


MAX_OUTPUT_SUMMARY_CHARS = 2_000


class WorkflowExecutionError(RuntimeError):
    """每日 v2 任一步驟失敗，且 manifest 已留下失敗證據。"""


class _StepFailure(RuntimeError):
    def __init__(
        self,
        reason: str,
        *,
        error_type: str,
        exit_code: int | None = None,
        stderr_summary: str = "",
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.error_type = error_type
        self.exit_code = exit_code
        self.stderr_summary = stderr_summary


class DailyWorkflowV2:
    """執行固定五步、原子 manifest 與同 run_id resume。"""

    def __init__(
        self,
        *,
        run_id: str,
        run_date: str,
        run_root: Path,
        model_path: Path,
        steps: tuple[StepSpec, ...],
        working_directory: Path | None = None,
    ) -> None:
        validate_run_identity(run_id, run_date)
        validate_step_order(steps)
        self.run_id = run_id
        self.run_date = run_date
        self.run_root = Path(run_root).expanduser().resolve()
        self.run_dir = (self.run_root / run_id).resolve()
        self.model_path = Path(model_path).expanduser().resolve()
        self.steps = steps
        self.working_directory = (working_directory or Path.cwd()).resolve()
        self.manifest_path = self.run_dir / "manifest.json"
        self._assert_within(self.run_dir, self.run_root, "run directory")
        for step in self.steps:
            for output in step.outputs:
                self._assert_within(self._resolve_artifact(output), self.run_dir, f"{step.name.value} output")

    def run(self) -> dict[str, Any]:
        """執行或續跑；已完成步驟只驗證內容，絕不重寫。"""

        self.run_dir.mkdir(parents=True, exist_ok=True)
        manifest = self._load_or_create_manifest()
        if manifest["status"] == "finished":
            self._verify_finished_prefix(manifest)
            return manifest

        if manifest["status"] == "failed":
            manifest["resume_count"] += 1
            manifest.setdefault("resumed_at", []).append(self._now())
        manifest["status"] = "started"
        manifest["finished_at"] = None
        self._write_manifest(manifest)

        for spec, step_record in zip(self.steps, manifest["steps"], strict=True):
            if step_record["status"] == "finished":
                self._verify_finished_step(spec, step_record)
                continue
            try:
                self._execute_step(manifest, spec, step_record)
            except _StepFailure as exc:
                manifest["status"] = "failed"
                manifest["finished_at"] = self._now()
                self._write_manifest(manifest)
                raise WorkflowExecutionError(exc.reason) from exc

        manifest["status"] = "finished"
        manifest["finished_at"] = self._now()
        self._write_manifest(manifest)
        return manifest

    def _load_or_create_manifest(self) -> dict[str, Any]:
        contract = self._contract_payload()
        signature = self._sha256_bytes(self._canonical_json(contract).encode("utf-8"))
        if self.manifest_path.exists():
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            expected = (
                manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION
                and manifest.get("run_id") == self.run_id
                and manifest.get("run_date") == self.run_date
                and manifest.get("contract", {}).get("signature") == signature
            )
            if not expected:
                raise WorkflowExecutionError("existing manifest does not match this run contract")
            return manifest

        now = self._now()
        return {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "run_id": self.run_id,
            "run_date": self.run_date,
            "status": "started",
            "shadow_only": True,
            "live_send_enabled": False,
            "run_dir": str(self.run_dir),
            "model": self._snapshot(self.model_path),
            "contract": {"signature": signature, **contract},
            "started_at": now,
            "updated_at": now,
            "finished_at": None,
            "resume_count": 0,
            "resumed_at": [],
            "steps": [self._new_step_record(step) for step in self.steps],
        }

    def _contract_payload(self) -> dict[str, Any]:
        return {
            "working_directory": str(self.working_directory),
            "model_path": str(self.model_path),
            "steps": [step.as_contract_dict() for step in self.steps],
        }

    def _new_step_record(self, spec: StepSpec) -> dict[str, Any]:
        return {
            "name": spec.name.value,
            "status": "pending",
            "command": self._expand_command(spec.command),
            "timeout_seconds": spec.timeout_seconds,
            "declared_inputs": [str(self._resolve_artifact(path)) for path in spec.inputs],
            "declared_outputs": [str(self._resolve_artifact(path)) for path in spec.outputs],
            "inputs": [],
            "outputs": [],
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "failure": None,
            "attempts": [],
        }

    def _execute_step(
        self,
        manifest: dict[str, Any],
        spec: StepSpec,
        step_record: dict[str, Any],
    ) -> None:
        started_at = self._now()
        started_clock = time.monotonic()
        command = self._expand_command(spec.command)
        attempt: dict[str, Any] = {
            "attempt": len(step_record["attempts"]) + 1,
            "status": "started",
            "command": command,
            "started_at": started_at,
            "finished_at": None,
            "duration_seconds": None,
            "exit_code": None,
            "stdout_summary": "",
            "stderr_summary": "",
            "failure_reason": None,
        }
        step_record.update(
            {
                "status": "started",
                "command": command,
                "started_at": started_at,
                "finished_at": None,
                "duration_seconds": None,
                "failure": None,
            }
        )
        step_record["attempts"].append(attempt)
        self._write_manifest(manifest)

        try:
            step_record["inputs"] = self._required_snapshots(spec.inputs, "input")
            if spec.name is DailyStep.VALIDATE:
                self._load_model()
            completed = self._run_subprocess(command, spec.timeout_seconds)
            attempt["exit_code"] = completed.returncode
            attempt["stdout_summary"] = self._summary(completed.stdout)
            attempt["stderr_summary"] = self._summary(completed.stderr)
            step_record["outputs"] = self._required_snapshots(spec.outputs, "output")
            self._validate_step_output(spec)
        except _StepFailure as exc:
            finished_at = self._now()
            duration = round(time.monotonic() - started_clock, 6)
            attempt.update(
                {
                    "status": "failed",
                    "finished_at": finished_at,
                    "duration_seconds": duration,
                    "exit_code": exc.exit_code,
                    "stderr_summary": exc.stderr_summary,
                    "failure_reason": exc.reason,
                }
            )
            step_record.update(
                {
                    "status": "failed",
                    "finished_at": finished_at,
                    "duration_seconds": duration,
                    "failure": {
                        "reason": exc.reason,
                        "error_type": exc.error_type,
                        "command": command,
                        "exit_code": exc.exit_code,
                        "stderr_summary": exc.stderr_summary,
                    },
                }
            )
            self._write_manifest(manifest)
            raise

        finished_at = self._now()
        duration = round(time.monotonic() - started_clock, 6)
        attempt.update(
            {
                "status": "finished",
                "finished_at": finished_at,
                "duration_seconds": duration,
            }
        )
        step_record.update(
            {
                "status": "finished",
                "finished_at": finished_at,
                "duration_seconds": duration,
                "failure": None,
            }
        )
        self._write_manifest(manifest)

    def _run_subprocess(self, command: list[str], timeout_seconds: float) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                command,
                cwd=self.working_directory,
                text=True,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stderr = self._summary(exc.stderr)
            timeout_message = f"timed out after {timeout_seconds:g}s"
            if stderr:
                stderr = f"{stderr}\n{timeout_message}"
            else:
                stderr = timeout_message
            raise _StepFailure(
                timeout_message,
                error_type="timeout",
                exit_code=124,
                stderr_summary=stderr,
            ) from exc
        if completed.returncode != 0:
            stderr = self._summary(completed.stderr) or "<empty stderr>"
            raise _StepFailure(
                f"subprocess failed: exit_code={completed.returncode}",
                error_type="subprocess_error",
                exit_code=completed.returncode,
                stderr_summary=stderr,
            )
        return completed

    def _validate_step_output(self, spec: StepSpec) -> None:
        if spec.name is DailyStep.ETL:
            self._validate_dated_json(self._resolve_artifact(spec.outputs[0]), "ETL")
        elif spec.name is DailyStep.VALIDATE:
            payload = self._validate_dated_json(self._resolve_artifact(spec.outputs[0]), "validation")
            if payload.get("valid") is not True:
                raise self._validation_failure("validation artifact must set valid=true")
        elif spec.name is DailyStep.RANK:
            self._validate_ranking(self._resolve_artifact(spec.outputs[0]))
        elif spec.name is DailyStep.REPORT:
            payload = self._validate_dated_json(self._resolve_artifact(spec.outputs[0]), "report")
            if payload.get("shadow_only") is not True:
                raise self._validation_failure("report must set shadow_only=true")
        elif spec.name is DailyStep.PUBLISH_READY:
            payload = self._validate_dated_json(self._resolve_artifact(spec.outputs[0]), "publish-ready")
            if payload.get("shadow_only") is not True:
                raise self._validation_failure("publish-ready must set shadow_only=true")
            if payload.get("send_enabled") is not False:
                raise self._validation_failure("publish-ready must set send_enabled=false")
            if payload.get("publish_ready") is not True:
                raise self._validation_failure("publish-ready artifact must set publish_ready=true")

    def _load_model(self) -> None:
        try:
            with self.model_path.open("rb") as handle:
                model = pickle.load(handle)
        except Exception as exc:
            raise self._validation_failure(f"model load failed: {self.model_path}: {exc}") from exc
        if model is None:
            raise self._validation_failure(f"model load failed: {self.model_path}: payload is null")

    def _validate_dated_json(self, path: Path, label: str) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise self._validation_failure(f"{label} artifact is not readable JSON: {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise self._validation_failure(f"{label} artifact must be a JSON object: {path}")
        actual_date = payload.get("run_date")
        if actual_date != self.run_date:
            raise self._validation_failure(
                f"{label} date mismatch: expected {self.run_date}, got {actual_date}"
            )
        return payload

    def _validate_ranking(self, path: Path) -> None:
        expected_name = f"ranking_{self.run_date}.csv"
        if path.name != expected_name:
            raise self._validation_failure(
                f"ranking date mismatch: expected filename {expected_name}, got {path.name}"
            )
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        except OSError as exc:
            raise self._validation_failure(f"ranking is not readable: {path}: {exc}") from exc
        if len(rows) != 10:
            raise self._validation_failure(f"ranking must contain exactly 10 rows, got {len(rows)}")
        if any(not row.get("rank") or not row.get("stock_id") for row in rows):
            raise self._validation_failure("ranking rows must contain rank and stock_id")
        try:
            ranks = [int(row["rank"]) for row in rows]
        except (TypeError, ValueError) as exc:
            raise self._validation_failure("ranking rank values must be integers") from exc
        if ranks != list(range(1, 11)):
            raise self._validation_failure(f"ranking ranks must be 1..10, got {ranks}")
        stock_ids = [str(row["stock_id"]).strip() for row in rows]
        if len(set(stock_ids)) != 10:
            raise self._validation_failure("ranking stock_id values must be unique")
        for date_field in ("run_date", "ranking_date", "date"):
            values = {row.get(date_field) for row in rows if row.get(date_field)}
            if values and values != {self.run_date}:
                actual = ", ".join(sorted(str(value) for value in values))
                raise self._validation_failure(
                    f"ranking date mismatch: expected {self.run_date}, got {actual}"
                )

    def _required_snapshots(self, paths: tuple[str, ...], kind: str) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for raw_path in paths:
            path = self._resolve_artifact(raw_path)
            if not path.is_file():
                raise self._validation_failure(f"required {kind} is missing: {path}")
            if kind == "output":
                self._assert_within(path.resolve(), self.run_dir, "step output")
            snapshots.append(self._snapshot(path))
        return snapshots

    def _verify_finished_prefix(self, manifest: dict[str, Any]) -> None:
        for spec, record in zip(self.steps, manifest["steps"], strict=True):
            if record["status"] != "finished":
                raise WorkflowExecutionError("finished manifest contains a non-finished step")
            self._verify_finished_step(spec, record)

    def _verify_finished_step(self, spec: StepSpec, record: dict[str, Any]) -> None:
        current_inputs = self._required_snapshots(spec.inputs, "input")
        current_outputs = self._required_snapshots(spec.outputs, "output")
        if not self._same_snapshots(record.get("inputs", []), current_inputs):
            raise WorkflowExecutionError(f"cannot resume {spec.name.value}: finished-step input changed")
        if not self._same_snapshots(record.get("outputs", []), current_outputs):
            raise WorkflowExecutionError(f"cannot resume {spec.name.value}: finished-step output changed")

    @staticmethod
    def _same_snapshots(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> bool:
        wanted = ("path", "size_bytes", "sha256")
        return [tuple(item.get(key) for key in wanted) for item in previous] == [
            tuple(item.get(key) for key in wanted) for item in current
        ]

    def _resolve_artifact(self, raw_path: str) -> Path:
        expanded = self._expand_tokens(raw_path)
        path = Path(expanded).expanduser()
        return path.resolve() if path.is_absolute() else (self.run_dir / path).resolve()

    def _expand_command(self, command: tuple[str, ...]) -> list[str]:
        return [self._expand_tokens(part) for part in command]

    def _expand_tokens(self, value: str) -> str:
        tokens = {
            "run_dir": str(self.run_dir),
            "run_root": str(self.run_root),
            "run_id": self.run_id,
            "run_date": self.run_date,
            "model_path": str(self.model_path),
        }
        for name, replacement in tokens.items():
            value = value.replace(f"{{{name}}}", replacement)
        return value

    def _snapshot(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {"path": str(path), "exists": False, "size_bytes": None, "sha256": None}
        return {
            "path": str(path),
            "exists": True,
            "size_bytes": path.stat().st_size,
            "sha256": self._sha256_file(path),
        }

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        manifest["updated_at"] = self._now()
        temp_path = self.manifest_path.with_name(f".{self.manifest_path.name}.{uuid4().hex}.tmp")
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.manifest_path)
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _assert_within(path: Path, root: Path, label: str) -> None:
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"{label} must stay inside shadow run directory: {path}") from exc

    @staticmethod
    def _validation_failure(reason: str) -> _StepFailure:
        return _StepFailure(reason, error_type="validation_error", stderr_summary=reason)

    @staticmethod
    def _summary(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        value = value.strip()
        if len(value) <= MAX_OUTPUT_SUMMARY_CHARS:
            return value
        return value[-MAX_OUTPUT_SUMMARY_CHARS:]

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _sha256_bytes(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _canonical_json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

#!/usr/bin/env python3
"""驗證入榜天數計算只使用目標日期以前的 ranking artifact。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_ranking(path: Path, rows: list[tuple[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stock_id", "stock_name", "close"])
        writer.writeheader()
        for stock_id, stock_name in rows:
            writer.writerow({"stock_id": stock_id, "stock_name": stock_name, "close": "100"})


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="top10-candidate-persistence-") as tmp:
        root = Path(tmp)
        rankings_dir = root / "artifacts"
        rankings_dir.mkdir()
        write_ranking(rankings_dir / "ranking_2026-05-24.csv", [("1111", "甲"), ("2222", "乙")])
        write_ranking(rankings_dir / "ranking_2026-05-25.csv", [("1111", "甲"), ("3333", "丙")])
        target = rankings_dir / "ranking_2026-05-26.csv"
        write_ranking(target, [("3333", "丙"), ("1111", "甲"), ("4444", "丁")])
        write_ranking(rankings_dir / "ranking_2026-05-27.csv", [("4444", "丁"), ("3333", "丙")])

        output = root / "candidate_persistence_2026-05-26.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "build_candidate_persistence.py"),
                "--ranking",
                str(target),
                "--rankings-dir",
                str(rankings_dir),
                "--output",
                str(output),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            return completed.returncode
        payload = json.loads(output.read_text(encoding="utf-8"))
        by_stock = {item["stock_id"]: item for item in payload["items"]}

        external_history_dir = root / "external_history"
        external_history_dir.mkdir()
        write_ranking(external_history_dir / "ranking_2026-05-24.csv", [("1111", "甲"), ("2222", "乙")])
        write_ranking(external_history_dir / "ranking_2026-05-25.csv", [("1111", "甲"), ("3333", "丙")])
        write_ranking(external_history_dir / "ranking_2026-05-27.csv", [("4444", "丁"), ("3333", "丙")])
        external_dir = root / "external"
        external_dir.mkdir()
        external_target = external_dir / "ranking_2026-05-26.csv"
        write_ranking(external_target, [("3333", "丙"), ("1111", "甲"), ("4444", "丁")])
        external_output = root / "candidate_persistence_external_2026-05-26.json"
        external_completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "build_candidate_persistence.py"),
                "--ranking",
                str(external_target),
                "--rankings-dir",
                str(external_history_dir),
                "--output",
                str(external_output),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if external_completed.returncode != 0:
            print(external_completed.stdout)
            print(external_completed.stderr, file=sys.stderr)
            return external_completed.returncode
        external_payload = json.loads(external_output.read_text(encoding="utf-8"))
        external_by_stock = {item["stock_id"]: item for item in external_payload["items"]}

        checks = {
            "status_ok": payload["schema_version"] == "candidate-persistence.v1",
            "no_future_date": "2026-05-27" not in by_stock["4444"]["history_dates"],
            "consecutive_1111": by_stock["1111"]["consecutive_ranked_days"] == 3,
            "consecutive_3333": by_stock["3333"]["consecutive_ranked_days"] == 2,
            "new_4444": by_stock["4444"]["consecutive_ranked_days"] == 1,
            "rank_delta_1111": by_stock["1111"]["rank_delta"] == -1,
            "external_target_in_history": "2026-05-26" in external_by_stock["1111"]["history_dates"],
            "external_target_consecutive_1111": external_by_stock["1111"]["consecutive_ranked_days"] == 3,
            "external_target_previous_1111": external_by_stock["1111"]["previous_rank"] == 1,
            "external_target_history_count": external_payload["history_artifact_count"] == 3,
        }
        ok = all(checks.values())
        artifact = PROJECT_ROOT / "artifacts" / "candidate_persistence_verification_latest.json"
        artifact.parent.mkdir(exist_ok=True)
        artifact.write_text(
            json.dumps(
                {
                    "schema_version": "candidate-persistence-verification.v1",
                    "status": "OK" if ok else "FAILED",
                    "checks": checks,
                    "note": "uses TemporaryDirectory and synthetic ranking artifacts",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if ok:
            print(f"CANDIDATE_PERSISTENCE_OK output={artifact}")
            return 0
        print(f"CANDIDATE_PERSISTENCE_FAILED output={artifact}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

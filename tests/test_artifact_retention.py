from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.artifact_management import RetentionPolicy, build_inventory, render_summary
from scripts import artifact_retention


def set_mtime(path: Path, value: str) -> None:
    timestamp = datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()
    path.touch()
    path.chmod(0o644)
    os.utime(path, (timestamp, timestamp))


def snapshot(root: Path) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        result[str(path.relative_to(root))] = (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())
    return result


class ArtifactRetentionTest(unittest.TestCase):
    def test_policy_boundaries_are_keep_keep_keep_archive_archive_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artifacts"
            root.mkdir()
            as_of = "2026-07-13"
            for age in (7, 8, 30, 31, 90, 91):
                path = root / f"age_{age}.txt"
                path.write_text(str(age), encoding="utf-8")
                mtime = datetime.fromisoformat(as_of) - timedelta(days=age)
                set_mtime(path, mtime.date().isoformat())

            inventory = build_inventory(
                root,
                policy=RetentionPolicy(recent_days=7, archive_after_days=30, delete_after_days=90),
                as_of=as_of,
            )

        actions = {item["path"]: item["candidate_action"] for item in inventory["files"]}
        self.assertEqual(actions, {
            "age_7.txt": "keep",
            "age_8.txt": "keep",
            "age_30.txt": "keep",
            "age_31.txt": "archive_candidate",
            "age_90.txt": "archive_candidate",
            "age_91.txt": "delete_candidate",
        })
        reasons = {item["path"]: item["retention_reason"] for item in inventory["files"]}
        self.assertIn("尚未超過 30 日 archive 閾值", reasons["age_8.txt"])
        self.assertIn("超過 30 日 archive 閾值", reasons["age_31.txt"])
        self.assertIn("超過 90 日 delete 閾值", reasons["age_91.txt"])

    def test_external_manifest_symlink_is_not_inventoried_or_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "artifacts"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            candidate = root / "candidate.txt"
            candidate.write_text("candidate", encoding="utf-8")
            set_mtime(candidate, "2026-01-01")
            external_manifest = outside / "manifest.json"
            external_manifest.write_text(
                json.dumps({"artifact_paths": ["candidate.txt"]}), encoding="utf-8"
            )
            os.symlink(external_manifest, root / "external_manifest.json")

            inventory = build_inventory(
                root,
                policy=RetentionPolicy(recent_days=7, archive_after_days=30, delete_after_days=90),
                as_of="2026-07-13",
            )

        paths = {item["path"] for item in inventory["files"]}
        self.assertNotIn("external_manifest.json", paths)
        candidate_row = next(item for item in inventory["files"] if item["path"] == "candidate.txt")
        self.assertEqual(candidate_row["candidate_action"], "delete_candidate")

    def test_inventory_classifies_keep_archive_and_delete_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artifacts"
            (root / "latest").mkdir(parents=True)
            (root / "models").mkdir()
            (root / "research").mkdir()
            (root / "latest" / "report.txt").write_text("latest", encoding="utf-8")
            (root / "models" / "candidate.pkl").write_bytes(b"model")
            (root / "research" / "recent.json").write_text("recent", encoding="utf-8")
            (root / "research" / "archive.json").write_text("archive", encoding="utf-8")
            (root / "research" / "delete.json").write_text("delete", encoding="utf-8")
            (root / "research" / "manifest.json").write_text(
                json.dumps({"artifact_paths": ["research/delete.json"]}), encoding="utf-8"
            )
            set_mtime(root / "latest" / "report.txt", "2026-01-01")
            set_mtime(root / "models" / "candidate.pkl", "2026-01-01")
            set_mtime(root / "research" / "recent.json", "2026-07-10")
            set_mtime(root / "research" / "archive.json", "2026-05-20")
            set_mtime(root / "research" / "delete.json", "2026-01-01")
            set_mtime(root / "research" / "manifest.json", "2026-01-01")
            before = snapshot(root)
            policy = RetentionPolicy(recent_days=7, archive_after_days=30, delete_after_days=90)

            inventory = build_inventory(root, policy=policy, as_of="2026-07-13")
            after = snapshot(root)

        self.assertEqual(before, after)
        actions = {item["path"]: item["candidate_action"] for item in inventory["files"]}
        self.assertEqual(actions["latest/report.txt"], "keep")
        self.assertEqual(actions["models/candidate.pkl"], "keep")
        self.assertEqual(actions["research/recent.json"], "keep")
        self.assertEqual(actions["research/archive.json"], "archive_candidate")
        self.assertEqual(actions["research/delete.json"], "keep")
        self.assertEqual(inventory["summary"]["reclaimable_bytes"], 0)

    def test_old_unreferenced_file_is_delete_candidate_and_result_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artifacts"
            root.mkdir()
            target = root / "old.bin"
            target.write_bytes(b"old")
            set_mtime(target, "2026-01-01")
            policy = RetentionPolicy(recent_days=7, archive_after_days=30, delete_after_days=90)

            first = build_inventory(root, policy=policy, as_of="2026-07-13")
            second = build_inventory(root, policy=policy, as_of="2026-07-13")

        self.assertEqual(first, second)
        self.assertEqual(first["files"][0]["candidate_action"], "delete_candidate")
        self.assertEqual(first["summary"]["reclaimable_bytes"], 3)

    def test_cli_writes_json_and_prints_human_summary_without_mutating_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "artifacts"
            root.mkdir()
            file_path = root / "old.txt"
            file_path.write_text("fixture", encoding="utf-8")
            set_mtime(file_path, "2026-01-01")
            output = Path(tmp) / "inventory.json"
            before = snapshot(root)
            with patch("builtins.print") as print_mock:
                exit_code = artifact_retention.main(
                    ["--dry-run", "--root", str(root), "--as-of", "2026-07-13", "--output", str(output)]
                )
            after = snapshot(root)
            output_exists = output.exists()
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(before, after)
        self.assertTrue(output_exists)
        self.assertTrue(payload["dry_run"])
        printed = "\n".join(call.args[0] for call in print_mock.call_args_list)
        self.assertIn("delete_candidate=1", printed)
        self.assertIn("本次未刪除", render_summary(payload))


if __name__ == "__main__":
    unittest.main()

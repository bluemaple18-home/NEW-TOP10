from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class Top10AgentStatusRollupCliTest(unittest.TestCase):
    def test_no_latest_does_not_write_latest_rollup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts"
            run_dir = artifacts / "harness_status" / "2026-06-25" / "scoped-run"
            events_dir = run_dir / "events"
            events_dir.mkdir(parents=True)
            event = {
                "schema_version": "top10-agent-status-event.v1",
                "run_id": "scoped-run",
                "run_date": "2026-06-25",
                "agent_id": "fog_map",
                "status": "ok",
                "decision": "pass",
                "started_at": "2026-06-25T00:00:00+00:00",
                "finished_at": "2026-06-25T00:00:01+00:00",
                "duration_seconds": 1,
                "input_refs": [],
                "artifact_paths": [],
                "failure_reason": None,
                "next_action": None,
                "metrics": {},
            }
            (events_dir / "fog_map.json").write_text(json.dumps(event), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "agents": [
                            {
                                "id": "fog_map",
                                "label": "Fog Map Bot",
                                "index": 12,
                                "lane": "research",
                                "responsibility": "test",
                            }
                        ],
                        "flows": [],
                        "channels": [],
                    }
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_top10_agent_status_rollup.py",
                    "--run-date",
                    "2026-06-25",
                    "--run-id",
                    "scoped-run",
                    "--artifacts-dir",
                    str(artifacts),
                    "--manifest",
                    str(manifest),
                    "--no-latest",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((run_dir / "rollup.json").exists())
            self.assertFalse((artifacts / "harness_status" / "2026-06-25" / "latest_rollup.json").exists())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.data.monitoring_repository import MonitoringRepository
from app.services.monitoring_service import MonitoringService

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routers.monitoring import create_monitoring_router
except ModuleNotFoundError:
    FastAPI = None
    TestClient = None
    create_monitoring_router = None


class MonitoringTop10HarnessApiTest(unittest.TestCase):
    def test_service_loads_latest_harness_rollup(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_rollup(project)
            service = MonitoringService(MonitoringRepository(project))

            response = service.top10_harness_status()

            self.assertTrue(response.available)
            self.assertEqual(response.run_id, "daily-2026-06-23")
            self.assertEqual(response.status, "warning")
            self.assertEqual(response.agents[0].agent_id, "harness_runner")
            self.assertEqual(response.formal_tasks[0].task_id, "TOP10-HARNESS-01-harness_runner")
            self.assertEqual(response.flow_edges[0].edge_status, "active")
            self.assertEqual(response.artifact_path, "artifacts/harness_status/2026-06-23/latest_rollup.json")

    def test_router_returns_harness_status(self):
        if FastAPI is None or TestClient is None or create_monitoring_router is None:
            self.skipTest("fastapi is not installed in this test environment")
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_rollup(project)
            service = MonitoringService(MonitoringRepository(project))
            app = FastAPI()
            app.include_router(create_monitoring_router(service))
            client = TestClient(app)

            response = client.get("/api/monitoring/top10-harness")

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["available"])
            self.assertEqual(payload["run_id"], "daily-2026-06-23")
            self.assertEqual(payload["agents"][0]["agent_id"], "harness_runner")
            self.assertEqual(payload["formal_tasks"][0]["task_id"], "TOP10-HARNESS-01-harness_runner")


def write_rollup(project: Path) -> None:
    latest = project / "artifacts" / "harness_status" / "2026-06-23" / "latest_rollup.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "top10-agent-status-rollup.v1",
        "generated_at": "2026-06-23T12:10:00+00:00",
        "run_date": "2026-06-23",
        "run_id": "daily-2026-06-23",
        "status": "warning",
        "summary": {"agent_count": 13, "event_count": 9},
        "agents": [
            {
                "agent_id": "harness_runner",
                "label": "Harness Runner",
                "index": 1,
                "lane": "daily",
                "status": "ok",
                "decision": "pass",
                "missing": False,
            }
        ],
        "formal_tasks": [
            {
                "task_id": "TOP10-HARNESS-01-harness_runner",
                "agent_id": "harness_runner",
                "label": "Harness Runner",
                "index": 1,
                "lane": "daily",
                "status": "ok",
                "decision": "pass",
                "requires_attention": False,
                "missing": False,
            }
        ],
        "flow_edges": [
            {
                "edge_id": "TOP10-FLOW-01-harness_runner-to-preflight",
                "from": "harness_runner",
                "to": "preflight",
                "kind": "daily",
                "label": "run request",
                "target_kind": "agent",
                "source_status": "ok",
                "target_status": "ok",
                "connected": True,
                "edge_status": "active",
            }
        ],
        "channels": [],
        "flows": [],
        "validation_errors": {},
    }
    latest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

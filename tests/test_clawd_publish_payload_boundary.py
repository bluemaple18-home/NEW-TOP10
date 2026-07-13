"""驗證 Clawd payload 邊界拆分後仍與 production 輸出完全等價。"""

from __future__ import annotations

import importlib
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "clawd_publish_payload"
REPORT_FIXTURE = FIXTURE_DIR / "daily_report_2026-07-10.json"
EXPECTED_PAYLOAD = FIXTURE_DIR / "expected_payload_2026-07-10.json"
EXPECTED_MESSAGE = FIXTURE_DIR / "expected_message_2026-07-10.md"
ADAPTER = PROJECT_ROOT / "scripts" / "build_clawd_publish_payload.py"


def normalize_payload(payload: dict) -> dict:
    """只正規化卡片允許忽略的時間戳與本機絕對路徑。"""
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    normalized["generated_at"] = "<generated_at>"
    report_path = Path(normalized["source"]["daily_report"])
    normalized["source"]["daily_report"] = report_path.relative_to(PROJECT_ROOT).as_posix()
    normalized["artifacts"]["payload"] = Path(normalized["artifacts"]["payload"]).name
    normalized["artifacts"]["message"] = Path(normalized["artifacts"]["message"]).name
    return normalized


class ClawdPublishPayloadBoundaryTest(unittest.TestCase):
    def test_cli_matches_pre_refactor_payload_and_markdown_golden(self) -> None:
        """公開 CLI 的完整 payload 與 Markdown 必須和拆分前 golden 相同。"""
        with tempfile.TemporaryDirectory(prefix="top10_clawd_payload_") as temp:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ADAPTER),
                    "--report",
                    str(REPORT_FIXTURE),
                    "--artifacts-dir",
                    temp,
                    "--channel",
                    "discord",
                    "--to",
                    "channel:fixture",
                    "--max-items",
                    "10",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            payload = json.loads((Path(temp) / "clawd_publish_payload_2026-07-10.json").read_text(encoding="utf-8"))
            message = (Path(temp) / "clawd_publish_message_2026-07-10.md").read_text(encoding="utf-8")

        expected_payload = json.loads(EXPECTED_PAYLOAD.read_text(encoding="utf-8"))
        expected_message = EXPECTED_MESSAGE.read_text(encoding="utf-8")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(normalize_payload(payload), expected_payload)
        self.assertEqual(message, expected_message)
        self.assertEqual(payload["message_markdown"], expected_message)

    def test_known_script_import_consumers_remain_available(self) -> None:
        """既有 daily tape/RR verifier 的 script imports 不得失效。"""
        adapter = importlib.import_module("scripts.build_clawd_publish_payload")
        for name in (
            "build_payload",
            "ai_feature_names",
            "classified_publish_sections",
            "notification_summary",
            "raw_signal_texts",
        ):
            self.assertTrue(callable(getattr(adapter, name)), name)

    def test_domain_module_has_no_cli_or_artifact_io(self) -> None:
        """app domain 不得解析 CLI、讀 reference CSV 或直接寫 artifact。"""
        domain = importlib.import_module("app.publishing.clawd_payload")
        source = inspect.getsource(domain)
        self.assertNotIn("argparse", source)
        self.assertNotIn("csv.DictReader", source)
        self.assertNotIn(".write_text(", source)

    def test_reference_loader_boundary_parses_all_inputs(self) -> None:
        """四組外部 lookup 應由獨立 loader 解析成 domain 明確輸入。"""
        loader = importlib.import_module("app.publishing.clawd_payload_io")
        with tempfile.TemporaryDirectory(prefix="top10_clawd_reference_") as temp:
            project = Path(temp)
            reference_dir = project / "data" / "reference"
            config_dir = project / "config"
            reference_dir.mkdir(parents=True)
            config_dir.mkdir()
            (reference_dir / "stock_industry_map.csv").write_text(
                "stock_id,industry_name,sector_name\n2330,IC生產製造,科技\n",
                encoding="utf-8",
            )
            (reference_dir / "stock_concept_membership.csv").write_text(
                "stock_id,concept_type,canonical_name,raw_concept_name,confidence\n"
                "2330,theme,AI伺服器,,0.9\n"
                "2330,theme,台積電,,0.8\n"
                "2330,industry,不應載入,,1.0\n",
                encoding="utf-8",
            )
            (config_dir / "notification_theme_buckets.csv").write_text(
                "priority,bucket,industry_keywords,concept_keywords,notes\n"
                "10,半導體/IC,IC|半導體,AI伺服器,fixture\n",
                encoding="utf-8",
            )
            (config_dir / "notification_industry_buckets.csv").write_text(
                "industry_name,notification_bucket,notes\nIC生產製造,半導體/IC,fixture\n",
                encoding="utf-8",
            )

            inputs = loader.load_payload_reference_data(project)

        self.assertEqual(inputs["industry_map"]["2330"]["industry_name"], "IC生產製造")
        self.assertEqual(inputs["concept_map"]["2330"], ["AI伺服器", "台積電"])
        self.assertEqual(inputs["industry_bucket_map"], {"IC生產製造": "半導體/IC"})
        self.assertEqual(inputs["bucket_rules"][0]["industry_keywords"], ["IC", "半導體"])
        self.assertEqual(inputs["bucket_rules"][0]["concept_keywords"], ["AI伺服器"])


if __name__ == "__main__":
    unittest.main()

"""驗證 uv 環境定義與公開操作文件一致。"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class EnvironmentContractTests(unittest.TestCase):
    """避免相依來源與新主機操作文件再次分歧。"""

    def test_pyproject_separates_dependency_groups(self) -> None:
        with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
            pyproject = tomllib.load(handle)

        dependencies = pyproject["project"]["dependencies"]
        groups = pyproject["dependency-groups"]
        self.assertTrue(any(item.startswith("pandas") for item in dependencies))
        self.assertTrue(any(item.startswith("lightgbm") for item in dependencies))
        self.assertEqual({"training", "reporting", "dev"}, set(groups))

    def test_operational_docs_use_uv_lockfile_workflow(self) -> None:
        documents = ("README.md", "QUICKSTART.md", "DEVELOPMENT.md")
        for document in documents:
            content = (PROJECT_ROOT / document).read_text(encoding="utf-8")
            self.assertIn("uv sync", content, document)
            self.assertNotIn("--with-requirements", content, document)
            self.assertNotIn("/Users/", content, document)

        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("每日 17:30", readme)
        self.assertNotIn("每日 22:00", readme)
        self.assertIn("scripts/run_daily.sh", readme)
        self.assertIn("scripts/run_daily_publish.sh", readme)

        documented_paths = (
            ".env.sample",
            "app/agent_b_ranking.py",
            "app/model_monitor.py",
            "app/pipeline_cli.py",
            "docs/AUTOMATION.md",
            "scripts/daily_retrain.sh",
            "scripts/run_daily.sh",
            "scripts/run_daily_publish.sh",
            "scripts/start_ui.sh",
        )
        for documented_path in documented_paths:
            self.assertTrue((PROJECT_ROOT / documented_path).exists(), documented_path)

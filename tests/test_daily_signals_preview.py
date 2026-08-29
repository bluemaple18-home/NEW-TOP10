import builtins
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pandas as pd

from app.pipeline.report_stage import ReportStage


def _context(tmp_path: Path) -> dict:
    return {
        "dirs": {"artifacts": tmp_path},
        "universe_df": pd.DataFrame({"stock_id": ["2330"]}),
    }


def test_skip_flag_writes_report_without_importing_or_calling_preview(tmp_path: Path) -> None:
    original_import = builtins.__import__
    preview_imports: list[str] = []

    def track_import(name, *args, **kwargs):
        if name == "app.visualization":
            preview_imports.append(name)
        return original_import(name, *args, **kwargs)

    with patch.dict(os.environ, {"TOP10_SKIP_SIGNALS_PREVIEW": "1"}), patch(
        "builtins.__import__", side_effect=track_import
    ):
        ReportStage().execute(pd.DataFrame(), _context(tmp_path))

    assert (tmp_path / "etl_report.md").is_file()
    assert preview_imports == []


def test_unset_flag_keeps_existing_preview_call(tmp_path: Path) -> None:
    preview = Mock()
    visualization = ModuleType("app.visualization")
    visualization.generate_signals_preview = preview
    context = _context(tmp_path)

    with patch.dict(os.environ, {}, clear=False), patch.dict(
        sys.modules, {"app.visualization": visualization}
    ):
        os.environ.pop("TOP10_SKIP_SIGNALS_PREVIEW", None)
        ReportStage().execute(pd.DataFrame(), context)

    preview.assert_called_once()
    assert preview.call_args.args[0] is context["universe_df"]
    assert preview.call_args.kwargs == {
        "output_path": str(tmp_path / "signals_preview.png")
    }


def test_daily_script_exports_skip_flag() -> None:
    script = Path("scripts/run_daily.sh").read_text(encoding="utf-8")

    assert "export TOP10_SKIP_SIGNALS_PREVIEW=1" in script

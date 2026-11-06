"""在受管暫存根執行 Daily 四組回歸；路徑隨專案搬遷，不碰正式排程。"""
import os
import re
import shutil
import sys
from pathlib import Path

SUITES = (
    'tests/test_external_cache_wiring.py',
    'tests/test_external_cache_repair.py',
    'tests/test_daily_storage_validation.py',
    'tests/test_storage_safety.py',
)


def prune_finished_links(cases: Path) -> None:
    """只移除 pytest 已回收目錄留下的同層便利連結，不碰 fixture 連結。"""
    for link in cases.glob('*current'):
        if not link.is_symlink():
            continue
        target = Path(os.readlink(link))
        if not target.is_absolute():
            target = link.parent / target
        if (target.parent == cases and re.fullmatch(re.escape(link.name[:-7]) + r'\d+', target.name)
                and not os.path.lexists(target)):
            link.unlink()


def run(root: Path, suites=SUITES) -> int:
    import pytest
    root = root.resolve(strict=True)
    temporary = root / 'pytest/tmp'
    cases = root / 'pytest/cases'
    if (root / 'pytest').is_symlink() or os.path.lexists(cases):
        raise RuntimeError('NO_GO: fresh pytest cases root required; existing evidence retained')
    temporary.mkdir(parents=True, exist_ok=True)
    os.environ['TMPDIR'] = str(temporary)
    # tempfile 可能已由上層 import；明示保持所有測試暫存於此 root。
    import tempfile
    tempfile.tempdir = str(temporary)
    for key in tuple(os.environ):
        if key.startswith('AI_CORE_CACHE_') or key in {'TOP10_EXTERNAL_CACHE_ROOT', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS'}:
            del os.environ[key]
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

    class FinishedFixtures:
        def __init__(self):
            self.results = {}

        @pytest.hookimpl(wrapper=True, tryfirst=True)
        def pytest_runtest_makereport(self, item, call):
            report = yield
            state = self.results.setdefault(item.nodeid, {"passed": True, "path": None})
            state["passed"] = state["passed"] and report.passed
            if report.when != "teardown":
                state["path"] = item.funcargs.get("tmp_path", state["path"])
            else:
                self.results.pop(item.nodeid)
                path = state["path"]
                # pytest 自帶 failed retention 不含 teardown error，必須等完整報告。
                if (state["passed"] and isinstance(path, Path) and path.parent == cases
                        and path.is_dir() and not path.is_symlink()):
                    shutil.rmtree(path)
                prune_finished_links(cases)
            return report

    return pytest.main([
        '-q', '--tb=short', '-p', 'no:cacheprovider', '--maxfail=1',
        '-o', 'tmp_path_retention_policy=all',
        '--basetemp=' + str(cases), '--junitxml=' + str(root / 'regression.xml'),
        *suites,
    ], plugins=[FinishedFixtures()])


if __name__ == '__main__':
    os.chdir(Path(__file__).resolve().parents[1])
    raise SystemExit(run(Path(os.environ['TMP_ARTIFACT_ROOT'])))

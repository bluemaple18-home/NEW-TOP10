"""重現 fixture 連結累積，確認修補後容量上限與失敗證據仍成立。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from scripts import run_daily_regression as harness


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='top10-harness-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'pytest').mkdir()
        self.suite = self.root / 'test_cases.py'
        self.env = {**os.environ, 'PYTHONPATH': str(Path(harness.__file__).parent),
                    'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
        self.python = sys.executable

    def call(self, fixed):
        code = ('import run_daily_regression as h; from pathlib import Path; import sys; '
                'raise SystemExit(h.run(Path(sys.argv[1]), [sys.argv[2]]))') if fixed else (
                'import pytest,sys; raise SystemExit(pytest.main(["-q","-p","no:cacheprovider",'
                '"--maxfail=1","--basetemp="+sys.argv[1]+"/pytest/cases",sys.argv[2]]))')
        return subprocess.run([self.python, '-B', '-c', code, str(self.root), str(self.suite)],
                              env=self.env, capture_output=True, text=True, timeout=30)

    def test_accumulation_red_then_green(self):
        # 以較小局部上限重現累積，RED 與 GREEN 並存也不得撞外層八個連結硬閘門。
        self.suite.write_text('import os,sys\nfrom pathlib import Path\n' + '\n'.join(
            f'def test_case_{i}(tmp_path):\n'
            '    (tmp_path / "fixture-python").symlink_to(sys.executable)\n'
            '    count=sum(p.is_symlink() for p in tmp_path.parent.rglob("*"))\n'
            '    assert count <= 2, "symlink fixture count exceeded"\n'
            for i in range(20)))
        red = self.call(False)
        self.assertEqual(1, red.returncode, red.stdout + red.stderr)
        self.assertIn('symlink fixture count exceeded', red.stdout)
        self.root = self.root / 'green'
        self.root.mkdir()
        green = self.call(True)
        self.assertEqual(0, green.returncode, green.stdout + green.stderr)
        self.assertIn('20 passed', green.stdout)
        self.assertEqual([], list((self.root / 'pytest/cases').glob('test_case*')))
        self.assertTrue((self.root / 'regression.xml').is_file())
        print('連結累積反例 RED：超過 8；修補 GREEN：20 passed，passed fixture 已回收')

    def test_failure_keeps_evidence(self):
        self.suite.write_text('def test_failed(tmp_path):\n    (tmp_path/"evidence").write_text("保留")\n    assert False\n')
        result = self.call(True)
        self.assertEqual(1, result.returncode)
        self.assertEqual('保留', (self.root / 'pytest/cases/test_failed0/evidence').read_text())

    def test_teardown_failure_keeps_evidence(self):
        self.suite.write_text('import pytest\n@pytest.fixture\ndef broken(tmp_path):\n'
            '    (tmp_path/"evidence").write_text("保留")\n    yield\n    raise RuntimeError("teardown failed")\n'
            'def test_failed(broken):\n    pass\n')
        result = self.call(True)
        self.assertEqual(1, result.returncode)
        self.assertIn('1 passed, 1 error', result.stdout)
        self.assertEqual('保留', (self.root / 'pytest/cases/test_failed0/evidence').read_text())

    def test_reuse_refused_without_deleting_failed_or_foreign(self):
        self.suite.write_text('def test_failed(tmp_path):\n    (tmp_path/"evidence").write_text("保留")\n    assert False\n')
        self.assertEqual(1, self.call(True).returncode)
        cases = self.root / 'pytest/cases'
        foreign = cases / 'foreign'
        foreign.write_text('不得刪除')
        self.suite.write_text('def test_ok(tmp_path):\n    pass\n')
        result = self.call(True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('fresh pytest cases root required', result.stderr)
        self.assertEqual('保留', (cases / 'test_failed0/evidence').read_text())
        self.assertEqual('不得刪除', foreign.read_text())

    def test_cases_symlink_refused(self):
        foreign = self.root / 'foreign'
        foreign.mkdir()
        (foreign / 'evidence').write_text('不得刪除')
        (self.root / 'pytest/cases').symlink_to(foreign)
        self.suite.write_text('def test_ok(tmp_path):\n    pass\n')
        result = self.call(True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('fresh pytest cases root required', result.stderr)
        self.assertEqual('不得刪除', (foreign / 'evidence').read_text())

    def test_only_exact_dangling_convenience_link_removed(self):
        cases = self.root / 'cases'
        cases.mkdir()
        (cases / 'test_acurrent').symlink_to(cases / 'test_a0')
        (cases / 'foreigncurrent').symlink_to(self.root / 'missing')
        (cases / 'test_b0').mkdir()
        (cases / 'test_bcurrent').symlink_to(cases / 'test_b0')
        (cases / 'test_ccurrent').symlink_to(cases / 'wrong0')
        harness.prune_finished_links(cases)
        self.assertFalse(os.path.lexists(cases / 'test_acurrent'))
        for name in ('foreigncurrent', 'test_bcurrent', 'test_ccurrent'):
            self.assertTrue((cases / name).is_symlink())


if __name__ == '__main__':
    unittest.main()

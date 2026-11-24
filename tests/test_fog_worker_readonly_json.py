"""原生Bash file-mode執行worker的兩段唯讀JSON；不啟完整研究或新增暫存目的地。"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("quota,state,expected", [
    (None, None, "0 UNKNOWN"),
    ({"outcome":{"decision":"TOPIC_SUPPLY_EXHAUSTED"},"topic_runs":[]}, {"status":"PARTIAL_NO_MORE_WORK"}, "1 PARTIAL_NO_MORE_WORK"),
    ({"outcome":{"decision":"NO_EXECUTABLE_TOPIC"},"topic_runs":[]}, {"status":"OK"}, "1 OK"),
    ({"outcome":{"decision":"TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED"},"topic_runs":[]}, {"status":"PARTIAL_RETRYABLE_TOPIC_SUPPLY"}, "0 PARTIAL_RETRYABLE_TOPIC_SUPPLY"),
    ({"outcome":{"decision":"TOPIC_SUPPLY_EXHAUSTED","topic_supply":{"status":"TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED"}},"topic_runs":[]}, {"status":"PARTIAL_RETRYABLE_TOPIC_SUPPLY"}, "0 PARTIAL_RETRYABLE_TOPIC_SUPPLY"),
    ({"outcome":{"decision":"TOPIC_SUPPLY_EXHAUSTED"},"topic_runs":[{"status":"OK"}]}, {"status":"OK"}, "0 OK"),
    ({"outcome":None,"topic_runs":None}, {"status":""}, "0 UNKNOWN"),
    ("corrupt-json", {"status":"OK"}, None),
    ({"outcome":{"decision":"TOPIC_SUPPLY_EXHAUSTED"}}, "corrupt-json", None),
])
def test_readonly_json_file_mode_preserves_terminal_semantics(tmp_path, quota, state, expected):
    raw=(ROOT/'scripts/run_fog_research_worker.sh').read_text()
    start=raw.index('  NO_MORE_WORK="$(');end=raw.index('  if [ "$RESEARCH_STATE"',start)
    body=raw[start:end]
    assert '<<' not in body and body.count('"$PYTHON_BIN" -c')==2
    data=tmp_path/'artifacts/autonomous_research';data.mkdir(parents=True)
    for name,value in [('autonomous_research_daily_quota_2026-11-19.json',quota),('daily_research_quota_verification_latest.json',state)]:
        if value is not None:(data/name).write_text('{' if value=='corrupt-json' else json.dumps(value))
    script=tmp_path/'readonly-json.sh'
    script.write_text('set -euo pipefail\nPYTHON_BIN='+shlex.quote(sys.executable)+'\nRUN_DATE=2026-11-19\n'+body+'printf "%s %s\\n" "$NO_MORE_WORK" "$RESEARCH_STATE"\n')
    environment=os.environ.copy();environment['PYTHONDONTWRITEBYTECODE']='1'
    before={k:environment.get(k) for k in ('TMPDIR','TMP','TEMP','TEMPDIR','TOP10_EXTERNAL_CACHE_ROOT')}
    p=subprocess.run(['/bin/bash',str(script)],cwd=tmp_path,env=environment,capture_output=True,text=True)
    assert {k:environment.get(k) for k in before}==before
    if expected is None:
        assert p.returncode!=0 and 'JSONDecodeError' in p.stderr
    else:
        assert p.returncode==0 and p.stdout.strip()==expected,p.stderr

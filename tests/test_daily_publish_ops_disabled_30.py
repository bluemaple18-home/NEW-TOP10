"""停用ops必須直接略過；啟用失敗與無效設定仍須保留非零退出。"""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('flag,helper_exit,backfill,expected,called',[
    ('false',1,'0',0,False),
    ('true',1,'0',1,True),
    ('true',0,'0',0,True),
    ('[',1,'0',64,False),
    ('true',1,'1',0,False),
    (None,1,'0',0,False),
    ('"true"',1,'0',0,False),
])
def test_postsend_ops_boundary(tmp_path,flag,helper_exit,backfill,expected,called):
    config=tmp_path/'config';config.mkdir()
    (config/'automation.yaml').write_text(('notify: {}' if flag is None else 'notify: {ops_clawd_enabled: '+flag+'}')+'\n')
    helper=tmp_path/'python-helper'
    helper.write_text('#!/bin/bash\nif [ "$1" = "-c" ]; then exec '+repr(sys.executable)+' "$@"; fi\nprintf called >> "$PROJECT_DIR/called"\nexit '+str(helper_exit)+'\n')
    helper.chmod(0o700)
    wrapper=(ROOT/'scripts/run_daily_publish.sh').read_text()
    function=wrapper.split('send_ops_report() {',1)[1].split('\n}',1)[0]
    script=('set -euo pipefail\nexport PROJECT_DIR='+repr(str(tmp_path))+
            '\nPYTHON_BIN='+repr(str(helper))+'\nRUN_DATE=2026-11-06\nLOG_FILE='+repr(str(tmp_path/'case.log'))+
            '\nexport TOP10_BACKFILL='+backfill+'\nsend_ops_report() {'+function+
            '\n}\nif ! send_ops_report; then exit "$OPS_EXIT_CODE"; fi\necho finished\nexit 0\n')
    result=subprocess.run(['/bin/bash','-c',script],capture_output=True,text=True,
                          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    assert result.returncode==expected,result.stderr
    assert (tmp_path/'called').exists() is called

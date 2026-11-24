"""既有wrapper fixture測交接ABI；shim不是venv，不宣稱R identity或原生容量驗證。"""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from tests.test_storage_safety import wrapper_toolchain_fixture

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("case", [
    "fog_directory", "other_directory", "fog_image", "other_image",
    "missing_contract", "missing_venv", "guard_nonzero", "env_failure",
])
def test_fog_directory_only_skips_shared_initializer(tmp_path, case):
    (tmp_path/'scripts').mkdir()
    wrapper=tmp_path/'scripts/run_with_storage_guard.sh'
    shutil.copy2(ROOT/'scripts/run_with_storage_guard.sh',wrapper)
    environment=wrapper_toolchain_fixture(tmp_path)
    config=tmp_path/'ai-core/config'
    envfile=config/'ai_core_env.sh'
    envfile.write_text(envfile.read_text()+
        'export AI_CORE_CACHE_ROOT=fixture-root\n'
        'export AI_CORE_CACHE_MAX_FILES=50000\n'
        'export AI_CORE_CACHE_RESERVED_OTHER_BYTES=0\n')
    if case=='missing_contract':
        envfile.write_text(envfile.read_text()+'unset AI_CORE_CACHE_VOLUME_UUID\n')
    elif case=='env_failure':
        envfile.write_text('return 9\n')
    called=tmp_path/'initializer-called'
    (config/'toolchain_paths.sh').write_text('printf called > "'+str(called)+'"\nreturn 9\n')
    job='reference' if case.startswith('other_') else 'fog-research-worker'
    mode='image' if case.endswith('_image') else 'directory'
    environment.update(AI_CORE_CACHE_MODE=mode,WRAPPER_GUARD_RESULT='42' if case=='guard_nonzero' else '0')
    # 沿既有測試的可執行ABI shim；不建立Python環境，也不執行child workload。
    python=tmp_path/'.venv/bin/python'
    python.parent.mkdir(parents=True)
    if case!='missing_venv':
        python.write_text('#!/bin/bash\nprintf \'HANDOFF\n\'\nprintf \'ARG=%s\n\' "$@"\nprintf \'TMPDIR=%s\n\' "${TMPDIR:-}"\nprintf \'MODE=%s\n\' "${AI_CORE_CACHE_MODE:-}"\nfor argument in "$@"; do\n  if [ "$argument" = --startup-failure ]; then\n    printf \'STARTUP_FAILED\n\'\n    exit 70\n  fi\ndone\nexit "${WRAPPER_GUARD_RESULT:-0}"\n')
        python.chmod(0o700)
    child=['/usr/bin/false','unchanged-child-argument']
    completed=subprocess.run(['/bin/bash',str(wrapper),job,*child],cwd=tmp_path,env=environment,capture_output=True,text=True)
    (tmp_path/'handoff-observation.json').write_text(json.dumps({
        'case':case, 'code':completed.returncode, 'stdout':completed.stdout,
        'stderr':completed.stderr, 'initializer_called':called.exists(),
        'job':job, 'mode':mode,
    },indent=2))
    lines=completed.stdout.splitlines()
    must_source=case in ('other_directory','fog_image','other_image')
    assert called.exists() is must_source
    if case=='missing_venv':
        assert completed.returncode==69 and 'HANDOFF' not in lines
        assert 'requires executable .venv/bin/python' in completed.stderr
        return
    assert lines.count('HANDOFF')==1
    if must_source or case in ('missing_contract','env_failure'):
        assert completed.returncode==70 and 'STARTUP_FAILED' in lines
        assert 'ARG=--startup-failure' in lines
    else:
        assert completed.returncode==(42 if case=='guard_nonzero' else 0),completed.stderr
        assert 'STARTUP_FAILED' not in lines and 'ARG=--startup-failure' not in lines
    args=[line.removeprefix('ARG=') for line in lines if line.startswith('ARG=')]
    assert args[-3:]==['--',*child]
    assert args[args.index('--job')+1]==job
    assert 'TMPDIR='+environment.get('TMPDIR','') in lines
    assert 'MODE='+mode in lines

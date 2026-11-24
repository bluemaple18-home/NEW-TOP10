"""fake sampler只驗既有receipt/marker；不宣稱原生容量或APFS測量。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from app import storage_safety as guard
from app.external_cache import ExternalCache, ExternalCacheError

ROOT=Path(__file__).resolve().parents[1]
REASON="EXTERNAL_CACHE_MANAGED_ADMISSION_DENIED"
SECRET="DO_NOT_PERSIST_message_path_argv_env_9db7"


@pytest.mark.parametrize("case", [
    "errno", "timeout", "host", "none", "cycle", "depth",
    "diagnostic_failure", "other_reason", "other_type", "spoof_source",
])
def test_managed_admission_cause_receipt_is_bounded(tmp_path, monkeypatch, case):
    monkeypatch.delenv('TOP10_EXTERNAL_CACHE_ROOT',raising=False)
    core_dir=Path(os.environ.get('AI_CORE_DIR','/Users/mattkuo/ai-core'))
    monkeypatch.syspath_prepend(str(core_dir/'scripts'))
    import runtime_cache_capacity_gate as core
    host=sys.modules[core.HostCapacityError.__module__]
    gp,jp,rules=guard.load_policy(ROOT/'docs/operations/top10-storage-policy.json','reference')
    cache=ExternalCache.__new__(ExternalCache)
    cache.directory_mode=True
    def fail_errno():
        raise FileNotFoundError(2,SECRET,'/'+SECRET)
    if case=='errno':
        cache._managed=SimpleNamespace(sample=fail_errno)
        def sampler(_):return cache.sample()
    elif case in ('timeout','host','spoof_source'):
        managed=core.ManagedCache.__new__(core.ManagedCache)
        def fail_identity():
            if case=='host':return host.apfs_capacity_snapshot({},'2026-11-19T00:00:00+00:00')
            raise subprocess.TimeoutExpired([SECRET],3,output=SECRET,stderr=SECRET)
        managed._identity=fail_identity
        cache._managed=managed
        if case=='spoof_source':monkeypatch.setattr(core,'__file__','/'+SECRET)
        def sampler(_):return cache.sample()
    else:
        outer=ExternalCacheError(REASON)
        if case=='cycle':
            first=ValueError(SECRET);second=OSError(2,SECRET)
            first.__cause__=second;second.__cause__=first;outer.__cause__=first
        elif case=='depth':
            previous=None
            for i in range(7):
                current=ValueError(SECRET);current.code=i;current.__cause__=previous;previous=current
            outer.__cause__=previous
        elif case=='diagnostic_failure':
            class BrokenDiagnostic(Exception):
                @property
                def errno(self):raise RuntimeError(SECRET)
            outer.__cause__=BrokenDiagnostic(SECRET)
        elif case=='other_reason':
            outer=ExternalCacheError('EXTERNAL_CACHE_RETENTION_EXPIRED');outer.__cause__=ValueError(SECRET)
        elif case=='other_type':
            outer=RuntimeError(SECRET);outer.reason=REASON;outer.__cause__=ValueError(SECRET)
        def sampler(_):raise outer
    code=guard.run_guarded_job(tmp_path,gp,jp,rules,['/usr/bin/false'],sampler=sampler)
    assert code==70
    receipt=tmp_path/'logs/storage_safety/reference_latest.json'
    marker=tmp_path/'logs/storage_safety/restart_denied/reference.json'
    payload=json.loads(receipt.read_text());denial=json.loads(marker.read_text())
    expected_reason='EXTERNAL_CACHE_RETENTION_EXPIRED' if case=='other_reason' else 'GUARD_INTERNAL_ERROR_RuntimeError' if case=='other_type' else REASON
    assert payload['reasons']==[expected_reason] and payload['child_exit_code'] is None
    assert denial['root_receipt']==payload
    assert denial['root_receipt_sha256']==guard._json_payload_sha256(payload)
    detail=payload['internal_error'];assert SECRET not in json.dumps(detail)
    if case in ('diagnostic_failure','other_reason','other_type'):
        assert 'causes' not in detail
    else:
        causes=detail['causes'];assert len(causes)<=4
        for item in causes:
            assert set(item)<= {'type','errno','code','frames'}
            for number in ('errno','code'):
                if number in item:assert type(item[number]) is int and -(2**31)<=item[number]<2**31
            assert len(item.get('frames',[]))<=4
            for frame in item.get('frames',[]):
                assert set(frame)=={'filename','function','line'}
                assert frame['filename'] in ('app/external_cache.py','scripts/runtime_cache_capacity_gate.py','scripts/host_capacity_sensor.py')
        frames=[f for item in causes for f in item.get('frames',[])]
        if case=='errno':
            assert causes[0]['type']=='FileNotFoundError' and causes[0]['errno']==2
            assert any(f['filename']=='app/external_cache.py' and f['function']=='sample' for f in frames)
        elif case=='timeout':
            assert [x['type'] for x in causes]==['ManagedCacheError','TimeoutExpired']
            assert causes[0]['code']==20
            assert any(f['filename']=='scripts/runtime_cache_capacity_gate.py' and f['function']=='sample' for f in frames)
        elif case=='host':assert any(f['filename']=='scripts/host_capacity_sensor.py' for f in frames)
        elif case=='none':assert causes==[]
        elif case=='cycle':assert len(causes)==2 and all('frames' not in x for x in causes)
        elif case=='depth':assert len(causes)==4 and [x['code'] for x in causes]==[6,5,4,3]
        elif case=='spoof_source':assert all(f['filename']!='scripts/runtime_cache_capacity_gate.py' for f in frames)
    before=(receipt.read_bytes(),marker.read_bytes(),marker.stat().st_ino)
    def forbidden_sampler(_):raise AssertionError('early marker不得再取樣')
    assert guard.run_guarded_job(tmp_path,gp,jp,rules,['/usr/bin/false'],sampler=forbidden_sampler)==75
    assert (receipt.read_bytes(),marker.read_bytes(),marker.stat().st_ino)==before

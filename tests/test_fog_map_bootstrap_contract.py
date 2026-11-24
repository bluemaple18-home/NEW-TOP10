"""有限unit fixture驗fresh map階段/實際sample/tamper/finalfail；非代表性資料。"""
from pathlib import Path
import sys

def test_fog_map_bootstrap_contract(tmp_path, monkeypatch):
    import json,os,sys,importlib.util,contextlib,io
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    monkeypatch.setattr(sys,'argv',list(sys.argv))
    root=tmp_path;e=root/'validation_evidence';e.mkdir();base=Path(__file__).resolve().parents[1]
    main=Path(str(Path(__file__).resolve().parents[1]));sys.path[:0]=[str(main),str(main/'scripts')]
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
    from app.research import fog_map_render,map_contract
    from tests.test_research_fog_map_burn_down import weekend_rollup
    m=load('candidate_fog_domain',base/'app/research/fog_map_domain.py')
    v=load('candidate_fog_verifier',base/'scripts/verify_research_fog_map.py')
    r=load('run_controlled_grid_drain_host_runner',base/'scripts/run_controlled_grid_drain_host_runner.py')
    results=[];date='2026-11-19'
    for count in (1,5,12):
        case=root/f'pytest/map-{count}';source=case/'auto';out=case/'map';source.mkdir(parents=True);out.mkdir()
        topics=[{'topic_id':f'test-topic-{i}','candidate_dir':f'artifacts/backtest/test-topic-{i}','manager_status':'candidate','score':1} for i in range(count)]
        dims={'horizon':'3','stop_loss':'none','take_profit':'none','group_exposure':'none'}
        records=[{'topic_id':topics[0]['topic_id'],'combo_id':map_contract.combo_id(topics[0],dims),'dimensions':dims,'status':'OK','decision':'DEVELOPMENT_CANDIDATE','artifact_path':'unit-fixture-only/result.json','finished_at':'2026-11-19T00:00:00+00:00'}]
        def build(rollup=None,rollup_source=None):
            return m.build_payload(date,progress={},registry={'topics':topics},queue={'actions':[{'topic_id':topics[0]['topic_id']}]},history={},history_records=records,weekend_rollup=rollup,weekend_rollup_source=rollup_source,active_expansion_parent={},active_expansion_parent_evidence=None,source_paths={})
        payload=build();total=payload['summary']['expanded_universe_total'];assert payload['full_universe_fog']['sample_count']==min(60000,max(0,total-1));assert payload['full_universe_fog']['executed_sample_count']<=payload['full_universe_fog']['sample_count']
        p=out/f'research_fog_map_{date}.json';html=out/'index.html';(source/f'research_campaign_progress_{date}.json').write_text(json.dumps({'summary':{}}))
        def materialize():
            p.write_text(json.dumps(payload));(out/'research_fog_map_latest.json').write_text(json.dumps(payload));html.write_text(fog_map_render.render_html(payload))
        materialize();monkeypatch.setattr(v,'SOURCE_DIR',source);monkeypatch.setattr(v,'OUTPUT_DIR',out)
        partial=out/'source-verification.json';final=out/'full-verification.json'
        def run(partial_mode):
            sys.argv=['verifier','--date',date,'--payload',str(p),'--html',str(html),'--output',str(partial if partial_mode else final)]+(['--source-only'] if partial_mode else [])
            with contextlib.redirect_stdout(io.StringIO()):code=v.main()
            return code,json.loads((partial if partial_mode else final).read_text())
        # fresh零完成只能由真零history與完整legend支援；錯比率仍拒絕。
        saved_records=records;records=[];payload=build();materialize()
        zero=v.build_payload(date,p,html);facts={c['name']:c['ok'] for c in zero['checks']}
        assert facts['base_and_expanded_progress_separated'] and facts['required_first_version_states_present_or_supported']
        for field in ('base_progress_pct','expanded_progress_pct','progress_pct'):
            payload['summary'][field]=0.001;materialize();bad=v.build_payload(date,p,html)
            assert not next(c['ok'] for c in bad['checks'] if c['name']=='base_and_expanded_progress_separated')
            payload=build()
        payload['legend']=[x for x in payload['legend'] if x['id']!='effective_insight'];materialize()
        assert not next(c['ok'] for c in v.build_payload(date,p,html)['checks'] if c['name']=='required_first_version_states_present_or_supported')
        payload=build();(source/'run_history.jsonl').write_text(json.dumps(saved_records[0])+'\n');materialize()
        assert not next(c['ok'] for c in v.build_payload(date,p,html)['checks'] if c['name']=='required_first_version_states_present_or_supported')
        (source/'run_history.jsonl').write_text('');records=saved_records;payload=build();materialize()
        code,report=run(True);assert code==0 and report['full_map_verified'] is False and len(report['deferred_checks'])==4,(count,report)
        assert not final.exists(),'partial覆蓋final'
        code,report=run(False);assert code!=0 and report['full_map_verified'] is False,'缺rollup被錯當完整PASS'
        rollup=weekend_rollup(total);rollup['summary'].update(artifact_blocker_count=0,baseline_blocker_cleared=True);rollup['controlled_grid_drain']={'baseline_blocker_cleared':True,'target_production_path_created':False,'production_impact':'NO_PRODUCTION_CHANGE','status':'OK','controlled_grid_drain_ready':True}
        rp=case/'unit-rollup.json';rp.write_text(json.dumps(rollup));payload=build(rollup,str(rp));materialize();code,report=run(False)
        assert code==0 and report['full_map_verified'] is True,(count,[c for c in report['checks'] if not c['ok']])
        payload['full_universe_fog']['sample_count']=total+1;materialize();code,report=run(False);assert code!=0 and any(c['name']=='full_universe_not_dom_points' and c['ok'] is False for c in report['checks'])
        results.append({'topics':count,'universe':total,'partial_independent':True,'missing_rollup_full_rejected':True,'complete_fixture_full_pass':True,'producer_sample_bound':min(60000,total-1),'actual_sample_tamper_rejected':True})
    # 既有完整hostrunner流程：pre基本拒絕、post完整拒絕均須非零；不跑cleanup/replay。
    for failing in (None,'verify_fog_map_before_inventory','verify_fog_map_after_rollup'):
        calls=[];r.PROJECT_ROOT=root/('host-'+str(failing));r.cleanup_enabled=lambda:False
        def step(name,command):
            calls.append(name)
            if name=='verify_fog_map_before_inventory':assert '--source-only' in command and 'source_verification' in command[-1]
            if name=='verify_fog_map_after_rollup':assert calls.index('verify_rollup')<calls.index(name) and '--source-only' not in command
            return {'name':name,'command':command,'returncode':1 if name==failing else 0,'status':'FAILED' if name==failing else 'OK','stdout_tail':'','stderr_tail':''}
        r.run_step=step
        with contextlib.redirect_stdout(io.StringIO()):code=r.run_linkage(date,'/fixture-python')
        assert code==(1 if failing else 0),(failing,code,calls)
        if failing=='verify_fog_map_before_inventory':assert 'build_inventory_and_bounded_frontier_queue' not in calls
        results.append({'host_final_failure':failing,'code':code,'calls':calls})
    (e/'map-bootstrap-tests.json').write_text(json.dumps({'representative':False,'cases':results},indent=2));print(json.dumps({'cases':len(results),'status':'PASS','representative':False}))

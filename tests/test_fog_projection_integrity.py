"""原生serialized投影contract正負例；fixture不可算代表性cycle。"""
from pathlib import Path
import sys

def test_fog_projection_integrity(tmp_path, monkeypatch):
    import json,os,sys,hashlib,importlib.util,subprocess
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    monkeypatch.setattr(sys,'argv',list(sys.argv))
    root=tmp_path;e=root/'validation_evidence';e.mkdir()
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from tests.test_research_ledger import corpus_with_receipt
    from app.research.observation_ingest import ingest_corpus
    from app.research.contracts import content_hash
    base=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('projection_candidate',base/'app/research/history_compatibility_projection.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    corpus,_=corpus_with_receipt(root/'fixture');ledger=root/'ledger.duckdb';ingest_corpus(corpus_root=corpus,ledger_path=ledger)
    output=root/'history.jsonl';manifest=root/'manifest.json';m.build_projection(ledger_path=ledger,corpus_root=corpus,output=output,manifest_output=manifest)
    raw=output.read_bytes();meta=manifest.read_bytes();original_ledger=hashlib.sha256(ledger.read_bytes()).hexdigest();results=[]
    def verify(label,expected,ledger_path=ledger):
        result=m.verify_projection(ledger_path=ledger_path,corpus_root=corpus,output=output,manifest_output=manifest)
        results.append({'case':label,**result});assert result['status']==expected,(label,result)
        (e/'projection-tests.json').write_text(json.dumps(results,indent=2))
    def reset():output.write_bytes(raw);manifest.write_bytes(meta)
    def rehash_manifest():
        x=json.loads(manifest.read_text());x['output_hash']='sha256:'+hashlib.sha256(output.read_bytes()).hexdigest();identity={k:v for k,v in x.items() if k not in ('projection_id','generated_at')};x['projection_id']=content_hash(identity);manifest.write_text(json.dumps(x))
    verify('valid_native_serialized','PASS')
    for field in ('row_count','native_row_count'):
     for bad in (True,1.0):
        reset();x=json.loads(meta);x[field]=bad;manifest.write_text(json.dumps(x));verify('strict_type_'+field+'_'+type(bad).__name__,'FAIL')
    reset()
    report=root/'cli-verification.json'
    bootstrap="import sys,runpy;sys.path.insert(0,"+repr(str(base))+");runpy.run_path("+repr(str(base/'app/research/history_compatibility_projection.py'))+",run_name='__main__')"
    completed=subprocess.run([sys.executable,'-B','-c',bootstrap,'--verify','--ledger',str(ledger),'--corpus-root',str(corpus),'--output',str(output),'--manifest-output',str(manifest),'--verification-output',str(report)],capture_output=True,text=True)
    assert completed.returncode==0 and json.loads(report.read_text())['status']=='PASS',completed.stderr
    results.append({'case':'actual_cli_serialized_report','status':'PASS'})

    for field,value in [('combo_id','wrong'),('dimensions',{'horizon':'999','stop_loss':'none','take_profit':'none','group_exposure':'none'}),('canonical_observation_id','wrong-observation'),('source','research_map_legacy_strategy_matrix_backfill')]:
        reset();rows=[json.loads(x) for x in raw.decode().splitlines() if x];assert rows
        rows[0][field]=value;output.write_text('\n'.join(json.dumps(x,sort_keys=True) for x in rows)+'\n');rehash_manifest();assert all(isinstance(json.loads(line),dict) for line in output.read_text().splitlines() if line);verify('self_consistent_'+field,'FAIL')
    reset();output.write_bytes(raw+b' ');verify('row_bytes_tamper','FAIL')
    reset();x=json.loads(meta);x['projection_policy_version']='wrong-policy';manifest.write_text(json.dumps(x));rehash_manifest();verify('manifest_policy_tamper','FAIL')
    reset();x=json.loads(meta);x['row_count']+=1;manifest.write_text(json.dumps(x));rehash_manifest();verify('manifest_row_count_tamper','FAIL')
    reset();manifest.write_text('[]');verify('non_object_manifest','FAIL')
    reset();empty=root/'empty';empty.mkdir();wrong=root/'wrong.duckdb';ingest_corpus(corpus_root=empty,ledger_path=wrong);verify('wrong_ledger','FAIL',wrong)
    assert hashlib.sha256(ledger.read_bytes()).hexdigest()==original_ledger,'唯讀verifier改寫ledger'
    reset();m.build_projection(ledger_path=wrong,corpus_root=empty,output=output,manifest_output=manifest)
    zero=m.verify_projection(ledger_path=wrong,corpus_root=empty,output=output,manifest_output=manifest);assert zero['status']=='PASS' and zero['zero_rows'] and zero['row_count']==0
    results.append({'case':'zero_rows_fact_only_native_ledger',**zero})
    zero_raw=output.read_bytes();zero_meta=manifest.read_bytes()
    for field in ('row_count','native_row_count'):
     for bad in (False,0.0):
        output.write_bytes(zero_raw);x=json.loads(zero_meta);x[field]=bad;manifest.write_text(json.dumps(x));res=m.verify_projection(ledger_path=wrong,corpus_root=empty,output=output,manifest_output=manifest);results.append({'case':'zero_strict_'+field+'_'+type(bad).__name__,**res});assert res['status']=='FAIL',res
    (e/'projection-tests.json').write_text(json.dumps(results,indent=2));(e/'fixture-native-history.jsonl').write_bytes(raw);(e/'fixture-native-manifest.json').write_bytes(meta)
    print(json.dumps({'cases':len(results),'status':'PASS','representative':False}))

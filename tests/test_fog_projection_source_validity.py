"""已知source/CAS破壞與合法非comparison group分類；不是業務no-work證明。"""
from pathlib import Path
import sys

def test_fog_projection_source_validity(tmp_path, monkeypatch):
    import json,os,sys,importlib.util,hashlib
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    monkeypatch.setattr(sys,'argv',list(sys.argv))
    root=tmp_path;e=root/'validation_evidence';e.mkdir();base=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import duckdb
    from tests.test_research_ledger import corpus_with_receipt
    from tests.test_autonomous_research_receipts import begin,write_matrix,write_development_authority
    from app.research.run_receipts import finish_topic_attempt
    from app.research.observation_ingest import ingest_corpus
    from app.research.legacy_migration import build_migration
    spec=importlib.util.spec_from_file_location('candidate_projection',base/'app/research/history_compatibility_projection.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    results=[]
    def check(label,corpus,ledger,output,manifest,expected):
        result=m.verify_projection(ledger_path=ledger,corpus_root=corpus,output=output,manifest_output=manifest)
        row={'case':label,'expected':expected,**result};results.append(row);(e/'source-validity.json').write_text(json.dumps(results,indent=2));return result
    corpus,_=corpus_with_receipt(root/'valid');ledger=root/'valid.duckdb';ingest_corpus(corpus_root=corpus,ledger_path=ledger);output=root/'valid.jsonl';manifest=root/'valid-manifest.json';m.build_projection(ledger_path=ledger,corpus_root=corpus,output=output,manifest_output=manifest)
    with duckdb.connect(str(ledger),read_only=True) as c: artifact,path=c.execute('SELECT artifact_id,source_corpus_path FROM observation_provenance LIMIT 1').fetchone()
    cas=corpus/path;raw=cas.read_bytes();cas.unlink();check('missing_native_CAS',corpus,ledger,output,manifest,'FAIL');cas.write_bytes(b'corrupt');check('corrupt_native_CAS',corpus,ledger,output,manifest,'FAIL');cas.write_bytes(raw)
    legacy=root/'legacy';legacy.mkdir();(legacy/'run_history.jsonl').write_text('42\n');lc=root/'legacy-corpus';migration=build_migration(legacy_root=legacy,corpus_root=lc);ll=root/'legacy.duckdb';ingest_corpus(corpus_root=lc,ledger_path=ll);lo=root/'legacy.jsonl';lm=root/'legacy-manifest.json';m.build_projection(ledger_path=ll,corpus_root=lc,output=lo,manifest_output=lm);check('non_object_legacy_source',lc,ll,lo,lm,'FAIL')
    # 以既有receipt API產生真FAILED partial attempt；不靠刪DB row偽造partial來源。
    partial=root/'partial';partial.mkdir();context=begin(partial);matrix=partial/'baseline.json';authority=partial/'development.json';write_matrix(matrix,context,'baseline');x=json.loads(matrix.read_text());x['scenarios'][0].update(scenario_id='partial',total_return=0.01,max_drawdown=-0.02,score=0.1,trade_count=1);matrix.write_text(json.dumps(x));write_development_authority(authority,context);receipt=finish_topic_attempt(context,terminal_status='FAILED',matrix_paths=[matrix],lineage_authority_paths=[authority]);pl=root/'partial.duckdb';ingest_corpus(corpus_root=context.root,ledger_path=pl);po=root/'partial.jsonl';pm=root/'partial-manifest.json';m.build_projection(ledger_path=pl,corpus_root=context.root,output=po,manifest_output=pm);result=check('legal_failed_partial_noncomparison',context.root,pl,po,pm,'PASS');assert 'zero_row_no_work' not in result
    with duckdb.connect(str(pl),read_only=True) as c: result['observed_partial_observations']=c.execute('SELECT COUNT(*) FROM observations').fetchone()[0]
    (e/'source-validity.json').write_text(json.dumps(results,indent=2))
    (e/'partial-receipt.json').write_text(json.dumps(receipt,indent=2));(e/'legacy-admission-classification.json').write_text(json.dumps(json.loads(Path(migration['manifest_path']).read_text()),indent=2))
    fail=[r['case'] for r in results if r['status']!=r['expected']];print(json.dumps({'results':results,'unexpected':fail}));assert not fail,fail

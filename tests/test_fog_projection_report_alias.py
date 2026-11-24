"""實際CLI report別名拒寫契約；只在owned fixture建立hardlink/symlink。"""
from pathlib import Path
import sys

def test_fog_projection_report_alias(tmp_path, monkeypatch):
    import json,os,sys,hashlib,subprocess,importlib.util
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    monkeypatch.setattr(sys,'argv',list(sys.argv))
    root=tmp_path;e=root/'validation_evidence';e.mkdir()
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from tests.test_research_ledger import corpus_with_receipt
    from app.research.observation_ingest import ingest_corpus
    base=Path(__file__).resolve().parents[1];module=base/'app/research/history_compatibility_projection.py'
    spec=importlib.util.spec_from_file_location('projection',module);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    corpus,_=corpus_with_receipt(root/'fixture');ledger=root/'ledger.duckdb';ingest_corpus(corpus_root=corpus,ledger_path=ledger)
    output=root/'history.jsonl';manifest=root/'manifest.json';m.build_projection(ledger_path=ledger,corpus_root=corpus,output=output,manifest_output=manifest)
    aliases=root/'pytest/report-alias';aliases.mkdir(parents=True)
    protected=[ledger,output,manifest];original={p:p.read_bytes() for p in protected};results=[]
    bootstrap="import sys,runpy;sys.path.insert(0,"+repr(str(base))+");runpy.run_path("+repr(str(module))+",run_name='__main__')"
    for kind in ('samepath','symlink','hardlink'):
     for target in protected:
        for path,data in original.items():path.write_bytes(data)
        report=target if kind=='samepath' else aliases/(kind+'-'+target.name)
        if kind=='symlink':report.symlink_to(target)
        if kind=='hardlink':os.link(target,report)
        p=subprocess.run([sys.executable,'-B','-c',bootstrap,'--verify','--ledger',str(ledger),'--corpus-root',str(corpus),'--output',str(output),'--manifest-output',str(manifest),'--verification-output',str(report)],capture_output=True,text=True)
        unchanged=all(path.read_bytes()==data for path,data in original.items())
        row={'kind':kind,'target':target.name,'code':p.returncode,'original_inputs_unchanged':unchanged,'stdout':p.stdout,'stderr':p.stderr};results.append(row);(e/'report-alias.json').write_text(json.dumps(results,indent=2))
        assert p.returncode!=0 and unchanged,row
        if report!=target:report.unlink()
    other=aliases/'other.txt';other.write_bytes(b'original-other')
    report=aliases/'report-link.json';report.symlink_to(other)
    p=subprocess.run([sys.executable,'-B','-c',bootstrap,'--verify','--ledger',str(ledger),'--corpus-root',str(corpus),'--output',str(output),'--manifest-output',str(manifest),'--verification-output',str(report)],capture_output=True,text=True)
    assert p.returncode==0 and not report.is_symlink() and other.read_bytes()==b'original-other'
    assert all(path.read_bytes()==data for path,data in original.items())
    results.append({'kind':'non_input_symlink_atomic_replace','code':0,'original_inputs_unchanged':True,'unrelated_target_unchanged':True});(e/'report-alias.json').write_text(json.dumps(results,indent=2))
    print(json.dumps({'cases':len(results),'status':'PASS','representative':False}))

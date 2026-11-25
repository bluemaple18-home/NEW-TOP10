"""原 AppleScript CLI 的實際 guard 產物；錯誤身分或草稿不能觸及 payload。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import shlex
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = os.environ.get("NODE_BIN", "/Users/mattkuo/.nvm/versions/node/v24.12.0/bin/node")


@pytest.mark.parametrize("provider", ["chatgpt", "gemini"])
@pytest.mark.parametrize("case", ["ok", "wrong_account", "missing_account", "wrong_url", "wrong_title", "wrong_draft"])
def test_applescript_identity_blocks_before_payload(tmp_path, provider, case):
    source = (ROOT / "scripts" / f"review_{provider}_chrome.sh").read_text()
    section = source.split("wrap_identity_js() {", 1)[1].split("\nrun_chrome_js()", 1)[0]
    builder = shlex.split(section.split('"$(python_bin)" -c ', 1)[1])[0]
    path = tmp_path / "probe.js"
    path.write_text("(()=>{sendButton.click();return JSON.stringify({ok:true});})()")
    account = "Fixture User Plus" if provider == "chatgpt" else "fixture@example.invalid"
    with patch.object(sys, "argv", ["guard", str(path), provider, "https://example.invalid/dialog", account, "Fixture title", "whole draft"]):
        exec(compile(builder, "actual-cli-guard-builder", "exec"), {})
    fixture = {"provider": provider, "case": case, "account": account}
    driver = r'''
const vm=require('node:vm'),fs=require('node:fs');
const f=JSON.parse(process.argv[2]);let calls=0;
const node=(text,attrs={})=>({innerText:text,value:undefined,href:attrs.href,
 getAttribute:k=>attrs[k]??null,getBoundingClientRect:()=>({width:10,height:10}),
 dispatchEvent:()=>{},click:()=>{calls++;}});
const actual=f.case==='wrong_account'?'wrong@example.invalid':f.account;
const menu=node(actual);
const link=node('',{href:'https://accounts.google.com/SignOutOptions','aria-label':`Google 帳戶 (${actual})`});
const editor=node(f.case==='wrong_draft'?'truncated':'whole draft');
const document={title:f.case==='wrong_title'?'wrong':'Fixture title',body:{innerText:f.account},
 querySelectorAll:s=>{
  if(f.case==='missing_account'&&['[role=menuitem]','a[href]','button[aria-label]'].includes(s))return [];
  if(s==='[role=menuitem]')return [menu];
  if(s==='a[href]')return [link];
  if(s==='[contenteditable=true],textarea')return [editor];
  return [];
 }};
const sandbox={URL,document,location:{href:f.case==='wrong_url'?'https://wrong.invalid/':'https://example.invalid/dialog'},
 getComputedStyle:()=>({display:'block',visibility:'visible'}),sendButton:{click:()=>{calls++;}},
 KeyboardEvent:class{},PointerEvent:class{}};
const result=JSON.parse(vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),sandbox));
process.stdout.write(JSON.stringify({result,calls}));
'''
    result = subprocess.run([NODE, "-e", driver, str(path), json.dumps(fixture)], text=True, capture_output=True, check=True)
    data = json.loads(result.stdout)
    assert data["calls"] == (1 if case == "ok" else 0), data
    assert data["result"]["ok"] is (case == "ok"), data
    if case != "ok":
        assert data["result"]["guard_blocked"] is True, data


@pytest.mark.parametrize("user_date", ["2026-11-23", "2026-11-24"])
def test_current_speaker_headings_preserve_user_correlation(tmp_path, user_date):
    """新版說話者標題可回收；另一日的 user 不得借用看似正確的回答。"""
    source = (ROOT / "scripts/review_chatgpt_chrome.sh").read_text()
    body = source.split("write_collect_js() {", 1)[1].split("<<'JS'\n", 1)[1].split("\nJS\n", 1)[0]
    body = body.replace("__TOP10_REVIEW_DATE__", "2026-11-23").replace("__TOP10_MIN_CHARS__", "500")
    path = tmp_path / "collector.js"
    path.write_text(body)
    response = json.dumps({"review_date": "2026-11-23", "analysis": "x" * 650})
    fixture = {"user": f'review_date={user_date}, provider=chatgpt, market=TW\n{{"packet_date": "{user_date}"}}', "response": response + "ChatGPT 可能會出錯。請查證重要資訊。最新回覆即時\n"}
    driver = r'''
const fs=require('node:fs'),vm=require('node:vm');
const f=JSON.parse(process.argv[2]);
const headings=[{innerText:'你說：'},{innerText:'ChatGPT 說：'}];
const main={};
const document={title:'台股波段推薦分析',body:{innerText:f.user+f.response},
 querySelectorAll:s=>s==='h1,h2,h3,h4,h5,h6'?headings:[],querySelector:()=>main,
 createRange:()=>{let index;return {setStartAfter:h=>{index=headings.indexOf(h)},setEndBefore:()=>{},setEndAfter:()=>{},cloneContents:()=>({textContent:index===0?f.user:f.response})}}};
const data=JSON.parse(vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{document,location:{href:'https://chatgpt.com/dialog'},getComputedStyle:()=>({})}));
process.stdout.write(JSON.stringify(data));
'''
    result = subprocess.run([NODE, "-e", driver, str(path), json.dumps(fixture)], text=True, capture_output=True, check=True)
    data = json.loads(result.stdout)
    assert data["ok"] is (user_date == "2026-11-23"), data
    assert data["raw_response"] == (response if user_date == "2026-11-23" else ""), data

// 離線 fake 只檢查 transport/artifact 契約；不是 provider 或 grounding 驗收。
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, readFileSync, realpathSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {run, turns, READ_COLLECTION, READ_COMPOSER} from '../scripts/external_review_mcp_adapter.mjs';

const url = 'https://chatgpt.com/c/fake';
const sha = 'a'.repeat(64);
function fixture(provider = 'chatgpt') {
  const outputRoot = mkdtempSync(join(realpathSync(tmpdir()), 'top10-mcp-fake-'));
  const state = {prompt: '', clicked: false, calls: [], closes: 0, connects: 0, tamperReadback: false, failClick: false, busy: false, wrongMarker: false,
    menu: false, identityLabels: ['Fixture User Plus'], emails: ['fixture@example.invalid'], rootTitle: 'fake', body: '', nestedIdentity: false};
  const request = {provider, mode: 'send', outputRoot, review_date: '2026-11-23', packet_sha256: sha,
    promptTemplate: 'packet_sha256=' + sha + '\nrequest_marker=__REQUEST_MARKER__\nreview_date=2026-11-23, provider=' + provider + ', market=TW\n{"packet_date":"2026-11-23"}',
    url: provider === 'chatgpt' ? url : 'https://gemini.google.com/app/fake', minChars: 500,
    timeoutSeconds: 3, intervalSeconds: 1, waitSeconds: 0,
    guards: {account: provider === 'chatgpt' ? 'Fixture User Plus' : 'fixture@example.invalid'}};
  const raw = JSON.stringify({review_date: '2026-11-23', explanation: '完整離線內容。'.repeat(100)});
  const composer = provider === 'chatgpt' ? '問問 ChatGPT' : '請輸入 Gemini 提示詞';
  const user = provider === 'chatgpt' ? '你說：' : '你說了 提示詞';
  const assistant = provider === 'chatgpt' ? 'ChatGPT 說：' : 'Gemini 說了';
  const snapshot = () => `uid=1_0 RootWebArea "${state.rootTitle}" url="${state.currentURL ?? request.url}"
  uid=1_20 StaticText "${state.body}"
  ${provider === 'chatgpt' ? `uid=1_7 button "開啟個人檔案選單"
  ${state.menu ? `uid=1_8 menu "開啟個人檔案選單"
    uid=1_21 menuitem "設定"
    ${state.nestedIdentity ? 'uid=1_22 group "正文"\n      ' : ''}${state.identityLabels.map((label, i) => `uid=1_${10+i} menuitem "${label}"`).join('\n    ')}` : ''}`
    : state.emails.map((email, i) => `uid=1_${30+i} link "Google 帳戶：Fixture (${email})" url="${state.accountURL ?? 'https://accounts.google.com/SignOutOptions?continue=https://gemini.google.com'}"`).join('\n  ')}
  ${state.clicked ? `uid=1_1 heading "${user}" level="4"
  uid=1_2 "${state.prompt}"
  uid=1_3 heading "${assistant}" level="4"
  uid=1_4 "${raw}"` : ''}
  uid=1_5 textbox "${composer}" multiline value="${state.clicked ? '\n' : state.prompt || '\n'}"
  uid=1_6 button "${state.busy ? '停止' : '傳送'}"`;
  const content = value => ({content: [{type: 'text', text: value}]});
  const connect = async () => {
    state.connects++;
    return {
    call: async (name, args) => {
      state.calls.push(name === 'click' && args.uid === '1_7' ? 'profile-menu-click'
        : name === 'press_key' && args.key === 'Escape' ? 'profile-menu-escape' : name);
      if (name === 'list_pages') return content('4: fake (' + request.url + ')');
      assert.equal(args.pageId, 4);
      if (name === 'select_page') { assert.equal(args.bringToFront, true); return content('selected'); }
    if (name === 'take_snapshot') return content(state.recordedSnapshot ?? snapshot());
      if (name === 'fill') { state.prompt = args.value; return content('filled'); }
      if (name === 'press_key') {
        if (args.key === 'Escape') { state.menu = false; if (state.escapeURL) state.currentURL = state.escapeURL; return content('closed'); }
        assert.equal(args.key, 'Shift+Enter'); state.prompt += '\n'; return content('soft line break');
      }
      if (name === 'type_text') { assert([...args.text].length <= 128, 'single native typing call exceeds bounded chunk'); assert(!args.text.includes('\n')); assert(!args.text.includes('\r')); assert.equal(args.submitKey, undefined); state.prompt += args.text; return content('typed'); }
      if (name === 'click') {
        if (args.uid === '1_7') { state.menu = true; return content('profile opened'); }
        assert.equal(args.uid, '1_6'); state.clicked = true; if (state.failClick) throw Error('timeout_after_click'); return content('clicked');
      }
      if (name === 'evaluate_script') {
        if (args.function === READ_COMPOSER) {
          assert.deepEqual(args.args, ['1_5']);
          return content('```json\n' + JSON.stringify({value: state.tamperReadback ? 'corrupt:' + state.prompt : state.prompt}) + '\n```');
        }
        assert.equal(args.function, READ_COLLECTION);
        assert.deepEqual(args.args, ['1_1', '1_3', '1_4']);
        assert.equal(args.waitForStableDom, false);
        return content('```json\n' + JSON.stringify({url: request.url,
          user_text: state.wrongMarker ? 'stale' : state.prompt, raw_response: raw}) + '\n```');
      }
      assert.fail('unexpected mutation/tool: ' + name);
    }, close: async () => { state.closes++; },
    };
  };
  // 兩次 snapshot 仍走同一實作；sleep 以 fake 接點略過，不等待或連線。
  return {request, state, raw, connect, sleep: async () => {}};
}
for (const provider of ['chatgpt', 'gemini']) test(provider + ': send/collect artifacts and duplicate denial', async () => {
  const f = fixture(provider);
  assert.equal((await run(f.request, f.connect, f.sleep)).ok, true);
  const statusPath = join(f.request.outputRoot, '2026-11-23', provider + '_collect_status_2026-11-23.json');
  const status = JSON.parse(readFileSync(statusPath));
  assert.equal(status.ok, false); // 原 normalizer 尚未執行，不能假稱正式 PASS。
  assert.equal(status.reason, 'raw_saved_pending_normalize');
  assert.equal(status.packet_sha256, sha);
  assert.equal(status.correlation.correlated_user_count, 1);
  assert.equal(readFileSync(status.raw_path, 'utf8').trim(), f.raw);
  const count = f.state.calls.length;
  assert.equal((await run(f.request, f.connect, f.sleep)).reason, 'send_already_attempted_collect_only');
  assert.equal(f.state.calls.length, count);
  const before = f.state.calls.length;
  assert.equal((await run({...f.request, mode: 'collect'}, f.connect, f.sleep)).ok, true);
  assert(!f.state.calls.slice(before).some(x => ['fill', 'type_text', 'press_key', 'click'].includes(x)));
});
test('click unknown keeps evidence and only read-only collect reconciles', async () => {
  const f = fixture(); f.state.failClick = true;
  assert.equal((await run(f.request, f.connect, f.sleep)).ok, false);
  const submit = JSON.parse(readFileSync(join(f.request.outputRoot, 'chatgpt_submit_2026-11-23.json')));
  assert.equal(submit.outcome_unknown, true); assert.equal(submit.ok, false);
  f.state.failClick = false;
  const before = f.state.calls.length;
  assert.equal((await run({...f.request, mode: 'collect'}, f.connect, f.sleep)).ok, true);
  assert(!f.state.calls.slice(before).some(x => ['fill', 'type_text', 'press_key', 'click'].includes(x)));
  assert.equal(JSON.parse(readFileSync(join(f.request.outputRoot, 'chatgpt_submit_2026-11-23.json'))).ok, false);
});
test('wrong packet, missing binding and wrong user fail closed without mutation', async () => {
  const f = fixture();
  const absent = await run({...f.request, mode: 'collect'}, f.connect, f.sleep);
  assert.equal(absent.ok, false); assert.equal(f.state.calls.length, 0);
  assert.equal((await run(f.request, f.connect, f.sleep)).ok, true);
  const before = f.state.calls.length;
  assert.equal((await run({...f.request, mode: 'collect', packet_sha256: 'b'.repeat(64)}, f.connect, f.sleep)).reason, 'submitted_binding_mismatch');
  assert.equal(f.state.calls.length, before);
  f.state.wrongMarker = true;
  const reject = await run({...f.request, mode: 'collect', intervalSeconds: 4}, f.connect, f.sleep);
  assert.equal(reject.ok, false);
});
test('recorded new UI headings locate smoke text without legacy author-role', () => {
  for (const [provider, name, userUID, assistantUID, textUID] of [
    ['chatgpt', 'response-12.json', '3_2', '6_3', '6_4'], ['gemini', 'response-14.json', '8_0', '8_5', '8_7'],
  ]) {
    const record = JSON.parse(readFileSync(new URL('./fixtures/external_review_mcp/' + name, import.meta.url)));
    const snapshot = record.content.filter(x => x.type === 'text').map(x => x.text).join('\n');
    const messages = turns(snapshot, provider);
    const index = messages.findIndex(x => x.uid === userUID);
    assert(index >= 0); assert.equal(messages[index].role, 'user');
    assert.equal(messages[index + 1].uid, assistantUID);
    assert.equal(messages[index + 1].content[0].uid, textUID);
  }
});


test('Gemini uses one session and native soft line breaks without Enter submit', async () => {
  const f = fixture('gemini');
  f.request.promptTemplate += '\n\n保留空白行與繁體中文\n';
  assert.equal((await run(f.request, f.connect, f.sleep)).ok, true);
  const binding = JSON.parse(readFileSync(join(f.request.outputRoot, 'gemini_fill_2026-11-23.json')));
  assert.equal(f.state.prompt, f.request.promptTemplate.replace('request_marker=__REQUEST_MARKER__', 'request_marker=' + binding.request_marker));
  assert.equal(f.state.connects, 1);
  assert.equal(f.state.closes, 1);
  assert.equal(f.state.calls.filter(x => x === 'click').length, 1);
  assert(f.state.calls.indexOf('select_page') < f.state.calls.indexOf('fill'));
});

test('Gemini always reads actual composer and rejects extra text before submit', async () => {
  const f = fixture('gemini'); f.state.tamperReadback = true;
  const result = await run(f.request, f.connect, f.sleep);
  assert.equal(result.reason, 'complete_packet_prompt_not_visible_after_fill');
  assert.equal(f.state.clicked, false);
  assert.equal(f.state.calls.filter(x => x === 'click').length, 0);
  assert.equal(f.state.connects, 1);
  assert.equal(f.state.closes, 1);
});

test('Gemini long JSON line stays exact across bounded native typing calls', async () => {
  const f = fixture('gemini');
  f.request.promptTemplate += '\n' + JSON.stringify({內容: '原生輸入🧭'.repeat(1000)});
  assert.equal((await run(f.request, f.connect, f.sleep)).ok, true);
  const binding = JSON.parse(readFileSync(join(f.request.outputRoot, 'gemini_fill_2026-11-23.json')));
  assert.equal(f.state.prompt, f.request.promptTemplate.replace('request_marker=__REQUEST_MARKER__', 'request_marker=' + binding.request_marker));
  assert.equal(f.state.calls.filter(x => x === 'click').length, 1);
  assert.equal(f.state.connects, 1);
});

test('composer reads paragraph text exactly while preserving actual empty paragraphs', () => {
  // 現場 Gemini 將原生換行存成 p；innerText 在段落間插入額外視覺換行。
  const read = Function('return (' + READ_COMPOSER + ')')();
  const paragraph = text => ({nodeType: 1, tagName: 'P', textContent: text,
    childNodes: text ? [{nodeType: 3, textContent: text}] : [{nodeType: 1, nodeName: 'BR', tagName: 'BR'}]});
  const editor = {isContentEditable: true, childNodes: [paragraph('第一行  保留空格'), paragraph(''), paragraph('{"close":226.5}')],
    innerText: '第一行  保留空格\n\n\n\n{"close":226.5}', textContent: '第一行  保留空格{"close":226.5}'};
  assert.equal(read(editor).value, '第一行  保留空格\n\n{"close":226.5}');
  editor.childNodes[2] = paragraph('{"close":226.6}');
  assert.notEqual(read(editor).value, '第一行  保留空格\n\n{"close":226.5}');
  assert.equal(read({value: 'textarea\n\n原文'}).value, 'textarea\n\n原文');
});

test('Gemini collector reads the correlated message instead of its first token span', () => {
  const raw = JSON.stringify({schema_version: 'external-review.v1', explanation: '完整回答'.repeat(200)});
  const document = {createRange: () => ({setStartAfter() {}, setEndBefore() {},
    cloneContents: () => ({textContent: 'exact correlated user prompt'})})};
  const read = Function('document', 'location', 'return (' + READ_COLLECTION + ')')(document, {href: 'https://gemini.google.com/app/fake'});
  const message = {tagName: 'MESSAGE-CONTENT', textContent: raw, innerText: 'visual spacing is not JSON'};
  const token = {textContent: '{', innerText: '{', closest: selector => selector === 'message-content' ? message : null};
  assert.equal(read({}, {}, token).raw_response, raw);
});

test('Gemini long first line never uses the native long-fill caret path', async () => {
  const f = fixture('gemini');
  f.request.promptTemplate = '必須完整保留的長首行。'.repeat(30) + '\n' + f.request.promptTemplate;
  const originalConnect = f.connect;
  const connect = async request => {
    const session = await originalConnect(request);
    const call = session.call;
    session.call = async (name, args) => {
      if (name === 'fill') assert(args.value.length <= 100, 'native long fill leaves caret before inserted text');
      return call(name, args);
    };
    return session;
  };
  assert.equal((await run(f.request, connect, f.sleep)).ok, true);
  assert(f.state.prompt.startsWith('必須完整保留的長首行。'.repeat(30) + '\n'));
  assert.equal(f.state.calls.filter(x => x === 'click').length, 1);
});

for (const provider of ['chatgpt', 'gemini']) {
  for (const mode of ['send', 'probe']) {
    for (const scenario of ['wrong', 'missing', 'multiple', 'partial', 'missing_guard', 'body_title']) {
      test(`${provider}/${mode}: authenticated identity rejects ${scenario} before input`, async () => {
        const f = fixture(provider); f.request.mode = mode;
        f.state.body = f.request.guards.account + ' fake';
        const labels = provider === 'chatgpt' ? 'identityLabels' : 'emails';
        if (scenario === 'wrong') f.state[labels] = provider === 'chatgpt' ? ['Wrong User Plus'] : ['wrong@example.invalid'];
        if (scenario === 'missing') f.state[labels] = [];
        if (scenario === 'multiple') f.state[labels].push(provider === 'chatgpt' ? 'Other User Pro' : 'other@example.invalid');
        if (scenario === 'partial') f.state[labels][0] += provider === 'chatgpt' ? ' extra' : '.extra';
        if (scenario === 'missing_guard') delete f.request.guards.account;
        if (scenario === 'body_title') { f.request.guards.title = 'fake'; f.state.rootTitle = 'wrong'; }
        const result = await run(f.request, f.connect, f.sleep);
        assert.equal(result.ok, false, JSON.stringify(result));
        assert(!f.state.calls.some(x => ['fill', 'type_text', 'click'].includes(x)));
        assert.equal(f.state.clicked, false);
        assert.equal(f.state.menu, false);
      });
    }
    if (provider === 'chatgpt') test(`chatgpt/${mode}: nested identity text is not a direct account row`, async () => {
      const f = fixture(); f.request.mode = mode; f.state.nestedIdentity = true;
      assert.equal((await run(f.request, f.connect, f.sleep)).ok, false);
      assert(!f.state.calls.some(x => ['fill', 'type_text', 'click'].includes(x)));
      assert.equal(f.state.menu, false);
    });
    if (provider === 'chatgpt') test(`chatgpt/${mode}: Escape must retain canonical conversation`, async () => {
      const f = fixture(); f.request.mode = mode; f.state.escapeURL = 'https://chatgpt.com/c/other';
      assert.equal((await run(f.request, f.connect, f.sleep)).reason, 'conversation_url_changed');
      assert(!f.state.calls.some(x => ['fill', 'type_text', 'click'].includes(x)));
    });
  }
}

for (const accountURL of ['https://evil.invalid/SignOutOptions', 'https://accounts.google.com/Other']) {
  test('Gemini rejects an account label on an untrusted link: ' + accountURL, async () => {
    const f = fixture('gemini'); f.state.accountURL = accountURL;
    assert.equal((await run(f.request, f.connect, f.sleep)).ok, false);
    assert(!f.state.calls.some(x => ['fill', 'type_text', 'click'].includes(x)));
  });
}

for (const provider of ['chatgpt', 'gemini']) test(provider + ': probe verifies account on the original single connection', async () => {
  const f = fixture(provider); f.request.mode = 'probe';
  assert.equal((await run(f.request, f.connect, f.sleep)).ok, true);
  assert.equal(f.state.connects, 1); assert.equal(f.state.closes, 1);
  assert(!f.state.calls.some(x => ['fill', 'type_text', 'click'].includes(x)));
});

test('Gemini recorded RootWebArea and account link satisfy exact guards on one connection', async () => {
  const f = fixture('gemini'); f.request.mode = 'probe';
  f.request.url = 'https://gemini.google.com/app/ea58b54eef550ded';
  f.request.guards = {account: 'bluemaple17@gmail.com', title: 'TOP10 External Review - Gemini PROD - Google Gemini'};
  const record = JSON.parse(readFileSync(new URL('./fixtures/external_review_mcp/response-14.json', import.meta.url)));
  const snapshot = record.content.filter(x => x.type === 'text').map(x => x.text).join('\n')
    + '\n  uid=fixture_composer textbox "請輸入 Gemini 提示詞" multiline value="\\n"\n  uid=fixture_send button "傳送"';
  f.state.recordedSnapshot = snapshot;
  assert.equal((await run(f.request, f.connect, f.sleep)).ok, true);
  assert.equal(f.state.connects, 1); assert.equal(f.state.closes, 1);
  assert(!f.state.calls.some(x => ['fill', 'type_text', 'click'].includes(x)));
  f.state.recordedSnapshot = snapshot.replace('bluemaple17@gmail.com', 'wrong@example.invalid')
    + '\n  uid=fixture_spoof StaticText "bluemaple17@gmail.com"';
  assert.equal((await run(f.request, f.connect, f.sleep)).reason, 'expected_account_mismatch');
  assert(!f.state.calls.some(x => ['fill', 'type_text', 'click'].includes(x)));
});

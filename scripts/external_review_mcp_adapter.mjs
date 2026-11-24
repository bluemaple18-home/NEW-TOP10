// 原 CLI 的標準 MCP client；不提供通用 JS executor、server 或 fallback。
import {readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync, realpathSync, lstatSync, statSync} from 'node:fs';
import {createHash, randomUUID} from 'node:crypto';
import {join, resolve, isAbsolute} from 'node:path';
import {pathToFileURL} from 'node:url';

const sha = value => createHash('sha256').update(value).digest('hex');
const fail = reason => { throw Error(reason); };
const text = result => {
  if (result?.isError) fail('mcp_tool_error');
  return (result?.content ?? []).filter(x => x.type === 'text').map(x => x.text).join('\n');
};
const jsonResult = result => {
  const value = text(result).match(/```json\s*([\s\S]*?)\s*```/);
  if (!value) fail('collection_probe_not_json');
  return JSON.parse(value[1]);
};

// 只以新 UI 的 snapshot heading/UID 決定角色，不猜 DOM 的 author-role。
export function entries(snapshot) {
  const rows = [...snapshot.matchAll(/^([ \t]*)uid=([^\s]+) ([\s\S]*?)(?=^[ \t]*uid=|$(?![\s\S]))/gm)];
  return rows.map(([, indent, uid, body]) => ({indent: indent.length, uid, body: body.trimEnd()}));
}
export function turns(snapshot, provider) {
  const messages = [];
  for (const row of entries(snapshot)) {
    const heading = row.body.match(/^heading "([\s\S]*)" level="\d+"/)?.[1] ?? '';
    const user = /^(?:你說[：:]?$|你說了(?: |$)|You said[: ]?)/u.test(heading);
    const assistant = provider === 'chatgpt'
      ? /^heading "(?:ChatGPT 說[：:]?|ChatGPT said[: ]?)/u.test(row.body)
      : /^heading "(?:Gemini 說了|Gemini said)/u.test(row.body);
    if (user || assistant) messages.push({role: user ? 'user' : 'assistant', uid: row.uid, content: []});
    else if (messages.length && row.body.startsWith('"') && !/^"(?:JSON|json)"$/.test(row.body.trim())) {
      messages.at(-1).content.push(row);
    }
  }
  return messages;
}
function control(snapshot, role, name) {
  const found = entries(snapshot).filter(x => x.body.startsWith(role + ' "') && name.test(x.body)
    && !/\bdisabled\b/.test(x.body));
  if (found.length !== 1) fail(role + '_missing_or_ambiguous');
  return found[0];
}
const composerName = provider => provider === 'chatgpt'
  ? /^textbox "(?:問問 ChatGPT|Ask (?:anything|ChatGPT)|Message ChatGPT)"/
  : /^textbox "(?:請輸入 Gemini 提示詞|Enter a prompt (?:here|for Gemini))"/;
const sendName = /^button "(?:傳送|送出|傳送訊息|Send|Send message|Submit)"/;
const busy = snapshot => /button "(?:停止[^"\n]*|Stop[^"\n]*|取消回覆)"/.test(snapshot);
function checkUrl(snapshot, url) {
  const roots = entries(snapshot).filter(x => x.body.startsWith('RootWebArea '));
  if (roots.length !== 1 || roots[0].body.split('\n')[0].match(/\burl="([^"]*)"/)?.[1] !== url)
    fail('conversation_url_changed');
}

function named(row, role) {
  const match = row.body.match(/^(\w+) ("(?:\\.|[^"\\])*")/);
  return match?.[1] === role ? JSON.parse(match[2]) : null;
}
const profileNames = new Set(['開啟個人檔案選單', 'Open profile menu']);
const identityPlan = /\S.+\s(Free|Go|Plus|Pro|Business|Enterprise|Team)$/u;
function requiredAccount(request) {
  const value = request.guards?.account;
  if (typeof value !== 'string' || !value.trim()) fail('expected_account_required');
  if (request.provider === 'chatgpt' ? !identityPlan.test(value)
      : !/^[^\s@()]+@[^\s@()]+\.[^\s@()]+$/.test(value)) fail('expected_account_invalid');
  return value;
}
async function accountSnapshot(request, session, pageId, snapshot, initial) {
  const expected = requiredAccount(request);
  const checkTitle = snap => {
    const root = entries(snap).find(x => named(x, 'RootWebArea') !== null);
    if (request.guards.title && named(root, 'RootWebArea') !== request.guards.title)
      fail('expected_title_mismatch');
  };
  checkTitle(initial);
  let identity, snap = initial;
  if (request.provider === 'gemini') {
    const links = entries(snap).filter(row => {
      if (named(row, 'link') === null) return false;
      const raw = row.body.split('\n')[0].match(/\burl="([^"]*)"/)?.[1];
      try {
        const url = new URL(raw);
        return url.origin === 'https://accounts.google.com' && url.pathname === '/SignOutOptions'
          && !url.username && !url.password;
      } catch { return false; }
    });
    if (links.length !== 1) fail('account_identity_missing_or_ambiguous');
    identity = named(links[0], 'link');
    const emails = identity.match(/[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+/gi) ?? [];
    if (emails.length !== 1 || emails[0] !== expected) fail('expected_account_mismatch');
  } else {
    const rows = entries(snap);
    const controls = rows.filter(row => profileNames.has(named(row, 'button')) && !/\bdisabled\b/.test(row.body));
    if (controls.length !== 1) fail('profile_control_missing_or_ambiguous');
    if (rows.some(row => profileNames.has(named(row, 'menu')))) fail('profile_menu_already_open');
    let opened = false;
    try {
      opened = true;
      text(await session.call('click', {pageId, uid: controls[0].uid}));
      const menuRows = entries(await snapshot());
      const menus = menuRows.filter(row => profileNames.has(named(row, 'menu')));
      if (menus.length !== 1 || named(menus[0], 'menu') !== named(controls[0], 'button'))
        fail('profile_menu_missing_or_ambiguous');
      const menu = menus[0], start = menuRows.indexOf(menu) + 1;
      const children = [];
      for (let i = start; i < menuRows.length && menuRows[i].indent > menu.indent; i++) children.push(menuRows[i]);
      const directIndent = Math.min(...children.map(row => row.indent));
      // 只接受已觀測的 direct identity menuitem（顯示名＋plan），不採正文或第一列。
      const identities = children.filter(row => row.indent === directIndent && identityPlan.test(named(row, 'menuitem') ?? ''));
      if (identities.length !== 1) fail('account_identity_missing_or_ambiguous');
      identity = named(identities[0], 'menuitem');
      if (identity !== expected) fail('expected_account_mismatch');
    } finally {
      if (opened) {
        text(await session.call('press_key', {pageId, key: 'Escape'}));
        snap = await snapshot();
        if (entries(snap).some(row => profileNames.has(named(row, 'menu')))) fail('profile_menu_close_unconfirmed');
        checkTitle(snap);
      }
    }
  }
  if (request.guards.plan && !identity.endsWith(' ' + request.guards.plan)) fail('expected_plan_mismatch');
  return snap;
}
function checkedPath(root, path) {
  if (!(path === root || path.startsWith(root + '/'))) fail('output_escape');
  if (existsSync(path) && (lstatSync(path).isSymbolicLink() || realpathSync(path) !== path)) fail('output_symlink');
  if (realpathSync(resolve(path, '..')) !== resolve(path, '..')) fail('output_parent_symlink');
  return path;
}
function save(root, path, value, exclusive = false) {
  checkedPath(root, path);
  writeFileSync(path, JSON.stringify(value, null, 2) + '\n', {flag: exclusive ? 'wx' : 'w', mode: 0o600});
}

// evaluate_script 僅讀 snapshot 已定位的 composer、user 與 assistant UID。
// 原 smoke 的 innerText 讀法；多 token JSON 以既有 pre/code 祖先取完整文字。
export const READ_COMPOSER = String.raw`(el) => {
  if (el.value != null) return {value: el.value};
  const paragraphs = [...(el.childNodes ?? [])];
  // 只處理現場證實的純文字 p 編輯模型；保留每個真實空段落與所有字元。
  // innerText 的段落視覺間距不是輸入內容，不能拿來做逐字核對。
  const plain = p => p.nodeType === 1 && p.tagName === 'P'
    && ([...p.childNodes].every(n => n.nodeType === 3)
      || (p.childNodes.length === 1 && p.childNodes[0].nodeName === 'BR'));
  const value = el.isContentEditable && paragraphs.length && paragraphs.every(plain)
    ? paragraphs.map(p => p.textContent).join('\n')
    : el.innerText ?? el.textContent ?? '';
  return {value, html: el.innerHTML, tag: el.tagName};
}`;
export const READ_COLLECTION = `(userHeading, assistantHeading, answer) => {
  const range = document.createRange();
  range.setStartAfter(userHeading); range.setEndBefore(assistantHeading);
  const message = answer.closest?.('message-content');
  const source = answer.closest?.('pre') || answer.closest?.('code') || message || answer;
  // Gemini 將 JSON 拆為多個 span；讀同一 assistant 訊息的完整文字，避免只拿第一 token。
  const raw = source === message ? source.textContent : source.innerText ?? source.textContent;
  return {url:location.href,user_text:range.cloneContents().textContent ?? '',
    raw_response:(raw ?? '').trim()};
}`;
export function correlated(payload, request) {
  const markers = [
    'review_date=' + request.review_date, 'provider=' + request.provider, 'market=TW',
    '"packet_date":"' + request.review_date + '"',
    'packet_sha256=' + request.packet_sha256, 'request_marker=' + request.request_marker,
  ];
  return payload.url === request.url && markers.every(x => payload.user_text.includes(x));
}
function rawRejection(raw, minChars) {
  if ([...raw].length < minChars) return 'assistant_response_too_short';
  if (/top10-browser|top10-chatgpt-script-click|"marker"/.test(raw)) return 'smoke_marker_detected';
  if (/SPEC: Taiwan Stock Knowledge Graph|Taiwan Stock Knowledge Graph \(TSKG\)/.test(raw)) return 'stale_tskg_response';
  if (!raw.includes('{') || !raw.includes('}')) return 'assistant_response_not_complete_json_like';
  return null;
}

export async function nativeSession(request) {
  const runtime = request.runtime;
  if (!runtime || !isAbsolute(runtime.node) || !statSync(runtime.node).isFile()
      || !(statSync(runtime.node).mode & 0o111)) fail('existing_node_required');
  const registered = JSON.parse(readFileSync(runtime.configPath, 'utf8')).mcpServers?.['chrome-devtools'];
  if (registered?.command !== 'npx' || !Array.isArray(registered.args)) fail('original_registered_server_required');
  const packageIndex = registered.args.findIndex(x => /^chrome-devtools-mcp(?:@(?:latest|1\.13\.0))?$/.test(x));
  if (packageIndex < 0 || registered.args.slice(0, packageIndex).some(x => !['-y', '--yes'].includes(x)))
    fail('registered_package_mismatch');
  let flags = registered.args.slice(packageIndex + 1);
  const allowed = new Set(['--auto-connect', '--no-usage-statistics', '--no-performance-crux', '--redact-network-headers=true']);
  if (flags.some(x => !allowed.has(x))) fail('attach_only_registered_flags_required');
  if (request.wsEndpoint) {
    if (!/^ws:\/\/(?:127\.0\.0\.1|localhost):\d{1,5}\/devtools\/browser\/[a-f0-9-]{36}$/i.test(request.wsEndpoint))
      fail('explicit_loopback_browser_ws_endpoint_required');
    flags = [...flags.filter(x => x !== '--auto-connect'), '--ws-endpoint=' + request.wsEndpoint];
  } else if (!flags.includes('--auto-connect')) fail('endpoint_missing');
  const packageRoot = realpathSync(runtime.packageRoot);
  const installed = JSON.parse(readFileSync(join(packageRoot, 'package.json'), 'utf8'));
  if (installed.name !== 'chrome-devtools-mcp' || installed.version !== '1.13.0') fail('fixed_package_version_mismatch');
  const entry = realpathSync(join(packageRoot, installed.bin?.['chrome-devtools-mcp'] ?? 'missing-bin'));
  if (!entry.startsWith(packageRoot + '/') || !statSync(entry).isFile()) fail('fixed_package_entry_missing');
  const sdkRoot = realpathSync(runtime.sdkRoot);
  if (JSON.parse(readFileSync(join(sdkRoot, 'package.json'), 'utf8')).name !== '@modelcontextprotocol/sdk')
    fail('existing_standard_mcp_sdk_required');
  // shared config 只提供原工具 flags；絕不執行 npx/@latest 或重套 Core sandbox。
  // 既有父環境原樣繼承，無 guarded 旗標／FOG helper／parent admission 自判。
  const serverEnv = {...process.env};
  if (Object.entries(registered.env ?? {}).some(([key, value]) =>
      key !== 'CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS' || value !== '1')) fail('unexpected_registered_env');
  Object.assign(serverEnv, registered.env);
  const {Client} = await import(pathToFileURL(join(sdkRoot, 'dist/esm/client/index.js')));
  const {StdioClientTransport} = await import(pathToFileURL(join(sdkRoot, 'dist/esm/client/stdio.js')));
  const transport = new StdioClientTransport({command: runtime.node, args: [entry, ...flags], env: serverEnv, stderr: 'pipe'});
  transport.stderr?.on('data', () => {});
  const client = new Client({name: 'top10-external-review', version: '2026.11.24'}, {});
  const close = async () => { await client.close().catch(() => {}); await transport.close().catch(() => {}); };
  const onSignal = () => { void close().finally(() => process.exit(143)); };
  process.once('SIGTERM', onSignal); process.once('SIGINT', onSignal);
  try {
    try { await client.connect(transport, {timeout: 30000}); }
    catch (error) { error.message = 'connect: ' + error.message; throw error; }
    if (client.getServerVersion()?.version !== '1.13.0') fail('server_version_mismatch');
    let schemas;
    try { schemas = (await client.listTools()).tools; }
    catch (error) { error.message = 'listTools: ' + error.message; throw error; }
    for (const name of ['list_pages', 'select_page', 'take_snapshot', 'fill', 'type_text', 'press_key', 'click', 'evaluate_script']) {
      const tool = schemas.find(x => x.name === name);
      if (!tool || (name !== 'list_pages' && !tool.inputSchema?.properties?.pageId)) fail('native_tool_schema_mismatch');
    }
    return {
      call: async (name, args) => {
        try { return await client.callTool({name, arguments: args}, undefined, {timeout: 30000}); }
        catch (error) { error.message = name + ': ' + error.message; throw error; }
      },
      close: async () => { process.removeListener('SIGTERM', onSignal); process.removeListener('SIGINT', onSignal); await close(); },
    };
  } catch (error) {
    process.removeListener('SIGTERM', onSignal); process.removeListener('SIGINT', onSignal);
    await close(); throw error;
  }
}

export async function run(request, connect = nativeSession, sleep = ms => new Promise(resolve => setTimeout(resolve, ms))) {
  const root = request.outputRoot;
  if (realpathSync(root) !== root || root === '/') fail('canonical_output_root_required');
  const provider = request.provider;
  if (!['chatgpt', 'gemini'].includes(provider) || !['probe', 'send', 'collect'].includes(request.mode)) fail('invalid_cli_request');
  let session, binding, ownsAttempt = false;
  const base = {provider, review_date: request.review_date, packet_sha256: request.packet_sha256, url: request.url};
  const evidence = (kind, payload) => {
    const path = join(root, `${provider}_${kind}_${Date.now()}_${randomUUID()}.json`);
    save(root, path, {...base, at: new Date().toISOString(), ...payload}); return path;
  };
  const fillPath = join(root, `${provider}_fill_${request.review_date}.json`);
  const submitPath = join(root, `${provider}_submit_${request.review_date}.json`);
  let reviewDir;
  const status = payload => {
    if (!reviewDir) return;
    save(root, join(reviewDir, `${provider}_collect_status_${request.review_date}.json`),
      {...base, request_marker: binding?.request_marker, ok: false, ...payload});
  };
  try {
    requiredAccount(request);
    if (request.mode !== 'probe') {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(request.review_date) || !/^[a-f0-9]{64}$/.test(request.packet_sha256)) fail('invalid_packet_identity');
      if (request.minChars < 500 || request.timeoutSeconds < 1 || request.timeoutSeconds > 900
          || request.intervalSeconds < 1 || request.intervalSeconds > 30 || request.waitSeconds < 0 || request.waitSeconds > 300)
        fail('invalid_collection_bounds');
      if (request.mode === 'send') {
        for (const name of readdirSync(root).filter(x => x.startsWith(provider + '_fill_') && x.endsWith('.json'))) {
          const prior = JSON.parse(readFileSync(checkedPath(root, join(root, name)), 'utf8'));
          if (prior.review_date === request.review_date) fail('send_already_attempted_collect_only');
        }
        if (existsSync(submitPath)) fail('submit_already_exists_collect_only');
      } else {
        binding = JSON.parse(readFileSync(checkedPath(root, fillPath), 'utf8'));
        const submitted = JSON.parse(readFileSync(checkedPath(root, submitPath), 'utf8'));
        if (!binding.ok || !/^[a-f0-9-]{36}$/i.test(binding.request_marker)
            || ['provider', 'review_date', 'packet_sha256', 'url'].some(k => binding[k] !== base[k])
            || ['provider', 'review_date', 'packet_sha256', 'url', 'request_marker'].some(k => submitted[k] !== binding[k]))
          fail('submitted_binding_mismatch');
        // click 回覆未知仍可只讀對帳；成功條件在 DOM 中重新核對，不回填 submit。
      }
      reviewDir = checkedPath(root, join(root, request.review_date));
      mkdirSync(reviewDir, {recursive: true});
    }
    session = await connect(request);
    const pages = text(await session.call('list_pages', {}));
    const matches = [...pages.matchAll(/^(\d+): .*\((https:\/\/[^\s]+)\)(?: \[selected\])?$/gm)].filter(x => x[2] === request.url);
    if (matches.length !== 1) fail('canonical_conversation_missing_or_ambiguous');
    const pageId = Number(matches[0][1]);
    text(await session.call('select_page', {pageId, bringToFront: true}));
    const snapshot = async () => {
      const value = text(await session.call('take_snapshot', {pageId})); checkUrl(value, request.url); return value;
    };
    let snap = await accountSnapshot(request, session, pageId, snapshot, await snapshot());
    if (/工作階段已過期|請重新登入|session has expired/i.test(snap)) fail('session_expired');
    const composer = control(snap, 'textbox', composerName(provider));
    const probe = {ok: !busy(snap), mode: 'probe', readiness: busy(snap) ? 'generation_still_busy' : 'input_ready',
      hasComposer: true, hasSendButton: entries(snap).some(x => sendName.test(x.body)), url: request.url, page_id: pageId,
      title: entries(snap).find(x => x.body.startsWith('RootWebArea '))?.body.match(/^RootWebArea "(.*?)"/)?.[1],
      review_packet_sent: false};
    if (request.mode === 'probe') {
      if (request.promptTemplate && existsSync(fillPath)) {
        const prior = JSON.parse(readFileSync(checkedPath(root, fillPath), 'utf8'));
        if (['provider', 'review_date', 'packet_sha256', 'url'].some(k => prior[k] !== base[k])
            || !/^[a-f0-9-]{36}$/i.test(prior.request_marker)) fail('draft_binding_mismatch');
        const expected = request.promptTemplate.replace('request_marker=__REQUEST_MARKER__', 'request_marker=' + prior.request_marker);
        const actual = jsonResult(await session.call('evaluate_script', {pageId, function: READ_COMPOSER,
          args: [composer.uid], waitForStableDom: false}));
        let firstMismatch = 0;
        while (firstMismatch < Math.min(expected.length, actual.value.length)
               && expected[firstMismatch] === actual.value[firstMismatch]) firstMismatch++;
        probe.draft_match = actual.value.trim() === expected.trim();
        probe.draft_evidence = evidence('draft', {request_marker: prior.request_marker, expected,
          actual: actual.value, composer: actual, exact_after_trim: probe.draft_match, first_mismatch: firstMismatch});
      }
      evidence('probe', probe); return probe;
    }
    if (request.mode === 'send') {
      evidence('probe', probe);
      if (busy(snap)) fail('generation_still_busy');
      const draft = composer.body.match(/value="([\s\S]*)"\s*$/);
      if (!draft || draft[1].trim()) fail('composer_existing_draft_or_unknown');
      binding = {...base, request_marker: randomUUID(), ok: false, mode: 'fill', page_id: pageId};
      const prompt = request.promptTemplate.replace('request_marker=__REQUEST_MARKER__', 'request_marker=' + binding.request_marker);
      if (prompt === request.promptTemplate || !prompt.includes('packet_sha256=' + request.packet_sha256)) fail('prompt_identity_missing');
      // 先保留 fill artifact；即使程序中斷也不允許第二次 send。
      save(root, fillPath, binding, true); ownsAttempt = true;
      if (provider === 'gemini') {
        // Gemini 富文字輸入不可整段改 innerText；用原生軟換行保留完整 prompt。
        // 每行不含 LF，避免 type_text 把 Enter 當送出；唯一送出仍在下方 click。
        const lines = prompt.split('\n');
        // 長 fill 的直接設定不保證游標在末尾；先清空，再讓所有字元沿原生鍵盤輸入。
        text(await session.call('fill', {pageId, uid: composer.uid, value: ''}));
        for (const [index, line] of lines.entries()) {
          if (index) text(await session.call('press_key', {pageId, key: 'Shift+Enter'}));
          // 原生 keyboard.type 逐字送 CDP；長 JSON 行分段，保持每次呼叫在既有期限內。
          const characters = [...line];
          for (let start = 0; start < characters.length; start += 128)
            text(await session.call('type_text', {pageId, text: characters.slice(start, start + 128).join('')}));
        }
      } else {
        text(await session.call('fill', {pageId, uid: composer.uid, value: prompt}));
      }
      snap = await snapshot();
      const filled = control(snap, 'textbox', composerName(provider));
      if (provider === 'gemini' || !filled.body.includes(prompt.trim())) {
        const draft = jsonResult(await session.call('evaluate_script', {pageId,
          function: READ_COMPOSER,
          args: [filled.uid], waitForStableDom: false}));
        if (draft.value.trim() !== prompt.trim()) fail('complete_packet_prompt_not_visible_after_fill');
      }
      const submit = control(snap, 'button', sendName);
      binding.ok = true; save(root, fillPath, binding);
      const pending = {...binding, mode: 'submit', ok: false, submitted: false, outcome_unknown: true};
      save(root, submitPath, pending, true);
      // 不重試 click。timeout/crash 後由 collect 以 marker 對帳。
      text(await session.call('click', {pageId, uid: submit.uid}));
      save(root, submitPath, {...pending, ok: true, submitted: true, outcome_unknown: false});
      await sleep(request.waitSeconds * 1000);
    }
    const deadline = Date.now() + request.timeoutSeconds * 1000;
    let previous = '', attempts = 0, lastReason = 'assistant_after_correlated_user_missing';
    while (Date.now() <= deadline) {
      attempts += 1; snap = await snapshot();
      const messages = turns(snap, provider);
      const users = messages.map((m, index) => ({...m, index})).filter(m => m.role === 'user');
      const found = [];
      const marked = users.filter(m => m.content.some(x => x.body.includes(binding.request_marker)));
      // 長 prompt 可能被 UI 摺疊；只讀標題間 DOM range 核對全 markers，絕不以截斷 snapshot 推定成功。
      for (const user of marked.length ? marked : users.slice(-1)) {
        const assistant = messages[user.index + 1];
        if (!assistant || assistant.role !== 'assistant' || !assistant.content.length) continue;
        const data = jsonResult(await session.call('evaluate_script', {pageId, function: READ_COLLECTION,
          args: [user.uid, assistant.uid, assistant.content[0].uid], waitForStableDom: false}));
        if (correlated(data, {...request, request_marker: binding.request_marker}))
          found.push({data, user, assistant, assistantIndex: user.index + 1});
      }
      const selected = found.length === 1 ? found[0] : null;
      const raw = selected?.data.raw_response?.trim() ?? '';
      lastReason = busy(snap) ? 'generation_still_busy' : found.length > 1 ? 'correlated_user_ambiguous'
        : selected ? rawRejection(raw, request.minChars) : 'assistant_after_correlated_user_missing';
      const fingerprint = !lastReason ? sha(JSON.stringify([raw, selected.user.uid, selected.assistant.uid])) : '';
      if (fingerprint && fingerprint === previous) {
        const correlation = {marker: {reviewDate: 'review_date=' + request.review_date, provider: 'provider=' + provider,
          market: 'market=TW', packetDate: '"packet_date":"' + request.review_date + '"',
          packet: 'packet_sha256=' + request.packet_sha256, request: 'request_marker=' + binding.request_marker},
          correlated_user_count: 1, selected_user_index: selected.user.index,
          selected_assistant_index: selected.assistantIndex, assistants_after_selected_user: 1,
          selected_user_uid: selected.user.uid, selected_assistant_uid: selected.assistant.uid,
          generation_busy: false, rejection_reason: null};
        const payload = {...base, ok: true, mode: 'collect', raw_response: raw, correlation,
          request_marker: binding.request_marker, raw_chars: [...raw].length,
          stability: {stable: true, required_stable_snapshots: 2, attempts}};
        const rawPath = checkedPath(root, join(reviewDir, `${provider}_raw_${request.review_date}.txt`));
        writeFileSync(rawPath, raw + '\n', {mode: 0o600});
        evidence('collect', payload);
        status({...payload, ok: false, raw_response: undefined, raw_path: rawPath,
          response_path: join(reviewDir, `${provider}_response_${request.review_date}.json`), reason: 'raw_saved_pending_normalize'});
        return {ok: true, mode: 'collect', reason: 'raw_saved_pending_normalize', raw_path: rawPath, correlation};
      }
      previous = fingerprint;
      if (Date.now() + request.intervalSeconds * 1000 > deadline) break;
      await sleep(request.intervalSeconds * 1000);
    }
    fail('response_not_stable_before_deadline:' + lastReason);
  } catch (error) {
    const payload = {ok: false, mode: request.mode, reason: String(error.message).slice(0, 300),
      request_marker: binding?.request_marker, submit_outcome: existsSync(submitPath) ? 'inspect_submit_and_collect_only' : 'not_confirmed'};
    evidence('failure', payload);
    if (ownsAttempt || (request.mode === 'collect' && binding)) status(payload);
    return payload;
  } finally { await session?.close(); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    let input = ''; for await (const chunk of process.stdin) input += chunk;
    const result = await run(JSON.parse(input));
    process.stdout.write(JSON.stringify(result) + '\n'); process.exitCode = result.ok ? 0 : 1;
  } catch (error) {
    process.stdout.write(JSON.stringify({ok: false, reason: String(error.message).slice(0, 300)}) + '\n'); process.exitCode = 1;
  }
}

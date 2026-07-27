# Fog Runtime Time Authority v1

## 1. 決策摘要

Fog runtime 的日期與 freshness 必須由同一份 versioned contract 重算，但日期
identity、資料來源與 freshness 是獨立 gate：

1. `market_run_date`：把具 timezone 的 UTC instant 透過 IANA
   `Asia/Taipei` 投影後取得市場 civil date。
2. `artifact_run_date`：daily artifact 本次 run 的 identity／path binding。
3. `daily_source_date` 與 `source_trade_date`：canonical artifacts 內最近適用的
   資料來源日期，均可早於 civil run date。
4. `receipt_age_seconds`：以兩個 UTC instant 相減取得 absolute age。

不得再把 `generated_at_utc` 的 UTC date 直接與 `market_run_date` 比較，也不得由
shell 的未綁時區 `date +%F`、LaunchAgent host timezone、locale 或 receipt
自報 policy 產生 contract identity。

本文件是 architecture candidate，不修改或授權現有 runtime。後續 implementation
必須建立獨立 candidate、Review 與 live acceptance。

## 2. 規範語彙與範圍

- **MUST／必須**：不符合即 fail closed。
- **MUST NOT／不得**：禁止的隱式 authority 或 trust path。
- **SHOULD／應**：除非有新的 architecture decision，否則遵守。

本 contract 處理：

- 市場時區下的 daily identity；
- UTC receipt timestamp；
- freshness 與 clock-skew window；
- LaunchAgent → worker → daily quota → receipt → verifier wiring；
- regime-history 與 daily artifact 的日期 lineage。

本 contract 不宣稱單憑 timezone 即可判斷 TWSE 假日或開市狀態。
`market_run_date` 是市場時區的 civil-day identity；若流程需要
`is_market_session_day`，必須另讀 versioned TWSE session calendar。週末或休市日
不得把 `market_run_date` 靜默回捲成前一交易日。

## 3. Versioned authority

### 3.1 Canonical policy

v1 的 semantic policy 固定如下；implementation 必須將相同資料放進 repo 內的
versioned authority，不得由 receipt 或任意 env 覆寫：

```json
{
  "schema_version": "fog-runtime-time-authority.v1",
  "market_id": "TWSE",
  "market_timezone": "Asia/Taipei",
  "market_day_semantics": "local-civil-date",
  "timestamp_format": "rfc3339-utc-z",
  "receipt_schema_version": "closed-regime-runtime-receipt.v3",
  "freshness": {
    "max_age_seconds": 900,
    "future_tolerance_seconds": 5
  },
  "lifecycle": {
    "market_midnight_boundary": "hard"
  }
}
```

選擇 900 秒是因 Fog LaunchAgent 的既有觸發間隔為 900 秒，且 receipt 在 daily
quota 完成後立即被 verifier 使用。這個 window 不是 batch 最大執行時間；receipt
只能證明最近一次完成結果，不能讓舊 receipt 跨過下一個 scheduler interval
持續授權。

`time_contract_hash` 是上述 semantic object 經 UTF-8、key sort、compact
separators、禁止 NaN 的 canonical JSON 所得 SHA-256。檔案路徑、空白、註解與
receipt 值不進 hash；任何 semantic 欄位、timezone、window 或 schema 變更都必須
改變 hash 與 contract version。

### 3.2 IANA timezone boundary

- v1 的 production `market_timezone` 必須恰為 `Asia/Taipei`。
- 不接受 `UTC+8`、`CST`、numeric offset、host locale 或 IANA alias 作為等價
  identity。
- Python 必須使用 `zoneinfo.ZoneInfo(market_timezone)`；shell 不實作 timezone
  arithmetic。
- 未來支援其他市場時，`market_id`、canonical IANA timezone 與適用的 tzdb
  policy 必須進 schema/hash；不得依 host locale。
- DST-capable market 上線前，必須在新的 contract version 鎖定 tzdb provider／
  release。v1 只有 `Asia/Taipei` production authority；DST zone 僅作 conversion
  invariant fixture，不是可由 runtime 選擇的市場。

## 4. Canonical time concepts

| Concept | Authority | Canonical format | 轉換／驗證順序 | 禁止的隱式假設 |
|---|---|---|---|---|
| `market_timezone` | versioned time authority | canonical IANA string；v1=`Asia/Taipei` | 先驗 schema/hash，再建立 `ZoneInfo` | host timezone、`TZ` env、locale、offset 字串皆不是 authority |
| `market_run_date` | time-authority pure function | `YYYY-MM-DD` | trusted UTC instant → UTC aware datetime → IANA projection → `.date()` | 不得用 `date +%F`、UTC `.date()`、檔名、mtime 或 receipt claim |
| `generated_at_utc` | receipt producer 的 UTC clock | `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` | 先取得 aware UTC instant，再 canonicalize 成 `Z` | naive timestamp、local timestamp、`+08:00` 冒充 UTC 欄位 |
| `verification_time_utc` | verifier 自己的 UTC clock | 同上 | verifier 啟動時取得；production 不接受 receipt／env／CLI 指定 | receipt 的 `verification_time`、檔案 mtime 不是現在時間 |
| `receipt_age_seconds` | verifier 重算 | signed decimal seconds | `verification_time_utc - generated_at_utc` | 不得以 calendar date、host clock 字串或整日差近似 |
| scheduler host timezone | OS diagnostic only | IANA name或 `UNKNOWN` | 可記錄於 verifier evidence，但不參與 identity 或 gate | host timezone 等於市場 timezone |
| regime-history source date | canonical regime history + `current_regime_context` 重算 | `YYYY-MM-DD` | 驗 history schema/hash，再依 `market_run_date` 選出 `source_trade_date` | 不要求假日 source date 等於 run date；不得信 receipt 自報 |
| `artifact_run_date` | immutable run context + canonical artifact path／payload identity | `YYYY-MM-DD` | 先重算 `market_run_date`，再驗 artifact path與 payload 的 run binding | 不得把 data source date、檔案 mtime或 receipt claim當 artifact identity |
| `daily_source_date` | canonical daily artifact payload + source lineage | `YYYY-MM-DD` | 驗 artifact schema/hash與 source lineage，再讀最近適用 data source date | 不得只從檔名或 receipt copy取得；不得要求休市日等於 civil run date |

補充規則：

- `generated_at_utc` 與 `verification_time_utc` 必須是 RFC 3339 UTC `Z` 形式；
  timezone-naive、leap-second 或無法 round-trip 的值 fail closed。
- `market_run_date` 必須通過 `date.fromisoformat` 的 exact parse，不接受 datetime
  字串或寬鬆 parser。
- regime-history `source_trade_date` 必須小於等於 `market_run_date`，且必須等於
  verifier 從 canonical history 對該 run date 重算的結果；休市日可以早於
  `market_run_date`。
- `artifact_run_date` 必須等於 immutable run context 的 `market_run_date`，且
  必須同時符合 canonical artifact path與 payload identity；這只綁定本次 run，
  不表示資料來源當日開市。
- `daily_source_date` 必須小於等於 `market_run_date`，且必須等於 verifier
  從 canonical daily artifact及其 source lineage 重算的結果。休市日可早於
  `artifact_run_date`，不得再要求
  `daily_source_date == market_run_date`。
- `daily_source_date > market_run_date` 一律
  `FUTURE_DAILY_SOURCE_DATE` fail closed；canonical lineage與 receipt claim不符
  一律 `DAILY_SOURCE_DATE_MISMATCH`；artifact path／payload identity與 run
  context不符一律 `ARTIFACT_IDENTITY_DRIFT`。

## 5. 唯一日期推導與 lifecycle

唯一合法的日期推導函式概念如下：

```text
derive_market_run_date(instant_utc, contract):
  require instant_utc is timezone-aware
  require contract schema/hash is canonical and market_timezone is allowed
  normalized_utc = instant_utc.astimezone(UTC)
  market_datetime = normalized_utc.astimezone(ZoneInfo(market_timezone))
  return market_datetime.date().isoformat()
```

所有 producer／consumer 都必須呼叫同一個 pure function；不得各自複製日期邏輯。
Fog worker 在取得 lock 後、開始第一批前只 sample 一次
`run_context_created_at_utc`，並以該 instant 建立 immutable run context。

market midnight 是 hard lifecycle boundary：

- `run_context_created_at_utc` 投影出的 date 必須等於 `market_run_date`。
- receipt 的 `generated_at_utc` 投影出的 date 也必須等於同一
  `market_run_date`。
- 若 batch 跨過市場午夜，producer 必須以 `MARKET_DATE_ROLLOVER` fail closed，
  不得把 receipt 寫入舊日期檔；下一次 LaunchAgent invocation 重新取得 context。
- 不允許以 freshness 尚未過期為由跨越日期 identity。

因此 freshness 與 lifecycle 的判定次序為：

1. parse／normalize timestamps；
2. 驗 contract schema/hash；
3. 由 UTC instant 重算 market dates；
4. 驗 lifecycle date identity；
5. 才計算並驗 freshness。

## 6. Freshness policy

```text
receipt_age_seconds =
  verification_time_utc - generated_at_utc

accept freshness iff:
  -future_tolerance_seconds
    <= receipt_age_seconds
    <= max_age_seconds
```

v1 boundaries：

- `max_age_seconds = 900`；
- `future_tolerance_seconds = 5`；
- `age = -5` 與 `age = 900` 可接受；
- `age < -5` 是 future receipt，拒絕；
- `age > 900` 是 stale receipt，拒絕。

5 秒只吸收小幅 host clock skew，不把 future timestamp 改寫成現在，也不修改
`generated_at_utc`。verifier output 必須保留 signed `receipt_age_seconds`、
兩個 UTC timestamps、policy bounds 與個別 check result。

policy 只能從已驗 hash 的 versioned authority 取得。下列來源不得改變 window：

- receipt 內的 `max_age_seconds` 或 `future_tolerance_seconds`；
- `TOP10_*` environment variables；
- LaunchAgent EnvironmentVariables；
- command-line freshness override；
- scheduler interval 的動態推測。

測試可直接向 pure function 注入 aware `verification_time_utc`；production CLI
不得提供任意 `--now`。

## 7. Runtime wiring contract

```text
LaunchAgent
  └─ run_fog_research_worker.sh
       ├─ Python time authority：建立 immutable run context
       └─ run_daily_research_quota.sh：只傳遞 context，不重算
            ├─ daily artifact：以相同 artifact_run_date綁 run；另存 daily_source_date
            ├─ runtime receipt producer：綁定來源並寫 v3 receipt
            └─ daily verifier：獨立載入 authority、重算 identity/freshness
```

### 7.1 LaunchAgent

- 只負責 executable path、900 秒 schedule 與既有非時間 runtime flags。
- 不設定 `TZ`、`TOP10_RUN_DATE`、`TOP10_RESEARCH_DATE`、freshness window 或
  `market_timezone`。
- host timezone 可為任意值；結果必須相同。

### 7.2 Fog worker

- 以 repo 固定路徑載入 versioned authority，先驗 schema/hash。
- 取得 `run_context_created_at_utc`，呼叫唯一日期推導函式。
- 將 `artifact_run_date` 固定為 immutable context 的
  `market_run_date`，並作為 artifact path／payload run identity；不得由 artifact
  data source date反推。
- 將 immutable context 以明確 arguments 或一次性 context JSON 傳給 daily
  quota；不得讓 child shell 自行 fallback 到 `date`.
- run id、log／retry state 檔名與 artifact identity 都使用 context 的
  `artifact_run_date`；時分秒 suffix 使用 UTC 或已明確標記的 market datetime。
- production path 若仍收到 legacy `TOP10_RUN_DATE`／`TOP10_RESEARCH_DATE`，只能
  比對是否相同；不相同 fail closed，不能成為 override。

### 7.3 Daily quota與receipt producer

- daily quota 必須驗證傳入 context 的 schema/hash，再把
  `market_run_date` 明確傳給 Python workload。
- receipt producer 必須自己重新載入 versioned authority，驗 context 與來源
  artifact，而不是把 shell 值原樣簽回。
- producer 必須分別保存 `artifact_run_date` 與 `daily_source_date`；前者來自
  immutable run identity，後者來自已驗 hash 的 canonical artifact source
  lineage，不得互相補值。
- receipt 只在 daily artifact 完整寫入並完成 hash 後產生；先前 READY receipt
  不得作為 COMPLETED freshness proof。

### 7.4 Receipt v3 single exact-schema authority

唯一 machine-readable normative contract 是：

`docs/architecture/fog_runtime_receipt_v3.schema.json`

producer 與 verifier 必須從相同 repo-relative path載入同一份 schema，不得各自
硬編另一份 key set、以 receipt 自報 schema取代 repo authority，或建立 permissive
fallback。schema 使用 JSON Schema 2020-12 closed object：

- top-level與每個 nested object均 `additionalProperties: false`；
- 所有列出欄位皆 required，沒有 optional top-level／object key；
- 唯一 nullable value 是 `topic_run_lineage[].decision`，型別為
  `string | null`；其餘欄位不可為 null；
- missing、unknown、type mismatch、format mismatch均 deterministic
  `RECEIPT_SCHEMA_REJECT`，而且必須在任何 receipt claim被信任前拒絕；
- schema完整綁定 time authority與 contract hash、run／artifact／source dates、
  queue owner、runner identity、research contract、exact regime、state
  transition、topic-run lineage及 production impact；
- UTC instant只接受 canonical RFC3339 `Z`，market projection只接受明確
  `+08:00`，timezone只接受 canonical IANA `Asia/Taipei`，date只接受
  `YYYY-MM-DD`，digest只接受 lowercase 64-hex SHA-256；
- path只能 repo-relative，不得包含 absolute path或 `..` traversal。

schema 的 `examples[0]` 是 canonical complete v3 fixture，也是唯一欄位 manifest
範例；`x-v2-to-v3-mapping` 是 normative migration ledger。fixture
`market_run_date=artifact_run_date=2026-08-08` 且
`daily_source_date=source_trade_date=2026-08-07`，明確證明合法休市日 lineage。

原始與正規化資料的保存規則：

- 原始 authoritative instants：
  `run_context_created_at_utc`、`generated_at_utc`。
- 正規化／投影結果：
  `run_context_market_datetime`、`generated_market_datetime`、
  `market_run_date`。
- source 原始 authority：
  被 hash 綁定的 regime-history 與 daily artifact。
- source 正規化結果：
  `source_trade_date` 與 `daily_source_date`。
- artifact identity正規化結果：
  `artifact_run_date`；它不等於 data source authority。
- scheduler host timezone 不放進 signed identity；可放 verifier diagnostics。

所有 path 必須 repo-relative，receipt 不保存本機絕對路徑。

#### v2 → v3 migration rule

schema 內的 `x-v2-to-v3-mapping` 逐欄分成三類：

1. **可直接比較**：`queue_owner`、`runner_identity`、
   `closed_regime_research`與固定 policy value仍須對 repo authority比對，不能
   因 v2 自報而直接信任。
2. **必須重新查 authority／重算**：time projections／contract hash、
   regime-history、daily artifact、research contract、exact regime、
   state transition與 topic-run lineage。
3. **無法補造**：缺 authoritative run-context instant、source lineage、contract、
   artifact或 hash時直接 fail closed；v2只可 archive，不得 relabel、補值或升級
   為 v3。

因此 migration沒有 dual trust，也沒有「以 status=OK 推論缺失 authority」的路徑。

### 7.5 Verifier

verifier 不信任 receipt 自報結果，必須獨立：

1. 以 repo 固定 authority 重算 expected contract hash；
2. 從固定 repo-relative path載入
   `fog_runtime_receipt_v3.schema.json`，以同一 exact schema驗 v3，拒絕
   unknown／missing／type mismatch／nullability／format mismatch；
3. strict parse UTC timestamps 與 IANA timezone；
4. 從 `run_context_created_at_utc`、`generated_at_utc` 各自重算
   `market_run_date`；
5. 比對 receipt market projection 與 claimed `market_run_date`；
6. 以自己的 `verification_time_utc` 重算 signed
   `receipt_age_seconds`；
7. 直接讀 canonical regime-history／daily artifact，重算 schema、hash、
   `source_trade_date`、`artifact_run_date`、`daily_source_date`與 exact regime；
8. 驗 `artifact_run_date == market_run_date`，並分別驗兩個 source date不在
   future且等於各自 canonical lineage；不得要求 source date等於 run date；
9. 聚合 checks；任何一項失敗即非零退出。

verifier output 必須使用以下 canonical 名稱：

- `verification_time_utc`
- `receipt_age_seconds`
- `computed_market_run_date`
- `contract_hash_expected`
- `contract_hash_observed`
- `scheduler_host_timezone_diagnostic`

## 8. Deterministic time與source-date matrix

| Case | Market time | UTC time | Verification／claim | Expected |
|---|---|---|---|---|
| 台北跨 UTC 日界 | `2026-07-28 00:30:00 +08` | `2026-07-27T16:30:00Z` | verify `16:31:00Z`；run date `2026-07-28`；age `60` | `ACCEPT`：fresh 且 market projection 相同 |
| 台北正常日間 | `2026-07-28 09:00:00 +08` | `2026-07-28T01:00:00Z` | verify `01:01:00Z`；run date `2026-07-28`；age `60` | `ACCEPT` |
| stale receipt | `2026-07-28 09:00:00 +08` | generated `01:00:00Z` | verify `01:15:01Z`；age `901` | `REJECT / STALE_RECEIPT` |
| future receipt | `2026-07-28 09:00:06 +08` | generated `01:00:06Z` | verify `01:00:00Z`；age `-6` | `REJECT / FUTURE_RECEIPT` |
| naive timestamp | n/a | `2026-07-28T01:00:00` | 無 `Z`／offset | `REJECT / NAIVE_TIMESTAMP` |
| wrong market date | computed `2026-07-28` | generated `2026-07-28T01:00:00Z` | receipt claims `2026-07-27`；age `60` | `REJECT / MARKET_DATE_MISMATCH` |
| host timezone drift | host=`America/Los_Angeles`；market=`2026-07-28 00:30 +08` | `2026-07-27T16:30:00Z` | 與 case 1 相同 authority／verify | `ACCEPT`；host zone 不影響任何 signed value |
| DST-capable fixture | `America/New_York` 的兩個 `2026-11-01 01:30` folds | `05:30:00Z`（`-04`）與 `06:30:00Z`（`-05`） | 各自 UTC→zone→UTC round-trip | `DETERMINISTIC`；保留原 UTC instant，不解析 ambiguous naive local time |
| 合法休市日 source lineage | `market_run_date=2026-08-08` | context／generated均投影 `2026-08-08` | `artifact_run_date=2026-08-08`；`daily_source_date=2026-08-07`；`source_trade_date=2026-08-07`；其他 lineage/hash/freshness gates通過 | `ACCEPT`；civil/artifact/source identity彼此獨立 |
| 錯誤 daily source date | `market_run_date=2026-08-08` | 同合法休市日 case | receipt `daily_source_date=2026-08-06`，canonical artifact lineage重算為 `2026-08-07` | `REJECT / DAILY_SOURCE_DATE_MISMATCH` |
| future daily source date | `market_run_date=2026-08-08` | 同合法休市日 case | `daily_source_date=2026-08-09` | `REJECT / FUTURE_DAILY_SOURCE_DATE` |
| artifact identity drift | `market_run_date=2026-08-08` | 同合法休市日 case | artifact path／payload claims `artifact_run_date=2026-08-07` | `REJECT / ARTIFACT_IDENTITY_DRIFT` |

Boundary subcases 必須另外固定：

- age `-5`：accept；
- age `-5.001`：reject；
- age `900`：accept；
- age `900.001`：reject；
- 台北 `23:59:59.999999 +08` 與下一 instant `00:00:00 +08` 產生不同
  `market_run_date`。

## 9. Properties與invariants

1. **UTC round-trip**：對任意 aware UTC instant `t` 與允許 zone `z`，
   `t → z → UTC` 必須等於 `t`。
2. **Projection identity**：`market_run_date` 只等於
   `generated_at_utc.astimezone(ZoneInfo(market_timezone)).date()`，不等於
   `generated_at_utc.date()`，除非兩者偶然相同。
3. **Freshness separation**：改變 market timezone 可能改變 date identity，但
   不得改變 `receipt_age_seconds`。
4. **Host invariance**：相同 contract、UTC instants 與 artifacts，在不同 host
   `TZ`／locale 下得到 byte-equivalent semantic result。
5. **Naive rejection**：任何 timezone-naive input 都不能被 host zone 補值。
6. **Midnight lifecycle**：context instant 與 generated instant 投影到不同
   market dates 時必須 fail closed。
7. **Boundary monotonicity**：verification time 前進且 generated time不變時，age
   不得減少；超過 900 秒後不能重新變 fresh。
8. **Future skew**：只有 `[-5, 0)` 的負 age 可接受；不能 clamp 成 0。
9. **Hash determinism**：semantic object key order／空白不影響 hash；任一 semantic
   value 改變必須改變 hash。
10. **Receipt non-authority**：修改 receipt 的 timezone、policy、projection 或
    source date，不修改 canonical inputs，必須被 verifier 拒絕。
11. **Identity與source lineage分離**：
    `artifact_run_date == market_run_date` 且等於 canonical artifact
    path／payload identity；`daily_source_date <= market_run_date` 且等於
    canonical artifact source lineage重算值；regime
    `source_trade_date <= market_run_date` 且等於 canonical history重算值。
    兩個 source dates均不得由 artifact identity或 receipt claim補造。
12. **DST fold safety**：只由 UTC instant 投影到 local；不得從 ambiguous naive
    local time反推 UTC。

Property tests 必須使用 fixed clock／seed，禁止讀取 real current time 或 host
timezone。

## 10. Successor lineage與clean-room safety rebuild

本 architecture Repair仍不是 implementation授權。只有本 Repair candidate由原
Reviewer targeted re-review GO、主線接受 architecture commit並另建
Implementation卡後，successor 才可開始。

### 10.1 唯一合法 base

- rejected candidate
  `acd835df…` 維持 non-ancestor evidence source；不得 merge、cherry-pick、copy
  patch、以其 tree作 worktree base或宣稱其 tests已通過。
- successor implementation唯一合法 base，是本 Repair經 Review GO後由主線接受的
  architecture commit；Implementation卡必須固定該完整 SHA及其 mainline parent。
- `acd835df…` 只能供理解 finding／行為契約，所有 runtime code與 tests必須在合法
  base上 clean-room reimplementation；每一行 diff都必須能由本文件、accepted
  前鏈 architecture或新 red test解釋，不以 rejected code存在作 green證據。

### 10.2 Keep／reimplement／reject matrix

| Capability | Successor action | Authority／regression ID | Required modules／tests |
|---|---|---|---|
| Accepted mainline非 Fog runtime行為 | `KEEP`；不得為本 chain改寫 | fixed successor base與 full regression | base既有 modules／tests |
| processed-ID authority | `REIMPLEMENT_CLEAN_ROOM` | `FRTA-REG-RRV-P1-01-PROCESSED-ID` | `scripts/verify_processed_id_authority.py`、`scripts/verify_fog_closed_regime_recovery.py`、`tests/test_fog_closed_regime_runtime.py` |
| source-lineage／trusted baseline authority | `REIMPLEMENT_CLEAN_ROOM` | `FRTA-REG-RRV-P1-03-SOURCE-BASELINE` | `scripts/fog_authority_contracts.py`、`scripts/verify_fog_closed_regime_recovery.py`、`tests/test_fog_closed_regime_runtime.py` |
| closed runtime exact receipt gate | `REIMPLEMENT_CLEAN_ROOM` | `FRTA-REG-RECEIPT-V3-EXACT` | `scripts/verify_closed_regime_runtime.py`、`scripts/verify_daily_research_quota.py`、`tests/test_fog_closed_regime_runtime.py`、`tests/test_daily_research_quota_verifier.py` |
| civil／artifact／source date authority | `REIMPLEMENT_CLEAN_ROOM` | `FRTA-REG-TIME-DATE-LINEAGE` | `scripts/fog_runtime_time_authority.py`、所有 producer／verifier adapters及直接 time tests |
| `acd835df…` code、fixtures與stored PASS | `REJECT` | non-ancestor evidence only | 不得成為 base、patch或 regression proof |

上述 regression ID是 successor required red→green ledger：

- `FRTA-REG-RRV-P1-01-PROCESSED-ID`：偽造／同源 processed-ID inventory必須 RED，
  clean-room independent authority後 GREEN。
- `FRTA-REG-RRV-P1-03-SOURCE-BASELINE`：source path/hash drift、self-reported
  baseline或 runtime可同步覆寫 baseline必須 RED，repo role-path authority與
  immutable baseline比對後 GREEN。
- `FRTA-REG-TIME-DATE-LINEAGE`：合法休市日 source lineage舊 invariant為 RED，
  三日期分離後 GREEN；wrong／future source與 artifact identity drift保持
  fail-closed GREEN。
- `FRTA-REG-RECEIPT-V3-EXACT`：missing／unknown／type mismatch／forged lineage
  必須 RED，producer與 verifier共用 schema後 GREEN。

### 10.3 Implementation slices

每個 slice 都是後續 successor implementation card 的上限，不由本 architecture
candidate 實作。下列 allowlist是逐 slice累加上限；若實作需要其他檔案，必須停下
回 architecture Review，不得臨場擴張。

### Slice I1：pure authority與red matrix

Changed-file allowlist：

- `config/fog_runtime_time_authority_v1.json`
- `docs/architecture/fog_runtime_receipt_v3.schema.json`（唯讀 authority；不得在
  implementation candidate改寫）
- `scripts/fog_authority_contracts.py`
- `scripts/fog_runtime_time_authority.py`
- `scripts/verify_processed_id_authority.py`
- `tests/test_fog_runtime_time_authority.py`
- `tests/test_fog_closed_regime_runtime.py`

Red tests：

- 本文件 deterministic time與source-date matrix；
- 12 項 invariants；
- exact RFC3339 `Z` parser、canonical hash與 boundary cases；
- host `TZ` parameterized replay。
- `FRTA-REG-RRV-P1-01-PROCESSED-ID` 與
  `FRTA-REG-RRV-P1-03-SOURCE-BASELINE` 的 authority unit tests。

Exit：pure tests green；尚未修改 runtime wiring。

### Slice I2：receipt v3 producer與source lineage

Changed-file allowlist：

- `scripts/verify_closed_regime_runtime.py`
- `scripts/verify_fog_closed_regime_recovery.py`
- `scripts/verify_processed_id_authority.py`
- `scripts/fog_authority_contracts.py`
- `scripts/fog_runtime_time_authority.py`
- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_daily_research_quota_verifier.py`

Red tests：

- v2 receipt 不得被誤標成 v3；
- context/generated market date mismatch fail closed；
- 合法休市日 `market_run_date=artifact_run_date=2026-08-08`、
  `daily_source_date=2026-08-07`通過；
- wrong／future source date、artifact identity drift、wrong contract hash、
  unknown fields、forged source dates、absolute paths 全拒；
- receipt producer 不接受 env policy override。
- `FRTA-REG-RECEIPT-V3-EXACT`、
  `FRTA-REG-RRV-P1-01-PROCESSED-ID`、
  `FRTA-REG-RRV-P1-03-SOURCE-BASELINE` red→green。

Exit：可用 fixture 產生 deterministic v3 receipt，未接 LaunchAgent。

### Slice I3：independent verifier

Changed-file allowlist：

- `scripts/verify_daily_research_quota.py`
- `scripts/verify_closed_regime_runtime.py`
- `scripts/verify_fog_closed_regime_recovery.py`
- `scripts/verify_processed_id_authority.py`
- `scripts/fog_authority_contracts.py`
- `scripts/fog_runtime_time_authority.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_closed_regime_runtime.py`

Red tests：

- 修復 `generated_utc.date() == run_date` regression；
- verifier 以自有 clock、canonical policy與 source artifacts 重算；
- stale/future/naive/wrong date/host drift 與 exact boundaries；
- v2／missing contract hash fail closed。
- predecessor processed-ID、source-lineage／baseline hostile cases與
  `FRTA-REG-TIME-DATE-LINEAGE`全部 red→green。

Exit：fixture consumer green；尚未切 production scheduler。

### Slice I4：shell與LaunchAgent wiring

Changed-file allowlist：

- `scripts/run_fog_research_worker.sh`
- `scripts/run_daily_research_quota.sh`
- `scripts/com.new-top10.fog-research-worker.plist`
- `scripts/fog_authority_contracts.py`
- `scripts/fog_runtime_time_authority.py`
- `scripts/verify_closed_regime_runtime.py`
- `scripts/verify_fog_closed_regime_recovery.py`
- `scripts/verify_processed_id_authority.py`
- `tests/test_fog_research_retry_circuit.sh`
- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_daily_research_quota_verifier.py`
- `tests/test_fog_runtime_time_wiring.sh`

Red tests：

- host `TZ=UTC`、`Asia/Taipei`、`America/Los_Angeles` 輸出相同 identity；
- shell source 中不存在 `date +%F` date authority fallback；
- legacy env mismatch fail closed；
- market-midnight rollover 不寫舊日期 receipt；
- plist 不注入 timezone/date/freshness policy。

Exit：static／fixture wiring green；不得 kickstart live LaunchAgent。

### Slice I5：migration與operational evidence

Changed-file allowlist：

- 後續 implementation card 本身
- `docs/AUTOMATION.md`
- 該卡指定的 `docs/evidence/<implementation-card>/**`
- 若 installer 需要同步 plist，明列 `scripts/setup_launchd.sh` 與對應 test

Red／acceptance gates：

- v2 receipt inventory 與 archive plan；
- installed plist 與 reviewed repo SHA/path alignment；
- 三輪跨 scheduler interval receipts；
- 一輪台北 00:00–07:59 bounded acceptance；
- circuit、queue、model、ranking與baseline before/after hashes。
- 固定 successor base、四個 `FRTA-REG-*` regression IDs及 clean-room diff
  mapping；不得引用 rejected candidate stored PASS。

I5 只有 independent Review GO 後才能操作 live state。

## 11. Migration ordering

1. 合併前先跑 I1 matrix/invariants，固定 policy hash。
2. 完成 I2 producer與 I3 verifier；新 verifier 只接受 v3，舊 v2 不做資料升級。
3. 完成 I4 wiring；候選碼仍不 reload/kickstart LaunchAgent。
4. independent Review 固定 base/candidate SHA，重跑 matrix、targeted tests、full
   suite、allowlist與 shell syntax。
5. Review GO 後，先停止 Fog LaunchAgent，保存 installed plist、retry state、
   queue與現有 v2 receipts 的 hashes。
6. 將 v2 receipts移到 timestamped archive；不得補造 contract hash 或改寫成 v3。
7. 安裝 reviewed plist／code，驗 installed path/SHA 與 canonical policy hash，
   再載入 job。
8. 先做一輪 bounded dry acceptance，再做三輪 scheduler acceptance；任何 gate
   失敗即停，不自動 open/recover circuit。

不採 dual-trust window：v2 沒有 versioned time contract hash，不能與 v3 同等
授權。短暫停止 worker比讓 legacy receipt 繼續取得 freshness authority安全。

## 12. Rollback

Rollback target 是 **safe stopped state**，不是恢復已知有 UTC/local-date regression
的 legacy runtime：

1. unload/stop Fog LaunchAgent；
2. 保存失敗 v3 receipt、verifier output、logs、retry/queue state hashes；
3. 還原 reviewed 前的 code/plist 只供 forensic comparison；
4. 不把 archived v2 receipt 改名回 active path，不自動清 circuit或重放 queue；
5. 保持 worker disabled，主線另開修復卡；
6. model、ranking、baseline與 production artifacts 必須維持 rollout 前 hash。

重新啟用必須有新的 reviewed candidate 與 live acceptance 授權。

## 13. Production與acceptance boundary

Architecture candidate 可以證明 contract 完整與 deterministic matrix 已定義，但
不能證明：

- 舊 strict chain 已修復；
- installed LaunchAgent 已更新；
- runtime、circuit或queue已恢復；
- 三輪 scheduler acceptance已通過；
- production ready或可 merge。

後續 implementation candidate 禁止自行 merge/push/deploy。只有固定 SHA 的
independent Review GO 後，主線才能授權 I5 live acceptance；live acceptance
仍不得修改 model、ranking、weights、baseline或 promotion state。

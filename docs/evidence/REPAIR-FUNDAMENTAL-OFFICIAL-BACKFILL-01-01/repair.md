# REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-01

status: `DELIVERED_REPAIR_CANDIDATE`

## Preflight

- runtime model：`gpt-5.6-sol`
- reasoning：`high`
- cwd／worktree：`<repo-root>`（乾淨的隔離 Codex worktree）
- branch：detached HEAD；既有 `codex/repair-fundamental-official-backfill-01-01`
  branch 綁定另一個 worktree，為避免跨 worktree 競寫未搶占 branch。
- 開始時 HEAD：`9d27d6d90a90ea2f73968eb05899cfb2c028bce0`
- 固定 parent candidate：
  `ae12ef39805e812d86d9a1a8bf3a963b6052a901`
- 固定 review evidence：
  `ce94b06ad0c691b6a2b5c3921bff1aff9b1f006c`
- ancestry：`parent candidate -> review evidence -> repair card HEAD`
- repair candidate：本 evidence 所在 commit；完整 SHA 由交付訊息回報，避免
  self-referential commit SHA。
- 未 merge、push、deploy 或 promotion。

目前 worktree 沒有 `.venv`；測試使用同 repo 既有
`<repo-root>/.venv/bin/python` 等價環境執行，程式碼與 pytest 工作目錄均為本隔離
worktree。

## Root-cause hypotheses

1. FND-FUND-001：production candidate 僅用 cache coverage gate，研究覆蓋率達
   80% 後即自動納入 `fundamental_*`。
2. FND-FUND-002：parser 只取 row 的第一個 fact，未解析 `contextRef`，且 cache
   builder 未將 Q2/Q3/Q4 YTD 現金流差分成單季。
3. FND-FUND-003：ZIP 在 `archive.read()` 前未驗證 member metadata。

三個假說均由 red tests 重現，未發現替代層（服務、shadow scoring 或下載 transport）
造成相同症狀。

## Red -> green

Red command：

```bash
<repo-root>/.venv/bin/python -m pytest -q tests/test_mops_xbrl_fundamentals.py
```

修復前：

```text
6 failed, 5 passed
```

- FND-FUND-001：99.8% coverage 時九個 `fundamental_*` 仍在 candidates。
- FND-FUND-002：prior-year 第一個 fact 被誤取，Q1 FCF 得到 `9000` 而非 `90`；
  Q2 缺前季時未 fail closed。
- FND-FUND-003：member count、單檔未壓縮大小、總未壓縮大小三種超限均未阻擋。

最小修復後：

```text
11 passed in 1.41s
```

## Fix mapping

### FND-FUND-001

- `FUNDAMENTAL_PRODUCTION_PROMOTION_ENABLED = False` 是獨立、預設關閉的 production
  gate。
- `candidate_feature_columns()` 在 gate 關閉時一律排除 `fundamental_*`，不再以高
  coverage 視為 promotion。
- 99.8% regression verifier：

```text
PRODUCTION_GATE_OK coverage=0.9980 fundamental_candidates=[] rows=535981
```

readiness 與 shadow 仍可載入基本面欄位；未改 promotion 狀態。

### FND-FUND-002

- 解析 inline XBRL `contextRef` 對應的 `startDate`／`endDate`，只選本期結束日，
  並優先使用正確單季或 YTD context；fixture 將去年同期排在本期之前，確認不再依
  DOM 順序誤選。
- Q1 保持單季；Q2/Q3/Q4 以同年度前季 YTD 差分 OCF 與 capex。
- 缺前季、context 不一致或差分所需 component 缺漏時，
  `free_cash_flow = null` 並標記 `missing_previous_ytd`／`invalid_context`。
- 真實官方 ZIP 2330 驗證：

```text
2025Q1 FCF=294746942 grain=single_quarter
2025Q2 FCF=199838284 normalization=ytd_difference
2025Q3 FCF=139377087 normalization=ytd_difference
2025Q4 FCF=368602783 normalization=ytd_difference
2026Q1 FCF=348213466 grain=single_quarter
2024Q4 FCF=null grain=missing_previous_ytd
```

2024Q4 缺 2024Q3（卡片起始資料為 2024Q4），故依契約 fail closed。

### FND-FUND-003

- 在任何 `archive.read()` 前檢查：
  - member 數：最多 `10000`
  - 單檔未壓縮大小：最多 `64 MiB`
  - 總未壓縮大小：最多 `8 GiB`
- 超限以含實際值、檔名與上限的 `ValueError` fail closed。
- regression 使用 4096 bytes 高壓縮比 member 與縮小的測試上限，不建立耗盡記憶體
  payload。
- 六個官方 ZIP 的實際最大值：

```text
members=2714
max_uncompressed=2985772 bytes
total_uncompressed=1539679438 bytes
```

全部低於 production limits。

## Readiness / shadow verifier

使用官方六季 ZIP 在系統暫存目錄建立隔離新 cache，沒有覆寫 repo cache 或既有
artifact：

```text
CACHE_WRITTEN 1963/1967
FUNDAMENTAL_POINT_IN_TIME_READINESS_OK
decision=READY_FOR_POINT_IN_TIME_RESEARCH
usable_stock_coverage=0.997966
recent_252_days_meeting_research_gate=252/252
```

readiness 舊／新一致，且 artifact 的 `promotion_allowed: false` 契約不變。

FCF 語義修正會改變 shadow artifact，因此不沿用舊 artifact 自證：

| 指標 | 舊 artifact | 新隔離重算 |
|---|---:|---:|
| stocks / coverage | 1967 / 0.998 | 1967 / 0.998 |
| mean score | 0.3784 | 0.3789 |
| IC | 0.0148 | 0.0156 |
| IC median | 0.0159 | 0.0190 |
| top-bottom spread | -0.000413 | -0.000141 |

- cashflow score 改變：552 檔。
- fundamental quality score 改變：534 檔。
- quality absolute delta mean / max：`0.020144 / 0.075`。
- 原因：Q2/Q3/Q4 FCF 從 YTD 累計改為可跨季比較的單季值；不是權重、ranking 或
  promotion 變更。

## Verification

```text
<repo-root>/.venv/bin/python -m pytest -q tests/test_mops_xbrl_fundamentals.py
=> 11 passed

<repo-root>/.venv/bin/python -m pytest -q
=> 1 failed, 484 passed, 246 subtests passed

git diff --check
=> PASS

py_compile changed Python files
=> PASS

debug instrumentation marker scan
=> none
```

全套唯一失敗：

```text
tests/test_research_component_ledger.py::
ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
failed check=evidence_exists
```

缺少的是既有 model experiment、reference data 與 market context artifacts；與 review
時的環境缺口相同，本 repair 未修改 ledger、artifact inventory 或相關測試。沒有新增
其他失敗。

## Remaining risk

- 官方整批 ZIP 仍可能反映後續更補正版本；本修復只校正目前檔案的 context grain，
  不宣稱逐版本歷史真值。
- 起始資料缺少前季時 FCF 會保守為 null；這會降低該期可用性，但避免把 YTD 當單季。
- 本交付只供原 Reviewer re-review，不是 production promotion 核准。

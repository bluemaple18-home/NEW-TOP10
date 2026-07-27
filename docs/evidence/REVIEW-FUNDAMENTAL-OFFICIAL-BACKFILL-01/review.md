---
id: REVIEW-FUNDAMENTAL-OFFICIAL-BACKFILL-01
status: completed
type: review
verdict: NO_GO
---

# REVIEW-FUNDAMENTAL-OFFICIAL-BACKFILL-01

## Preflight

- reviewer model：`gpt-5.6-sol`
- reasoning：`high`
- 實際 review worktree／cwd：`/private/tmp/top10new-review-fundamental-official-backfill-01`
- branch：`codex/review-fundamental-official-backfill-01`
- review 開始時 HEAD：`c54463387c63ca201e2ca7bbc3bb8b8a472ee3a3`
- 固定 base：`09a9fa0`
- 固定 candidate／完整 reviewed SHA：`ae12ef39805e812d86d9a1a8bf3a963b6052a901`
- ancestry：`base -> candidate -> c544633`；`c544633` 僅新增本 review 卡片。
- review 開始時 worktree：乾淨。
- reviewer 未修改 candidate，未 merge、push 或 deploy。

## Findings

### [P1] 匯入後會自動把九個基本面欄位送進正式 retrain 候選，違反「不做 feature promotion」

- 位置：`scripts/import_mops_xbrl_fundamentals.py:54-59`
- 既有 consumer：`app/modeling/feature_contract.py:150-164`、
  `app/agent_b_modeling.py:150-170`
- 觸發條件：執行本卡匯入，讓 `data/fundamentals` coverage 從低覆蓋提升至
  `0.998`，之後執行既有 Agent B retrain。
- 實際證據：在隔離 candidate 與本次 cache 上呼叫
  `load_m4_feature_frame()` + `candidate_feature_columns()`，九個欄位全部自動納入：
  `fundamental_roe`、`fundamental_gross_margin`、`fundamental_debt_ratio`、
  `fundamental_operating_margin`、`fundamental_net_margin`、
  `fundamental_current_ratio`、`fundamental_roa`、
  `fundamental_free_cash_flow`、`fundamental_eps`。
- 風險：本卡雖未直接改權重，但資料 side effect 解除既有 80% gate，下一次正式 retrain
  會改變模型候選特徵與模型行為；這與 implementation 卡的
  「不調整 feature promotion」及 readiness artifact 的
  `promotion_allowed: false` 不一致。
- 建議修法：將「資料研究可用」與「production trainable」拆成獨立、預設關閉的顯式
  promotion gate；Agent B 只有在另張 promotion 卡與通過 replay/OOS 證據後才允許基本面欄位。
  加一個使用 99.8% cache 的 regression test，斷言 production retrain 在 promotion 前仍排除
  全部 `fundamental_*`。

### [P1] Q2/Q3 現金流是 YTD 累計值，卻與單季指標混用並直接做跨季趨勢

- 位置：`app/fundamentals/mops_xbrl.py:159-180`
- downstream：`app/fundamentals/scoring.py:86-91`
- 觸發條件：解析 Q2/Q3 MOPS inline XBRL，接著建立 shadow score 或使用
  `fundamental_free_cash_flow`。
- 實際證據：官方 `2330-2025Q2` 報表的收入第一個 context 是
  `From20250401To20250630`，但營業現金流與資本支出的 context 是
  `From20250101To20250630`；Q3 同樣是單季收入
  `From20250701To20250930` 搭配 YTD 現金流
  `From20250101To20250930`。parser 不保留或檢查 `contextRef`，直接把兩者存成同一季
  metric。`score_fundamentals()` 又將最新 FCF 與前一季 FCF 比較，因此 Q2/Q3 很容易只因
  累計期間變長而得到「改善」分數。
- 風險：`fundamental_free_cash_flow` 的跨季可比性不成立，shadow IC、分位數及未來可能的
  模型特徵都會混入機械性季序效果；這不是單純單位問題。
- 建議修法：解析並驗證 `contextRef` 的起訖日；將 YTD OCF/capex 差分成單季值，或明確把
  FCF 定義為 YTD 並禁止跨季 trend comparison。補 Q2/Q3 真實結構 fixture，驗證單季化及
  去年同期／本期 context 選擇。

### [P2] 外部 ZIP member 無解壓後大小上限，單一惡意 member 可耗盡記憶體

- 位置：`app/fundamentals/mops_xbrl.py:128-146`
- 觸發條件：下載端、cache 或人工指定的 ZIP 含高壓縮比或超大 HTML member。
- 風險：`archive.read(name)` 會一次把完整解壓內容載入記憶體；目前 `_valid_zip()` 只確認
  ZIP 可開啟且非空，無 member 數量、未壓縮總量或單檔上限。
- 建議修法：讀取前檢查 `ZipInfo.file_size`、member 數量與總未壓縮量，採明確上限並在超限
  時 fail closed；補 zip-bomb metadata regression test。

## Spec axis

- 驗收 1：合成 parser 測試涵蓋欄位、`sign="-"`、合併優先與日期，但未覆蓋真實
  Q2/Q3 context grain，故不足以證明現金流語義正確。
- 驗收 2：通過；隔離資料重現 `1963/1967`、coverage `0.998`。
- 驗收 3：數字可重現；readiness 為 `READY_FOR_POINT_IN_TIME_RESEARCH`，
  artifact 與 candidate 版本逐 byte 相同。但 P1 finding 使其不能代表 feature promotion
  仍被關閉。
- 驗收 4：受影響測試與 `git diff --check` 通過；全套測試在 reviewer worktree 因缺少
  既有 ledger evidence artifacts 得到 `1 failed, 478 passed, 246 subtests passed`。
  唯一失敗為 `evidence_exists` 環境缺口，未歸因於本 diff。
- 明確限制：更補正版本限制有一致揭露，未宣稱逐版本歷史真值。
- 結論：`FAIL`。資料覆蓋與 readiness 數字成立，但「不做 feature promotion」及可比
  財務指標契約不成立。

## Standards axis

- Correctness：`FAIL`；Q2/Q3 FCF grain 不一致。
- Regression：`FAIL`；高 coverage cache 會改變正式 retrain 候選特徵。
- Security/privacy：`FAIL`；無 secret/PII/本機絕對路徑洩漏，但 ZIP 解壓資源無界。
- Testing：`FAIL`；缺真實多 context、YTD/單季化、高 coverage production gate 與 ZIP
  資源限制測試。
- Evidence：`PASS_WITH_LIMIT`；readiness artifact byte-for-byte 重現，shadow 核心數字重現；
  full suite 有 reviewer worktree 既有 artifact 缺口。
- Maintainability：未發現額外阻塞問題。
- 結論：`FAIL`。

## Verification

```text
git diff --check 09a9fa0...ae12ef39805e812d86d9a1a8bf3a963b6052a901
=> PASS

/Users/mattkuo/TOP10new/.venv/bin/python -m pytest -q tests/test_mops_xbrl_fundamentals.py
=> 5 passed in 2.41s

/Users/mattkuo/TOP10new/.venv/bin/python -m pytest -q
=> 1 failed, 478 passed, 246 subtests passed
=> 唯一失敗：tests/test_research_component_ledger.py::...test_verifier_accepts_generated_ledger
=> 根因：reviewer worktree 未攜帶既有 ledger evidence artifacts；failed check=evidence_exists

# 隔離 candidate + cache
/Users/mattkuo/TOP10new/.venv/bin/python scripts/build_fundamental_point_in_time_readiness.py
=> READY_FOR_POINT_IN_TIME_RESEARCH; usable_stock_coverage=0.997966

/Users/mattkuo/TOP10new/.venv/bin/python scripts/verify_fundamental_point_in_time_readiness.py
=> FUNDAMENTAL_POINT_IN_TIME_READINESS_OK

/Users/mattkuo/TOP10new/.venv/bin/python scripts/build_fundamental_shadow_scores.py \
  --data-dir data/clean \
  --output-prefix reviewer_fundamental_shadow_mops_full_universe \
  --horizon 10
=> stocks=1967; coverage=0.9980; ic=0.0148; top_bottom_spread=-0.000413

shasum -a 256 <candidate-artifact> <reviewer-generated-artifact>
=> 兩者皆為 a56bf5c34f6c8a28e1d48fb4b2f0765be66c35801b761b6d2727ecb5cebdc3bc
=> cmp exit 0

load_m4_feature_frame() + candidate_feature_columns()
=> coverage=0.998
=> 九個 fundamental_* 欄位全部 auto_included
```

## Verdict

`NO_GO`

candidate 不得進 mainline acceptance；應另開 Repair 卡修正 production promotion gate、
季度現金流 grain 與 ZIP resource limits，再以固定 repair SHA 重審。

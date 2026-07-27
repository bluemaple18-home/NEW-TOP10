---
id: REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-01
status: CARD_DRAFTED
type: repair
chain_id: FUNDAMENTAL-OFFICIAL-BACKFILL-01
generation: 1
ownership: repair_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 修正 point-in-time 財務資料、production promotion gate 與外部 ZIP 資源邊界。
parent_candidate_sha: ae12ef39805e812d86d9a1a8bf3a963b6052a901
review_evidence_sha: ce94b06ad0c691b6a2b5c3921bff1aff9b1f006c
reviewer_thread_id: 019fa23f-1e4b-7b31-b2a4-9fcd37301771
evidence_path: docs/evidence/REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-01/
---

# REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-01

## 目的

只修正獨立 Review 的三項 finding，維持原 Fundamental backfill 範圍；完成後交回同一
Reviewer task re-review，不自行接受、整合或推送。

## 固定 Findings

### FND-FUND-001（P1）Production feature promotion gate

- 高 coverage cache 不得讓 `fundamental_*` 自動進入 production retrain candidate。
- 建立獨立、預設關閉的明確 promotion gate。
- 未有另一張 promotion 卡與 evidence 前，production retrain 必須排除全部
  `fundamental_*`；research/readiness/shadow 仍可使用。
- 加 99.8% coverage regression test。

### FND-FUND-002（P1）Q2/Q3 現金流 grain

- 解析並驗證 inline XBRL `contextRef` 起訖日。
- 對 YTD OCF/capex 做單季化，或採另一個明確且禁止跨季誤比的等價契約。
- 必須處理 Q1、Q2、Q3、Q4、去年同期／本期 context 與缺前季資料。
- 加真實結構 fixture，證明 FCF 跨季可比；不得只加合成單 context happy path。

### FND-FUND-003（P2）ZIP resource limits

- 讀取 member 前限制 member 數量、單檔與總未壓縮大小。
- 超限 fail closed，錯誤訊息可診斷。
- 加高壓縮比／超大 metadata regression test；不得實際建立會耗盡記憶體的 payload。

## Allowlist

- `app/fundamentals/**`
- `app/modeling/feature_contract.py`
- `app/agent_b_modeling.py`
- `app/services/fundamental_service.py`
- `scripts/import_mops_xbrl_fundamentals.py`
- `scripts/build_fundamental_point_in_time_readiness.py`
- `scripts/build_fundamental_shadow_scores.py`
- `tests/**fundamental**`
- 與 production feature contract 直接相關的最小測試檔
- `docs/evidence/REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-01/**`
- 本卡狀態更新

超出 allowlist 必須停手回報，不得順手重構。

## 禁止範圍

- 不調 ranking、權重、Top10、UI、API 或模型 promotion 狀態。
- 不 merge、push、deploy。
- 不改 Review finding ID、severity 或 reviewer verdict。
- 不把本 repair 宣稱為 production promotion 核准。

## 執行順序

1. 保存 parent candidate baseline。
2. 先新增會重現三項 finding 的紅燈測試，記錄 failure。
3. 做最小修復。
4. 跑受影響測試、Fundamental verifier、全套 pytest 與 `git diff --check`。
5. 寫入 repair evidence，提交唯一 repair candidate SHA。

## 驗證

```bash
cd <repo-root>
.venv/bin/python -m pytest -q tests/test_mops_xbrl_fundamentals.py
.venv/bin/python -m pytest -q
git diff --check
```

另需重跑 readiness／shadow verifier，確認：

- readiness 仍只代表 point-in-time research readiness。
- production retrain 在 promotion 前排除 `fundamental_*`。
- FCF 修正後 artifact 若改變，舊／新數字與原因完整揭露，不得沿用舊 artifact 自證。

## 交付

- `DELIVERED_REPAIR_CANDIDATE`
- 完整 parent、review evidence、repair candidate SHA
- 三項 finding 的 red→green 證據
- 測試／verifier 結果與剩餘風險

交付後回原 Reviewer task `019fa23f-1e4b-7b31-b2a4-9fcd37301771` re-review。

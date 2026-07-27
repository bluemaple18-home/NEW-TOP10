---
id: REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-02
status: CARD_DRAFTED
type: repair
chain_id: FUNDAMENTAL-OFFICIAL-BACKFILL-01
generation: 2
ownership: repair_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 最後一次 bounded repair，只修正式 downloader 的 ZIP 資源超限診斷契約。
parent_repair_sha: 48c10ab86420d57bb8a662e74d95b920e25930d3
re_review_evidence_sha: dbb66cdee42b4a9d94ffaf6cffcbc320838b0a82
reviewer_thread_id: 019fa23f-1e4b-7b31-b2a4-9fcd37301771
evidence_path: docs/evidence/REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-02/
---

# REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-02

## 目的

只關閉尚未完成的 `FND-FUND-003` download-path 診斷傳遞。`FND-FUND-001` 與
`FND-FUND-002` 已由原 Reviewer 關閉，不得重開或修改。

## 唯一 Finding

### FND-FUND-003（P2）

`download_xbrl_zip()` 目前透過 `_valid_zip()` 吞掉 `_validate_zip_resources()` 的詳細
`ValueError`，將 member 數、單檔或總未壓縮量超限泛化成「不是有效 ZIP」。

修復契約：

- ZIP 結構無效與資源超限必須是可區分的失敗。
- 正式 download path 必須保留超限 member 名稱、實際值與上限。
- cache reuse 與新下載都必須套用相同資源驗證。
- 補 downloader regression；不得只測 `parse_xbrl_zip()`。

## Allowlist

- `app/fundamentals/mops_xbrl.py`
- `tests/test_mops_xbrl_fundamentals.py`
- `docs/evidence/REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-02/**`
- 本卡狀態更新

任何其他程式碼檔案變更都必須停手。

## 禁止範圍

- 不改 promotion gate、FCF normalization、ranking、權重、API、UI 或 production 狀態。
- 不重開 FND-FUND-001/002。
- 不 merge、push、deploy。
- 這是 Repair-2；若原 Reviewer仍 `NO_GO`，必須進入 `BLOCKED / REVIEW_REPAIR_LIMIT`，
  不得建立 Repair-3。

## 執行順序

1. 先新增 downloader/cache reuse 超限訊息紅燈測試。
2. 保存 red failure。
3. 做最小 exception-flow 修復。
4. 跑 targeted、Fundamental suite、全套 pytest 與 `git diff --check`。
5. 寫 repair evidence 並提交唯一 Repair-2 candidate。

## 驗證

```bash
cd <repo-root>
.venv/bin/python -m pytest -q tests/test_mops_xbrl_fundamentals.py
.venv/bin/python -m pytest -q
git diff --check
```

## 交付

只交付：

- `DELIVERED_REPAIR_CANDIDATE`
- 完整 parent Repair-1 SHA、Repair-2 SHA
- FND-FUND-003 red→green 證據
- 測試結果與剩餘風險

交付後必須回原 Reviewer task 最終 re-review。

---
id: RESEARCH-FEATURE-REGIME-WF-01
status: COMPLETED_NO_GO
type: evaluation
---

# Feature Group × Regime 嚴格 Walk-forward

## Root question

哪些 feature group 在只使用當時已成熟標籤的情況下，仍能於不同市場盤勢產生穩定的橫斷面選股訊號？

## 契約

- expanding-window；每 fold 的測試資料不得參與特徵選擇或方向判定。
- 10D 預測使用 10 個交易日 label embargo。
- UNKNOWN 或訓練樣本不足的 regime/group 必須標記 unavailable，不得套 fallback。
- regime history 延伸必須 append-only；重疊日期保留封存 base label，資料回補造成的 drift 只記 receipt、不覆寫。
- 排除 availability flag、原始價格層級與絕對 VWAP；技術趨勢和籌碼流分組評估。
- 每個特徵與 OOS group score 的逐日有效橫斷面覆蓋率至少 70%。
- 所有籌碼衍生欄位必須服從 `institutional_available`；來源不可得時遮罩為 unavailable，禁止把衍生 0 當成未買超。
- 僅能輸出 `WALKFORWARD_CANDIDATE`、`MONITOR_ONLY`、`REJECTED` 或 `INSUFFICIENT_DATA`。
- 不修改模型、production ranking、正式 feature、權重、API 或 UI。

## Acceptance

- verifier 證明 fold embargo、train-only selection 與負向特徵方向處理。
- 以受控真實資料完成至少 3 folds。
- artifact 記錄資料範圍、fold、selection、OOS 指標、排除與剩餘風險。
- `git diff --check` 通過，production 與 model hash 不受影響。

## 執行

```bash
uv run --with-requirements requirements.txt python scripts/verify_feature_group_regime_walkforward.py
uv run --with-requirements requirements.txt python scripts/research_feature_group_regime_walkforward.py
```

## 結果

- acceptance：`NO_GO_FOR_PORTFOLIO_REPLAY`
- 嚴格候選：0
- `MONITOR_ONLY`：`cost_basis`
- 條件監控：`NARROW_LEADER/liquidity_activity`
- `chip_flow`：真實法人來源覆蓋僅 10.4471%，遮罩缺值後為 `INSUFFICIENT_DATA`。
- 詳細證據：`docs/evidence/RESEARCH-FEATURE-REGIME-WF-01/result.md`

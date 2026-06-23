# WEEKEND-TRAINING-10 unsupported unlock plan

## 任務目的

代表 queue 已結束後，不再繼續 drain representative replay。

本卡負責把 `574,695` 個 `UNSUPPORTED_INPUT` 拆成可執行的下一階段：

- 哪些 unsupported 是資料或 artifact 缺口，補齊後可以重算。
- 哪些 unsupported 是目前策略世界觀不支援，應保留灰霧，不假裝已探索。
- 哪一類最值得先解鎖，避免盲目展開 60 萬格。

## 目前基準

來源：`artifacts/weekend_training/weekend_training_rollup_2026-06-13.json`

```text
full_universe_total: 662,256
expanded_processed: 21,147
rollup_classified_total: 662,256
representative_replay_pending_count: 0
next_stage_count: 196
survivor_deep_replay: 196 MONITOR_ONLY
unsupported_count: 574,695
```

Unsupported 分布：

```text
UNSUPPORTED_REGIME_SLICE_NO_DATA: 283,824
UNSUPPORTED_RANKING_DIR_MISSING: 202,176
UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE: 88,695
```

## 判斷原則

本卡不是 production rollout。

不准：

- 改 production ranking。
- 改 `models/latest_lgbm.pkl`。
- 改 Clawd live publish。
- 把 unsupported / inherited / pruned 當成 executed replay。
- 為了點亮地圖而新增無證據規則。

可以：

- 建立 unsupported unlock audit artifact。
- 找出 ranking dir 是否能由既有 artifact 補齊。
- 評估 `TOPIC_DEFAULT` entry filter 是否應正規化成既有 filter，或保持不支援。
- 評估 `NEUTRAL_ONLY` / `PANIC_SELLING_ONLY` / `RISK_OFF_ONLY` 是否缺資料、缺合約，或本階段不該跑。

## 優先順序

1. `UNSUPPORTED_RANKING_DIR_MISSING`

   這類最像 artifact 接線缺口。若能由既有 production / candidate ranking artifact 補齊，可釋放 `202,176` 格。

2. `UNSUPPORTED_ENTRY_FILTER_NOT_AVAILABLE`

   `TOPIC_DEFAULT` 目前不是可 replay filter。要決定它是：

   - 映射到 `NONE` / `LOG_GATE` / `PERCENTILE_GATE` 的其中之一。
   - 還是明確保留 unsupported，避免假設污染。

3. `UNSUPPORTED_REGIME_SLICE_NO_DATA`

   數量最大，但風險最高。`NEUTRAL_ONLY` / `PANIC_SELLING_ONLY` / `RISK_OFF_ONLY` 不能只為了湊數硬跑；必須先確認該 regime slice 有足夠樣本與明確用途。

## 預期產物

- `artifacts/weekend_training/weekend_unsupported_unlock_audit_YYYY-MM-DD.json`
- `artifacts/weekend_training/weekend_unsupported_unlock_audit_YYYY-MM-DD.md`
- `artifacts/weekend_training/weekend_unsupported_unlock_audit_verification_latest.json`

## 驗收標準

- audit 必須列出三類 unsupported 的 count、原因、是否可解鎖、解鎖成本、風險。
- 若某類不可解鎖，必須寫明原因，不得只寫 `skip`。
- 若某類可解鎖，必須列出下一步要跑的最小 smoke replay，不得直接大批量重跑。
- verifier 必須確認：
  - unsupported count 與 rollup 一致。
  - category count 加總等於 unsupported count。
  - 每個 category 都有 `unlock_decision`。
  - production impact 是 `NO_PRODUCTION_CHANGE`。

## 下一步建議

先做 audit builder / verifier。

如果 audit 顯示 `UNSUPPORTED_RANKING_DIR_MISSING` 可低風險補齊，再開下一張卡跑最小 smoke，不直接重跑 202,176 格。

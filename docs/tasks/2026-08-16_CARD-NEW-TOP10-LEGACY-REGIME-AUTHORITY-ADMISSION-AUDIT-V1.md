# CARD-NEW-TOP10-LEGACY-REGIME-AUTHORITY-ADMISSION-AUDIT-V1

## 目標

判定既有 `market-regime-history.v1` 長區間資料，是否可在不重抓行情、不改 regime 定義的前提下，升級成 exact-regime replay 可接受的研究 authority。

## 固定輸入

- legacy：`artifacts/model_experiments/market_regime_history_2023-11-21_2026-05-15.json`
- current authority：`artifacts/market_regime_history.json`
- canonical builder：`scripts/build_market_regime_history.py`
- replay horizon：`20`
- entry delay：`1`

## 邊界

- 全程唯讀既有資料。
- 不改 base regime label、family 判定、ranking、模型或 production。
- 不把 schema 遷移結果寫回 legacy/current authority。
- legacy producer input 不存在、重疊 identity 漂移或契約不完整時必須 fail closed。

## 產出

- `app/research/legacy_regime_authority_admission.py`
- `tests/test_legacy_regime_authority_admission.py`
- `docs/evidence/CARD-NEW-TOP10-LEGACY-REGIME-AUTHORITY-ADMISSION-AUDIT-V1/admission.json`

## 決策契約

- `READY_FOR_STAGED_MIGRATION`：來源可重現、重疊 identity 完全一致、v2 contract 完整，且至少一個 exact h20 episode 可用。
- `NO-GO_NO_ELIGIBLE_EPISODE`：authority 可接受，但沒有 exact h20 episode。
- `BLOCKED_AUTHORITY_NOT_ADMISSIBLE`：來源不可重現、hash/shape/schema 錯誤、重疊 identity 漂移或契約升級無法證明。

## 驗收

- 以 SHA-256 鎖定兩份輸入。
- 驗證日期唯一、排序、schema 與摘要一致。
- 使用 canonical v2 enrichment 函式做記憶體內遷移；不得改 base label。
- 比對所有重疊日期的 exact identity，列出漂移數與樣本。
- 依 canonical episode 規則計算 `h20 + entry_delay=1` 可用 episode。
- 缺來源或 identity 漂移時，即使有可用 episode也不得 admission。
- `pytest`、artifact verifier、`git diff --check` 通過。

## 儲存安全

- 網路請求：0。
- raw data 寫入：0。
- evidence 上限：1 檔、256 KiB。
- 超限、輸入異動或磁碟使用率達 80% 即停止，不啟動任何回填。

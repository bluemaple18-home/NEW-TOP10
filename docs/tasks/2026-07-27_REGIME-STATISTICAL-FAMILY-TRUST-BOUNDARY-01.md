---
id: REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01
status: CARD_DRAFTED
type: implementation
chain_id: REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01
supersedes_blocked_chain: REGIME-RESEARCH-AUTONOMY-01
ownership: implementation_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 修正可偽造 statistical family 的研究信任邊界，並以 720 universe／81 partition 實跑驗證。
source_candidate_sha: f656c18a6ec716d40c824d83174419abbeaf2530
blocked_review_evidence_sha: e2da87d64ffeb35d2a6855e5af20b29aa8e46814
evidence_path: docs/evidence/REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01/
---

# REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01

## 目的

封閉 public matrix CLI 可自行登錄小型 local family 的最後漏洞，然後實際跑通目前可稽核
的 720-combination universe 與 81-combination profile partition，保存真實 canary trace
與資料缺口。

本卡是新的 successor chain，不是 `REGIME-RESEARCH-AUTONOMY-01` Repair-3；舊 chain
維持 `BLOCKED / REVIEW_REPAIR_LIMIT`，其最終 evidence 不得改寫。

## 根因

目前 public matrix CLI 仍可接受一份內容自洽、可進 registry、但只宣告 3 個 combinations
的 registration，並以 `0.05 / 3` 通過。這讓呼叫者可縮小 family，繞過正式 contract 的
720-family Bonferroni 校正。

## 必做修復

1. Statistical family authority 必須來自 immutable contract／由主 manager 簽發的
   content-addressed registration，不得由 matrix caller 自行宣告。
2. Registration 必須綁定：
   - contract hash
   - 720 global combination IDs／hash／family ID
   - 合法 partition policy
   - 本次 81 tested IDs／hash
   - exact regime／episode split／dataset lineage
3. Registry acceptance 不等於 statistical authority；matrix CLI 必須重新由可信 contract
   驗證 registration。
4. 偽造 3-combination local family、未知 contract、錯誤 global hash、非法 partition、
   重複／遺漏 tested IDs 一律 fail closed。
5. 統計分母固定使用 contract global family size 720。

## 實跑要求

### Canary A：Trust-boundary adversarial

- 重現 blocked Reviewer 的 3-combination registration。
- 修復前保存可通過證據；修復後必須拒絕。

### Canary B：81／720 public CLI

- 由正式 contract 產生 720 immutable IDs。
- 執行目前 validation profile 的 81 IDs。
- 驗證 81 IDs 是合法 partition、無重複且皆屬於 720。
- corrected alpha 固定 `0.05 / 720`。
- baseline／candidate 使用同一 registration、episode split 與 family。

### Canary C：Partition coverage

- 列舉所有合法 partitions。
- union 必須覆蓋 720，intersection／重複與遺漏必須有明確 policy。
- 若現有 profiles 無法覆蓋 720，輸出 `PARTITION_COVERAGE_INCOMPLETE` 與缺少 IDs；
  不得假裝已完成完整搜尋。

### Canary D：Available-data closed run

- 使用 repo 現有真實可用資料，選擇資料最完整的 exact regime 做 bounded closed-mode run。
- 不下載新機敏資料、不使用未授權 production feed。
- 完整跑 registration → matrix → statistical gate → state transition。
- 樣本不足時輸出 `INSUFFICIENT_EVIDENCE`，附：
  - exact regime
  - 可用 episode 數
  - development／validation／sealed 缺口
  - 理論最低統計單位與目前實際值
  - 下一個可重跑資料日期／條件（若可推導）

## Allowlist

- `scripts/run_autonomous_research.py`
- `scripts/run_backtest_strategy_matrix.py`
- `scripts/verify_regime_research_autonomy.py`
- `config/regime_research_contract.json`
- `tests/test_regime_research_autonomy.py`
- 新增的 bounded canary runner／verifier 與測試
- `docs/evidence/REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01/**`
- 本卡狀態更新

## 禁止範圍

- 不修改 production model、ranking、權重、promotion、API 或 UI。
- 不宣稱兩百萬 universe 已被證明。
- 不因想取得策略而降低 family size、alpha、episode 或 sealed gate。
- 不 merge、push、deploy。
- 不把 canary 的 `INSUFFICIENT_EVIDENCE` 寫成 `NO_STRATEGY`。

## Phase 0：Red baseline

先建立：

- 偽造 3-family registration 可通過的 public-path red test。
- 81／720 合法 registration positive test。
- partition union／duplicate／missing red tests。
- available-data canary 的 dry-run contract test。

保存 red evidence後才能修改 production 接縫。

## 驗證

```bash
cd <repo-root>
.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py
.venv/bin/python scripts/verify_regime_research_autonomy.py \
  --base 7efda43641118f36b10261b4a04e0278bba941a2 \
  --candidate <candidate-sha>
.venv/bin/python -m pytest -q
git diff --check
```

另需保存四個 canary 的命令、輸入 hash、輸出、耗時、組合數、episode 數與狀態鏈。

## 交付

- `DELIVERED_CANDIDATE`
- 完整 candidate SHA
- Red→green evidence
- 720 universe／81 partition receipts
- available-data closed-run result
- 實跑發現的新問題清單
- production hashes unchanged

交付後建立新的獨立 Review；不得沿用舊 blocked Reviewer verdict 自行接受。

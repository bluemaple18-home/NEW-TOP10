---
id: REPAIR-REGIME-RESEARCH-AUTONOMY-01-01
status: DELIVERED_REPAIR_CANDIDATE
type: repair
chain_id: REGIME-RESEARCH-AUTONOMY-01
generation: 1
ownership: repair_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 修復 closed regime 研究治理中可造成資料洩漏、sealed reuse 與錯誤策略結論的阻塞缺口。
parent_candidate_sha: 5cc87798804a48046cd9698b901e2b1bc8995871
review_evidence_sha: e6bd85790b8873e1b4149bab1bb5afbe2fdcede1
reviewer_thread_id: 019fa2a2-2b0a-7df0-9a97-e100a9550776
evidence_path: docs/evidence/REPAIR-REGIME-RESEARCH-AUTONOMY-01-01/
---

# REPAIR-REGIME-RESEARCH-AUTONOMY-01-01

## 目的

只修正原 Reviewer 的八項 finding，讓 `NO_STRATEGY`、regime candidate 與 universal
candidate 都由完整 closed-mode 證據鏈推導。不得擴張到新研究題目、production
promotion 或參數暴力搜尋。

## 固定 Findings

### REG-R001（P1）完整交易窗 exact-match

ranking、entry、每個 holding bar、exit 必須屬於同一允許 episode；跨 regime／transition／
unknown 必須排除並 fail loud。baseline 與 candidate 共用相同 episode IDs。

### REG-R002（P1）Closed manager lifecycle 接線

closed-mode 真實入口必須建立 pre-registration、immutable episode split、sealed registry
與 append-only funnel transition；缺任一證據不得跳階。

### REG-R003（P1）真實 matrix multiple-testing 證據

真實 matrix row 必須接 deterministic `combination_id`、預註冊 correction family、
`p_value`、neighbor lineage／robustness 與 drawdown gate。證據未計算時回
`INSUFFICIENT_EVIDENCE/BLOCKED`，不得冒充完整評估後的 `NO_STRATEGY`。

### REG-R004（P1）Episode 日期互斥與 chronology

episode trade dates 必須非空、內部唯一、與 start/end 一致；跨 episode 日期集合互斥且
嚴格時間排序。overlap metadata 必須由實際驗證推導。

### REG-R005（P1）Canonical sealed reuse／stitching lineage

以 canonical sealed trade-date hash／dataset slice hash 防別名重用；component sources
必須存在 registry 且 hash 可追溯；fresh composition 日期不得與所有 source 重疊。

### REG-R006（P1）Universal gate fail closed

必要欄位缺失、required regime 缺少、sealed lineage 重複、固定 parameter hash 不一致、
independent emergence 或 transition forward shadow 缺失，一律 locked。

### REG-R007（P2）Topic eligibility

generate、queue、fallback、execute 全入口都要求 `eligible=true`；不合格只進 monitor／
coverage artifact。

### REG-R008（P2）Verifier 固定 candidate end-ref

新增 `--candidate`，固定 diff `base...candidate`，從 candidate tree 讀 production hashes；
review-only／untracked 檔不得改變 candidate verdict。

## Allowlist

- `app/modeling/sealed_oos.py`
- `scripts/run_autonomous_research.py`
- `scripts/run_backtest_strategy_matrix.py`
- `scripts/run_portfolio_replay.py`
- `scripts/verify_regime_research_autonomy.py`
- `config/regime_research_contract.json`
- `tests/test_regime_research_autonomy.py`
- 與上述真實入口直接相關的既有 autonomous research 測試
- `docs/evidence/REPAIR-REGIME-RESEARCH-AUTONOMY-01-01/**`
- 本卡狀態更新

超出 allowlist 或需要 production ranking／模型檔變更時立即停手。

## 禁止範圍

- 不改 production model、ranking、權重、promotion、API 或 UI。
- 不跑或宣稱已證明兩百萬參數來源。
- 不把缺證據改寫成策略失敗。
- 不 merge、push、deploy。
- 不修改 finding ID、severity 或原 Review verdict。

## 執行順序

1. 將 Reviewer 七組 adversarial fixtures 轉成 red tests，另補 closed manager CLI
   end-to-end red test。
2. 保存 red evidence，確認失敗精確映射 REG-R001..R008。
3. 以最小接線修復；不得只強化 verifier 文案。
4. 跑 targeted、affected suites、consolidated verifier、完整 pytest、production hash 與
   `git diff --check`。
5. 寫 repair evidence並提交唯一 Repair-1 candidate。

## 交付

- `DELIVERED_REPAIR_CANDIDATE`
- 完整 parent、review evidence、repair candidate SHA
- REG-R001..R008 red→green mapping
- 真實 closed manager trace 與 state transition evidence
- 測試／verifier／production hash 結果
- 剩餘資料與統計風險

交付後回原 Reviewer task re-review，不得自行接受或整合。

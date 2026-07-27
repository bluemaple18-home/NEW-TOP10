---
id: REPAIR-REGIME-RESEARCH-AUTONOMY-01-02
status: CARD_DRAFTED
type: repair
chain_id: REGIME-RESEARCH-AUTONOMY-01
generation: 2
ownership: repair_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 最後一次 bounded repair，關閉預註冊統計 family 與 universal exact-regime fail-open。
parent_repair_sha: 9f59aab69a70305d6afb4951ac7b97f176350f69
re_review_evidence_sha: 4c249aba3dd052b6a693773bb4606e3f5b8302d3
reviewer_thread_id: 019fa2a2-2b0a-7df0-9a97-e100a9550776
evidence_path: docs/evidence/REPAIR-REGIME-RESEARCH-AUTONOMY-01-02/
---

# REPAIR-REGIME-RESEARCH-AUTONOMY-01-02

## 目的

只關閉 `REG-R003-R1` 與 `REG-R006-R1`。其餘六項 finding 已由原 Reviewer 通過，
不得重開或擴張。

## REG-R003-R1：Pre-registered statistical family

- Pre-registration 保存本次實際測試的 immutable combination IDs、correction family ID、
  partition policy 與 hash。
- Matrix／gate 必須接收 expected family 並逐項比對。
- 完整 720 universe 若只跑 profile 子集，必須由 registration 明確允許 partition，且仍
  遵守全域 correction policy；不得事後以 rows 自算較小 family。
- 統計單位以獨立 episode／cluster 聚合；相同、重疊或 alias trades 不得當作獨立樣本。
- family mismatch、pseudo-replication 或證據未完成時回
  `INSUFFICIENT_EVIDENCE/BLOCKED`。

## REG-R006-R1：Contract-derived universal gate

- `universe_declared_complete` 由 immutable contract／coverage artifact 推導，不信任
  candidate payload。
- Contract `declared_complete=false` 或 inventory blocked 時，universal 必須無條件 locked。
- required exact identities 必須與 base＋family tag policy 一致。
- 若不是完整笛卡兒積，contract 必須提供可稽核合法 identity rules 與完整 required set。
- 所有實際研究過的 tagged exact identities 必須納入 required coverage。

## Allowlist

- `scripts/run_autonomous_research.py`
- `scripts/run_backtest_strategy_matrix.py`
- `config/regime_research_contract.json`
- `tests/test_regime_research_autonomy.py`
- 與 statistical family／universal gate 直接相關的最小既有測試
- `docs/evidence/REPAIR-REGIME-RESEARCH-AUTONOMY-01-02/**`
- 本卡狀態更新

## 禁止範圍

- 不修改已通過的 REG-R001/R002/R004/R005/R007/R008 行為。
- 不改 production model、ranking、權重、promotion、API 或 UI。
- 不 merge、push、deploy。
- 若最終 re-review 仍 NO_GO，進入 `BLOCKED / REVIEW_REPAIR_LIMIT`；不得建立 Repair-3。

## 執行順序

1. 先建立兩組 public-path adversarial red tests：
   - registration/matrix family mismatch＋重複 trade pseudo-replication。
   - contract incomplete＋tagged exact identity coverage 缺口。
2. 保存 red evidence。
3. 做最小真實入口修復，不得只改 verifier。
4. 重跑 targeted／affected／public CLI trace／verifier／full suite／production hashes／
   `git diff --check`。
5. 寫 Repair-2 evidence並提交唯一 candidate。

## 交付

- `DELIVERED_REPAIR_CANDIDATE`
- 完整 parent／re-review／Repair-2 SHA
- 兩項 red→green 與 public CLI evidence
- 其餘六項 no-regression
- 測試／verifier／production hash 結果

完成後回原 Reviewer最終 re-review，不自行接受或整合。

---
id: REVIEW-FOG-RECOVERY-01
chain_id: FOG-RECOVERY-01
status: READY_FOR_REVIEW
type: review
owner: independent-review-thread
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 多檔 correctness／race／shell recovery 審查，範圍固定且不需 strict 架構決策。
base_sha: 605ad284718cb8b9cae1ab94a8938b3dd8c7f044
candidate_sha: 58ff3467426b4ec01386a6ad14cd38c8950b601b
---

# REVIEW-FOG-RECOVERY-01

## Review scope

只審查 `605ad284718cb8b9cae1ab94a8938b3dd8c7f044..58ff3467426b4ec01386a6ad14cd38c8950b601b`：

- `scripts/build_weekend_universe_inventory.py`
- `scripts/run_fog_research_worker.sh`
- `tests/test_weekend_universe_inventory_snapshot.py`
- `tests/test_fog_research_retry_circuit.sh`
- `docs/evidence/FOG-RECOVERY-01/**`

## Spec axis

- inventory build 遇到 source snapshot 前進時，只能 bounded 重取；仍不一致必須 fail-loud。
- controlled-grid／inventory verifier 必須維持 fail-closed。
- retry circuit 預設不可自動解除；只有明確 recovery mode 且 blocker verifier 通過後才能輪替舊 state/context。
- 新 failure fingerprint 不得被舊 recovery 流程吞掉。
- 不得碰 production ranking、模型、權重或 promotion。

## Standards axis

- race 與 shell recovery 測試必須觸及 public/observable behavior。
- 不接受固定 sleep、無限 retry、刪除 evidence、TOCTOU 擴大或本機絕對路徑寫進共享契約。
- 檢查 correctness、regression、security/path safety、performance、maintainability 與 test gap。

## Reviewer 輸出

寫入 `docs/evidence/REVIEW-FOG-RECOVERY-01/review.md`：

- `verdict: REVIEW_GO | REVIEW_NO_GO`
- `reviewed_commit`
- findings（若有）：固定 finding ID、severity、`path:line`、觸發條件、證據、修復驗收條件
- 已跑驗證、未跑項目與剩餘風險

Review 預設 read-only；只允許新增 review evidence 與原子 review commit，不得修改 candidate code、merge、push、清除 circuit 或執行 production recovery。

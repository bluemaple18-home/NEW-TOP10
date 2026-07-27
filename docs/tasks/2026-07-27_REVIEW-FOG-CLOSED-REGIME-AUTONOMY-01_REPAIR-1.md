---
id: REVIEW-FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1
status: READY_TO_DISPATCH
type: review
chain_id: FOG-CLOSED-REGIME-AUTONOMY-01
review_generation: 1
ownership: independent_reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
base_sha: 5e1de6aa170f7c2446e5da76fadfa75a88495e54
reviewed_candidate_sha: 394b90feae0a5c11a75a578ea4e721b44bb3893d
implementation_thread_id: 019fa3f1-a072-73f3-8ede-bc24a0756932
evidence_path: docs/evidence/REVIEW-FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1/
---

# REVIEW-FOG-CLOSED-REGIME-AUTONOMY-01 Repair-1

## Review question

Repair candidate `394b90feae0a5c11a75a578ea4e721b44bb3893d` 是否封閉三個
verifier trust-boundary P1，且未破壞 closed-regime public path、queue/circuit safety
或 production boundary？

## Fixed boundary

- Base：`5e1de6aa170f7c2446e5da76fadfa75a88495e54`
- Candidate：`394b90feae0a5c11a75a578ea4e721b44bb3893d`
- Repair card：
  `docs/tasks/2026-07-27_FOG-CLOSED-REGIME-AUTONOMY-01_REPAIR-1_verifier_trust_boundaries.md`
- Repair evidence：
  `docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1/`

Reviewer 只可新增本卡 review evidence／狀態，不得修改 candidate、merge、push、
kickstart、輪替 live state或執行 acceptance。

## 必須獨立攻擊

1. 以 forged ID 取代 inventory 的一個 processed ID；必須 fail closed，且
   `map_only`／`inventory_only` 正確。
2. 以錯日期、偽 identity、缺 `state_transition`、未知欄位及 artifact hash drift
   攻擊 runtime receipt；均不得取得 `COMPLETED`／recovery approval。
3. 建立 trusted production baseline 後修改 model fixture，並分別攻擊 missing
   role、path-set drift、source identity drift；均須拒絕。

Reviewer 必須檢查 authority 是否真的來自兩個獨立 artifact、baseline 是否能被待驗
runtime 同步重寫，以及 shell wiring 是否在 recovery 前建立可信 baseline。

## Verification

```bash
cd <repo-root>
.venv/bin/python -m pytest -q \
  tests/test_weekend_universe_inventory_snapshot.py \
  tests/test_daily_research_quota_verifier.py \
  tests/test_fog_closed_regime_runtime.py
bash tests/test_fog_research_retry_circuit.sh
bash tests/test_research_lock_contention.sh
bash -n scripts/run_daily_research_quota.sh
bash -n scripts/run_fog_research_worker.sh
.venv/bin/python -m pytest -q
git diff --check 5e1de6aa170f7c2446e5da76fadfa75a88495e54..394b90feae0a5c11a75a578ea4e721b44bb3893d
```

若 isolated worktree 缺少 gitignored historical evidence，可使用主 repo 既有檔案建立
read-only 暫時 symlink；測試後必須移除並記錄，不得把該 provisioning 當 candidate
功能。

## Verdict

- `GO_FOR_MAINLINE_RUNTIME_ACCEPTANCE`：三個 P1 均關閉、無新增 P0/P1、production
  protected artifacts unchanged。只代表可進主線整合與 live acceptance。
- `NO_GO`：列 findings、重現證據與 validation gap；進 Repair-2。

Review evidence：
`docs/evidence/REVIEW-FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1/review.md`。

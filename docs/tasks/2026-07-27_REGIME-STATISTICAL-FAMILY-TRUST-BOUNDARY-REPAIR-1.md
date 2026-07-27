---
id: REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-1
status: CARD_DRAFTED
type: repair
chain_id: REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01
generation: 1
ownership: repair_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 修補 public research CLI 可接受偽造 dataset／split lineage 的高風險信任邊界。
base_candidate_sha: 47cd110f17ce0f008de86156820d83436d1072dd
review_evidence_sha: e4a801c773739cd7a2e121c245c692980e38d3b7
reviewer_thread_id: 019fa367-851b-7402-bec7-6b11b68249de
evidence_path: docs/evidence/REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-1/
---

# REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-1

## 目的

修補 `F-01`：public matrix CLI 目前只驗證 registration 自洽與 development IDs，
未將 dataset hash、split artifact 與 validation／embargo／sealed IDs 重新綁回 runtime
可信輸入，因此可接受重新 content-address 的 forged lineage。

## 固定來源

- Repair base：`47cd110f17ce0f008de86156820d83436d1072dd`
- Review evidence：`e4a801c773739cd7a2e121c245c692980e38d3b7`
- 原 Reviewer：`019fa367-851b-7402-bec7-6b11b68249de`
- Finding：`F-01`

## Phase 0：Red baseline

先新增 public-path 測試，建立一份 registry hash 正確但下列 lineage 偽造的 registration：

- `dataset_hash`
- `split_id`
- `split_artifact_hash`
- `episode_split_ids_hash`
- validation／embargo／sealed episode IDs

測試須先證明原 candidate 會以 return code 0 接受，再開始改碼。

## 必做修復

1. Public CLI 從可信 runtime history 與 immutable split artifact（或 manager 等價 authority）
   重算完整 lineage，不得把 registration 內 lineage 當作真相。
2. 逐欄比對 dataset hash、split artifact hash、split ID、development／validation／embargo／
   sealed episode IDs 與 `episode_split_ids_hash`。
3. 任一不符 fail closed，輸出穩定、可測試的 reason code。
4. 合法 `81/720` public CLI、`242/720` coverage 與 available-data canary 行為不變。
5. Production model、ranking、權重、promotion hashes 不變。

## Allowlist

- `scripts/run_autonomous_research.py`
- `scripts/run_backtest_strategy_matrix.py`
- `scripts/verify_regime_research_autonomy.py`
- `scripts/run_regime_statistical_family_canaries.py`
- `tests/test_regime_research_autonomy.py`
- `docs/evidence/REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-REPAIR-1/**`
- 本卡狀態更新

## 禁止範圍

- 不修改模型、ranking、權重、promotion、API、UI。
- 不降低 720 family、alpha、episode 或 sealed gate。
- 不改寫原 Review evidence。
- 不 merge、push、deploy、自行 acceptance。

## 驗證

```bash
cd <repo-root>
.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py
.venv/bin/python scripts/verify_regime_research_autonomy.py \
  --base 47cd110f17ce0f008de86156820d83436d1072dd \
  --candidate <repair-candidate-sha>
.venv/bin/python -m pytest -q
git diff --check
```

另需重跑四個 canary 與 forged-lineage public-path attack，保存命令、hash、return code、
reason code、counts、state trace 與 production hashes。

## Worktree pre-dispatch receipt

- Main cwd：`<repo-root>`
- Repair worktree：`/private/tmp/top10new-regime-statistical-family-trust-boundary-repair-1`
- Branch：`codex/regime-statistical-family-trust-boundary-repair-1`
- Source kind：`commit`
- Source SHA：`47cd110f17ce0f008de86156820d83436d1072dd`
- Source clean：是
- Git metadata：preflight 可建立 branch/worktree
- `index.lock`：不存在
- unrelated dirty paths：`[]`
- Workflow：`REVIEW_NO_GO → REPAIR_READY → READY_FOR_REVIEW`
- Gate 1：由本卡實體契約與固定 finding 成立
- Gate 2：正式 thread 建立後回寫 receipt
- Gate 3：需完整 candidate SHA、completed turn、error null 與 evidence
- Gate 4：由原 Reviewer 複審
- Gate 5：主線另行 acceptance

## 交付

- `DELIVERED_CANDIDATE`
- 完整 repair candidate SHA
- Red→green evidence
- forged-lineage attack 修復後 fail-closed receipt
- targeted／verifier／full-suite／四 canary 結果
- production hashes unchanged
- 交回同一 Reviewer task 複審

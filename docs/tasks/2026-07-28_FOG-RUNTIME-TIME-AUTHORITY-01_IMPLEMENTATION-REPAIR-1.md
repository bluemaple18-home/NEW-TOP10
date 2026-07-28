---
id: FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-REPAIR-1
chain_id: FOG-RUNTIME-TIME-AUTHORITY-01
status: READY_FOR_REPAIR
type: repair
ownership: reusable_implementation_repair
repair_generation: 1
max_repair_generation: 2
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
base_candidate_sha: f7d51a3d994707c819198fd1edcdcf0db4dd0775
review_sha: 15a87e5
reviewer_thread_id: 019fa66b-444f-7522-915b-15aad3de5fe3
repair_thread_id: PENDING
---

# FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-REPAIR-1

## Goal

只修復 Implementation Review 的三個固定 finding：

- `FRTA-IMPL-P1-01`
- `FRTA-IMPL-P1-02`
- `FRTA-IMPL-P2-03`

不得重寫 architecture、擴張 I5、重新設計 ranking／model／promotion或順手整理
無關程式。Repair只交修復 candidate，回原 Reviewer re-review。

## Authority與lineage

- Base implementation candidate：
  `f7d51a3d994707c819198fd1edcdcf0db4dd0775`
- Blocking Review：
  `15a87e5`
- Review evidence：
  `docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/`
- Reusable Reviewer：
  `019fa66b-444f-7522-915b-15aad3de5fe3`

Repair worktree必須從包含 `15a87e5` 的 review lineage開始，使 hostile probe與
finding text可直接重現；不得修改或弱化 Reviewer probe。

## Finding closure

### `FRTA-IMPL-P1-01`：repo-owned source／baseline authority

必須：

- 在 repo-owned versioned config固定 research-map／inventory artifact path、
  各自 source role/path set、canonical baseline path與 source identity。
- production verifier從 repo config載入 expected authority，不接受 caller自選
  mapping、baseline path或 source identity。
- 若保留 legacy CLI flags，只能與 repo authority exact compare；缺少、額外、
  role/path swap、path escape、symlink escape、hash drift全部 fail closed。
- baseline不得由 recovery invocation同步生成後自我認證；verifier只讀既定
  baseline並驗其 canonical identity/hash。

Exit：

- Reviewer hostile probe中的
  `self_reported_distinct_sources_rejected=true`；
- `self_reported_baseline_rejected=true`；
- legitimate repo-owned control仍通過。

### `FRTA-IMPL-P1-02`：missing daily lineage fail closed

必須：

- daily artifact只能從明定欄位／lineage object取得 `daily_source_date`。
- 完全缺少 daily source lineage時 producer立即
  `DAILY_ARTIFACT_SCHEMA_REJECT`。
- 禁止以 regime/source trade date、run date或 host date補值。
- producer與 independent verifier各自有 missing-lineage regression。

Exit：

- Reviewer hostile probe中的
  `missing_daily_source_rejected=true`；
- 明示合法休市日 lineage仍通過。

### `FRTA-IMPL-P2-03`：bounded context lifecycle

必須：

- context只存在於本 invocation所需期間；
- child與receipt流程完成或中途失敗後，由精確 trap cleanup自己的 context；
- 不刪其他 invocation context、不擴大 queue owner、不採用 unbounded glob；
- 若選 retention，必須有明確上限與測試；預設優先精確 cleanup。

Exit：

- success與failure path都無本 invocation context殘留；
- concurrent／foreign context不被刪除。

## Changed-file allowlist

Production/config：

- `config/fog_runtime_time_authority_v1.json`
- `scripts/fog_authority_contracts.py`
- `scripts/verify_processed_id_authority.py`
- `scripts/verify_fog_closed_regime_recovery.py`
- `scripts/verify_closed_regime_runtime.py`
- `scripts/run_fog_research_worker.sh`

Tests：

- `tests/test_fog_closed_regime_runtime.py`
- `tests/test_fog_runtime_time_authority.py`
- `tests/test_fog_research_retry_circuit.sh`

Evidence/card：

- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-REPAIR-1/**`
- 本卡

Read-only：

- `docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/**`
- accepted architecture/schema
- original Implementation evidence

需要 allowlist外檔案時立即停止回報，不得自行擴張。

## Phase 0與verification

修改 production code前：

1. 重跑 Reviewer hostile probe並保存三個 fail-open RED。
2. 保存 protected hashes與exact changed-file baseline。
3. 先新增 public-behavior regression，確認 RED原因不是 missing module。

完成後至少跑：

```bash
cd <repo-root>
.venv/bin/python \
  docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/hostile_probe.py
.venv/bin/python -m pytest -q \
  tests/test_fog_runtime_time_authority.py \
  tests/test_fog_closed_regime_runtime.py \
  tests/test_daily_research_quota_verifier.py
bash tests/test_fog_research_retry_circuit.sh
bash tests/test_fog_runtime_time_wiring.sh
bash -n scripts/run_fog_research_worker.sh
bash -n scripts/run_daily_research_quota.sh
plutil -lint scripts/com.new-top10.fog-research-worker.plist
.venv/bin/python -m pytest -q
git diff --check
```

另驗證：

- exact allowlist；
- Reviewer probe不得修改且 exit `0`；
- protected hashes before／after一致；
- architecture/schema與原 evidence無 diff；
- 無 secret、本機絕對路徑、debug marker、TODO／FIXME；
- worktree commit後 clean。

## Forbidden

- 不修改或刪除 Reviewer hostile probe／finding。
- 不以 test-only special case、relax assertion或 stored PASS關閉 finding。
- 不操作 live LaunchAgent、queue、retry/circuit state、production artifacts。
- 不 merge、push、deploy、建立新 Reviewer／Repair／Implementation卡。
- 不執行 I5或宣稱 Review GO／mainline acceptance。

## Delivery

- Repair只交 `DELIVERED_REPAIR_CANDIDATE`與完整 SHA。
- 完成後回同一 Reviewer
  `019fa66b-444f-7522-915b-15aad3de5fe3` targeted re-review。
- 若仍 NO_GO，重用同一 Repair task執行 Repair-2；Repair-2為最後一輪。

## Dispatch receipt

- Dispatcher task：`019f82c1-b7d0-7eb3-9371-7a95ebfbd7ce`
- Review verdict：`REVIEW_NO_GO`
- Review commit：`15a87e5`
- Repair task：`PENDING`
- Gate 1 physical card：`PASS`
- Gate 2 visible thread：`PENDING`
- Gate 3 Repair candidate：`PENDING`


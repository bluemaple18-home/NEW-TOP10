---
id: CARD-NEW-TOP10-BATCH-OWNER-INTEGRATION-AND-ISOLATED-CANARY-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: integration_and_acceptance
priority: P1
owner: TOP10new research platform
role: implementer
cycle: 1
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
date: 2026-08-14
production_change_allowed: false
live_activation_allowed: false
---

# Batch Owner Integration and Isolated Native Evidence Canary V1

## 工作名稱

整合可信 Batch Owner，完成隔離原生證據閉環。

## 固定輸入

- Main baseline：本卡提交後的 `main` HEAD。
- Reviewed implementation：`5df1fce0ef7426e804a9b0c6cc819b18cf51f3c3`
- Reviewed repair：`d7daea870ff3c2afc737358981b60507b254955d`
- Reviewer task：`019fff37-cb09-7403-bf98-332c37eeb8c5`
- Final verdict：`GO`
- Closed finding：`P1-FORGED-BATCH-INTENT-SCHEDULER-OWNER`

## 目標

1. 將已審核 Batch Owner commits 以可追溯方式整合進目前主線，不覆蓋使用者既有 dirty files。
2. 重跑完整受影響 gates。
3. 使用完全隔離的 tmp output/spine/ledger/manager root，證明單次 native development evidence 可形成：

```text
Batch Intent → Runner → Receipt → Observation → Eligibility
```

4. 本卡不得啟用 live daily、scheduler deployment或 Adaptive Queue。

## Slice

### `BOI-001`｜Integration provenance

`traces_to`: `BATCH-OWNER-FR-001..006`

- 開始前記錄 main HEAD、dirty path set與hash。
- 只整合 `5df1fce` 與 `d7daea8` 的功能變更；若 card commit已存在不得重複。
- 衝突時 fail closed，不得覆蓋使用者修改。
- 整合後 production-sensitive path diff必須為0。

### `BOI-002`｜Post-integration regression

`traces_to`: `BATCH-OWNER-FR-003..006`

- 重跑 11 targeted、17 receipt/cutover regression。
- 重跑 compile、`bash -n`、`git diff --check`。
- `tests/test_native_evidence_activation.py` 的 `AUTONOMOUS_NEXT_ACTION_QUEUE` 缺失須保留 PRE-EXISTING 分類；不得補造正式 artifact。

### `BOI-003`｜Isolated native evidence canary

`traces_to`: `NEA activation GO gate`, `Observation Eligibility Contract`

- 使用 `mktemp -d` 或 pytest tmp root。
- output、spine、CAS、ledger、manager/history、logs、matrix/comparison全部 resolve 在同一隔離 root。
- 只允許 `DEVELOPMENT_SCREEN` 與明確 non-sealed authority；`UNSCOPED`、sealed、validation、embargo一律拒絕。
- 可 stub昂貴 backtest計算，但不得 stub Batch Intent、Receipt、matrix authority、ledger ingestion或eligibility判斷。
- 需產 1 intent、1 attempt、1 terminal receipt；requested/executed exact match。
- receipt 必須 `SUCCEEDED / OBSERVED / EXACT`；units 必須 `VALID / PROVEN_NON_SEALED`。
- ingest後 observations數等於 executed units；第二次 ingest不增加。
- eligibility必須 `ADAPTIVE_ELIGIBLE`；sealed/unknown對照仍0 eligible。
- canary前後 canonical Research Spine、正式 ledger、manager/history、production files path set與hash完全不變。

## Blocking edges

- Frontier：`BOI-001`。
- `BOI-002` blocked by successful conflict-free integration。
- `BOI-003` blocked by all BOI-002 gates PASS。
- 任一 canonical write、lineage UNKNOWN、identity mismatch、capacity unknown即停止；不得 fallback成 live。

## Required verification

```bash
uv run pytest -q tests/test_research_batch_owner.py tests/test_daily_research_batch_owner_shell.py
uv run pytest -q tests/test_autonomous_research_receipts.py tests/test_research_spine_daily_cutover.py
uv run pytest -q <isolated native evidence canary tests>
uv run python -m py_compile app/research/batch_owner.py scripts/publish_research_batch_intent.py scripts/run_autonomous_research.py
bash -n scripts/run_daily_research_quota.sh
git diff --check
```

## Acceptance

- Reviewed Batch Owner code已進整合 candidate。
- 使用者 dirty files內容與hash不變。
- Reviewer GO反例仍全部 fail closed。
- 隔離 canary閉環成功且 idempotent。
- Canonical/production pre/post inventory完全一致。
- 不部署、不push、不啟用live、不建立第二scheduler。
- 完成後提交單一 integration candidate，再交原 Reviewer task final integration review。

## Rollback

捨棄 integration candidate；主線、正式 artifacts、ledger、scheduler、production保持原狀。隔離 tmp可回收，不刪 immutable正式 corpus。

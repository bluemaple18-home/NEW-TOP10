---
id: REVIEW-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: code-review
priority: P1
role: review
cycle: 13
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 固定高風險 evidence runner candidate，需獨立核對 fail-closed、receipt 與分類一致性。
date: 2026-08-15
base_sha: aff48f782cd178657baef7c44ead3dc991b10ed2
candidate_sha: 9008901b84010253064bb468b904b4b427f5071e
production_change_allowed: false
candidate_code_change_allowed: false
---

# 審查隔離 Shadow Plan Replay

## 固定範圍

- Base：`aff48f782cd178657baef7c44ead3dc991b10ed2`
- Candidate：`9008901b84010253064bb468b904b4b427f5071e`
- 唯讀審查固定 diff；不得修檔、merge、push、deploy、scheduler、canonical queue 或 production。

## Spec axis

1. 只接受 authoritative committed proposal，矩陣固定為 baseline／candidate × horizons `{10,20}`。
2. 正式 runner、batch owner、correlation、attempt、argv、return code 與 immutable receipt 必須可稽核。
3. 四 units 全部合格才可形成比較；資料不足必須 structured `NO-GO`，不得包裝為正向 evidence。
4. `result.json`、`final_result.json`、CLI verifier 與 post-verification 對 status、reason、classification 必須一致且不可偽造。
5. 容量不超過 64 MiB／250 files；canonical queue、scheduler、production 前後零變更。

## Standards axis

- correctness：zero-unit、partial matrix、classification、receipt binding、exception path。
- regression：既有 research contracts、formal runner、ingest 與 CLI 相容。
- security/path：proposal/evidence/isolated root traversal、symlink、shared-root write。
- performance/storage：最多 4 units，輸入、檔案與 bytes 有界。
- test gap：tampered final/result、分類矛盾、receipt mismatch、capacity/parity 負向案例。

## 已知審查提示

- 主線觀察到 committed `result.json` 在 `unit_count=0` 時為 `classification=MIXED_LINEAGES`，但 `final_result.json` 為 `NO_COMPARISON`；請獨立判定嚴重度與是否違反 evidence contract，不沿用主線結論。

## 必做驗證

```bash
git diff --check aff48f782cd178657baef7c44ead3dc991b10ed2 9008901b84010253064bb468b904b4b427f5071e
<repo-root>/.venv/bin/pytest -q tests/test_isolated_shadow_plan_replay.py
PYTHONPYCACHEPREFIX=/tmp/card_d_review_pycache <repo-root>/.venv/bin/python -m py_compile app/research/isolated_shadow_plan_replay.py tests/test_isolated_shadow_plan_replay.py
<repo-root>/.venv/bin/python -m app.research.isolated_shadow_plan_replay --verify docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/result.json
<repo-root>/.venv/bin/python -m app.research.isolated_shadow_plan_replay --verify docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/final_result.json
```

- 獨立重算 plan／receipt identity，核對禁止路徑 diff 為空。
- 反證 zero-unit 卻宣稱比較、tampered reason/classification 與 receipt mismatch。

## Verdict

- P0／P1、evidence 可錯標或 verifier 可放過契約矛盾：`CHANGES_REQUIRED`。
- 無阻塞 finding：`APPROVED`，P2／P3 僅列 residual risk。

---
card_id: FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1
evidence_kind: implementation_candidate_verification
status: CANDIDATE_VERIFIED
scope: I1-I4
i5: NOT_RUN_OUT_OF_SCOPE
---

# Implementation candidate verification

## Root question

是否以合法 accepted mainline base clean-room完成 I1–I4，且四個固定
`FRTA-REG-*` public behaviors均由 RED 轉 GREEN、protected surface unchanged，
可交付獨立 Implementation Review？

## Clean-room lineage

- starting HEAD：
  `87e4da7dd63bafe82b16c28990e7be6db137b4e6`
- accepted mainline parent：
  `408f3e0cced14bca451503cc35f845b403f72822`
- accepted architecture candidate：
  `f9cfbabde1d89d2f759a7cbc60d1dd03e96a2171`
- targeted architecture Review：
  `5c95a2e2858e0a214d5680cbd2fac147e5cad893`
- rejected `acd835df3a4fe40a149333dca0b55e62cc8eded9`：
  non-ancestor only；未 merge、cherry-pick、copy patch或採用 stored PASS
- CodeGraph：worktree無 index，未建立 allowlist外 `.codegraph`；唯讀 `rg`
  fallback完成現況與 diff確認

## RED → GREEN ledger

RED evidence：
`docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/phase0.md`。

| Regression ID | RED | GREEN public behavior |
|---|---|---|
| `FRTA-REG-RRV-P1-01-PROCESSED-ID` | missing authority module | forged／missing symmetric difference、同源 artifacts、source hash drift均 fail closed |
| `FRTA-REG-RRV-P1-03-SOURCE-BASELINE` | missing authority module | fixed five-role path set、legitimate control、self-reported alternate paths與 post-baseline hash drift |
| `FRTA-REG-RECEIPT-V3-EXACT` | missing verifier module | missing／unknown／type／v2 relabel／forged lineage均 reject |
| `FRTA-REG-TIME-DATE-LINEAGE` | missing time module | Taipei UTC日界、合法休市日、wrong/future source與 artifact drift deterministic |

## Slice evidence

- Checkpoint A：
  `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/checkpoint-a.md`
- Checkpoint B：
  `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/checkpoint-b.md`
- canonical time contract hash：
  `67327c40206251adf4d377e76833dfd6261ce4fb3f56c7de0b0bf92c7231e357`
- producer與 verifier schema authority：
  `docs/architecture/fog_runtime_receipt_v3.schema.json`
- architecture/schema diff：none

## Required verification

Targeted：

```text
32 passed in 0.10s
```

Commands：

```bash
.venv/bin/python -m pytest -q \
  tests/test_fog_runtime_time_authority.py \
  tests/test_fog_closed_regime_runtime.py \
  tests/test_daily_research_quota_verifier.py
bash tests/test_fog_research_retry_circuit.sh
bash tests/test_fog_runtime_time_wiring.sh
bash -n scripts/run_fog_research_worker.sh
bash -n scripts/run_daily_research_quota.sh
plutil -lint scripts/com.new-top10.fog-research-worker.plist
```

Result：all PASS；plist `OK`。

Final-tree full suite：

```text
565 passed, 4 warnings, 246 subtests passed in 67.98s
```

Full suite 首跑只有既有 `research_component_ledger` historical evidence缺檔：
`564 passed, 1 failed, 246 subtests passed`。依前鏈已記錄的 provisioning方式，
final run暫掛 main repo既有12個 read-only evidence/reference symlinks；完成後逐一
移除。Candidate未新增或修改該 historical evidence，cleanup後 symlink檢查通過。

## Exact changed-file allowlist

```text
config/fog_runtime_time_authority_v1.json
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/checkpoint-a.md
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/checkpoint-b.md
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/phase0.md
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/verification.md
docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_IMPLEMENTATION-1_clean_room_runtime.md
scripts/fog_authority_contracts.py
scripts/fog_runtime_time_authority.py
scripts/run_daily_research_quota.sh
scripts/run_fog_research_worker.sh
scripts/verify_closed_regime_runtime.py
scripts/verify_daily_research_quota.py
scripts/verify_fog_closed_regime_recovery.py
scripts/verify_processed_id_authority.py
tests/test_daily_research_quota_verifier.py
tests/test_fog_closed_regime_runtime.py
tests/test_fog_research_retry_circuit.sh
tests/test_fog_runtime_time_authority.py
tests/test_fog_runtime_time_wiring.sh
```

All paths位於 implementation card exact allowlist。

## Protected hashes與hygiene

- protected tracked path inventory：model／ranking／weight／baseline／promotion
- before aggregate：
  `2aa2345f567d982634a1cf7a770cea96a77f0d8e3d5d9bd16b211e7abe75d126`
- after aggregate：
  `2aa2345f567d982634a1cf7a770cea96a77f0d8e3d5d9bd16b211e7abe75d126`
- protected byte identity：PASS
- `git diff --check`：PASS
- architecture/schema read-only：PASS
- secret／本機絕對路徑／debug marker／TODO／FIXME scan：production/test code
  無命中；docs只有本卡既有 checklist與本 evidence文字
- worker/daily `date +%F` authority fallback scan：PASS（不存在）

## Boundary

- LaunchAgent reload／kickstart／install：NOT RUN
- live queue／retry circuit／scheduler mutation：NOT RUN
- model／ranking／weights／baseline／promotion mutation：NONE
- merge／push／deploy：NOT RUN
- I5 migration／三輪 acceptance：NOT RUN / OUT OF SCOPE

## Candidate status

```text
status: DELIVERED_IMPLEMENTATION_CANDIDATE
acceptance_mapping: I1-I4 verified; four FRTA-REG IDs RED→GREEN
missing_evidence: independent Implementation Review; I5 live acceptance
remaining_risk: candidate 尚未經新的唯一 Implementation Reviewer固定SHA重驗
next_step: dispatch this exact candidate commit to independent Implementation Review
limits: 不宣稱 GO、ACCEPTED、production ready或可 deploy
```

---
id: REPAIR-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: repair
priority: P1
role: repair
cycle: 8
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
date: 2026-08-15
source_sha: 160823387689d3a5e557e7f004dbb46b6977d7eb
review_sha: 1f057bbda35fc3c87b38ae5b2f69898714d6bc5b
production_change_allowed: false
evidence_path: docs/evidence/REPAIR-NEW-TOP10-NATIVE-EVIDENCE-REPLAY-BUNDLE-V1/
---

# 修復 Native Evidence Replay Bundle 審查缺陷

## 目標

關閉 Reviewer 對 `1608233` 提出的兩個 P1，維持既有 replay counts、manifest hash、capacity、cleanup 與 canonical parity。

## 固定 Findings

### P1-VERIFIER-DEVELOPMENT-BOUNDARY-BYPASS

- `verify_bundle()` 目前接受 observation stage 改為 `COARSE_SCREEN` 後重算 `bundle_id` 的 bundle。
- 它也接受 `boundary.development_only=false`、`production_promotion_allowed=true`。
- 必須檢查並鎖死 replay 的 exact development-only boundary；stage／boundary 要進入可驗證語意。

### P1-OUTPUT-DIR-WRITE-BEFORE-BOUNDARY

- `--output-dir` 指到 repo 外時，CLI 先寫 `bundle.json`，再於 `relative_to(PROJECT_ROOT)` 崩潰。
- 必須在跑 cycles、mkdir 或任何寫入前驗證路徑；非法路徑要 controlled fail-closed 且零寫入。

## Allowlist

- `app/research/native_evidence_replay.py`
- `scripts/native_evidence_replay_bundle.py`
- `tests/test_native_evidence_replay.py`
- 本任務卡與 repair evidence。

不得修改 committed replay bundle／manifest、canonical queue、main ledger、scheduler、ranking、model、signals、promotion或 production config。

## 驗收

1. 原 committed bundle verifier 仍 PASS，counts 維持 cycles=2、units／observations／eligible=8、lineages／contrasts=4。
2. `COARSE_SCREEN`、mixed stage、production boundary tamper 即使重算 `bundle_id` 仍 FAIL。
3. repo 外絕對路徑與 traversal output dir 在任何 side effect 前 FAIL；目標路徑不存在或保持空白。
4. 合法 repo 內 evidence path 仍可重跑，capacity／cleanup／parity皆 PASS。
5. focused tests、isolated canary、CLI help、py_compile、`git diff --check` 全綠。
6. 既有 activation suite 缺 `next_action_queue.json` 僅記 PRE-EXISTING，不得補造。

## 邊界

- 不 merge、push、deploy、啟 scheduler、live或 production write。
- 完成後提交單一 repair candidate SHA，交回同一 Reviewer thread targeted re-review。

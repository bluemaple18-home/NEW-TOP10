---
card_id: REVIEW-TSKG-MFO-01
chain_id: TSKG-MFO
title: Independent SecurityFlowObservation contract review
status: REVIEWED_NO_GO
type: review
owner: Codex 主線
assignee: independent visible review task
created_on: 2026-07-20
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 跨 schema、fixture、validator、tests 與既有 TSKG regression，但候選與禁區已固定，適合標準獨立 code review
source_kind: commit
source_sha: 11c68e9c32812a394788c95bc69a8763a92a8929
source_base_sha: 13349cc9ee038a2577d763f4f0c0390c182d734f
source_branch: codex/tskg-mfo-01
mainline_dispatcher: current TSKG root task
previous_card: TSKG-MFO-01
previous_worktree: platform-independent-worktree
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
operation_level: local_read_only_plus_review_evidence
evidence_path: docs/evidence/REVIEW-TSKG-MFO-01/review.md
---

# REVIEW-TSKG-MFO-01

## Goal

獨立審查候選 `11c68e9c32812a394788c95bc69a8763a92a8929` 相對基線 `13349cc9ee038a2577d763f4f0c0390c182d734f`，判定 raw `SecurityFlowObservation` contract 是否可整合。

Review 只判定，不修改候選 implementation、fixture、tests 或原 MFO-01 evidence。

## Review scope

- `app/tskg/flow_observation.py`
- `app/tskg/__init__.py`
- `data/fixtures/tskg/security_flow_observations_v1.json`
- `tests/test_tskg_mfo01.py`
- `docs/tasks/2026-07-20_TSKG-MFO-01_security_flow_observation_contract.md`
- `docs/evidence/TSKG-MFO-01/verification.md`
- lineage commits `0e955dc..11c68e9`

Reviewer 唯一可寫：

- `docs/evidence/REVIEW-TSKG-MFO-01/review.md`
- 本 Review 卡的 `status`／`Result`

## Required review axes

### Spec axis

1. Observation 與 `RelationshipClaim`／canonical graph fact 分離。
2. MFO-01 只接受 raw single-day observation；沒有 5d/20d、price、acceleration、force、anomaly、Theme aggregation 或預測欄位。
3. closed schema、version、TWD integer、date/UTC、semantic key、provenance/evidence、freshness gate 可 fail loud。
4. deterministic order、exact lookup、defensive copy、summary 行為符合卡片。
5. synthetic fixture 不暗示真實市場資料、source approval 或外部 ingestion。

### Standards axis

1. malformed JSON 不漏出非契約例外；特別重驗 unhashable/list/dict/null/bool 邊界。
2. duplicate ID/key、dangling source/evidence、timestamp ordering 與 freshness coherence 測試充分。
3. `app.tskg` public exports 無既有相容性回歸。
4. 無 secret、本機絕對路徑、外部存取、API/UI/Top10/runtime/dependency 變更。
5. `git diff --check`、exact allowlist 與既有 46-test regression 可重現。
6. Python 3.13 未執行必須保留為 caveat；不得把 Python 3.11 clean run 冒充 3.13 acceptance。

## Verification

最低執行：

```text
<repo-root>/.venv/bin/python -m unittest \
  tests.test_tskg_mfo01 tests.test_tskg_slc01 tests.test_tskg_src01
```

另以 table-driven probes 覆蓋 JSON scalar/container type confusion。不得安裝依賴、連外、呼叫真實資料或改寫 runtime。

## Verdict contract

- Findings 使用 P0–P3，必須含 `path:line`、觸發條件、風險、建議修法。
- Spec axis 與 Standards axis 分開判定。
- 最終 machine verdict 僅能是 `GO` 或 `NO_GO`。
- Python 3.13 caveat 若未擴大到已知 incompatibility，可列 remaining risk；不得隱藏。
- `GO` 只代表候選可由主線驗收整合，不代表 Theme、衍生公式、外部來源、API、UI 或 Top10 已批准。
- `NO_GO` 時列最小 repair allowlist；Review task 不得自行修復。

## Forbidden scope

- 不修改 candidate code、fixture、tests、原任務卡或原 verification。
- 不整合主線、不 push、不建立 PR。
- 不新增 API、來源 adapter、ThemeFlowObservation、rolling formula、DB、scheduler、UI 或 Top10 feature。

## Result

`NO_GO`

- Reviewed candidate：`11c68e9c32812a394788c95bc69a8763a92a8929`。
- Spec axis：`NO_GO`；RFC 3339 timestamp 欄位仍接受非字串 `datetime`。
- Standards axis：`NO_GO`；invalid JSON syntax 仍漏出 `JSONDecodeError`。
- Regression：Python 3.11.14 `46/46 PASS`；Python 3.13 `NOT_RUN` caveat 保留。
- Evidence：`docs/evidence/REVIEW-TSKG-MFO-01/review.md`。

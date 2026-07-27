---
card_id: REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01
status: NO_GO
evidence_kind: independent_architecture_review
reviewed_candidate_sha: 26d8471d15572f216095122f2462df79bc96edc1
candidate_parent_sha: cfaabf914f752b63a8efaf15ca40a5984221c2e1
---

# REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01

## Verdict

`NO_GO`

Candidate 的 UTC→IANA projection、signed UTC age、boundary inequalities、DST
fold、host timezone independence與 canonical policy hash 均可重算且一致；但有
三個固定 P1 finding。Spec axis 不通過，Standards axis 的 determinism 子軸通過，
後者不能抵銷前者。

固定 targeted re-review finding IDs：

- `FRTA-P1-01`：daily artifact source date 被硬綁 `market_run_date`
- `FRTA-P1-02`：successor lineage／allowlist 無法保留前鏈已關閉的安全邊界
- `FRTA-P1-03`：receipt v3 exact schema 未被完整定義

## Fixed boundary與capability preflight

```text
worktree: isolated / registered / detached
starting_head: deffa7e5f84aeae47461d5877a015754618ef1e6
starting_head_parent: 26d8471d15572f216095122f2462df79bc96edc1
starting_head_delta: Review card only
reviewed_candidate: 26d8471d15572f216095122f2462df79bc96edc1
candidate_parent: cfaabf914f752b63a8efaf15ca40a5984221c2e1
candidate_parent_match: PASS
starting_worktree_clean: PASS
unrelated_dirty_paths: []
git_metadata: PASS
uv: available
python: uv-managed .venv / CPython 3.12.12
zoneinfo: PASS
sha256: PASS
network_needed_for_review_logic: NO
live_runtime_needed: NO
production_acceptance: NOT_RUN
```

Review 前 `git diff-tree -r HEAD` 只列：

```text
A docs/tasks/2026-07-27_REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01.md
```

Candidate diff 只列 architecture、Executor evidence與 architecture card；沒有
runtime、tests、config、plist或 production artifact。

## Findings

### FRTA-P1-01：daily source date 與 civil run date 被混成同一 authority

- Severity：`P1`
- Location：
  - `docs/architecture/fog_runtime_time_authority_v1.md:108-109`
  - `docs/architecture/fog_runtime_time_authority_v1.md:338-340`
  - `docs/tasks/2026-07-27_REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01.md:67-69`
- Trigger：休市日或 source artifact 仍指向最近可信交易資料時，
  `market_run_date=2026-08-08`、`daily source date=2026-08-07`。
- Evidence：Review contract 明定 `source_trade_date`／daily source date 應獨立，
  休市日不得硬綁 run date；candidate 卻兩次要求
  `daily artifact source_date == market_run_date`。獨立 probe 的
  `source_date_counterexample` 顯示這組合法獨立日期會被 candidate invariant
  拒絕。
- Risk：實作者只能在「拒絕合法休市日 lineage」與「把 artifact identity
  冒充 source date」之間選一個，會重建本 architecture 原本要消除的日期權威混用。
- Validation gap：8-case matrix 沒有 daily source date 早於 civil run date 的
  休市日 case。
- Required repair：分開定義 artifact run identity 與 artifact data source date；
  verifier 應從 canonical artifact/source lineage 重算兩者，不得要求 source date
  必然等於 civil run date。新增固定休市日 matrix case。

### FRTA-P1-02：I1–I5 上限無法在固定 lineage 保留前鏈安全閉包

- Severity：`P1`
- Location：
  - `docs/architecture/fog_runtime_time_authority_v1.md:347-445`
  - `docs/architecture/fog_runtime_time_authority_v1.md:448-476`
- Trigger：主線依固定 candidate 建立 successor implementation card，並遵守
  architecture 所稱「每個 slice 都是後續卡的上限」。
- Evidence：
  - `git merge-base --is-ancestor acd835d… 26d8471…` exit `1`；
    Repair-2 candidate 不是本 candidate ancestor。
  - `26d8471…` 不含 `scripts/fog_authority_contracts.py`、
    `scripts/verify_fog_closed_regime_recovery.py`、
    `scripts/verify_processed_id_authority.py`、
    `scripts/verify_closed_regime_runtime.py`與
    `tests/test_fog_closed_regime_runtime.py`；這些在 `acd835d…` 存在。
  - I1–I5 allowlist 沒有納入前三個 authority／recovery／source-lineage
    modules，也沒有其直接 regression tests；因此不能在本 lineage 重建前一
    Review 已關閉的 `RRV-P1-01`、`RRV-P1-03` 保護。
- Risk：只實作 time authority 會以缺少 baseline/source-lineage authority 的
  mainline 版本接線；若改以未通過 Review 的 `acd835d…` 為隱含 base，則繞過固定
  candidate lineage與 rejected-code boundary。兩條路都不符合「不得弱化前一
  chain circuit、queue、model、ranking、baseline protection」。
- Validation gap：migration ordering 只有 v2 receipt inventory，沒有 successor
  base SHA、rejected Repair-2 code 的安全重建策略、或前一三個 finding 的完整
  regression allowlist。
- Required repair：明定合法 successor base與重建方式，將前鏈已關閉安全邊界所需
  modules/tests 納入 changed-file allowlist，並以新 candidate 重新驗證；不得把
  `acd835d…` 當成已接受 ancestor。

### FRTA-P1-03：`minimum fields` 無法支撐 exact-schema trust boundary

- Severity：`P1`
- Location：
  - `docs/architecture/fog_runtime_time_authority_v1.md:219-253`
  - `docs/architecture/fog_runtime_time_authority_v1.md:270-284`
- Trigger：producer/verifier 各自依文件實作 receipt v3，或由 v2 migration 到
  v3。
- Evidence：§7.4 只提供「minimum fields」，接著要求另外保留未列出的既有
  queue owner、runner identity、research contract、exact-regime、state
  transition、topic-run lineage與 production-impact 欄位；§7.5 同時要求
  exact-schema 拒絕所有 unknown/missing fields。文件沒有列出完整 key set、
  nested types、nullable/optional 規則與 v2→v3 field mapping；固定 candidate
  lineage 也沒有可作 normative schema 的 v2 implementation。
- Risk：producer與verifier可各自選出不同的「完整」schema，合法 receipt 可能
  fail closed；更嚴重時，實作者可能把未列欄位視為 optional 或 unknown，弱化
  queue／runner／state／production-impact trust boundary。
- Validation gap：I2 red tests列 hostile fields，但沒有 canonical complete v3
  fixture與 exact key/type manifest，無法證明 unknown/missing-field gate 的
  唯一預期。
- Required repair：在 versioned authority 中列出完整 receipt v3 exact schema
  與 type/optionality constraints，明定 v2 field mapping及 v2 fail-closed
  migration；producer與verifier共用同一 repo authority。

## Independent deterministic verification

Probe：

- `docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01/independent_probe.py`
- `docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01/probe_results.json`

執行：

```bash
<repo-root>/.venv/bin/python \
  docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01/independent_probe.py
```

結果：

| Axis | Result |
|---|---|
| 8-case matrix | PASS，八項皆 `true` |
| exact ages | PASS：`-5=true`、`-5.001=false`、`900=true`、`900.001=false` |
| Taipei midnight | PASS：相鄰 instants 產生不同 civil date |
| host timezone drift | PASS：UTC／Taipei／Los Angeles 均得 `2026-07-28` |
| DST fold | PASS：`05:30Z→fold=0/-04`；`06:30Z→fold=1/-05`，均 round-trip |
| policy hash | PASS：key reorder不變；semantic mutation改變 |
| receipt hostile hash | PASS：forged observed hash被拒 |
| receipt hostile policy/result | PASS：自報 policy/result不能讓 stale receipt通過 |

Canonical semantic policy SHA-256：

```text
67327c40206251adf4d377e76833dfd6261ce4fb3f56c7de0b0bf92c7231e357
```

這證明候選政策的純時間數學可實作，但不證明三個 P1 architecture contract 已閉合。

## Other gates

```text
required architecture file: PASS
required Executor evidence file: PASS
required canonical concept names: PASS
candidate diff --check: PASS
candidate changed-file allowlist: PASS
candidate runtime/live side effects: NONE OBSERVED
```

未執行 LaunchAgent、queue、retry state、model、ranking、baseline、merge、push、
deploy或 production acceptance。

## Acceptance snapshot

```text
status: NO_GO
root_question: candidate 是否建立單一、可重算且可實作的時間權威
evidence: deterministic probe PASS；三個固定 P1 findings
acceptance_mapping: time math PASS；source semantics、successor readiness、exact receipt schema FAIL
missing_evidence: repaired architecture candidate及三個 finding targeted re-review
remaining_risk: 休市日 source lineage誤拒、rejected-code lineage bypass、receipt verifier schema分歧
next_step: 唯一 Repair task修復 FRTA-P1-01/02/03；由本 Reviewer做 targeted re-review
limits: 不授權 implementation card、runtime、merge、push、deploy或 production acceptance
```

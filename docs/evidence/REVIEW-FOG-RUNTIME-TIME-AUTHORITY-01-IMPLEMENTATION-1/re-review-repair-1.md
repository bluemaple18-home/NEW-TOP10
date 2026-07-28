---
card_id: REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1
evidence_kind: targeted_implementation_re_review
verdict: REVIEW_GO
reviewed_commit: 6905ab28137fe255d86b2f49dcdd6f98ce1af661
review_base: 8b4b6e33cad066a884b486c284cd5f707d09cf83
amendment: 32798bd4df355315a39fe9ee4a693cfd1c90f9af
reviewer_thread_id: 019fa66b-444f-7522-915b-15aad3de5fe3
---

# Repair-1 targeted implementation re-review

## Verdict

`REVIEW_GO`

只 re-review原三項 finding：

- `FRTA-IMPL-P1-01`
- `FRTA-IMPL-P1-02`
- `FRTA-IMPL-P2-03`

三項均 `CLOSED`，targeted scope內未發現新阻塞問題。本 verdict只代表固定 Repair-1
candidate通過 Implementation targeted re-review；不授權 push、merge、deploy、
I5 migration、live runtime操作或 mainline／production acceptance。

## Fixed boundary與preflight

```text
worktree: registered / isolated / existing reusable Reviewer branch
review_branch: codex/fog-runtime-time-authority-implementation-review-1
review_base: 8b4b6e33cad066a884b486c284cd5f707d09cf83
repair_candidate: 6905ab28137fe255d86b2f49dcdd6f98ce1af661
candidate_parent: 8b4b6e33cad066a884b486c284cd5f707d09cf83
candidate_parent_count: 1
merge_base: 8b4b6e33cad066a884b486c284cd5f707d09cf83
amendment: 32798bd4df355315a39fe9ee4a693cfd1c90f9af
starting_worktree_clean: PASS
git_metadata: PASS
python: trusted main-repo .venv / CPython 3.12.12
network_needed: NO
live_runtime_needed: NO
```

Reviewer hostile probe的 blob在 base與candidate皆為：

```text
40a95cd0d1dbb38efb62ebf39f8fe0c70750a7e6
```

因此 probe byte-identical，Repair未修改或弱化 Reviewer assertions。

## Finding disposition

### `FRTA-IMPL-P1-01`：`CLOSED`

`config/fog_runtime_data_authority_v1.json`獨立固定：

- research-map／inventory canonical artifact paths；
- 各自 source role/path sets；
- trusted baseline path與 source identity；
- protected role/path set。

`scripts/fog_authority_contracts.py`以 hard-coded semantic object exact compare repo
config；time authority沒有混入 data semantics。Processed／baseline verifier仍保留
legacy arguments，但任何 path、role或 identity drift直接
`DATA_AUTHORITY_ARGUMENT_DRIFT`，只有 repo authority exact values才繼續讀
canonical artifacts。

獨立 corrected Reviewer probe：

```text
self_reported_distinct_sources_rejected: true
self_reported_baseline_rejected: true
legitimate_shape_control_accepted: true
baseline_hash_drift_rejected: true
```

Path escape、symlink escape、source hash drift、role swap與 shared source亦全數
fail closed。

### `FRTA-IMPL-P1-02`：`CLOSED`

`_canonical_daily()`只接受明示 `source_date`、`daily_source_date`或
`source_lineage.daily_source_date`。完全缺少、wrong type或多欄衝突立即
`DAILY_ARTIFACT_SCHEMA_REJECT`，不再以 regime source、run date或 host date
補值。

獨立 corrected Reviewer probe：

```text
missing_daily_source_rejected: true
control_accepted: true
```

Targeted tests另分別重跑 producer與 independent verifier missing-lineage
regressions；明示合法休市日 lineage仍通過。

### `FRTA-IMPL-P2-03`：`CLOSED`

Worker只保存 `mktemp`回傳的本 invocation exact path，統一 trap先
`cleanup_context`再釋放 locks；沒有 glob或跨 invocation掃描。

重跑 shell regression證明：

- circuit-open early exit清除自己的 context；
- verifier failure清除自己的 context；
- batch failure／正常 shell completion清除自己的 context；
- context建立失敗不留殘檔；
- foreign context全程保留。

## Spec axis

`PASS`

- Amendment `32798bd`：獨立 data authority config在 exact allowlist內；既有 time
  policy object與 semantic hash不變。
- P1-01：repo-owned source/baseline authority與 caller drift fail-closed完成。
- P1-02：missing daily lineage producer／verifier fail-closed完成。
- P2-03：bounded exact-path cleanup與 foreign-context isolation完成。
- Repair沒有擴張 I5或修改 architecture/schema、model、ranking、weights、
  baseline、promotion與 Reviewer evidence。

## Standards axis

`PASS`

- correctness：三項 finding皆由原 hostile trigger轉 GREEN。
- regression／backward compatibility：targeted與final full suite通過。
- security／authority confusion：caller mapping/path/identity不能取得 authority；
  path/symlink/hash/role attacks仍拒絕。
- performance／unbounded I/O：本 invocation context已有 bounded cleanup。
- maintainability：data/time authority分離，共用 canonical loader；cleanup只處理
  精確 owned path。
- test gaps：targeted scope無阻塞缺口；signal-level operational acceptance仍屬
  後續 I5／live boundary，不由本 re-review宣稱完成。

## Independent verification

Corrected Reviewer hostile probe：

```text
exit: 0
ok: true
failures: []
```

Targeted Python：

```text
35 passed in 0.09s
```

Shell／syntax／plist：

```text
tests/test_fog_research_retry_circuit.sh: PASS
tests/test_fog_runtime_time_wiring.sh: PASS
bash -n scripts/run_fog_research_worker.sh: PASS
bash -n scripts/run_daily_research_quota.sh: PASS
plutil -lint scripts/com.new-top10.fog-research-worker.plist: OK
```

Full suite原始 isolated run：

```text
1 failed, 567 passed, 4 warnings, 246 subtests passed
failure: ResearchComponentLedgerTest.test_verifier_accepts_generated_ledger
cause: 12 historical evidence/reference paths absent from isolated worktree
```

12 paths均在 Repair diff外且main repo有既有實體。暫掛12個 read-only symlinks後：

```text
568 passed, 4 warnings, 246 subtests passed in 54.89s
```

完成後逐一移除12個 symlinks與新建空目錄，無 provisioning殘留。

## Allowlist、hash與hygiene

Repair exact diff共10 paths，全部位於 amendment後 allowlist：

```text
config/fog_runtime_data_authority_v1.json
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-REPAIR-1/phase0.md
docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-REPAIR-1/verification.md
docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_IMPLEMENTATION-REPAIR-1.md
scripts/fog_authority_contracts.py
scripts/run_fog_research_worker.sh
scripts/verify_closed_regime_runtime.py
scripts/verify_processed_id_authority.py
tests/test_fog_closed_regime_runtime.py
tests/test_fog_research_retry_circuit.sh
```

```text
protected aggregate:
2aa2345f567d982634a1cf7a770cea96a77f0d8e3d5d9bd16b211e7abe75d126

time policy file:
d7bb19851d1e33e5245803bee4a7ef7d8534d97f58fc95c62e386aad5d60a058

time semantic hash:
67327c40206251adf4d377e76833dfd6261ce4fb3f56c7de0b0bf92c7231e357

time authority Python:
a2598480f268ec8bf5c8534dd1daae3cd867a6f90fab29a2e6daf15601efe59d

corrected Reviewer probe:
d2253a5e62c9d46f0079312a939d2e8c3cf1338c80ef107587d523eca5a6a33c

corrected review.md:
aa5415790cc78b5eb03f24fd7e4ffafa2fef752802c4ec39cd12b352dbc18229

accepted architecture:
b68c254f763a67b0c21ad90cb1c971fa7a7f7e1f188e5e26ee3ed30f0917f03b

receipt schema:
7c7d9836d418c84c6de046a5c8a063dc4af092aa5ff5fd10000257e3a8928ecc
```

Protected/read-only hashes與Repair Phase 0一致；base→candidate在 read-only paths無
diff。Changed production/tests無 secret、本機絕對路徑、debug marker或
TODO／FIXME；`git diff --check` PASS。

## Boundary

- live LaunchAgent／queue／retry-circuit／production artifacts：未操作。
- push／merge／deploy／I5：未執行。
- 新 Reviewer／Repair／Implementation task：未建立。
- Remaining risk：I5 migration與live operational acceptance仍未完成，本
  `REVIEW_GO`不得解讀為 mainline或 production acceptance。

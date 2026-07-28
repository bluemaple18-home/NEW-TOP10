---
card_id: FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-REPAIR-1
evidence_kind: repair_candidate_verification
status: CANDIDATE_VERIFIED
review_status: NOT_RUN
---

# Repair-1 verification

## Finding closure

- `FRTA-IMPL-P1-01`：新增獨立 versioned
  `config/fog_runtime_data_authority_v1.json`。processed artifact path、
  source role/path、baseline path/source identity與 protected role/path均由
  repo config固定；legacy function／CLI arguments只允許 exact compare。
- `FRTA-IMPL-P1-02`：daily source只接受明示 `source_date`、
  `daily_source_date`或`source_lineage.daily_source_date`；缺少、型別錯誤或
  多欄衝突立即 `DAILY_ARTIFACT_SCHEMA_REJECT`，不再使用 regime/run/host date
  fallback。Producer與independent verifier各有 regression。
- `FRTA-IMPL-P2-03`：worker trap只刪本 invocation由`mktemp`回傳的 exact
  context path。Success、circuit exit與context建立失敗皆無殘留；foreign
  context保留。

既有 time-policy v1 semantic object、canonical `67327c…` hash與
`scripts/fog_runtime_time_authority.py`完全未改。

## GREEN

Corrected Reviewer hostile probe：

```text
exit 0
failures: []
self_reported_distinct_sources_rejected: true
self_reported_baseline_rejected: true
legitimate_shape_control_accepted: true
missing_daily_source_rejected: true
```

Targeted Python：

```text
35 passed in 0.10s
```

Shell／syntax／plist：

```text
tests/test_fog_research_retry_circuit.sh: PASS
tests/test_fog_runtime_time_wiring.sh: PASS
bash -n scripts/run_fog_research_worker.sh: PASS
bash -n scripts/run_daily_research_quota.sh: PASS
plutil -lint scripts/com.new-top10.fog-research-worker.plist: OK
```

Full pytest首跑：

```text
1 failed, 567 passed, 4 warnings, 246 subtests passed
```

唯一 failure是已由原 Review記錄的
`ResearchComponentLedgerTest.test_verifier_accepts_generated_ledger`：
isolated worktree缺12個 historical evidence/reference paths，與本 Repair diff
無關。只暫掛 main repo既有12個 read-only paths後：

```text
568 passed, 4 warnings, 246 subtests passed in 56.72s
```

完成後已逐一移除12個 symlink與唯一新建的空
`artifacts/model_experiments`目錄；worktree無 provisioning殘留。

## Allowlist與hygiene

Candidate paths：

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

全部位於 amended Repair exact allowlist。

- protected aggregate after：
  `2aa2345f567d982634a1cf7a770cea96a77f0d8e3d5d9bd16b211e7abe75d126`
- protected before／after：byte-identical
- Reviewer evidence/probe、architecture/schema、原 Implementation evidence：
  read-only hashes與 Phase 0一致
- `git diff --check`：PASS
- secret、本機絕對路徑、debug marker、TODO／FIXME：changed production/tests無命中
- live LaunchAgent／queue／retry-circuit／production artifacts：未操作
- push／merge／deploy／I5：未執行

Candidate SHA由本 evidence所屬單一 repair commit與外部 delivery receipt綁定；
本文件不建立自我引用 SHA。

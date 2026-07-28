---
id: REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1
chain_id: FOG-RUNTIME-TIME-AUTHORITY-01
status: REVIEW_NO_GO
type: review
owner: independent-implementation-reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 變更橫跨市場時間權威、closed receipt v3、processed/source/baseline fail-closed verifier、shell scheduler wiring與既有 daily quota 相容性；需以 hostile fixtures獨立驗證 candidate evidence。
base_sha: 87e4da7dd63bafe82b16c28990e7be6db137b4e6
candidate_sha: f7d51a3d994707c819198fd1edcdcf0db4dd0775
implementation_thread_id: 019fa64f-3973-7d10-b0aa-4759af7aff1d
reviewer_thread_id: 019fa66b-444f-7522-915b-15aad3de5fe3
repair_thread_id: PENDING
---

# REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1

## Review boundary

只審查：

```text
87e4da7dd63bafe82b16c28990e7be6db137b4e6..
f7d51a3d994707c819198fd1edcdcf0db4dd0775
```

Candidate branch：
`codex/fog-runtime-time-authority-implementation-1`。

Reviewer 必須在獨立 clean worktree 重建測試，不可沿用 Executor 的 stored PASS。
原 architecture Reviewer 與本 Implementation Reviewer 是不同責任線。

## Spec axis

逐項比對：

- `docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_IMPLEMENTATION-1_clean_room_runtime.md`
- `docs/architecture/fog_runtime_time_authority_v1.md`
- `docs/architecture/fog_runtime_receipt_v3.schema.json`
- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/**`

必須確認：

1. I1–I4 已完整實作；I5 live migration／production acceptance 沒有偷跑。
2. strict RFC3339 UTC `Z`、`Asia/Taipei` projection、signed freshness
   `-5`／`900` accept與超界 reject。
3. `market_run_date`、`artifact_run_date`、`daily_source_date`、
   `source_trade_date`分離，跨 UTC 日界與合法休市日 deterministic。
4. processed-ID、canonical source role/path/hash、trusted baseline都由 repo
   authority重算；receipt／env自報不能取得 authority。
5. receipt v3 exact schema、canonical hashes、unknown/missing/type/path
   mutation fail closed；v2不可 relabel。
6. worker只建立一次 immutable time context，daily child只傳遞；shell無
   `date +%F` contract identity fallback，plist不注入 policy。
7. `fog_worker`仍為唯一 queue mutation owner；未操作 live LaunchAgent、
   queue、retry/circuit、model、ranking、weights、baseline或 promotion。

## Required hostile probes

Reviewer 至少自行新增或在暫存目錄執行下列不信任 candidate fixture的 probes：

- forged processed-ID、兩份 artifact共享同一 source、集合差異；
- source path escape、symlink escape、source hash drift、role swap；
- self-reported baseline、legitimate trusted baseline control、baseline hash drift；
- receipt missing／unknown／wrong type／wrong contract hash／artifact identity drift；
- naive／stale／future timestamp，`-5`／`900`與超界；
- UTC 日界、合法休市日、`TZ=UTC|Asia/Taipei|America/Los_Angeles` identity；
- legacy env mismatch、market-midnight rollover；
- shell/plist static scan與 queue mutation ownership。

固定回歸 ID：

- `FRTA-REG-RRV-P1-01-PROCESSED-ID`
- `FRTA-REG-RRV-P1-03-SOURCE-BASELINE`
- `FRTA-REG-RECEIPT-V3-EXACT`
- `FRTA-REG-TIME-DATE-LINEAGE`

## Standards axis

分開輸出：

- correctness
- regression／backward compatibility
- security／path traversal／symlink／authority confusion
- performance／unbounded I/O
- maintainability
- test gaps

Finding 必須包含 `severity`、`category`、`path:line`、觸發條件、證據、
風險、建議修法、驗證缺口與信心。只有 P0／P1、production safety risk、
可利用 security問題或重複 warning pattern可阻擋；不得用單一風格 warning
阻擋。

## Verification

至少重跑：

```bash
cd <repo-root>
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

若 full suite因已知 historical evidence provisioning gap失敗，必須：

- 保存原始 fail；
- 證明與 candidate diff無關；
- 只暫掛既有 read-only evidence；
- 重跑後移除並確認 worktree無 allowlist外污染。

## Output contract

只允許新增：

- `docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/**`
- 本卡的 review receipt／狀態欄位

寫入 `review.md`：

- `verdict: REVIEW_GO | REVIEW_NO_GO`
- `reviewed_commit: f7d51a3d994707c819198fd1edcdcf0db4dd0775`
- Spec axis與Standards axis分離結論
- findings／hostile probes／驗證結果／剩餘風險

Reviewer只交原子 review commit，不得修改 candidate code、push、merge、
deploy、建立 Repair、操作 live runtime或自行宣稱 mainline acceptance。

## Review receipt

```text
verdict: REVIEW_NO_GO
reviewed_commit: f7d51a3d994707c819198fd1edcdcf0db4dd0775
reviewer_task: 019fa66b-444f-7522-915b-15aad3de5fe3
spec_axis: FAIL
standards_axis: FAIL
blocking_findings: FRTA-IMPL-P1-01, FRTA-IMPL-P1-02
i5_live_acceptance: NOT_RUN_OUT_OF_SCOPE
```

## Dispatch receipt

- Dispatcher task：`019f82c1-b7d0-7eb3-9371-7a95ebfbd7ce`
- Implementation task：
  `019fa64f-3973-7d10-b0aa-4759af7aff1d`
- Candidate：
  `f7d51a3d994707c819198fd1edcdcf0db4dd0775`
- Candidate branch：
  `codex/fog-runtime-time-authority-implementation-1`
- Reviewer task：`019fa66b-444f-7522-915b-15aad3de5fe3`
- Gate 1 physical card：`PASS`
- Gate 2 visible thread：`PASS`
- Gate 3 independent verdict：`REVIEW_NO_GO`

---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1
chain_id: FOG-I5-EXACT-REGIME-ELIGIBILITY
status: READY_FOR_REVIEW
type: repair
generation: 1
ownership: repair_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: xhigh
model_reason: 修補 closed-regime ranking inventory 可透過 file-level symlink 越過 repo authority 的 P1 trust-boundary 缺口；正式 task繼承使用者設定的 gpt-5.6-sol xhigh。
base_candidate_sha: 684d3adf3916100a7eb9bb57c6164f3b67a58064
review_evidence_sha: e50022a9db130832d9855846d12168a79d454cef
reviewer_thread_id: 019fa76b-e568-7653-ade0-a399a3a1aa4a
repair_thread_id: 019fa778-8623-70b1-840d-a542a9a2e46d
repair_candidate_sha: 51c084cd077cd4e997873e4a924f73e3dca2ba3d
finding_id: FOG-EXACT-REGIME-REVIEW-P1-001
evidence_path: docs/evidence/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/
---

# FOG exact-regime topic eligibility Repair-1：file-level symlink authority

## 角色與目的

你是 Repair Executor，不是 Reviewer或 Integrator。

只關閉 `FOG-EXACT-REGIME-REVIEW-P1-001`：repo內 candidate／baseline ranking
directory若含有指向 repo外的 `ranking_YYYY-MM-DD.csv` symlink，目前仍會被
視為 canonical exact-date inventory，並讓 matrix讀取外部內容。

## 固定來源

- Repair source／Review commit：
  `e50022a9db130832d9855846d12168a79d454cef`
- Reviewed candidate：
  `684d3adf3916100a7eb9bb57c6164f3b67a58064`
- Original implementation：
  `3969aba5c62171ef52d5c54856f0c0821b750627`
- Review evidence：
  `docs/evidence/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review.md`
- Original Reviewer：
  `019fa76b-e568-7653-ade0-a399a3a1aa4a`

開始前確認 HEAD精確命中 Review commit、worktree clean、cwd不是 main checkout，
並執行 `worktree_capability_preflight.sh --check`。

## Phase 0：RED

在 production edit前：

1. 重跑 reviewer hostile probe，證明
   `symlink_file_escape`是唯一失敗案例。
2. 在 `tests/test_regime_research_autonomy.py`新增 observable regression：
   candidate與 baseline兩個角色都必須覆蓋 repo內 ranking file symlink指向
   repo外 regular file。
3. 測試必須先在未修改 production code的 Review commit上失敗，保存 command、
   exit code與 failure摘要。

不得把既有 reviewer probe改成假綠。

## 必做修復

1. `repo_owned_ranking_date_inventory`逐一驗證 matched ranking entry。
2. 任一 matched entry符合下列條件即整個 inventory fail closed：
   - entry本身為 symlink；
   - 非 regular file；
   - `resolve(strict=True)`失敗；
   - resolved target不在 `PROJECT_ROOT`內。
3. Candidate與 baseline任一側失敗，都必須使 topic
   `eligible=False`，回穩定 `RANKING_INVENTORY_PATH_ESCAPE`；不得降級成
   zero-intersection或忽略壞檔後繼續。
4. 合法 regular-file candidate/baseline、legacy non-closed topic、
   index/fallback/queue排除、`NO_EXECUTABLE_TOPIC` daily source lineage行為不變。
5. `scripts/run_backtest_strategy_matrix.py`維持不變；本 Repair在 scheduler
   authority邊界阻止外部 ranking進入 matrix。

## Allowlist

- `scripts/run_autonomous_research.py`
- `tests/test_regime_research_autonomy.py`
- `docs/evidence/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/**`
- `.work/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/**`

除非出現可重現且無法在此 allowlist內處理的新 blocker，禁止擴大範圍。

## 禁止範圍

- 不修改 `scripts/run_backtest_strategy_matrix.py`。
- 不修改 production model、ranking、weights、baseline、promotion、queue policy、
  manager history、LaunchAgent、retry circuit或 live artifacts。
- 不執行第四次 live Fog probe、不重啟 LaunchAgent、不清 circuit。
- 不修改原 Review evidence或 reviewer hostile probe。
- 不自審、不建立 Review verdict、不 merge、push、deploy或 integration。

## 驗證

至少執行：

```bash
cd <repo-root>
.venv/bin/python \
  .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review/hostile_probes.py
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_fog_daily_source_lineage.py \
  tests/test_fog_closed_regime_runtime.py
.venv/bin/python -m pytest -q
.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  tests/test_regime_research_autonomy.py
git diff --check e50022a9db130832d9855846d12168a79d454cef..<repair-candidate>
git diff --quiet 684d3adf3916100a7eb9bb57c6164f3b67a58064..<repair-candidate> \
  -- scripts/run_backtest_strategy_matrix.py
```

Hostile probe修復後須為16/16通過。Full suite若只重現 Review已記錄的
research component ledger missing ignored-artifact failure，必須附 exact failure與
base/review歸因證據；不得把其他 failure視為可接受。

另需保存：

- candidate與 baseline兩種 symlink角色的 RED→GREEN；
- reason code與 `eligible=False` observable payload；
- changed-file allowlist；
- protected matrix diff為零；
- production/runtime protected path diff為零。

## Output contract

只提交一個原子 Repair candidate commit，回報：

- `READY_FOR_REVIEW`
- 完整 Repair candidate SHA與 parent SHA
- Phase 0 RED、GREEN與 hostile probe 16/16證據
- targeted／full suite／py_compile／diff／allowlist結果
- 未驗證項目與剩餘風險

完成即停止，交回原 Reviewer task做 targeted re-review。

## Dispatch receipt

- Formal task：`019fa778-8623-70b1-840d-a542a9a2e46d`
- Worktree：`<codex-worktree>/39c6/TOP10new`
- Source SHA：
  `e50022a9db130832d9855846d12168a79d454cef`
- Initial worktree：clean
- Actual model：`gpt-5.6-sol xhigh`
- Receipt：
  `.work/FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/dispatch_receipt.md`

## Candidate receipt

- Status：`READY_FOR_REVIEW`
- Repair candidate：
  `51c084cd077cd4e997873e4a924f73e3dca2ba3d`
- Parent：
  `e50022a9db130832d9855846d12168a79d454cef`
- Hostile probes：`16/16`
- Targeted：`88 passed`
- Full suite：`586 passed, 1 failed`；唯一失敗為既有 isolated-worktree ledger
  missing ignored-artifact failure。
- Protected matrix、原 Review evidence/probe：零差異。
- Next gate：原 Reviewer task targeted re-review。

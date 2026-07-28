---
id: FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-MAINLINE-ACCEPTANCE
status: GO_LOCAL_DETERMINISTIC
integration_sha: 374792652b8bee8a869052228da78f7a0d4558b4
reviewed_repair_sha: 51c084cd077cd4e997873e4a924f73e3dca2ba3d
review_go_sha: 0b1373bdea3d02b6a92c07a121f664949e4f48f2
---

# Mainline acceptance

## Status

`GO_LOCAL_DETERMINISTIC`

這代表 exact-regime topic eligibility修復、Repair-1與獨立 Review已在目前
task branch完成本機整合與 deterministic acceptance；不代表 I5 live scheduler
acceptance、push或 production deployment完成。

## Fixed lineage

- Base：`33aee4d`
- Initial candidate：
  `684d3adf3916100a7eb9bb57c6164f3b67a58064`
- Initial Review：`REVIEW_NO_GO`
- Initial Review commit：
  `e50022a9db130832d9855846d12168a79d454cef`
- Repair-1：
  `51c084cd077cd4e997873e4a924f73e3dca2ba3d`
- Targeted re-review：`REVIEW_GO`
- Re-review commit：
  `0b1373bdea3d02b6a92c07a121f664949e4f48f2`
- Local integration：
  `374792652b8bee8a869052228da78f7a0d4558b4`
- Merge parents：
  `813a8294410d5d9df414e8ffefcb7a526b4f5df6`、
  `0b1373bdea3d02b6a92c07a121f664949e4f48f2`

## Acceptance evidence

Original hostile probes：

```text
.venv/bin/python \
  .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01/review/hostile_probes.py
```

Result：exit 0，`16/16`。

Repair-1 independent probes：

```text
.venv/bin/python \
  .work/REVIEW-FOG-EXACT-REGIME-TOPIC-ELIGIBILITY-01-REPAIR-1/review/hostile_probes.py
```

Result：exit 0，`7/7`。Candidate／baseline external symlink、broken symlink、
matched non-regular entry皆為`eligible=False`，reason為
`RANKING_INVENTORY_PATH_ESCAPE`，role正確；index／fallback／queue皆不選回。

Targeted：

```text
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_fog_daily_source_lineage.py \
  tests/test_fog_closed_regime_runtime.py
```

Result：exit 0，`88 passed in 4.43s`。

Main checkout full suite：

```text
.venv/bin/python -m pytest -q
```

Result：exit 0，`587 passed, 4 warnings, 246 subtests passed in 219.92s`。
這也關閉 isolated Reviewer worktree因缺 ignored artifacts造成的單一 ledger
failure不確定性。

Static／boundary gates：

```text
.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  tests/test_regime_research_autonomy.py
git diff --check 33aee4d..374792652b8bee8a869052228da78f7a0d4558b4
git diff --quiet 33aee4d..374792652b8bee8a869052228da78f7a0d4558b4 \
  -- scripts/run_backtest_strategy_matrix.py
```

Result：全部 exit 0。

## Runtime safety recheck

只做 read-only recheck，未執行 worker：

- LaunchAgent query exit 1／job不存在，維持 unloaded。
- Retry state：`attempts=3`、`circuit_open=1`。
- Retry state SHA-256：
  `acfbfbc43bc02af51e5fb6b1d3e285616bf2fcf846e41ceda8ee3b79cd74096c`
- Retry context SHA-256：
  `528d5cca4482f0e9ccb9e6d2374e856ca57557ebd69df3deb87c858a787f3255`
- Installed plist SHA-256：
  `f63ae67c4ae7b437246d31f8122307b5a5726778d36d302794b80fa342f664cb`

三個 hash與 implementation preflight完全一致。

## Acceptance mapping

- Root question：已由 deterministic regression與兩層 hostile probes回答。
- Original eligibility blocker：closed。
- Review P1：resolved。
- Candidate/baseline path authority：fail closed。
- Legal regular inventory與 legacy behavior：保留。
- Matrix second-line guard：未修改。
- Main checkout regression：全綠。

## Remaining risk / waiting conditions

- I5仍未執行新的 live acceptance；三次 live probe停損仍有效。
- LaunchAgent保持 unloaded，retry circuit保持 open。
- Matrix若被直接繞過 scheduler呼叫，仍缺 file-level defense-in-depth；Reviewer列為
  TOCTOU／direct-call residual，不阻擋本卡 scheduler authority修復。
- 未執行 large ranking inventory benchmark。
- Branch尚未 push；push／PR／production deployment需另行明確授權。

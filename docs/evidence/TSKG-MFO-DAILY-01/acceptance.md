# TSKG-MFO-DAILY-01 Mainline Acceptance

## Status

```text
status: CLOSED_GO
candidate: dfc30dc4a8466b914c642c1b38ea206dd388aa7c
independent_review: REVIEW_GO
review_commit: cc7355c
mainline_integration_commit: 66b26f8
mainline_merge_commit: 02ab4a9
ranking_or_model_change: NONE
```

## Acceptance mapping

- Candidate 未直接 merge：`main` 當時已有較新的 daily orchestrator，因此以 `66b26f8` 做契約等價整合，再由 `02ab4a9` 合入。
- 與 candidate 完全相同的核心檔包含 T86 strict parser、flow read model、fetch CLI、market-context reuse 與主要 contract tests。
- `config/automation.yaml`、`scripts/run_automation.py` 保留後續主線功能，同時維持 `tskg_t86_enabled`、T86 先抓一次再交 market-context 的順序。
- `tests/test_tskg_t86_automation.py` 在主線額外覆蓋 invalid cached artifact fail-soft。
- `app/tskg/__init__.py` 只存在整合期 import ordering 差異；acceptance 同時移除重複 import，未改 public exports。

## Evidence chain

- Candidate implementation evidence：`docs/evidence/TSKG-MFO-RM-01/verification.md`、`docs/evidence/TSKG-MFO-T86-01/verification.md`。
- Independent review evidence：`docs/evidence/REVIEW-TSKG-MFO-DAILY-01/review.md`。
- Integration evidence：`docs/evidence/TSKG-MFO-INTEGRATE-01/verification.md`。
- Review finding：無 P0–P2；1 個 P3 unit-hints validator asymmetry 留待獨立 hardening，不阻塞本機 read-only acceptance。

## Mainline verification

```text
TSKG targeted unittest: 63 PASS
market-context verifier: PASS
daily market coverage gate: PASS
daily pipeline window override gate: PASS
resource guard: PASS
pytest tests/: 414 PASS, 246 subtests PASS
script reference audit --strict-new: PASS
git diff --check: PASS
```

## Boundaries

- `SHARE` 不映射成 MFO-01 TWD value。
- TPEx、ThemeFlow、graph diffusion、ranking feature、API／LLM redistribution 與正式 rate／retention governance 維持 blocked。
- runtime T86 artifact 位於 ignored `artifacts/tskg/t86/`，不隨 Git 跨機。

## Cleanup contract

- Acceptance push 成功後移除 isolated review worktree。
- 僅刪除本任務的 `codex/tskg-mfo-daily-01`、`codex/top10new-review-tskg-mfo-daily-01-20260721-153932` 與 `codex/tskg-mfo-mainline-integration` local/remote refs。
- Thread receipt `019f839f-5faf-72a3-9ea3-5b847cfeb709` 在權威主機查無可操作實體；cleanup 結果記為 `ABSENT_ON_CANONICAL_HOST`，不再保留為 blocker。

## Final closure

```text
chain_status: CLOSED
canonical_workspace_clean: true
canonical_main_synced: true
related_local_branches_remaining: 0
related_remote_branches_remaining: 0
related_worktrees_remaining: 0
review_thread_cleanup: ABSENT_ON_CANONICAL_HOST
remaining_actions: 0
```

另一台電腦曾回報的 10 個 dirty files 與 `/Users/matt/...` checkout 在權威主機不存在，因此不是 canonical unresolved state，不得繼續列為本鏈待辦。

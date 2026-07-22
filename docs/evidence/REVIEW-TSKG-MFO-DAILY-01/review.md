# REVIEW-TSKG-MFO-DAILY-01 Independent Review

## Verdict

```text
reviewed_sha: dfc30dc4a8466b914c642c1b38ea206dd388aa7c
candidate_parent: c84120be3ca0fb9efa6ed367ddac70e3b1a801b8
verdict: REVIEW_GO
P0: 0
P1: 0
P2: 0
P3: 1
```

Candidate 可交主線 acceptance。此 GO 僅涵蓋 TWSE T86 本機逐日唯讀 snapshot、source-neutral read model 與既有 market-context reuse；不授權 ranking feature、Theme aggregation、TPEx、API／LLM redistribution 或正式 retention policy。

## Findings

### [P3] Saved snapshot 的 source hints 單位檢查比 ingestion 路徑寬 — `app/tskg/twse_t86.py:282`

建檔路徑拒絕 hints 同時含「元」，但載入既存 snapshot 時只要求含「股」。若本機程式自行重算 checksum 並寫入矛盾 hints，仍可能通過 loader。top-level `unit=SHARE`、整數 `_shares` schema 與本機 artifact trust boundary 使其不構成本次阻塞；後續可共用同一個 exact unit predicate，避免兩條驗證路徑漂移。

## Spec axis

- `flow_read_model.py`：deterministic grouping/order/hash、partial/stale warnings、provenance refs、defensive lookup 均由測試覆蓋。
- T86：19 欄 closed field set、17 個 integer share metrics、日期、row count、唯一代碼、算術與 checksum fail closed。
- Fetch：固定官方 HTTPS endpoint、一次 GET、20 秒 timeout、無 retry loop、無 credential。
- Write：同目錄 temporary file、flush/fsync、atomic replace；runtime path 位於 ignored `artifacts/`。
- Automation：先產 T86 snapshot，再以 `--twse-t86-input` 交給 market-context；正常成功路徑不重複抓 T86；disabled path 保持原 command。
- Production boundary：candidate 未修改 ranking policy、模型、推薦 score、API、UI 或 promotion path。

Spec axis：`PASS`。

## Standards axis

- Python 使用既有 `.venv`；新增測試與現有 unittest／verifier 模式一致。
- shared docs／handoff 未引入本機絕對路徑。
- candidate diff `git diff --check` 通過。
- review branch changed-file allowlist 僅含本卡與本 evidence。

Standards axis：`PASS_WITH_P3`。

## Commands and exit codes

| Command | Exit | Result |
|---|---:|---|
| `git status --short` | 0 | review worktree clean |
| `git show --stat --oneline dfc30dc...` | 0 | 20 files, 1,420 insertions, 144 deletions |
| `git diff --check c84120b..dfc30dc` | 0 | PASS |
| `.venv/bin/python -m unittest tests.test_tskg_flow_read_model tests.test_tskg_twse_t86 tests.test_tskg_t86_automation tests.test_tskg_mfo01 tests.test_tskg_slc01 tests.test_tskg_src01` | 0 | 62 tests PASS |
| `.venv/bin/python scripts/verify_market_context_fetcher.py` | 0 | PASS |
| `.venv/bin/python scripts/verify_daily_market_coverage_gate.py` | 0 | PASS |
| `.venv/bin/python scripts/verify_daily_pipeline_window_override.py` | 0 | PASS |
| `.venv/bin/python scripts/verify_resource_guard.py` | 0 | PASS |
| `.venv/bin/python -m pytest -q tests` | 0 | 62 tests + 218 subtests PASS |

額外執行未限定路徑的 `pytest -q` 時，candidate 基線的 `scripts/test_regex.py` 因 ignored `artifacts/analysis_report.md` 不存在而在 collection 階段退出 2；該檔不在 candidate diff。改以明確 `tests/` collection 完成全測試目錄回歸，未把前者記為通過。

## Changed-file allowlist

Independent review 僅新增／修改：

- `docs/tasks/2026-07-21_REVIEW-TSKG-MFO-DAILY-01_cross_machine.md`
- `docs/evidence/REVIEW-TSKG-MFO-DAILY-01/review.md`

Candidate code、config、fixtures、tests、implementation evidence 與 `.work/current` 均未修改。

## Not rerun

- 未重跑外部 TWSE endpoint；依卡片沿用 candidate 已記錄的單次真實 GET evidence。
- 未執行 daily production run、deploy、scheduler、通知或任何 external write。

## Remaining risks and blocked edges

- 正式 rate、retention、redistribution governance 未核准。
- TPEx 法人資料、ThemeFlow、graph diffusion 與 ranking feature 維持 blocked。
- T86 是 `SHARE`，不得映射為 MFO-01 的 TWD value。
- P3 unit-hints validator asymmetry 可另卡 harden，不阻塞本次本機 read-only acceptance。

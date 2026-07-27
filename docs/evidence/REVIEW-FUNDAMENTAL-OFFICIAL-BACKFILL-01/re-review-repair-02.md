---
id: RE-REVIEW-REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-02
status: completed
type: final_re_review
verdict: GO
---

# Repair-2 Final Re-review

## Fixed scope

- Repair-1 parent：`48c10ab86420d57bb8a662e74d95b920e25930d3`
- Repair-1 re-review evidence：`dbb66cdee42b4a9d94ffaf6cffcbc320838b0a82`
- complete reviewed Repair-2 SHA：`410b9d2464bc6e72a94631ec1600ccbb6a72ebe1`
- reviewer branch：`codex/review-fundamental-official-backfill-01`
- reviewer start HEAD：`dbb66cdee42b4a9d94ffaf6cffcbc320838b0a82`
- reviewer 未修改 Repair-2 candidate，未 merge、push、deploy 或 promotion。

Repair-2 sibling branch 包含等價 re-review commit
`baa22768f7cc37f4dc5fe4848c8f25430786cefd`，而非直接包含固定
`dbb66cd...`。兩個 commit 的 stable patch-id 均為：

```text
3d39e44439fb1490d180c5573a068ee048c4de5d
```

`re-review-repair-01.md` 內容亦逐 byte 相同，因此固定 re-review evidence 綁定成立。

## Findings

未發現阻塞問題。

## FND-FUND-003：CLOSED

Repair-2 將 `_valid_zip()` 的例外捕捉由 broad `Exception` 縮小為
`BadZipFile` 與 `OSError`：

- ZIP 結構無效／檔案讀取失敗仍回傳 `False`，保留既有 downloader 行為。
- `_validate_zip_resources()` 的詳細 `ValueError` 不再被吞掉。
- cache reuse 與新下載入口均原樣保留 member 名稱、實際值及上限。
- cache reuse 超限時不會誤發起重新下載。

獨立 targeted 結果：

```text
2 passed, 11 deselected
```

兩個正式入口都驗證完整訊息：

```text
ZIP member 單檔未壓縮大小超限：
tifrs-fr1-m1-ci-cr-2330-2025Q2.html=2048 > 1024
```

FND-FUND-003 的 download/cache resource-limit 診斷傳遞契約已成立。

## Closed finding regression

Repair-2 的程式 diff 僅修改：

- `app/fundamentals/mops_xbrl.py` 的 `_valid_zip()` exception boundary。
- `tests/test_mops_xbrl_fundamentals.py` 的兩個 downloader regression。

未修改 production promotion gate、context selection 或 FCF normalization。

獨立重跑 FND-001/002 保護測試：

```text
test_high_coverage_fundamentals_stay_out_of_production_candidates
test_cash_flow_contexts_select_current_period_and_normalize_ytd_to_quarter
test_ytd_cash_flow_without_previous_quarter_fails_closed
=> 3 passed, 10 deselected
```

- FND-FUND-001：維持 `CLOSED`。
- FND-FUND-002：維持 `CLOSED`。

## Verification

```text
git diff --check 48c10ab...410b9d2
=> PASS

targeted downloader/cache regression
=> 2 passed, 11 deselected in 0.98s

<repo-root>/.venv/bin/python -m pytest -q tests/test_mops_xbrl_fundamentals.py
=> 13 passed in 0.79s

<repo-root>/.venv/bin/python -m pytest -q
=> 1 failed, 486 passed, 246 subtests passed
```

全套唯一失敗仍為：

```text
tests/test_research_component_ledger.py::
ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
```

其原因仍是 clone/worktree 未包含既有 ledger `evidence_exists` artifacts，與 Repair-1
及其兩次 review 所記錄的環境缺口一致。Repair-2 未修改 ledger、artifact inventory
或相關測試，且沒有新增 failure。

## Axis conclusions

- Spec axis：`PASS`；FND-FUND-003 已關閉，FND-FUND-001/002 未回歸。
- Standards axis：`PASS_WITH_KNOWN_ENV_GAP`；targeted、Fundamental suite 與 diff
  gate 通過，全套僅保留既有 ledger evidence 環境缺口。

## Verdict

`GO`

此 verdict 只代表 Repair-2 通過原 Reviewer 的 bounded repair re-review，不等於
merge、deployment 或 production feature promotion 核准。

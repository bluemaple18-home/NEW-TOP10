# REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-02

status: `DELIVERED_REPAIR_CANDIDATE`

## Preflight

- runtime model：`gpt-5.6-sol`
- reasoning：`high`
- cwd／worktree：`<repo-root>`（隔離 Codex worktree）
- branch：detached HEAD；`codex/repair-fundamental-official-backfill-01-02` 指向開始時
  HEAD。
- 開始時 HEAD：`8374cfa11b051b86a32d8b71ccf973241a3354c8`
- 固定 parent Repair-1：
  `48c10ab86420d57bb8a662e74d95b920e25930d3`
- 固定 re-review evidence：
  `dbb66cdee42b4a9d94ffaf6cffcbc320838b0a82`
- 工作鏈上的 re-review commit：
  `baa22768f7cc37f4dc5fe4848c8f25430786cefd`；其與固定 evidence 的 stable
  patch-id 均為 `3d39e44439fb1490d180c5573a068ee048c4de5d`。
- ancestry：`Repair-1 -> equivalent re-review evidence -> Repair-2 card HEAD`
- repair candidate：本 evidence 所在 commit；完整 SHA 由交付訊息回報，避免
  self-referential commit SHA。
- 未 merge、push、deploy 或 promotion。

此 worktree 沒有 `.venv`；測試使用同 repo 既有 `<repo-root>/.venv/bin/python`
等價環境執行，程式碼與 pytest 工作目錄均為本隔離 worktree。

## Root-cause hypotheses

1. `_valid_zip()` 的 broad `except Exception` 吞掉
   `_validate_zip_resources()` 的詳細 `ValueError`。
2. cache reuse 與新下載使用不同資源驗證接縫，可能需要兩套修復。

兩個 downloader regression 證實假說 1；程式呼叫關係與 red 結果否證假說 2：
cache reuse 與新下載都經過 `_valid_zip()`，因此同一 exception-flow 缺陷會將兩者
都泛化成「不是有效 ZIP」。

## Red -> green

Red command：

```bash
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_mops_xbrl_fundamentals.py \
  -k 'download_xbrl_zip_cache_reuse_preserves_resource_limit_diagnostic or download_xbrl_zip_new_download_preserves_resource_limit_diagnostic'
```

修復前：

```text
2 failed, 11 deselected in 1.61s
```

cache reuse 與新下載都實際收到：

```text
MOPS 2025Q2 回應不是有效 ZIP
```

而契約要求保留：

```text
ZIP member 單檔未壓縮大小超限：tifrs-fr1-m1-ci-cr-2330-2025Q2.html=2048 > 1024
```

最小修復後，以完全相同指令重跑：

```text
2 passed, 11 deselected in 0.91s
```

## Fix mapping

### FND-FUND-003

- `_valid_zip()` 仍將 `BadZipFile` 與 `OSError` 視為 ZIP 結構／檔案讀取無效並回傳
  `False`，由 downloader 產生既有的「不是有效 ZIP」錯誤。
- `_validate_zip_resources()` 的 `ValueError` 不再被 broad catch 吞掉，因此正式
  download path 原樣保留 member 名稱、實際值與上限。
- cache reuse regression 同時斷言資源超限時不發起重新下載。
- 新下載 regression 以 mock transport 覆蓋正式 downloader 接縫，不只直接測
  `parse_xbrl_zip()`。
- 未修改任何 ZIP 上限、parser、promotion gate、FCF normalization、ranking、權重、
  API、UI 或 production 狀態；未重開 FND-FUND-001/002。

## Verification

```text
targeted downloader/cache regression
=> 2 passed, 11 deselected

<repo-root>/.venv/bin/python -m pytest -q tests/test_mops_xbrl_fundamentals.py
=> 13 passed in 0.81s

<repo-root>/.venv/bin/python -m pytest -q
=> 1 failed, 486 passed, 246 subtests passed in 53.71s

git diff --check
=> PASS

debug instrumentation marker scan
=> none
```

全套唯一失敗：

```text
tests/test_research_component_ledger.py::
ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
AssertionError: 'FAILED' != 'OK'
```

此項與 Repair-1 re-review 記載的 clone/worktree `evidence_exists` 缺口相同。本 repair
未修改 research ledger、artifact inventory 或該測試；新增兩個 downloader
regression 後，通過數由既有 `484` 增為 `486`，沒有新增其他失敗。

## Allowlist

- `app/fundamentals/mops_xbrl.py`
- `tests/test_mops_xbrl_fundamentals.py`
- `docs/tasks/2026-07-27_REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-02.md`（狀態更新）
- `docs/evidence/REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-02/repair.md`

## Remaining risk

- 全套 pytest 仍受既有 research ledger evidence 缺口阻擋，不能宣稱 repository
  全綠；FND-FUND-003 的 targeted 與 Fundamental suite 均已通過。
- 本交付只供原 Reviewer 最終 re-review，不是 acceptance、merge 或 production
  promotion 核准。

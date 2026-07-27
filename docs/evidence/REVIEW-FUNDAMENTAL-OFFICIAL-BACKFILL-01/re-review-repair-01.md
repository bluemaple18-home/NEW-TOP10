---
id: RE-REVIEW-REPAIR-FUNDAMENTAL-OFFICIAL-BACKFILL-01-01
status: completed
type: re-review
verdict: NO_GO
---

# Repair-1 Formal Re-review

## Fixed scope

- parent candidate：`ae12ef39805e812d86d9a1a8bf3a963b6052a901`
- original review evidence：`ce94b06ad0c691b6a2b5c3921bff1aff9b1f006c`
- complete reviewed repair SHA：`48c10ab86420d57bb8a662e74d95b920e25930d3`
- reviewer branch：`codex/review-fundamental-official-backfill-01`
- reviewer start HEAD：`ce94b06ad0c691b6a2b5c3921bff1aff9b1f006c`
- ancestry：`parent -> original review evidence -> repair card -> repair candidate`
- reviewer 未修改 repair candidate，未 merge、push、deploy 或 promotion。

## Finding re-validation

### FND-FUND-001：CLOSED

Repair 新增預設關閉的 `FUNDAMENTAL_PRODUCTION_PROMOTION_ENABLED`，且
`candidate_feature_columns()` 在 gate 關閉時排除整個 fundamental group。

使用官方六季 ZIP 重建的隔離 cache 實測：

```text
coverage=0.998
fundamental_candidates=[]
```

`tests/test_mops_xbrl_fundamentals.py` 亦包含 99.8% coverage regression。
高資料 coverage 不再等同 production feature promotion。

### FND-FUND-002：CLOSED

Repair 解析 `contextRef` 起訖日，選擇本期 context，並將 Q2/Q3/Q4 的 YTD OCF 與
capex 對前季 YTD 差分；缺前季時 FCF fail closed 為 null。

使用官方 ZIP 重建 2330 cache 的獨立結果：

```text
2024Q4 FCF=null grain=missing_previous_ytd
2025Q1 FCF=294746942 grain=single_quarter
2025Q2 FCF=199838284 normalization=ytd_difference
2025Q3 FCF=139377087 normalization=ytd_difference
2025Q4 FCF=368602783 normalization=ytd_difference
2026Q1 FCF=348213466 grain=single_quarter
```

readiness 保持 `READY_FOR_POINT_IN_TIME_RESEARCH`；shadow 重算得到
coverage `0.9980`、IC `0.0156`、Top–Bottom spread `-0.000141`，與 repair evidence
一致，且沒有沿用舊 FCF artifact 自證。

### FND-FUND-003：NOT CLOSED

#### [P2] 正式下載入口吞掉 ZIP 資源超限診斷

- 位置：`app/fundamentals/mops_xbrl.py:124-137`、`:436-442`
- 觸發條件：`download_xbrl_zip()` 收到 member 數、單檔大小或總未壓縮大小超限的
  ZIP。
- 實際結果：

```text
ValueError MOPS 2025Q1 回應不是有效 ZIP
```

- 原因：`_validate_zip_resources()` 的詳細 `ValueError` 被 `_valid_zip()` 的
  broad `except Exception` 吞掉，download path 只回傳泛化的「不是有效 ZIP」。
- 風險：repair 卡要求超限錯誤包含實際值、檔名與上限並可診斷；正式 importer
  必經的 download path 不符合該契約。新增的三個 regression tests 只直接呼叫
  `parse_xbrl_zip()`，未覆蓋 `download_xbrl_zip()`。
- 建議修法：將 ZIP 結構有效性與 resource validation 分離，或讓
  `download_xbrl_zip()` 保留 `_validate_zip_resources()` 的詳細例外；補一個
  downloader regression，分別驗證 cache reuse 與新下載超限訊息。

資源阻擋本身在 `parse_xbrl_zip()` 已成立，且官方六季 ZIP 均低於限制：

```text
max members=2714
max single member=2985772 bytes
max total uncompressed=1539679438 bytes
```

但可診斷錯誤契約尚未完成，因此 finding 不能標記 closed。

## Verification

```text
git diff --check ce94b06...48c10ab
=> PASS

<repo-root>/.venv/bin/python -m pytest -q tests/test_mops_xbrl_fundamentals.py
=> 11 passed in 1.57s

<repo-root>/.venv/bin/python -m pytest -q
=> 1 failed, 484 passed, 246 subtests passed
=> 唯一失敗仍為既有 research ledger evidence_exists clone/worktree 缺口

isolated import from six official ZIPs
=> 1963/1967, coverage=99.80%

build + verify readiness
=> READY_FOR_POINT_IN_TIME_RESEARCH
=> usable_stock_coverage=0.997966
=> FUNDAMENTAL_POINT_IN_TIME_READINESS_OK

production candidate verifier
=> coverage=0.998, fundamental_candidates=[]

shadow recomputation
=> stocks=1967, coverage=0.9980, IC=0.0156, top_bottom_spread=-0.000141
```

## Axis conclusions

- Spec axis：`FAIL`；FND-FUND-001/002 已關閉，FND-FUND-003 的可診斷 download-path
  契約未完成。
- Standards axis：`FAIL`；核心資源阻擋與測試大致正確，但 broad exception 造成正式
  入口診斷資訊遺失，且缺 downloader regression。

## Verdict

`NO_GO`

Repair-1 不得視為 acceptance 或 promotion。下一次 repair 只需處理
FND-FUND-003 的 download-path 診斷傳遞與 regression test，不得重開已關閉的
FND-FUND-001/002。

# REPAIR-RADAR-01-P1-C-G1-INTEGRITY

狀態：`COMPLETE / ORIGINAL_REVIEWER_RE_REVIEW_GO`

Parent：`CARD-RADAR-01-P1-C-SIGNAL-OCCURRENCE-RADAR-PROJECTION`

## Findings scope

- **P1-F001**：hit 的 instrument 未驗證屬於 exact snapshot scan date，可偽造 snapshot 外 occurrence。
- **P1-F002**：`SignalOccurrence.endpoint_contract` 暴露 mutable mapping，frozen dataclass 仍可原地修改並使 content ID 失真。
- **P1-F003**：malformed report nested dataclass、enum、hash/ref、bool count 與 warning 未集中驗證，可能被接受或漏出原生例外。

## Repair contract

1. 在任何 regex、enum `.value`、iteration 或 count 比較前，驗證 report／status／tuples／summary／hit／warning exact types 與非負／非空 invariant；所有失敗轉成 stable `SignalOccurrenceError` reason code。
2. hit 的 `(trading_date, stock_id)` 必須存在 exact loaded snapshot 的 scan-date rows；empty/non-string/outside snapshot 一律 fail closed。
3. occurrence 不得暴露可變 nested object；以 immutable scalar provenance fields 與綁定完整 endpoint/source 的 content hash 取代 mutable mapping，且 ID 可重算。
4. 補 RED/GREEN：snapshot 外 instrument、empty/non-string instrument、nested mutation、non-string refs、string status、bool counts、wrong nested object、invalid warnings。
5. 只改 `app/signals/occurrences.py`、必要時 `app/signals/radar_projection.py`、`app/signals/__init__.py`、`tests/test_signal_occurrence_radar_projection.py`；不改 parent scanner/spec/snapshot contract，不碰其他 scope。

## Acceptance

- 三個 P1 finding 均有可重現 RED 與 GREEN。
- parent targeted suite 全綠，`git diff --check` 通過。
- 同一獨立 Reviewer 只針對原 findings 與 repair regression 做 re-review；不得加入一般新建議移動球門。

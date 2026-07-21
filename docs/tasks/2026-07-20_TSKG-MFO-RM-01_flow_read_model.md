---
card_id: TSKG-MFO-RM-01
chain_id: TSKG-MFO
title: Security flow non-strategy read model
status: DELIVERED_CANDIDATE
type: implementation
owner: Codex 主線
assignee_model: 5.6 Terra
created_on: 2026-07-20
operation_level: local_only
depends_on: TSKG-MFO-01, ADR-TSKG-OSS-01
---

# TSKG-MFO-RM-01：法人資金唯讀投影

## Goal

把已通過 `SecurityFlowObservationFixture` 驗證的 source-neutral observation，投影成 Top10／LLM 可讀、但不含策略語意的 deterministic read model。

```text
validated observations
  → group by security_id + trade_date
  → deterministic investor ordering
  → freshness / provenance / partial warnings
  → canonical hash
```

## Acceptance

1. 相同 logical input 即使重新排序，輸出與 canonical hash 仍一致。
2. 每個 item 保留 observation ID、日期、法人別、integer-TWD 值、freshness 與 provenance refs。
3. 缺法人別不得補零，必須輸出 `PARTIAL` warning；任一 stale observation 必須向上傳遞 stale 狀態。
4. 查詢回傳 defensive copy；不存在的 security/date 回 `None`。
5. 全輸出禁止 `rank`、`score`、`weight`、`signal`、`prediction`、`recommendation`、`expected_return` 等策略欄位。
6. external call=0；不修改 API、DB、scheduler、ranking 或既有 observation contract。

## Blocking edges

- Live T86 不可直接灌入本 read model：T86 單位是 `SHARE`，MFO-01 是 `TWD`。
- Theme aggregation、圖譜擴散與 ranking feature 仍由後續卡處理。

## Verification

- `tests/test_tskg_flow_read_model.py`
- 既有 `tests.test_tskg_mfo01` regression
- prohibited-field recursive scan
- `git diff --check`

## Result

`DELIVERED_CANDIDATE`

- Pure projection、canonical hash、partial/stale warning、defensive query 已完成。
- 新增測試與既有 TSKG regression 全通過。
- 未新增外部呼叫、API、DB、scheduler、ranking 或策略欄位。
- Evidence：`docs/evidence/TSKG-MFO-RM-01/verification.md`。

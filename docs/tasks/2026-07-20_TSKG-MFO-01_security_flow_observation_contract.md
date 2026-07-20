---
card_id: TSKG-MFO-01
chain_id: TSKG-MFO
title: SecurityFlowObservation raw contract
status: IN_PROGRESS
type: implementation
owner: Codex 主線
assignee: current task
created_on: 2026-07-20
source_kind: commit
source_sha: 13349cc9ee038a2577d763f4f0c0390c182d734f
related_handoff: docs/handoff/handoff_20260720_tide_tskg_concepts.md
operation_level: local_only
---

# TSKG-MFO-01：SecurityFlowObservation raw contract

## Goal

建立一條完全離線、synthetic-only 的每日證券法人資金觀測契約：

```text
synthetic official-shaped rows
  → closed schema gate
  → deterministic validated SecurityFlowObservation records
  → summary / lookup public contract
```

本卡只固定 raw observation，不建立 Theme 聚合、衍生公式、外部來源 adapter、API、資料庫、排程、Top10 特徵或 UI。

## Design decision

`SecurityFlowObservation` 是可重算、可刪除、具日期與 provenance 的時間序列觀測，不是 `RelationshipClaim` 或 canonical graph fact。

MFO-01 raw contract 只接受單日淨買賣值：

- `net_buy_value_1d`，單位固定為整數 TWD。
- `net_buy_value_5d/20d`、`price_change_5d`、`flow_acceleration`、`flow_force_ratio`、`anomaly_type` 尚未有 owner-approved formula，禁止出現在本卡 schema。
- `formula_version` 固定為 `raw-only-v1`，明示本 slice 沒有衍生公式。
- `ThemeFlowObservation` 留給 MFO-02/03 的 membership snapshot 與 deterministic aggregation，不在本卡假造。

## Public contract

Fixture top-level closed schema：

- `fixture_version=security-flow-v1`
- `schema_version=tskg-security-flow-observation-v1`
- `formula_version=raw-only-v1`
- `provenance`
- `evidence`
- `observations`

Observation closed schema：

- `observation_id`
- `security_id`
- `trade_date`（ISO `YYYY-MM-DD`）
- `investor_type`：`FOREIGN | INVESTMENT_TRUST | DEALER | ALL_INSTITUTIONAL`
- `currency=TWD`
- `net_buy_value_1d`（integer；不可用 float/bool）
- `source_id`
- `evidence_id`
- `observed_at`／`retrieved_at`（RFC 3339 UTC；retrieved 不早於 observed）
- `freshness`：`FRESH | STALE`
- `is_stale`（須與 freshness 一致）

唯一性：

- `observation_id` 不可重複。
- `(security_id, trade_date, investor_type)` semantic key 不可重複。
- 所有 `source_id/evidence_id` 必須指向 fixture 內的 synthetic provenance/evidence。

## Prohibited fields

任何層級禁止加入交易或預測語意：

- `score`, `rank`, `prediction`, `recommendation`
- `buy_signal`, `sell_signal`, `target_price`, `stop_loss`
- `expected_return`, `upside`, `weight`

`net_buy_value_1d` 的 `buy` 是官方市場欄位語意，不是交易建議，屬明確例外。

## TDD acceptance

1. RED：缺少 implementation 時，fixture contract tests 失敗。
2. GREEN：合法 synthetic fixture 可載入、排序、summary 與 semantic-key lookup。
3. Negative gates：closed schema、版本、日期、UTC、單位、型別、枚舉、重複鍵、dangling provenance、freshness coherence、prohibited fields 均 fail loud。
4. Boundary gate：fixture 不能包含 `RelationshipClaim`、Theme 聚合、衍生公式或 prediction/trading fields。
5. Regression：既有 TSKG SLC-01 與 SRC-01 tests 不回歸。

## Allowlist

- `app/tskg/flow_observation.py`
- `app/tskg/__init__.py`
- `data/fixtures/tskg/security_flow_observations_v1.json`
- `tests/test_tskg_mfo01.py`
- `docs/tasks/2026-07-20_TSKG-MFO-01_security_flow_observation_contract.md`
- `docs/evidence/TSKG-MFO-01/verification.md`

## Forbidden scope

- 不修改 `docs/specs/TSKG_v1.1.md`；正式 spec 擴充留待 contract checkpoint。
- 不修改 `app/api/**`、`web/frontend/**`、Top10 model/feature/ranking、Neo4j/Postgres/Redis、crawler/ETL/scheduler。
- 不連外、不使用 MOPS/TWSE/Tide 真實資料、不建立 source approval。
- 不建立 Theme aggregation、graph-flow export 或 predictive evaluation。

## Blocking edges after this card

- MFO-02：Theme membership source governance 與 immutable snapshot。
- MFO-03：MFO-01/02 完成後才能定義 5d/20d、Theme aggregation 與 coverage。
- MFO-04/05：仍受 TSKG graph slices、回測契約與 leakage gate 阻擋。
- UI-MFR：仍為 `BACKLOG / NOT AUTHORIZED`。

## Result

`IN_PROGRESS`

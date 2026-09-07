# CARD-RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY

狀態：`MAINLINE_ACCEPTED_LOCAL / CONTRACT_ONLY_PARITY_VERIFIED / NON_RUNTIME`

Owner admission：2026-09-07 本對話在 `RADAR-01 = MEASURED_GAP_CONFIRMED / READY_FOR_OWNER_ADMISSION_DECISION / NOT_ADMITTED` 後明確回覆「授權」。授權只適用本卡 P1-A；P1-B 至 P1-E 不自動准入。

## Root question

如何在不建立 scanner、Occurrence store 或第二套 research truth 的前提下，讓少量既有 Daily Close 訊號擁有 versioned、唯一可指認的 SignalSpec authority，並把「觸發／未觸發／不可觀測」與雙來源 parity drift 變成 fail-closed 契約？

## 使用者需求

### SignalSpec authority and observability <!-- US-001 -->

系統必須先固定可稽核的 SignalSpec 與 observability semantics，未達 research evidence gate 的訊號不得取得 Radar eligibility。

- **FR-001**：建立 immutable、content-addressed SignalSpec contract，至少涵蓋 version、名稱、分類、方向、唯一 rule reference、calendar policy、required features、Daily Close dataset contract、evaluation horizon、research evidence、eligibility 與 educational reference。 <!-- FR-001 traces_to: US-001 -->
- **FR-002**：第一批 catalog 只映射少量已存在且本次 parity probe 為零差異的 deterministic signals；不得新增 signal 規則、數量目標或 ranking weight。 <!-- FR-002 traces_to: US-001 -->
- **FR-003**：提供 `TRIGGERED / NOT_TRIGGERED / NOT_OBSERVABLE` 三態 resolver；缺 required feature、rule result 或 evaluation error 必須結構化 fail loud，不得轉成 `0`。 <!-- FR-003 traces_to: US-001 -->
- **FR-004**：提供 read-only parity validator，驗證兩份既有 projection 的 key、binary values、required-feature observability 與逐 SignalSpec parity；缺欄、重複鍵、key drift、invalid value 或 signal drift 必須 fail closed。 <!-- FR-004 traces_to: US-001 -->
- **FR-005**：P1-A 不建立 scanner、SignalOccurrence、統計、confluence、UI、API、writer、scheduler 或 production wiring；不改既有 indicator math、events output、ranking、Research Spine 或 Research Ledger。 <!-- FR-005 traces_to: US-001 -->

1. **Given** 同一份 SignalSpec payload，**When** 重建，**Then** content ID 穩定；任一 authority／semantic 欄位改變時 identity 必須改變。 <!-- AS-US001-01 traces_to: FR-001 -->
2. **Given** catalog 初始訊號，**When** 讀取，**Then** 皆為 contract-only／not Radar eligible，且沒有未指認的 rule 或 required feature。 <!-- AS-US001-02 traces_to: FR-001, FR-002 -->
3. **Given** rule result 為 `1` 或 `0`，**When** required inputs 均可用，**Then** 分別得到 `TRIGGERED` 或 `NOT_TRIGGERED`。 <!-- AS-US001-03 traces_to: FR-003 -->
4. **Given** required feature 缺失、rule result 缺失或 evaluation error，**When** resolve，**Then** 得到帶 reason code 的 `NOT_OBSERVABLE`，不產生 false negative。 <!-- AS-US001-04 traces_to: FR-003 -->
5. **Given** parity inputs 有 duplicate key、key drift、missing signal column、non-binary value 或 value mismatch，**When** validate，**Then** 以穩定 reason code 拒絕。 <!-- AS-US001-05 traces_to: FR-004 -->
6. **Given** 本機 `features.parquet` 與 `events.parquet`，**When** 只載入初始 catalog 所需欄位執行 validator，**Then** keys／values parity 通過，required-feature unavailable rows 被計數而非冒充觸發判斷。 <!-- AS-US001-06 traces_to: FR-002, FR-003, FR-004 -->
7. **Given** P1-A 完成 diff，**When** 檢查 changed paths 與 imports，**Then** 不包含 scanner、Occurrence persistence、statistics、confluence、UI、API、ranking 或 runtime wiring。 <!-- AS-US001-07 traces_to: FR-005 -->

- **SC-001**：新增 targeted unit tests 全綠，並以本機代表性 parquet 做 read-only reconciliation。 <!-- SC-001 traces_to: US-001, FR-001, FR-002, FR-003, FR-004 -->
- **SC-002**：`git diff --check` 通過，無 scanner／ranking／runtime／external write diff。 <!-- SC-002 traces_to: US-001, FR-005 -->
- **SC-003**：canonical Research Matrix dimension growth=`0`；Radar eligible count=`0`，直到未來 evidence admission。 <!-- SC-003 traces_to: US-001, FR-001, FR-005 -->

## Guardrails

- `EXTEND_EXISTING > ADD_SUBSYSTEM`；只延伸 `app/signals`。
- 初始 catalog 不宣稱任何 historical edge，不配置 production weight。
- `SignalEvaluation` 是單筆 rule-result contract，不是 `SignalOccurrence`，不得加入 instrument/date/dataset persistence。
- parity validator 只讀 caller 提供的 DataFrame，不寫 artifact、不修改既有 parquet。
- 不做 P1-B scanner、P1-C Occurrence/Projection、P1-D base-rate statistics、P1-E confluence。
- 不碰 Fog、provider、scheduler、publish、production、deploy 或外部 write。
- 本卡不授權 push。

## 垂直切片與依賴

| Slice | Scope | traces_to | Blocking edge | Verification |
|---|---|---|---|---|
| `RADAR01-P1A-SLICE-001` | SignalSpec identity、bounded catalog、三態 resolver | `FR-001`–`FR-003`, `AS-US001-01`–`04`, `SC-003` | 無；目前 frontier | contract／resolver RED-GREEN |
| `RADAR01-P1A-SLICE-002` | read-only parity／observability validator | `FR-004`, `AS-US001-05` | `SLICE-001` | parity failure-mode RED-GREEN |
| `RADAR01-P1A-SLICE-003` | 代表性 parquet reconciliation、evidence 與 canonical status | `AS-US001-06`, `SC-001`, `SC-002` | `SLICE-001`, `SLICE-002` | real-data read-only probe＋targeted suite＋diff gate |

Checkpoint：完成 `SLICE-001/002` 後先跑 targeted tests；只有 contract、failure semantics 與 real-data parity 都通過，才可進 `SLICE-003` acceptance。P1-A 接受後停止，不自動前進 P1-B。

## Likely files

- `app/signals/specs.py`
- `app/signals/__init__.py`
- `tests/test_signal_specs.py`
- `docs/evidence/RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY-20260907.md`
- `docs/RESEARCH_SPINE_BACKLOG.md`
- `docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`

## Evidence

- `docs/evidence/RADAR-01-EXISTING-SEAM-AUDIT-20260907.md`
- `docs/evidence/RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY-20260907.md`

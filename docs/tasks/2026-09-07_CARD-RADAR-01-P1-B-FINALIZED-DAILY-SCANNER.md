# CARD-RADAR-01-P1-B-FINALIZED-DAILY-SCANNER

狀態：`MAINLINE_ACCEPTED_LOCAL / VALIDATION_REPLAY_VERIFIED / NON_RUNTIME`

Owner admission：2026-09-07 本對話在 P1-A 完成後，使用者確認下一步為 P1-B，並明確回覆「授權」。授權只適用本卡 P1-B；P1-C 至 P1-E 不自動准入。

## Root question

如何在不持久化 SignalOccurrence、不建立第二套 research truth 的前提下，以 ME-D1 finalized Daily Close snapshot 與 P1-A Radar-eligible SignalSpec 為唯一輸入邊界，完成 market-wide、read-only、可重跑且資料缺口可觀測的單日 scanner？

## 使用者需求

### Finalized Daily market-wide scanner <!-- US-001 -->

系統必須只掃描 finalized snapshot 的 observed-through date，且只有通過 P1-A eligibility gate 的 SignalSpec 能參與；任何輸入漂移或資料消失都不得被解讀成未觸發。

- **FR-001**：scanner 必須自行載入並驗證 content-addressed ME-D1 manifest／records，拒絕 invalid、unresolved-empty、非 finalized 或 identity drift。 <!-- FR-001 traces_to: US-001 -->
- **FR-002**：indicator feature projection 必須是 regular local parquet，scanner 自行計算 artifact SHA-256，禁止 caller 注入未驗證 content ID；projection key 不得超出 snapshot，matched raw Daily Close 欄位必須一致，且 report identity 必須綁定明確的 indicator semantics content/git ref。 <!-- FR-002 traces_to: US-001 -->
- **FR-003**：只允許 `RADAR_ELIGIBLE` SignalSpec；目前 P1-A catalog 全為 `CONTRACT_ONLY`，default scan 必須明示 `NO_RADAR_ELIGIBLE_SIGNAL_SPEC`，不得繞過 gate。 <!-- FR-003 traces_to: US-001 -->
- **FR-004**：scanner 只評估 snapshot `observed_through_date`，每個 snapshot row／eligible spec 必須落入 `TRIGGERED / NOT_TRIGGERED / NOT_OBSERVABLE` 之一；row 缺失、required feature/history 或 rule result 缺失不得 silent zero。 <!-- FR-004 traces_to: US-001 -->
- **FR-005**：history semantics 必須沿用 SignalSpec calendar policy；`DATASET_SESSION_CONTIGUOUS` 使用 ME-D1 manifest 的 weekday candidates，遇 unresolved date／缺 row 時 fail loud，`PREVIOUS_OBSERVED_ROW` 只使用 snapshot-bound prior rows。 <!-- FR-005 traces_to: US-001 -->
- **FR-006**：輸出為 deterministic、immutable in-memory scan report，固定 snapshot／feature／spec identities、各狀態 count、triggered hits 與結構化 warnings；不寫 artifact、DB 或 queue。 <!-- FR-006 traces_to: US-001 -->
- **FR-007**：P1-B 不建立 canonical SignalOccurrence、歷史統計、base-rate comparison、confluence、Radar UI/API、ranking、scheduler、provider fetch 或 production wiring。 <!-- FR-007 traces_to: US-001 -->

1. **Given** valid finalized snapshot 與完全對齊的 feature parquet，**When** 掃描 test-only eligible spec，**Then** 每個 market row 恰好落入三態之一，counts 相加等於 snapshot as-of rows。 <!-- AS-US001-01 traces_to: FR-001, FR-002, FR-003, FR-004 -->
2. **Given** current P1-A catalog，**When** default scan，**Then** 回傳 explicit no-eligible status、零 hits，且不把 contract-only spec 當 eligible。 <!-- AS-US001-02 traces_to: FR-003 -->
3. **Given** invalid manifest、records hash drift、feature symlink／非 parquet 或 extra feature key，**When** scan，**Then** 以穩定 reason code fail closed。 <!-- AS-US001-03 traces_to: FR-001, FR-002 -->
4. **Given** snapshot row 未進 feature projection，**When** scan，**Then** 該 row 對每個 eligible spec 都是 `NOT_OBSERVABLE`，並有包含 record key、reason、stage、affected count 的 warning。 <!-- AS-US001-04 traces_to: FR-002, FR-004, FR-006 -->
5. **Given** matched row 的 OHLCV／market identity 漂移，**When** scan，**Then** 拒絕，不產生 hits。 <!-- AS-US001-05 traces_to: FR-002 -->
6. **Given** required previous weekday candidate 無 observation，**When** 使用 dataset-session policy，**Then** history 不可觀測；previous-observed policy 則依最近 snapshot-bound row判讀。 <!-- AS-US001-06 traces_to: FR-004, FR-005 -->
7. **Given** 相同 snapshot、feature bytes 與 SignalSpec identities，**When** 重跑，**Then** scan content ID、排序、counts 與 hits 完全相同。 <!-- AS-US001-07 traces_to: FR-006 -->
8. **Given** P1-B 完成 diff，**When** 檢查 changed paths，**Then** 不包含 Occurrence persistence、statistics、confluence、UI、API、ranking 或 runtime wiring。 <!-- AS-US001-08 traces_to: FR-007 -->

- **SC-001**：targeted unit／fixture tests 全綠，包含 positive、negative、degradation 與 deterministic replay。 <!-- SC-001 traces_to: US-001, FR-001, FR-002, FR-003, FR-004, FR-005, FR-006 -->
- **SC-002**：以既有 validation-snapshot ETL seam 做 offline end-to-end scan；若 checkout 無 materialized official snapshot，狀態不得冒稱 production／live acceptance。 <!-- SC-002 traces_to: US-001, FR-001, FR-002, FR-004, FR-006 -->
- **SC-003**：`git diff --check` 通過；Research Spine／canonical Matrix dimension delta=0，ranking/runtime impact=NONE。 <!-- SC-003 traces_to: US-001, FR-007 -->

## Guardrails

- `EXTEND_EXISTING > ADD_SUBSYSTEM`；沿用 ME-D1 snapshot、P1-A SignalSpec 與既有 feature parquet，不新增 ledger／registry／DB。
- scanner output 是暫態 projection，不是 `SignalOccurrence`，不得產生持久 ID 或寫入 artifact。
- 目前 catalog 沒有 Radar-eligible spec；只有測試可使用明確 `TEST_ONLY` eligible clone 驗證 scanner 行為，不得回寫 catalog 或宣稱 research edge。
- 不碰 Fog、provider acquisition、scheduler、publish、production、deploy、push 或外部 write。
- 本卡不授權 P1-C 至 P1-E。

## 垂直切片與依賴

| Slice | Scope | traces_to | Blocking edge | Verification |
|---|---|---|---|---|
| `RADAR01-P1B-SLICE-001` | finalized snapshot／feature artifact／eligible spec input gate | `FR-001`–`FR-003`, `AS-US001-02`–`05` | P1-A accepted；Owner P1-B admission | input-boundary RED/GREEN |
| `RADAR01-P1B-SLICE-002` | as-of 三態 scanner、history policy、deterministic report | `FR-004`–`FR-006`, `AS-US001-01`, `AS-US001-06`, `AS-US001-07` | `SLICE-001` | scanner RED/GREEN＋replay |
| `RADAR01-P1B-SLICE-003` | offline validation-snapshot acceptance、review 與 canonical status | `FR-007`, `AS-US001-08`, `SC-001`–`03` | `SLICE-001`, `SLICE-002` | targeted suite＋offline E2E＋diff gate |

Checkpoint：`SLICE-001/002` 綠燈後才進 offline acceptance；若沒有可驗證的 finalized snapshot identity，P1-B 只能標 `PARTIAL/BLOCKED_EVIDENCE`，不得用 mutable clean parquet 冒充。

## Likely files

- `app/signals/scanner.py`
- `app/signals/__init__.py`
- `tests/test_daily_signal_scanner.py`
- `docs/evidence/RADAR-01-P1-B-FINALIZED-DAILY-SCANNER-20260907.md`
- `docs/RESEARCH_SPINE_BACKLOG.md`
- `docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`

## Evidence

- `docs/evidence/RADAR-01-P1-A-SIGNAL-SPEC-AUTHORITY-20260907.md`
- `docs/evidence/ME-D1-DAILY-CLOSE-SNAPSHOT-IMPLEMENTATION-20260907.md`

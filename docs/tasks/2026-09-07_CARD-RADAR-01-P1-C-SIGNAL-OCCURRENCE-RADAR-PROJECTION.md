# CARD-RADAR-01-P1-C-SIGNAL-OCCURRENCE-RADAR-PROJECTION

狀態：`MAINLINE_ACCEPTED_LOCAL / RE-REVIEW_GO / VALIDATION_REPLAY_VERIFIED / NON_RUNTIME`

Owner admission：2026-09-07 本對話在 P1-B 完成本機驗收後，使用者明確回覆「授權」。授權只適用本卡 P1-C；P1-D historical statistics、P1-E confluence、UI/API/runtime 與 push 均未准入。

## Root question

如何把已驗證的 P1-B triggered hits 轉為可由上游契約完整重建的 content-addressed `SignalOccurrence`，並提供 deterministic、無分數／無排名權限的 Daily Radar read-model，同時拒絕任何 scanner report、snapshot 或 SignalSpec identity 漂移？

## 使用者需求

### Rebuildable occurrence 與無排名 Radar projection <!-- US-001 -->

- **FR-001**：builder 必須重新載入並驗證 exact ME-D1 manifest，且 scanner contract、scan date、snapshot ID、records ID、row coverage 與 feature／indicator refs 必須完整一致；任何漂移以穩定 reason code fail closed。 <!-- FR-001 traces_to: US-001 -->
- **FR-002**：只有 exact `RADAR_ELIGIBLE` SignalSpec 能參與；report summaries／hits 必須與排序後 spec identities 一致，三態 counts 必須閉合，hit count、identity、direction 與 uniqueness 必須可重算。 <!-- FR-002 traces_to: US-001 -->
- **FR-003**：每個 triggered hit 產生一個 immutable、content-addressed `SignalOccurrence`，至少包含 instrument、trading date、SignalSpec identity/version/direction、evaluation=`TRIGGERED`、snapshot/records fingerprint、provider/adapter provenance、feature artifact ID、indicator semantics ref、research evidence ref 與 projection build version。 <!-- FR-003 traces_to: US-001 -->
- **FR-004**：`NOT_TRIGGERED`／`NOT_OBSERVABLE` 只保留在 scan summary/warnings，不建立 occurrence；current default catalog eligible count=0 時輸出 explicit no-eligible projection。 <!-- FR-004 traces_to: US-001 -->
- **FR-005**：Radar projection 只依 instrument 聚合 occurrence，分開 bullish／bearish／neutral IDs；排序只為 deterministic serialization，不含 score、rank、recommendation 或 hit-count ranking authority。 <!-- FR-005 traces_to: US-001 -->
- **FR-006**：輸出為 strict immutable in-memory read-model，帶 input identities、coverage、warnings、`ranking_impact=NONE` 與 deterministic content ID；不得落盤、寫 DB、queue、API、UI、scheduler 或 production。 <!-- FR-006 traces_to: US-001 -->
- **FR-007**：P1-C 不建立 historical statistics／base-rate comparison、confluence、個人化、AI explanation 或任何 SignalSpec eligibility promotion；P1-D/P1-E 仍需另行 admission。 <!-- FR-007 traces_to: US-001 -->

1. **Given** valid report、exact snapshot 與 exact eligible specs，**When** build，**Then** 每個 triggered hit 恰好對應一個 occurrence，且 provenance／research evidence／build version 完整。 <!-- AS-US001-01 traces_to: FR-001, FR-002, FR-003 -->
2. **Given** 相同 inputs，**When** 重跑，**Then** occurrence IDs、projection ID、items 與排序完全相同。 <!-- AS-US001-02 traces_to: FR-003, FR-005, FR-006 -->
3. **Given** default catalog 沒有 eligible spec，**When** build default report，**Then** projection 明示 no-eligible、零 occurrence／items，且不繞過 gate。 <!-- AS-US001-03 traces_to: FR-002, FR-004 -->
4. **Given** report 的 snapshot/date/hash/ref、summary count、hit identity/direction/count 或 duplicate 被竄改，**When** build，**Then** 以穩定 reason code fail closed，不輸出 projection。 <!-- AS-US001-04 traces_to: FR-001, FR-002 -->
5. **Given** snapshot 帶 gap 或 scanner warnings，**When** build，**Then** projection 保留 PARTIAL 與原 warning evidence，不把缺資料視為未觸發。 <!-- AS-US001-05 traces_to: FR-004, FR-006 -->
6. **Given** 同一 instrument 有多方向 hits，**When** project，**Then** 只分組 occurrence IDs，不產生 score/rank；items 依 instrument ID deterministic 排序。 <!-- AS-US001-06 traces_to: FR-005 -->
7. **Given** P1-C diff，**When** 檢查 changed paths／schema，**Then** 不含 persistence、statistics、confluence、UI/API、runtime、Fog 或 production wiring。 <!-- AS-US001-07 traces_to: FR-006, FR-007 -->

- **SC-001**：targeted unit tests 全綠，覆蓋 positive、no-eligible、partial、tampering、uniqueness 與 deterministic replay。 <!-- SC-001 traces_to: US-001, FR-001, FR-002, FR-003, FR-004, FR-005, FR-006 -->
- **SC-002**：以 P1-B validation-snapshot seam 做 offline representative replay；若沒有 official materialized snapshot，不得冒稱 production/live acceptance。 <!-- SC-002 traces_to: US-001, FR-001, FR-003, FR-006 -->
- **SC-003**：`git diff --check` 通過；Research Spine／canonical Matrix dimension delta=0，ranking/runtime impact=NONE。 <!-- SC-003 traces_to: US-001, FR-007 -->

## Guardrails

- `EXTEND_EXISTING > ADD_SUBSYSTEM`；沿用 ME-D1、P1-A、P1-B 與 canonical hash helper，不新增 ledger／registry／DB／writer。
- validation-only eligible clone 不得回寫 catalog，也不得取得 research edge 或 production authority。
- `SignalOccurrence` 是 downstream rebuildable projection，不是第二套 signal/research truth。
- 不碰 Fog、provider fetch、existing ranking weights、scheduler、publish、production、deploy、push 或外部 write。

## 垂直切片與依賴

| Slice | Scope | traces_to | Blocking edge | Verification |
|---|---|---|---|---|
| `RADAR01-P1C-SLICE-001` | strict input/report/spec integrity gate＋occurrence contract | `FR-001`–`FR-004`, `AS-US001-01`, `AS-US001-03`, `AS-US001-04` | P1-B accepted；Owner P1-C admission | RED/GREEN contract tests |
| `RADAR01-P1C-SLICE-002` | deterministic no-rank Radar projection | `FR-005`, `FR-006`, `AS-US001-02`, `AS-US001-05`, `AS-US001-06` | `SLICE-001` | projection RED/GREEN＋replay |
| `RADAR01-P1C-SLICE-003` | offline representative replay、strict review、canonical status | `FR-007`, `AS-US001-07`, `SC-001`–`SC-003` | `SLICE-001`, `SLICE-002` | targeted suite＋offline replay＋diff gate |

Checkpoint：`SLICE-001/002` 綠燈後才可進 representative replay；任何 input identity 無法重算時必須停在 fail-closed，不得接受 caller assertion。

## Likely files

- `app/signals/occurrences.py`
- `app/signals/radar_projection.py`
- `app/signals/__init__.py`
- `tests/test_signal_occurrence_radar_projection.py`
- `docs/evidence/RADAR-01-P1-C-SIGNAL-OCCURRENCE-RADAR-PROJECTION-20260907.md`
- `docs/RESEARCH_SPINE_BACKLOG.md`
- `docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`

## Evidence inputs

- `docs/evidence/RADAR-01-P1-B-FINALIZED-DAILY-SCANNER-20260907.md`
- `docs/evidence/ME-D1-DAILY-CLOSE-SNAPSHOT-IMPLEMENTATION-20260907.md`

## Acceptance evidence

- `docs/evidence/RADAR-01-P1-C-SIGNAL-OCCURRENCE-RADAR-PROJECTION-20260907.md`
- `.work/RADAR-01-P1-C/review/review_state.jsonl`

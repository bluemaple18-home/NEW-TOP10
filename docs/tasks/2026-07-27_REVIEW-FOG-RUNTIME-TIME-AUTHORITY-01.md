---
id: REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01
status: GO_FOR_IMPLEMENTATION_CARD
type: review
chain_id: FOG-RUNTIME-TIME-AUTHORITY-01
dispatch_version: 2
review_cycle: repair_1_targeted
ownership: independent_reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 時間權威契約橫跨市場日、UTC freshness、receipt schema、shell/Python 與 LaunchAgent 邊界；錯誤會直接阻斷或誤放行自動研究。
chain_base_sha: cfaabf914f752b63a8efaf15ca40a5984221c2e1
base_sha: cfaabf914f752b63a8efaf15ca40a5984221c2e1
reviewed_candidate_sha: 26d8471d15572f216095122f2462df79bc96edc1
repair_candidate_sha: f9cfbabde1d89d2f759a7cbc60d1dd03e96a2171
architecture_thread_id: 019fa43d-3544-7662-be9c-3b258eee681c
reviewer_thread_id: 019fa448-4ffe-7473-af1a-7cc1f417bdd7
evidence_path: docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01/
---

# REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01

## Review question

Candidate `26d8471d15572f216095122f2462df79bc96edc1` 是否建立了單一、
可重算且可實作的市場時間權威，能正確區分：

- `Asia/Taipei` 的 market-day identity；
- UTC absolute freshness；
- scheduler host timezone；
- regime／daily source date；
- receipt claim 與 verifier 重新計算的 authority。

Reviewer 只審固定 candidate 與新增 Review evidence；不得修改 architecture
candidate、runtime code、tests、config、plist、live state或 production artifacts。

## Fixed boundary

- Candidate parent：
  `cfaabf914f752b63a8efaf15ca40a5984221c2e1`
- Candidate：
  `26d8471d15572f216095122f2462df79bc96edc1`
- Candidate branch：`codex/fog-runtime-time-authority-01`
- Architecture：
  `docs/architecture/fog_runtime_time_authority_v1.md`
- Architecture card：
  `docs/tasks/2026-07-27_FOG-RUNTIME-TIME-AUTHORITY-01_market_day_timestamp_contract.md`
- Executor evidence：
  `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01/architecture.md`
- Review evidence：
  `docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01/review.md`

## Dispatch v2 ledger

| Cycle | Candidate | State | Blocking finding IDs |
|---|---|---|---|
| architecture | `26d8471d15572f216095122f2462df79bc96edc1` | `NO_GO` | `FRTA-P1-01`, `FRTA-P1-02`, `FRTA-P1-03` |
| repair-1 targeted | `f9cfbabde1d89d2f759a7cbc60d1dd03e96a2171` | `GO_FOR_IMPLEMENTATION_CARD` | none；三個 fixed findings closed |

- 本卡是此 chain 唯一可重用 Reviewer identity。
- 若 `NO_GO`，只建立一個可重用 Repair task，並由本 Reviewer做 targeted
  re-review；不得每一代另開 Reviewer。
- strict chain 最多 Repair-2。Repair-2 後仍有 P0/P1，固定
  `BLOCKED / REVIEW_REPAIR_LIMIT`，禁止 Repair-3。
- Re-review只能檢查既有 P0/P1與其直接 regression，不得以新建議移動球門。

## 必審軸

### 1. Authority與語意分離

- `market_run_date` 是否只由 aware UTC instant投影 IANA timezone產生。
- freshness 是否只由 signed UTC age計算，且不以 date equality代替。
- `market_run_date` 是否明確為 civil-day identity，而非未證明的 trading-day。
- `source_trade_date`／daily source date 是否獨立，休市日不會被硬綁 run date。

### 2. Boundary與determinism

- 獨立檢查 8-case matrix及 exact boundaries：
  `-5`、`-5.001`、`900`、`900.001`。
- 台北 00:00–07:59、host timezone drift、naive timestamp、future/stale receipt、
  wrong market date與 DST fold必須有唯一 expected result。
- fixed clock／seed、UTC→IANA projection及 host locale independence必須可測。

### 3. Receipt／policy trust boundary

- policy version/hash是否來自 repo versioned authority，而非 receipt/env。
- receipt v3是否綁 raw UTC instants、normalized market fields、source lineage與
  contract hash。
- verifier是否明確不信任 receipt自報 date/hash/result，並獨立重算。
- schema migration是否禁止補造 legacy v2 authority或 dual-trust bypass。

### 4. Runtime wiring與lifecycle

- LaunchAgent不得成為日期／timezone authority。
- worker建立 immutable context；child shell只能傳遞，不能再跑 `date +%F`。
- market midnight是否為 hard lifecycle boundary，避免跨日批次寫入舊 receipt。
- migration ordering、safe-stopped rollback與 live acceptance boundary是否閉合。

### 5. Implementation readiness

- I1–I5 slices是否各有 changed-file allowlist、red tests、entry/exit與禁止的 live
  side effect。
- 契約不得要求無法由目前 Python `zoneinfo`、shell wiring與 receipt verifier
  實作的能力。
- 不得弱化前一 chain的 circuit、queue、model、ranking、baseline或 production
  protection。

## Independent verification

至少執行：

```bash
cd <repo-root>
test -f docs/architecture/fog_runtime_time_authority_v1.md
test -f docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01/architecture.md
rg -n \
  'market_timezone|market_run_date|generated_at_utc|verification_time_utc|receipt_age_seconds' \
  docs/architecture/fog_runtime_time_authority_v1.md
git diff --check \
  cfaabf914f752b63a8efaf15ca40a5984221c2e1..\
  26d8471d15572f216095122f2462df79bc96edc1
```

Reviewer 另需自行寫 bounded read-only probes或對照表，驗證 8-case matrix、
boundary inequalities、policy hash determinism、DST fold與 host timezone drift；
不得只採信 Executor stored PASS。

## Verdict

- `GO_FOR_IMPLEMENTATION_CARD`：零 P0/P1，契約完整且可實作；只授權主線建立
  successor implementation card，不等於 runtime或 production acceptance。
- `NO_GO`：列 finding ID、severity、path/section、trigger、evidence、risk與
  validation gap；主線依本卡 ledger派到唯一 Repair task。

Review commit只允許新增本卡 evidence與更新本卡狀態；不得修改 candidate。

## Pre-dispatch receipt

- Current card：
  `docs/tasks/2026-07-27_REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01.md`
- Mainline dispatcher：
  `019f82c1-b7d0-7eb3-9371-7a95ebfbd7ce`
- Previous card／task：
  `FOG-RUNTIME-TIME-AUTHORITY-01`／
  `019fa43d-3544-7662-be9c-3b258eee681c`
- Source kind：`commit`
- Source SHA：`26d8471d15572f216095122f2462df79bc96edc1`
- Source branch：`codex/fog-runtime-time-authority-01`
- Source clean：是
- Git metadata：可用
- unrelated dirty paths：`[]`
- Client receipt：
  `client-new-thread:a513c2de-a944-4ee6-bf52-b05dc2930aad`
- Reviewer task：`019fa448-4ffe-7473-af1a-7cc1f417bdd7`
- Reviewer title：`Review 市場時間權威契約`
- Reviewer worktree：isolated／registered
- Reviewer initial HEAD：
  `deffa7e5f84aeae47461d5877a015754618ef1e6`
- Reviewer initial branch：`detached`
- Reviewer initial worktree：clean
- Capability preflight：`PASS`；isolated detached worktree、Git、uv-managed
  Python 3.12、`zoneinfo`與 SHA-256 可用；不需 network/live runtime
- Workflow：
  `DELIVERED_ARCHITECTURE_CANDIDATE → READY_FOR_REVIEW → NO_GO`
- Gate 1 card contract：`PASS`
- Gate 2 visible thread：`PASS`
- Gate 3 candidate delivery：`PASS`
- Gate 4 independent review：`NO_GO`；固定 findings：
  `FRTA-P1-01`、`FRTA-P1-02`、`FRTA-P1-03`
- Gate 5 implementation authorization：`DENIED`

## Repair-1 targeted re-review receipt

- Repair card：
  `docs/tasks/2026-07-28_FOG-RUNTIME-TIME-AUTHORITY-01_REPAIR-1_contract_closure.md`
- Repair candidate parent：
  `5ffc0a33874fe742ba7ffa2170ad6236612817e4`
- Repair candidate：
  `f9cfbabde1d89d2f759a7cbc60d1dd03e96a2171`
- Reviewer identity：同一 task/thread
  `019fa448-4ffe-7473-af1a-7cc1f417bdd7`
- Worktree/capability：isolated detached、clean；Git、uv-created temporary
  `.venv` CPython 3.12.12、`zoneinfo`與 SHA-256 可用；不需 network/live runtime
- Fixed finding disposition：
  - `FRTA-P1-01 CLOSED`
  - `FRTA-P1-02 CLOSED`
  - `FRTA-P1-03 CLOSED`
- Independent probes：
  `docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01/repair1_targeted_probe.py`
  與 `repair1_targeted_results.json`
- Workflow：
  `REVIEW_NO_GO → REPAIR_1 → TARGETED_REVIEW → GO_FOR_IMPLEMENTATION_CARD`
- Gate 1 Repair card contract：`PASS`
- Gate 2 fixed candidate／allowlist：`PASS`
- Gate 3 independent targeted probes：`PASS`
- Gate 4 targeted re-review：`GO_FOR_IMPLEMENTATION_CARD`
- Gate 5 implementation authorization：`AUTHORIZED_CARD_CREATION_ONLY`
- Runtime／production：`NOT_IMPLEMENTED / NOT_ACCEPTED`

# B0 Phase 1：E1–E4 初步成本分類

## 初步分類

| Class | 現行證據狀態 | Phase-1 成本判定 | 容量含義 |
|---|---|---|---|
| E1 — pure vector / mathematical evaluation | `FORMAL_720_GENERATION_IDENTITY_PARTITION_CONFIRMED` | committed code 以四個 executable dimensions 的 Cartesian product 產生 720 個 parameter combinations，並以 deterministic `combination_id`、global family hash 與 validation-profile partition check 固定 formal 720 family | C0 可使用 `720`、legal ID hash 與 partition facts 作 formal denominator；不可把 E1 authority 等同 E3 full-replay capacity或B1 admission |
| E2 — reusable intermediate path evaluation | `NOT_PROVEN_AS_FULL_CANDIDATE_EVALUATOR` | features/price frame 只在 matrix 外層載入一次，但每個 scenario 仍呼叫完整 portfolio replay；沒有證據顯示 path-dependent intermediate 可跨候選安全重用 | 不得用 E2 吞吐假設估算 720 個績效 evaluation |
| E3 — full path-dependent replay / backtest | `CONFIRMED_CURRENT_EXECUTION_CLASS` | 每個 scenario 依 horizon、exit events、portfolio/group exposure 與 ranking-date path 重跑 replay | C0 應以 E3 作目前 executable matrix 的保守容量基線；candidate/sec、CPU、RAM、I/O 尚未量測 |
| E4 — forward-shadow-only validation | `REQUIRED_FUNNEL_STAGE / PATH_CAPACITY_UNCHARACTERIZED` | governing funnel 要求 `FORWARD_SHADOW` 後才可能成為 regime policy candidate，但 Phase 1 未證明一個統一 matrix-to-forward-shadow evaluator 或其 wall-clock cadence | C0 必須把 E4 視為日曆時間／市場觀察約束，不可用 E1/E3 benchmark 取代 |

## Full-scan / adaptive preliminary boundary

- 已證明 formal 720 path：`parameter_combinations()` 從四個 executable dimensions 做 Cartesian product，
  產生 `720` 個 legal combinations 與 `720` 個 unique `combination_id`；
  `parameter_universe_summary()` 固定 `combination_id_hash`，validation-profile partitions
  對 global legal IDs 做 subset / exact-partition 檢查。這仍不是 B1 或完整 search policy admission。
- 可能 full-scan、但容量未證明：固定 development inputs 上的 720 個 E3 replay；沒有
  candidate/sec 或 peak-memory 證據，不能宣稱 daily full scan feasible。
- 可先跑 bounded committed partitions：validation profiles 是 catalog-derived 子集合；characterization
  顯示四個 public profiles 共覆蓋 `242` 個 unique legal IDs、缺 `478` 個 global IDs且跨 partition
  overlap `32` 個 IDs，因此它是 bounded validation seam，不是 full-scan 或 Phase-2 search policy。
- plausibly adaptive：已取得合法且 adaptive-eligible observations 後，四個 ordinal numeric
  dimensions 的相鄰 matched contrasts、robust basin、interaction challenge；現有 learning 與 shadow
  priority projection證明這類資訊可被消費，但不授予執行或 Phase-2 policy authority。
- 不得 adaptive：三個 coverage-only dimensions與任何 larger/uncommitted dimension；在 executable
  authority 出現前，它們只能是 coverage gap／unknown。

## Material claims

### B0P1-COST-001

```yaml
claim_id: B0P1-COST-001
claim: `parameter_combinations()` 先核對 legacy projection，再由四個 executable dimensions 做 Cartesian product，產生 720 個 legal combinations；bounded characterization 重算出 720 個 unique `combination_id`、`combination_id_hash=sha256:78cd9b8b6fa39935f9037d5b4c8dde3fcc2ae39955414aa51bda96dafb69f6b4`，且 `statistical_family_contract()` / `validate_statistical_partition()` 固定 global 720 family 與合法 validation-profile partitions。
classification: E1_FORMAL_720_GENERATION_IDENTITY_PARTITION_CONFIRMED
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: app/research/parameter_catalog.py; scripts/run_autonomous_research.py; config/research_parameter_catalog.json; config/regime_research_contract.json
source_range_or_section: parameter_catalog.py lines 16-21,87-128; run_autonomous_research.py lines 493-577,581-649,655-688; catalog lines 7-169; regime contract lines 126-128; characterization command observed 720/720 unique IDs/hash/partition coverage at 2026-09-01T07:18:37Z
observed_at: 2026-09-01T07:18:37Z
confidence: HIGH
authority_level: COMMITTED_FORMAL_720_FAMILY_AUTHORITY
conflict_with: treating 720 as only arithmetic with no canonical generator/identity/partition path; treating E1 formal authority as E3 full-replay capacity or B1 admission
implication: 720、legal ID hash、global family size與validation partitions可作C0/BC fixed facts；績效容量仍須以E3分類且吞吐未量測。
open_question: 720個E3 replay的bounded benchmark、rank/unrank convenience path、larger product dimension/constraint authority；B1尚未准入
owner: B0 evidence owner / future B1 owner
```

### B0P1-COST-002

```yaml
claim_id: B0P1-COST-002
claim: 現有 strategy matrix 雖宣告 features load_once_per_matrix 並在 scenario loop 外載入 price frame，但每個 scenario 都呼叫 run_portfolio_from_price_frame；目前沒有可證明的 reusable path-dependent intermediate evaluator，因此 E2 對 full candidate evaluation 為 NOT_PROVEN。
classification: E2_NOT_PROVEN_WITH_INPUT_REUSE_ONLY
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: scripts/run_backtest_strategy_matrix.py
source_range_or_section: lines 580-624,705-724
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: CURRENT_RUNNER_CODE_PATH
conflict_with: assuming vectorized or cached path evaluation
implication: C0 不得用「load once」等同「candidate evaluation 可重用」；需要另做 bounded benchmark/semantic audit。
open_question: 哪些 ranking/entry/holding/exit intermediates可跨候選安全重用而不改 backtest math
owner: C0 capacity owner / backtest owner
```

### B0P1-COST-003

```yaml
claim_id: B0P1-COST-003
claim: 現行 stock matrix 的績效 evaluation 屬 E3，因每個 scenario 綁定 horizon、stop/take events、group exposure並執行完整 portfolio replay，且 exact regime 時還受 horizon-safe dates 與 episode scope 限制。
classification: E3_CONFIRMED_CURRENT_EXECUTION_CLASS
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: scripts/run_backtest_strategy_matrix.py
source_range_or_section: lines 1-6,35-37,64-135,580-669
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: CURRENT_RUNNER_CODE_PATH
conflict_with: classifying the current full evaluator as E1 or proven E2
implication: C0 的保守容量模型應使用「至多720個E3 candidate replays × context-specific data scope」。
open_question: candidate/sec、wall time、CPU、peak memory、I/O 與 input-size scaling
owner: C0 capacity owner
```

### B0P1-COST-004

```yaml
claim_id: B0P1-COST-004
claim: FORWARD_SHADOW 是 committed research funnel 的必要後段驗證 class（E4），但本 Phase 1 未發現或執行一條把完整 720 matrix直接送入統一 forward-shadow evaluator 的 authority/capacity path。
classification: E4_REQUIRED_BUT_CAPACITY_UNCHARACTERIZED
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: config/regime_research_contract.json; docs/architecture/AUTONOMOUS_RESEARCH_MANAGER.md; docs/RESEARCH_SPINE_BACKLOG.md
source_range_or_section: regime contract lines 154-160; manager doc lines 31-59; backlog lines 625-660
observed_at: 2026-09-01T03:06:26Z
confidence: MEDIUM_HIGH
authority_level: GOVERNING_FUNNEL_WITH_MISSING_CAPACITY_PATH
conflict_with: treating historical replay as forward-shadow completion
implication: E4 的日曆時間、樣本到達率與 observation cadence 必須由 C0/未來 phase另行盤點。
open_question: canonical TrialSpec到forward-shadow observation的direct runner/receipt seam與最小觀察窗口
owner: BC-CP1 Integrator / future C0 phase owner
```

### B0P1-COST-005

```yaml
claim_id: B0P1-COST-005
claim: 四個 ordinal numeric parameters 已有 catalog-adjacent matched-contrast、robust-basin與pairwise-interaction learning projection；這使 evidence-driven adaptive refinement在技術上 plausible，但它只讀 ADAPTIVE_ELIGIBLE evidence，且 Phase 2仍未准入。
classification: ADAPTIVE_PLAUSIBLE_NOT_ADMITTED
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: app/research/parameter_learning.py; app/research/adaptive_shadow_queue.py; docs/RESEARCH_SPINE_BACKLOG.md
source_range_or_section: parameter_learning.py lines 31-70,300-390,430-505; adaptive_shadow_queue.py lines 285-345,403-518; backlog lines 393-406,637-660
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: COMMITTED_DERIVED_CAPABILITY_WITH_GOVERNANCE_LOCK
conflict_with: Phase-1 adaptive-search policy or execution admission
implication: BC-CP1可把四維 local refinement列為Phase-2候選問題，但不得在本 receipt 定案策略或執行。
open_question: 哪些 measured gaps足以支持Phase-2 admission，以及 full-scan baseline是否先具成本可行性
owner: BC-CP1 Integrator / Owner
```

### B0P1-COST-006

```yaml
claim_id: B0P1-COST-006
claim: Phase 1 未執行 replay benchmark；candidate/sec、wall time、CPU、peak memory與I/O均標記 UNMEASURED_CAPACITY，因靜態 code-path evidence已足以完成初步E-class且避免full-matrix/operational interference。
classification: UNMEASURED_CAPACITY
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: docs/RESEARCH_SPINE_BACKLOG.md; https://github.com/bluemaple18-home/NEW-TOP10/issues/13
source_range_or_section: backlog lines 286-321,600-621; Issue #13 sections Initial E1–E4 evaluation classification and Hard constraints
observed_at: 2026-09-01T03:06:26Z
confidence: HIGH
authority_level: PHASE_1_SCOPE_AND_OBSERVATION
conflict_with: any numeric throughput claim
implication: C0必須保留容量未知，不得把本文件當性能benchmark。
open_question: safe bounded benchmark input、sample size、operational isolation與measurement owner
owner: C0 capacity owner
```

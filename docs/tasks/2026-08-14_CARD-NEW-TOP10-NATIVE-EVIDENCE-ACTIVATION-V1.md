---
id: CARD-NEW-TOP10-NATIVE-EVIDENCE-ACTIVATION-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: architecture-implementation
priority: P1
owner: TOP10new research platform
role: implementation
cycle: 0
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 核心execution identity、sealed lineage、capacity stop-loss與跨模組activation契約已固定，需高強度bounded實作。
date: 2026-08-14
production_change_allowed: false
card_b_allowed: false
live_activation_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-ACTIVATION-V1/
---

# NEW-TOP10 Native Evidence Activation V1

## 目標

在不改選題、queue、scheduler、Fog Map與production的前提下，證明既有daily runner可形成：

```text
TrialSpec → Intent → Attempt → Matrix → Receipt → Observation → ADAPTIVE_ELIGIBLE
```

Card A已建立Research Spine。本卡只補Card A contract與Card B evidence-guided priority之間的operational proof；不是新增第二層架構。

目前shared checkout已有未完成、未驗收的`PRE_CARD_CANDIDATE`。正式implementation thread必須逐項重驗、修復或替換；不得把source commit內的候選視為已完成。

## Ownership

允許修改：`app/research/`、`config/research_*`、`config/native_evidence_*`、research runner/verifier scripts、對應tests，以及本卡evidence workspace。

禁止修改：production model/ranking/signals、Fog Map語意、queue selection、scheduler/launchd、LightGBM、promotion；另不得碰已存在的使用者變更`build_weekend_universe_inventory.py`、其snapshot test與2026-08-02/03 storage task docs。

## 現況基線

- Unique legacy records：207,871。
- `ADAPTIVE_ELIGIBLE`：0。
- Native execution units：0。
- Raw observations：0。
- Matched contrasts：0。
- Canonical corpus現有14份native receipts，皆未證明成功執行事實，為`FAILED / UNKNOWN / NOT_EXECUTED / INCOMPLETE_EXECUTION_FACTS`；其中8份已進ledger。
- 這14份requested stage為`SEALED_VALIDATION`、regime為`UNSCOPED`、沒有artifacts/units，且多數缺batch ID；屬測試／手動舊路徑污染候選，不得當activation evidence，也不得修改或刪除immutable facts。
- 主機可用空間約12 GiB，低於`max(20 GiB, 10%)`；任何live recurring activation為`NO-GO`。
- Eligibility目前把base parameter合法`null` baseline誤判為identity incomplete，須改成catalog-aware validation。

## Root question

Existing daily runner能否讓每個實際完成的development/coarse matrix scenario，從immutable execution plan一路被證明為完整、non-sealed、可重建且eligible的native observation？

## Scope

### 必做

- Immutable pre-execution plan與batch/run/intent correlation。
- Development-only lineage authority；sealed fail closed。
- Requested/executed scenario集合與result完整對帳。
- Catalog-aware nullable parameter identity。
- Receipt→execution unit→observation→eligibility完整度驗證。
- 兩個有界代表週期、容量budget、retention dry-run、回收與stop-loss演練。
- Production、selection、scheduler前後manifest parity。

### 禁止

- Adaptive/shadow queue或priority。
- 改manager selection、topic ordering、quota、rerun/cooldown。
- 新scheduler、launchd或背景服務。
- 使用sealed、legacy或synthetic evidence冒充real native learning。
- Optuna、dynamic refinement、dashboard。
- Production ranking/model/signals/config/promotion write。
- 容量gate前啟用daily recurring run。

## Contracts

### FR-001 Immutable execution plan

Subprocess前以exclusive-create、fsync、content identity保存：batch/intent/run/topic、baseline/candidate TrialSpecs、ordered scenario hash、catalog hash、stage/regime、dataset/ranking manifests、development與excluded episode authority、execution settings、runner/code policy、expected outputs、安全旗標。

Plan未成功發布不得執行。

### FR-002 Development lineage

`PROVEN_NON_SEALED`必須同時證明：

- `research_stage=DEVELOPMENT_SCREEN`或核准的`COARSE_SCREEN`。
- executed episodes為development authority子集。
- executed episodes與validation/embargo/sealed交集為空。
- ranking dates位於allowed development dates。
- executed dataset/ranking/settings與plan一致。

缺失或衝突一律`UNKNOWN + INVALID_LINEAGE`。

### FR-003 Requested/executed completeness

每個variant驗證scenario count、unique IDs、parameter-space hash、parameters、role、stage、regime、dataset/ranking、episode IDs、artifact/result correlation。Missing、duplicate、unexpected scenario不得略過或eligible。

### FR-004 Observation reconciliation

每批須對帳：

```text
planned scenarios
= executed scenarios
= receipt execution units
= ledger observations
```

Eligible數另計；receipt成功不等於observation成功。

### FR-005 Catalog-aware null

- `horizon`必須存在且為catalog合法integer。
- `stop_loss_pct`、`take_profit_pct`、`max_group_exposure`欄位必須存在；`null`是catalog合法disabled baseline。
- `regime_gate`、`risk_guard`、`entry_filter=null`表示未執行；不得補Fog defaults。
- 缺欄與合法`null`必須分開。

不得降低既有eligibility policy。

### FR-006 Capacity safety

Activation policy須有：`max_bytes`、`max_file_count`、per-cycle bytes/files、正常增長率、burst/stabilization window、retention、rotation、cleanup allowlist、sampling interval、RSS/swap限制、stop command、restart gate。

寫入盤點至少涵蓋spine entities/CAS、matrix/comparison、run archives、logs、DuckDB/WAL/tmp、projections、Fog compatibility、verification artifacts。

主機free低於`max(20 GiB,10%)`時禁止啟動。Stop-loss只停止research activation；不刪canonical facts、不kill其他專案。

### FR-007 Rollback

`TOP10_NATIVE_EVIDENCE_ACTIVATION_ENABLED=false`回舊operational flow；保留immutable evidence，不改production。

## Implementation slices

### NEA-SLICE-000｜Test corpus isolation

所有會呼叫autonomous `main()`或receipt lifecycle的測試，必須使用tmp corpus/output/ledger。新增guard：完整測試前後repo canonical receipt inventory/hash不變。

既有14份immutable receipts不改；使用versioned provenance/exclusion分類，使其不進activation success計數。Derived ledger只可重建，不可修寫source facts。

### NEA-SLICE-001｜Contract、baseline、capacity preflight

交付activation/execution-plan/capacity schema；鎖production、selection、scheduler、runner argv、storage baseline。

驗收：缺budget、authority、batch ID即fail；host容量不足只允許隔離測試，不允許live cycle。

### NEA-SLICE-002｜Execution plan與development lineage

Plan先於subprocess；matrix綁batch/run/intent/plan；wrong hash、sealed overlap、ranking越界、authority conflict全fail closed。

### NEA-SLICE-003｜Receipt→Observation completeness

精確scenario回映、catalog-aware null、planned/executed/unit/observation verifier、partial quarantine。

驗收：合法null可eligible；missing/duplicate/unexpected/corrupt不可eligible；baseline/candidate不混淆。

### CHECKPOINT-1

只跑synthetic/fixture與isolated ledger。Targeted tests、rebuild parity、`git diff --check`、獨立adversarial review須GO。

### NEA-SLICE-004｜Cycle 1 isolated dry-run

正式entrypoint、代表性development input、隔離corpus/ledger/output、bounded topic/quota；不啟排程、不寫production。若用synthetic，只驗鏈，不算市場evidence或Card B門檻。

GO：至少一個完整receipt/observation/eligible；sealed eligible=0；second ingest增量0；rebuild一致；完成容量量測。

### NEA-SLICE-005｜Capacity recovery與stop-loss drill

依Cycle 1校準budget；retention dry-run；只對allowlist可重建副本做實際回收；演練stop/restart。Canonical corpus不得刪。

### CHECKPOINT-2

容量閘門需PASS。若host仍低於保留線，狀態`NO-GO_CAPACITY`，不得進Cycle 2。

### NEA-SLICE-006｜Cycle 2 real research-only canary

人工單次正式daily entrypoint；強制real development-only；scheduler不啟用；前後production與selection parity。

GO：所有attempt有terminal receipt；successful identity/completeness=100%；至少一筆real eligible；sealed/unknown eligible=0；無新增conflict/rejection；容量在budget內。

無real topic時：`BLOCKED_NO_REAL_ACTIVATION_CANDIDATE`，不得用synthetic替代。

### NEA-SLICE-007｜Activation decision與rollback proof

產status、PM summary、capacity/rollback receipts、before/after。最終只可`GO`或`NO-GO`。

## Card B gate

本卡GO只證明native evidence path可用，不授權Card B。

Card B另需：

- 至少兩個real完整週期。
- `SUCCEEDED + OBSERVED + EXACT + VALID + PROVEN_NON_SEALED` 100%。
- 零sealed overlap、duplicate、collision、orphan。
- 至少一個parameter/scope具`>=3` independent catalog-adjacent matched contrasts、`>=2` lineages。
- Official knowledge/verifier PASS；production、queue、scheduler零變更。
- 容量安全閘門持續PASS。

## Required tests

1. Valid development authority→`PROVEN_NON_SEALED`。
2. Missing/conflicting authority→UNKNOWN。
3. Sealed overlap與ranking越界fail。
4. Dataset/ranking/settings substitution fail。
5. Plan先於execution且batch/run/intent/plan correlation完整。
6. Missing/duplicate/unexpected scenario fail。
7. Legal null通過；missing field失敗；coverage-only null不冒充execution。
8. Complete scenario恰好一observation；partial/corrupt不eligible。
9. Ingest idempotent；semantic conflict fail closed。
10. Synthetic與real evidence隔離。
11. Queue/scheduler/production parity。
12. Write inventory完整；budget/host gate/stop-loss/回收/rollback通過。

## 現在的frontier

`NEA-SLICE-000`與`NEA-SLICE-001`可平行施工。`NEA-SLICE-002+`受兩者阻擋；Cycle 2另受容量gate阻擋。

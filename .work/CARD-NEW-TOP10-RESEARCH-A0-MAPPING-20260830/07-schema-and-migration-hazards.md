# 07 — Schema and Migration Hazards

日期：2026-08-30
Execution base：`origin/main@4c6d41a44314beb3592ccdf7a9b43d8fe614ad88`
整合輸入：A0 01–06 與 Owner-accepted dataset identity-grain decision
模式：`READ_ONLY_RESEARCH / DOCS_AND_EVIDENCE_ONLY`

本檔只辨識 schema/migration hazards，不修改或授權 schema、runtime、DB、data 或 production。裁決欄只使用 A0 taxonomy；`CONFIRMED` 僅可出現在 claim 文字或 evidence 描述，不作本檔裁決值。

## Structured findings

### A0-INT-HAZ-001

| field | value |
|---|---|
| claim_id | `A0-INT-HAZ-001` |
| subject | legacy `dataset_hash` semantic migration |
| claim | 現行 `dataset_hash` 的可證明 grain 是單一 `features.parquet` bytes hash；若原地改稱完整 dataset identity，會把歷史 evidence 錯誤升級。Owner 已接受其固定型別為 `FEATURES_ARTIFACT_V1`，新 bundle identity 必須 additive 並禁止 shadow reinterpretation。 |
| authority | Owner-accepted dataset identity-grain decision；Lane B pinned code mapping |
| scope | A1 schema compatibility boundary |
| as_of | 2026-08-30 |
| evidence_ref | decision §§2、5、12；04 `CLAIM-DATASET-009`～`014` |
| evidence_hash | `decision=44b3f5cd173c36d98144c385ac2e399284145bfc`; `04=7c60fc73ec1e8608d28461e47d5fe7b38033346b` |
| status | `MEASURED_GAP` |
| owner | A1 card owner（尚未派工） |
| next_action | A1 只可新增 typed bundle fields/validator 與 legacy bridge；不可改寫既有 receipt 語意。 |

### A0-INT-HAZ-002

| field | value |
|---|---|
| claim_id | `A0-INT-HAZ-002` |
| subject | dataset bundle executable contract |
| claim | `DATASET_BUNDLE_V1` 的 grain、canonical hash、requested/executed invariant 已由 Owner 裁決，但 repository runtime/schema 尚未實作 manifest schema、validator、round-trip 或 fail-closed tests。 |
| authority | Owner-accepted dataset identity-grain decision |
| scope | A1 implementation prerequisite；不是 A0 implementation claim |
| as_of | 2026-08-30 |
| evidence_ref | decision §§4、8、10、12 |
| evidence_hash | `44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `MEASURED_GAP` |
| owner | A1 card owner（尚未派工） |
| next_action | 另立 A1 card 固化 schema/canonicalizer/validator/tests；在此之前不得宣稱 bundle runtime 已存在。 |

### A0-INT-HAZ-003

| field | value |
|---|---|
| claim_id | `A0-INT-HAZ-003` |
| subject | per-consumer component cardinality |
| claim | training、backtest、ranking 的 mandatory/optional component matrix，以及 events/signals/universe 的實際讀取條件，尚未固化為 executable contract。 |
| authority | Owner-accepted decision technical follow-up；Lane B consumer mapping |
| scope | A1 schema validation |
| as_of | 2026-08-30 |
| evidence_ref | decision §11 `U-DATASET-001`、`U-DATASET-004`；04 `CLAIM-DATASET-006`～`008` |
| evidence_hash | `decision=44b3f5cd173c36d98144c385ac2e399284145bfc`; `04=7c60fc73ec1e8608d28461e47d5fe7b38033346b` |
| status | `UNKNOWN` |
| owner | A1 card owner（尚未派工） |
| next_action | A1 逐 entrypoint 以 pinned code/tests 定義 matrix；未定義或 unresolved component 必須 fail closed。 |

### A0-INT-HAZ-004

| field | value |
|---|---|
| claim_id | `A0-INT-HAZ-004` |
| subject | transformation identity |
| claim | Architecture default 已固定為 `contract version + exact Git blob set`，但 exact blob-set 計算、version ownership 與驗證規則仍未實作。 |
| authority | Owner-accepted dataset identity-grain decision |
| scope | A1 transformation identity contract |
| as_of | 2026-08-30 |
| evidence_ref | decision §§4.2、4.3、11 `U-DATASET-002`、12 item 4 |
| evidence_hash | `44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `MEASURED_GAP` |
| owner | A1 card owner（尚未派工） |
| next_action | A1 定義 deterministic blob-set membership、contract version owner 與 change tests；不得退回 branch/path identity。 |

### A0-INT-HAZ-005

| field | value |
|---|---|
| claim_id | `A0-INT-HAZ-005` |
| subject | fundamentals snapshot identity |
| claim | M4 consumer 可受 fundamentals cache 影響，但目前沒有完整 immutable snapshot identity/coverage contract；Owner 已將它列為 A1 prerequisite。 |
| authority | Owner-accepted decision；Lane B lineage mapping |
| scope | A1 dataset closure |
| as_of | 2026-08-30 |
| evidence_ref | decision §§4.2、11 `U-DATASET-003`、12 item 5；04 `CLAIM-DATASET-006` |
| evidence_hash | `decision=44b3f5cd173c36d98144c385ac2e399284145bfc`; `04=7c60fc73ec1e8608d28461e47d5fe7b38033346b` |
| status | `MEASURED_GAP` |
| owner | A1 card owner（尚未派工） |
| next_action | A1 必須建立最小 snapshot identity/coverage contract，或將依賴該 snapshot 的 consumer 標為 not executable。 |

### A0-INT-HAZ-006

| field | value |
|---|---|
| claim_id | `A0-INT-HAZ-006` |
| subject | canonical writer and projection separation |
| claim | Native TrialSpec/Intent/Attempt/Receipt writers、immutable corpus/CAS、legacy migration、compatibility `run_history` writer與 DuckDB projection 的角色可區分；現有 evidence 未顯示兩個 layer 同時宣稱同一 canonical writer authority。 |
| authority | Lane A authority/boundary maps；Lane C existing-capability matrix |
| scope | writer authority reconciliation |
| as_of | 2026-08-30 |
| evidence_ref | 01 `A0-AUTH-007`～`009`；03 `A0-BND-001`、`004`～`008`；06 `C-NEW-001`～`002` |
| evidence_hash | `01=fce6fda213887f5d891f169e96cd8fb8c3a5fe65`; `03=02db82892a91e6f3f95528717434104b6f365f63`; `06=f49c5279cf55010eba996579628dddb6050d64ca` |
| status | `NOT_A_GAP` |
| owner | Research Spine owner |
| next_action | 後續 schema 必須維持 immutable evidence 為 authority、DuckDB/run_history 為可重建或 compatibility projection。 |

### A0-INT-HAZ-007

| field | value |
|---|---|
| claim_id | `A0-INT-HAZ-007` |
| subject | legacy exact migration coverage |
| claim | 可用 contemporaneous immutable evidence 精確映射為 `dataset_bundle_id` 的 legacy corpus 覆蓋率尚未盤點；不足 evidence 不得猜測升級。 |
| authority | Owner-accepted dataset identity-grain decision |
| scope | A3 prerequisite only；不啟動 A3 |
| as_of | 2026-08-30 |
| evidence_ref | decision §§5、11 `U-DATASET-007` |
| evidence_hash | `44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `UNKNOWN` |
| owner | Future A3 card owner（未准入） |
| next_action | 保持 legacy quarantine；只有另行 admitted A3 可盤點 EXACT coverage，且不可改寫原 receipt。 |

### A0-INT-HAZ-008

| field | value |
|---|---|
| claim_id | `A0-INT-HAZ-008` |
| subject | materialized dataset state |
| claim | A0 未讀取目前 materialized parquet bytes、row/date coverage 或 producer run，因此任何 current-runtime migration sizing 都未被固定。 |
| authority | A0 read-only committed-evidence boundary |
| scope | runtime artifact state |
| as_of | 2026-08-30 |
| evidence_ref | 04 `CLAIM-DATASET-013`；decision §11 `U-DATASET-006` |
| evidence_hash | `04=7c60fc73ec1e8608d28461e47d5fe7b38033346b`; `decision=44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `UNPINNED_RUNTIME_ARTIFACT` |
| owner | Mainline / separately authorized runtime evidence owner |
| next_action | 不阻塞 A0；只有後續卡確有需要且另獲授權時才讀 runtime artifacts，禁止由 committed code 推定。 |

## Integrator disposition

`IDENTITY_GRAIN_AMBIGUITY_RESOLVED_BY_OWNER_DECISION` 適用於 A0 mapping；未發現 governing-authority 或 terminal-boundary hard stop。A1 的 schema、validator、snapshot 與 compatibility work 仍是未實作的 measured gaps。

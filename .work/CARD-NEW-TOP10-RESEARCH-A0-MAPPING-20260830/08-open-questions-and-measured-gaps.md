# 08 — Open Questions and Measured Gaps

日期：2026-08-30
Execution base：`origin/main@4c6d41a44314beb3592ccdf7a9b43d8fe614ad88`
整合輸入：A0 01–06 與 Owner-accepted dataset identity-grain decision
模式：`READ_ONLY_RESEARCH / DOCS_AND_EVIDENCE_ONLY`

## Cross-lane reconciliation

### A0-INT-GAP-001

| field | value |
|---|---|
| claim_id | `A0-INT-GAP-001` |
| subject | cross-map research identity consistency |
| claim | `trial_spec_id`、`intent_id`、`run_id`、attempt/receipt/observation/artifact identities 在 Lane A/C 的語意一致：requested definition、execution attempt、terminal evidence與projection 不互相取代；legacy `combo_id` 僅是 migration/compatibility identity。 |
| authority | Lane A identity/boundary maps；Lane C current-capability mapping |
| scope | Research Spine identity reconciliation |
| as_of | 2026-08-30 |
| evidence_ref | 02 `A0-ID-002`～`010`；03 `A0-BND-001`～`007`；06 `C-NEW-001`～`002` |
| evidence_hash | `02=bd695af1ad4af72cdcfd300b431228c2175fed6c`; `03=02db82892a91e6f3f95528717434104b6f365f63`; `06=f49c5279cf55010eba996579628dddb6050d64ca` |
| status | `NOT_A_GAP` |
| owner | Research Spine owner |
| next_action | 後續不得把 `combo_id`、runtime ID、projection row ID 升格為 canonical research identity。 |

### A0-INT-GAP-002

| field | value |
|---|---|
| claim_id | `A0-INT-GAP-002` |
| subject | dataset identity consistency after Owner decision |
| claim | Lane B 的單檔-vs-consumer-closure conflict 已由 Owner 接受的 `DATASET_BUNDLE_V1` 與 legacy `FEATURES_ARTIFACT_V1` 分型裁決；此裁決只解除 A0 mapping blocker，未證明 runtime/schema implementation。 |
| authority | Owner-accepted dataset identity-grain decision；Lane B mapping |
| scope | A0 identity-grain reconciliation |
| as_of | 2026-08-30 |
| evidence_ref | decision §§1、4、5、12；04 `CLAIM-DATASET-014` |
| evidence_hash | `decision=44b3f5cd173c36d98144c385ac2e399284145bfc`; `04=7c60fc73ec1e8608d28461e47d5fe7b38033346b` |
| status | `NOT_A_GAP` |
| owner | Owner / Mainline Integrator |
| next_action | 將未實作部分留給另行 admitted A1；不得把 decision 文件當 runtime receipt。 |

### A0-INT-GAP-003

| field | value |
|---|---|
| claim_id | `A0-INT-GAP-003` |
| subject | MarketObservation / ResearchObservation split |
| claim | A0 evidence證明現有 Research Observation 是 completed execution/result unit；OMI 的 market observation/source-lineage 僅為 `prior_art_only`。沒有 measured evidence 證明 NEW-TOP10 現在需要新增獨立 `MarketObservation` runtime/schema，亦不能讓它取代 Research Observation。 |
| authority | Lane A identity map；Lane B OMI lens；Lane C donor boundary |
| scope | Observation naming and authority |
| as_of | 2026-08-30 |
| evidence_ref | 02 `A0-ID-005`；05 `CLAIM-MARKET-008`～`011`；06 `C-PRIOR-OMI-001` |
| evidence_hash | `02=bd695af1ad4af72cdcfd300b431228c2175fed6c`; `05=32bde5d5f3553dffbd8aeef6624899f6d12a425c`; `06=f49c5279cf55010eba996579628dddb6050d64ca` |
| status | `NOT_A_GAP` |
| owner | Research Spine owner |
| next_action | 不建立 `MarketObservation`；若未來 direct consumer dependency 提供新 evidence，另卡評估 provider provenance vocabulary。 |

### A0-INT-GAP-004

| field | value |
|---|---|
| claim_id | `A0-INT-GAP-004` |
| subject | Dataset Registry equivalence |
| claim | 現有 immutable receipts/CAS/manifests 加 rebuildable projection 已提供 dataset bundle 可落入的最低 seam；A0 沒有 evidence 支持中心 Dataset Registry/DB 是必要缺口。 |
| authority | Lane A authority map；Lane B ranking receipt seam；Lane C authority-risk review；Owner decision |
| scope | Dataset authority architecture |
| as_of | 2026-08-30 |
| evidence_ref | 01 `A0-AUTH-007`；04 `CLAIM-DATASET-012`；06 runtime authority risk；decision §§3、6 |
| evidence_hash | `01=fce6fda213887f5d891f169e96cd8fb8c3a5fe65`; `04=7c60fc73ec1e8608d28461e47d5fe7b38033346b`; `06=f49c5279cf55010eba996579628dddb6050d64ca`; `decision=44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `NOT_A_GAP` |
| owner | Research Spine owner |
| next_action | A1 WRAP/ADAPT 現有 seams；禁止新增 registry authority。 |

### A0-INT-GAP-005

| field | value |
|---|---|
| claim_id | `A0-INT-GAP-005` |
| subject | Research Ledger role |
| claim | Research Ledger / DuckDB 是由 immutable corpus/CAS/migration evidence 重建的 projection，不是 canonical truth；現有 maps 對此無 authority conflict。 |
| authority | Lane A authority/boundary maps；Lane C current-capability mapping |
| scope | Ledger authority reconciliation |
| as_of | 2026-08-30 |
| evidence_ref | 01 `A0-AUTH-007`～`009`；03 `A0-BND-004`～`005`；06 `C-NEW-002` |
| evidence_hash | `01=fce6fda213887f5d891f169e96cd8fb8c3a5fe65`; `03=02db82892a91e6f3f95528717434104b6f365f63`; `06=f49c5279cf55010eba996579628dddb6050d64ca` |
| status | `NOT_A_GAP` |
| owner | Research Spine owner |
| next_action | 保留 delete-and-rebuild invariant；禁止把 pass/projection receipt 解讀成 runtime load 或 admission proof。 |

### A0-INT-GAP-006

| field | value |
|---|---|
| claim_id | `A0-INT-GAP-006` |
| subject | raw provider acquisition provenance |
| claim | Bounded committed evidence 未找到把 endpoint/request/fallback/session/raw content hash、normalized rows與dataset identity串成 immutable live acquisition receipt；Owner 明確將它 deferred 為 provenance gap，除非 consumer 直接依賴 raw payload。 |
| authority | Lane B negative finding；Owner-accepted decision |
| scope | Deferred market-source provenance |
| as_of | 2026-08-30 |
| evidence_ref | 04 `CLAIM-DATASET-003`；05 `CLAIM-MARKET-003`、`005`、`007`；decision §§4.2、11 `U-DATASET-005`、12 item 5 |
| evidence_hash | `04=7c60fc73ec1e8608d28461e47d5fe7b38033346b`; `05=32bde5d5f3553dffbd8aeef6624899f6d12a425c`; `decision=44b3f5cd173c36d98144c385ac2e399284145bfc` |
| status | `MEASURED_GAP` |
| owner | Deferred provenance owner（尚未派工） |
| next_action | 不納入 A1 minimum slice、不阻塞 A0；只有 direct dependency 或另行 Owner admission 才開卡，且不得順帶導入 OMI runtime。 |

### A0-INT-GAP-007

| field | value |
|---|---|
| claim_id | `A0-INT-GAP-007` |
| subject | A0 baseline manifest |
| claim | Lane A 確認 worktree HEAD 符合指定 base，但未找到獨立 committed A0 baseline manifest body。這不改變固定 Git base，亦不阻塞本輪 bundle synthesis。 |
| authority | Lane A authority map |
| scope | A0 evidence packaging |
| as_of | 2026-08-30 |
| evidence_ref | 01 `A0-AUTH-006` |
| evidence_hash | `fce6fda213887f5d891f169e96cd8fb8c3a5fe65` |
| status | `UNKNOWN` |
| owner | Mainline A0 acceptance owner |
| next_action | 若驗收要求獨立 manifest，可在不讀 runtime 的 docs-only acceptance receipt 補固定 inputs/SHAs；不可改寫 lane evidence。 |

### A0-INT-GAP-008

| field | value |
|---|---|
| claim_id | `A0-INT-GAP-008` |
| subject | OMI pinned evidence cross-lane discrepancy |
| claim | Lane C 因自身 network boundary 未取得 OMI pinned bytes，Lane B 則以指定 commit 的檔案 blob hashes提出詳細 OMI claims；這是 lane evidence availability 差異，不是 governing authority conflict。只有 Lane B 已 pin 的個別檔案 claims可作 A0 prior-art evidence，OMI仍是 `prior_art_only`。 |
| authority | Lane B OMI evidence index；Lane C UNKNOWN register |
| scope | Prior-art evidence reconciliation |
| as_of | 2026-08-30 |
| evidence_ref | 05 evidence index / `CLAIM-MARKET-008`～`011`；06 `U-OMI-001` / `C-PRIOR-OMI-001` |
| evidence_hash | `05=32bde5d5f3553dffbd8aeef6624899f6d12a425c`; `06=f49c5279cf55010eba996579628dddb6050d64ca` |
| status | `NOT_A_GAP` |
| owner | Integrator |
| next_action | 只引用 Lane B 已 pin 的 OMI檔案；不得把 OMI 升為 governing authority、runtime 或 code-copy admission。 |

### A0-INT-GAP-009

| field | value |
|---|---|
| claim_id | `A0-INT-GAP-009` |
| subject | terminal success/failure boundary |
| claim | Canonical terminal states、success所需 executed units/observed facts、missing receipt fail-closed與 orphan=`UNKNOWN` 在 Lane A evidence中一致，沒有 material terminal-boundary ambiguity。 |
| authority | Lane A identity/boundary maps |
| scope | Terminal receipt admission boundary |
| as_of | 2026-08-30 |
| evidence_ref | 02 `A0-ID-008`～`010`；03 `A0-BND-002`～`003` and terminal summary |
| evidence_hash | `02=bd695af1ad4af72cdcfd300b431228c2175fed6c`; `03=02db82892a91e6f3f95528717434104b6f365f63` |
| status | `NOT_A_GAP` |
| owner | Research Spine owner |
| next_action | A1/A2 不得弱化 terminal invariant；A2 只能在 A1實作後驗證 dataset binding prerequisites。 |

### A0-INT-GAP-010

| field | value |
|---|---|
| claim_id | `A0-INT-GAP-010` |
| subject | current adaptive-learning evidence |
| claim | Committed verification evidence顯示 native receipts存在但 native execution units、raw result observations與adaptive eligible皆為零，因此現在沒有 adaptive learning/promotion admission evidence。 |
| authority | Lane A current evidence interpretation |
| scope | A1/A2 non-goal and later admission safety |
| as_of | 2026-08-30 |
| evidence_ref | 01 `A0-AUTH-008`；02 `A0-ID-010` |
| evidence_hash | `01=fce6fda213887f5d891f169e96cd8fb8c3a5fe65`; `02=bd695af1ad4af72cdcfd300b431228c2175fed6c` |
| status | `MEASURED_GAP` |
| owner | Future learning/admission owner（不屬 A1/A2） |
| next_action | 不阻塞 narrow A1 schema work，但阻擋任何 adaptive learning、promotion、queue/priority/ranking policy claim。 |

## Hard-stop assessment

- governing-authority conflict：未發現。
- identity-grain ambiguity：已由 Owner decision 對 A0 mapping 解決；runtime/schema尚未實作。
- terminal-boundary ambiguity：未發現。
- required runtime mutation：A0未需要且未執行。

因此本輪 Integrator 無未決 A0 hard stop；UNKNOWN individual evidence 保留並繼續，不以猜測補齊。

# BC-CP2 R6 Configured Ranking Source Authority Decision

## Receipt

- 任務：`BC-CP2-R6-CONFIGURED-RANKING-SOURCE-AUTHORITY`
- 固定 parent：`1035ca82a56a4b182be0508498ed10676b064da9`
- 任務卡 sha256：`aa1cfbc8f51090a3a719ecf68b437e9a4ce1e0e13483c47110c3639a374ad7fd`
- 產出限制：只新增本檔；未切換 config/root、未 copy/generate rankings、未執行 replay/full-720。
- Verdict：`PARTIAL_EXISTING_SOURCE_AUTHORITY_GAP`

## Verification Receipt

- Fixed parent verified：work start 前 `HEAD` 為 `1035ca82a56a4b182be0508498ed10676b064da9`。
- Card verification：任務卡 hash matched `aa1cfbc8f51090a3a719ecf68b437e9a4ce1e0e13483c47110c3639a374ad7fd`；卡片為 delegation input，驗證後移除。
- Clean preflight：移除任務卡後工作區為 clean，再開始本 evidence write。
- Changed-file allowlist：只允許 `docs/evidence/BC-CP2-R6-CONFIGURED-RANKING-SOURCE-AUTHORITY/01-existing-source-authority-decision.md`；commit diff-tree 亦只有本檔。
- Diff check：write 後與 staged 狀態均通過 `git diff --check`。
- Scope guard：未修改 `config/research_shadow_runs.yaml`、未切換 ranking root、未 copy/generate ranking files、未執行 horizon-safe replay、未執行 full-720。
- Review amend guard：reviewer 修補只 amend 同一 evidence 檔；第二次修補僅唯讀核對指定 features/universe/model/config bytes，不重掃全 repo、不新增 artifact inventory。

## Source Decision

CodeGraph 在本 worktree 回報未初始化，因此 source decision 降級為限域檔案與 artifact inventory：

- `config/research_shadow_runs.yaml`
- `scripts/build_historical_ranking_replay_set.py`
- `scripts/run_daily_research_quota.sh`
- `docs/tasks/2026-08-16_CARD-NEW-TOP10-FORWARD-RANKING-PROVENANCE-RECEIPT-V1.md`
- first-party `<local-data-root>/artifacts/backtest/*` ranking roots、manifest 與 receipt 檔案

## Absorption Boundary

Why not less：

- R5 blocker 不是單純缺檔訊息，而是 configured root、candidate root、manifest lineage、per-ranking receipt/admission boundary 的組合判斷；只寫「有 CSV」會誤把 filename existence 當 authority。
- R6 必須區分 configured baseline/current-model、shadow/candidate/staging、以及 first-party historical replay root，否則下一張卡會拿錯 root 重跑。
- R5 required dates 必須逐日固定，才能證明目前 configured root 是 0/9 overlap，而 strongest fog root 是 9/9 overlap。
- fog root 的 source lineage 必須與目前 configured bytes 分開記錄；否則會誤宣稱 current configured feature compatibility。

Why not more：

- R6 是 source authority decision，不是 config switch、ranking backfill、replay repair 或 admission registration。
- `historical_rankings_current_model_fog_2025-06-03_2026-07-28_ce643797` 只能被列為 strongest existing candidate；本卡不得把它升級成已 configured 或 admission-eligible source。
- Forward capture/admission provenance 不屬於 BC-CP2 當前 capacity/research replay unblock 的最小必要面。
- Source binding 不是 R5 first runner blocker 的下一步；R5 已證明 horizon-safe episode continuity 是第一邊界，ranking overlap/source binding 是第二邊界。

Do not absorb：

- 不吸收 production daily ranking、scheduler/deploy、model training、candidate/shadow promotion。
- 不吸收 `FORWARD_CAPTURE`/admission-eligible receipt generation；歷史日期仍維持 `REPLAY_GENERATED`/non-admission 邊界。
- 不吸收 dense root 作 authority，因其缺 `source_lineage`。
- 不吸收 fog root 作 current configured feature-compatible 或 research-replay authority；目前只能保留為 ranking-date/file lineage candidate。
- 不吸收任何新 authority registry、第二套 runtime、或跨 root 自動選擇邏輯。

## R5 Required Dates

R5 的 failing boundary 需要區分「regime 需要的日期」與「ranking root 實際可供應的日期」：

| Scope | Required ranking dates |
| --- | --- |
| `NARROW_LEADER|BIG_BULL` | `2025-08-13`, `2025-08-15`, `2025-08-18`, `2025-08-27`, `2025-08-28`, `2025-08-29` |
| `NARROW_LEADER|BIG_BULL+HIGH_CHOPPY` | `2025-08-12`, `2025-08-14`, `2025-09-08` |

總 required date set 共 9 日：`2025-08-12`, `2025-08-13`, `2025-08-14`, `2025-08-15`, `2025-08-18`, `2025-08-27`, `2025-08-28`, `2025-08-29`, `2025-09-08`。

## Configured Source

`config/research_shadow_runs.yaml` 目前固定：

- `dates_from_dir: artifacts/backtest/historical_rankings_current_model`
- `features: data/clean/features.parquet`
- `market_regime_history: artifacts/market_regime_history_2026-05-29.json`

`artifacts/backtest/historical_rankings_current_model` 是目前 BC-CP2 R4/R5 使用的 configured root。inventory 結果：

| Root | Role | Ranking files | Date range | R5 required overlap | Authority status |
| --- | --- | ---: | --- | ---: | --- |
| `artifacts/backtest/historical_rankings_current_model` | configured current-model baseline | 25 | `2026-04-08..2026-05-13` | 0/9 | config-bound but coverage gap |

Decision：configured root 沒有任何 R5 required ranking date，因此不能解除 R5 的 `NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE`。

## Existing Candidate Roots

第一方 artifact inventory 找到兩個 full-overlap current-model candidate root，但 authority 強度不同：

| Root | Role | Ranking files | Date range | R5 required overlap | Manifest / lineage | Decision |
| --- | --- | ---: | --- | ---: | --- | --- |
| `artifacts/backtest/historical_rankings_current_model_fog_2025-06-03_2026-07-28_ce643797` | current-model historical replay candidate | 282 | `2025-06-03..2026-07-28` | 9/9 | `manifest.json` sha256 `a6334c4d42f0496043daf4535f8a11d5dfd449efc58450068b2c371f81600f9c`; manifest status `OK`; source lineage includes old snapshot features/universe/model/config bytes; model/config match current configured bytes, but features/universe do not | Strongest date/file candidate, but not current configured feature-compatible authority |
| `artifacts/backtest/historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15` | current-model research replay candidate | 599 | `2023-11-21..2026-05-15` | 9/9 | `manifest.json` sha256 `38b372fdc041e8d1f926a01b6399391ef17b1f0434d8d41b9427e8ebda98bed1`; manifest status `OK`; no `source_lineage` | Coverage exists, authority insufficient |

Partial current-model roots:

| Root | Ranking files | Date range | R5 required overlap | Decision |
| --- | ---: | --- | ---: | --- |
| `artifacts/backtest/historical_rankings_current_model_batch_stride3_2023-11-21_2026-05-15` | 200 | `2023-11-21..2026-05-14` | 3/9 | coverage insufficient |
| `artifacts/backtest/historical_rankings_current_model_extended` | 60 | `2023-11-21..2026-05-04` | 2/9 | coverage insufficient and no sufficient manifest authority |

Shadow/candidate/staging roots were rejected as BC-CP2 configured baseline authority because they are not current-model baseline ranking roots, and the inspected production baseline harness/staging roots had zero R5 required overlap.

## Strongest Candidate Hash Evidence

For `artifacts/backtest/historical_rankings_current_model_fog_2025-06-03_2026-07-28_ce643797`, all 9 R5 required files exist:

| Ranking file | sha256 |
| --- | --- |
| `ranking_2025-08-12.csv` | `ecd8c236652bd3460dc8913915b924562c3ab32313f6f3c32f2841fc170a8dfa` |
| `ranking_2025-08-13.csv` | `49653622fe51437c7d7eb3772ad6b81a9b4bace32e44fe875c4ce1dbff1c9944` |
| `ranking_2025-08-14.csv` | `d9d17a64324dff137fb6d44209e45f77594eeaf4018ae477ba6e295f5d387aa9` |
| `ranking_2025-08-15.csv` | `2581bc798eebfb54194ffa16c4e845e71a6e7cb4a610229f455364797c831070` |
| `ranking_2025-08-18.csv` | `97b5b6199041d0bf2a6f5c92ccf5fdfb8d3182ca3283a430e0b62f01b62b69ca` |
| `ranking_2025-08-27.csv` | `1d960f260c74371f2e14ea07719d79e19f47891c33d0f678f411c9b9bf461140` |
| `ranking_2025-08-28.csv` | `a52ab4d4d4e21e0d7fbbe9a8d1801cd8e080745262644d7feae2c70268227e0d` |
| `ranking_2025-08-29.csv` | `9206ade5807d99616158f49780b7424a7bede84361c987b8137f53b291793ef1` |
| `ranking_2025-09-08.csv` | `7fe17636204a0658fabf486d524a61fe1304d0ec6be8bc9baeccc54ed1ee9704` |

## Input Snapshot Compatibility

唯讀核對指定 bytes 後，fog manifest 綁定的是 old input snapshot：

| Input | fog manifest sha256 | current configured sha256 | Decision |
| --- | --- | --- | --- |
| `data/clean/features.parquet` | `0a4eccd0ac076237ad64a21693934b409a9aa50afe936b9bd185cd8a49518523` | `93e8432987b6037db243b2864f7bc8d09f12acd50249d9238d2acddacd2561d2` | mismatch |
| `data/clean/universe.parquet` | `64ab2c34dc54b2238d62a1edaad20df2b992d9fa50ffd94f6e13989715d4150a` | `ba9c69dc5270bf53968e39a51c93e6e80421d7545c83b29df5a95a693aede85a` | mismatch |
| `models/latest_lgbm.pkl` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` | match |
| `config/signals.yaml` | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` | match |

Decision：fog root 可證明 9 個 required ranking date/file 存在，也保留 old snapshot lineage；但 old features/universe bytes 不等於目前 configured bytes，且 bundle 內未固定可重用的 current input snapshot。因此不得宣稱 current configured feature compatibility，也不得宣稱它已是 BC-CP2 research-replay authority。

## Authority Gap

No unique legal configured source exists yet.

Precise gap:

1. The only BC-CP2 configured root is `artifacts/backtest/historical_rankings_current_model`, and it has 0/9 R5 required dates.
2. The strongest full-overlap root, `historical_rankings_current_model_fog_2025-06-03_2026-07-28_ce643797`, has ranking-date/file lineage and old input lineage, but the old features/universe bytes do not match current configured bytes; it is not bound by `config/research_shadow_runs.yaml` for BC-CP2 R4/R5 and contains no per-ranking `ranking-provenance-receipt.v1` files in the artifact directory.
3. The forward provenance contract states that ordinary historical range rebuilds are `REPLAY_GENERATED`; `REPLAY_GENERATED` remains `admission_eligible=false` and cannot解除 provenance blocker by completeness alone.
4. The dense full-overlap root has no `source_lineage`, so it is weaker than the fog root and cannot be selected as authority.
5. R5 already identified horizon-safe episode continuity as the first runner blocker; even a future ranking source binding would not make the gate advance until exact identity/episode authority is settled.

Therefore the existing source state is partial: there is a best existing ranking-date/file candidate, but R6 cannot honestly declare `GO_EXISTING_SOURCE` without changing config, resolving input snapshot compatibility, or granting replay-generated artifacts authority they do not currently have.

## Minimal Next Frontier

唯一最小 R7：`R7-HORIZON-SAFE-IDENTITY-EPISODE-AUTHORITY` 唯讀卡。

R7 應先判定是否存在既有 trusted exact identity/episode 可讓 `NARROW_LEADER|BIG_BULL` 與 `NARROW_LEADER|BIG_BULL+HIGH_CHOPPY` 在 h3/h5/h10/h20 全部 horizon-safe；若不存在，明確回報需要 taxonomy/split authority decision。

fog source binding 保留為第二依賴，未到執行順位。Forward capture/admission provenance 另屬未來更高層工作，明確列為 why_not_more/do_not_absorb，不是目前 BC-CP2 capacity/research replay 的解除條件。

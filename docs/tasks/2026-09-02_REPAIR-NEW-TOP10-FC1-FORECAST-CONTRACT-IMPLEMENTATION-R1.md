# FC1 Forecast Contract Implementation Repair R1

工作名稱：P2／FC1 通用 Forecast Contract 最小實作修復；slice_id=`FC1-FORECAST-CONTRACT-01-R1`；traces_to=`FC1-FORECAST-CONTRACT-01`。

狀態：`REPAIR_REQUIRED / NOT_MERGED / TFM3-S1_NOT_ADMITTED`。

固定審查輸入：parent `ff3d30bcab1ad6c8abef01410706d81e9e998a4a`；candidate `f888141f60dc3a80a040a2c946fafc15ae0ac908`。

Review verdict：`REVIEW_NO_GO`。

P1 findings：

1. `app/research/dataset_bundle.py:489-537` 把 forecast channel set 限制成 `exactly one TARGET`，違反 FM0 `target_channels` plural 與 multivariate multiple-target contract。最小修法：支援一個以上 TARGET，使用 explicit contiguous `channel_index` 保序，並在 forecast trial spec 綁定 ordered `target_channel_ids`，不得退回單一 `target_channel_id`。
2. `app/research/dataset_bundle.py:541-558` 的 temporal availability 沒有 `event_at` 欄位，也未依 `TARGET / PAST_COVARIATE / FUTURE_KNOWN_COVARIATE` 分別驗證語意；現行 future-known covariate 沒有 `event_at` 仍可 `EXECUTABLE`。最小修法：加入 `event_at / available_at / forecast_origin`，並測試 target context、target horizon、past-only covariate、future-known covariate 與 leakage fail-closed。
3. `app/research/forecast_contracts.py:62-69` 與 `:256-260` 只做字串 sorted unique；`0.1` 與 `0.10` rehash 後可通過，未做到 quantile numeric uniqueness。最小修法：以 `Decimal` 正規化後檢查數值唯一、排序、範圍，並讓 trial spec 與 artifact receipt 共用同一 validator。
4. `app/research/forecast_contracts.py:202-267` 的 license propagation 只有任意 `sha256` refs 與 artifact equality，沒有 FM0 要求的 usage-policy boundary 或 effective usage statuses。最小修法：receipt 必須綁定 usage policy ref 或 license receipt shape，能表達 `RESEARCH_ONLY / SHADOW_BENCHMARK_ONLY / NO_PRODUCTION_SIGNAL_EXPORT / NO_B_DECISION_CONSUMPTION / NO_M4_M5_M6_M7_MUTATION`，未知或 production-like 使用必須 fail closed。

Reproduced evidence：

- `git diff --check ff3d30bcab1ad6c8abef01410706d81e9e998a4a f888141f60dc3a80a040a2c946fafc15ae0ac908`：PASS。
- changed-file allowlist：only `app/research/dataset_bundle.py`、`app/research/forecast_contracts.py`、`tests/test_forecast_contracts.py`、FC1 card。
- `cd <repo-root> && uv run pytest tests/test_forecast_contracts.py -q` on candidate snapshot：`9 passed`。
- probe on candidate snapshot：future-known channel without `event_at` returned `EXECUTABLE`；two TARGET channels returned `components[0].channels must contain exactly one TARGET`；`["0.1", "0.10", "0.9"]` quantiles rehashed returned no errors in both trial spec and artifact receipt。
- reviewer-card regression pair in archive snapshots fails on both parent and candidate due missing git/control artifacts; in main checkout it passes. Treat as environment/control-artifact dependency, not sufficient candidate-only blocker.

Repair acceptance：

- Add failing tests before or with repair for multiple TARGET acceptance, missing `event_at` rejection, role-specific temporal semantics, numeric duplicate quantile rejection after content hash recompute, and license usage boundary fail-closed.
- Keep scope contract-only and validator-only.
- Do not download models, run inference, create TimesFM adapter, mutate queue/runner, alter B0/C0/BC-CP2/M4-M7, push, deploy, or external write.
- After repair, run targeted FC1 tests、affected contract regression 與 `git diff --check`；兩個 control-artifact regression 必須在 parent／repair 相同且 git-aware 的隔離條件下比對，若環境依賴使比較無效則誠實記為非 FC1 baseline gap，不得以 dirty main checkout 單獨宣稱修復；最後交 fixed-SHA independent re-review。

Repair R1 outcome：

- Finding 1 closure：`FORECAST_CHANNEL_SET` now accepts one or more `TARGET` channels, keeps explicit contiguous `channel_index` ordering, and `forecast-trial-spec.v1` binds ordered `target_channel_ids` instead of legacy singular `target_channel_id`.
- Finding 2 closure：forecast channel temporal availability now requires `event_at / available_at / forecast_origin` and validates role-specific semantics for context target, future target, past covariate, and future-known covariate.
- Finding 3 closure：trial spec and artifact receipt quantile levels now use the same Decimal validator, rejecting numeric duplicates such as `0.1` and `0.10` after content-hash recompute.
- Finding 4 closure：forecast artifact receipt now requires `usage_policy_ref` plus effective usage statuses exactly limited to `RESEARCH_ONLY / SHADOW_BENCHMARK_ONLY / NO_PRODUCTION_SIGNAL_EXPORT / NO_B_DECISION_CONSUMPTION / NO_M4_M5_M6_M7_MUTATION`; missing, unknown, or production-like usage fails closed.
- Targeted tests：`uv run pytest tests/test_forecast_contracts.py -q` -> `17 passed`.
- Affected regression comparison：same isolated worktree command on repair and parent `ff3d30bcab1ad6c8abef01410706d81e9e998a4a` leaves `test_execution_plan_is_strict_identity_and_safety_contract` and `ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger` failing in both snapshots; classified as pre-existing control-artifact/baseline environment gap, not FC1-introduced.
- Diff hygiene：`git diff --check` -> PASS.
- Boundary：no model download, inference, TimesFM adapter, queue/runner, ranking, B0/C0/BC-CP2/M4-M7, production, push, deploy, or external write.

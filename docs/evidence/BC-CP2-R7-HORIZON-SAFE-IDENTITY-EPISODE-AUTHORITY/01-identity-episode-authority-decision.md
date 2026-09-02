# BC-CP2 R7 Horizon-safe Identity／Episode Authority Decision

## Receipt

- 任務：`BC-CP2-R7-HORIZON-SAFE-IDENTITY-EPISODE-AUTHORITY`
- 固定 parent：`b7ba1fc6065d6221353f7362db92ac7638bb8017`
- 任務卡 sha256：`b3c8706e0d2e6082f4694c0fe62d01605e1cde02580961e357f6be014f824bcb`
- Verdict：`NO_GO_IDENTITY_EPISODE_AUTHORITY_MISSING`
- 交付限制：只新增本檔；未修改 code/tests/config/history/features/ranking/taxonomy/split/horizon/workflow/runner/queue/scheduler/backtest/production/既有 evidence。
- 執行限制：未使用 ranking availability 或 outcome 選 identity；未執行 replay/full-720；未 merge/push/deploy/external write；未准入後續階段。

## Verification Receipt

- Fixed parent verified：start `HEAD` 為 `b7ba1fc6065d6221353f7362db92ac7638bb8017`。
- Card verification：任務卡 hash matched `b3c8706e0d2e6082f4694c0fe62d01605e1cde02580961e357f6be014f824bcb`；卡片為 delegation input，驗證後移除。
- Clean preflight：移除任務卡後工作區為 clean，再開始 evidence write。
- Changed-file allowlist：只允許 `docs/evidence/BC-CP2-R7-HORIZON-SAFE-IDENTITY-EPISODE-AUTHORITY/01-identity-episode-authority-decision.md`。
- Diff check：write 後通過 `git diff --check`。
- Temporary census script：`/private/tmp/top10-r7-identity-episode-census.py`，sha256 `54d6a7d657027fe7584043b44fb46540faf0ba5a88fddd56d3fe7056e1ffdd00`。
- Temporary census output：`/private/tmp/top10-r7-identity-episode-census.json`，sha256 `9d88199dc9b905581a98f6acabde77c40eacf1b3c03b7af7255650505ba737ef`。
- Census command exit：`0`；pyarrow emitted sandbox `sysctlbyname` warnings only，output JSON completed。

## Source Decision

CodeGraph 在本 worktree 回報未初始化，因此 source decision 降級為限域 helper read：

- `scripts/run_autonomous_research.py::canonical_regime_identity`
- `scripts/run_autonomous_research.py::regime_identity_id`
- `scripts/run_autonomous_research.py::regime_row_identity`
- `scripts/run_autonomous_research.py::validate_as_of_regime_rows`
- `scripts/run_autonomous_research.py::build_regime_episodes`
- `scripts/run_autonomous_research.py::statistical_lineage_authority`
- `app/modeling/sealed_oos.py::build_regime_episode_split`
- `scripts/run_backtest_strategy_matrix.py::exact_horizon_safe_ranking_dates`
- `scripts/run_backtest_replay.py::load_price_frame`
- `scripts/run_backtest_replay.py::market_trade_dates`

Helper/source hashes：

| Source | sha256 |
| --- | --- |
| `scripts/run_autonomous_research.py` | `2c5b9b11c22b13aeae78045a721c362f1ad65390ea69eac075e69f0807df951c` |
| `scripts/run_backtest_strategy_matrix.py` | `39b42aac6d7c232c9bbb4f1d8981b55ca43826758d91cd3a45281ff19f590b43` |
| `app/modeling/sealed_oos.py` | `b4e57673764f9aa9330fdef74b67c2170036109f43270f0153401859450e8e89` |
| `config/regime_research_contract.json` | `e3ada41e5a9de4f471750f298718ba815582db550abd9b537a73b66bd818bc34` |

## Absorption Boundary

Why not less：

- 必須對 taxonomy 的 28 個 required universal exact identities 全量 census；只查 R5 兩個 identity 會漏掉是否存在其他 trusted horizon-safe identity。
- 必須同時固定 rows、episodes、split verdict、development episode/date counts、h3/h5/h10/h20 safe counts 與 first failing reason；只報總數無法重現 authority gap。
- 必須使用 canonical split 與 horizon-safe helper；手算 episode 長度不足以證明 runner 第一邊界。

Why not more：

- R7 是唯讀 identity/episode authority census，不是 taxonomy/split/horizon policy repair。
- 不改 ranking source；R6 已證明 ranking overlap/source binding 是第二邊界，R7 先處理 episode continuity 第一邊界。
- 不做 replay/full-720，因為沒有任何 identity 具備 h3/h5/h10/h20 全 horizon-safe development dates，後續 replay 會在同一 runner blocker 前 fail closed。

Do not absorb：

- 不吸收 fog source binding、ranking backfill、ranking provenance、admission provenance 或 `FORWARD_CAPTURE`。
- 不吸收 taxonomy 合併、identity alias、episode split 調整、horizon 變更或便利樣本選擇。
- 不吸收 production daily ranking、scheduler/deploy、model training、candidate/shadow promotion。
- 不吸收任何新 registry、第二套 runtime 或非 canonical helper。

## Inputs

| Input | sha256 / value |
| --- | --- |
| `artifacts/market_regime_history_2026-05-29.json` | `4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70` |
| `data/clean/features.parquet` | `93e8432987b6037db243b2864f7bc8d09f12acd50249d9238d2acddacd2561d2` |
| `config/regime_research_contract.json` | `e3ada41e5a9de4f471750f298718ba815582db550abd9b537a73b66bd818bc34` |
| History rows | `218` |
| as-of check | `ok=true`, violations `[]` |
| Feature trade dates | `282`, range `2025-07-07..2026-08-31` |
| Horizon set | `3`, `5`, `10`, `20` |
| Identity set | `config/regime_research_contract.json` taxonomy `required_universal_regime_ids` |

## Census Summary

| Metric | Value |
| --- | ---: |
| Universal exact identities enumerated | 28 |
| Identities with rows | 16 |
| Split-OK identities | 2 |
| Identities safe for all h3/h5/h10/h20 | 0 |
| Qualifying identities | 0 |

Outcome-free selection rule：不以 ranking availability、return、PnL、win rate、Sharpe、alpha、target 或任何 outcome 欄位選 identity；所有 required universal exact identities 依 contract order 全量列舉。

## Per-identity Census

| Identity | Rows | Episodes | Max episode dates | Split | Dev episodes | Dev dates | h3 | h5 | h10 | h20 | First blocker |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `BROAD_RISK_ON|` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `BROAD_RISK_ON|BIG_BULL` | 6 | 3 | 1 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `完整盤勢 episode 不足，無法建立封閉切分` |
| `BROAD_RISK_ON|HIGH_CHOPPY` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `BROAD_RISK_ON|BIG_BULL+HIGH_CHOPPY` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `NARROW_LEADER|` | 14 | 7 | 2 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `完整盤勢 episode 不足：development_available=0 required=2 embargo_days=7 required_embargo_days=20` |
| `NARROW_LEADER|BIG_BULL` | 36 | 14 | 8 | OK | 3 | 6 | 0 | 0 | 0 | 0 | `NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE` |
| `NARROW_LEADER|HIGH_CHOPPY` | 5 | 2 | 3 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `完整盤勢 episode 不足，無法建立封閉切分` |
| `NARROW_LEADER|BIG_BULL+HIGH_CHOPPY` | 32 | 13 | 5 | OK | 3 | 3 | 0 | 0 | 0 | 0 | `NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE` |
| `CHOPPY_RANGE|` | 1 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `CHOPPY_RANGE|BIG_BULL` | 2 | 1 | 1 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `完整盤勢 episode 不足，無法建立封閉切分` |
| `CHOPPY_RANGE|HIGH_CHOPPY` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `CHOPPY_RANGE|BIG_BULL+HIGH_CHOPPY` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `RISK_OFF|` | 60 | 9 | 14 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `完整盤勢 episode 不足：development_available=0 required=2 embargo_days=30 required_embargo_days=20` |
| `RISK_OFF|BIG_BULL` | 13 | 5 | 6 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `完整盤勢 episode 不足：development_available=0 required=2 embargo_days=9 required_embargo_days=20` |
| `RISK_OFF|HIGH_CHOPPY` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `RISK_OFF|BIG_BULL+HIGH_CHOPPY` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `PANIC_SELLING|` | 23 | 2 | 13 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `完整盤勢 episode 不足，無法建立封閉切分` |
| `PANIC_SELLING|BIG_BULL` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `PANIC_SELLING|HIGH_CHOPPY` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `PANIC_SELLING|BIG_BULL+HIGH_CHOPPY` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `EARLY_REVERSAL|` | 1 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `EARLY_REVERSAL|BIG_BULL` | 2 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `EARLY_REVERSAL|HIGH_CHOPPY` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `EARLY_REVERSAL|BIG_BULL+HIGH_CHOPPY` | 0 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `MIXED_NEUTRAL|` | 5 | 2 | 2 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `完整盤勢 episode 不足，無法建立封閉切分` |
| `MIXED_NEUTRAL|BIG_BULL` | 2 | 0 | 0 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `episode_id 缺失或重複` |
| `MIXED_NEUTRAL|HIGH_CHOPPY` | 4 | 2 | 1 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `完整盤勢 episode 不足，無法建立封閉切分` |
| `MIXED_NEUTRAL|BIG_BULL+HIGH_CHOPPY` | 11 | 4 | 3 | FAIL | 0 | 0 | 0 | 0 | 0 | 0 | `完整盤勢 episode 不足，無法建立封閉切分` |

## Split-OK Identity Detail

`NARROW_LEADER|BIG_BULL`：

- Development episodes：`sha256:ab2442b043277e8b884856d3eade50987206a335d15449eb1a7df94155c1ee8a`, `sha256:5b93ba0b6cbc1c00d2bae026ff2cf30cba5505e7d8106ee76a9b5d31d74d0caa`, `sha256:cca35396aec295940b89b961aae1b52d59c3e2290153d635858217decf3a3764`
- Development dates：`2025-08-13`, `2025-08-15`, `2025-08-18`, `2025-08-27`, `2025-08-28`, `2025-08-29`
- h3/h5/h10/h20 safe-date counts：`0/0/0/0`
- First failing probe：ranking date `2025-08-13`，entry `2025-08-14`，h3 holding dates `2025-08-14`, `2025-08-15`, `2025-08-18`，全部跨出 ranking date 的 immutable episode。

`NARROW_LEADER|BIG_BULL+HIGH_CHOPPY`：

- Development episodes：`sha256:45bb53389aeb0c3639e89aeded85f73b72848b1e3d6c5881f6c108d733ab235d`, `sha256:b707c31b2893367e153d22fb3da9e58175bb3bd8afec20998c0cbd335123286b`, `sha256:96c97a341f104a04d19cb2a3d70233422969f81a22b7ca62053c0b9574e21945`
- Development dates：`2025-08-12`, `2025-08-14`, `2025-09-08`
- h3/h5/h10/h20 safe-date counts：`0/0/0/0`
- First failing probe：ranking date `2025-08-12`，entry `2025-08-13`，h3 holding dates `2025-08-13`, `2025-08-14`, `2025-08-15`，全部跨出 ranking date 的 immutable episode。

## Authority Gap

精確缺失：

1. Taxonomy 的 28 個 required universal exact identities 中，沒有任何 identity 同時具備 trusted split authority 與 h3/h5/h10/h20 safe development dates。
2. 26 個 identities 無法建立 split authority；主要原因是 zero/non-eligible episodes 或 complete episode 數不足，部分 identity 在 embargo/h20 split 下 development_available 為 0。
3. 唯二 split-OK identities 都在 h3 第一關失敗，原因是 D+1 entry 與 holding window 立即跨出 immutable episode；h5/h10/h20 因同一 continuity gap 也沒有 safe dates。
4. Ranking source binding 不是下一個可前進點；即使後續綁定 R6 的 fog ranking-date/file candidate，runner 仍會先停在 horizon-safe episode continuity。

因此本卡不能宣告 `GO_EXISTING_HORIZON_SAFE_IDENTITY`，也不是 `PARTIAL_HORIZON_SAFE_AUTHORITY`；沒有可供 BC-CP2 目前 h3/h5/h10/h20 matrix 使用的既有 horizon-safe exact identity/episode authority。

## Minimal Next Frontier

唯一最小下一卡：`R8-TAXONOMY-SPLIT-AUTHORITY-DECISION`。

R8 只做 policy/authority decision，不跑 replay/full-720、不選 outcome：

- 判定是否允許修改 taxonomy、split policy 或 episode construction，以解決 exact identity episode 過短與 h20 embargo 後 development_available=0 的問題；或
- 若不允許修改，正式關閉 BC-CP2 configured h3/h5/h10/h20 path，改回等待自然累積足夠 trusted complete episodes。

R6 fog source binding 保留為第二依賴；只有 R8 先解決 horizon-safe identity/episode authority 後，才值得回來處理 ranking source binding 與 horizon-safe runner rerun。

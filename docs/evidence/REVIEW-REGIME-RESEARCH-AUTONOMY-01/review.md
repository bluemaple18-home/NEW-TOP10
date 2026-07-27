# REVIEW-REGIME-RESEARCH-AUTONOMY-01

## Verdict

- verdict: `NO_GO`
- base: `7efda43641118f36b10261b4a04e0278bba941a2`
- candidate: `5cc87798804a48046cd9698b901e2b1bc8995871`
- reviewed_sha: `5cc87798804a48046cd9698b901e2b1bc8995871`
- review_scope: fixed `7efda43641118f36b10261b4a04e0278bba941a2...5cc87798804a48046cd9698b901e2b1bc8995871`
- candidate_modified: `false`
- merge_push_deploy_promotion: `not_performed`

## Reviewer Preflight

- review worktree: `<codex-review-worktree>/TOP10new`
- branch: `codex/review-regime-research-autonomy-01`
- pre-review HEAD: `c682c9a82f5e3d83b01e50fe9707ec6d6ae0c092`
- model: Codex／GPT-5 系列；執行環境未揭露更細型號
- reasoning: 執行環境未揭露
- candidate verification worktree: `<temporary-candidate-worktree>`
- base verification worktree: `<temporary-base-worktree>`

## Findings

### [P1] Exact-match 只限制 ranking 日，持有窗仍可跨入其他盤勢

- category: `correctness`
- path: `scripts/run_backtest_strategy_matrix.py`
- line: `143`
- evidence:
  - `exact_ranking_file_scope()` 只 patch `ranking_files()`，以 ranking filename 日期過濾。
  - `scripts/run_portfolio_replay.py:123` 仍從全市場交易日建立
    `holding_dates`，沒有要求 entry／holding／exit 全部位於同一 exact-match episode。
  - adversarial fixture 只允許 ranking 日 `2026-03-02`，仍建立
    `entry=2026-03-03`、`exit=2026-03-05` 的三日持有窗；後兩日沒有經過
    exact-match gate。
- risk: 正式 return、drawdown、winner 與 baseline metric 可混入 transition 或其他
  regime 的價格路徑，違反 AC-02 與「完整 episode」隔離契約。
- suggested_fix: 先建立預註冊 exact-match episode split，回測前驗證 ranking、
  entry、每個 holding bar 與 exit 都屬於同一允許 episode；跨界 trade 必須排除並
  fail loud。baseline 與 candidate 必須共用相同 episode IDs。
- validation_gap: 現有測試只斷言 ranking filename 被過濾，沒有跨 regime holding
  fixture。
- confidence: `high`
- status: `open`

### [P1] Closed manager 主流程沒有接上 pre-registration、episode split 與 sealed funnel

- category: `correctness`
- path: `scripts/run_autonomous_research.py`
- line: `1538`
- evidence:
  - `execute_topic()` 只依序執行 baseline matrix、candidate matrix、comparison。
  - `main()`（`1689-1738`）沒有建立 experiment、episode split、sealed registry
    或 append-only state transition。
  - 全 repo call-site 核對顯示 `build_regime_episodes()`、
    `build_experiment_pre_registration()`、`append_experiment_registry()`、
    `transition_experiment_registry()` 與 `build_regime_episode_split()` 只被測試或
    consolidated verifier 呼叫，未被 manager production path 呼叫。
- risk: CLI 雖在 artifact 宣告 `sealed_oos_required_before_policy_candidate=true`，
  實際執行仍是未預註冊的 coarse matrix；不能證明 split immutable、sealed 未揭封、
  state 不跳階或 forward shadow。
- suggested_fix: 在 closed mode 的 executable path 建立不可變 registration，
  將 exact-match episodes 綁定 dataset/split hash，依序執行並寫入每個 funnel
  transition；缺任一證據時不得執行下一階段。
- validation_gap: 現有測試分別測 helper，沒有從 CLI／manager 入口驗證完整狀態鏈。
- confidence: `high`
- status: `open`

### [P1] 真實 matrix 永遠缺 multiple-testing 證據，`NO_STRATEGY` 來自實作斷路

- category: `correctness`
- path: `scripts/run_backtest_strategy_matrix.py`
- line: `175`
- evidence:
  - `matrix_row()` 不產生 `combination_id`、`p_value`、
    `robust_neighbor_pass_count` 或 `drawdown_within_limit`。
  - `build_payload()` 在 `256` 直接把這些 rows 傳給
    `multiple_testing_gate()`；missing `p_value` 被當作 `1.0`，所有真實 row
    必然不合格。
  - adversarial fixture 的正常正報酬 matrix row 缺上述四欄，gate 固定回傳
    `MULTIPLE_TESTING_OR_ROBUSTNESS_FAILED`。
  - verifier 的 multiple-testing 正例是手工製造、已填齊四欄的 dict，沒有測 matrix
    integration。
- risk: closed workflow 結構上無法產生合格 candidate；所有 `NO_STRATEGY` 都可能是
  缺失統計與鄰域計算造成，而不是「完整評估後無策略」，正是 review 卡要求排除的
  implementation-gap misclassification。
- suggested_fix: 由實際交易／episode 結果計算預註冊 p-value、correction family、
  neighbor lineage 與 drawdown gate，並使用 parameter-universe 的 deterministic
  combination ID；若證據尚未計算，回傳 `INSUFFICIENT_EVIDENCE/BLOCKED`，不得冒充
  完整評估後的 `NO_STRATEGY`。
- validation_gap: 缺 matrix → statistical gate → round decision 的整合正例與反例。
- confidence: `high`
- status: `open`

### [P1] Episode split 只檢查 ID，允許相同交易日跨 split

- category: `correctness`
- path: `app/modeling/sealed_oos.py`
- line: `105`
- evidence:
  - split 僅驗證 `episode_id` 唯一與 `regime_id` 相同；`135-142` 也只比較 IDs。
  - adversarial fixture 提供四個不同 episode IDs、但每個都含相同
    `trade_date=2026-01-05`；function 成功分到 development／validation／embargo／
    sealed，且 metadata 仍寫 `episode_overlap=false`。
- risk: 同一天可同時影響調參與 sealed OOS，直接造成 temporal leakage，違反 AC-03。
- suggested_fix: 驗證每個 episode 的 trade dates 非空、內部唯一、與 start/end 一致；
  全部 episodes 的日期集合必須互斥且嚴格時間排序。metadata 必須由驗證結果計算，
  不得常數寫 `false`。
- validation_gap: synthetic negative 只測 mixed regime ID，沒有 duplicate dates、
  overlap、逆序或偽造 start/end。
- confidence: `high`
- status: `open`

### [P1] Sealed reuse 與 stitching 可藉 episode ID 別名繞過

- category: `correctness`
- path: `scripts/run_autonomous_research.py`
- line: `473`
- evidence:
  - reuse gate 只比較 `sealed_episode_ids` 字串集合（`483-495`），不比較 canonical
    trade-date set、dataset lineage 或 split contents。
  - composition gate 只檢查 source ID 數量與 boolean
    `fresh_composition_experiment`，不要求 source IDs 存在於 registry。
  - adversarial fixture 將相同 sealed dates 改名為 `episode-alias-a/b`，第二個
    experiment 得到 `REGISTERED`。
  - 拼接 fixture 引用一個不存在 registry 的 source，並以第三個 alias 重用相同
    sealed dates，仍得到 `REGISTERED`。
- risk: 已影響選擇的日期可再次冒充 fresh sealed OOS；跨實驗零件 lineage 也可偽造，
  違反 AC-04／AC-05。
- suggested_fix: registration 必須引用 verifier 產生的 immutable split artifact，
  以 canonical sealed trade-date hash／dataset slice hash 防重；所有 component source
  IDs 與 component hashes 必須存在且可追溯，fresh composition 必須證明新資料日期
  與所有 source experiments 不重疊。
- validation_gap: 現有反例只重用完全相同 episode ID，沒有 alias、同日期不同 hash 或
  unknown source。
- confidence: `high`
- status: `open`

### [P1] Universal gate 對缺失必要欄位 fail open，單一盤勢即可解鎖

- category: `correctness`
- path: `scripts/run_autonomous_research.py`
- line: `647`
- evidence:
  - `universe_declared_complete` 缺失時預設 `True`（`648`）。
  - `fresh_sealed_oos_per_regime` 缺失時預設 `True`（`670`）。
  - gate 不核對 taxonomy 所需盤勢集合、逐盤勢 sealed IDs、同一固定參數是否獨立浮現，
    也不要求跨盤勢 transition forward shadow。
  - adversarial minimal payload 省略兩個必要旗標，只提供一個 passing regime，仍回傳
    `UNIVERSAL_CANDIDATE_UNLOCKED`。
- risk: 不完整或偽造的 artifact 可取得 universal unlock，可能把單盤勢策略誤稱通用
  策略，違反 AC-09。
- suggested_fix: 所有必要欄位缺失一律 locked；由 contract taxonomy 與 coverage map
  推導 required regimes，逐一驗證固定 parameter hash、fresh unique sealed lineage、
  independent emergence、worst-regime pass 及 transition forward-shadow evidence。
- validation_gap: 現有反例只新增一個明確 failed regime，沒有 missing fields／missing
  regimes／duplicate sealed lineage／missing forward shadow。
- confidence: `high`
- status: `open`

### [P2] Topic eligibility 沒有進入執行選擇 gate

- category: `correctness`
- path: `scripts/run_autonomous_research.py`
- line: `1122`
- evidence:
  - `select_topics_for_run()` 只套 manager status／run count／cooldown，沒有檢查
    `topic.eligible`。
  - adversarial `eligible=false`、`reason_code=ZERO_INFORMATION_VALUE` topic 仍被選回。
- risk: coverage 已閉合、資訊價值為零或 deterministic scorer 判定不合格的區域仍可耗用
  compute 並寫入研究 artifacts，違反自主選題停止契約。
- suggested_fix: generate、queue、fallback 與 execute 四個入口都必須要求
  `eligible=true`；不合格原因寫入 monitor／coverage artifact，不得排入 runner。
- validation_gap: 現有測試只驗 scorer 回傳 eligibility，未驗證 selector 尊重結果。
- confidence: `high`
- status: `open`

### [P2] Consolidated verifier 綁定目前 worktree，無法依 review 卡固定 candidate

- category: `testing`
- path: `scripts/verify_regime_research_autonomy.py`
- line: `102`
- evidence:
  - `changed_paths(base)` 使用 `git diff --name-only <base>` 到目前 HEAD，並把全部 untracked
    files 加入 production no-change gate；沒有 candidate/end-ref 參數。
  - 在乾淨 candidate worktree：`26 checks / 0 failed`。
  - 在正式 review branch（只多 review 卡）：`26 checks / 1 failed`，且 card 指定 targeted
    test 變成 `20 passed, 1 failed`；唯一失敗是 review 卡不在 candidate allowlist。
- risk: verifier 不能在卡片要求的 review worktree 原樣重跑，也可能把 reviewer evidence
  誤報為 production change；反之，若 HEAD 超過 candidate，驗證範圍也會漂移。
- suggested_fix: 接受 `--candidate`，固定 diff `base...candidate`；production hashes 從
  candidate tree 讀取。review evidence／本地 untracked 應分開報告，不得改變 candidate
  verdict。
- validation_gap: 缺「candidate 後有 review-only commit」的 verifier regression test。
- confidence: `high`
- status: `open`

## Adversarial Fixtures

Fixtures 以 review-only 暫存腳本執行，沒有加入 candidate：

1. exact-match：只允許一個 ranking 日，證明持有窗仍延伸到未驗證日期。
2. episode split：不同 episode IDs 使用同一 trade date，split 仍成功。
3. sealed reuse：同一 sealed dates 改用不同 episode IDs，registration 仍成功。
4. stitching：引用不存在 registry 的 component source 並重用相同 sealed dates，仍成功。
5. universal：省略 complete/fresh flags、只放單一 passing regime，仍 unlocked。
6. selection：`eligible=false` topic 仍被 selector 選入。
7. multiple testing：真實 `matrix_row()` 缺四個必要 gate 欄位。

關鍵觀察：

```text
episode_split_overlapping_dates_admitted = true
sealed_same_dates_different_ids.reason_code = REGISTERED
stitching_unknown_source_and_reused_dates.reason_code = REGISTERED
universal_minimal_payload.reason_code = UNIVERSAL_CANDIDATE_UNLOCKED
ineligible_topic_selected = [review:ineligible-zero-coverage]
matrix_gate_missing_fields =
  [combination_id, drawdown_within_limit, p_value, robust_neighbor_pass_count]
exact_ranking_entry_holding_dates =
  ranking 2026-03-02 → entry 2026-03-03 → exit 2026-03-05
```

## Verification

### Fixed candidate

```bash
.venv/bin/python -m pytest -q \
  tests/test_regime_research_autonomy.py
```

- result: `21 passed in 2.43s`

```bash
.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_pm_research_harness_loop.py \
  tests/test_shadow_research_campaign.py \
  tests/test_feature_promotion_decision.py \
  tests/test_regime_research_autonomy.py
```

- result: `57 passed in 3.09s`

```bash
.venv/bin/python \
  scripts/verify_regime_research_autonomy.py \
  --base 7efda43641118f36b10261b4a04e0278bba941a2 \
  --output <temporary-output>/review-regime-candidate-verifier.json
```

- result: `26 checks, 0 failed`
- limitation: consolidated verifier 的 synthetic fixtures 沒有覆蓋本 review 的 bypasses。

```bash
.venv/bin/python -m pytest -q
```

- result: `507 passed, 1 failed, 246 subtests passed, 4 warnings in 73.73s`
- failure:
  `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`
- base reproduction: 固定 base worktree 的同一單測也為 `1 failed in 0.97s`。
- interpretation: 此 full-suite failure 是既有 artifact provisioning 問題，不是本次
  `NO_GO` 的 candidate regression 證據。

```bash
git diff --check \
  7efda43641118f36b10261b4a04e0278bba941a2...\
  5cc87798804a48046cd9698b901e2b1bc8995871
```

- result: `PASS`
- production model／baseline stats／正式 data／backtest paths candidate diff: 無變更。

### Review branch verifier scope reproduction

- targeted: `20 passed, 1 failed`
- verifier: `26 checks, 1 failed`
- failed check: `production_no_change.positive`
- extra path: `docs/tasks/2026-07-27_REVIEW-REGIME-RESEARCH-AUTONOMY-01.md`

## Contract Mapping

- exact regime identity canonicalization: deterministic，base 與排序後 family tag set 的
  helper 測試通過；但正式 trade path 僅過濾 ranking 日，故 Spec fail。
- parameter universe／combination IDs: 目前 720 組的 canonical hash 可重現，且誠實標記
  `PARTIAL_BLOCKED_SOURCE_UNKNOWN`；但 matrix `scenario_id` 未接上該 combination ID。
- sealed reuse／stitching: helper 對同字串 ID 可拒絕；canonical 日期 lineage 可被別名
  繞過，Spec fail。
- episode split／embargo: nominal episode-count 與 horizon-day fixture 通過；日期重疊與
  chronology 沒有驗證，Spec fail。
- multiple testing: synthetic dict gate 可拒絕 lucky winner；真實 matrix 沒有必要證據，
  integration fail。
- universal gate: 明確 failed regime 可鎖定；missing-field／missing-regime payload 可解鎖，
  Spec fail。
- `NO_STRATEGY`: 對缺 gate evidence 有 fail-closed 表面行為，但真實 runner 永遠不產生
  gate evidence，故屬 implementation gap，不足以證明無策略。
- production isolation: candidate 沒有修改 production model、ranking、權重或 promotion。

## Axis Conclusions

### Spec axis: `NO_GO`

Exact-match trade path、完整 episode split、sealed reuse、stitching、multiple-testing
integration、universal gate 與 closed manager lifecycle 均有 P1 缺口。Candidate 尚不能
證明原卡研究憲法。

### Standards axis: `NO_GO`

Targeted／affected tests 與 candidate verifier 綠燈，production 也未變；但測試主要驗證
未接線 helpers 的 happy path／單一 synthetic negative，沒有覆蓋 ID alias、日期重疊、
missing fields、missing regimes 與 CLI end-to-end。Verifier 也沒有固定 candidate end-ref。

## Remaining Risk

在上述 P1 修復前，不得把 closed-mode artifacts 當作 `REGIME_POLICY_CANDIDATE` 或
universal candidate 證據，也不得以目前 `NO_STRATEGY` 判定代表完整研究後無合格策略。

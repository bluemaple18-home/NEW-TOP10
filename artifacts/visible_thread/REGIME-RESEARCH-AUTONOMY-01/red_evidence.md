# Phase 0 Red Evidence

- command:
  `.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py`
- source_sha: `ebfffbd5b926b169dde353c6f1a888fe04fbd159`
- exit_code: `1`
- result: `6 failed in 0.03s`

## Expected Red Cases

| Case | Test | Observed red |
|---|---|---|
| 名稱含 regime 但沒有 current context | `test_regime_name_does_not_grant_eligibility_without_current_context` | missing deterministic topic scorer |
| base 相同但 family tags 不同 | `test_exact_base_match_rejects_family_tag_mismatch` | missing exact-match selector |
| transition / UNKNOWN 被硬塞 | `test_transition_and_unknown_are_not_forced_into_nearest_regime` | missing exclusion policy |
| sealed reuse | `test_used_sealed_episode_cannot_be_reused_as_new_oos` | missing contamination registry |
| 跨實驗事後拼接 | `test_cross_experiment_composition_requires_new_id_and_fresh_sealed_data` | missing composition guard |
| 全期間平均掩蓋單一盤勢失敗 | `test_universal_gate_rejects_full_period_average_when_one_regime_fails` | missing worst-regime gate |

六個失敗皆為 `AttributeError`，證明 `ebfffbd` 基準尚不存在對應的 deterministic
contract implementation。此證據只用來建立 red baseline；最終驗收仍要求正例與合成反例皆通過。

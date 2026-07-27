# REPAIR-REGIME-RESEARCH-AUTONOMY-01-01 Red Evidence

- captured_at: `2026-07-27`
- pre_repair_head: `0c2d0e441859ccf53c2210512c7671b8081616b6`
- fixed_parent_candidate: `5cc87798804a48046cd9698b901e2b1bc8995871`
- fixed_review_evidence: `e6bd85790b8873e1b4149bab1bb5afbe2fdcede1`
- command: `.venv/bin/python -m pytest -q tests/test_regime_research_autonomy.py`
- result: `20 passed, 9 failed in 2.47s`

## Red Mapping

| Finding | Red test | Observed pre-repair failure |
|---|---|---|
| REG-R001 | `test_exact_match_replay_rejects_holding_window_crossing_episode` | 完整 holding window 跨入另一 episode 時未 fail loud |
| REG-R002 | `test_closed_manager_cli_writes_registration_split_and_append_only_trace` | CLI output 缺 `closed_experiment_registry`，真實入口未建立 registration/split/trace |
| REG-R003 | `test_real_matrix_row_contains_pre_registered_statistical_evidence` | 真實 `matrix_row()` 缺 `combination_id` 與統計證據 |
| REG-R004 | `test_episode_split_rejects_overlapping_trade_dates_across_alias_ids` | 不同 episode alias 共用相同日期仍成功切分 |
| REG-R005 | `test_sealed_reuse_rejects_same_dates_hidden_behind_episode_aliases` | 相同 sealed dates 改名後仍 `ok=true` |
| REG-R005 | `test_stitching_rejects_unknown_component_source_and_untraceable_hash` | unknown component source 與不可追溯 hash 仍 `ok=true` |
| REG-R006 | `test_universal_gate_fails_closed_on_missing_fields_and_missing_regimes` | 缺必要旗標與 required regime 仍 `unlocked=true` |
| REG-R007 | `test_ineligible_topic_is_excluded_from_selection_and_fallback` | `eligible=false` topic 仍被 selector 選入 |
| REG-R008 | `test_consolidated_verifier_has_positive_and_synthetic_negative_checks` | `build_report()` 不接受固定 `candidate` end-ref |

## Interpretation

九個 failure 都命中 Reviewer 描述的舊行為；沒有 production 修復前即綠燈的假陰性，也沒有
fixture setup error。後續以同一 targeted command 作 red→green 判定。

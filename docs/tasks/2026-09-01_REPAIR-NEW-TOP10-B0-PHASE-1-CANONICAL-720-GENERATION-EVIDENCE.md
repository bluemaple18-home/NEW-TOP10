# B0 Phase 1 Canonical 720 Generation Evidence Repair 派工卡

工作名稱：修正 B0 720 generation／identity／partition 證據

任務簡介：修正 B0 Phase 1 對 canonical main `35bb9927eb0eac9a624dcaf0dcffcbf88857c070` 的漏讀；固定證據已顯示 `parameter_combinations()` 從 canonical executable values 產生 720 組、建立 deterministic `combination_id`，`parameter_universe_summary()` 固定 legal IDs/hash，且 validation profiles 會對 global legal IDs 做 partition membership 檢查。不得把此 finding 擴張為 B1 implementation 或完整產品矩陣 authority。

來源與依賴：repair_id=`B0P1-R2-CANONICAL-720-PATH`；parent=`d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98`；canonical main=`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`；source=`scripts/run_autonomous_research.py:493-575`、`app/research/parameter_catalog.py:87-159`、`config/research_parameter_catalog.json`；下游 blocker=`BC-CP2 @ 36ba9df44539cc42e663a48be7d6f8577fd888fc`。

執行規範：你是 GPT-5.5 high strict/core-bounded Repair Worker；Sol 只做 Mainline 裁決與驗收。只可修改 B0 Phase 1 的 `03-e1-e4-initial-cost-classification.md`、`04-bc-checkpoint-input.md` 與本卡；不得修改 code、config、workflow、C0／BC-CP2 evidence，不得准入 B0 Phase 2／B1／C1，不得 merge、push、改 Issue 或 external write。

驗收與交接：以固定 SHA 重算 720、ID 唯一性、ID hash 與 validation-profile subset；精確區分「formal executable 720 path 已證明」與「larger product matrix authority 仍 missing」。需通過範圍核對、`git diff --check` 與獨立 fixed-SHA review；完成後只用繁中回報固定 SHA、修正 claims、驗證與仍未證明項。

## Repair receipt

status: CANDIDATE_REPAIRED_PENDING_REVIEW
fixed_source_sha: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
parent_candidate: `d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98`
characterization_observed_at: `2026-09-01T07:18:37Z`

重算結果：
- `combination_count=720`
- `unique_ids=720`
- `universe_legal_count=720`
- `global_family_size=720`
- `combination_id_hash=sha256:78cd9b8b6fa39935f9037d5b4c8dde3fcc2ae39955414aa51bda96dafb69f6b4`
- `global_family_id=sha256:79899da01ead21b31ebd48571e2e3b6460f65946dad86bab7e5a1d546a0b4baa`
- `partition_status=PARTITION_COVERAGE_INCOMPLETE`
- `covered_unique_count=242`
- `missing_count=478`
- `cross_partition_overlap_count=32`
- `partition_counts={'standard': 81, 'risk_guard': 81, 'long_horizon': 81, 'tight_exit': 36}`

修正邊界：B0 03/04 只改為承認 formal executable 720 generation、unique identity、global family hash 與 validation-profile partition authority 已證明；仍明確保留 larger product matrix authority missing、E3 capacity unmeasured、E2 not proven、E4 required/uncharacterized、B0 Phase 2/B1 not admitted。

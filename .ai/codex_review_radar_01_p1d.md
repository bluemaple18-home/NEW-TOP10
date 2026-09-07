# RADAR-01 P1-D independent strict review

- chain_id：`RADAR-01-P1-D-STRICT-20260907`；base SHA `23401329f9ffea56b99765f821c29eb57e17caf7`；candidate working-tree composite digest `sha256:afcfafea1f77334f9365e16e8a243de58372fbca47b54db8fd277b9de1ca1321`。
- 請讀：`AGENTS.md`、`docs/tasks/2026-09-07_CARD-RADAR-01-P1-D-HISTORICAL-STATISTICS-BASE-RATE.md`、`.work/RADAR-01-P1-D/review/review_plan.json`、`app/signals/historical_statistics.py`、`app/signals/scanner.py`、`tests/test_signal_historical_statistics.py`，並檢查相對 base 的完整 diff。
- 必答：baseline 是否真的同 universe/window/horizon/direction 且無 caller injection；H-session outcome/MAE 是否無 future leakage 或 off-by-one；effective-N overlap policy 是否正確閉合；missing/unobservable/tail 是否 fail-loud；所有 public input/type/identity drift 是否只出 stable reason；nested immutability/content ID/provenance 是否完整；scanner seam 是否造成 P1-B regression；是否越權碰 eligibility/ranking/research/runtime。
- 驗證：可唯讀跑 P1-D tests 與受影響 regression；不得修改任何檔案。只有可重現 P0/P1 才 `NO_GO`；P2/P3 列 residual risk，不得移動 scope。
- 輸出：`verdict`、candidate digest、測試、findings（id/severity/category/path/line/evidence/risk/suggested_fix/validation_gap/confidence）與剩餘風險；Mainline acceptance required。

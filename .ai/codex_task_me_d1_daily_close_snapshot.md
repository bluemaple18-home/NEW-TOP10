# Worker task — CARD-ME-D1-DAILY-CLOSE-SNAPSHOT-01

請先讀：

- `AGENTS.md`
- `docs/tasks/2026-09-07_CARD-ME-D1-DAILY-CLOSE-SNAPSHOT-01.md`
- `docs/evidence/ME-D1-DAILY-CLOSE-SEAM-AUDIT-20260907.md`
- `app/pipeline/validation_snapshot.py`
- `app/pipeline/fetch_stage.py`
- `app/research/dataset_bundle.py`
- `app/research/run_receipts.py`

目標：直接實作卡片的 `ME-D1-SLICE-001`～`003` code／tests。請採 TDD，修改你的 forked workspace，最後回報變更檔案與驗證結果；不要修改卡片、backlog、frontier、handoff、`.work` 或其他 control/evidence 文件。

必要行為：

1. 沿既有 pipeline seam 新增 provider-neutral finalized Daily Close snapshot contract；不要建立 registry／ledger／scheduler／resolver。
2. canonical records 必須排序且 deterministic；required null、duplicate `(date, stock_id)`、invalid market、invalid OHLC、negative volume/value、price-basis 或 finalization drift需 fail loud。missing 不得補 `0`。
3. manifest 至少包含 exact source/provider identity、adapter/endpoint contract、UTC `fetched_at`、finalization、price basis、coverage、business-day gap／partial-market evidence、records fingerprint 與 snapshot identity。無資料日只能標示 unresolved/no-observation，不能猜成休市或抓取成功。
4. snapshot data／manifest 使用 content-addressed immutable path；同一完整輸入契約 identity 相同；既有 collision 必須 fail closed。可沿用 `write_immutable_json` 與 research `content_hash`，不得以 mutable path 作 identity。
5. FetchStage 在 provider acquisition 後、FinMind／indicator enrichment 前 materialize 並重新載入固定 snapshot；把 identity/path/coverage 放入 context stats。validation-only snapshot seam 必須保持離線相容。
6. DatasetBundle 以 versioned consumer contract新增 `DAILY_CLOSE_SNAPSHOT` component，保留既有 v1 consumers 不破壞。component content id 必須對上已驗證 Daily Close manifest。
7. `begin_topic_attempt` 增加向後相容的 explicit Daily Close manifest path；提供時 requested/executed bundle與 receipt lineage 都必須綁同一 snapshot，未提供時既有行為不變。若需要，為 `scripts/run_autonomous_research.py` 增加 optional CLI argument並傳入；不得改 runtime/default production behavior。
8. canonical Research Matrix dimension growth 必須為 0；不改 TrialSpec parameters、backtest math、ranking、publish、scheduler 或 production。

允許修改：

- `app/pipeline/daily_close_snapshot.py`（可新增）
- `app/pipeline/fetch_stage.py`
- `app/research/dataset_bundle.py`
- `app/research/run_receipts.py`
- `scripts/run_autonomous_research.py`（僅 optional manifest plumbing）
- `tests/test_daily_close_snapshot.py`（可新增）
- `tests/test_validation_snapshot_adapter.py`
- `tests/test_research_dataset_bundle.py`
- `tests/test_autonomous_research_receipts.py`

驗證：

- 先跑新增的 focused tests，再跑上述四個 test modules。
- 跑 `git diff --check`。
- 不連外、不使用 production data 作 write target、不 commit、不 push。
- 若需要超出 allowlist 或發現 contract fork，立即停止並回報，不自行擴 scope。

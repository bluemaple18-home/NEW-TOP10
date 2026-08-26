# Checkpoint 0｜Fog revalidation preflight

## 判定

`PREFLIGHT_PASS_TO_BUILD_TRUSTED_ENTRYPOINT`。這只允許建立與測試 validation-only fog
entrypoint；不代表 fog 週期或 production 通過，也不授權啟用 launchd。

## Dispatch、trace 與 Git

- Formal thread：`019fc69c-05c8-70b2-b7c4-db332f382805`。
- projectId：`local-49c40f44270697f9bce80f898c3c5a4d`。
- provisioning source／啟動 HEAD：
  `80d9160be0347680688f6dbc62bf45a5d1dffb1e`，兩者相同。
- source candidate：`a798a13785c505c73a005b7e045226f51f99dda9`；
  `git merge-base --is-ancestor` 通過。
- worktree 是獨立 Codex worktree、detached HEAD；啟動時 clean，實際 git-dir 無
  `index.lock`。
- 本卡四個 trace anchors 均存在：parent task 的 `AC-1`、`AC-2`、`AC-3`、`AC-5`。
- provisioning commit 相對 source candidate 只新增本卡；未混入其他實作。

## CodeGraph 與 strict fact gate

CodeGraph semantic query 回報本 worktree 尚未初始化。建立 `.codegraph` 會超出本卡
allowlist，因此依規則記為 `CONTEXT_DEGRADED / CODEGRAPH_NOT_INITIALIZED`，改用限域 source
inspection。

Source facts：

- trusted entrypoint contract 的 public boundary 是
  `load_trusted_validation_entrypoint()` → `run_guarded_job()`；CLI 只接受
  `validate-run --entrypoint-contract`，沒有 raw command remainder。
- digest、job、scope 與 spawn 前 TOCTOU 驗證位於 `app/storage_safety.py`；CLI root、marker、
  input/output 與 runtime cache 收斂位於 `scripts/storage_safety.py`。
- 現有 fog business entry 是 `scripts/run_fog_research_worker.sh`；它再執行既有 fog map、
  research quota、status rollup 與 representative replay drain，不由本卡重寫。
- 本卡預計只新增 `scripts/storage_validation/fog_research_worker.py` 與
  `tests/test_fog_storage_validation.py`，再寫本卡 evidence／狀態。既有 storage public API、
  policy ceiling、其他七個 job 與 business logic 不改。
- adapter 介面固定為 digest-pinned Python entrypoint；不接受 command remainder。執行資料只用
  sandbox clone；production checkout、data、artifacts、models 只作 copy 前唯讀來源。

## Main protected state

Main checkout 啟動時既存 dirty state：

- `scripts/build_weekend_universe_inventory.py`：
  `c1ff76dcdc125248b3c5aa137ba1344eaa84c8ca2fd08b1c404be58a1fdef538`
- `tests/test_weekend_universe_inventory_snapshot.py`：
  `ef233dd7b3814044134457d928f3bef0cb7b098b80c457b985b7d290af0961c9`
- `docs/tasks/2026-08-02_TOP10-STORAGE-RUNAWAY-01.md`：
  `f93c6fb025b31379c6dd35110e8f081739437c77b30214de43629691517fcdea`

以上三個檔案不在本卡提交範圍；收尾必須重算並完全相同。

## 主機容量、swap、程序與 open-deleted

- filesystem total：`245107195904` bytes。
- host free：`49552089088` bytes；高於啟動門檻
  `max(32212254720, 15%) = 36766079385.6` bytes。
- runtime reserve：`max(21474836480, 10%) = 24510719590.4` bytes。
- swap metric 可讀：total `6144.00 MiB`、used `4875.50 MiB`、free `1268.50 MiB`。
- storage measure 正確維持 production `NO-GO / POLICY_NOT_LIVE_VERIFIED`；validation-only
  path 尚未啟動。
- 目標程序掃描沒有 `run_fog_research_worker`、`storage_safety.py validate-run`、
  `run_top10_fog_map_handoff` 或 representative replay workload。Codex app 的 node／shell cwd
  屬已知控制面，不是 TOP10 job。
- `lsof +L1` capability 可用，沒有 TOP10 open-deleted file。

## Launchd 與 restart denial

下列八個 label 在 `launchctl print-disabled gui/<uid>` 均為 `disabled`，且逐 label
`launchctl print` 均為 `NOT_LOADED`：

- `com.new-top10.daily`
- `com.new-top10.retrain`
- `com.new-top10.reference`
- `com.new-top10.fog-research-worker`
- `com.new-top10.pm-research-harness`
- `com.new-top10.external-review`
- `com.new-top10.external-review-preflight`
- `com.new-top10.baseline-harness`

Main checkout 沒有 live fog restart-denied marker。Parent evidence 內唯一封存 marker 明確屬於
`daily` 的 hard-RSS stop-loss drill，並非 fog 或未知 live marker；因此沒有 marker ownership gap。
本卡不清除任何 marker；若 cycle stop，guard 必須在專屬 sandbox 留下 fog marker。

## Bounded sandbox copy budget

核准 copy 僅含 reviewed tracked source、main `.venv`、`data`、`models`，以及 fog 實際需要的
下列 artifacts input：

- `artifacts/autonomous_research`
- `artifacts/weekend_training`
- `artifacts/harness_status`
- `artifacts/research_map`
- `artifacts/research_reviews`
- `artifacts/backtest`
- `artifacts/market_regime_history.json`

copy 前盤點約 `2.60 GiB` logical input。fog policy meter 只涵蓋 logs 與明列 fog artifacts；
上述初始 meter input 約 `0.51 GiB`／`13,884` files，低於
`2,147,483,648` bytes／`30,000` files。即使 copy 後再消耗完整 `max_bytes`，host free 仍預估
約 `44.4 GiB`，高於 runtime reserve 約 `22.8 GiB`。copy 不包含 `.git`、symlink、browser、
provider、其他專案或 production output redirect。

## Preflight conclusion

Trace、capacity、process、launchd、protected hash 與 marker ownership 均可判定；沒有啟動前
blocker。下一步只允許 RED／GREEN trusted entrypoint。Seatbelt executable 與實際 confinement
probe 必須在測試與每次 cycle spawn 前通過；否則立即 fail closed。

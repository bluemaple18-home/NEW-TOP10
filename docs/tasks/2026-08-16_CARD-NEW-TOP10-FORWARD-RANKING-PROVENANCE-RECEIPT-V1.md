---
id: CARD-NEW-TOP10-FORWARD-RANKING-PROVENANCE-RECEIPT-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: runtime-contract
risk: critical
model: gpt-5.6-sol
reasoning: high
cycle: 24
production_change_allowed: false
runtime_change_allowed: true
network_allowed: false
---

# Forward Ranking Provenance Receipt V1

## 工作名稱 → 正在做什麼 → 現在狀態

`Forward Ranking Provenance Receipt V1` → 讓新產生的 research baseline／regime-shadow ranking 同步產生完整 provenance receipt → `READY_FOR_ARCHITECTURE_AND_IMPLEMENTATION`

## Root question

如何讓未來 ranking 在產生當下就固定 artifact、producer、model、config、universe與top-N lineage，供後續 admission；同時禁止拿新契約回填舊 ranking？

## 固定 producer scope

- `scripts/build_historical_ranking_replay_set.py`：research baseline ranking set。
- `scripts/research_regime_shadow_ranking.py`：regime-shadow ranking set。
- 共用 receipt builder／validator放在 `app/research/`。
- 不修改 `app/agent_b_ranking.py` 的 production daily輸出契約；production接入另卡處理。

## Receipt contract

每個新 `ranking_YYYY-MM-DD.csv` 必須同步建立一筆 `ranking-provenance-receipt.v1`，並綁定：

- `scenario`、`ranking_date`、`run_identity`、`receipt_identity`；
- ranking artifact repo-relative path與生成後 bytes SHA256；
- producer entrypoint、source commit、source bytes SHA256；
- model artifact path/version/content SHA256；
- config path/content SHA256；
- universe snapshot path/content SHA256；
- feature/calendar source path/content SHA256；
- top-N、sort policy、tie-break policy；
- capture mode只允許 `FORWARD_CAPTURE`或`REPLAY_GENERATED`，永遠禁止 `BACKFILLED`。
- `REPLAY_GENERATED`固定 `admission_eligible=false`；不得因 receipt 完整就升級。
- `FORWARD_CAPTURE`只接受單一 ranking date、該日等於 producer明示且驗證的 capture trade date，並固定 `admission_eligible=pending_registration`。

六欄必須共享同一 scenario/date/run/artifact identity；receipt缺欄、hash無法計算、source commit無法解析、輸入在 run 前後漂移或 artifact被覆寫即整批 fail closed。

## Write／registration boundary

- ranking寫完後立即由同一 producer建立 receipt；receipt採 canonical JSON與 atomic replace。
- batch manifest列出每個 ranking path/hash、receipt path/hash及共同 run identity。
- artifacts仍是 runtime output；本卡不得自動 `git add/commit/push`。
- 未來只有經獨立 registration 卡將完整 receipt bundle納入 committed evidence後，admission authority才可啟用。
- 新 receipt不得宣稱舊 ranking具 contemporaneous provenance；既有 50 筆歷史 inventory維持 NO-GO。

## Historical／forward 時間邊界

- `build_historical_ranking_replay_set.py` 的一般日期區間重建永遠是 `REPLAY_GENERATED`，不能解除 provenance blocker。
- 只有明示 `--forward-capture`、單一日期、日期等於 capture trade date，且所有 strict inputs通過時，baseline research producer才能寫 `FORWARD_CAPTURE`。
- `research_regime_shadow_ranking.py` 對批次／過去日期同樣固定 `REPLAY_GENERATED`；forward模式只允許同一單日。
- Shadow 的 `dates-from-dir` ranking檔只提供排程日期，不是 scoring input；receipt必須標為 `calendar_schedule_source`並 hash-bind其 bytes，禁止宣稱它是 baseline ranking lineage。
- 本卡建立 research forward collection能力，不改 production daily ranking；部署／排程另卡處理。

## Immutable model與排序

- receipt模式不得直接把 `latest_lgbm.pkl`、default或fallback path當 model identity。
- producer先把 resolved model bytes複製成 run-local content-addressed immutable snapshot，再由該 snapshot載入；receipt只引用 snapshot path/hash/version。
- config與universe不可 fallback；缺檔即失敗。Features、universe、config、model與shadow額外輸入都做 run前後hash比對。
- 輸出排序固定 stable `score DESC, stock_id ASC`，必須有連續 rank、唯一 stock_id且 row count恰等於top-N；不足即fail closed。

## Atomic bundle

- 使用 run-unique staging directory；禁止覆寫既有 ranking、receipt或 COMPLETE manifest。
- `batch_plan_id`由 run/scenario/producer與預定日期/path清單計算；receipt綁 plan ID，final manifest再綁每筆 ranking/receipt bytes hash，避免循環 hash。
- 任一日期失敗只能留下 FAILED/INVALID run marker，不能產生 COMPLETE manifest或發布半批次。

## Fail-closed

- dirty／unresolved producer source：source commit與source bytes不匹配即拒絕產生可 admission receipt。
- `latest`或default fallback不得出現在 receipt identity；實際 resolved path/hash必須固定。
- model/config/universe/features在 run 前後 hash不一致即失敗，已寫出的候選 bundle標 invalid，不得發布為完整 manifest。
- duplicate scenario/date、同 artifact不同 receipt、同 receipt identity不同 bytes、top-N與實際 ranking row count不符即失敗。
- past-date replay、日期區間或 capture date不符若標成 `FORWARD_CAPTURE`即失敗。
- 不讀 return、future price、PnL、win rate、Sharpe、alpha、target或 sealed outcome；不執行 replay/promotion。

## 允許產出

- `app/research/ranking_provenance_receipt.py`
- 修改上述兩個 research producer與相關 tests。
- fixture／deterministic verifier；不得執行實際歷史重建。

## 驗收

- 共用 builder／validator／canonical encoder有正向與負向測試。
- baseline與shadow producer測試證明每個 ranking都有 receipt，manifest雙向 hash-bind。
- 測試 historical replay永遠不可 admission；forward模式只准同一單日。
- 測試 `dates-from-dir`只屬 calendar schedule source，不得被標成 baseline scoring lineage。
- 測試 content-addressed model snapshot與 stable score／stock_id排序。
- 測試 source drift、input drift、overwrite、duplicate、wrong date、row-count/top-N、BACKFILLED、absolute path、outcome key、noncanonical bytes都fail closed。
- 舊 ranking不會在沒有重跑producer時被補 receipt。
- 聚焦 tests、既有 producer regression、`git diff --check`與獨立 Review通過。
- 不部署、不執行正式 ranking、不 push。

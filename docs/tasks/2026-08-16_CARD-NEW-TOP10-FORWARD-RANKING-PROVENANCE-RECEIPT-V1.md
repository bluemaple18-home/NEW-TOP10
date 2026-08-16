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
- capture mode固定為 `AT_GENERATION`，不得是 `BACKFILLED`。

六欄必須共享同一 scenario/date/run/artifact identity；receipt缺欄、hash無法計算、source commit無法解析、輸入在 run 前後漂移或 artifact被覆寫即整批 fail closed。

## Write／registration boundary

- ranking寫完後立即由同一 producer建立 receipt；receipt採 canonical JSON與 atomic replace。
- batch manifest列出每個 ranking path/hash、receipt path/hash及共同 run identity。
- artifacts仍是 runtime output；本卡不得自動 `git add/commit/push`。
- 未來只有經獨立 registration 卡將完整 receipt bundle納入 committed evidence後，admission authority才可啟用。
- 新 receipt不得宣稱舊 ranking具 contemporaneous provenance；既有 50 筆歷史 inventory維持 NO-GO。

## Fail-closed

- dirty／unresolved producer source：source commit與source bytes不匹配即拒絕產生可 admission receipt。
- `latest`或default fallback不得出現在 receipt identity；實際 resolved path/hash必須固定。
- model/config/universe/features在 run 前後 hash不一致即失敗，已寫出的候選 bundle標 invalid，不得發布為完整 manifest。
- duplicate scenario/date、同 artifact不同 receipt、同 receipt identity不同 bytes、top-N與實際 ranking row count不符即失敗。
- 不讀 return、future price、PnL、win rate、Sharpe、alpha、target或 sealed outcome；不執行 replay/promotion。

## 允許產出

- `app/research/ranking_provenance_receipt.py`
- 修改上述兩個 research producer與相關 tests。
- fixture／deterministic verifier；不得執行實際歷史重建。

## 驗收

- 共用 builder／validator／canonical encoder有正向與負向測試。
- baseline與shadow producer測試證明每個 ranking都有 receipt，manifest雙向 hash-bind。
- 測試 source drift、input drift、overwrite、duplicate、wrong date、row-count/top-N、BACKFILLED、absolute path、outcome key、noncanonical bytes都fail closed。
- 舊 ranking不會在沒有重跑producer時被補 receipt。
- 聚焦 tests、既有 producer regression、`git diff --check`與獨立 Review通過。
- 不部署、不執行正式 ranking、不 push。

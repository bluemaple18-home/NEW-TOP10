# Handoff: MARKET-CONTEXT-01 外部每日大盤追蹤研究

## Goal

把外部每日大盤追蹤網站研究整理成 TOP10new 可接手開發的 market context layer 方案。

## Root Question

TOP10new 應該從外部 dashboard 參考什麼，且如何避免把未回測權重或 iframe UI 直接抄進 production？

## Blocker

無實作 blocker。研究已整理完成。

## Fork

候選 fork 有兩個：

- 推薦路線：先做 `market_context_YYYY-MM-DD.json` artifact，再接 daily report，最後做 shadow regime。
- 不推薦路線：直接改 `RankingPolicy` 或抄外部戰略溫度計權重。

## Completed Actions

- 爬過外部 WordPress 包頁與 GitHub Pages iframe。
- 用 headless Chrome DevTools Protocol 檢查 runtime network。
- 確認 iframe dashboard 沒有 runtime 市場資料 API，資料是預先渲染。
- 查公開 repo `tetsu811/tw-stock-dashboard` 的檔案結構、workflow、README、data source 與 generate flow。
- 對照 TOP10new 的 `app/data_fetcher.py`、`app/trading/market_regime.py`、`app/trading/ranking_policy.py`、`app/agent_b_ranking.py`、`app/reason_generator.py`。
- 產出主文件：`docs/tasks/2026-05-28_MARKET-CONTEXT-01_external_dashboard_research.md`。

## Active State

本次只新增文件，沒有修改 production code。

接手前請執行：

```bash
cd <repo-root>
git status --short
git worktree list
```

整理前已觀察到本機有既有 dirty files：

- `models/baseline_stats.json`
- `models/latest_lgbm.pkl`
- `scripts/build_clawd_publish_payload.py`

這些不是本次研究文件新增造成的變更，接手者不要直接覆寫。

## In Progress / Remaining Work

下一步建議開 `MARKET-CONTEXT-02`：

- 新增 market context fetcher。
- 輸出 `artifacts/market_context_YYYY-MM-DD.json`。
- 先接 artifact，不接 ranking 權重。

## Waiting Conditions

若要開發，需要確認：

- 接手者是否在獨立 worktree 或 branch。
- 是否允許新增 `app/market_context_fetcher.py` 或偏好放入 `app/pipeline/`。

## Limits

- 不要直接改 `risk_adjusted_score`。
- 不要把外部戰略溫度計權重接進 production ranking。
- 不要照抄 WordPress iframe。
- 不要讓非核心外部 API 失敗阻塞 daily ranking。
- 共享指令與文件只使用 repo-relative path。

## Verification

本次沒有跑 TOP10new test，因為只做研究與交接文件。

已驗證研究事實：

- 外部 iframe runtime 只載入 HTML、Chart.js、favicon。
- 外部 repo workflow 週一到週五台灣時間 18:00 產生並 commit 靜態 dashboard。
- 外部 dashboard 資料當時為 `2026-05-25 21:31:59`，不是 `2026-05-28` 最新快照。

## Changed Files

- `docs/tasks/2026-05-28_MARKET-CONTEXT-01_external_dashboard_research.md`
- `.work/current/brief.md`
- `.work/current/status.md`
- `.work/current/context_manifest.md`
- `.work/current/handoff.md`

## Do Not Touch

- 既有 dirty files，除非使用者明確要求：
  - `models/baseline_stats.json`
  - `models/latest_lgbm.pkl`
  - `scripts/build_clawd_publish_payload.py`

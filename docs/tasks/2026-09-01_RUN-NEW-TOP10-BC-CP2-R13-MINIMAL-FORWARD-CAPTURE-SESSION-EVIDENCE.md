# 工作名稱：BC-CP2 R13 最小 Forward-Capture Session Evidence

任務簡介：使用既有 first-party seam，在 fresh local inputs 與 trusted contemporaneous trade date 都成立時執行一次隔離 create→capture→verify；任一前置 authority 缺失即停止，不得以歷史日期、舊 ranking 或 replay 代替 forward capture。

來源與依賴：slice_id=`BC-CP2-R13-FORWARD-CAPTURE-SESSION-01`；canonical main=`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`；fixed parent／R12=`48d0f2ba57dcfcad0d9f32153d185d62a882f157`；R12 evidence=`docs/evidence/BC-CP2-R12-RANKING-PROVENANCE-AUTHORITY-DECISION/01-forward-capture-or-defer.md`；session clock=`2026-09-01 / Asia/Taipei`；historical corpus 永久 `NON_ADMISSION`。

執行規範：你是 GPT-5.5 high strict/core-bounded Session Worker；Sol Mainline 只做監工與驗收。先唯讀確認 existing producer command、single-date `FORWARD_CAPTURE` gate、trusted completed market trade date、local features／universe／model／config freshness與 exact hashes。只有全部 PASS 才可用現有 CLI 在 `/private/tmp/top10-r13-forward-capture-session/` 執行一次；不得修改 seam 或放寬 validator。

Fail-closed：不得把 2026-05 historical data、fog root、old manifest、`REPLAY_GENERATED`、自填舊 capture date 或 filename coverage 當 contemporaneous authority。若 session clock／market calendar／local inputs 無法共同證明同一 fresh completed trade date，回 `BLOCKED_FRESH_INPUT_OR_TRUSTED_DATE_AUTHORITY`，且 capture／bundle／verification 全部 `NOT_RUN`。若前置全 PASS 但既有 seam runtime 失敗，回 `NO_GO_EXISTING_SEAM_RUNTIME_FAILURE`。

成功條件：只有實際單日 create→capture→verify 全鏈通過，receipt／manifest／ranking hash 與 model、config、universe、features/calendar、top-N、producer source、run identity 全部綁定，才可回 `GO_FORWARD_CAPTURE_SESSION_VERIFIED`。成功只證明 isolated session seam，不建立 canonical authority、不寫 configured ranking root、不准入歷史 corpus、Entry-Regime capacity、R14、preregistration或 production。

交付：只新增 `docs/evidence/BC-CP2-R13-MINIMAL-FORWARD-CAPTURE-SESSION-EVIDENCE/01-session-decision.md`。記錄逐 gate PASS／FAIL／NOT_RUN、完整命令、exit、session clock/date authority、輸入／輸出 hashes、bundle verification、temp size與保留／清理狀態、why_not_less／why_not_more／do_not_absorb、唯一 frontier。Temporary output 上限 `256 MiB`，超限立即停止，不得刪除 repo 或 configured artifacts。

邊界：不得 network fetch、修改 code/tests/config/workflow/data/ranking/manifest/receipt/registry/runner/queue/scheduler/backtest或 production；除隔離 temp session 與指定 evidence 外不得寫檔；不得讀 outcome／sealed data、跑 replay／benchmark／training；不得 merge、push、改 Issue、deploy或 external write。changed-files allowlist 僅指定 evidence，`git diff --check` 通過、worktree clean、獨立 fixed-SHA Review 無 P0/P1。

現在狀態：`ADMITTED / SINGLE_ISOLATED_SESSION / FRESHNESS_FAIL_CLOSED / NO_DOWNSTREAM_ADMISSION`

# NEW-TOP10 Daily Publish Incident — 2026-08-27

狀態：`OPEN / P0 OPERATIONAL RECOVERY / PREEMPTS RESEARCH A0`

Issue：`#9 INCIDENT-NEW-TOP10-DAILY-PUBLISH-RECOVERY-AND-HARDENING-V1`

## Current conclusion

目前無法從 GitHub 取得 Mac 本機 launchd、logs 與未提交 artifacts，因此尚未宣稱單一已證實 root cause。Repo inspection 已確認多個足以造成「daily 有跑、報牌沒送」或「launchd 看似成功、實際沒有 live send」的結構性風險。

## Confirmed repository risks

1. `run_daily.sh` 有 `.venv → uv` runtime fallback，但 `run_daily_publish.sh` 只有 `.venv → python3`。當 `.venv` 不存在或損壞時，daily 可能靠 uv 成功，publish gate / sender 卻因 system Python 缺 PyYAML 或依賴而失敗。
2. `config/automation.yaml` 把 Node、OpenClaw/Clawd checkout 與 Discord channel IDs 寫死在 tracked config；`clawd_cli_entry` 指向 `/Users/mattkuo/new clawd/dist/index.js`，未驗證這是否仍是目前 `New-clawd` checkout 與 canonical CLI entry。
3. 目前 `New-clawd` package 的正式 bin 是 `openclaw.mjs`；它再載入 `dist/entry.(m)js`。Top10 sender 沒有 CLI version / entry compatibility / gateway health smoke，只檢查檔案是否存在。
4. daily 的 publish-critical artifact（daily report / Clawd payload）在整條 main pipeline 全部完成後才產生。market context、recommendation performance、decision quality、performance review 等非 ranking 核心步驟中，部分失敗會阻止報表與推播，即使 ranking 已成功。
5. daily freshness 允許 `max_data_lag_days: 7`，但 sender 對 live send 要求 message date 等於本地今日。trigger date、market session date、ranking date、publish date 尚未形成一級契約；資料尚未更新、平日休市或 market date 落後時可能形成 daily OK / stale-send blocked 的矛盾。
6. `run_daily_publish.sh` 對「live send not allowed」路徑可記錄 skipped 並以 0 結束；在應該出牌的交易日，這可能讓 launchd 看起來成功但使用者沒有收到報牌。
7. scheduler ownership verifier只檢查 `com.new-top10.daily` 與 cron，不檢查歷史 launchd labels。先前使用過的 `com.clawd.newtop10`、`com.clawd.discord-notify`、`com.clawd.daily-brief` 可能殘留、重複或已失效但未被現有 verifier 發現。
8. Top10 報牌與 ops failure report 共用同一個 OpenClaw transport；transport 本身壞掉時，告警也一起消失。
9. repo plist / docs / config 以 17:30 為 current canonical schedule，但 `run_daily.sh` header 仍寫 22:00，歷史 repair 需求曾使用 09:00，存在 scheduler/product contract drift。

## Recovery order

1. 只讀盤點本機 launchd owner、installed plist、last exit、logs、latest artifacts 與 OpenClaw runtime。
2. 分類 failure boundary：scheduler / daily core / final artifacts / publish gate / OpenClaw send。
3. 修復 active runtime path與 CLI compatibility，先做 dry-run，再做一次受控 live send。
4. 清除或停用 legacy scheduler owners，重新 bootstrap唯一 `com.new-top10.daily`。
5. 再進行 critical-path、date contract、health watchdog 等長期 hardening。

## Stop rule

在本機 evidence 尚未證明 root cause 前，不直接改 ranking、backtest、模型、Discord target 或 production data。不得用猜測路徑做 live send。

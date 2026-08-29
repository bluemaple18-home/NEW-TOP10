# GPT Sol Max Read-only Architecture Review Prompt

## Review mode

你是 GPT Sol Max reviewer。請做 critical、read-only architecture review。這個 bundle 是固定 SHA 的證據包；請只閱讀 bundle 內檔案並回覆判斷，不得修改檔案、不得執行 production、不得清 marker、不得 send、不得操作 launchd、不得做 Git commit/push/merge/deploy，也不得用真正 canary 來補證據。

請把回答建立在可引用的 bundle path 與 SHA 上。若證據不足，請明確寫 `UNKNOWN` 或 `BLOCKED`，不要用推測補成 PASS。

## Root question

Issue #10 daily swap stop-loss candidate 已進 main，但 `daily.launch_verified=false`，S1 只有 non-production representative validation；S2 audit 判定 generic seven-step production canary path 與此專案正式 daily entrypoint 不相容。請判定目前是否可進入 production recovery 的下一步，以及最小安全路徑。

## Fixed context to review

- Daily candidate behavior：2GiB `SOFT_SWAP_WARNING` warning；4GiB `SWAP_EMERGENCY_HARD_STOP` hard stop；RSS hard cap 4GiB；daily sample interval 60s；legacy jobs 不變。
- Current production policy state：`daily.launch_verified=false`。
- S1 fresh rerun：cold/warm 兩輪 exit0/status OK；cold 有 2 個 live samples、peak RSS 約 1.816GB；warm 約 56-58 秒且只有 1 個 live sample；兩輪都沒有 exercise 2GiB warning path。
- S2 audit：official production chain 是 `com.new-top10.daily.plist → scripts/run_with_storage_guard.sh daily → scripts/run_daily_publish.sh → scripts/run_daily.sh → python -m scripts.run_automation daily`；專案正式 daily chain 沒有 generic canary 七步的 transaction/tag/push entrypoint/correlation artifacts。
- Existing global production canary readiness gate 要求 create→run→select→publish→transaction→tag→push 全鏈路；不能用任意文字 artifact 填 PASS。

## Required questions

請逐題回答：

1. S2 對 generic seven-step canary 的拒絕是否正確？若正確，這是 `BLOCK_SCOPE_EXPANSION`、`CANARY_PATH_NOT_APPLICABLE`，還是應要求建立新 subsystem？
2. 60s sampling 與 warm run 只有單一 live sample，是否阻擋 `launch_verified=true`？若阻擋，缺的是哪種 evidence？
3. 兩輪未 exercise 2GiB warning path，是否可以只靠 deterministic tests 接受 warning/cadence contract？哪些部分可接受，哪些部分仍不可宣稱 live-verified？
4. 最小 production recovery sequence 應該是什麼？請列出每步的 entrypoint、send 狀態、acceptance artifact、stop condition，以及 atomic rollback。
5. 是否應改成 10–15s sampling 或 boundary sampling？請明確寫 `why_not_less`、`why_not_more`、`do_not_absorb`。
6. 最終請給 `PRE_PRODUCTION_GO` 或 `PRE_PRODUCTION_NO_GO`，並寫下一張 exact card 的建議標題、scope、allowed files/actions、forbidden actions、acceptance。

## Output format

請用繁體中文回覆，格式如下：

```text
verdict: PRE_PRODUCTION_GO | PRE_PRODUCTION_NO_GO

findings:
- [P0/P1/P2/P3] <title>
  evidence: <bundle path + short sha>
  impact: <why it matters>
  required_action: <minimal next action>

answers:
1. ...
2. ...
3. ...
4. ...
5. ...
6. ...

minimum_next_card:
- title:
- scope:
- allowed_files_or_actions:
- forbidden_actions:
- acceptance:
- rollback:
```


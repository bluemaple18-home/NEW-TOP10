# 2026-06-08 研究收尾總結

日期：2026-06-08
狀態：MAINLINE_SUMMARY_READY

## 結論

目前研究線已可收斂成三類：

1. 可進 review 決策，但不可直接升正式。
2. 只能繼續 daily shadow monitor。
3. 已封存為 research-only / blocked，不再佔主線。

目前沒有任何分支可以直接改 production model、production ranking、`risk_adjusted_score` 或正式推播。

## 主線狀態

| 主線 | 目前狀態 | 結論 | 下一步 |
| --- | --- | --- | --- |
| `gross55_exposure_shadow` | ACTIVE_DAILY_MONITOR | 長區間回測支持保守曝險 profile review，但少賺、低回撤，不是選股變強 | 進 review 決策；forward monitor 作近期確認 |
| `capital_entry_quality_shadow` | ACTIVE_DAILY_MONITOR | `non_worsening` 長短期較平衡，可作入場品質 shadow | 進 review 決策；不可直接改入場資格 |
| `candidate_trail10_shadow` | ACTIVE_DAILY_MONITOR | 新 candidate ranking 加上 trail10 出場規則，長區間驗證較強，但仍需每日 shadow 累積近期穩定性 | 每天產 candidate Top10 / Top7 trail10 影子計畫；不可直接改正式推播 |
| `chip_flow` | BLOCKED / RESEARCH_OVERLAY_ONLY | 外資、投信、融資不適合當正式大盤或出場主訊號 | 封存 blocked evidence；轉測 price/rank/volume/overheat reversal |
| `BIG_BULL family_only` | RESTRICTED_SHADOW_ONLY | 不走模型升版，只能 ranking-only shadow | 暫不再主線鑽，除非有新證據 |
| `HIGH_CHOPPY` | MONITOR_ONLY | 可作分層診斷，不作正式模型或 overlay | 保留 stratified evaluation |
| `liquidity quality` | RESEARCH_ONLY | 流動性要拆 gate + percentile，不可硬改門檻 | 暫不進 production score |
| `capital realism / exit rules` | RESEARCH_ONLY | 固定 40D 仍是目前基準；simple stop / trailing 尚未可用 | 下一輪測 exit-signal 主線 |
| `warning-only message` | DRY_RUN_READY | 可產生 warning-only 文案，但不是個人持倉提醒 | Phase 1 先不分頻、不正式送 |

## 最新可引用證據

| Artifact | 用途 | 結論 |
| --- | --- | --- |
| `artifacts/model_experiments/daily_shadow_status_2026-06-09.json` | 每日 shadow 分支總狀態 | 3 條 active monitor、3 條 research monitor；production ready = 0 |
| `artifacts/model_experiments/candidate_trail10_daily_shadow_monitor_2026-06-09.json` | candidate ranking + trail10 每日影子觀察 | 6/9 smoke OK；candidate / production Top10 overlap = 3；只可 daily shadow |
| `artifacts/model_experiments/shadow_historical_evidence_2026-06-08.json` | 歷史回測證據 | 不用只等；599 個 ranking day 可支持 gross55 / capital entry 進 review |
| `artifacts/feature_experiment_gate_2026-06-08.json` | feature gate | 8 候選、3 ready for shadow、5 blocked；production promotion=false |
| `artifacts/model_experiments/chip_flow_readiness_report_2026-06-08.json` | chip_flow readiness | NOT_READY_FOR_PRODUCTION；research overlay only |
| `artifacts/model_experiments/chip_warning_replay_aggregate_2026-06-08.json` | 籌碼 warning aggregate | PARTIAL_MONITOR_ONLY，不可正式 warning |
| `artifacts/model_experiments/chip_composite_warning_report_top10_20d_2026-06-08.json` | chip + price/rank composite | COMPOSITE_RISK 只有 3 筆，不穩 |
| `artifacts/model_experiments/gross55_daily_shadow_monitor_batch_2026-06-08.json` | gross55 forward monitor | 12 天樣本，仍未達 review sample policy |
| `artifacts/model_experiments/capital_entry_quality_daily_shadow_monitor_batch_2026-06-08.json` | 入場品質 forward monitor | 9 天樣本，仍未達 review sample policy |

## 不要再混線的規則

- `chip_flow` 不再往正式 warning channel 推。
- 外資 / 投信 / 融資不可單獨當大盤方向判斷。
- 融資增加不可單獨解讀成危險。
- warning-only 不是個人持倉賣出通知。
- `MONITOR_ONLY` 不可當 promotion evidence。
- research replay 通過不等於可改 production。
- dirty / untracked 檔案很多，git 只能分批 stage，不可 `git add .`。

## 下一步工作

### A. 先做 review 決策

把 `gross55_exposure_shadow` 和 `capital_entry_quality_shadow` 拿出來做 review：

- 是否允許成為「保守 profile」或「入場品質提示」。
- 若允許，仍需定義 product surface，不直接改 production ranking。

### B. 啟動 EXIT-SIGNAL-01

下一輪研究主線：

- 價格失速。
- 排名退潮。
- 量能退潮。
- 過熱後反轉。

參考卡：

- `docs/tasks/2026-06-08_EXIT-SIGNAL-01_price_rank_volume_overheat_reversal.md`

### C. Git 收斂建議

建議分兩個 commit，不要混在一起：

1. `research closure/status summary`
   - 本總結檔。
   - daily shadow status / historical evidence / chip readiness 相關主線整合。

2. `research tooling backlog`
   - 大量 untracked research scripts / verify scripts / task cards。
   - 這包要先 review 檔案清單，避免把過時實驗或 unrelated dirty 一起收進主線。

## 驗證紀錄

最近已跑過：

```text
verify_feature_experiment_gate.py: OK
verify_chip_flow_readiness_report.py: OK
verify_daily_shadow_status_report.py: OK
verify_shadow_historical_evidence_report.py: OK
verify_model_foundation.py: OK
git diff --check: OK
```

## 目前判定

可以收尾。

但不建議現在直接做大包 commit。應先 stage 一個小範圍 closure commit，剩下研究腳本再分批 review。

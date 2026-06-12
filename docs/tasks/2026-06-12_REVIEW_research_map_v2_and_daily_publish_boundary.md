# REVIEW｜Research Map V2 與 Daily Publish 邊界檢查

## 任務ID

`REVIEW-20260612-research-map-v2-daily-publish-boundary`

## 卡片類型｜派工對象

Code Review / Boundary Review｜Codex

## Root Question

目前工作區同時包含：

- daily publish 事故修復與 workflow guard
- research map v2 世界觀升級
- 5913 review / liquidity strict replay 相關研究檔

請 review 這些變更能否分包收尾，並確認沒有把研究地圖、推播修復、模型或 production ranking 混在一起。

## 請讀

- `docs/tasks/2026-06-12_RESEARCH-MAP-V2-01_worldview_schema_upgrade.md`
- `docs/operations/incidents/2026-06-12_daily_publish_missed_push.md`
- `scripts/research_map_contract.py`
- `scripts/build_research_campaign_progress.py`
- `scripts/build_research_fog_map.py`
- `scripts/verify_research_fog_map.py`
- `scripts/verify_research_map_v2_schema.py`
- `scripts/verify_daily_publish_workflow.py`
- `docs/AUTOMATION.md`
- `scripts/run_daily.sh`
- `scripts/run_daily_publish.sh`

## 任務目的

確認是否可以把目前變更拆成安全 commit，至少分成：

1. Daily publish incident / workflow guard
2. Research map v2 worldview schema
3. Research evidence / liquidity replay follow-up

## Review 重點

- `research map v2` 是否只是擴充研究座標，沒有改 production ranking / model / Clawd live push。
- `5913 -> 662256` 是否呈現為 full universe early stage，而不是假裝完成。
- v1 5913 是否 migrate 到 v2 default coordinates：
  - `regime_gate=ALL`
  - `risk_guard=NONE`
  - `entry_filter=TOPIC_DEFAULT`
- `LIQUIDITY-REPLAY-02` 的 144 顆是否掛在 v2 active queue，不是另一張地圖。
- daily publish 修復是否只修 workflow / verifier / 文件，不影響研究 map。
- `run_daily.sh` 的 shadow / research 旁路是否 default-off，失敗不得阻斷 daily 主流程。
- 是否有任何 production artifact、model file、live send path 被意外納入。

## 已知狀態

```text
base universe: 5913 / 5913
expanded universe: 5913 / 662256
expanded progress: 0.8929%
active queue: 144
active stage: LIQUIDITY-REPLAY-02
production impact claimed: none
```

## 已跑驗證

```text
verify_research_fog_map.py --date 2026-06-12: OK
verify_research_map_v2_schema.py: OK
verify_research_map_run_history_backfill.py: OK
verify_daily_publish_workflow.py --date 2026-06-11 --require-send --check-launchd: OK
git diff --check: OK
```

## 請輸出

- Findings，依嚴重度排序。
- 是否可分包 commit。
- 建議 commit 分組。
- 還需要補的 verifier。
- 是否需要先重跑任何 production dry-run。

## 禁止事項

- 不要 commit。
- 不要 push。
- 不要 live send。
- 不要改模型。
- 不要改 production ranking。
- 不要把 review 結論寫成 promotion approval。


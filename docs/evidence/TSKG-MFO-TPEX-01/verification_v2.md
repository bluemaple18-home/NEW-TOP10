# TSKG-MFO-TPEX-01 verification v2

## Decision

- candidate identity：本文件與 implementation 所在 commit
- access date：`2026-07-22`（Asia/Taipei）
- supersedes：candidate `5a436b1` 的 `KEEP_BLOCKED`
- source decision：`GO_CURRENT_DAY_OPENAPI_ONLY`
- history／website crawler／paid S35／raw public redistribution：`BLOCKED`

原 decision 的關鍵負面證據「沒有對應 government-open-data dataset」已被官方 dataset `11856` 推翻。本版沒有把 website endpoint existence 當成 permission，而是將 OGL dataset identity、官方 Swagger operation 與實際 response 三者綁定。

## Implementation

- `config/tskg_source_policy_governed_v1.json`：唯一正式 PUBLIC policy；method/path/media、internal retention、redistribution boundary、review/expiry 固定。
- `SourcePolicyRegistry.from_mapping()`／一般 `from_file()`：仍拒絕 PUBLIC APPROVED。
- `from_governed_file()`：只接受 repo 內 pinned policy path、registry version 與 canonical checksum；即使匯入真正 private token，任意 runtime mapping 也無法改 source/path 後提權。
- `app/tskg/tpex_institutional.py`：preflight 後單次 GET、20 欄 closed schema、ROC date、buy/sell/net arithmetic、unique stock、TPEx publisher 與證期局 data-providing organization、canonical SHA-256、atomic write。
- `scripts/fetch_tskg_tpex_institutional.py`：current-day CLI；`--expect-date` 為 required，日期不符 fail closed，不提供歷史網站 fallback。

## Live bounded receipt

```text
trade_date=2026-07-22
row_count=906
canonical_sha256=b913b2b019fd70e50c0f4e709b9c5514279368fd874684c539b4872017fc6005
foreign_ex_dealer_net_shares=-89434575
investment_trust_net_shares=-2417243
dealer_total_net_shares=24687606
all_institutional_net_shares=-67164212
```

真實 snapshot 只寫入本機 temporary path，未進 Git。只呼叫一次官方 OGL endpoint，未做 rate/load test、未接受新條款、未購買、未登入。

## Verification receipts

- TPEx/source/promotion focused：`25 passed`。
- TPEx + source + MFO + Theme + Graph + Radar + industry promotion：Repair 後 `70 passed`。
- repo full suite：`462 passed, 1 baseline failure`。唯一失敗是 fresh worktree 缺少 Git 忽略的歷史 research artifacts／`features.parquet`，使既有 `research_component_ledger` 的 `evidence_exists` 檢查失敗；同一失敗已在既有主線整合證據記為固定 baseline，且本 candidate 未修改 ledger builder／verifier／registry。
- `scripts/verify_industry_promotion_decision.py`：先驗 committed replay SHA／production ranking manifest，再重算 `NO_GO_INSUFFICIENT_PRODUCTION_HISTORY`。
- py_compile：PASS。
- `git diff --check`：PASS。
- production `RankingPolicy`／`risk_adjusted_score`／model weights：未修改。

## Independent Review repair

固定 SHA `4f27dee` 初審為 `REVIEW_NO_GO`：proxy baseline、runtime token bypass、unbound promotion artifact 與 OGL attribution 各一項 P1。Repair 已全部處理：promotion 改用 40 份真實 production ranking artifacts（26 個成熟日期、低於 60 日 floor）；replay JSON 進 Git 並由 SHA-bound verifier 重算；governed registry checksum pin；資料提供機關改為金融監督管理委員會證券期貨局。P2 的 cost 宣稱改為兩臂皆不套交易成本，stale date 改為 required assertion。

## Official sources

- https://data.nat.gov.tw/dataset/11856
- https://www.tpex.org.tw/openapi/swagger.json
- https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading
- https://data.gov.tw/license
- https://www.tpex.org.tw/zh-tw/gtsm_disclaimer.html

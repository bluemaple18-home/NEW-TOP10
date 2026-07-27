---
id: FOG-RUNTIME-TIME-AUTHORITY-01
status: RUNNING
type: architecture
chain_id: FOG-RUNTIME-TIME-AUTHORITY-01
successor_of:
  - FOG-CLOSED-REGIME-AUTONOMY-01
ownership: architecture_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 需重建跨 shell、Python receipt、LaunchAgent 與 verifier 的市場日／UTC 時間權威，屬跨模組核心契約且回退成本高；不得由 Repair-3 繼續局部補丁。
source_sha: 403f6c5
evidence_path: docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01/
---

# FOG-RUNTIME-TIME-AUTHORITY-01：市場日與 timestamp 權威契約

## Root question

Fog runtime 應如何以單一、可重算、跨 shell/Python 一致的時間權威，同時表達台股
市場營業日、UTC receipt timestamp、freshness window 與 LaunchAgent 執行時間，
避免合法跨 UTC 日界線的 receipt 被誤拒？

## Successor boundary

前一條 strict chain `FOG-CLOSED-REGIME-AUTONOMY-01` 已於 Repair-2 達到
`BLOCKED / REVIEW_REPAIR_LIMIT`。本卡是新的 architecture contract，不是
Repair-3：

- 不修改前一 candidate `acd835df3a4fe40a149333dca0b55e62cc8eded9`。
- 不關閉或重命名 `RRV-P1-02`。
- 只建立可獨立 Review 的時間契約、決策紀錄、測試矩陣與 migration slice。
- architecture acceptance 後，主線另建新的 implementation chain；不得回寫舊
  Repair generation。

前一 Review evidence：
`docs/evidence/REVIEW-FOG-CLOSED-REGIME-AUTONOMY-01/review.md`。

## Required decisions

### A. Canonical time concepts

至少明確區分並定義：

- `market_timezone`
- `market_run_date`
- `generated_at_utc`
- `verification_time_utc`
- `receipt_age_seconds`
- scheduler host timezone
- regime-history source date
- daily artifact source date

每個欄位必須指定 authority、格式、轉換順序與禁止的隱式假設。

### B. Market-day authority

- 判定台股市場日是否固定使用 IANA `Asia/Taipei`。
- 說明 shell 不得以未綁時區的 `date +%F` 自行產生 contract identity。
- 說明 UTC timestamp 如何轉成 market timezone 後與 `market_run_date` 比較。
- 明確處理台北 00:00–07:59、UTC 跨日、host timezone drift、timezone-naive
  timestamp、future/stale receipt。
- 若 contract 未來支援其他市場，定義 timezone 欄位如何進 schema/hash，而不是
  依主機 locale。

### C. Freshness policy

- freshness 必須以 absolute UTC age 計算，market-day identity 則以 canonical
  market timezone 計算；兩者不得混為同一 gate。
- 定義可接受 age window、clock skew、future tolerance與 lifecycle boundary。
- policy 參數必須來自 versioned authority，不得由 receipt或任意 env覆寫。

### D. Runtime wiring contract

定義 LaunchAgent → Fog worker → daily quota → runtime receipt → verifier 的欄位
傳遞與重算位置，包含：

- 唯一產生 `market_run_date` 的 authority。
- shell 與 Python 如何取得相同 timezone contract。
- receipt 必須保存哪些原始／正規化欄位與 contract hash。
- verifier 如何在不信任 receipt 自報結果的前提下重算。

## Required deterministic matrix

Architecture evidence 必須列出 expected outcome：

| Case | Market time | UTC time | Expected |
|---|---|---|---|
| 台北跨 UTC 日界 | 00:30 +08 | 前一日 16:30Z | accept when fresh |
| 台北正常日間 | 09:00 +08 | 01:00Z | accept when fresh |
| stale receipt | same market day | age over policy | reject |
| future receipt | same market day | beyond skew | reject |
| naive timestamp | n/a | no timezone | reject |
| wrong market date | computed date differs | fresh | reject |
| host timezone drift | host not Asia/Taipei | valid authority | deterministic |
| DST-capable fixture | explicit IANA zone | transition edge | deterministic |

另需定義 property/invariant tests，至少涵蓋 UTC↔market timezone round-trip、跨午夜與
clock-skew boundaries。

## Deliverables

- `docs/architecture/fog_runtime_time_authority_v1.md`
- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01/architecture.md`
- 本卡狀態／receipt 更新
- 後續 implementation slice 建議，須列 changed-file allowlist、red tests、
  migration ordering、rollback與 live acceptance 邊界

## Allowlist

- `docs/architecture/fog_runtime_time_authority_v1.md`
- `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01/**`
- 本卡

## Forbidden scope

- 不修改 `scripts/**`、`tests/**`、config、LaunchAgent、model、ranking或 production
  artifacts。
- 不操作 live retry state、queue、baseline、LaunchAgent或 scheduler。
- 不建立 Repair-3、不修改舊 Repair candidate、不 merge/push/deploy/acceptance。
- 不以「直接改成 UTC date」或「放寬 8 小時」作為未經契約證明的捷徑。

## Verification

```bash
cd <repo-root>
test -f docs/architecture/fog_runtime_time_authority_v1.md
test -f docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01/architecture.md
rg -n \
  'market_timezone|market_run_date|generated_at_utc|verification_time_utc|receipt_age_seconds' \
  docs/architecture/fog_runtime_time_authority_v1.md
git diff --check
```

Architecture evidence 另需逐項映射 Review trigger、8-case matrix、invariants、
implementation slices、migration、rollback與 production boundary。

## Delivery and review

- Executor 只交付 `DELIVERED_ARCHITECTURE_CANDIDATE` 與完整 SHA。
- 不得宣稱舊 chain 已修復、runtime 已恢復或可整合。
- 本卡為 strict architecture，candidate 必須進獨立 Review；只有 architecture
  `GO` 後主線才可建立 successor implementation card。
- 同一 blocker 失敗三次立即停手，不得第 4 次盲重試。

## Initial workflow receipt

- Card commit：`cfaabf914f752b63a8efaf15ca40a5984221c2e1`
- Provisioning source kind：`commit`
- Provisioning source SHA：`cfaabf914f752b63a8efaf15ca40a5984221c2e1`
- Source branch：`main`
- Source clean：是
- Git metadata：可用
- `index.lock`：不存在
- unrelated dirty paths：`[]`
- Client receipt：
  `client-new-thread:db26489f-be59-4ff5-a20e-61f85ec0e602`
- Formal task：`019fa43d-3544-7662-be9c-3b258eee681c`
- Task title：`建立市場時間權威契約`
- Task status：`active / inProgress`
- Worktree／cwd（local-only）：
  `/Users/mattkuo/.codex/worktrees/d6ce/TOP10new`
- Main cwd（local-only）：`/Users/mattkuo/TOP10new`
- Worktree exists／registered：是
- Initial worktree HEAD：
  `cfaabf914f752b63a8efaf15ca40a5984221c2e1`
- Initial branch：`detached`
- Capability preflight：
  `worktree_registered=true`、`python_tests=needs_prepare`、
  `codegraph=degraded:fallback_rg`
- Current card：`FOG-RUNTIME-TIME-AUTHORITY-01`
- Mainline dispatcher：
  `019f82c1-b7d0-7eb3-9371-7a95ebfbd7ce`
- Previous blocked chain Reviewer：
  `019fa409-ead7-71d3-8115-5ac50857613a`
- Cross-thread binding：
  current task/worktree/title 與 previous Reviewer 均不同，`PASS`
- Workflow：
  `CARD_DRAFTED → QUEUED → THREAD_CREATED → RUNNING`
- Gate 1 card contract：`PASS`
- Gate 2 visible thread：`PASS`
- Gate 3 candidate delivery：`PENDING`
- Gate 4 independent review：`PENDING`
- Gate 5 mainline acceptance：`PENDING`

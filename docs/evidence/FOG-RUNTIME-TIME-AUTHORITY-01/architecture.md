---
card_id: FOG-RUNTIME-TIME-AUTHORITY-01
status: DELIVERED_ARCHITECTURE_CANDIDATE
evidence_kind: strict_architecture
candidate_sha_binding: external_final_receipt
---

# FOG-RUNTIME-TIME-AUTHORITY-01 architecture evidence

## 1. Preflight receipt

```text
worktree: <isolated-worktree>
worktree_registered: PASS
independent_from_main_worktree: PASS
starting_head: cfaabf914f752b63a8efaf15ca40a5984221c2e1
starting_branch: detached
clean_before_edits: PASS
card_source_sha: 403f6c5
actual_candidate_parent: cfaabf914f752b63a8efaf15ca40a5984221c2e1
source_sha_not_treated_as_head: PASS
workspace_write: PASS
git_commit_capability: PASS
network_required: NO
live_runtime_required: NO
codegraph: degraded:fallback_rg
unrelated_dirty_paths: []
```

CodeGraph 未在 isolated worktree 初始化。初始化會新增 allowlist 外的 index
state，因此沒有寫入；現況蒐證改用唯讀、限範圍 `rg`／`sed`。

## 2. Fixed evidence與事實

| Evidence | Observed fact | Architecture consequence |
|---|---|---|
| 本卡 | freshness 必須以 absolute UTC age，market-day identity 必須以 canonical timezone 計算 | 拆成兩個獨立 gate，不互相替代 |
| `docs/evidence/REVIEW-FOG-CLOSED-REGIME-AUTONOMY-01/review.md` | predecessor candidate 在台北 00:00–07:59 把 fresh receipt 誤拒；`RRV-P1-02` OPEN/P1 | 不能建立 Repair-3；另建 v1 time authority |
| predecessor candidate `acd835d…:scripts/verify_daily_research_quota.py` | `generated.date() == expected_date` 直接比較 UTC date 與 local run date；max age 為 24 小時 | 改為 IANA projection；freshness window versioned 為 900 秒 |
| predecessor candidate `acd835d…:scripts/run_fog_research_worker.sh` | `RUN_DATE` fallback 到未綁時區 `date +%F` | shell 移除 date authority，只傳 immutable Python context |
| predecessor candidate `acd835d…:scripts/run_daily_research_quota.sh` | daily shell 再次 fallback 到 `date +%F`，並用該 date 命名 artifacts | child 不重算；date、path與receipt共用同一 context |
| `scripts/com.new-top10.fog-research-worker.plist` | LaunchAgent 每 900 秒啟動 worker | v1 freshness max age 固定 900 秒；plist 不注入日期／timezone／policy |
| `config/automation.yaml` | repo 已宣告 `timezone: Asia/Taipei` | v1 canonical IANA zone 採 `Asia/Taipei`，但 Fog contract 需獨立 version/hash |
| `scripts/build_market_regime_history.py` | history 有 UTC `generated_at` 與 trade-date rows | generated timestamp 與 `source_trade_date` 分開；休市日不可硬等於 run date |

本 architecture 未執行 predecessor candidate、tests、LaunchAgent、queue、retry
state、model或 production artifacts。

## 3. Root question answer

單一可重算 contract 是
`docs/architecture/fog_runtime_time_authority_v1.md`：

- v1 production market timezone 固定為 IANA `Asia/Taipei`；
- `market_run_date` 只由 aware UTC instant 經 `ZoneInfo` 投影；
- `generated_at_utc`／`verification_time_utc` 僅用來計算 signed absolute age；
- versioned policy與 canonical JSON hash 是唯一 policy authority；
- LaunchAgent 不供應 time identity；worker 建 context，daily quota只傳遞，
  producer綁定，verifier獨立重算；
- market midnight 是 hard lifecycle boundary；
- receipt v3 綁定 raw UTC instants、market projections、source artifacts、
  source dates與 contract hash。

`market_run_date` 是市場時區 civil-day identity，不是 TWSE 開市日斷言。
regime-history 的 `source_trade_date` 另行表達最近適用交易日；未來若要 gate
`is_market_session_day`，需另有 versioned TWSE calendar，不可從 timezone猜測。

## 4. Review trigger mapping

| Trigger / gap | Contract locator | Resolution |
|---|---|---|
| 合法台北跨 UTC 日界 fresh receipt 被拒 | architecture §1、§5、§8 case 1 | UTC instant先投影 `Asia/Taipei` 再比較 date；age仍在 UTC 計算 |
| 同 UTC 日期控制組 | §8 case 2 | 保留 accept，證明不是只特判跨日 |
| stale receipt | §6、§8 case 3 | `age > 900` fail closed |
| future receipt | §6、§8 case 4 | 只容許 5 秒負 age；beyond skew拒絕 |
| timezone-naive receipt | §4、§8 case 5 | strict RFC3339 UTC `Z` parse，禁止 host zone補值 |
| wrong market date | §5、§7.5、§8 case 6 | verifier由 raw UTC instant重算，拒絕 receipt claim |
| host timezone drift | §3.2、§7.1、§8 case 7 | host timezone僅 diagnostic，不進 identity/hash |
| DST ambiguous local time | §3.2、§8 case 8、§9 | 只做 UTC→IANA projection，不解析 naive local time |
| shell與Python各算一套日期 | §5、§7 | 唯一 pure function；shell只傳 immutable context |
| receipt 自報 policy | §3、§6、§7.5 | repo versioned authority + expected hash；receipt只供 observed value |
| 跨市場午夜長批次 | §5 | hard rollover，舊日期 receipt不得寫入 |
| validation 未覆蓋 local/UTC 跨日 | §8、§9、§10 I1/I3 | 固定 8-case matrix、boundary與properties作為 red tests |
| regime source date 與 daily date 混用 | §4、§7.4、§9 invariant 11 | source dates各自從 canonical artifact重算 |

原 finding `RRV-P1-02` 仍由 predecessor Review 持有；本卡沒有關閉或改名。

## 5. Required deterministic matrix

| Case | Market time | UTC time | Expected |
|---|---|---|---|
| 台北跨 UTC 日界 | `2026-07-28 00:30:00 +08` | generated `2026-07-27T16:30:00Z`；verify `16:31:00Z` | `ACCEPT` when claimed market date=`2026-07-28`；age=`60` |
| 台北正常日間 | `2026-07-28 09:00:00 +08` | generated `2026-07-28T01:00:00Z`；verify `01:01:00Z` | `ACCEPT`；age=`60` |
| stale receipt | same market day | generated `01:00:00Z`；verify `01:15:01Z` | `REJECT / STALE_RECEIPT`；age=`901` |
| future receipt | same market day | generated `01:00:06Z`；verify `01:00:00Z` | `REJECT / FUTURE_RECEIPT`；age=`-6` |
| naive timestamp | n/a | `2026-07-28T01:00:00` | `REJECT / NAIVE_TIMESTAMP` |
| wrong market date | computed=`2026-07-28` | fresh generated `2026-07-28T01:00:00Z` | receipt claim `2026-07-27` → `REJECT / MARKET_DATE_MISMATCH` |
| host timezone drift | host=`America/Los_Angeles`；authority=`Asia/Taipei` | 與跨 UTC case相同 | `ACCEPT`；semantic result不受 host zone影響 |
| DST-capable fixture | `America/New_York` 的兩個 `2026-11-01 01:30` folds | `05:30:00Z`與`06:30:00Z` | `DETERMINISTIC` UTC→zone→UTC round-trip；不解析 ambiguous naive local |

Additional exact boundaries：

- `age=-5` accept；`-5.001` reject；
- `age=900` accept；`900.001` reject；
- 台北午夜前後相鄰 instants 必須得到不同 `market_run_date`。

## 6. Invariants coverage

Architecture §9 固定 12 項 property/invariant tests：

1. UTC↔market timezone round-trip；
2. market projection identity；
3. freshness 與 timezone separation；
4. host timezone／locale invariance；
5. naive timestamp rejection；
6. market-midnight lifecycle；
7. age monotonicity；
8. future skew不 clamp；
9. canonical policy hash determinism；
10. receipt non-authority；
11. regime/daily source lineage；
12. DST fold safety。

所有 property tests 必須 fixed clock／seed，不讀 real current time 或 host timezone。

## 7. Implementation slices mapping

| Slice | Changed-file allowlist | Required red tests | Runtime boundary |
|---|---|---|---|
| I1 pure authority | `config/fog_runtime_time_authority_v1.json`；`scripts/fog_runtime_time_authority.py`；`tests/test_fog_runtime_time_authority.py` | 8-case matrix、12 invariants、hash/RFC3339/boundaries | 不接 runtime |
| I2 receipt v3 | `scripts/verify_closed_regime_runtime.py`；authority module；`tests/test_fog_closed_regime_runtime.py` | v2≠v3、rollover、hash/unknown-field/source-date/path hostile cases | fixture producer only |
| I3 verifier | `scripts/verify_daily_research_quota.py`；authority module；`tests/test_daily_research_quota_verifier.py` | predecessor regression、trusted clock、stale/future/naive/wrong-date/host drift | fixture consumer only |
| I4 wiring | worker shell、daily shell、Fog plist、authority module、retry-circuit test、新 wiring shell test | 三種 host TZ、無 `date +%F` authority、legacy env mismatch、rollover、plist policy isolation | 不 kickstart LaunchAgent |
| I5 migration | implementation card、`docs/AUTOMATION.md`、該卡 evidence；installer僅在卡片明列時納入 | v2 inventory、installed path/SHA、三輪 receipts、台北凌晨 bounded case、protected hashes | Review GO 後才可 live |

詳細逐檔 allowlist、red tests與 exits 見 architecture §10。

## 8. Migration

Architecture §11 的固定 ordering：

1. I1 先鎖 policy/hash與 matrix；
2. I2/I3 一起完成 producer/verifier，v3-only trust；
3. I4 完成 static wiring，但不 reload scheduler；
4. independent Review 固定 SHA並跑完整 gates；
5. Review GO 後停止 Fog job，snapshot installed/live state；
6. v2 receipt只 archive，不補造 hash、不升級；
7. 安裝 reviewed plist/code，驗 path/SHA/hash後再 load；
8. bounded dry acceptance後才做三輪 scheduler acceptance。

不設 v2/v3 dual-trust window，避免缺 contract hash 的 v2 receipt 繼續授權。

## 9. Rollback

Architecture §12 將 rollback 固定為 safe stopped state：

- stop/unload Fog job；
- 保存失敗 v3 receipt、logs與 state hashes；
- 舊 code/plist僅供 forensic comparison；
- 不把 v2 receipt恢復到 active path；
- 不自動清 circuit或重放 queue；
- worker保持 disabled，另開修復卡；
- model/ranking/baseline/production artifact hashes不變。

因此 rollback 不會把已知有 local/UTC date regression 的 legacy path 誤稱為安全
production。

## 10. Production boundary

本 candidate：

- 沒有修改 `scripts/**`、`tests/**`、config、plist、model、ranking或 artifacts；
- 沒有操作 live retry state、queue、baseline、LaunchAgent或 scheduler；
- 沒有建立 Repair-3、修改 predecessor candidate、merge、push、deploy或
  acceptance；
- 只足以進 independent architecture Review；
- 不宣稱舊 chain修復、runtime恢復、production ready或可整合。

Architecture GO 後只能由主線建立 successor implementation card；本 candidate
本身不授權任何 runtime action。

## 11. Deliverable coverage

| Card deliverable | Evidence |
|---|---|
| Canonical time concepts | architecture §4 |
| Market-day authority | architecture §2–§5 |
| Freshness policy | architecture §6 |
| Runtime wiring | architecture §7 |
| Raw／normalized receipt fields + hash | architecture §7.4 |
| Verifier distrust/recompute | architecture §7.5 |
| 8-case matrix | architecture §8；本 evidence §5 |
| Properties/invariants | architecture §9；本 evidence §6 |
| Implementation slices + allowlists + red tests | architecture §10；本 evidence §7 |
| Migration ordering | architecture §11；本 evidence §8 |
| Rollback | architecture §12；本 evidence §9 |
| Live acceptance boundary | architecture §13；本 evidence §10 |

## 12. Verification receipts

| Gate | Exit | Result |
|---|---:|---|
| required architecture/evidence files | 0 | PASS |
| card-required canonical concepts `rg` | 0 | PASS：五個 required names均存在 |
| evidence section coverage | 0 | PASS：trigger、matrix、invariants、slices、migration、rollback、production boundary |
| 8-case matrix coverage | 0 | PASS：architecture與evidence各含八個 required cases |
| exact changed-file allowlist | 0 | PASS：architecture、evidence、card 共三檔 |
| local absolute path raw scan | 1 | PASS：無 macOS user-root 或 private-root 絕對路徑 pattern |
| `git diff --check` | 0 | PASS |
| staged exact allowlist／no unstaged paths | 0 | PASS：三個 allowlist paths，無 unstaged diff |
| `git diff --cached --check` | 0 | PASS |

Candidate SHA 無法在自身 commit 內自我引用，依卡片要求由 external final receipt
綁定。

## 13. Acceptance snapshot

```text
status: PARTIAL — DELIVERED_ARCHITECTURE_CANDIDATE only
evidence: architecture contract、trigger mapping、8-case matrix、invariants、slices、migration、rollback、production boundary
acceptance_mapping: sufficient for independent architecture Review
missing_evidence: independent Review GO、successor implementation candidate、runtime/live acceptance
remaining_risk: contract尚未實作；predecessor RRV-P1-02維持 OPEN/P1
next_step: independent Review fixed candidate SHA；GO後由主線建立 successor implementation card
```

# REVIEW-FOG-CLOSED-REGIME-AUTONOMY-01 Repair-2 Targeted Re-review

## Verdict

`NO_GO`

Lifecycle status：`BLOCKED / REVIEW_REPAIR_LIMIT`。

Repair-2 已關閉 `RRV-P1-01` 與 `RRV-P1-03`，但
`R2-REG-RECEIPT-IDENTITY-FRESHNESS` 在合法 LaunchAgent runtime path 出現直接
regression，因此 `RRV-P1-02` 尚未關閉。Strict chain 已達 Repair-2 上限；禁止
Repair-3。

## Fixed boundary and preflight

- replacement Reviewer identity：
  `019fa409-ead7-71d3-8115-5ac50857613a`
- re-review base：`394b90feae0a5c11a75a578ea4e721b44bb3893d`
- candidate：`acd835df3a4fe40a149333dca0b55e62cc8eded9`
- review starting HEAD：`02b8c90ebdb1b9461efb9111768620a9ee884d24`
- `base` 是 `candidate` ancestor：PASS
- `candidate` 是 starting HEAD ancestor：PASS
- `candidate..HEAD` 只有 Review v2 card commit：PASS
- starting worktree：clean
- unrelated dirty paths：`[]`
- capability preflight：worktree registered；Python tests `needs_prepare`；
  CodeGraph `degraded:fallback_rg`
- runtime：主 repo 受信任 Python `<main-repo>/.venv/bin/python`
- 未建立或下載 `.venv`
- 未修改 candidate、live state、queue、LaunchAgent 或 production artifacts；未
  merge、push、kickstart 或執行 acceptance

## Fixed findings ledger

| Finding | Regression ID | Disposition |
|---|---|---|
| `RRV-P1-01` | `R2-REG-BASELINE-AUTHORITY` | `CLOSED` |
| `RRV-P1-02` | `R2-REG-RECEIPT-IDENTITY-FRESHNESS` | `OPEN / P1` |
| `RRV-P1-03` | `R2-REG-SOURCE-LINEAGE` | `CLOSED` |

本次沒有新增 finding ID，也沒有用 P2/P3 或一般建議移動球門。

## Blocking finding

### RRV-P1-02：Freshness 將 UTC receipt date 與本地 run date 直接比較

位置：

- `scripts/run_fog_research_worker.sh:24`
- `scripts/run_daily_research_quota.sh:26`
- `scripts/verify_closed_regime_runtime.py:119-120`
- `scripts/verify_daily_research_quota.py:120-143`
- `scripts/com.new-top10.fog-research-worker.plist:14-15`

Trigger：

1. LaunchAgent 每 900 秒執行 Fog worker。
2. Worker 與 daily shell 以主機本地 `date +%F` 建立 `RUN_DATE`。
3. Runtime receipt 以 `datetime.now(timezone.utc)` 建立 `generated_at`。
4. Freshness gate 把已正規化為 UTC 的 `generated.date()` 直接與本地
   `RUN_DATE` 比較。

在 Asia/Taipei 的 00:00–07:59，合法、僅一分鐘新的 receipt 仍位於前一個 UTC
日期，因此被拒絕：

```text
run_date:          2026-07-28
generated_at:      2026-07-27T16:30:00+00:00
verification_time: 2026-07-27T16:31:00+00:00
age_seconds:       60
result:            ok=false
```

控制組：

```text
run_date:          2026-07-28
generated_at:      2026-07-28T01:00:00+00:00
verification_time: 2026-07-28T01:01:00+00:00
age_seconds:       60
result:            ok=true
```

Risk：合法 closed-regime run 在每日八小時窗口內會被 daily verifier 阻擋。Fog
worker 會把這個 verification failure 視為 batch failure，依既有三次 retry
邏輯可能開啟 circuit。這是原 receipt freshness finding 的 production-path
regression，不是新需求。

Validation gap：candidate tests 將 `run_date`、`generated_at` 與
`verification_time` 固定在同一 UTC 日期，未覆蓋 shell local-date 與 receipt
UTC-date 跨日的合法案例。

## Independent hostile replay

### RRV-P1-01 / R2-REG-BASELINE-AUTHORITY

- 合法 canonical baseline：`ok=true`
- model drift：`ok=false`
- baseline overwrite：`FileExistsError`
- 任意五檔 protected path set：`ok=false`
- alternate baseline output：拒絕
- source identity drift：`ok=false`
- worker 忽略 attacker baseline env，僅讀 canonical baseline
- worker 不含 baseline create/update path

Disposition：`CLOSED`。

### RRV-P1-02 / R2-REG-RECEIPT-IDENTITY-FRESHNESS

原 hostile attacks：

| Attack | Result |
|---|---|
| wrong run date | `BLOCKED` |
| forged queue/runner identity | `BLOCKED` |
| missing state transition | `BLOCKED` |
| unknown field | `BLOCKED` |
| daily artifact hash drift | `BLOCKED` |
| 1999 generated time | `BLOCKED` |
| 2199 generated time | `BLOCKED` |
| timezone-naive generated time | `BLOCKED` |
| forged exact-regime identity | `BLOCKED` |
| legitimate same-UTC-date receipt | `COMPLETED` |

但合法 local/UTC 跨日 receipt 重現 `ok=false`，所以 disposition 為
`OPEN / P1`。

### RRV-P1-03 / R2-REG-SOURCE-LINEAGE

- forged processed ID：`FAILED`
- difference：
  `map_only=["processed-b"]`、`inventory_only=["forged-id"]`
- legitimate canonical lineage：`OK`
- missing canonical source：`FAILED`
- nonexistent path＋任意 64-char hash：`FAILED`
- source role addition/removal：`FAILED`
- `../` path escape：`FAILED`
- symlink escape：`FAILED`

Disposition：`CLOSED`。

## Canonical contract hashes

獨立重算結果與 Repair evidence 一致：

| Contract | SHA-256 |
|---|---|
| protected roles/paths | `746738190aeb9063f5b37ba42b4f50ed9df3952e251bcde180ab0c75d9281917` |
| research-map sources | `6e2997a68b3e215cda201488e41a2387b56badd0ae52024b05df6a350ed7e3f1` |
| weekend-inventory sources | `e924d55c67766ce26053ce873172c3b4297efaadb8ef431f14d009ab02116348` |

## Verification

Fixed Repair-2 regression tests：

```text
R2-REG-BASELINE-AUTHORITY
R2-REG-RECEIPT-IDENTITY-FRESHNESS
R2-REG-SOURCE-LINEAGE

10 passed in 1.15s
```

Required targeted：

```text
tests/test_weekend_universe_inventory_snapshot.py
tests/test_daily_research_quota_verifier.py
tests/test_fog_closed_regime_runtime.py

31 passed in 1.67s
```

Shell / syntax：

```text
bash tests/test_fog_research_retry_circuit.sh: PASS
bash tests/test_research_lock_contention.sh: PASS
bash -n scripts/run_daily_research_quota.sh: PASS
bash -n scripts/run_fog_research_worker.sh: PASS
```

Full suite 初跑：

```text
560 passed, 1 failed, 4 warnings, 246 subtests passed
failure: research_component_ledger evidence_exists
```

暫掛與前次 Review 相同的 12 個主 repo gitignored historical evidence/reference
read-only symlink 後：

```text
561 passed, 4 warnings, 246 subtests passed in 61.08s
```

所有暫時 symlink 與 hostile harness 均已移除；provisioning 不計為 candidate
能力。

Diff hygiene：

```text
git diff --check \
  394b90feae0a5c11a75a578ea4e721b44bb3893d..\
  acd835df3a4fe40a149333dca0b55e62cc8eded9

PASS
```

## Scope and production boundary

- base→candidate changed files 均位於 Repair-2 allowlist。
- tracked model、baseline stats、weights、promotion contract 無 candidate diff。
- candidate diff 未出現新增本機絕對路徑、TODO、FIXME 或 DEBUG marker。
- 本 review 沒有執行 live baseline create、circuit recovery 或三輪 scheduler
  acceptance。

## Acceptance mapping

- `SC-R2-01`：PASS；`RRV-P1-01` closed。
- `SC-R2-02`：FAIL；hostile freshness/identity 已拒絕，但合法 local/UTC 跨日
  receipt 被誤拒，`RRV-P1-02` remains open。
- `SC-R2-03`：PASS；`RRV-P1-03` closed。
- `SC-R2-04`：hostile/targeted/shell/full suite 與 protected diff boundary
  通過，但不能抵銷 `SC-R2-02` P1。

Final state：`BLOCKED / REVIEW_REPAIR_LIMIT`。禁止 Repair-3；等待主線依
visible-thread-card-flow 決定 successor architecture chain，不在本 Reviewer
task 建卡或修改 candidate。

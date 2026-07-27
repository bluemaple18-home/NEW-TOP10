# REVIEW-FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1

## Verdict

`NO_GO`

Repair candidate `394b90feae0a5c11a75a578ea4e721b44bb3893d` 已封閉卡片列出的
基本 forged-ID、receipt 欄位與 baseline mutation 測試，但三個 trust boundary
仍可被獨立 hostile fixture 繞過。不得進入 mainline runtime acceptance；應進
Repair-2。

## Fixed boundary and preflight

- base：`5e1de6aa170f7c2446e5da76fadfa75a88495e54`
- candidate：`394b90feae0a5c11a75a578ea4e721b44bb3893d`
- review starting HEAD：`5fc158b2acc30a5f57f3bc78cc4eda605cbfeca0`
- `base` 是 `candidate` ancestor：PASS
- `candidate` 是 review starting HEAD ancestor：PASS
- `candidate..HEAD` 只有 Review card commit
  `5fc158b2acc30a5f57f3bc78cc4eda605cbfeca0`：PASS
- preflight worktree：clean
- runtime：主 repo 受信任 Python `<main-repo>/.venv/bin/python`
- 未建立或下載 `.venv`；未操作 live state、queue、LaunchAgent、production
  artifacts、merge、push、kickstart 或 acceptance

## Findings

### RRV-P1-01：Production baseline 的 path/hash authority 仍由 baseline 自己提供

位置：

- `scripts/verify_fog_closed_regime_recovery.py:123-170`
- `scripts/verify_fog_closed_regime_recovery.py:266-280`
- `scripts/run_fog_research_worker.sh:157-174`

Production 主路徑未傳入獨立、固定的 protected role-to-path authority。
`verify_production_hash_baseline()` 在 `protected_paths` 缺省時，直接從待驗
baseline 的 `artifacts[*].path` 建立 current paths，再把同一 baseline 的 hash
與這些路徑的當下 hash 比較。因此 baseline 同時定義「哪些檔案受保護」及「正確 hash
為何」。

獨立重現：

- 對已建立 baseline 的 model fixture 改檔，且保留原 baseline：
  `ok=false`（正確拒絕）。
- missing role：`ok=false`。
- 以外部 protected-path mapping 攻擊 path drift：`ok=false`。
- source identity drift：`ok=false`。
- model 漂移後，以當下五個檔案重建 baseline，再走 production 實際使用的
  `protected_paths=None` 路徑：`ok=true`。
- 以任意五個 attacker-controlled 檔案宣告 model/baseline/ranking/weights/
  promotion，source identity 使用預期值：`ok=true`。

Shell 只要求 `TOP10_FOG_PRODUCTION_HASH_BASELINE` 指向既有檔案；candidate 沒有
CLI/callsite 在 recovery 前從獨立 authority 建立或封存 baseline。候選測試中的
fake verifier 也不讀 baseline 內容，不能證明 shell wiring 建立了可信 baseline。

影響：待驗 runtime 漂移後可同步重建 self-consistent baseline，或替換完整 path
set，仍取得 production hash gate approval。這直接違反 immutable trusted
baseline、path-set drift 與「不可由 runtime 自我覆寫」契約。

Repair 建議：verifier 內建或讀取另一個受信任、不可由 baseline 控制的 canonical
role-to-path contract；在待驗 runtime 前由明確 shell step 建立 baseline，固定
provenance/creation boundary，recovery 只能唯讀該 baseline，且測試必須走真正
shell/verifier 而非忽略 baseline 的 fake success。

### RRV-P1-02：Receipt freshness 與 exact-regime identity 未綁定可重算 authority

位置：

- `scripts/verify_daily_research_quota.py:248-319`

`generated_at` 只參與 exact-key schema 檢查，沒有解析、日期或 freshness 驗證。
`exact_regime` 只檢查 base regime 非空、family tags 是 list、identity ID 非空；
verifier 沒有從已驗證 history 與 run date 重算 identity 後逐欄比較。

獨立重現以合法 receipt 為起點：

| Mutation | Result |
|---|---|
| wrong `run_date` | `BLOCKED` |
| forged queue owner / runner identity | `BLOCKED` |
| missing `state_transition` | `BLOCKED` |
| unknown top-level field | `BLOCKED` |
| daily artifact hash drift | `BLOCKED` |
| `generated_at=1999-01-01T00:00:00+00:00` | `COMPLETED` |
| `generated_at=2199-01-01T00:00:00+00:00` | `COMPLETED` |
| forged base regime / family tags / identity ID | `COMPLETED` |

影響：stale/future receipt 或偽造 exact regime identity 仍可取得 `COMPLETED`，
違反 receipt date/freshness 與 exact-regime lineage binding。

Repair 建議：從綁定 history 呼叫同一個 regime context authority，以 run date
重算完整 exact identity 並 exact compare；解析 `generated_at`，拒絕無 timezone、
future、stale 或不符合 run lifecycle window 的 receipt。

### RRV-P1-03：Processed artifact 的 source hash lineage 只驗格式，不驗內容

位置：

- `scripts/verify_processed_id_authority.py:132-158`
- `scripts/verify_processed_id_authority.py:238-276`

`_source_hashes()` 只要看到非空 mapping、非空 path 與長度 64 的 digest 就直接接受；
`source_hash_lineage` check 也只檢查兩邊 mapping 非空。它不要求 canonical source
set、source file 存在，也不重算 hash 與 declared digest 比較。

獨立重現：

- inventory 以 `forged-id` 取代 `processed-b`：
  `FAILED`，`map_only=["processed-b"]`、
  `inventory_only=["forged-id"]`（正確拒絕）。
- 將兩邊 processed IDs 修正一致，但 source paths 指向不存在的 fixture，hash
  分別填入任意 64 個 `a`/`b`：整體 `status=OK`。

兩個 processed set 的確從兩個 artifact representation 讀取，但 source lineage
不是可信 authority。這違反 artifact source-hash failure 必須 fail closed 的
Repair requirement。

Repair 建議：固定每種 artifact 的必要 source role/path set，resolve canonical
path、要求檔案存在，重算 digest 並 exact compare；不得以 payload 自報的任意
path/hash mapping 取代 lineage 驗證。

## Required hostile attacks

### Processed-ID authority

- forged ID replacement：正確 fail closed。
- bounded difference：`map_only=["processed-b"]`、
  `inventory_only=["forged-id"]`。
- 額外 lineage attack：不存在來源加任意 64-char hash 仍 `OK`，形成
  `RRV-P1-03`。

### Runtime receipt

- wrong date、forged queue/runner identity、missing transition、unknown field、
  artifact hash drift：均正確 `BLOCKED`。
- stale/future `generated_at` 與 forged exact-regime identity：仍
  `COMPLETED`，形成 `RRV-P1-02`。

### Production baseline

- 原 baseline 下的 model hash drift、missing role、external-authority path drift、
  source identity drift：均正確拒絕。
- production 實際 self-authoritative path 下，漂移後重建 baseline 或任意五檔
  path set：均 `ok=true`，形成 `RRV-P1-01`。

## Verification

Targeted：

```text
tests/test_weekend_universe_inventory_snapshot.py
tests/test_daily_research_quota_verifier.py
tests/test_fog_closed_regime_runtime.py

21 passed in 2.68s
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
550 passed, 1 failed, 4 warnings, 246 subtests passed
failure: research_component_ledger evidence_exists
```

依 Review card 暫掛主 repo 既有 gitignored historical evidence/reference fixtures
的 read-only symlink 後：

```text
551 passed, 4 warnings, 246 subtests passed in 61.51s
```

所有暫時 symlink 與臨時 hostile harness 均已移除；provisioning 不計為 candidate
能力。

Diff hygiene：

```text
git diff --check \
  5e1de6aa170f7c2446e5da76fadfa75a88495e54..\
  394b90feae0a5c11a75a578ea4e721b44bb3893d

PASS
```

## Scope and production boundary

- base→candidate 共 14 個 changed files，全部位於 Repair allowlist。
- diff 未修改 model、baseline stats、ranking、weights、promotion contract 或其他
  production protected artifacts。
- closed-regime public path、queue/circuit regression tests 均通過。
- 未執行 live/runtime acceptance；本 verdict 只判定 Repair trust contract。

## Acceptance mapping

- `SC-R1-01`：`NO_GO`。forged processed ID 已拒絕，但 source lineage 仍可偽造。
- `SC-R1-02`：`NO_GO`。指定欄位攻擊已拒絕，但 stale/future generated time 與
  forged exact-regime identity 仍可完成。
- `SC-R1-03`：`NO_GO`。mutation tests 在外部 authority 下通過，但 production
  verifier 沒有獨立 path authority，baseline 可在 drift 後自我重建。
- `SC-R1-04`：測試與 protected diff boundary 通過；無法抵銷前三個 P1。

下一步：建立 `FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-2`，封閉上述三個 P1 後重新
獨立 review。

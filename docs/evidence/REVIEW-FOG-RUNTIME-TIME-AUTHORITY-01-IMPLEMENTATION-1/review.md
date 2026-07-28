---
card_id: REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1
verdict: REVIEW_NO_GO
reviewed_commit: f7d51a3d994707c819198fd1edcdcf0db4dd0775
base_commit: 87e4da7dd63bafe82b16c28990e7be6db137b4e6
reviewer_thread_id: 019fa66b-444f-7522-915b-15aad3de5fe3
evidence_kind: independent_implementation_review
---

# REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1

## Verdict

`REVIEW_NO_GO`

Candidate 的 time projection、freshness、receipt exact schema與 shell static
wiring通過 targeted、full regression及多數 hostile probes；但 repo-owned
source/baseline authority仍可由呼叫端自報，且 daily source lineage缺欄時 producer
會以 regime source date補值並簽出有效 v3 receipt。兩項皆重現 predecessor
authority-confusion production safety pattern，屬 P1 blocker。

本 verdict只審查固定 candidate；不建立 Repair、不修改 candidate code、不授權
merge、push、deploy、I5 migration或 mainline／production acceptance。

## Preflight與fixed boundary

```text
worktree: registered / isolated / detached
review_starting_head: 207db540fba66ac4516d6a86d0471e6172ae1f08
reviewed_candidate: f7d51a3d994707c819198fd1edcdcf0db4dd0775
candidate_parent: 87e4da7dd63bafe82b16c28990e7be6db137b4e6
merge_base: 87e4da7dd63bafe82b16c28990e7be6db137b4e6
candidate_parent_count: 1
candidate_reachable: PASS
starting_worktree_clean: PASS
git_metadata: PASS
python: trusted main-repo .venv / CPython 3.12.12
pytest: 9.1.1
bash: /bin/bash
plutil: /usr/bin/plutil
network_needed: NO
live_runtime_needed: NO
live_state_mutation: NONE
```

Candidate diff共 19 個檔案，均在 Implementation allowlist；architecture/schema
未改，model／ranking／weights／baseline／promotion protected surface無 diff。

## Findings

### FRTA-IMPL-P1-01：source role/path與 baseline provenance仍由 caller自報

- severity：`P1`
- category：`correctness / security / authority confusion / regression`
- path:line：
  `scripts/verify_fog_closed_regime_recovery.py:27`、
  `scripts/verify_fog_closed_regime_recovery.py:82`、
  `scripts/verify_processed_id_authority.py:48`、
  `scripts/fog_authority_contracts.py:123`
- 觸發條件：呼叫端同時提供兩組自選但互異的 source role/path，或在 runtime
  當下依目前 protected files建立 baseline，再把 baseline path與自選
  `source_identity`傳入 verifier。
- 證據：獨立 probe 的
  `processed_authority.self_reported_distinct_sources_rejected=false`與
  `baseline_authority.self_reported_baseline_rejected=false`。同一 probe同時證明
  forged set、shared source、hash drift、role swap、parent escape、symlink escape
  均會拒絕，因此問題不是 digest/path resolver，而是 expected authority本身來自
  caller。CLI 的 `--research-map-source-role`、
  `--inventory-source-role`、`--baseline`與`--source-identity`沒有與 repo-owned
  versioned contract exact compare。
- 風險：attacker／runtime可建立 self-consistent source與 baseline envelope，
  使 `verify_recovery()`回傳 `RECOVERY_AUTHORITY_VERIFIED`；這重新打開已固定的
  `RRV-P1-01`／`RRV-P1-03` trust-boundary pattern，違反
  `FRTA-REG-RRV-P1-01-PROCESSED-ID`與
  `FRTA-REG-RRV-P1-03-SOURCE-BASELINE`。
- 建議修法：把 research-map／inventory artifact path、各自 source role/path
  set、canonical baseline path與 source identity放入 repo-owned versioned
  authority；production CLI不得接受 override，legacy flags只能 exact-compare。
  Baseline建立需在 recovery runtime之外形成不可覆寫的 provenance boundary，
  verifier只讀既定 baseline並驗其 identity/hash。
- 驗證缺口：candidate tests直接把測試自行建立的 mapping傳為
  `expected_roles`，因此沒有走 production CLI的自報 attack；也沒有以同步建立的
  canonical-path baseline測試 immutability。
- 信心：`high`

### FRTA-IMPL-P1-02：缺少 daily source lineage仍可產生有效 receipt v3

- severity：`P1`
- category：`correctness / source-lineage authority / production safety`
- path:line：`scripts/verify_closed_regime_runtime.py:123`
- 觸發條件：canonical daily artifact有合法 `run_date`與 topic runs，但沒有
  `source_date`、`daily_source_date`或
  `source_lineage.daily_source_date`。
- 證據：`_canonical_daily()`第 128–133 行最後回退到
  `canonical_source_trade_date`。獨立 fixture完全移除 daily source lineage後，
  `build_receipt()`仍成功，probe回報
  `receipt_and_time.missing_daily_source_rejected=false`。
- 風險：regime-history source date被補成 daily artifact source authority，
  producer會為缺失 lineage的 artifact簽出 exact-schema v3 receipt；verifier又用
  同一補值邏輯重算，因此 producer／verifier共識無法證明原始 daily source。
  這直接違反「兩個 source dates不得互相補值」及 missing authority fail-closed
  contract。
- 建議修法：daily artifact必須從唯一明定欄位／lineage object讀到
  `daily_source_date`；缺欄立即
  `DAILY_ARTIFACT_SCHEMA_REJECT`，不得以 regime source date回填。新增 producer與
  verifier各自的 missing-lineage hostile regression。
- 驗證缺口：candidate only測 wrong/future source date，沒有刪除全部 daily
  source欄位。
- 信心：`high`

### FRTA-IMPL-P2-03：immutable context檔案沒有 lifecycle cleanup

- severity：`P2`
- category：`performance / unbounded I/O / maintainability`
- path:line：`scripts/run_fog_research_worker.sh:128`
- 觸發條件：每次 worker invocation取得 locks後建立
  `logs/fog_runtime_run_context.*`。
- 證據：檔案被改為 `0444`，但 `cleanup_locks()`只刪 locks，script無 context
  cleanup或 retention；每個 scheduler interval永久增加一個 inode。
- 風險：長期 scheduler運行造成無界小檔案與 inode成長；不影響本次 authority
  verdict，但屬明確 operational debt。
- 建議修法：在 child與receipt完成後由 trap精確刪除本 invocation context，或把
  context納入有界、明確的 receipt retention policy。
- 驗證缺口：shell test只驗建立一次，未驗退出後清理／retention。
- 信心：`high`

## Spec axis

`FAIL`

- I1–I4：不完整；P1-01使 processed/source/baseline authority不是 repo-owned，
  P1-02使 daily source authority可被另一來源補造。
- Time authority：PASS；strict UTC `Z`、Taipei projection、`-5`／`900`與超界、
  UTC日界、market-midnight、host TZ invariance均通過。
- Date separation：部分 PASS；合法明示休市 lineage通過，但 missing daily
  lineage fail-open。
- Receipt v3 exact schema：PASS；missing/unknown/type/hash/artifact mutation與v2
  relabel拒絕。
- Wiring：PASS；worker只建立一次 context，daily只傳遞，無 `date +%F`
  identity fallback，plist未注入 policy，queue owner維持 `fog_worker`。
- I5／live migration／production acceptance：`NOT RUN / OUT OF SCOPE`。

## Standards axis

`FAIL`

- correctness：P1-01、P1-02阻擋。
- regression／backward compatibility：targeted與full suite在補齊既有唯讀
  evidence後通過；authority trust-boundary屬 predecessor warning pattern復發。
- security／path traversal／symlink：escape、hash drift、role swap均 fail closed；
  expected authority caller-controlled仍形成 authority confusion。
- performance／unbounded I/O：P2-03；沒有無界 loop或大型 payload新 regression。
- maintainability：producer／verifier共用 schema與 time/date helpers是單一實作；
  但共用的 source-date fallback會讓雙方一致地接受錯誤 authority。
- test gaps：缺 production CLI self-report、runtime-synchronous baseline與 missing
  daily-source probes；candidate stored 32 PASS不足以覆蓋這三種 attack。

## Independent hostile probes

Probe：
`docs/evidence/REVIEW-FOG-RUNTIME-TIME-AUTHORITY-01-IMPLEMENTATION-1/hostile_probe.py`

Command exit：`1`（預期，因三個 candidate fail-open）。

```text
PASS: forged processed-ID / set difference
PASS: two artifacts sharing one source
PASS: source path escape / symlink escape / hash drift / role swap
FAIL: caller-selected distinct source role/path authority
PASS: legitimate baseline shape control / post-baseline hash drift
FAIL: caller-selected baseline path + source identity
PASS: receipt missing / unknown / wrong type / wrong contract hash
PASS: artifact identity drift / naive timestamp / v2 exact-schema rejection
PASS: -5 and 900 boundaries; -5.001 and 900.001 rejection
PASS: UTC date boundary / legal holiday explicit lineage / three host TZs
PASS: legacy env mismatch / market-midnight rollover / shell-plist static scan
PASS: queue owner static ownership
FAIL: missing daily source lineage
```

固定 regression disposition：

```text
FRTA-REG-RRV-P1-01-PROCESSED-ID: FAIL
FRTA-REG-RRV-P1-03-SOURCE-BASELINE: FAIL
FRTA-REG-RECEIPT-V3-EXACT: PASS
FRTA-REG-TIME-DATE-LINEAGE: FAIL (missing-lineage subcase)
```

## Verification

Targeted Python：

```text
32 passed in 0.09s
```

Shell／syntax／plist：

```text
test_fog_research_retry_circuit.sh: PASS
test_fog_runtime_time_wiring.sh: PASS
run_fog_research_worker.sh bash -n: PASS
run_daily_research_quota.sh bash -n: PASS
com.new-top10.fog-research-worker.plist: OK
```

Full suite原始 isolated run：

```text
1 failed, 564 passed, 4 warnings, 246 subtests passed
failure: ResearchComponentLedgerTest.test_verifier_accepts_generated_ledger
cause: 12 historical evidence/reference paths absent from isolated worktree
```

12 個路徑逐一確認在 base→candidate無 diff，且 main repo有既有實體。第一次暫掛因
`artifacts/model_experiments/`目錄本身缺失，7 個 link未建立，保存相同原始
failure；建立空目錄並確認總數 12 後，final full suite：

```text
565 passed, 4 warnings, 246 subtests passed in 62.19s
```

重跑後已逐一移除 12 個 symlink與空目錄，無 allowlist外殘留。

其他 gates：

```text
candidate exact allowlist: PASS
protected surface diff: NONE
architecture/schema diff: NONE
secret/local-absolute-path/debug/TODO scan: no blocking hit
git diff --check: PASS
```

## Remaining risk與boundary

- P1-01與P1-02修復前，candidate不得取得 Implementation Review GO。
- P2-03不單獨阻擋，但應在同一 Repair評估 bounded cleanup。
- 未操作 live LaunchAgent、queue、retry/circuit、model、ranking、weights、
  baseline、promotion或 production artifact。
- 未 push、merge、deploy、建立 Repair或執行 I5。

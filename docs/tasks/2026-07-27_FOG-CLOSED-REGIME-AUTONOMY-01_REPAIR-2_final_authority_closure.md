---
id: FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-2
status: READY_TO_DISPATCH
type: repair
chain_id: FOG-CLOSED-REGIME-AUTONOMY-01
repair_generation: 2
ownership: repair_executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
base_candidate_sha: 394b90feae0a5c11a75a578ea4e721b44bb3893d
review_evidence_commit: 78d2eddc34386d998675e8e16f0013892ffb3b09
evidence_path: docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-2/
---

# FOG-CLOSED-REGIME-AUTONOMY-01 Repair-2：最終 authority closure

## Root question

如何讓三個 verifier 的 authority 來自 runtime payload 以外、可重算且不可在 drift 後
被待驗流程重建的固定契約，關閉 Repair-1 re-review 的三個 P1？

這是本 chain 最後允許的 Repair。若 re-review 仍為 `NO_GO`，必須標記
`BLOCKED_REPAIR_LIMIT` 並另開 successor architecture chain；禁止 Repair-3。

## Fixed boundary

- Repair base：`394b90feae0a5c11a75a578ea4e721b44bb3893d`
- Review verdict：`NO_GO`
- Review evidence：
  `docs/evidence/REVIEW-FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-1/review.md`

## Blocking findings

### R2-P1-01：Production protected-set authority 可自我宣告

- protected role-to-path set 必須由 verifier 內建的 versioned canonical contract
  或獨立受信任 tracked contract 提供；不得從 baseline、env payload或 runtime
  receipt 推導。
- baseline 建立必須是 mainline integration 後、任何 recovery／worker mutation
  前的明確一次性 pre-recovery step。
- recovery worker只能唯讀既有 baseline；不得建立、更新、覆寫或接受替代 path set。
- baseline 必須綁 canonical contract hash、source commit、created-at boundary與
  current artifact hashes；baseline 檔已存在時 create command 必須 fail closed。

### R2-P1-02：Receipt freshness／exact-regime identity 未可重算

- 由已驗證的 market-regime history artifact與 run date呼叫同一 accepted regime
  context authority，重算完整 exact identity；逐欄 exact compare base regime、
  family tags、identity ID與 lineage。
- `generated_at` 必須是有 timezone 的 RFC3339；拒絕 parse failure、future、
  run-date mismatch及超出明確 lifecycle window 的 stale receipt。
- freshness window 必須由 verifier policy固定，不得由 receipt/env 控制。

### R2-P1-03：Processed source lineage 只驗 digest 格式

- 對 research-map與inventory分別固定必要 source roles與 canonical repo-relative
  paths；不得接受 payload 自選 source set/path。
- 要求 source file存在、不是 symlink escape，重算 SHA-256並與 artifact宣告逐項
  exact compare。
- source role/path set增減、缺檔、任意 64-char digest、路徑逃逸均須 fail closed。

## Phase 0：Hostile tests first

修改 production code前，將 Reviewer 的三個 bypass 固化為 red tests：

1. drift 後重建 baseline、任意五檔 protected set、baseline overwrite。
2. 1999/2199 `generated_at`、naive timestamp、forged exact identity。
3. 不存在 source path＋任意 64-char hash、source set增減、symlink/path escape。

舊 candidate必須紅；修後全部綠。保存：
`docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-2/phase0-red.md`。

## Allowlist

- Repair-1 已修改的 verifier／builder／Fog shell wiring
- 直接相關的 `tests/test_*.py`／shell tests
- 新增 tracked canonical authority contract（僅必要時）
- `docs/evidence/FOG-CLOSED-REGIME-AUTONOMY-01-REPAIR-2/**`
- 本卡狀態／receipt

## 禁止範圍

- 不修改 research policy、ranking、model、weights、promotion、API、UI或外部資料。
- 不操作 live state、queue、LaunchAgent或 production artifacts。
- 不 merge、push、kickstart、建立 live baseline或執行 acceptance。
- 不以 HMAC／簽章假裝解決 key custody；本輪 authority 必須由固定 tracked contract、
  source commit與受控 pre-recovery ordering建立。

## Verification

```bash
cd <repo-root>
.venv/bin/python -m pytest -q \
  tests/test_weekend_universe_inventory_snapshot.py \
  tests/test_daily_research_quota_verifier.py \
  tests/test_fog_closed_regime_runtime.py
bash tests/test_fog_research_retry_circuit.sh
bash tests/test_research_lock_contention.sh
bash -n scripts/run_daily_research_quota.sh
bash -n scripts/run_fog_research_worker.sh
.venv/bin/python -m pytest -q
git diff --check
```

需保存 hostile red→green、canonical authority contract hash、protected artifacts
before/after hashes、changed-files allowlist與 candidate SHA。

## Success criteria

- `SC-R2-01`：baseline 不能自選 path set、重建或覆寫；canonical protected-set drift
  必定拒絕。
- `SC-R2-02`：receipt freshness與 exact identity均由外部可信 artifact重算。
- `SC-R2-03`：processed source roles、paths與 hashes均實際存在並重算一致。
- `SC-R2-04`：hostile／targeted／shell／full suite全綠，protected production
  artifacts unchanged。

## Delivery

- 只交付 `DELIVERED_REPAIR_2_CANDIDATE`。
- 必須由 Repair-1 的獨立 Reviewer task進行 re-review；Reviewer不得修改 candidate。
- `GO_FOR_MAINLINE_RUNTIME_ACCEPTANCE` 前不得整合或操作 live runtime。
- `NO_GO` 時標記 `BLOCKED_REPAIR_LIMIT`，禁止 Repair-3。

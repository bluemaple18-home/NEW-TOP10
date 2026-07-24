# REVIEW-RESEARCH-FUNDAMENTAL-VOLUME-01 Independent Review

## Verdict

`REVIEW_NO_GO`

本次為 research-only implementation 的獨立 post-merge review。未修改 reviewed implementation；未存取元大 secure attachment；未抓取外部資料；未修改 production ranking、model、feature、weights 或 push。

## Reviewed range

- base commit：`f716883503941320fd8b27a9c88b36576557ed50`
- base tree：`fa7e6d73102c80c95af6a243cc59959d55f6649b`
- reviewed commit：`4deb72660dce9fc15f44d45e30307eb24f0caae1`
- reviewed tree：`0da29621e673a1b78d6899f4077e05f4f3a82d4f`
- reviewed commits：
  - `d97a4f5` — fundamental point-in-time readiness
  - `4deb726` — volume climax warning shadow automation

## Findings

### [P1] Daily runner 未 fail closed 驗證既有 Volume ledger 不變量

- path：`scripts/run_volume_climax_warning_append_only_shadow.py:158`
- related path：`scripts/run_volume_climax_warning_append_only_shadow.py:178`
- related path：`scripts/run_overlay_shadow_daily_monitor.py:229`
- 觸發條件：既有 ledger 已含重複 `ranking_date`、seal date 以前 observation、被改寫的 warning-only 欄位，或 observation source hash 缺漏／異常。
- evidence：runner 僅把既有日期收成 `set` 後跳過重算，再排序並寫回；沒有在追加前驗證日期唯一、既有順序、所有 observation 都晚於 seal、warning-only 欄位、source hash 或 60-date promotion 邊界。combined daily monitor 只依 component exit code 判定 `OK`，不會呼叫 verifier。
- risk：已損壞或遭改寫的 prospective ledger 可被 daily monitor 繼續接受並回報 component `OK`，使 append-only research evidence 失去完整性；production 流程雖維持 allow-failure，但研究結論可能建立在不可信 ledger 上。
- 修復驗收：
  1. Volume runner 在任何寫入前驗證既有 observation 日期唯一、嚴格排序且全部晚於 seal。
  2. 驗證 frozen contract／config hash、source hashes、warning-only／no-ranking-change／no-push 欄位及 promotion fail-closed。
  3. 任一不變量失敗時 component 非零退出，combined status 為 `PARTIAL`，production daily 仍不被阻斷。
  4. 新增 corrupt-ledger fixtures，覆蓋 duplicate date、pre-seal date、mutated warning semantics 與 missing source hash。

### [P2] Fundamental verifier 並非獨立重算

- path：`scripts/verify_fundamental_point_in_time_readiness.py:15`
- related path：`scripts/verify_fundamental_point_in_time_readiness.py:23`
- 觸發條件：builder 的 as-of、maturity、coverage 或 gate 實作出現共同邏輯錯誤。
- evidence：verifier 直接 import 並呼叫 `build_payload()`，再與 committed artifact 比對；它沒有用獨立計算路徑重算 `23/1967`、latest `3/200`、`0/252`。
- risk：builder 與 verifier 共享同一錯誤時仍可 PASS，無法支持 result 所宣稱的「independent recomputation verifier」。
- 修復驗收：verifier 不 import `build_payload`，以獨立資料讀取與聚合路徑重算 stock coverage、Top200 daily coverage、D+10 maturity exclusion、252-day research gate 與 80% model gate，並加入至少一個會使 builder 與 verifier 分歧的 mutation fixture。

### [P2] Volume verifier 未覆蓋任務卡要求的完整封印契約

- path：`scripts/verify_volume_climax_warning_append_only_shadow.py:71`
- related path：`scripts/verify_overlay_shadow_daily_monitor.py:34`
- 觸發條件：config／ledger contract、source hash、warning-only 欄位或 60-date gate 發生 regression，但 RISK_ON／RISK_OFF happy-path counts 仍相同。
- evidence：fixture 驗證 signal counts、regime activation 與 observation rerun idempotency；combined verifier驗證日期唯一及 component receipt，但未明確斷言 config hash、每筆 source hash、`production_ranking_changed=false`、`push_sent=false`、warning text 唯一語意及 60-date fail-closed。
- risk：核心 frozen contract regression 可能未被指定 verifier 捕捉。
- 修復驗收：新增逐項 invariant assertions 與 59／60／61 observation boundary fixtures；任何缺漏或語意改寫皆非零退出。

## Spec axis

- Fundamental readiness：
  - builder 重用 M4 backward as-of join。
  - 使用 point-in-time trailing 20D liquidity Top200。
  - 排除最後 10 個交易日後取最近 252 日。
  - 30 檔／70% research gate 與 80% model gate 寫入 artifact。
  - selection-bias note 明確禁止把低 coverage 正向 IC／spread 當 promotion 證據。
  - Reviewer 的獨立唯讀重算曾得到 `23/1967`、latest `3/200`、`0/252`，但該次在 provisioning 補充前於非 Reviewer cwd 執行，因此不列入正式 worktree acceptance。
- Volume Climax：
  - frozen signal 實作為 `volume_ratio_20d >= 1.8 AND long_upper_shadow`。
  - 只有 `RISK_ON` 產生 active warning；其他 regime 保留 raw signal。
  - 新日期只接受 seal 後 ranking files；existing dates 不重算。
  - config hash 與 observation source hashes 有寫入。
  - production ranking mutation、push 與 automatic promotion 均為 false。
  - 因 P1／P2，既有 ledger fail-closed 與 verifier 完整性未達 strict contract。

## Standards axis

- `uv + .venv`：worktree 本身沒有 `.venv`，正式驗證使用既有專案 `.venv` interpreter，cwd 固定為 Reviewer worktree。
- package manager：未使用 `npm`／`yarn`。
- security／privacy：added-lines secret／token／credential／PII／本機絕對路徑掃描未命中。
- production boundary：reviewed changed-file allowlist 未包含 production ranking、model、weights 或 push implementation。
- tracked worktree：複製 gitignored research inputs／receipts後，`git status --short` 仍 clean；review 寫入前沒有 tracked drift。

## Commands and exit codes

正式完整驗證輪以 Reviewer worktree 為 cwd：

| Command | Exit | Result |
|---|---:|---|
| `<main-repo>/.venv/bin/python scripts/verify_fundamental_point_in_time_readiness.py` | 1 | `AssertionError` at `artifact == build_payload()` |
| `<main-repo>/.venv/bin/python scripts/verify_volume_climax_warning_append_only_shadow.py` | 0 | `VOLUME_CLIMAX_WARNING_APPEND_ONLY_SHADOW_OK` |
| `<main-repo>/.venv/bin/python scripts/verify_overlay_shadow_daily_monitor.py` | 0 | `OVERLAY_SHADOW_DAILY_MONITOR_OK` |
| `<main-repo>/.venv/bin/python -m pytest -q tests/test_overlay_shadow_daily_automation.py tests/test_daily_automation_orchestrator.py` | 0 | `7 passed` |
| `git diff --check f716883503941320fd8b27a9c88b36576557ed50..4deb72660dce9fc15f44d45e30307eb24f0caae1` | 0 | PASS |

Fundamental failure 的唯讀定位顯示：copy 時因 tracked `data/fundamentals/.gitkeep` 使來源目錄被巢狀放入 `data/fundamentals/fundamentals/`，正式 verifier 因此看到不同 cache layout。依停損規則不進行第 4 次驗證；本次 acceptance fail closed。

## Reviewed changed-file allowlist

- `config/volume_climax_warning_shadow_v1.json`
- `docs/evidence/RESEARCH-FUNDAMENTAL-READINESS-01/artifact.json`
- `docs/evidence/RESEARCH-FUNDAMENTAL-READINESS-01/artifact.md`
- `docs/evidence/RESEARCH-FUNDAMENTAL-READINESS-01/result.md`
- `docs/evidence/VOLUME-CLIMAX-WARNING-SHADOW-01/result.md`
- `docs/tasks/2026-07-24_RESEARCH-FUNDAMENTAL-READINESS-01.md`
- `docs/tasks/2026-07-24_VOLUME-CLIMAX-WARNING-SHADOW-01.md`
- `scripts/build_fundamental_point_in_time_readiness.py`
- `scripts/run_overlay_shadow_daily_monitor.py`
- `scripts/run_volume_climax_warning_append_only_shadow.py`
- `scripts/verify_fundamental_point_in_time_readiness.py`
- `scripts/verify_overlay_shadow_daily_monitor.py`
- `scripts/verify_volume_climax_warning_append_only_shadow.py`

## Review change allowlist

- `docs/evidence/REVIEW-RESEARCH-FUNDAMENTAL-VOLUME-01/review.md`
- `docs/tasks/2026-07-24_REVIEW-RESEARCH-FUNDAMENTAL-VOLUME-01.md`

## Not rerun／not performed

- 依停損規則，Fundamental verifier 未做第 4 次重跑。
- 未執行 builder、combined daily runner 或 production daily automation，避免改寫 runtime artifacts。
- 未執行外部資料抓取、model training、ranking、push 或 deployment。
- 未存取元大 secure attachment。

## Remaining risks

- Reviewer worktree 的 ignored local inputs／receipts不是 commit 的一部分，跨機仍需明確 provisioning。
- committed Fundamental artifact 目前缺少真正獨立 verifier 的保證。
- Volume ledger 在 daily runtime 缺少既有資料完整性 fail-closed guard。

## Next step

由主線另開 Repair 卡處理 P1／P2；修復後建立新的固定 SHA re-review。不得在本 Review thread 修改 implementation。

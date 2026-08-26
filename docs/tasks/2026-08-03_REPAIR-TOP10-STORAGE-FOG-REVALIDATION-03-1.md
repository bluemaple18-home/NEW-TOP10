---
id: REPAIR-TOP10-STORAGE-FOG-REVALIDATION-03-1
chain_id: TOP10-STORAGE-FOG-REVALIDATION
status: ready_for_re_review
type: repair
priority: P0
role: repair
cycle: 1
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: Reviewer 已重現 trusted entrypoint digest bypass，且 repair 同時涉及 Seatbelt 與容量 meter fail-closed 邊界；需高強度安全修復，禁止以重跑 workload 取代契約驗證。
repair_base: 9e50aeeef79511906fbca170000084824320821d
review_thread: 019fc6b3-94d8-7373-bdbc-07f82e048d88
review_verdict: REVIEW_NO_GO
blocking_findings: 1
residual_findings: 1
forbidden_scope:
  - 執行 fog、代表性 workload、cycle、reclaim drill 或 stop-loss drill
  - 清除既有 sandbox 或 restart denial
  - 修改 fog business logic、其他七個 job 或 production data/artifacts/models
  - 瀏覽器、cookie、外部 provider、connector 或控制面
  - launchd load、enable、kickstart、restart 或 reload
  - merge、push、deploy 或發布外部訊息
allowed_paths:
  - app/storage_safety.py
  - scripts/storage_validation/fog_research_worker.py
  - docs/operations/top10-storage-policy.json
  - tests/test_storage_safety.py
  - tests/test_fog_storage_validation.py
  - docs/tasks/2026-08-03_REPAIR-TOP10-STORAGE-FOG-REVALIDATION-03-1.md
  - docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/repair-1-verification.md
---

# REPAIR-TOP10-STORAGE-FOG-REVALIDATION-03-1｜Trusted runner 與 meter 邊界修復

## Root question

如何在完全不重跑 fog workload 的前提下，封住 Reviewer 已重現的 `BASH_ENV`／runner-swap
digest bypass、讓 validation Seatbelt 安全支援既有 runner 對 `/dev/null` 的 redirect，並保證
`fog-research-worker` 所有 registered writes 不是被 meter 計量，就是被 guard 以精確原因拒絕？

## 已鎖定失敗證據

### P1｜Shell startup injection 與 runner TOCTOU

Reviewer 在純 tempfile probe 中重現：candidate 會繼承 `BASH_ENV`，`/bin/bash` 在已通過 runner
digest 驗證後、讀取 runner 前先執行 injected file；injected code 可替換 runner，程序仍 exit 0。

這證明目前的 digest pinning 不是 spawn-time 完整性契約。Seatbelt 只能限制可寫 scope，不能把
未受 pinning 的 shell startup code 變成 trusted code。

### Runtime blocker｜`/dev/null` Seatbelt incompatibility

Cycle 1 唯一實際 runtime blocker 是 `scripts/run_fog_research_worker.sh` 在 lock path 使用
`2>/dev/null`，現有 Seatbelt profile 對 `/dev/null` write 回 `Operation not permitted`。child 於
2.39 秒 exit 0，guard 因沒有 valid live sample 判 NO-GO。

### P2｜Registered-but-unmetered writes

fog policy 的 `registered_write_paths=["logs","artifacts"]`，但 meter 只涵蓋部分 artifact
subtrees。實際 call chain 會寫 `artifacts/host_runner`；目前它既不計入 30,000-file／2 GiB
ceiling，也不會被 unknown-write gate 阻擋。

## Root-cause triage 契約

先建立三個彼此獨立、可重跑的 RED；每個 RED 必須因對應症狀失敗，不得以 import／fixture
錯誤替代：

1. hostile environment／runner swap：`BASH_ENV`、`ENV`、shell function import 或相等注入面不得在 pinned runner 前執行；digest 後替換 runner 不得產生 injected output。
2. confinement compatibility：受限 child 對 exact `/dev/null` redirect 成功，但 sandbox 外一般檔案寫入仍被拒絕。
3. meter coverage：registered root 下、所有 meter path 外的新增或修改必須觸發精確 reason code；`artifacts/host_runner` 必須被量測或拒絕。

每次只驗證一個假說；寫入 repair verification 的 RED command／輸出，再做 minimal fix 與 GREEN。
禁止用放寬整個 `/dev`、放寬 sandbox 外 write、提高容量 ceiling、把 `artifacts` 全部視為可信免檢，
或停用 digest check 來轉綠。

## Required repair

### R1｜Strict child environment

- `fog_research_worker.py` 必須改成明確 allowlist／固定值環境，不得從 caller 透傳任意變數。
- 必須固定 `PATH` 與 locale；明確排除 `BASH_ENV`、`ENV`、`SHELLOPTS`、`BASHOPTS`、
  `CDPATH`、`GLOBIGNORE`、`PROMPT_COMMAND`、`LD_*`、`DYLD_*`、`PYTHON*` 與 shell function import。
- 所有必要 HOME/tmp/cache/XDG 路徑仍須收斂在 sandbox。
- 測試必須使用 hostile inherited environment，證明 injected startup code 完全未執行。

### R2｜Execute verified runner bytes

- runner 的 SHA-256 驗證與 Bash 實際讀取之間不得重新信任可替換 path。
- 可採已驗證 file descriptor、child 不可寫 materialization 或等價設計；不得以 raw shell、
  `bash -c`、dynamic command remainder、eval 或重寫 fog business logic 達成。
- runner path replacement、symlink swap、in-place mutation與 entrypoint／contract TOCTOU 必須在
  spawn 前或 child 執行前 fail closed。

### R3｜Exact `/dev/null` Seatbelt capability

- validation profile 只可新增 exact `/dev/null` 所需的最小 read/write capability。
- confinement probe 與 unit test 必須同時證明 `/dev/null` redirect 成功、sandbox 內寫入成功、
  sandbox 外普通檔案寫入仍失敗。
- 不得允許其他 `/dev/*`、任意 absolute path 或 source/main 寫入。

### R4｜Meter coverage invariant

- `artifacts/host_runner` 等已知 fog output 必須加入 meter，或移到既有受 meter 管理的 output root。
- guard 必須保證 registered root 下任何 meter 外變更都有精確 stop reason（例如
  `REGISTERED_WRITE_OUTSIDE_METER`）；不能因路徑被 registered 就跳過 unknown-write 又跳過容量計量。
- 測試要覆蓋新增、修改與 nested path；重疊 meter paths 不得重複計量。
- 不提高 `max_bytes=2147483648`、`max_file_count=30000` 或其他 ceiling。

## Acceptance

### AC-1｜Injection sealed

Given hostile caller environment
When trusted fog entrypoint 啟動
Then 只有 contract、entrypoint 與 runner pinned bytes 可影響執行；shell startup injection 不執行，runner swap fail closed。

### AC-2｜Confinement compatible and narrow

Given validation Seatbelt profile
When child redirect exact `/dev/null` 並嘗試寫 sandbox 外普通檔案
Then `/dev/null` 與 sandbox 內寫入成功，scope 外寫入仍拒絕。

### AC-3｜Every write governed

Given fog registered write roots
When任一檔案變更
Then 它要嘛落在 meter 並受 bytes/files ceiling，要嘛觸發 registered-but-unmetered stop reason；不存在第三條免檢路徑。

### AC-4｜No workload and production remains closed

Repair 只跑 unit／integration／static checks，不建立新 sandbox cycle、不清 restart denial、不執行 fog。
policy `launch_verified=false`、八個 launchd disabled 狀態不變。

## Verification

- RED／GREEN hostile environment + runner swap tests
- RED／GREEN Seatbelt exact `/dev/null` confinement test
- RED／GREEN registered-but-unmetered write tests
- `tests/test_storage_safety.py`
- `tests/test_fog_storage_validation.py`
- 受影響完整 suite
- `PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider`
- `python -m py_compile` 受影響 Python
- policy JSON validation
- `git diff --check`
- main protected hashes與八個 launchd disabled／not loaded 收尾證據

## 收卡輸出

- 單一 candidate commit，40-char SHA，worktree clean。
- `READY_FOR_RE_REVIEW / <SHA>` 或精確 `BLOCKED / <REASON>`。
- changed files、RED／GREEN、affected/full tests、`git diff --check`、residual risks。
- `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/repair-1-verification.md`。
- 不得自審、重跑 workload、merge、push、deploy 或建立 replacement Reviewer。

Repair candidate 產生後，主線必須把同一 Reviewer task `019fc6b3-94d8-7373-bdbc-07f82e048d88`
喚醒做 targeted re-review；只有 `REVIEW_GO` 才能另開 fresh revalidation 卡。

## 施工結果（2026-08-03）

- Trusted adapter 改用 fixed child environment，執行 unlink 後唯讀 materialization bytes，並
  保留真實 runner 的 `$0`／sandbox cwd 與 exit semantics；Generation 2 恢復固定
  `PYTHONDONTWRITEBYTECODE=1`，禁止 local import 回寫 source-tree pycache。
- Validation Seatbelt 只新增 exact `/dev/null` capability；sandbox 外普通檔案仍被拒絕。
- Guard 新增 `REGISTERED_WRITE_OUTSIDE_METER`，fog policy 將
  `artifacts/host_runner` 納入既有 2 GiB／30,000-file ceiling。
- Affected suites：`46 passed, 16 subtests passed`；full suite：
  `1 failed, 679 passed, 4 warnings, 270 subtests passed`，唯一 failure 是既有 ledger evidence gap。
- 未執行 fog／cycle／workload，production `launch_verified=false`；八個 launchd 維持
  disabled／not loaded。詳細 RED／GREEN 與收尾證據見
  `docs/evidence/TOP10-STORAGE-FOG-REVALIDATION-03/repair-1-verification.md`。

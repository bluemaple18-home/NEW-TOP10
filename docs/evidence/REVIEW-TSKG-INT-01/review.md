# REVIEW-TSKG-INT-01 Review Evidence

## Verdict

`REVIEW_GO`

- Fixed reviewed commit：`2a1e5d2493975fda32bb5f9ecdff5dbc5aa018ff`
- Fixed base / first parent：`a9758aa91e95985b16ce154a65521d10df6544d1`
- Fixed target / second parent：`7f472be548c79a0b8d9758dcb3a4cfaca83751ff`
- Findings：P0 0、P1 0、P2 0、P3 0。

## Preflight and topology

- Review worktree 為 platform-managed independent worktree，cwd 不等於 main worktree；review 開始時為 detached HEAD 且 clean。
- `HEAD` 精確等於 fixed reviewed commit。
- Candidate 為恰有兩個 parents 的 merge commit，parent 順序精確等於 fixed base、fixed target。
- Review 卡與 `docs/evidence/TSKG-INT-01/integration.md` 可讀；dispatch receipt 將 Review 卡 placeholder 綁定為 fixed reviewed commit。
- First-parent diff 為 36 個檔：34 個 target payload、1 個 integration evidence、1 個 integration card status/Result 更新；未發現 allowlist 外變更。
- `git diff --check <base>..<candidate>` 通過，review 前後 candidate worktree clean。

## Spec axis

- Candidate 完整保留 accepted TSKG v1.1、SLC-01、Source Gate，以及各自的 Repair、Review、Verification、Acceptance artifacts 與 lineage。
- TSKG v1.1 acceptance 仍只接受 executable spec 與 SLC-01 frontier；baseline provenance 與 SLC-07 SLO acceptance 的既有 blocked/partial 註記未被抹除。
- SLC-01 acceptance 仍明示 synthetic/offline identity-to-company slice，不代表 crawler、外部 source、database、production API 或 SLO 完成。
- Source Gate acceptance 仍明示只接受 synthetic/offline fail-closed gate；OQ-SRC-01 未解除，SLC-02 仍 blocked，沒有把 PUBLIC source 或後續 SLC 誤標為完成。
- Integration card 只標示 `DELIVERED_CANDIDATE`，沒有自稱已 accepted、merged to main、deployed 或 production-ready。

Spec axis verdict：`GO`。

## Standards axis

### Correctness and regression

- `app/tskg` public behavior、closed fixture contracts、temporal resolution、ambiguity handling、standalone router 與 source preflight 均由 focused suite 覆蓋並通過。
- Full suite 唯一 failure 在 fixed first parent 使用同一 interpreter 獨立重現，failure test 與 assertion 相同，未發現 candidate 新增 regression。

### Security and privacy

- Source policy registry 拒絕 `PUBLIC + APPROVED`，PUBLIC fixture 僅為 `BLOCKED/EXPIRED`；denied request 在 reader invocation 前 fail closed。
- Path validation 拒絕 traversal、percent encoding、Unicode compatibility 字元、control characters、URL 與 prefix confusion；receipt 與 reader 共用 canonical path。
- 未發現外部 URL、真實 source bytes、secret、token、PII、交易判定、prediction、score、target price 或模型權重被帶入 runtime payload/fixture。

### Production isolation and scope

- First-parent diff 未修改 `app/api/main.py`、production source adapter、ranking、model、ETL、scheduler、deployment 或 dependency manifest/lockfile。
- TSKG router 保持 standalone，沒有掛入 production API；review 未連外、未 deploy、未 push、未核准 PUBLIC source。

### Maintainability, performance, and testing

- 新模組維持 dependency injection、closed/versioned schema 與 deterministic checksum/receipt 邊界；未新增 dependency。
- 本 candidate 沒有 production hot-path 或 SLO promotion；既有 SLC-07 performance acceptance 仍 blocked，因此本輪無新增 performance finding。
- Focused tests 覆蓋 39 tests／154 subtests；full suite 覆蓋既有 repo regression surface。未發現足以構成 P0–P3 的 testing gap。

Standards axis verdict：`GO`。

## Verification results

### Focused suite

```text
39 passed, 1 warning, 154 subtests passed in 0.93s
```

獨立 worktree 沒有自有 `.venv`，故卡片的字面 `<repo-root>/.venv/bin/python` 第一次執行在進入 pytest 前即因路徑不存在停止；其後沿用主專案既有 uv venv 的 Python 3.12.12 interpreter，cwd/import tree 仍固定在 candidate，未安裝或更新依賴。

### Full suite

```text
1 failed, 367 passed, 4 warnings, 182 subtests passed in 53.58s
```

唯一 failure：

```text
tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
AssertionError: 'FAILED' != 'OK'
```

### Fixed first-parent baseline

固定 first parent 以 `git archive` 匯出到獨立 `/tmp` directory，使用同一 interpreter、停用 bytecode 與 pytest cache，重跑唯一 failing test：

```text
1 failed in 0.62s
AssertionError: 'FAILED' != 'OK'
```

因此 full suite 沒有新增 regression。

### Additional gates

- `python -m py_compile`：TSKG modules 與兩個 focused test files 通過。
- `git diff --check <base>..<candidate>`：通過。
- Merge topology、36-file first-parent allowlist、production/dependency/prohibited-field scans：通過。

## Remaining risk

- OQ-SRC-01 仍需 source/compliance owner 對特定 PUBLIC source 提供 immutable approval；在此之前 SLC-02 不得開始。
- SLC-03 之後、production API 掛載、coverage、persistence、benchmark/SLO 與 Top10 integration 仍依 spec 保持 blocked 或需另卡核准。
- Full suite 保留一個與 candidate 無關、已在 fixed first parent 重現的 research component ledger baseline failure。
- 獨立 worktree 無自有 `.venv`；本次以既有 uv venv 驗證 candidate import tree，未驗證從零同步環境。

## Final state

`REVIEW_GO` — 未發現阻塞問題，亦未發現 P0–P3 findings。Review 僅新增本 evidence 並更新 Review 卡；未修改 candidate code、fixture、spec、merge topology，未修 finding、merge、push 或 deploy。

# REPAIR-TSKG-SRC-01 Repair Evidence

## Lineage and scope

- Fixed base candidate：`bcbf773f8dbee51e84488b1ea3c11fabbad7a28a`。
- Fixed review：`31715802f794f411986abdebb6f368ce31b35834`，verdict
  `REVIEW_NO_GO`。
- Repair-card parent：`717e1c6dffedf254661a12ab41b1092bfae948d9`。
- 只修改 F-01、F-02、F-03；沒有修改 review evidence、fixture、dependency、
  production runtime 或 SLC-01 code/fixture，且沒有連外或建立 public approval。

## Root cause and minimal change

### F-01 — generic mapping public false approval

- Root cause：policy validator 只驗證 `source_class` 與 `decision_status` 各自 enum，
  沒有在 OQ-SRC-01 未解除期間禁止其 `PUBLIC + APPROVED` 組合。
- Change：registry construction 一律拒絕 `PUBLIC + APPROVED`，因此 fixture、file 與
  in-memory mapping 都無法透過 generic contract 建立 public approval。
- Reader proof：custom mapping 在 construction fail loud，reader `0` call。
- Remaining boundary：未來若 source owner 核准 public source，仍須由另一張卡引入
  獨立 immutable decision artifact/constructor；本 repair 沒有實作該能力。

### F-02 — duplicate JSON last-wins

- Root cause：`json.load` 預設先將 duplicate object members last-wins collapse，
  closed-shape validator 接收 mapping 時已失去 raw ambiguity。
- Change：`from_file` 使用遞迴 `object_pairs_hook`，在 mapping 建構前拒絕任何層級
  duplicate member；頂層、policy 與 nested object probes 均 fail loud。
- Remaining boundary：`from_mapping` 接收的 object 已不含 raw JSON member
  provenance，因此無法回溯偵測先前被 parser collapse 的 duplicates；raw policy
  JSON 必須走 `from_file` strict loader，不宣稱 mapping path 可偵測 duplicate JSON。

### F-03 — Unicode compatibility traversal

- Root cause：request path 只檢查 ASCII token 與 `.`／`..` segment，沒有拒絕
  NFKC 後改變的 compatibility characters 或 Unicode control characters。
- Change：allowlist matching 前建立單一保守 canonical path；拒絕 NFKC 會改變的
  path、Unicode `C*` codepoints、backslash、percent encoding、absolute/scheme-relative
  URL、query/fragment、double slash、空 segment 與 `.`／`..`。validation、matching
  與 receipt 共用同一 `canonical_path`，reader callback 也只接收該值；accepted path
  不經改寫。
- Reader proof：fullwidth dot/slash、control、encoded traversal 等 denied matrix 合計
  reader `0` call。

## TDD evidence

所有命令均使用 dispatch 指定的既有 main-workspace `.venv` Python，設定 temporary
`PYTHONPYCACHEPREFIX`，沒有安裝或下載 dependency。

### RED

先只新增三個 public-behavior regression tests，再執行：

```text
<main-workspace>/.venv/bin/python -m unittest \
  tests.test_tskg_src01.TskgSrc01PublicBehaviorTests.test_generic_mapping_cannot_grant_public_approval \
  tests.test_tskg_src01.TskgSrc01PublicBehaviorTests.test_file_loader_rejects_duplicate_json_members_recursively \
  tests.test_tskg_src01.TskgSrc01PublicBehaviorTests.test_unicode_compatibility_and_control_paths_fail_closed -v
```

結果：exit `1`，`Ran 3 tests`，`FAILED (failures=9)`。

- F-01：`SourcePolicyContractError not raised`。
- F-02：registry 與 policy duplicate subtests 均未丟例外。
- F-03：fullwidth compatibility traversal／separator 與三個 control-character
  subtests 均回 `ok=true`，因此 reader 被呼叫。

另以 approved request 建立 reader-boundary seam RED：callback 改為要求 path 參數、
實作仍以零參數呼叫時，`Ran 1 test` / `FAILED (errors=1)`，錯誤為
`ReaderSpy.__call__() missing 1 required positional argument: 'path'`。

### GREEN

相同 focused command：

```text
Ran 3 tests in 0.015s
OK
```

reader-boundary seam 轉 GREEN，並斷言 callback path 與 receipt path 均為同一
`/synthetic/v1/records/item-1`。

完整要求的離線回歸：

```text
<main-workspace>/.venv/bin/python -m unittest \
  tests.test_tskg_src01 tests.test_tskg_slc01 -v
Ran 39 tests in 1.939s
OK
```

計數：`17` SRC + `22` SLC = `39/39`。

編譯：

```text
<main-workspace>/.venv/bin/python -m py_compile \
  app/tskg/source_policy.py tests/test_tskg_src01.py
exit 0
```

## Reviewer-equivalent probes

以 `<temporary-path>` 離線 harness 重建 review evidence 的 12 類 mandatory probes：

```text
MATRIX 51/51
EXPLOIT F-01_public_approval: BLOCKED
EXPLOIT F-02_top_level_duplicate: BLOCKED
EXPLOIT F-02_nested_duplicate: BLOCKED
EXPLOITS 3/3 BLOCKED
DENIED_READER_CALLS 0 across 10 denied requests
```

51 cases 覆蓋 public approval、decision/review/expiry/timezone、closed/duplicate/type/
numeric、traversal/prefix/encoding/Unicode/backslash/absolute URL、method/media/rate/
wildcard、governance、blocked/expired/unknown/invalid、reader exception、checksum 與
receipt binding。probe script 位於 temporary path，未加入 candidate。

## Verification gates

- Exact changed-file allowlist：只允許 repair card 列出的 code、test、repair evidence、
  原 verification 與兩張 task card。
- Prohibited/network/dependency/production/host-path scan：零匹配。
- Review evidence diff：零變更。
- `git diff --check`：PASS。
- Post-commit worktree：clean。

## Remaining blockers

- OQ-SRC-01 未解除，沒有 public source `APPROVED`。
- SLC-02 仍 blocked；本 repair 沒有建立 ingestion、RawArtifact、claim、Evidence、
  relationship 或任何 external I/O。
- 此 evidence 只交付 successor candidate，不宣稱 findings resolved、Review GO、
  accepted 或 integrated。

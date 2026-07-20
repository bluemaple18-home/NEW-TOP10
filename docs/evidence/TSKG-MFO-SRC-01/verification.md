---
card_id: TSKG-MFO-SRC-01
status: DELIVERED_CANDIDATE
verified_on: 2026-07-20
verification_kind: source_trace_gate
decision: KEEP_BLOCKED
---

# TSKG-MFO-SRC-01 verification

## 1. Fixed source and workspace

| Check | Evidence | Result |
|---|---|---|
| repo | `<repo-root>` worktree for `codex/tskg-mfo-src-01` | PASS |
| fixed base | `a938dc1cc7a2545d2587a78647a14bcbd8bc9a6a` | PASS |
| card commit | `df3f5ec` | PASS |
| operation level | official public web `read_only` only | PASS |

## 2. External-operation scope

- External writes：0。
- 登入、註冊、OAuth、購買、表單提交：0。
- Data endpoint／response URL calls：0。
- `swagger.json`、CSV、JSON、XLS、TEXT、PDF 或附件下載：0。
- 公司／日期參數查詢：0。
- crawler、Playwright、rate/load test、自動重試：0。
- Runtime／code／config／registry／fixture／test 變更：0。

## 3. Source trace gate

| Metric | Result |
|---|---:|
| Retrieved official pages | 10 |
| Of which readable substantive text | 9 |
| Retrieved landing/index with limited body | 1 |
| Failed robots opens | 2 |
| Failed URLs used for substantive claims | 0 |
| Data endpoints opened | 0 |
| Non-official conclusion sources | 0 |

兩個 robots URL 均回工具 `Internal Error`；依停損與研究契約直接記為 `NOT_FOUND`，未重試、未推論 allow/disallow。OpenAPI landing 可達且官方索引可辨識，但直接 parser 無正文，因此只標 `retrieved_limited`，不拿來證明 `T86` target operation 存在或不存在。

完整 URL／status／用途位於 `docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md` §4。

## 4. Required-field gate

| Required item | Dossier locator | Result |
|---|---|---|
| identity／publisher／contact | §3、§5 | COVERED_WITH_CHANNEL_SCOPE |
| dataset／distribution media | §3、§5 | COVERED_WITHOUT_APPROVED_MACHINE_CHANNEL |
| terms／license／attribution | §5、§6 | COVERED_WITH_SCOPE_CONFLICT |
| programmatic permission vs docs existence | §5、§6.1–§6.3 | COVERED |
| target path／method／version | §5、§6.1–§6.2 | GAP_RECORDED |
| auth／robots | §5 | GAP_RECORDED |
| rate／concurrency／retry／UA | §5、§8 | GAP_RECORDED |
| update／business date／correction | §5、§8 | PARTIAL_AND_GAP_RECORDED |
| retention／redaction／deletion／legal hold | §5、§8 | GAP_RECORDED |
| redistribution／derivative／commercial | §5、§6.3–§6.4 | COVERED_WITH_SCOPE_CONFLICT |
| policy version／review／expiry | §5、§8 | GAP_RECORDED |
| scope separation | §3、§6、§7 | COVERED |
| decision／blockers／next card | §7–§9 | COVERED |

所有缺口均 fail closed，未用常識、endpoint 行為、search snippet 或其他 dataset 補猜。

## 5. Decision verification

| Channel | Decision | Consistency check |
|---|---|---|
| `interactive_report` | `KEEP_BLOCKED` | PASS：公開可讀不等於 automation 授權 |
| `official_openapi` | `KEEP_BLOCKED` | PASS：target operation 與完整 operational contract 未取得 |
| `government_open_data` | `NOT_APPLICABLE` | PASS：本次未找到已上架 target；建議頁不是 dataset |
| `paid_file_product` | `KEEP_BLOCKED` | PASS：需另行訂購／簽核且下游用途受限 |
| overall | `KEEP_BLOCKED` | PASS：target 存在，但沒有已核准的 TSKG machine distribution |

- Executable `APPROVED` SourcePolicy：未產生。
- Registry／fixture：未修改。
- OQ-SRC-01／SLC-02／MFO 後續卡：未解除。
- RawArtifact／Evidence／RelationshipClaim／真實 `SecurityFlowObservation`：未建立。

## 6. Local verification contract

交付前執行：

```bash
git diff --check
git diff --name-only
rg -n '/(Users|private)/|file:/[/]' docs/tasks/2026-07-20_TSKG-MFO-SRC-01_twse_institutional_flow_source.md docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md docs/evidence/TSKG-MFO-SRC-01/verification.md
rg -n 'KEEP_BLOCKED|NOT_APPLICABLE|RECOMMEND_APPROVAL_REVIEW|APPROVED|SLC-02' docs/tasks/2026-07-20_TSKG-MFO-SRC-01_twse_institutional_flow_source.md docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md docs/evidence/TSKG-MFO-SRC-01/verification.md
```

Exact changed-file allowlist：

```text
docs/evidence/TSKG-MFO-SRC-01/verification.md
docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md
docs/tasks/2026-07-20_TSKG-MFO-SRC-01_twse_institutional_flow_source.md
```

本卡為唯讀研究文件；TDD 不適用。候選交付必須通過 exact allowlist、host-specific path scan、`git diff --check`、candidate commit 與 post-commit clean。

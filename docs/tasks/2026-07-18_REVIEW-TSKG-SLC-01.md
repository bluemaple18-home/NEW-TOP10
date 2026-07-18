---
card_id: REVIEW-TSKG-SLC-01
chain_id: TSKG-SLC-01
status: REVIEW_GO
type: review
owner: Codex 主線
assignee: 獨立 Reviewer
thickness: standard
risk: medium
model: gpt-5.5
reasoning: high
model_reason: 10 檔 identity/API/test candidate，需獨立 correctness、regression、security 與 test-gap 審查
base_sha: f1ece54bd8d072da70265a4c8ea5ab6f8b4d1210
candidate_sha: 7e8006be813be627317a1087744615dafb547a81
reviewed_commit: 7e8006be813be627317a1087744615dafb547a81
source_kind: commit
evidence_path: docs/evidence/REVIEW-TSKG-SLC-01/
---

# REVIEW-TSKG-SLC-01

任務：獨立審查 SLC-01 candidate 是否滿足實作卡與 TSKG v1.1，不修改 candidate。
範圍：`f1ece54..7e8006b` 的 10 個 allowlist 檔案；Spec axis 與 Standards axis 分開。
禁區：不得修改 `app/tskg`、fixture、tests、原卡或既有 runtime；不得連外或安裝依賴。
驗證：實際讀 diff、用既有 `<repo-root>/.venv` 重跑 tests/compile，核對 production isolation、allowlist 與 `git diff --check`。
證據：`docs/evidence/REVIEW-TSKG-SLC-01/review.md`；verdict `GO` 或 `NO_GO`。

## Allowlist

- `docs/evidence/REVIEW-TSKG-SLC-01/review.md`
- 本卡 status／Result。

## 必查風險

1. Fixture loader 是否對 duplicate entity ID、issuer dangling reference、非法 type/market/code/alias、schema/version 與 input order fail loud。
2. Alias normalization／collision 是否真的 deterministic，且不會因 duplicate alias 或 dictionary overwrite 靜默選錯 entity。
3. Security resolve 是否正確處理前導零、market normalization、invalid code、同 code 跨 market 與 valid interval。
4. Company service 是否只沿 `issuer_id`，所有 relation sections 是否各自獨立且不共享 mutable object。
5. FastAPI 400/404/409 error envelope 與 response 是否符合卡片；request_id 注入是否安全、沒有全域 side effect。
6. Import `app.api.main` 與 OpenAPI isolation test 是否真的證明未掛 production route，而非測錯 app instance。
7. Deterministic checksum 是否穩定且沒有忽略會改變語意的欄位。
8. Prohibited trading fields scan 是否避免 substring／巢狀漏檢或 false confidence。
9. `data/*` force-add、JSON fixture、路徑處理是否可跨 worktree／跨機重現，shared docs 無硬編本機絕對路徑。
10. 驗證工具鏈 caveat：原卡 `uv --with-requirements` 未通過，direct Python 3.11 是否足以接受，或需 P1/P2 修復卡。

## Reviewer output

- Findings 依 P0→P3，必須含 severity/category/path/line/evidence/risk/suggested_fix/validation_gap/confidence。
- 沒有阻塞問題時明確寫未發現 P0/P1；P2/P3 與工具鏈 caveat另列。
- 只可回報 `REVIEW_GO` 或 `REVIEW_NO_GO`、完整 review commit、reviewed candidate、tests、evidence。
- 不得宣稱 candidate 已整合或修改 candidate。

## Result

- Initial review：`REVIEW_NO_GO`；review commit
  `040f3806ecdcea9e7580f2586b9850312d48862a`，reviewed candidate
  `7e8006be813be627317a1087744615dafb547a81`。
- Re-review Round 1：`REVIEW_GO`；reviewed successor
  `fbd8fa09ce570971b2ecbf6b18a92c47c42a8f5b`，parent Repair card commit
  `895f4275c4c49a45db7f27cbae0330074ff85303`。
- Finding dispositions：F-01、F-02、F-03、F-04 全部 `RESOLVED`；未發現新的
  P0/P1/P2/P3 finding。
- Axis：Spec `GO`；Standards `GO`。
- Validation：22 tests 全通過、`py_compile` PASS、parent/original-candidate range
  `git diff --check` PASS、8-file Repair allowlist PASS、host-specific absolute-path
  scan 無匹配；原 reviewer malformed/expired/compound-key probes 全通過。
- Toolchain caveat：原 `uv --with-requirements` 仍未記為通過；依本輪明確指示，
  既有 Python 3.11 direct local-only verification 足以接受 successor behavior。
- Evidence：`docs/evidence/REVIEW-TSKG-SLC-01/review.md` 的
  `Re-review Round 1`；reviewer 未修改 candidate/runtime，也未宣稱整合。
- Round 1 review artifact commit：完整 SHA 由 reviewer 最終回報提供，避免 commit
  自參照。

# Storage guard integration repair 1: proposal authority

## 範圍

- Base candidate：`b381b06c1dcb5d4f407f6372e08b7577ca6f9475`
- Finding：storage guard 整合後，兩個受保護 scheduler plist 的已提交內容改變；既有 shadow proposal 的 scheduler snapshot、semantic hash 與 replay admission constants 因此不再具 authoritative parity。
- 修復：由既有 fail-closed builder 以目前已提交的 protected surfaces 重建 canonical proposal 與 verification evidence；同步更新 replay 的 committed proposal-set／semantic-hash fixtures，並新增 committed-evidence exact-recompute regression。

## 不變邊界

- 未變更 storage guard、scheduler plist、proposal builder/verifier、authority checks 或 protected surfaces 清單。
- 未放寬 hash、未將 plist 移出 protected surfaces。
- 未執行 launchd、live workload、FOG、reclaim、send、push 或 deploy。

## 身分結果

- proposal set：`sha256:1a1867a6097a92264c75f094c11e7248fdcd99900bd4b3d66d9642b699ac565a`
- semantic hash：`sha256:a6f1ba6711cf8a3b0ea32c1075781ac916b4140b82ee66fc6bd701a94b484d96`
- proposal ID：`sha256:6cf375eba0a52aa95f41ed807d346ed96999cd9636848b063515ebdbe55b4101`（研究提案語意未變）
- pm harness plist：`sha256:b3e954a195e2862a10d8b99ddc6d571a143278cbe1de1e2849373e1b6ce0144c`
- fog worker plist：`sha256:ece9072fe4c742f7744b6a219b2cdaa8eb830170a8a914e2651f16064eee87cb`

## 驗證

- RED：`uv run pytest tests/test_isolated_shadow_plan_replay.py::test_authoritative_proposal_admission_passes -q` → `PROPOSAL_VERIFICATION_FAILED`。
- Proposal regression：`uv run pytest tests/test_shadow_research_plan_proposal.py -q` → `15 passed`。
- Builder self-test：`uv run python scripts/verify_shadow_research_plan_proposal.py --self-test` → `PASS`，且二跑 bytes 相同。
- Storage focused suite：`uv run pytest tests/test_storage_safety.py tests/test_fog_storage_validation.py tests/test_daily_research_batch_owner_shell.py tests/test_scheduler_ownership.py tests/test_daily_workflow_v2.py -q` → `80 passed, 31 subtests passed`。
- `git diff --check` → PASS。
- Exact-HEAD admission GREEN 必須由主線將本 repair 的五個檔案建立為單一 commit 後執行；在未提交 worktree，預期會停於 `PROPOSAL_NOT_EXACT_HEAD_BLOB`，此為既有 authority gate，不是放寬目標。

未宣稱此 receipt 本身是 runtime activation 證據。

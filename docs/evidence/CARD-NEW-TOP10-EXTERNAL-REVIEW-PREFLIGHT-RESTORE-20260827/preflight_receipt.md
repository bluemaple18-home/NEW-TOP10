# 外部審查 Provider Preflight 收據

👉 [假設與目標確認] 目標：驗證 17:40 僅 probe 的 ChatGPT／Gemini 預檢能安全 fail-closed；邊界：不送 packet、不登入、不改 token、不啟用 LaunchAgent；驗收：保留 RED／GREEN、容量與安裝入口差異。

## Source decision

- CodeGraph CLI 不在目前 session 的可用 PATH，`GBRAIN_BIN` 亦為空；依卡片範圍以 bounded `rg` 限定檢視五個 allowlist entrypoint、其直接 host runner contract 與 targeted tests。
- Source `scripts/com.new-top10.external-review-preflight.plist` 已指定 `run_with_storage_guard.sh external-review-preflight`，時間為 17:40，且 `RunAtLoad=false`。

## RED

- 首次 guarded entry 返回 exit 69：`storage guard requires executable .venv/bin/python`。使用 offline `uv sync` 恢復本機忽略的 `.venv`，未納入候選 commit。
- 恢復環境後兩個 guarded representative cycles 都返回 exit 78，receipt 為 `NO-GO`；兩輪原因相同：`POLICY_NOT_LIVE_VERIFIED`、`SWAP_METRIC_UNAVAILABLE`。
- cycle 1 measure：free 47,278,481,408 bytes、scope 1,869 bytes / 3 files；cycle 2：free 47,278,452,736 bytes、scope 1,873 bytes / 3 files。兩輪 dry-run reclaim 均為 0 bytes / 0 files，沒有移除任何內容。
- 此 worktree 的 `SWAP_METRIC_UNAVAILABLE` 是 host telemetry boundary，不是程式修復失敗。主線必須在 canonical host 取得 escalation 後，完成兩輪 guarded provider probe 補驗，才能將該 runtime prerequisite 視為已滿足。
- guard 在 preflight fail-closed，未執行 child provider probe；因此沒有外部 review packet，也沒有任何 provider write。

## GREEN（程式契約）

- `preflight_external_review_providers.py` 會將每個 provider 的 adapter 結果正規化為 `PASS` 或 structured `BLOCKED`，保留 provider-specific blocker code、authority/runtime/session/readiness 分類與 probe evidence。
- receipt 明示 `mode=probe_only`、`review_packet_sent=false`；只有兩個 provider 都 PASS 才回傳 overall PASS。
- targeted tests 證明 probe command 在呼叫 adapter 前移除 `--date`、`--packet`，因此不可能由預檢送件。
- ChatGPT／Gemini probe adapter 支援 `TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT`：未設定時仍使用原本的 `<repo-root>/artifacts/external_review`；設定時只接受既有、canonical、絕對且非根目錄的 sandbox directory，拒絕不存在、symlink 或 traversal 路徑。這使 Seatbelt representative cycle 能把 probe evidence 收斂至 validation sandbox，而不改變正常排程預設。

## 安裝入口與最終判定

- 已安裝的 host-local `$HOME/Library/LaunchAgents/com.new-top10.external-review-preflight.plist` 為有效 plist，亦為 17:40、`RunAtLoad=false`，但 `ProgramArguments` 直接呼叫 host-local checkout 的 `scripts/run_external_review_provider_preflight.sh`，未走 storage guard，且與本 worktree source 不一致。
- 此卡未授權寫入／啟用 LaunchAgent；因此不修改 installed plist。
- Verdict：`NO-GO / BLOCKED`。排程不得啟用、`launch_verified` 必須維持 false。解除條件為：主線在 canonical host 取得 escalation 後完成兩個 guarded provider probe 補驗，並由主線授權將 installed LaunchAgent 更新為 source 的 guarded entrypoint。

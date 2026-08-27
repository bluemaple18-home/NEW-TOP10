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
- ChatGPT 的 provider adapter、preflight shell 與 host-runner shell 已統一為既有「台股波段推薦分析」project conversation marker；三處皆保留 `TOP10_CHATGPT_URL_PART` 明確覆寫，未包含帳號 email 或 token。
- 在受控 override 下，probe JS 以 script-level base64 常數經 `printf` stream 與 Python 寫入已驗證的 `$JS_FILE`；不讀取自身 script、也不執行 Bash heredoc。預設分支仍保留原始 heredoc 與 JS bytes。Gemini override 同步套用既有 title/account/plan placeholder substitution。
- 新增的內部 `--materialize-probe-js-test-only` 只接受受控 output root、只 materialize probe JS 並輸出 `mode=probe_only`／`review_packet_sent=false`，不啟動 Chrome 或送件。targeted test 實際呼叫兩個 adapter，證明 JS 僅寫入指定 root、source tree 與 `TMPDIR` snapshot 無新增檔、materialized bytes 與預設 probe template 相同，且 Gemini 的 title/account/plan substitutions 完整保留。
- 本輪驗證：`bash -n scripts/review_chatgpt_chrome.sh scripts/review_gemini_chrome.sh scripts/run_external_review_provider_preflight.sh scripts/run_external_review_host_runner.sh`、`.venv/bin/python -m unittest tests.test_external_review_provider_preflight`（14 tests）與 `git diff --check` 均通過。

## Provider、容量與 policy 判定

- account19 direct provider receipt（`…/artifacts/external_review/2026-08-27/provider_preflight_2026-08-27_account19-exact.json`）顯示 canonical ChatGPT project conversation 與 Gemini 皆 `PASS`；`mode=probe_only`、`review_packet_sent=false`。receipt 不含帳號 email、token 或 review 回覆內容。
- 兩份隔離 validation-only capacity receipt（`…/logs/storage_safety/external-review-preflight_cycle-1.json`、`cycle-2.json`）皆為 `OK`，`reasons=[]`、`unknown_changed_paths=[]`、swap delta=0、`final_process_group_quiescent=true`。cycle-1 為 4,554 bytes／4 files、cycle-2 為 4,554 bytes／3 files；兩輪 peak RSS 均為 3,997,696 bytes。
- 因此 `docs/operations/top10-storage-policy.json` 的 `external-review-preflight.launch_verified` 已提升為 `true`，verification basis 記錄上述最小必要證據與不送件契約。
- 本輪 policy 驗證：JSON parse、`StorageSafetyRegressionTest.test_policy_contract_is_complete_and_verified_jobs_have_evidence` 與 external-review preflight targeted suite 合計 15 tests 均通過，且 `git diff --check` 通過。完整 `tests.test_storage_safety` 曾出現既有環境型 subprocess／resource warning 與失敗，未作為本次 bounded policy promotion 的通過證據。
- 此 policy promotion 不會安裝、載入或啟用 LaunchAgent；已安裝入口的調整與啟用仍由主線另行驗收與授權。
- Verdict：`DELIVERED_CANDIDATE / POLICY_READY`。本卡只交付 provider 與容量證據、policy 更新與候選 commit；不宣稱排程已啟用。

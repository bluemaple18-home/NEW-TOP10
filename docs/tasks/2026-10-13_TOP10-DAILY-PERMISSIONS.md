# Daily 正式排程權限修復

- 目標：10/13 17:30 Daily 沿正式 storage guard 完成報告與既有 Discord 發送。
- 範圍：釐清並修復 bash 暫存及 OpenClaw 狀態寫入；保留容量隔離、發送 gates、Fog/provider/retrain。
- 驗收：同正式 confinement 重現 RED；修復後代表性正向與負向驗證；獨立 review；部署後 readback。自然排程成功須另有當次收據，不預先宣稱。
- 假說：production sandbox 排除必要寫入，故與 Codex bridge 無關；若正式 guard probe 重現即證實。另查 shell 暫存落點與 OpenClaw 官方唯讀接點。
- 狀態：已修復並正式切換 Daily；獨立 readback PASS。10/13 17:30 自然執行尚未發生，delivery acceptance 待該次實際收據。

## 實作派工

- 模型：chatgpt-web/gpt-5.6-sol high；理由：兩個 sender 的外部 API 接點與正式排程。
- 唯一 delivery writer：Web worker；目標隔離 checkout `/Volumes/VibeCode/Development/Codex-Worktrees/top10-daily-permissions/TOP10new`，base ec08e846db21a1601fa5e3995138e46015eaceb7。主線只寫本 task/control evidence。
- 實測 RED：原 runtime 正式 guard 下 bash heredoc EPERM；CLI dry-run 雖 exit 0，stderr 有 .openclaw/identity EPERM。讀 logs/storage_safety/daily.log 和 artifacts/daily_permissions_sender_probe_20261013.json。
- 已驗證 seam：本機 OpenClaw dist/plugin-sdk/gateway-runtime.js 公開 callGatewayFromCli，extra={clientName:'gateway-client', mode:'backend', deviceIdentity:null, scopes:['operator.read'], progress:false} 的 health 在正式 guard PASS。使用既有 token auth，不改 Gateway auth/policy。SDK path 從現有 notify.clawd_cli_entry 所在 dist 推導，不能 pin hash bundle。
- HTTP tools/invoke message 被既有 agent allowlist 拒絕，不放寬它。
- 注意：Gateway send 沒 dryRun；message.action handler 硬設 dryRun:false，絕不可把 action send 當 dry-run。dry-run 僅 local payload/SDK health/read 檢查，絕不送。
- 修復：publish shell Python heredoc 改 -c 或等效免 shell tmp 接點；兩個既有 sender 改走薄 SDK adapter，send/date/target/presentation gates 保留。正式發送使用官方 send RPC 或確認相容的 message.action；未知/不支援輸入 fail closed；不新增服務/ledger/queue，不放寬 storage sandbox，不複製 credentials/state，不改 Fog/provider/retrain/vendor。
- SDK timeout 有界，錯誤退出非零；同一次 transport request 不自動重送。發送回執需實際 message id，維持既有 status JSON 契約；secret 不出現在 argv/stdout/error。
- 測試：原 shell RED regression、sender stale/send gate、兩 sender args、SDK success/failure/timeout/invalid receipt、dry-run 絕不 RPC send、presentation 不可悄悄丟失；測試 fixture 不外送。不可改正式 artifacts 或啟動完整 ETL。
- 交付：直接改隔離 checkout；targeted tests、diff --check、修改路徑、風險。不得 commit/activation/live-send；由主線驗收。

## 驗收／部署控制

- 10:30 基線：Daily enabled、loaded/not running、runs=0；平日 17:30；ec08e84 source clean。其餘 plist SHA 保存 daily-permissions-baseline-20261013.json。
- 已追加實測：SDK message.action read 在相同 guard 成功讀取兩個既有頻道，ID 符合已發送的 10/12 訊息。只算 authenticated downstream read，不冒充 delivery acceptance。
- 先 fixture regression／sender contract，再兩名獨立 Web high Reviewer；不共享彼此 verdict。activation 程式沿既有已審版本，本輪不修改。
- 新候選 freeze 後使用同 repo detached linked runtime；保留舊 runtime 作回退。沿既有 scripts/activate_automation_runtime.py --job daily，嚴禁 kickstart 或補發 10/12。
- side effects／failure states：staging 前失敗 live 不動；bootout 後依 transaction rollback；replace 後 bootstrap 失敗還原舊 plist/loaded/enabled state；receipt 寫入失敗保留原錯誤及獨立回讀；activation 成功後 root/config/dependencies/denial/非目標plist 校驗。自然 17:30 尚未執行不得報 delivery PASS。
- runtime 資料沿 10/12 成功 baseline 複製 data/models/artifacts；不複製 logs/lock/denial；依賴可唯讀重用旧 runtime .venv，不升版。copy 前計算每卷 budget，Rule24 preflight 及代表性 transport 周期要 PASS。
- 直接取代範圍：Daily 兩個 sender 的 local message CLI 呼叫 → 官方 Gateway SDK 單次呼叫；原日期/開關/狀態驗證保留。舊 runtime 保留作回退且仍服務其他 job，不屬本次刪除範圍；不建自動清理排程。
- 已通過真實負向 capability：原 guard 中，SDK send 和 message.action 的空參數皆在 schema/dispatch 前被拒絕；未包含目標或訊息，未進行發送。

## 獨立審查卡（候選已完成，尚未 commit）

- checkout：上述 isolated delivery root，base ec08e846；scope 僅 git diff 與新增 openclaw_gateway_adapter.mjs、openclaw_gateway_sender.py、test_openclaw_gateway_sender.py。未改 activation/storage guard/vendor/config。
- Worker reported：25 passed + 5 subtests；bash -n、diff --check PASS。worker 自己 health 因其 Web execution network 1006；主線 host-native official guard health/read/schema-negative 均 PASS。不要把任一方聲稱直接當最終 verdict。
- Reviewer 必須獨立跑相關 tests，先 CodeGraph，再針對 diff/source。使用 runtime 絕對 python；不可 live send、ETL、activation、改 code、讀另一 reviewer verdict。回報 GO/NO-GO、P0/P1具體觸發/證據、剩餘非阻塞風險與實際執行命令。
- 核對：兩 sender gates、SDK auth/state writes、dry-run無任何send RPC、receipt truth、timeout不自動retry、presentation、source frozen/runtime/rollback/非目標plist。不新增需求；自然17:30未驗證須精確揭露。
- 部署沿既有 activation transaction；可獨立跑 tests/test_activate_automation_runtime.py 相關 suite（先確認實際檔名）。請從 trap/handler 描述 stage/bootout/replace/bootstrap/receipt failure rollback，不僅看 fixed diff。

## Repair 1（兩名 reviewer 已完成 v1，現開放限定寫入）

- 主線已確認兩個契約反例：unknown vendor sentinel 可被 sender/verifier接受為actual ID；同名 clawd-send-status.v1 舊回執 stdout 中有效 ID 不被新 verifier 接受。各 reviewer verdict 分別保存，不互相傳閱。
- 主線已重現：目前 10/12 真實成功回執被新版 verifier 判 missing receipt.message_id；extract_message_id({messageId:'unknown'})='unknown'，bool=True也被轉為ID。
- 限定修復：共用一致的有效 ID 判斷（排除 sentinel、空白、bool、錯型），sender與verifier都使用；舊 v1 僅在原成功旗標且已知 stdout JSON receipt shape 有有效actual ID 時dual-read。新版receipt已存在卻invalid不得偷fallback到別處。拒絕invalid/unknown/失敗回覆，保留date/send/dryrun gates，不改auth/adapter傳輸/activation。
- 不以修改歷史receipt掩蓋相容性。legacy stdout可參照原runtime artifacts/clawd_send_status_2026-10-12.json，唯讀且不得把訊息內容/secret寫進tests。
- 必要回歸：新valid、new sentinel/blank/bool、nested failed payload、legacy實際stdout形狀valid、legacy invalid JSON/無ID/unknown、dryrun/failed不可當live success；現有tests及diff check。
- 本輪只允許第1代repair；交付後原兩名reviewer只複驗原findings及回歸。
- 兩名獨立 verdict 皆為 NO-GO，僅上述兩個 P1；各自 activation suite 103 PASS。修復規格已固定，route=chatgpt-web/gpt-5.6-sol medium，fork_context=false。

## 凍結與維運驗證

- Repair1 後原兩名 reviewer GO/GO；candidate 8c864ce706e841df93ca4c820c21f2a468f19c43。
- 新 frozen runtime `/Users/mattkuo/TOP10-runtime-automation-8c864ce` 已 RUNTIME_CHECKOUT_GO；.venv 為真正目錄的 CoW clone，data/models 24檔hash匹配。
- 最後一次 standalone dryrun 探針輸入有誤：複製的10/12 payload保存舊message絕對路徑，--date選新message路徑被正確拒絕；child太快退出，guard產生 MISSING_VALID_LIVE_RESOURCE_SAMPLE。未 activation，old Daily仍enabled/loaded。
- 原失敗 invocation=daily-20261013T030424Z-51134。newroot marker禁止常駐/guard自動clear；本次依Owner『有問題就直接修好』的Daily修復授權進行一次性明確維運，沒有新增自動clear能力。
- 恢復前置：保存marker/latest/receipt及sha；原因必須僅為上述probe，unknown/unmetered writes空、process group quiescent；新root fresh Rule24 PASS；修正輸入的純唯讀 preflight PASS。final source兩次代表性transport/wrapper cycles已有OK receipts，恢復後在新root再跑兩次完整相同probe。
- 僅持有newroot daily.lock時解除本輪probe-owned marker；不得清任何其他marker或改歷史payload，保留失敗證據。由既有reviewer核對此維運恢復方案；正式activation依既有transaction。

## 完成結果

- 新root兩輪完整permission representative cycle PASS/PASS：031057Z-54039、031138Z-54767；temp cleaned、process groups quiescent、無active denial；沒有live-send。
- Daily-only activation成功；交易狀態 ACTIVATED_PARTIAL_ACCEPTANCE_PENDING 表示自然週期尚待驗收。
- 獨立 readback：loaded/enabled/not running、runs=0、平日17:30、runtime 8c864ce、source clean；其餘TOP10 plist hash全未變。
- 最終收據：docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/daily-permissions-final-readback-8c864ce-20261013.json。
- 今日自然17:30未執行前不宣稱全鏈路送達，原runtime保留供回退。

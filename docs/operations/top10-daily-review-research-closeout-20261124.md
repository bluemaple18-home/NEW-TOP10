# 每日報牌、外部 review、研究接收：2026-11-24 收尾
狀態：本次有人在場的送收與研究交付完成；剩餘程式的本機版本整合以本文件所在 Git 提交及 final-integration-receipt.json 為準。正式 runtime 未部署，無人 review 排程未恢復，未 push。

## 流程與已觀測結果
| 節點 | 本次結果 | 證據／入口 |
|---|---|---|
| 每日報牌 → Discord | 11/24 已送達；message ID 1574723004066168833；本輪未重跑 | daily-discord-delivery-20261124-02/validation_evidence/daily-completion-receipt.json |
| 固定 packet → GPT／Gemini | 使用 Owner 指定 11/23 packet；兩方均經原檢查接受，summary valid_provider_count=2 | review-json-format-conversion-20261124-03/validation_evidence/ |
| Gemini 格式更正 | 僅十檔 cites_input_attr 改單一 rank=N；其餘 JSON 值與分析文字完全相同 | correction-comparison.json |
| review → 研究輸入 | accepted summary 與原件以資料參照放入 artifacts/external_review/2026-11-23/，payload 仍在外接封存 | RESEARCH-INPUT-PUBLISH-20261124.json |
| 研究 consumer 接收 | 原 run_autonomous_research.external_review_signals 實際讀回該來源；收到7個假說與5類訊號 | top10-review-research-receive-20261124-02/validation_evidence/research-receipt.json |
| 研究交接摘要 | 原 build_research_decision_brief.py 產生1份待複核摘要，已連到 artifacts/research_decisions/ | research_decision_brief_2026-11-23.json／.md |

11/24 daily 與 11/23 固定 packet 是 Owner 分別指定的驗收日期，不把它們說成同日全自動執行。
研究端接收已完成；研究實驗、排隊執行、改排名、訓練或模型升級均沒有在本輪啟動。

## 往後的操作邊界
1. 每日報牌維持原守護入口與 Discord 回執，禁止因 review 失敗重送 daily。
2. review 使用既有外接生命周期及明確 output root；先確認 GPT「家維」與 Gemini「17 一年 (留痕)／bluemaple17@gmail.com／Gemini PROD」。
3. Chrome 每條新 MCP 連線仍需有人允許。同一 provider 的檢查、輸入、送出與收件沿同一原 adapter session；這不是無人排程。
4. 沿 run_external_review_host_runner.py 的原入口送收；本次驗收使用 --skip-ops-report --skip-fog-map-handoff --skip-research-quota，避免意外啟動另一條研究／地圖流程。
5. 已送出但結果未知時，只沿 external_review_mcp_adapter.py collect 核對原 marker，不重跑整輪 send。
6. 兩方原 normalizer／contract／summary 接受後，再交研究端讀取並產生研究摘要。研究意見保持 research_only，不能直接改排名或推播。
7. 本次整合只到主工作區；正式 runtime 的部署及任何排程啟用，仍須另走既有部署／容量／canary 閘門，不能從本次 one-shot 推導為已放行。

### 明示帳號 binding（含 probe）

兩方都必須在原 lifecycle 的操作環境明示 `TOP10_CHATGPT_EXPECTED_ACCOUNT`／`TOP10_GEMINI_EXPECTED_ACCOUNT`，不得依正文或 Chrome profile 名推定。依本輪 `pending-integration-20261124/account-ui-observation.json` 的唯讀觀測，可明示：

```bash
export TOP10_CHATGPT_EXPECTED_ACCOUNT='家維 郭 Plus'
export TOP10_GEMINI_EXPECTED_ACCOUNT='bluemaple17@gmail.com'
export TOP10_CHATGPT_EXPECTED_TITLE='台股波段推薦分析'
export TOP10_GEMINI_EXPECTED_TITLE='TOP10 External Review - Gemini PROD - Google Gemini'
```

`EXPECTED_TITLE` 是可選的完整 RootWebArea exact 值，保留所有字元；不得沿用舊 substring（例如 `Gemini PROD`）。若現場 title 改變，先唯讀確認並更新 operator 明示值，不弱化程式比對。

GPT 只讀同名 profile menu 的 direct identity menuitem 完整 label；自行開啟後以 Escape 關閉並重驗 canonical conversation URL。完整顯示名＋plan 無法區分同名同方案帳號；此限制不代表已綁定 email，不會導向 settings。Gemini 只接受 accounts.google.com 的 `/SignOutOptions` 帳戶 link accessible name 中完整且唯一的 email。缺少、多重或不符身分都在輸入／送出前停止，probe 亦同。可選的 `EXPECTED_TITLE` 僅核唯一 RootWebArea 的完整標題；`EXPECTED_PLAN` 若設定只核 authenticated identity 區，不得拿正文充當身分證據。上述值是本輪 operator 明示範例，不是程式預設值。

## 程式與測試
本批將剩餘程式、測試、操作文件一併納入本機版本，包括外接 cache、storage validation、FOG 路徑、daily delivery 狀態、既有 MCP adapter 與 runtime checkout。原四項 P1 及驗證中重現的 signal mask 問題已修復；兩份獨立複核、最終 hash 與提交 SHA 記於 final-integration-receipt.json。

受影響的50份 Python 套件分組執行，避免混淆 CLI 的真 cache 環境與單元 fixture：
- activation 117項、API 5項、provider preflight 14項、wrapper 7項、regression harness 6項通過。
- storage 純函式22項、一般回歸90項，以及六個 exact-owner 原生隔離案例實跑通過；原生案例各自使用既有 lifecycle 的 active owned root。
- Node 44項及六份 shell 測試通過，lifecycle parent 正常結束。
- 其餘44份套件的逐項結果見原回執。先前明列未驗的十項原生案例，已於2026-11-25從 host controller 同批實跑10 PASS（54.57秒），controller exit0。涵蓋外接 cache confinement1、source-write probe1、FOG shared-helper4、daily lifecycle cleanup4；與前述六項 validation 原生案例分列，不混算。

A6 歷史研究重建 fixture 明示既有基準 bb617e98 → 6f6796c，另以25348435的真實排程變更驗拒；該歷史回歸與當前交付的版本驗收各有實際 Git 範圍。歷史 closure receipt 原件保留；tests/fixtures/research_spine_a6/closure_receipt.json 僅補目前來源掃描新增的兩個已映射 reader，其他驗收值不變。

單元測試中的 CLI、環境回復、tmpfile、停損與 cleanup 接點明示範圍；真 child／sitecustomize 與原斷言仍保留。測試結束還原 process-global tempfile cache，避免指向已回收 fixture。原 symlink 上限8未調高；regression harness 在案例結束才回收已通過的 fixture，失敗證據保留。

117項 activation 另於 fresh CLI 驗真 process signal；既存未遮罩 native thread 的 library 呼叫仍有邊界，不推論為所有 embedding 場景都已驗。GPT 新帳號 guard 真 probe 通過；Gemini 新 guard 僅有唯讀身分觀測與錄製 UI 的回歸，真 probe 未完成，不冒稱新版雙方 live 驗收。先前固定 packet 的兩方真送收結果維持有效，本輪未重送。

重現入口分兩層：一般套件仍由 scripts/run_daily_regression.py 與既有 tmp_artifact_lifecycle run --external-only 執行；legacy unit 組 unset PYTHONPATH、使用 validation-libproc，CLI 組保留 parent cache 環境。原生十項從未受限 host 協調，先以原 ManagedCache 真實取樣准入及持續停損，再以原 lifecycle.run_child 管理 controller 程序群；原生權限 probe 首次套用原 profile，FOG 真 payload 由原 lifecycle run --external-only --owned-root-writes-only 啟動，daily 真 payload 保持原 run --external-only。controller 不偽造 active 身分，不將 payload 改成 raw shell，不以外層寬鬆 profile 略過隔離。

FOG 外層 Python 保留 Core 的 temp hook；進入實際 owned root 後才清除 legacy CLI 不接受的 cache 欄位，parent 的 admission、nonce、卷身分與鎖仍由原契約驗證。FOG helper 原有的固定 immutable bootstrap 與拒寫檢查保持不變。FOG 四案分別驗到0/OK、17/CHILD_FAILED、70/HARD_RUNTIME_EXCEEDED、70/GuardInterrupted，source完整指紋不變、process group收束、root與marker清理均通過。daily 四案為0、0、1、143，訊號案確認已進入真 runner 才送SIGTERM，四案root與marker皆已清理。這些是合成小型驗收，不會送Discord或啟動真研究。

實際 native host 指令、JUnit、stdout、容量前後取樣與各案原生收據見 native-10-acceptance-20261125/ 及 top10-native-10-host-all-20261125-01/。重跑需從未受限host執行同一原生選集並換全新外接 evidence 目的地；原 controller fixture、失敗紀錄與證據保留，不刪未知 root。十項原生缺證已補齊；正式部署、排程與正式資料試跑仍維持原獨立 gate。

## 檔案如何收尾
詳見 ../evidence/ARCHIVE-20261124.md。
624份歷史未追蹤證據，197546124 bytes、610362行，已外接封存並逐檔驗證SHA-256。原工作檔未刪。
使用Git原生本機info/exclude只排除manifest中的精確歷史路徑，讓它們不再混入整合差異；app/、scripts/、tests/的其他未提交修改沒有被忽略。
主工作區保留必要程式／測試、操作文件、封存索引與任務卡，以精確檔案清單提交本機 Git。歷史原件、另一份 working tree 的差異與回復備份保留；未 reset、clean、push 或部署。

## 證據位置
本文件中的 evidence 目錄名均相對於：
<external-checks>/TOP10-STORAGE-LIFECYCLE-20261118/evidence/。
完整結案收據與CC回報：
<external-checks>/EXTERNAL-REVIEW-PATH-RESTORE-20261124/formal-review/CODEX-END-TO-END-CLOSEOUT-TO-CC-20261124.md。

## 版本整合回執
<external-checks>/EXTERNAL-REVIEW-PATH-RESTORE-20261124/formal-review/pending-integration-20261124/final-integration-receipt.json。
本機提交後的 CC 回報：同 formal-review/CODEX-VERSION-INTEGRATION-TO-CC-20261125.md。歷史結案卡只代表當時送收／搬檔狀態，以本次版本回執補足未提交的缺口。

## 十項原生驗收補齊
補驗與後續本機提交回執：<external-checks>/EXTERNAL-REVIEW-PATH-RESTORE-20261124/formal-review/native-10-acceptance-20261125/final-receipt.json。
補驗CC回報：同 formal-review/CODEX-NATIVE-10-COMPLETE-TO-CC-20261125.md。先前回報中的十項「未驗」屬歷史狀態，以本次逐案證據補正；未部署runtime或恢復排程。

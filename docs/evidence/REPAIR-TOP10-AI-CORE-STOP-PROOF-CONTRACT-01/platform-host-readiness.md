# 平台唯讀評估：TOP10 主機與接入需求

> 2026-09-27 容量整理：本目錄原始輸出與重現腳本已逐檔 SHA-256 核對後合併為 [證據壓縮包](raw-evidence-2026-09-27.tar.gz)。文中原始檔名為包內路徑；需重跑時先在本目錄執行 `tar -xzf raw-evidence-2026-09-27.tar.gz`，再依原說明操作。歷史驗證結果不變。

日期：2026-09-22。範圍：Owner 最新「繼續啊。不然在幹嘛」准入唯一剩餘的平台唯讀評估；不包含事件監聽、產品原型、權限變更或 Daily 試跑。ai-core 負責官方平台能力比較；本文件負責已存在主機工具與 TOP10 契約適配，不另建管理系統。

## 本機實際觀測

| 查詢 | 結果 | 可以／不能證明 |
|---|---|---|
| `sw_vers` | macOS 26.6.2，build 25G83 | 當下主機版本；不由版本推論 ES client 可啟動 |
| `id -u` | 501 | 目前查核 shell 並非 root；不是 sudo 授權盤點 |
| `ls -l /usr/bin/eslogger /usr/sbin/dtrace` | 兩個系統執行檔存在；eslogger 1,180,224 bytes | 已有工具，不需下載；未執行或採集事件 |
| `xcrun --show-sdk-path` | `/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk` | SDK 可讀，未編譯／建立 client |
| `codesign -dv --verbose=2 /usr/bin/eslogger` | identifier=`com.apple.eslogger`、Platform identifier=26 | 簽署中繼資料，不是當前 caller 的 root／FDA／ES admission |
| `codesign -d --entitlements :- /usr/bin/eslogger` | 工具回報 deprecated path syntax 及 invalid entitlements blob 警告 | 無法以此判定有效 ES entitlement 存在或缺失；本項 UNKNOWN，沒有透過啟動 client 探測 |

目前 responsible process 的 FDA 與 native ES client entitlement／啟動能力均未測；沒有讀取 TCC 資料庫、發起權限提示、sudo 啟動監聽或執行 `eslogger --list-events`。不能把讀到 SDK／系統執行檔當成當前可接入。

本機來源 digest：`/usr/share/man/man1/eslogger.1` SHA-256=`b0378cec2f92ea0093a9ca7d42b0bd27ad9469018dd40c2c541eb97eebd72f3d`；`/usr/bin/eslogger` SHA-256=`ebff5608a2840a8b0b3ee2e4bbc9afaa1034171729c5e78c72ec63b0c7e1fcd1`。

## 現成 eslogger 的限制

依本機 Apple 原始 man page `/usr/share/man/man1/eslogger.1`：

- 第 19～27 行：工具連接 ES 並輸出事件；要求 super-user 及 responsible process 的 FDA，且會抑制與工具同 process group 的程序事件。
- 第 29～45 行：不是應用程式 API，沒有與原生 ES 相同的功能／效能／schema 保證，不能把其輸出結構或資訊當成穩定接口。
- EVENTS：支援 notify events，不支援 auth events。
- FORMATS：JSON Lines／JSON 模型近似 `es_message_t`，附 schema version；沒有正式穩定 schema。
- TCC AUTHORIZATION：從 app、SSH、launch daemon 執行時，responsible process／授權對象不同。這不是安裝一個檔案就能解決的依賴。

因此本案不把 eslogger stdout parser 直接准入為 production cleanup certificate 來源。它至多是後續另行授權的診斷候選；尚未驗 schema、初始化完成訊號、同 group 事件抑制、退出時 drain、事件缺失與 observer 故障時的 fail closed。這不是宣稱 eslogger 無用，也不是要求自建常駐服務。

## A1–A8 對平台接入的最低要求

| 原契約 | 平台來源仍須證明的事 | 不能替代它的訊號 |
|---|---|---|
| A1／A4 正常 nested、短命 parent、另 SID | 放行前已具有效觀測，fork/spawn/exec/exit 能以本輪不可混淆的 identity 關聯；正確處理 exec 的 pidversion 轉換；全部 owned identities 的生命週期閉合 | 首 child ACK、PGID 消失、程序 exit 0、固定 audit token 不變、API 有 fork event |
| A2 交接／死亡競態 | observer ready 與 bootstrap release 順序可驗；outer／guard 任一死亡或觀測斷裂後不產生完整證明 | 監聽程序已存在或 stdout 有第一筆 JSON |
| A3 signal／TTL／容量 | 後代異步通知與實際停止可交叉核驗；不能漏掉延遲／忽略 TERM 者；監聽與證據本身具容量及停止上限 | 已送出 signal、固定 grace 到期、沒有新事件 |
| A5 錯 identity／遺失 | PID reuse、事件序號 gap、mute/filter、起始與末尾窗口、query error 都有拒絕行為 | 單獨 PID、只在中段未見 gap、empty snapshot |
| A6 匯出／清理錯誤 | 原始事件／停止證據成功匯出，再刪 exact root；observer 死亡不得誤判為全部 exit | pipe EOF、監聽 exit 0、close kqueue 的例外 |
| A7 無關程序 | 只對本輪核驗 identities 操作；跨程序觀測不是跨程序 kill 權限 | 全機事件清單或 root 權限本身 |
| A8 legacy／opt-in／准入 | 明示作用範圍與版本；不繞過既有 resource gate、不更改 default 的已知風險聲明 | 單次原型或 SDK 範例成功 |

本矩陣是既有卡的接入條件整理，不新增防惡意威脅模型或驗收級別。沒有產品原型／配對候選，不能標為 SAFE_FOR_TOP10_ISOLATED_VALIDATION。

補核的本機官方 SDK：`EndpointSecurity/ESMessage.h:230–242` 說明 exec 前後同 PID 的 pidversion／audit token 會改變；`ESClient.h:630–659` 說明 client entitlement／FDA、serial handler 與預設 muting；`ESMessage.h:2678,2687` 的 seq_num／global_seq_num 有 message version 條件。這些能支持候選設計要求，仍非已完成本輪根程序→所有後代→終端 drain 的證據。

## 本輪檢查方式

只執行上表唯讀命令與精確 man／SDK 範圍讀取。ai-core 原 evidence 目錄的 `platform-readonly-assessment.md` 已交回，本次核對 SHA-256：`83bc35badf4757062f2bfd6f0e953107a5c650c5898f379544d43f5590e8768a`。唯一卡已記錄平台研究完成、沒有可直接採用的自動清理來源，以及兩段最小原型候選：離線事件歸約／失效規則，之後才是具備必要權限的單次合成原生 ES fixture。

候選可採按需應用程式形態，不需預設常駐 daemon 或 system extension；但原生 ES 所需 entitlement、簽署、root、FDA 及終端事件完整性尚未驗證。此結論不解除原安全阻擋，也不將文件能力冒稱 runtime PASS。

沒有對 `/usr/bin/eslogger` 或 `/usr/sbin/dtrace` 啟動事件擷取，沒有新增原型、代理、Reviewer、排程或常駐程序；沒有改 production／marker／runtime／plist、未外送或 push。

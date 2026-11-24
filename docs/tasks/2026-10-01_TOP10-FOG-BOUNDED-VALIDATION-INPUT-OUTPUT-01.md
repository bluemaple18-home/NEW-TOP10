# TOP10-FOG-BOUNDED-VALIDATION-INPUT-OUTPUT-01

- 工作名稱：Fog 小型隔離驗證入口修補。
- 狀態：`PARTIAL / LIVE_VALIDATION_BLOCKED`；FOG-NF-001 的兩葉候選 A～D 已 GREEN，但原 AI Core Rule24 Foundation admission 目前回零，native E 在 root／spawn 前 `BLOCKED_WITH_EVIDENCE`。正式工作負載仍禁止。
- 負責：TOP10 Codex Mainline 統籌實作、整合與驗收；本卡不轉交 ai-core Mainline。
- 授權：Owner 2026-10-04 明示先修外接接線、通過後直接繼續既有開發，並回覆「繼續處理完畢」。只承接本機開發，不代表部署或工作負載准入。
- 延續：[原恢復卡](2026-09-29_RECOVER-TOP10-AUTOMATION-BBD32B4-01.md) 的 Fog P0；保留原 Repair 2 核准、修復次數與停止條件，不另開根因、不重置成本。

## 問題與目標

Fog 的 `67f2d28` runtime 於 9/15 留下 `LIVE_SAMPLE_CADENCE_EXCEEDED` 與 `GUARD_INTERNAL_ERROR_PermissionError`，後續 exit 75 是持續封鎖，不能當作新一輪故障。歷史單筆量測約 98.33 秒；目前唯讀量測約 0.60 秒，尚未重現原始故障。已完成的本機診斷補丁只補例外位置，未修復或恢復 Fog。

現有隔離入口至少複製 3,071,805,483 bytes／42,054 files，超出既有 256 MiB 暫存硬上限。目標是沿既有入口分離唯讀程式／必要輸入與受管輸出，使代表性驗證可在既有容量與停止契約內執行，再依實測定位根因。入口修補通過不等於原始 Fog 故障修復。

## 擬核准範圍

1. 先查 CodeGraph 與實際呼叫鏈，確認既有驗證 runner、Fog handoff 及下游寫入的最小修改點。
2. 共用唯讀 source／既有 interpreter，選定必要資料並保存版本、大小與 SHA-256；不複製完整專案或 `.venv`。
3. 所有測試寫入限定於唯一受管 output，保留既有鎖、來源防寫、unknown-write 判定與程序停止證據；不繞過 ai-core 完整停止證明缺口。
4. 先離線反例，再做符合容量與停止准入的有界代表性驗證。未具備完整停止證據時不得啟動依賴該證據的巢狀 workload 或清理。

候選既有入口：`scripts/run_external_fog_revalidation.py`、`scripts/storage_validation/fog_research_worker.py`、`scripts/run_top10_fog_map_handoff.py`、`scripts/run_fog_representative_validation.py`。此清單供定位，不授權整批重寫；實作前凍結最小 affected files 與測試契約。

## 邊界與容量

- 不改 production 預設、不清 marker、不重啟 Fog、不切 launchd、不跑 production Daily、不送 review packet、不 push／部署。
- 不新增 runtime、常駐服務、ledger／registry、Apple Endpoint Security 或平台管理系統。
- 不提高 global policy；測試 owned root 必須實測不超過 256 MiB，檔數與 TTL 沿用既有 policy。
- workload 前取得 fresh host 容量准入與可回退／停止證據；容量不足或完整停止證明不足即 `NO_GO`，不得以人工刪除補成通過。
- 不用任意縮減資料或空 workload 湊驗收；保留既有代表性日期、topic／regime 與真實候選語意。
- 同類兩次無進展或同一 blocker 第三次失敗即停；不得再泛查相同歷史或重派已收斂可行性研究。

## 驗收與交付

1. 來源防寫反例成立；source／input hashes 前後一致，沒有來源、production 或未宣告路徑寫入。
2. owned output 的實測峰值大小、檔數、TTL 與 host 准入均通過；不生成 G 級 clone。
3. 有代表性 topic 實際執行證據；正常完成與失敗／中斷均有足夠程序停止證據。unknown 不得判 PASS，不得清理。
4. 受影響回歸及 `git diff --check` 通過；保存 exact source、命令、精簡 receipt 與可重跑反例。需要 activation／rollback／teardown 變更時依原契約取得兩名獨立驗證，未通過不得放行。
5. 分開裁決「入口是否安全可用」與「9/15 根因是否已重現／確認」；無法確認時明列未知項及最小下一步，不猜改採樣門檻。

交付：最小 diff、驗證 receipt、容量／停止證據、根因裁決與後續處理方案。Daily／provider 第二自然週期另沿原卡驗收，不以本卡取代。

## 證據與回退


### 2026-10-07 FOG-NF-001：固定代表性 no-fork 兩葉候選

- result：`CANDIDATE_GREEN / NATIVE_PREFLIGHT_BLOCKED / LIVE_BLOCKED`。新增 validation-only prepare／execute 兩葉；pinned project head、固定 matrix／compare callable 與原 publish→execute→verify 語意已由 69 項定向測試及 `git diff --check` 驗證。預設 CLI／subprocess 路徑保持相容。
- native preflight：來源與 runner 已凍結；外接 `/Volumes/VibeCode` 以 mount／ioreg／open-fd 核對 UUID。原 lifecycle 在 root 建立前呼叫 Foundation capacity sensor，實際取得 external/internal `admission_available_bytes=0`，依既有 fail-closed 契約拒絕。兩葉均未 spawn，因此沒有停止證明可接受。
- decision：本輪不修改 AI Core、容量 sensor、政策或門檻，不以 raw free 代替 important-usage，也不重試同一 deterministic blocker。managed root／marker／evidence destination 均未建立；Fog、Daily、`restart_denied` 與 production 維持原狀。
- evidence：[完整 receipt](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-nofork-native-preflight-20261007.json)；詳細候選範圍與回退見 [FOG-NF-001 子卡](2026-10-07_TOP10-FOG-NOFORK-LEAF-FEASIBILITY-01.md)。

### 2026-10-05 FOG-TOPO-004：固定代表性分支同程序拆分

- objective：承接 Owner「繼續」與已驗證兩步交接，移除 representative 三階段之間可避免的 subprocess 包裝，沿既有固定 callable 接點保留發布、intent 綁定、研究與驗證語意。
- scope：固定 representative 與三個 CLI 的最小 argv／callable 接回、定向測試；Mainline 承接既有外接 pytest 入口，僅必要新 node。不得新增通用執行器、改共享 lifecycle、降低 authority 或將 mock 當原生停止證明。
- constraints：Daily／Fog／LIVE_BLOCKED／restart_denied 與原 Repair 額度原樣；不啟正式服務，不重跑既有容量測試。不適用的 downstream git／run_step／native 後代保持明示阻擋。
- acceptance：固定各階段順序、argv、退出／中斷、intent 路徑與驗證結果不回歸；新測試必須沿原外接入口有界執行，核對新寫入位置／預算／回收。單一切片通過不代表兩步 nofork 或全專案通過。
- status：CANDIDATE_DEVELOPMENT_PASS / TWO_STEP_FOG_NO_GO。原 Worker 模型容量不可用，Mainline 接手單 writer；未重設 Repair 額度。完成明示 `inprocess=False` 的固定三階段候選與 CLI argv 薄接回，預設 helper／CLI 原樣。
- verification：新外接定向 11/11 PASS；入口邊界 10/10 PASS，bash -n／git diff --check PASS。完整 fixture 18 個 regular files、2653 bytes 均核對外接 device；owned root 觀測峰值 3034 bytes／20 檔，swap 無增長、原 helper cleanup=true，root／isolation marker 已回收。內建／backing／image 分開記錄，未重複扣內建預算。先前新測試遇 symlink 上限與錯誤 sys.exit stderr 斷言均已修正；未調高原限額。
- review：Reviewer A 限定入口獨立 10/10 PASS；Reviewer B 限定 source 無 P0/P1，確認 authority argv／finally／unknown route／預設未啟用。最後 fixture finalizer 的完整寫入契約由 Mainline 真實外接驗證，不冒稱 Reviewer 已重跑；未變停止或啟用機制。
- remaining：batch_owner 強制 git authority、run_step 三次 baseline／candidate／compare subprocess、外層 guard／shared helper 探測與 ambient 外接隔離拒絕皆仍存在。兩步原型只接受兩個 nonfork argv，当前 Fog 不適用；不能用這個候選測試代替真正葉節點停止證明或清 LIVE_BLOCKED。共同 helper 舊容量／Unix socket 未驗項目與完整專案 suite 仍未驗收。
- evidence：[本輪開發與隔離收驗 receipt](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-inprocess-candidate-20261005.json)。現有三階段 subprocess 分支保留為未啟用候選的相容預設；不是第二套 runtime，也未替換 shared helper authority。下一個有效研究點是上述 mandatory git 與固定 matrix／compare 的真正葉節點契約，禁止僅湊成兩組 argv。

### 2026-10-05 FOG-TOPO-003：有限兩步原型交接適用性

- intake：Owner指名承接ai-core `multi-child-prototype-handoff-20261005.md`。五個final source／test／doc SHA皆與freeze一致；原雙審批准有限兩個nonfork步驟，原64項／native兩案沿交接證據，不重跑容量。
- decision：`PROTOTYPE_IDENTITY_VERIFIED / CURRENT_FOG_MAPPING_NO_GO`。新helper已補同root／共同deadline／一次finalize，取代FOG-TOPO-002對這個接點缺席的旧限制。現有兩guard cycle仍各自Popen payload，shared helper啟git，representative三階段及research run_step仍啟subprocess；不是兩個nonfork葉節點。直接三tuple plan的實際API probe在policy／lock／root前拒絕。外接隔離helper的明確拒絕也未解除。
- evidence：[本輪接回核對](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-finite-two-step-intake-20261005.md)列當前呼叫行號、版本、每種擬映射反例與已補／尚缺能力。
- next required artifact：TOP10須先有保持publish／execute／verify及固定12／1／1／8研究語意的兩個實際nonfork葉節點和外接隔離契約；無此映射不接raw argv、不略verify、不啟代表性工作。依Owner本輪條件交付具體缺口，產品source不改；Daily／Fog／BLOCKED及原修復額度不變。


### 2026-10-05 FOG-TOPO-002：跨 TOP10 guard／ai-core lifecycle 授權後裁決

- authorization：Owner 在本對話直接回覆「授權」，准許評估原ASK_USER_SCOPE所列有界跨層接回；沒有改變原Repair 2額度、產品等級、production與解除封鎖限制。
- result：`CROSS_BOUNDARY_DESIGN_NO_GO / ABANDON_CURRENT_NOFORK_ROUTE`。固定Fog外層 launcher 已啟git與guard；guard又啟探針及研究child，representative／research下游仍啟subprocess。原ai-core `command_run` 只持有一個受管command／一份no-fork停止證明；搬動函式或分兩次呼叫會割裂同root的lock、budget、evidence與cleanup ownership。刪fork授權則無固定分支語意完成／native不可繞過證據。四候選與原始碼SHA、行號、failure state見[跨層裁決](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-topology-cross-boundary-20261005.md)。此為新的跨責任範圍核對，非重述FOG-TOPO-001內層檢查。
- status：原ASK_USER_SCOPE已由Owner答覆；現行no-fork路線在本輪授權邊界內無可安全實作的最小產品diff，故停止此路線的本機產品接線。`LIVE_BLOCKED`、Daily／Fog停止、原Repair額度保留。不能把外接pytest或三case容量拒絕PASS換算為完整後代全停。若未來改採多child controller或OS enforcement，須另成明確有界決策，不由本次授權自動延伸。


### 2026-10-05 FOG-IO-003：外接輸出容量拒絕反例接回

- decision：CONTINUE，僅沿Owner本輪明示的既有外接入口接回下一個必要測試；不視為FOG-TOPO-001所需跨guard／lifecycle拓樸擴張授權，原ASK_USER_SCOPE／LIVE_BLOCKED及Repair額度不變。
- objective／traces_to：本卡「擬核准範圍」3、4及「驗收與交付」2、4。驗證shared output容量不足、未知、無效三種情況在spawn前拒絕；此前固定meter node不足以執行這個必要Fog反例。不是重跑meter兩輪，也不改產品容量政策。
- frontier／scope：固定meter外接入口雙審及native兩輪已收驗，允許最小新增 `tests/test_fog_shared_source.py::test_output_capacity_failure_denies_before_spawn` 精確node。僅改 `scripts/test_with_shared_runtime.sh` allowlist／argv傳遞、`tests/test_shared_pytest_entry.py` 選擇與拒絕邊界、該Fog測試的受管外接檔案證據，及原卡／receipt。無舊路徑取代，不新增runtime或清理權限。
- contract：保留預設meter；僅單一已列node，不接受任意參數／多node／未列參數化case。三case建立數KB synthetic source、manifest及拒絕receipt，位於同一owned/pytest/tmp下；沒有真研究或巢狀child，mock容量不是native故障證據。原8MiB／256檔／30s／CPU20s不擴額，RSS512MiB與swap增量256MiB為此輪觀測上限；projected bytes只記backing，不重扣內建。cleanup仍原helper完整停止契約。
- acceptance／verification：入口選擇RED→GREEN；8項既有邊界不退化，另驗新node與注入拒絕；node內逐檔resolved/fstat證明寫入外接，保存bytes/files及case拒絕reason；沿原helper執行新node一次（含三case），記native退出／外接root消失／分卷RSS與swap。原policy／denial／guard SHA不變。完整suite及helper25項缺口照列。
- trace preflight：本slice ID唯一、上述引用存在、測試node已核對、必要8MiB預算不增；無阻塞本切片的未決決策。Jira/US schema not-applicable（沿既有本機卡）。回退只撤本切片allowlist／證據與測試差異，保留其他dirty修改。
- status：`FOG_IO_003_EXTERNAL_CAPACITY_REJECTION_PASS_NOT_LIVE`。入口RED1→GREEN9；原Reviewer A獨立9/9、Spec／Standards PASS，無P0/P1。14:39台北沿原外接入口三case皆PASS／exit0，各30檔，合計90檔150847bytes；整owned root觀測峰值151228bytes／92檔，RSS取樣峰值99319808bytes，swap增量0。真實fstat均device16777240，原helper回收root且isolation無殘留，policy／Daily／Fog denial未變。[FOG-IO-003收據](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-io-003-external-capacity-rejection-20261005.json)保留容量注入與native寫入的區別、原helper25項缺口及回退；未重跑meter兩輪，不是Fog恢復或全專案PASS。

### 2026-10-05 Mainline 範圍裁決：REPLAN，受控啟動拓樸

#### FOG-TOPO-001 檢查點結果（同日接續）

- traces_to：本節「新範圍與第一個檢查點」第 2–4 項；純靜態範圍核對，不適用產品 TDD。未新增 delegation／Repair generation。
- result：靜態核對發現外層 `run_external_fog_revalidation` 強制位於 ai-core lifecycle command 內，但自身啟動 git／guard；guard 又啟動 sysctl／ps／confinement probes／bootstrap。只改 representative／research 的內層 spawn 不能滿足外層 nonfork 成功契約。
- decision：**內層改造實作准入 NOT_PASSED；ASK_USER_SCOPE，LIVE_BLOCKED 保留。** 前述 REPLAN 批准方向不等於此檢查點已通過；不自動進入實作、不重跑已過回歸。
- next scope requiring Owner：是否允許有界設計擴至 TOP10 guard 與 ai-core lifecycle 的責任／接回邊界，包含跨步驟 root／evidence／cleanup ownership；仍不允許新增共用 runtime／Apple／ES／正式啟動。未批准就停止本路線產品改造，不自行搬移或移除 lifecycle，也不將同案重送 ai-core。
- evidence：見既有 `external-cache-wiring-20261004.md` 新增的「2026-10-05 FOG-TOPO-001」；含來源行號、拓樸、第三方未知邊界、候選裁決與版本。32 檔 AST import 候選清單不是完整動態或 native 證明。

- root question：能否將本卡固定 Fog 代表性分支改為所有程序啟動皆不可繞過受控入口、且每個執行單元停止可核驗的有限拓樸？不是為一般任意 fork 工作補造停止證書。
- evidence：已讀 `<ai-core-root>/docs/evaluations/REPAIR-AI-CORE-NESTED-SANDBOX-TEARDOWN-01/handoff-20261005.md`。原交付已找回，但 B-02／R2-C 未成立；現版一般 nested 不支援，TMPDIR 缺路徑仍可回落內建。ai-core 本輪七項離線檢查及雙審只批准恢復完整性／拒絕裁決，不是 nested runtime PASS。r2-decision 歷史 SHA 未配對亦保留，不沿用未知版本批准。
- current state：`STOP_LOCAL_CONTINUATION` 舊的「等待通用 helper 停止證明再接回」計畫；保留 FOG-IO-002 本機受控成果。此次不是第四次嘗試 ACK／kqueue／PGID／加長 grace，也不重新跑 254 項來聲稱 blocker 有進展。
- decision：**REPLAN／批准有界拓樸改造的技術範圍，LIVE_EXECUTION_NOT_APPROVED**。先閉合固定分支的入口清單與不可繞過機制，才可進入最小實作；本輪只作靜態核對與主線裁決，沒有修改產品或啟動探針。原修復成本、次數與停止上限不重置；不得以本節為新一代 Repair 的成本核准。

#### 新範圍與第一個檢查點

1. 只處理本卡日期／regime／12-1-1-8 固定語意的 validation-only 分支。沿現有 guard、shared helper、representative 與 research runner 接點；不改 production 預設、排名／研究語意、輸入資料或既有容量門檻。
2. 第一個交付是可對照原始碼的啟動拓樸：入口、直接／間接啟動者、command／exec／fork／spawn、第三方／native 邊界、歸屬、停止與未知路徑。CodeGraph 已定位 representative `run()`→subprocess.run；原始碼另確認 `run_autonomous_research.run_step()`→subprocess.run、shared helper 的 git 查核 subprocess 與 legacy execve。這只是最小已知集合，不是完整清單；matrix 檔未搜到 spawn 不代表其 import／native 依賴不會啟動程序。
3. 候選優先比較：將必要工作改為不產生後代的執行單元，或由既有控制端直接依序啟動、監督可證明不再產生後代的單元。保持 publish／execute／verify 與中間輸出語意。兩者皆只是候選，未核准新增 broker／runtime／schema；不能只用 Python monkeypatch、allowlist、設定 n_jobs 或「我們的程式不會 fork」當不可繞過證明。
4. 若仍有未受控第三方／native spawn，先以既有可用機制證明其被禁用或在執行前可靠拒絕；無法成立即 **ABANDON_PATH／保持 LIVE_BLOCKED**。不得先放行完整負載來尋找缺失的停止證明。

#### 准入、驗收與禁區

- 靜態清單＋候選差異＋可重現反例設計通過主線檢查點後，才凍結最小 affected files／測試契約並按既有成本路由實作。超出既有成本核准、需要新平台能力或無法維持研究語意時，回 Owner 決策，不自動擴張。
- 新的受控實機探針須先具備獨立安全回收與 fresh 容量准入；不得靠待驗證機制本身保證探針能被回收。覆蓋正常、非零退出、取消／中斷、逾時及試圖繞過入口的 fork／另 SID 情境；記錄程序身分、歸屬與觀測失敗。未知、漏觀測、仍有活後代皆拒絕接回／清理。
- 成功標準是每個可能產生後代的入口均有不可繞過的控制與停止證據；不是父程序退出、PGID 空、第一 child ACK、固定掃描未找到程序或 fixture oracle 能 kill。兩名獨立盲審只對凍結版本與新反例裁決。
- 外接隔離相容列為 **pending**，與停止證明分開准入；內建／image／backing 分開量測，20 GiB 不變，缺碟不得回寫內建。ai-core 10/05 容量 receipt 不是未來 TOP10 workload 准入。
- Apple／ES 路線 **CLOSED**；不重開淘汰候選、不新增共用 runtime／容量專案、不清 LIVE_BLOCKED／restart_denied、不接回巢狀 Fog、不重啟 Daily／正式服務、不清未知 root、不 commit／push／部署／外送。
- why_not_less：只改最外層 wrapper 無法約束 research runner 與間接後代。why_not_more：只需證明固定 validation 分支，不承接全機或任意程序監管。do_not_absorb：Apple／ES、通用程序 broker、第二套 lifecycle／清理 authority。
- next step：交付固定分支的完整啟動邊界與候選可行性裁決；若邊界不能閉合就停，不再將同一 blocker 送回 ai-core 重試。TOP10 Mainline 保留裁決與整合責任。

### FOG-IO-002：既有入口接回（2026-10-04，Owner「做啊」）

- objective：把 external revalidation 的完整 copy 假設改為共享唯讀 source／既有 interpreter＋獨立 owned sandbox，實際接至既有 storage guard。不是只新增 argv builder。
- scope：`scripts/run_external_fog_revalidation.py`、`scripts/storage_safety.py`、既有 `scripts/storage_validation/fog_research_worker.py`、`scripts/run_fog_representative_validation.py` 及對應小型 tests；必要薄 source manifest 放同一既有入口，不新增 runtime／共用元件。不修改 app/storage_safety 的停止／鎖／容量政策來湊通過。
- decision：共享模式是既有 validation-only 入口的明示 root mapping；CLI 的 guard root 從程式 root 解耦，marker／pinned contract／runtime／meter／receipt 仍屬 sandbox。source 必須等於此 checkout 且與 sandbox 不重疊；共享模式限 Fog。保留原 legacy branch 與其外接配置拒絕，不默默降級。helper 固定 source digest／source commit／輸出根並使用原 Seatbelt，來源不得寫入。
- constraints：唯一 writer；不改 production／marker／launchd，不跑真實 Fog 或 full clone；不繞過 lifecycle、source pinning、unknown-write、容量、停止與外接缺碟契約。shared source 模式不得清除 ambient 外接配置以假裝准入，未實作相容時明確拒絕；新入口不能把 missing source/output 轉內建 fallback。
- acceptance：RED（既有 CLI 無分離 root／copy 會含 .venv）→GREEN；小 fixture 證明不複製 venv／source tree、記錄必要輸入大小／SHA；real guard boundary 核對 root、pinned entrypoint、source protection、超額／失敗／回退且 legacy tests 不回歸。正常與中斷驗證僅受控 fixture；單一 PGID 不當完整後代證明。真實代表性驗證仍由原容量／完整停止准入阻擋。
- review：strict，沿既有兩名唯讀盲 Reviewer；Worker 與主線只 sequential single writer，維持原模型。無新 Repair generation／無新側邊欄 task。舊 copy helper 在此入口替換，相關測試改用小 fixture，不保留可誤用的完整 clone 預設。
- status：LOCAL_CONTROLLED_PASS／LIVE_BLOCKED；既有入口接回與受控微型驗證已完成，254 passed／2 deselected／41 subtests。A-001／A-002／B1 原 finding 經兩名獨立複驗閉合；只適用本次受控接線，非整卡完成、真實研究或完整後代停止 PASS。FOG-IO-001 保留 PASS。
- remaining：真實代表性執行仍缺內建容量准入與完整後代停止證明；inputs_closed=false，啟動前 hash 非原子 snapshot。shared isolated Fog 對 ambient 外接快取配置仍明確拒絕，未宣稱該組合已支援，不得刪配置後當作外接整合成功。
- measured scope adjustment：`take_sample` 的 disk_usage(root) 同時把 meter root 當 host 卷；shared root 外接後會誤報內建容量。允許只在 app/storage_safety.py 該函式加入可選 host_root（舊 API 行為不變），CLI shared sampler 分別指定 source 所在 host 與 sandbox meter；輸出卷單獨量測，不加總 free、不調低 global host reserve，不改停止／鎖／diagnostic 既有差異。真實 Foundation 准入仍不能由 raw 取代。
- evidence：沿 `docs/evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/external-cache-wiring-20261004.md` 追加，不另開容量案。

### 2026-10-04 離線切片

- FOG-IO-001，traces_to：本卡「擬核准範圍」2、3 及「驗收與交付」4。frontier：外接接線 development PASS 已完成；本切片不依賴 live workload。Jira／US schema not-applicable：沿既有本機卡，不另開 spec／專案。
- objective／scope：只在 `scripts/run_fog_representative_validation.py` 抽離既有 publish／execute／verify 的命令建構，明確 source root 與 fixture output root；main 使用同一 seam，保留原 no-git／validation-mode gate，不提供新 activation CLI。必要測試限新 `tests/test_fog_representative_paths.py`。
- acceptance：所有命令 source script、config、candidate、baseline 指向 source；所有 fixture history、intent、ledger、corpus、manager、result 指向明示 output。保留 2026-08-31／NARROW_LEADER／BIG_BULL+HIGH_CHOPPY 與 12／1／1／8 參數，不改研究語意、不复制 repo／venv。離線 unit 與 mocked main 檢查不呼叫真實 nested workload。
- data_contract：真實 history `rows` 的 trade_date 粒度，2026-08-31 唯一匹配 identity；history 304677 bytes、SHA 44d21ca8ab606c6dc8d1f2ec5da8fa6473fce4604b2109cbf564d889b62ed0ac；contract 5562 bytes、SHA e3ada41e5a9de4f471750f298718ba815582db550abd9b537a73b66bd818bc34。候選 249 files／1101136 bytes，baseline 283 files／1399960 bytes，均無 symlink；只作唯讀 inventory，不代表所有下游 inputs 已閉合。
- retirement：同檔原命令建構由單一 helper 取代，避免兩套 argv；舊隔離 launcher 不退場或繞過。技能引用的 code-retirement.md 不存在，採本卡最小退出契約，不自行補建共用規則。
- trace preflight：單一穩定 ID、上列引用存在、無重複／懸空；本切片無未決執行授權，測試方式明確。下一 slice 的 live 准入仍 BLOCKED，不將其與本次離線開發混用。
- checkpoint：本切片回歸後才裁決下游寫入及 guard source/output root 接回；禁止以 mock 結果宣稱代表性 topic、完整停止或原故障修復。
- result：FOG-IO-001 新增 12 tests，主線相關 38 tests 通過；獨立 Reviewer Spec／Standards PASS；舊新三階段 argv canonicalize 後一致。既有 gate／helper／完整 clone 路徑尚未替換，不據此啟用共享 source workload。詳見[本輪 receipt](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/external-cache-wiring-20261004.md)。

- [既有精簡證據](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/natural-acceptance-20260930.json)：Fog 歷史故障、量測、診斷補丁與 `reproduction_frontier`。
- [既有 Fog activation 卡](2026-09-14_ACTIVATE-TOP10-FOG-67F2D28-01.md)：runtime 身分與原自然驗收契約。
- [原停止證明案](2026-09-22_REPAIR-TOP10-AI-CORE-STOP-PROOF-CONTRACT-01.md)：Repair 2 成本及禁止 Apple 路線。
- 回退僅撤銷本卡的本機差異，保留昨天已驗證的診斷補丁與證據；不得用整體 reset 覆蓋既有工作。

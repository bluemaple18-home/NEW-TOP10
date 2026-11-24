# TOP10 外接暫存／快取接線

- objective：依 Owner 2026-10-04 明示，修 run_with_storage_guard.sh 覆寫暫存至內建的缺口；沿既有 guard/output 入口完成外接寫入、容量監控、超額停損及回退。
- scope：TOP10 wrapper、既有 storage guard／validation runtime 接點、必要 TOP10 薄路徑 helper 與測試；source / durable artifacts / receipt / lock / marker 維持既有歸屬。先凍結實際寫入清單，不遷移歷史資料。
- constraints：載入 ai-core/config/toolchain_paths.sh，沿用現有外接 cache image（20 GiB 邏輯硬限額），不得新增共用 runtime／容量專案；缺碟／identity 不明拒絕寫入，禁止內建 fallback；內建、cache volume、backing volume 分別量測。保留目前 storage_safety.py 與 tests 的診斷 diff。Daily／production／BLOCKED 不動；不把容量 PASS 當後代全停證明，不執行正式工作負載或外送。
- acceptance：覆寫 RED → wrapper/child 實際 env 與寫入 GREEN；缺碟、超額、identity drift fail closed；既有 stopping/denial 與 ownership/rollback 不回歸；真實小型外接 I/O 證據、內外容量、完整寫入路徑清單、受影響測試及兩名盲驗證；無完整停止證據的 workload 維持禁止。
- status：DEVELOPMENT_WIRING_PASS（受控 Python consumer 邊界）。166 tests、41 subtests、真實外接五路 I/O 與缺 tmp 反例通過，兩名 Reviewer 最終 Spec／Standards PASS；A1／A2／B1／B2 閉合。非任意 hostile code 的隔離證明，非 production 准入或後代全停證明。接續既有 Fog 本機開發，Daily／正式服務／BLOCKED 不動，未 commit／push／部署／外送。
- evidence：[本輪驗證與接續快照](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/external-cache-wiring-20261004.md)。

## 2026-10-04 接續裁決

### 2026-10-05 外接開發有效疏通續接

- continuation（14:39台北）：Owner明示承接已驗兩輪後，沿FOG-IO-003最小新增一個精確Fog容量拒絕node（含三case），不是開放任意pytest。預設meter不變，9項邊界測試及原A定向review通過；新node native 3 passed，90個fixture檔案確在外接並由原helper回收，swap增量0，8MiB／256檔／30秒預算不變。[新切片收據](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/fog-io-003-external-capacity-rejection-20261005.json)。原兩輪證據綁舊版SHA，不冒稱本次重跑；新SHA與增量驗收見新收據。Daily/Fog/BLOCKED及原修復額度未動，helper25項與全suite仍不宣稱驗收。

- acceptance（14:26–14:27 台北最新）：`FIXED_NODE_EXTERNAL_TWO_CYCLES_PASS_NOT_FOG_OR_FULL_SUITE`。原A/B獨立複驗FD接點均無P0/P1，採helper SHA `b34e22dd6721ba9e57002689ed61695f71a54cc624a672c22fe35326234c682f`。經原cache與backing projected gate，固定pytest兩輪各1 passed／exit0；每輪100真檔、400 bytes、逐檔fstat device=16777240（VibeCode），RSS整樹取樣峰值105168896／108707840 bytes，swap增量0；原helper完整stopproof／cleanup成功、兩個owned root消失、isolation marker無殘留。只回收本輪可重建fixture，未碰其他資料。定向測試8項REDGREEN及雙審證據見[外接兩輪實測收據](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/external-pytest-native-two-cycles-20261005.json)。此入口已非容量接線阻塞；不是任意pytest入口或Fog解封。共用helper尚有25容量依賴methods未收驗，full suite不稱PASS；最後check→rmdir的單writer限制及close-error未知FD原樣揭露。Daily/Fog policy與denial SHA未變，未上線／外送／commit。以下均為歷史進度，不覆蓋本行最新判定。

- status（parent FD薄接線）：原兩位Reviewer共同P1為原helper pathname建立／清理未綁定已驗FD，非外接容量不足。ai-core沿 `CARD-TMP-LIFECYCLE-PINNED-VOLUME-20261005.md` 修原authority；TOP10僅傳 `parent_fd=fd` 並補fake邊界身分斷言，同8項測試RED（missing parent_fd）→GREEN，bash syntax／diff check通過。`THIN_MAPPING_PASS_SHARED_HELPER_REVIEW_PENDING`，尚非預設入口；等待已驗helper SHA/REDGREEN後復用原A/B複驗，native外接兩輪仍0，Daily/Fog封鎖不變。[本輪實作與審查收據](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/external-pytest-entry-20261005.json)保留前版hash與P1歷史。

- scope（正常pytest外接入口）：承接Owner「做吧」及ai-core `CARD-TOP10-EXTERNAL-PYTEST-ENTRY-20261005.md`。新增一個薄專案入口與必要定向測試，實際owned root採已驗UUID的 `AI_CORE_CACHE_BACKING_VOLUME` 外接主卷；工具cache仍走20GiB限額卷。重用原tmp lifecycle完整停止證明／8MiB、256檔、30s／exact-owned cleanup，不新增quota、監控或清理器，不改Fog/guard/政策。RSS512MiB與swap增量256MiB僅此固定node兩輪觀測收驗上限，CPU20s沿原生rlimit；未知pytest不推廣保證。
- decision（實作前接點核對）：pure重現20GiB快取卷即使全空，套原lifecycle 20GiB保留線並扣8MiB仍拒絕，因此不降低門檻，依Mainline決定採外接主卷。normal pytest的parent與child均固定tempfile根；child位於owned/pytest/tmp以符合既有symlink fixture policy，同PID跑原pytest與research spine finalizer，fork／退出未知保留root。Worker Rawls為本輪唯一source writer；Ramanujan／Sartre獨立盲審，先前「缺持久RSS監管」的候選finding已因明確契約收斂送原Reviewer重新核對，尚未宣稱通過。

- decision（真實離線入口）：選原 `pytest` node `tests/test_storage_safety.py::StorageSafetyRegressionTest::test_overlapping_meter_paths_do_not_resolve_each_regular_file`，驗證新sample／分卷計算依賴的真檔案meter；不是Fog或受拒工作更名，無服務guard適用。13:12台北同命令兩輪各1 passed／exit0；每輪100真檔、400 logical bytes、409600 allocated bytes與1 symlink，RSS峰值68534272／71204864 bytes，swap觀測增量0，自有fixture和空父目錄全數回收，退出後受測process group為空。三卷free分判、必要預算、call chain、適用gate與取樣限制見[兩輪離線meter實測](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/offline-meter-test-two-cycles-20261005.json)。本次內建raw已回升約25.03GB，不沿用上午缺口或歸因修補。僅此入口可正常開發：暫存仍在內建，外接新產物／完整代表性負載／Fog仍未放行；未修改delivery source、未重跑37項或調整既有門檻。

- acceptance（sensor首次收卡退件補驗）：先前35項及非macOS模擬未涵蓋原始macOS host_root測試，Standards當時應為NEEDS_WORK。依明確擴充allowlist，原命令先重現2 failed，再只修改 `tests/test_fog_shared_source.py::test_take_sample_host_root_preserves_output_meter` 的sensor mock及admission/raw/source斷言；同命令2 passed，合併原35項共37 passed／175 deselected，未改platform。產品SHA仍為94cc0011318dd7af75f67f4da905ba693ef43b517e18733e5473efd253a444de，無新負載或原生重測。當前 `MAINLINE_ACCEPTED_NOT_WORKLOAD_GO`；[Mainline收驗收據](../../../ai-core/docs/evaluations/WEBGPT-LIFECYCLE-RECOVERY-20261001/daily-archive-capacity-20261002/top10-mainline-capacity-acceptance-20261005.json)確認有界sensor/accounting修正收驗，[原receipt的standards_followup](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/capacity-sensor-alignment-20261005.json)保留退件與補驗歷史。工作週期／Fog／正式服務仍未放行。

- status（固定sensor修正）：`SENSOR_ALIGNMENT_PASS_NOT_WORKLOAD_GO`。承接ai-core `CARD-TOP10-CAPACITY-SENSOR-ALIGNMENT-20261005.md`，只改TOP10 `Sample`／主機sensor／`take_sample`及指定測試。macOS沿既有共用sensor採Foundation准入，另存raw與source；未知失敗直接拒絕，非macOS原樣。門檻、writer/output root、停止契約均未改。
- acceptance：先重現raw不足／important足卻被拒的RED；GREEN為35項定向pure checks。另兩個既有shared-source root cases於模組局部模擬非macOS通過；未聲稱全庫測試。11:26:57台北原生唯讀取樣確認source正確：raw23160893440、admission24220143680 bytes，政策差額290575910 bytes；外接cache gate PASS，可用16397836288 bytes。Daily plist／Daily與Fog denial及policy前後hash不變。
- evidence：[固定量測修正、原生取樣與限制](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/capacity-sensor-alignment-20261005.json)。本次修補完成但兩週期仍未執行；不改持久輸出映射、不冒稱Fog可接回。下面ROOT_CAUSE_IDENTIFIED_NOT_REPAIRED為修補前歷史狀態，sensor缺口由本項取代，其他阻擋保留。

- decision（根因排查續補）：`ROOT_CAUSE_IDENTIFIED_NOT_REPAIRED`。Rule24要求macOS Foundation admission，但TOP10仍用raw free；11:15樣本兩者差額分別225564262與1284691558 bytes，兩者皆未達線。不得再將後者稱為工作负載必要容量或外接不足。外接快取接線不涵蓋預設持久產物；既有fixture/output/manager/corpus/ledger可指定路徑，但外接隔離／後代全停仍阻擋正式接回。本輪只查證，未改產品或門檻。下一修正範圍、writer清單、純函式反證與回退見[根因證據](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/development-relief-root-cause-20261005.json)。不再重複量同一門檻或要求Owner先清硬碟。

- scope：承接 ai-core `CARD-EXTERNAL-DEVELOPMENT-RELIEF-20261005.md`，已由 source thread 核對 Owner「處理好 開卡派工去處理」直接授權。保留 TOP10 Mainline、原額度與已驗接線；不改 ai-core，不啟 Fog／Daily。
- measured admission：11:04 台北量測內建 Foundation admission 24263663616 bytes，政策 reserve 24510719590 bytes，尚差 247055974 bytes；TOP10 raw sampler 23204544512 bytes，既有 evaluate_preflight 拒絕 HOST_START_FREE_SPACE_BELOW_THRESHOLD。外接 cache gate PASS，非外接容量不足；未啟動代表性 child，兩輪峰值／回收仍未驗收。
- measured gap：`take_external` 合併內建與外接 bytes；`evaluate_runtime` 又以合併 growth 預扣 host_free，將外接增長錯算為內建未來需求。允許同函式最小會計修正與必要離線測試；不是降低門檻／跳過 gate，不涉及停止／trap／cleanup 改造。
- acceptance：單純外接增長不觸發內建投影不足；真實內建增長仍停、job 總量／穩定與原生 cache gate 不變；分卷觀測缺失／不一致 fail closed。本輪離線驗證只證明投影，不冒稱兩輪產品 workload。
- limits：外接 retention 目前 deny-and-preserve／automatic_cleanup=false；不擅自新增外接自動清理。新實測不足不重跑舊166項；只驗本次 affected seam。
- result：跨卷重扣反例 RED（外接增長 0/10/20 bytes 被誤判 SUSTAINED_GROWTH）→GREEN；只改 evaluate_runtime 投影，14項新增pure cases與7項受影響既有檢查共21 passed／124 deselected。兩名原Reviewer限定雙軸PASS，無新P1；沒有把測試相加當實際負載。
- status：ACCOUNTING_FIX_PASS／DEVELOPMENT_CYCLES_NO_GO。兩輪均未啟動，RSS／swap增量／各卷峰值／回收未知；外接卷不是拒絕原因。既有真實五路I/O、超額與缺碟證據沿用，不重做或改日期。
- receipt：[2026-10-05 分卷准入與計算修補](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/development-relief-20261005.json)。ai-core由read/wait收卡，本對話不另行回送。
- receipt：Owner 要求執行後於 11:15:17 台北重新原生量測；既有 raw guard 仍差 1284691558 bytes，Foundation reserve 差 225564262 bytes，外接 cache 可用 16489889792 bytes。兩輪未啟動，不降低門檻或重複輪詢；[本次准入證據](../evidence/RECOVER-TOP10-AUTOMATION-BBD32B4-20260929/development-relief-recheck-20261005-111517.json)。需先指定可安全回收的內建資料／完成其他既有回收，另留負載增量；不授權刪除未知資料。
- next step：原guard准入成立後才選定同一安全代表性開發命令與逐卷增量預算，補兩週期。Fog仍缺全停證明且checkout的Fog denial已存在，不可拿provider入口或改job名代替；不為補週期另建入口／lower gate。可繼續的本輪離線最小修正已完成。

- Owner 在「是否允許既有 TOP10 guard 加入子程序寫入限制」後回覆「繼續處理完畢」；承接此唯一指名範圍，其他禁區不變。
- measured gap：缺失 TMPDIR 的單一 Python child 在原環境寫入 `/tmp`；同一 child 套既有 Seatbelt profile 後得到 FileNotFoundError、無 fallback，host 實測 exit 0。
- affected seam：`run_guarded_job` external 分支的 spawn command、既有 `_sandbox_profile`／原生 sandbox-exec、`JobPolicy.registered_write_paths`。不改共用 ai-core、不更換 interpreter、不注入 sitecustomize。
- minimum sufficient：僅在 external-required child 加入原生 file-write 限制，允許原登記輸出、精確 owned external root 及 /dev/null；保留原非寫入行為，不順手放寬 validation-only profile。未知平台／能力檢查失敗沿原 receipt／denial 拒絕。較少（只設 env／輪詢）已有反例；較多（新 runtime／全域 Python patch）不吸收。
- acceptance：同一缺碟 tempfile 反例轉綠；有效外接與合法持久輸出仍可寫；project root／來源／未登記位置不可寫；symlink／上層路徑不能擴權；超額停損與回退不回歸。僅 synthetic single-child 與小型 host I/O，不跑正式或缺全停證據的 workload。
- status：IN_PROGRESS／A1 最後有界收斂。主線先完成即時阻擋的原生能力驗證與最小接點，不新增 Worker 對話；沿用兩名原 Reviewer 定向複驗。失敗不再無限開 Repair，不重置前輪成本。
- measured revision：Reviewer 重現 registered-output cwd 的正常 tempfile fallback；LightGBM 與 Matplotlib 也使用未指定 dir 的標準庫呼叫。僅原生 pathname profile 不足，前項「不注入 sitecustomize」的候選假設因此失效。最小接回改用 Python 原生 sitecustomize（TOP10 內 14 行，不安裝到 interpreter／全域）：只在 guard 本次 child PYTHONPATH 啟用並固定 `tempfile.tempdir`，finally 還原 PYTHONPATH；缺 tmp 直接 OSError。禁止在本寫入入口用 -I/-E/-S 關掉映射；既有唯讀 identity helper 不變。這不是新增共用 runtime／服務，也不擴張允許寫入根。

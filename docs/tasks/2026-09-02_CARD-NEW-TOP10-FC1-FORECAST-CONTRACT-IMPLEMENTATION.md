# FC1 Forecast Contract Implementation 待派工卡

工作名稱：P2／FC1 通用 Forecast Contract 最小實作；slice_id=`FC1-FORECAST-CONTRACT-01`；traces_to=`FM0-CONTRACT-ABSORPTION-01`；狀態=`ADMITTED / READY_FOR_DISPATCH / TFM3-S1_NOT_ADMITTED`。

依賴與基線：FM0 fixed candidate `43c561160a81b6bd4ae96a809de215f4bfdd43ac` 已 `REVIEW_GO / P0=0 / P1=0`，並整合為 canonical main `ff3d30bcab1ad6c8abef01410706d81e9e998a4a`；origin 尚未 push。Worker 必須從此 fixed main 建立獨立 worktree，核對 FM0 三份 evidence、現行 Dataset Bundle／TrialSpec／RunReceipt／Observation seams 與 dirty-worktree 邊界。

最小範圍：由 GPT-5.5 high strict/core-bounded Worker 實作 vendor-neutral forecast contract 與 deterministic validators；只允許版本化 forecast dataset consumer／ordered channel 與 temporal availability contract、獨立薄 `forecast-trial-spec.v1`、forecast artifact/license receipt contract、獨立 Forecast Evaluation Observation shape及對應測試。必須沿用 canonical JSON/content identity、既有 intent/attempt/receipt authority 與 artifact CAS；不得修改或升版 `research-trial-spec.v1`，也不得以 `ranking_source_authority` 或 strategy parameters 假裝 forecast 欄位。

禁區：不得使用 `TimesFM*` 作通用類別名稱；不得下載模型、安裝模型套件、執行 inference、建立 TimesFM adapter；不得修改 #13／#14、B0 strategy matrix、BC-CP2、C0 queue／runner、M4–M7、ranking、production、scheduler；不得新增 DB、registry、ledger、canonical writer 或第二套 runtime；TFM3-S1 維持 `HOLD / NOT_ADMITTED`。

驗收與停損：測試至少證明 channel order／duplicate／missingness ambiguity fail closed、`available_at > forecast_origin` leakage fail closed、合法 future-known covariate 通過、forecast spec 拒絕 strategy-parameter pollution、receipt 綁定 point／quantile／license refs、forecast observation 不進 strategy observation／eligibility；跑 affected regression 與 `git diff --check`，再由獨立 fixed-SHA Reviewer 裁決。遇 authority conflict、需 queue/runner mutation、需外部服務或 license 不明時立即 `NO_GO` 回主線；不得 merge、push、deploy、production 或 external write。

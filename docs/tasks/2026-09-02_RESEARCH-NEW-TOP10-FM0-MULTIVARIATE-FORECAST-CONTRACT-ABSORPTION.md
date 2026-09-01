# FM0 Multivariate Forecast Contract Absorption 派工卡

工作名稱：P2／FM0 多變量預測契約吸收；slice_id=`FM0-CONTRACT-ABSORPTION-01`；traces_to=`FORECAST-CONTRACT / LICENSE-BOUNDARY / EXISTING-SEAM-FIT`。

任務簡介：以 canonical main `35bb9927eb0eac9a624dcaf0dcffcbf88857c070` 為固定基線，唯讀核對現有 Modeling、Research Dataset Bundle、TrialSpec、RunReceipt、Feature as-of、Observation／Eligibility seams，產出 vendor-neutral forecast contract 與下一卡 admission 建議；TimesFM-3 僅作 donor evidence，不是 authority、subsystem 或 runtime dependency。

允許與禁止：你是 GPT-5.5 high strict/core-bounded docs-only Worker；只可新增 `docs/evidence/FM0-MULTIVARIATE-FORECAST-CONTRACT-ABSORPTION/01-existing-seam-map-and-absorption-boundary.md`、`02-vendor-neutral-forecast-contract.md`、`03-license-boundary-and-next-card-admission.md`，以及更新本卡的 evidence handoff；不得修改 code、config、workflow、canonical backlog、#13／#14、BC-CP2、M4–M7、queue／runner，不得下載模型、安裝套件、執行 inference、建立 adapter／schema／DB／registry，不得 merge、push、改 Issue 或 external write。

契約要求：逐 seam 裁決 `USE_AS_AUTHORITY / USE_AS_IS / WRAP / ADAPT_LATER / NEW_VERSION_LATER / DO_NOT_USE`，不可把現行 strategy-specific TrialSpec、RunReceipt builder 或 Observation／Eligibility 誤稱為 forecast-ready；通用類別不得使用 `TimesFM*` 命名，必須分離 source code、checkpoint、license、output usage，保留 `event_at / available_at / forecast_origin`、ordered channel manifest、missingness、pre/postprocessing receipt、point／quantile artifacts 與 license propagation，並明記 forecast benchmark matrix 不得混入 B0 strategy matrix。

驗收與停損：三份 evidence 必須包含 fixed source SHA／file anchors、現況與目標差距、`why_not_less / why_not_more / do_not_absorb`、TFM3-S1 admission prerequisites 與明確 `GO_NEXT_CARD / HOLD / NO_GO`；只允許決定是否另開 Forecast Contract implementation card，TFM3-S1 維持 `REGISTERED / NOT_ADMITTED / NO_DOWNLOAD / NO_INFERENCE / NO_PRODUCTION`。遇 authority conflict、需要 runtime claim、需要新增第三套 authority、或無法以 fixed evidence 裁決時立即停止回報；完成只回 candidate SHA、changed files、verification、remaining unknowns 與 next-card decision。

## Evidence Handoff

執行狀態：`COMPLETE / DOCS_ONLY / NO_RUNTIME_MUTATION`
工作基線：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
隔離分支：`codex/fm0-forecast-contract-absorption-20260902`

交付文件：

- `docs/evidence/FM0-MULTIVARIATE-FORECAST-CONTRACT-ABSORPTION/01-existing-seam-map-and-absorption-boundary.md`
- `docs/evidence/FM0-MULTIVARIATE-FORECAST-CONTRACT-ABSORPTION/02-vendor-neutral-forecast-contract.md`
- `docs/evidence/FM0-MULTIVARIATE-FORECAST-CONTRACT-ABSORPTION/03-license-boundary-and-next-card-admission.md`

Seam 裁決摘要：

- `USE_AS_AUTHORITY`：canonical JSON/content hash、Dataset Bundle envelope、TrialSpec identity、RunReceipt identity/terminal taxonomy、Observation derivation principle、Eligibility projection principle。
- `USE_AS_IS`：artifact CAS。
- `WRAP`：existing component roles、M4 fundamentals as-of pattern。
- `ADAPT_LATER`：ExecutionIntent/AttemptStarted、current Eligibility policy。
- `NEW_VERSION_LATER`：Dataset Bundle forecast consumer matrix、TrialSpec forecast variant、Forecast Evaluation Observation。
- `DO_NOT_USE`：strategy receipt builder for forecast、B0 strategy matrix、C0 queue/runner inventory、TimesFM-3 checkpoint。

Verification：

- CodeGraph status checked for fixed repo context: 820 indexed files / 17357 nodes / 40025 edges。
- Repo anchors checked with bounded `rg` and focused `sed/nl` reads。
- Official donor facts checked against Google Research Blog, Google Research GitHub, and Hugging Face model/license pages; no model download, install, inference, adapter, external write, merge, push or issue mutation。
- `git diff --cached --check`：PASS。

Remaining unknowns：

- FC1 must choose `research-trial-spec.v2` forecast variant vs thin `forecast-trial-spec.v1` with tests。
- Forecast dataset bundle implementation must define exact ordered-channel validator and availability manifest shape。
- TimesFM-3 license remains non-commercial/non-production unless a separate license authority is obtained。

Next-card decision：

- `GO_NEXT_CARD`：bounded `P2 / FC1 Forecast Contract Implementation` may be proposed after Mainline acceptance。
- `HOLD`：`TFM3-S1 Restricted Shadow Benchmark` remains `REGISTERED / NOT_ADMITTED / NO_DOWNLOAD / NO_INFERENCE / NO_PRODUCTION`。
- `NO_GO`：production use, M4-M7 mutation, B0 strategy matrix consumption, queue/runner mutation, external write。

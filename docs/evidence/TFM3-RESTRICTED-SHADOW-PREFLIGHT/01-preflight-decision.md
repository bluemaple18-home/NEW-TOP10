# TFM3 restricted shadow benchmark preflight decision

## Verdict

`TFM3_S0_PREFLIGHT_COMPLETE / TFM3_S1_NO_GO_EXTERNAL_ACCEPTANCE_ENV_AND_CAPACITY`

## Official-source snapshot

- Google Research目前把TimesFM 3.0列為latest model version，並說明source code為Apache-2.0，但3.0 pretrained weights另受`timesfm-non-commercial-license-v1.0`限制，只可non-commercial、non-production使用：[official repository](https://github.com/google-research/timesfm#readme)。
- 官方Hugging Face model card確認`google/timesfm-3.0-pytorch`、0.3B級模型與non-commercial license；model repo目前要求登入後接受條件並分享聯絡資訊才能存取檔案：[model card](https://huggingface.co/google/timesfm-3.0-pytorch)。
- 權重檔由verified commit `6455822fd4703713f3bf9cb2845f7ba51dc65250`上傳；remote file約`1.32 GB`，SHA-256=`a7592b0a8432baee54483254e5647856911ce69e09d09a9bb65904b2d98f17da`：[model blob](https://huggingface.co/google/timesfm-3.0-pytorch/blob/main/model.safetensors)。
- 目前model-card commit history head為`900fcab43d1bfe71733a33b3fec61a41fce28a27`；license content對下載、存取與使用有明確acceptance與用途限制：[commit history](https://huggingface.co/google/timesfm-3.0-pytorch/commits/main)、[license](https://huggingface.co/google/timesfm-3.0-pytorch/blob/main/LICENSE)。

## External-tool gate

```text
tool/service: official Google Research GitHub + Hugging Face public pages
operation_level: read_only
connection_status: public metadata readable; checkpoint access gated
schema_checked: repository README, model card, commit history, model blob metadata, license
confirmation_required: yes before account/license acceptance, dependency install, download or inference
execution_status: preflight only; no remote mutation and no download
remaining_risk: intended-use license fit and gated-account acceptance cannot be inferred
```

## Existing contract readiness

- `forecast-trial-spec.v1`、ordered target/covariate channels、artifact/license refs與Forecast Evaluation Observation已存在。
- `tests/test_forecast_contracts.py tests/test_forecast_fixture.py`：`31 passed`。
- TFM3-specific內容仍必須只映射進existing model／execution-profile refs與immutable artifacts；不得新增TimesFM專用schema、ledger、queue、runner或canonical writer。

## Local runtime and capacity snapshot

| Item | Observed | Gate |
|---|---:|---|
| Host architecture | `arm64` | RECORDED |
| Project Python | `3.12.12` | RECORDED |
| `torch` / `timesfm` / `timesfm3` | missing | BLOCKED |
| `huggingface_hub` / `safetensors` | missing | BLOCKED |
| Project `.venv` | about `0.69 GiB` | RECORDED |
| Filesystem total | `228.27 GiB` | RECORDED |
| Filesystem available | `49.87 GiB` (`21.84%`) | raw-model threshold PASS |
| Published model blob | about `1.32 GB` | RECORDED |
| Dependency/cache peak budget | unknown | BLOCKED |
| Representative two-cycle growth | not run | BLOCKED |
| Cleanup/recovery drill | not run | BLOCKED |
| Process RSS/swap stop-loss | not established | BLOCKED |

目前free space高於10%，且只放入1.32 GB權重後仍高於`max(20 GiB, 10%)`；但這只證明raw model blob的靜態餘裕。依賴、cache、temporary extraction與兩週期inference峰值未量測，因此完整S1 storage gate仍是NO-GO。

## License/use boundary

官方license把商業用途、production，以及把outputs用於commercial decision-making排除在non-commercial purpose之外。本專案與股票預測有關，不能自動推定未來輸出符合license；需要Owner明確限定為private、non-commercial、non-production research，且不得把TFM3 outputs接入交易／推薦／production決策。

## Minimum next authorization payload

只有以下內容一次確認後，才可另開S1：

1. 用途固定為private non-commercial research，接受不進交易、推薦或production決策的限制。
2. Owner自行完成Hugging Face gated model條件接受／登入；agent不代填聯絡資料或代替接受license。
3. 授權用`uv`在project-local隔離環境安裝固定版本依賴。
4. 授權最多`6 GiB`的download/cache/tmp總預算；超過即fail closed，不清理其他專案資料。
5. 先跑單一tiny smoke inference，再決定是否執行兩週期representative shadow benchmark；任何輸出維持`RESEARCH_ONLY / NO_B_DECISION_CONSUMPTION / NO_PRODUCTION_SIGNAL_EXPORT`。

## Final boundary

未取得上述條件前，不下載、不安裝、不inference、不新增adapter implementation。TFM3-S1維持`NO_GO / HOLD`。

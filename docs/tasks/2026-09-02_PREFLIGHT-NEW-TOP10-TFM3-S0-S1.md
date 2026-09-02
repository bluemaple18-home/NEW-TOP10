---
id: PREFLIGHT-NEW-TOP10-TFM3-S0-S1
chain_id: TFM3-RESTRICTED-SHADOW-01
status: preflight_complete
type: external-model-readiness-preflight
risk: critical
production_change_allowed: false
runtime_change_allowed: false
network_allowed: read_only_official_sources_only
download_allowed: false
inference_allowed: false
---

# TFM3-S0／S1 restricted shadow benchmark preflight

## 工作名稱 → 正在做什麼 → 現在狀態

`TFM3 Restricted Shadow Preflight` → 核對官方model／license、現有Forecast contract、本機runtime與容量 → `S0_COMPLETE / S1_NO_GO_EXTERNAL_ACCEPTANCE_ENV_AND_CAPACITY`

## Root question／blocker／fork

- Root question：不下載checkpoint、不安裝依賴、不執行inference的前提下，TFM3-S1還剩哪些真正需要Owner介入的邊界？
- Current state：FC1／FC2 vendor-neutral create→run→receipt→artifact→evaluation→eligibility-isolation contracts已在main，targeted tests `31 passed`。
- Blockers：Hugging Face model是gated access且要求接受條件／分享聯絡資訊；權重僅允許non-commercial、non-production使用；本機缺`torch/timesfm3/huggingface_hub/safetensors`；dependency footprint、兩週期代表性試跑、cleanup與memory stop-loss尚未驗證。
- Candidate fork：只能在Owner確認用途、完成外部license acceptance並明確授權bounded download/inference後，另開TFM3-S1；否則維持HOLD。

## Verdict

`TFM3_S0_PREFLIGHT_COMPLETE / TFM3_S1_NO_GO`

## 邊界

- 未登入Hugging Face、未接受license、未下載model、未安裝package、未執行inference。
- 未修改Forecast schema、runtime、queue、runner、model、ranking、backtest、scheduler或production。
- 詳細證據：`docs/evidence/TFM3-RESTRICTED-SHADOW-PREFLIGHT/01-preflight-decision.md`。

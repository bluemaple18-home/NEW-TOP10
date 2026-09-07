---
id: REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01
status: confirmed
type: evidence
---

# Root cause evidence

- live invocation `fog-research-worker-20260907T070804Z-4310` 顯示 child exit=0、process group quiescent，但 `artifact_run_date=null`、`natural_trigger_verified=false`、`accepted_natural_cycles=0`。
- `_receipt_payload()` 固定不讀 artifact/cadence evidence，因此成功 child 也只能 pending。
- wrapper 只把 PPID=1 分成 natural candidate；launchd natural fire 與 manual kickstart 無法由 PPID 區分。
- Fog worker 已有 `RUN_DATE`/`RUN_ID` 與 canonical `fog_map.json` event，但未產生 invocation-bound terminal evidence。
- 既有 archive receipt 可作 cadence chain；不得以 mutable latest 取代 exact invocation binding。

本卡不回填舊 receipt；修復後仍需兩個新的、自然且合格的 runtime cycles 才可完成 live acceptance。

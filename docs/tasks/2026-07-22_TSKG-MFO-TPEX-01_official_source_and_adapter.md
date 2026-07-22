---
card_id: TSKG-MFO-TPEX-01
chain_id: TOP10-NEXT-WAVE-20260722
status: READY_FOR_REVIEW_V2
type: source-governance-and-conditional-implementation
owner: receiving Mini
model: receiving Mini
reasoning: medium
model_reason: 使用者指定 Mini；官方來源、法遵與外部資料風險以 fail-closed source gate 控制。
thickness: strict
depends_on: []
worktree: receiving_host_must_provision
---

# TSKG-MFO-TPEX-01 TPEx 法人來源

任務ID：TSKG-MFO-TPEX-01
卡片類型｜派工對象：Source Governance + Conditional Adapter｜Mini
請讀：docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md、app/tskg/source_policy.py、app/tskg/twse_t86.py、app/tskg/flow_observation.py
任務目的：查明 TPEx 逐證券三大法人官方機器可讀來源與使用契約；只有 source gate GO 時才建立 bounded adapter
證據路徑：docs/research/TSKG-MFO-TPEX-01_source_dossier.md、docs/evidence/TSKG-MFO-TPEX-01/

## Allowlist

- docs/research/TSKG-MFO-TPEX-01_source_dossier.md
- app/tskg/source_policy.py
- app/tskg/tpex_*.py
- scripts/fetch_tskg_tpex*.py
- data/fixtures/tskg/tpex_*.json
- tests/test_tskg_tpex*.py
- docs/tasks/、docs/evidence/、.work/ 本卡路徑

## Acceptance

- 只引用 TPEx、政府開放資料或其他官方 primary sources，固定 access date、dataset identity、license/terms、automation permission、rate、retention、revision、deletion、redistribution 與 owner。
- 找不到明確 machine-use permission 時輸出 KEEP_BLOCKED，不實作 live connector。
- 若 source gate GO，先以 captured/synthetic fixture 實作 parser、normalizer、provenance、late-data 與 error behavior；live fetch 預設關閉。
- 輸出與 SecurityFlowObservation schema 相容，TWSE/TPEx venue 不混淆。
- 不購買、不註冊、不接受條款、不 load/rate test。

## Verification

```bash
uv run pytest tests/test_tskg_tpex*.py tests/test_tskg_mfo01.py
uv run python -m py_compile app/tskg/tpex_*.py scripts/fetch_tskg_tpex*.py
git diff --check
```

若 glob 無對應檔，改列實際檔案；不得讓 shell 的空 glob 掩蓋測試。

## 2026-07-22 source correction

政府資料開放平臺 dataset `11856` 已證明 target dataset identity、每日更新與 OGL 1.0 授權；原 `KEEP_BLOCKED` 負面證據因此被更正。實作只開放 current-day 官方 OpenAPI，歷史網站／CSV crawler、paid S35 與 raw public redistribution 仍 blocked。驗證見 `docs/evidence/TSKG-MFO-TPEX-01/verification_v2.md`。

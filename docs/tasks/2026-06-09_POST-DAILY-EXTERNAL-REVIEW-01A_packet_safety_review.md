# POST-DAILY-EXTERNAL-REVIEW-01A｜Packet Safety Review

## 任務ID

`POST-DAILY-EXTERNAL-REVIEW-01A`

## 卡片類型｜派工對象

External Review Packet Safety Review｜Codex reviewer

## 請讀

- `docs/tasks/2026-06-09_POST-DAILY-EXTERNAL-REVIEW-00_mainline.md`
- `docs/tasks/2026-06-09_POST-DAILY-EXTERNAL-REVIEW-01_review_packet_and_storage.md`
- `docs/architecture/EXTERNAL_REVIEW_CONTRACT.md`
- `scripts/build_external_review_packet.py`
- `scripts/verify_external_review_packet.py`
- `artifacts/external_review/2026-06-08/review_packet_2026-06-08.json`
- `artifacts/external_review/2026-06-08/review_packet_2026-06-08.md`

## 任務目的

針對 `POST-DAILY-EXTERNAL-REVIEW-01` 做 targeted review，確認安全版 `review_packet` 是否真的只包含可外送資料，且 verifier 能阻擋內部模型/feature/score/本機路徑外洩。

## Review 範圍

只審以下項目：

- `scripts/build_external_review_packet.py`
- `scripts/verify_external_review_packet.py`
- `artifacts/external_review/2026-06-08/review_packet_2026-06-08.json`
- `artifacts/external_review/2026-06-08/review_packet_2026-06-08.md`

不要審：

- ranking algorithm
- model promotion
- publish flow
- ChatGPT / Gemini collector
- daily pipeline 接線

## 已知待確認風險

本卡已修正的 primary concern：

- `review_packet_*.json` 不得含 `sources`、`features_ohlc`、`data/clean`、`*.parquet`、`models/` 或 `artifacts/ranking_*.csv`。
- sendable packet：只給外部 reviewer。
- local manifest：`review_packet_manifest_YYYY-MM-DD.json`，只留本機 lineage / source trace。
- collector 只能讀 verifier 通過的 sendable packet，不得直接外送 manifest。

## Review 問題

1. packet 是否還含有不該外送的內部資料？
2. verifier 是否能擋住：
   - `model_prob`
   - `final_score`
   - `risk_adjusted_score`
   - `AI:`
   - `SHAP`
   - `/Users/...`
   - `/private/...`
   - `data/clean/features.parquet`
3. JSON packet 是否已是 sendable-only，且 local manifest 沒有被 collector 使用？
4. packet schema 是否足夠支援下一張 `POST-DAILY-EXTERNAL-REVIEW-02_chatgpt_collector`？

## 建議驗證

```bash
.venv/bin/python scripts/build_external_review_packet.py --date 2026-06-08
.venv/bin/python scripts/verify_external_review_packet.py --packet artifacts/external_review/2026-06-08/review_packet_2026-06-08.json
.venv/bin/python -m py_compile scripts/build_external_review_packet.py scripts/verify_external_review_packet.py
git diff --check
```

另請新增或手動構造負例，確認 verifier 會擋下含有 `sources`、`data/clean/features.parquet`、`features_ohlc`、`*.parquet`、`models/latest_lgbm.pkl`、`artifacts/ranking_YYYY-MM-DD.csv` 的 sendable packet。

## 輸出要求

請用 code review 格式回覆：

- Findings：依 P0/P1/P2/P3 排序，需含檔案與行號。
- Open Questions：若 collector sendable 格式仍不明，請明確提出。
- Testing Gaps：只列會影響外送安全邊界的缺口。

若無阻塞問題，請明確寫：

```text
未發現阻塞問題。
```

## 證據路徑

- `artifacts/external_review/2026-06-08/review_packet_2026-06-08.json`
- `artifacts/external_review/2026-06-08/review_packet_2026-06-08.md`
- `scripts/verify_external_review_packet.py`

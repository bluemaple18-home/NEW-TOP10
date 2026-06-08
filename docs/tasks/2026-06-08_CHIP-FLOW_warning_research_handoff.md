# CHIP-FLOW 籌碼提醒研究交接

日期：2026-06-08
狀態：研究收尾，交給主線評估
範圍：三大法人、融資融券、外資賣且融資增、籌碼搭配價格/排名轉弱，是否能作為「獲利了結 / 減碼 / 風險提醒」訊號。

## 1. 結論先講

本輪研究已收斂，不建議把 `chip_flow` 推進正式 production warning 或 ranking score。

決策建議：

- `chip_flow` 維持 `BLOCKED`。
- 不接入 `risk_adjusted_score`。
- 不作為正式 `RISK_ALERT`、個人化賣出提醒、減碼提醒。
- 可保留為研究 overlay 或推薦理由文字，例如：「籌碼偏擁擠，需搭配價格/排名轉弱觀察」。
- 主線若要繼續找「該獲利了結」訊號，建議轉向價格/排名/量能/漲幅過熱後失速，而不是繼續硬挖單一籌碼條件。

一句話版：

> 籌碼資料有參考價值，但本次 replay 沒有證明它夠格單獨成為正式提醒；更嚴格的 composite 訊號方向較像風險，但目前命中樣本太少，不能產品化。

## 2. Root Question

使用者原始問題：

- 大盤下跌時，很多之前的飆股也跌，系統有沒有提醒？
- 是否能透過籌碼看出該先獲利了結？
- 主要訊號是籌碼漸漸不見、外資偷賣、融資變低或變高、散戶變多？
- 若目前只有程式雛形，能否補到更具體、有結論？

本輪實際回答的研究問題：

> `三大法人 + 融資融券` 能不能形成一個可靠的 warning-only shadow signal，用來提醒 TopN 標的可能該獲利了結？

## 3. 本輪做了什麼

### 3.1 資料與整合

已補上的能力：

- `app/finmind_integrator.py`
  - 整合三大法人買賣超。
  - 整合融資融券。
  - 保留 `institutional_available`、`margin_available`。
  - 缺資料不填成 0，避免把「沒抓到」誤判為「法人沒有買賣」。

- `scripts/build_chip_flow_materialized_features.py`
  - 可 materialize chip-flow shadow CSV。
  - 支援 FinMind 抓取、cache、seed CSV。
  - 支援 `--seed-csv`、`--cache-dir`、`--refresh-cache`。
  - seed 完全覆蓋時不初始化 FinMind client，避免不必要打 API。

主要 materialized artifacts：

- `data/raw/chip/chip_flow_materialized_top3_60d_2026-06-07.csv`
  - 60 個 target dates × Top3 universe。
  - 140 檔股票。
  - 8400 rows。
  - 日期範圍到 2026-05-15。

- `data/raw/chip/chip_flow_materialized_top10_20d_2026-06-08.csv`
  - 20 個 target dates × Top10 universe。
  - 142 檔股票。
  - 2840 rows。
  - `institutional_rows = 2840`。
  - `margin_rows = 2756`。
  - 日期範圍到 2026-05-15。

### 3.2 Warning-only replay

已補上的 replay：

- `scripts/build_chip_warning_shadow_report.py`
  - 測試單純籌碼條件：
    - 外資 5D 賣超。
    - 融資 5D 增加。
    - 外資賣且融資增。
    - 融資單獨增加。
    - 外資單獨賣。
    - supportive 組。

- `scripts/build_chip_warning_replay_aggregate.py`
  - 彙總多份 shadow replay。
  - 按 `(date, stock_id)` 去重。
  - 重新計算 group outcomes，避免重複樣本膨脹。

彙總結果：

- artifact: `artifacts/model_experiments/chip_warning_replay_aggregate_2026-06-08.json`
- markdown: `artifacts/model_experiments/chip_warning_replay_aggregate_2026-06-08.md`
- decision: `PARTIAL_MONITOR_ONLY`
- production_status: `BLOCKED`
- raw observations: `544`
- duplicate observations: `150`
- deduped observations: `394`
- target date count: `68`

5D outcome 重點：

| Group | 5D count | 5D avg return | 5D median | Negative rate | Loss > 5% |
| --- | ---: | ---: | ---: | ---: | ---: |
| `CHIP_RISK` | 60 | +1.53% | -0.56% | 51.67% | 31.67% |
| `CHIP_SUPPORTIVE` | 80 | +2.33% | +0.37% | 48.75% | 31.25% |
| `MARGIN_UP_ONLY` | 179 | +3.31% | +0.66% | 44.13% | 21.23% |
| `FOREIGN_SELL_ONLY` | 25 | +1.73% | +1.58% | 40.00% | 28.00% |

解讀：

- `CHIP_RISK` 比 `CHIP_SUPPORTIVE` 弱，但差距只有約 0.8 個百分點，且仍是正報酬。
- `MARGIN_UP_ONLY` 不是壞訊號，反而在本樣本中 5D 平均報酬最高。
- `FOREIGN_SELL_ONLY` 也沒有明確失效。
- 因此不能把「外資賣」、「融資增」、「外資賣且融資增」單獨當成正式獲利了結提醒。

### 3.3 Composite warning replay

已補上的 composite 測試：

- `scripts/build_chip_composite_warning_report.py`
  - 測試「籌碼風險 + 價格/排名轉弱」是否比較接近可用 warning。
  - composite 條件包含：
    - 外資 5D 賣超。
    - 融資 5D 增加。
    - 收盤低於 MA10 / MA20。
    - trailing 5D 非正報酬。
    - 長上影線。
    - 排名惡化 2 名以上。

Top10 20D composite 結果：

- artifact: `artifacts/model_experiments/chip_composite_warning_report_top10_20d_2026-06-08.json`
- markdown: `artifacts/model_experiments/chip_composite_warning_report_top10_20d_2026-06-08.md`
- decision: `NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL`
- production_status: `BLOCKED`
- observations: `196`
- target date count: `20`

Group counts：

| Group | Count |
| --- | ---: |
| `COMPOSITE_RISK` | 3 |
| `CHIP_RISK_ONLY` | 31 |
| `TECH_WEAK_ONLY` | 15 |
| `NO_COMPOSITE_RISK` | 147 |

5D outcome 重點：

| Group | 5D count | 5D avg return | 5D median | Negative rate | Loss > 5% |
| --- | ---: | ---: | ---: | ---: | ---: |
| `COMPOSITE_RISK` | 3 | -3.08% | -1.72% | 66.67% | 33.33% |
| `CHIP_RISK_ONLY` | 31 | -0.39% | 0.00% | 48.39% | 35.48% |
| `TECH_WEAK_ONLY` | 15 | +7.06% | +4.14% | 20.00% | 0.00% |
| `NO_COMPOSITE_RISK` | 147 | +0.03% | -0.63% | 52.38% | 31.29% |

解讀：

- `COMPOSITE_RISK` 看起來最像風險，5D 平均為 -3.08%。
- 但命中只有 3 筆，不足以進入正式 warning channel。
- `TECH_WEAK_ONLY` 在這批樣本反而強，代表價格/排名轉弱條件本身也需要重新校準，不能直接硬接。
- composite 的方向值得「日後更大樣本研究」，但不是本輪可推 production 的結論。

## 4. Feature Gate / Readiness 狀態

feature gate artifact：

- `artifacts/feature_experiment_gate_2026-06-08.json`

結果：

- `candidate_count = 8`
- `ready_for_shadow_count = 3`
- `blocked_count = 5`
- `chip_flow` 在 blocked list。
- `production_promotion_allowed = false`

readiness artifact：

- `artifacts/model_experiments/chip_flow_readiness_report_2026-06-08.json`
- `artifacts/model_experiments/chip_flow_readiness_report_2026-06-08.md`

readiness decision：

- status: `NOT_READY_FOR_PRODUCTION`
- shadow_status: `BLOCKED`
- production_status: `BLOCKED`

readiness blocker：

- feature gate shadow_status = `BLOCKED`
- warning-only replay not stable enough。
- composite warning replay not stable enough。
- FinMind failures are skipped, so absence cannot be interpreted as zero flow。
- warning-only replay sample is not stable enough for warning channel。

## 5. 目前對「融資到底什麼情況」的回答

本輪資料不支持「融資增加 = 危險」。

在 aggregate replay 中：

- `MARGIN_UP_ONLY`
  - count: 179
  - 5D avg return: +3.31%
  - negative rate: 44.13%

這代表在 TopN 強勢股樣本裡，融資增加可能同時代表追價資金進場、行情擴散或強勢延續，不一定是倒貨前兆。

比較合理的產品表述：

- 融資增加不是單獨賣出訊號。
- 外資賣 + 融資增也不是單獨賣出訊號。
- 若要把融資納入提醒，必須搭配更嚴格的條件，例如價格失速、排名惡化、量能退潮、乖離過熱後跌破短均線等。

## 6. 可用與不可用

### 可用

- 研究用 warning overlay。
- 產生輔助說明文字。
- 做下一輪更大樣本 composite replay 的基礎資料管線。
- 做 chip data contract / runtime coverage / smoke verifier。

### 不可用

- 不可進 production ranking score。
- 不可作正式賣出、減碼、獲利了結提醒。
- 不可把缺資料填 0 後解讀成法人未買賣。
- 不可把 `融資增加` 或 `外資賣` 單獨包成紅燈。

## 7. 建議給主線的決策

建議主線直接接受以下狀態：

```text
chip_flow.status = BLOCKED
chip_flow.production_promotion_allowed = false
chip_flow.product_surface = research_overlay_only
chip_flow.warning_channel = do_not_promote
```

主線若要繼續解「獲利了結」問題，建議新開一條 exit-signal 主線，不要再沿用 chip_flow 當主軸。

優先研究方向：

1. 價格轉弱
   - 高檔跌破 MA5/MA10。
   - 5D momentum 從強轉負。
   - 高檔長黑 / 長上影。

2. 排名惡化
   - Top10 內排名連續惡化。
   - 從 Top3 掉出 Top10。
   - score momentum 轉負。

3. 量能退潮
   - 價漲量縮後轉跌。
   - 爆量長上影。
   - 成交量高峰後縮量跌破短均。

4. 過熱後失速
   - 短期漲幅過大。
   - 乖離過高。
   - 接著 ranking/price 同步轉弱。

籌碼可作為輔助變數，但不應當成第一順位 exit trigger。

## 8. 驗證紀錄

已通過：

```bash
.venv/bin/python -m py_compile scripts/build_chip_warning_replay_aggregate.py scripts/verify_chip_warning_replay_aggregate.py scripts/build_feature_experiment_gate.py scripts/build_chip_flow_readiness_report.py scripts/verify_feature_experiment_gate.py scripts/verify_chip_flow_readiness_report.py
.venv/bin/python scripts/build_chip_warning_replay_aggregate.py
.venv/bin/python scripts/verify_chip_warning_replay_aggregate.py
.venv/bin/python scripts/build_feature_experiment_gate.py
.venv/bin/python scripts/build_chip_flow_readiness_report.py
.venv/bin/python scripts/verify_feature_experiment_gate.py
.venv/bin/python scripts/verify_chip_flow_readiness_report.py
```

關鍵 verifier 結果：

- `verify_chip_warning_replay_aggregate.py`: OK
- `verify_feature_experiment_gate.py`: OK
- `verify_chip_flow_readiness_report.py`: OK

## 9. 相關程式與 artifact

程式：

- `app/finmind_integrator.py`
- `scripts/build_chip_flow_materialized_features.py`
- `scripts/build_chip_warning_shadow_report.py`
- `scripts/build_chip_warning_replay_aggregate.py`
- `scripts/build_chip_composite_warning_report.py`
- `scripts/build_chip_flow_readiness_report.py`
- `scripts/verify_chip_flow_materialized_features.py`
- `scripts/verify_chip_warning_shadow_report.py`
- `scripts/verify_chip_warning_replay_aggregate.py`
- `scripts/verify_chip_composite_warning_report.py`
- `scripts/verify_chip_flow_readiness_report.py`

證據：

- `artifacts/model_experiments/chip_warning_replay_aggregate_2026-06-08.json`
- `artifacts/model_experiments/chip_warning_replay_aggregate_2026-06-08.md`
- `artifacts/model_experiments/chip_composite_warning_report_top10_20d_2026-06-08.json`
- `artifacts/model_experiments/chip_composite_warning_report_top10_20d_2026-06-08.md`
- `artifacts/model_experiments/chip_flow_readiness_report_2026-06-08.json`
- `artifacts/model_experiments/chip_flow_readiness_report_2026-06-08.md`
- `artifacts/feature_experiment_gate_2026-06-08.json`

資料：

- `data/raw/chip/chip_flow_materialized_top3_60d_2026-06-07.csv`
- `data/raw/chip/chip_flow_materialized_top10_20d_2026-06-08.csv`

## 10. 範圍外提醒

工作區目前有大量既有 dirty / untracked 檔案，並非本輪 chip_flow 研究主線原始範圍。這份交接只對上述 chip_flow 籌碼提醒研究負責。

若主線要處理其他 dirty work，請另開 review / merge-risk / cleanup 主線，不要把那些狀態混入本研究結論。

## 11. 最終交接判定

Root question 已回答。

目前 blocker 不是「資料完全沒有」或「程式沒有雛形」，而是 replay 證據不支持 production promotion。

最小可採納結論：

```text
chip_flow 可保留為研究監控與文字輔助。
chip_flow 不可作正式獲利了結提醒。
若要找正式 exit signal，下一步應轉向 price/rank/volume/overheat reversal。
```

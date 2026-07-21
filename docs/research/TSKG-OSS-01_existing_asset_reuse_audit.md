---
card_id: TSKG-OSS-01
status: DELIVERED_CANDIDATE
operation_level: repo_first_read_only
access_date: 2026-07-20
decision_authority: downstream_adr_or_source_owner_required
---

# TSKG-OSS-01：既有 FinMind／T86 資產沿用盤點

## 1. 結論

TOP10 repo 內已有兩條與三大法人相關、但權利與資料粒度完全不同的路徑。

1. `FinMind` 個股籌碼路徑：`app/finmind_fetcher.py` 透過 `FinMind.data.DataLoader` 抓個股三大法人與融資融券；`app/finmind_integrator.py` 將買賣超 pivot 成 `foreign_buy/trust_buy/dealer_buy`；`app/pipeline/fetch_stage.py` 會在價格 fetch 後嘗試整合，失敗時 skip。這是存在且被 fetch stage 呼叫的 fallback-like ingestion hook，但本次找不到 dedicated verifier、fixture、artifact 或 production source approval。
2. Direct TWSE `T86` market context 路徑：`app/market_context_fetcher.py` 直接呼叫 `https://www.twse.com.tw/rwd/zh/fund/T86`，解析市場總量 `foreign_net/trust_net/dealer_net`，輸出 `artifacts/market_context_YYYY-MM-DD.json`；`scripts/run_automation.py` 會在 daily automation 呼叫；`scripts/verify_market_context_fetcher.py` 有 synthetic verifier；`scripts/build_decision_quality.py` 與 feature experiment gate 會消費 artifact。這是仍在 repo 呼叫鏈上的 market-context shadow/active artifact 路徑，但 source governance 不是本卡可批准，且 `TSKG-MFO-SRC-01` 對免費 T86 ingestion 維持 `KEEP_BLOCKED`。

因此本卡建議：FinMind 與 T86 既有程式都只能作 `REFERENCE_ONLY`，除非後續 ADR/source owner 補齊 production source policy、欄位語意、單位、retention、late correction 與 verifier。不得直接把任一路徑沿用為 TSKG `SecurityFlowObservation` production ingestion。

## 2. 狀態詞彙

| Status | 本卡用法 |
|---|---|
| `ACTIVE` | repo 內有 runtime caller 或 automation path，且有測試或 artifact 消費證據；不代表 source 已核准 |
| `FALLBACK` | 被主要 pipeline 嘗試呼叫，但設計上失敗可 skip，不阻斷核心流程 |
| `SHADOW` | 產物或候選只做背景、研究或 promotion gate，不直接改 ranking/model |
| `DORMANT` | 只有文件或歷史程式存在，找不到目前 caller |
| `BROKEN` | 有明確錯誤或無法滿足最小 contract；本卡未執行外部 fetch，不以外部可達性判斷 |
| `UNKNOWN` | 找不到足夠 caller、test、artifact 或 source approval 證據 |

## 3. 既有資產清單

| Asset | Symbol / API surface | Responsibility | Input | Output | Caller | Test / artifact evidence | Git evidence | Status |
|---|---|---|---|---|---|---|---|---|
| `app/finmind_fetcher.py` | `FinMindFetcher.get_institutional_investors` | 以 FinMind DataLoader 抓單一股票三大法人資料 | `stock_id`, `start_date`, `end_date`, optional token | raw DataFrame，保留 FinMind `date/name/buy/sell` 等欄位 | `app/finmind_integrator.py` | 無 dedicated verifier；`__main__` 會連外，不在本卡執行 | blame 顯示初始 commit `f657245`；log 最近相關 commit 仍是 `f657245` | `FALLBACK` + `NEEDS_VALIDATION` |
| `app/finmind_fetcher.py` | `get_margin_purchase_short_sale` | 抓融資融券 | 同上 | raw DataFrame | 本次 `rg` 未找到 production caller | 無 verifier/artifact | 初始 commit `f657245` | `DORMANT` |
| `app/finmind_integrator.py` | `FinMindIntegrator.integrate_chip_data` | 挑成交額前 N 檔、逐股抓 FinMind、計算 `buy-sell`、pivot 成三大法人欄位並 merge 回價格資料 | price DataFrame with `date/stock_id/volume/close` | price DataFrame plus `foreign_buy/trust_buy/dealer_buy` | `app/pipeline/fetch_stage.py` | 無 dedicated test；缺資料填 0，無 coverage gate artifact | blame 顯示主邏輯初始 commit `f657245` | `FALLBACK` |
| `app/pipeline/fetch_stage.py` | `FetchStage.execute` FinMind block | 價格資料抓取後嘗試整合 FinMind；例外時記 `context['stats']['finmind']={'status':'skipped'}` | historical price df, context dirs/date | enriched df or original df | pipeline stage runtime | 無本卡可重現 verifier；例外設計證明非 hard dependency | FinMind block blame `f657245`，dedupe nearby later changed `814261b` | `FALLBACK` |
| `app/indicators/mixins/volume.py` | `calculate_institutional_indicators` | 若 pivots 內有 `foreign_buy/trust_buy/dealer_buy`，產生 `inst_buy_total`、`inst_buy_ratio_*d`、`trust_buy_days_*d` | TechnicalIndicators pivots | model/ranking candidate feature columns | `app/indicators/core.py::calculate_all_indicators` | 本次未找到 dedicated FinMind feature verifier；缺欄位會 warning skip | 初始 commit `f657245` | `ACTIVE` consumer, source `UNKNOWN` |
| `app/market_context_fetcher.py` | `parse_twse_institutional` | 解析 TWSE T86 response rows，合計市場層級外資、投信、自營商淨額 | T86-like list/table payload | `foreign_net/trust_net/dealer_net` and warnings | `build_market_context` | `scripts/verify_market_context_fetcher.py` synthetic payload 檢查 `institutional_parsed` | commit `61c6d541` 新增 decision-quality / market context path | `ACTIVE` parser |
| `app/market_context_fetcher.py` | `build_market_context` TWSE T86 fetch block | 呼叫 direct T86 URL，將解析結果寫入 market context artifact source status | `trade_date` | `market-context.tw.v1` JSON section `institutional` | `scripts/run_automation.py::_run_market_context`; CLI `python -m app.market_context_fetcher` | verifier monkeypatches `fetch_json`，不連外；artifact path contract documented | commit `61c6d541`; MARKET-CONTEXT docs dated 2026-05-29 | `ACTIVE` + source approval `UNKNOWN/BLOCKED` |
| `scripts/verify_market_context_fetcher.py` | synthetic verifier | 驗證 parser、single-source failure、JSON no-NaN、write roundtrip | synthetic payloads | `artifacts/market_context_fetcher_verification_latest.json` | manually invoked by task docs | explicit checks include `institutional_parsed` and source failure behavior | commit `61c6d541` | `ACTIVE` verifier |
| `docs/References.md` | FinMind / official APIs entries | Reference bibliography only | n/a | external links | docs only | 不等於 approval | initial/reference history through `f657245` | `DORMANT` reference |
| `docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md` | T86 source governance dossier | official-source governance for listed-security institutional flow | public-source research evidence | `KEEP_BLOCKED` decision | downstream TSKG source gate | evidence file exists; no code caller | card delivered 2026-07-20 | `ACTIVE` governance blocker |

## 4. 資料流圖

### 4.1 FinMind 個股籌碼路徑

```text
FetchStage.execute
  -> DataFetcherOrchestrator.fetch_historical_data
  -> FinMindIntegrator()
      -> FinMindFetcher()
          -> FinMind DataLoader taiwan_stock_institutional_investors
      -> raw_chip buy/sell
      -> net_buy = buy - sell
      -> pivot by date/name
      -> foreign_buy / trust_buy / dealer_buy
      -> merge on date, stock_id
  -> TechnicalIndicators.calculate_all_indicators
      -> calculate_institutional_indicators
      -> inst_buy_total / inst_buy_ratio_*d / trust_buy_days_*d
```

判讀：這條路徑是逐股且接在 ETL/indicator surface 上，但抓取端依賴外部 FinMind，測試與 artifact 證據不足；fetch stage 設計成失敗不阻斷價格資料重建。

### 4.2 Direct TWSE T86 market context 路徑

```text
scripts/run_automation.py
  -> python -m app.market_context_fetcher --date <latest_feature_date>
      -> build_market_context
          -> fetch_json(TWSE MI_INDEX)
          -> fetch_json(TWSE /rwd/zh/fund/T86)
          -> parse_twse_institutional
          -> payload["institutional"] foreign_net / trust_net / dealer_net
      -> write_payload artifacts/market_context_YYYY-MM-DD.json
  -> scripts/build_decision_quality.py
      -> market_context_summary(... institutional ...)
  -> scripts/build_feature_experiment_gate.py
      -> market_context candidate readiness
```

判讀：這條路徑已有 synthetic verifier 與 downstream artifact consumers，但資料粒度是市場總量，不是 TSKG `SecurityFlowObservation` 需要的逐證券觀測；source policy 仍未核准。

## 5. 存在／呼叫／測試／production 核准狀態

| Candidate | Existing code | Runtime caller | Test / verifier | Artifact / consumer | Production source approved | Production reuse decision |
|---|---:|---:|---:|---:|---:|---|
| FinMind individual institutional investors | yes | yes, via `FetchStage` | no dedicated verifier found | no durable artifact found | no approval found | `REFERENCE_ONLY` |
| FinMind margin purchase / short sale | yes | no caller found | no | no | no approval found | `DO_NOT_REUSE` until scoped |
| FinMind merged `foreign_buy/trust_buy/dealer_buy` feature columns | yes | yes, if FetchStage succeeds | no dedicated coverage gate | consumed by indicators if columns exist | no approval found | `REFERENCE_ONLY` |
| Indicator institutional features | yes | yes, `calculate_all_indicators` | unknown in this card | feature columns only if input exists | source upstream not approved | `REFERENCE_ONLY` |
| TWSE T86 parser for market aggregate | yes | yes | yes, synthetic verifier | yes, market context artifact | no; `TSKG-MFO-SRC-01` says `KEEP_BLOCKED` | `REFERENCE_ONLY` parser only |
| TWSE T86 direct fetch URL | yes | yes | verifier monkeypatches fetch, does not prove live source | market context artifact path | no; target source governance blocked | `DO_NOT_REUSE` for TSKG ingestion |
| Market context artifact shape/status model | yes | yes | yes | yes | source still blocked | `REUSE` for internal status/error pattern only |

## 6. Reuse matrix for TSKG `SecurityFlowObservation`

| Asset | TSKG mapping | Gap | Decision | Rationale |
|---|---|---|---|---|
| `FinMindFetcher.get_institutional_investors` | Could provide per-security investor rows before normalization | Source approval, token/rate, raw retention, late correction, units, exact investor taxonomy, fixture verifier | `REFERENCE_ONLY` | It has the closest per-security shape but is not source-approved and lacks TSKG contract adapter/tests |
| `FinMindIntegrator.integrate_chip_data` | Could inform normalization from raw investor names to `FOREIGN/INVESTMENT_TRUST/DEALER` | It outputs share-like `foreign_buy/trust_buy/dealer_buy`, while MFO-01 requires integer TWD `net_buy_value_1d`; fills missing data with 0 | `REFERENCE_ONLY` | Useful pattern, unsafe semantics for raw observations |
| `FetchStage` FinMind hook | Could show non-blocking ingestion pattern | TSKG raw observation should fail-loud on contract/source-policy violations; silent skip may hide missing official evidence | `DO_NOT_REUSE` as-is | Keep the idea of isolating optional data, not the behavior |
| `calculate_institutional_indicators` | Could be downstream derived-feature inspiration after MFO-03 | MFO-01 prohibits derived formulas such as 5d/20d flow until owner-approved | `REFERENCE_ONLY` | Do not import into raw observation slice |
| `parse_twse_institutional` | Could inspire robust row/field parsing and warnings | Aggregates market totals, not per-security rows; uses numeric share/count-like values, not guaranteed TWD net value | `REFERENCE_ONLY` | Parser pattern is reusable, data product is not |
| Direct T86 fetch URL in `build_market_context` | None until source approval | `TSKG-MFO-SRC-01` did not find approved free machine distribution; TWSE terms require care | `DO_NOT_REUSE` | Must not be copied into TSKG ETL |
| Market context `SourceStatus` pattern | Could inform provenance/status shape for source-specific adapters | TSKG MFO contract uses fixture provenance/evidence; source status is not a replacement for SourcePolicy approval | `REUSE` for status/error pattern | Internal code pattern only, not source approval |
| `scripts/verify_market_context_fetcher.py` monkeypatch style | Could inform synthetic-only parser tests | Need TSKG-specific official-shaped fixtures and closed schema gates | `REUSE` as test pattern | It avoids external API calls and checks single-source failure |
| `docs/References.md` links | Bibliography for later ADR | Links do not establish approval | `REFERENCE_ONLY` | Useful for navigation only |
| `TSKG-MFO-SRC-01` source dossier | Blocks or informs ADR/source-owner decision | Still needs owner action for target distribution | `NEEDS_VALIDATION` by source/compliance owner | Existing conclusion is `KEEP_BLOCKED` |

## 7. Production-readiness判定

`已有程式`：FinMind fetcher/integrator、FetchStage hook、indicator consumer、TWSE T86 parser/fetcher、market context verifier all exist.

`可執行`：Market context verifier is designed to run offline with synthetic fetch monkeypatch. FinMind paths likely import through requirements, but live execution would call external FinMind and was forbidden here.

`已測試`：Direct T86 parsing/status behavior has a synthetic verifier. FinMind ingestion and normalization do not have a dedicated test found by repo search in this card.

`已核准 production source`：No. FinMind has a dependency and reference link but no repo SourcePolicy approval found. TWSE T86 source governance explicitly remains `KEEP_BLOCKED` in `TSKG-MFO-SRC-01`.

## 8. 下一張 synthesis 卡問題

1. TSKG 是否要採用 FinMind、TWSE Data E-Shop、官方 OpenAPI、人工 report 或完全不同 source 作 source candidate？
2. `SecurityFlowObservation.net_buy_value_1d` 要求 TWD；現有 FinMind/T86 路徑的欄位單位與買賣超口徑如何合法且可重現地換算？
3. 若 source 是 T86 paid file，逐證券欄位、ETF/filter、鉅額含否、每日產製時間與 late correction 要如何寫入 SourcePolicy？
4. 缺資料時 TSKG adapter 應 fail loud、tombstone、stale，還是允許 partial day？不得直接沿用 FetchStage 的 silent skip。
5. 是否需要保留 raw response、row hash、snippet、license snapshot、request metadata 與 parser version？保存期限與刪除權限誰批准？
6. 現有 market context artifact 是市場總量背景；是否與 TSKG per-security observation 分開，避免在 ADR 中混用？
7. FinMind investor names、Dealer split 與 TSKG enum 的 mapping 是否需要 fixture-backed source-specific adapter？

## 9. 本卡未做

- 未執行任何會連到 FinMind、TWSE、TPEx、TAIFEX 或其他外部金融資料服務的程式。
- 未修改 `app/**`、`scripts/**`、`tests/**`、`config/**`、requirements、runtime、API、UI 或 TSKG contract。
- 未下載、更新或驗證 live market artifact。
- 未批准任何 source，也未宣稱可直接進 production。

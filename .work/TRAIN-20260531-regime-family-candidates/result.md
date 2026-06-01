# Result

## 目前結果
已完成第一版 regime family training candidate 研究，並追加 `BIG_BULL` research-only sealed replay。

## 結論
- `HIGH_CHOPPY`：`MONITOR_ONLY`。`family_only_training` 有初步正向，但 family 日期只有 14 天，低於 gate 18 天，不可 promotion。
- `BIG_BULL`：第一關 `PROMOTE_CANDIDATE`，但 sealed replay 降回 `MONITOR_ONLY`。原因不是 Top10 沒效，而是 AUC delta 小輸 global baseline，未通過預註冊分類 gate。

## 修正說明
原本 `BIG_BULL` 定義過度偏向「全市場廣度一起強」，會把近半年這種權值 / 科技主流帶動的大牛市誤判成 `RISK_OFF`。已改成以 rolling value-weight return、主流族群成交占比、強勢族群占比、RSI 與 breakdown ratio 判斷 index-led bull。

## Taxonomy 收斂
- base regime 固定為 8 個 label：`BROAD_RISK_ON`、`NARROW_LEADER`、`CHOPPY_RANGE`、`RISK_OFF`、`PANIC_SELLING`、`EARLY_REVERSAL`、`MIXED_NEUTRAL`、`UNKNOWN`。
- `BIG_BULL` / `HIGH_CHOPPY` 不再視為新的市場 preset，而是可重疊的 regime family tag。
- 目前 `HIGH_CHOPPY` 14 天、`BIG_BULL` 168 天、重疊 12 天；語意是「大牛市裡的高檔震盪段」。
- verifier 已要求 family tag 清單固定，不允許 artifact 偷新增 tag。

## 關鍵數字
- 近半年 value-weight 累積報酬：`+354.26%`。
- 近半年 equal-weight 累積報酬：`+17.58%`。
- 近半年平均 top sector 成交占比：`74.10%`。
- 近半年平均 breadth_ma20：`22.31%`。
- `BIG_BULL` candidate AUC delta vs global：`+0.019166`。
- `BIG_BULL` candidate Top10 return delta vs global：`+0.015028`。
- `BIG_BULL` candidate Top10 uplift：`+0.027525`。
- `BIG_BULL` sealed replay：2026-02-06 ~ 2026-05-15，48 個 family 日期。
- `BIG_BULL` sealed family-only AUC：`0.641350`；global baseline AUC：`0.643699`；AUC delta：`-0.002349`。
- `BIG_BULL` sealed family-only Top10 return：`+5.2331%`；global baseline Top10 return：`-0.1656%`；Top10 return delta：`+5.3987%`。
- `BIG_BULL` sealed family-only Top10 uplift：`+4.1847%`。

## 解讀
這輪訊號比較像「Top10 排名有用，但整體分類模型未穩定勝過 global baseline」。依照不開後照鏡原則，不能因為 Top10 亮眼就回頭刪掉 AUC gate；只能把它列成下一輪假設，另外做 ranking/replay-oriented 實驗。

## 多視窗穩定性
- 40D / 60D / 80D / 100D sealed replay 全部維持 `MONITOR_ONLY`。
- AUC delta 非負比例：`0.0`，所以模型替換路徑 blocked。
- Top10 uplift 正向比例：`1.0`。
- Top10 return delta 正向比例：`0.75`。
- 平均 Top10 uplift：`+3.0543%`。
- 平均 Top10 return delta vs global：`+1.8823%`。

結論：`BIG_BULL family_only_training` 不適合直接取代正式模型，但值得開下一輪「ranking / replay 取向」候選，驗證是否只在大牛市用 family model 排 Top10，而不是拿它當全體分類模型。

## 證據
- `uv run --with-requirements requirements.txt python scripts/build_market_regime_history.py --output artifacts/market_regime_history_2026-05-31.json`：OK。
- `uv run --with-requirements requirements.txt python scripts/research_regime_family_training_candidates.py --date 2026-05-31 --market-regime-history artifacts/market_regime_history_2026-05-31.json --folds 4 --embargo-trade-days 10 --top-n 10 --num-boost-round 120 --output artifacts/model_experiments/regime_family_training_candidates_2026-05-31.json`：OK。
- `uv run --with-requirements requirements.txt python scripts/verify_regime_family_training_candidates.py --artifact artifacts/model_experiments/regime_family_training_candidates_2026-05-31.json`：OK。
- `uv run --with-requirements requirements.txt python scripts/research_regime_family_sealed_replay.py --date 2026-05-31 --market-regime-history artifacts/market_regime_history_2026-05-31.json --candidate-artifact artifacts/model_experiments/regime_family_training_candidates_2026-05-31.json --families BIG_BULL --sealed-trade-days 60 --embargo-trade-days 10 --top-n 10 --num-boost-round 120 --output artifacts/model_experiments/regime_family_sealed_replay_2026-05-31.json`：OK，decision=`MONITOR_ONLY`。
- `uv run --with-requirements requirements.txt python scripts/verify_regime_family_sealed_replay.py --artifact artifacts/model_experiments/regime_family_sealed_replay_2026-05-31.json`：OK。
- `uv run --with-requirements requirements.txt python scripts/build_regime_family_sealed_stability_report.py --date 2026-05-31 --family BIG_BULL --artifact 40d=artifacts/model_experiments/regime_family_sealed_replay_big_bull_40d_2026-05-31.json --artifact 60d=artifacts/model_experiments/regime_family_sealed_replay_2026-05-31.json --artifact 80d=artifacts/model_experiments/regime_family_sealed_replay_big_bull_80d_2026-05-31.json --artifact 100d=artifacts/model_experiments/regime_family_sealed_replay_big_bull_100d_2026-05-31.json --output artifacts/model_experiments/regime_family_sealed_stability_2026-05-31.json`：OK，decision=`MODEL_PROMOTION_BLOCKED`，ranking_decision=`RANKING_FOLLOWUP_CANDIDATE`。
- `uv run --with-requirements requirements.txt python -m py_compile scripts/research_regime_family_training_candidates.py scripts/verify_regime_family_training_candidates.py scripts/research_regime_family_sealed_replay.py scripts/verify_regime_family_sealed_replay.py scripts/build_regime_family_sealed_stability_report.py`：OK。
- `git diff --check`：OK。

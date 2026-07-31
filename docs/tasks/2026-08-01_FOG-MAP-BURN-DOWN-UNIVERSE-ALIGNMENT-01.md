---
id: FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01
status: READY_FOR_INDEPENDENT_REVIEW
type: repair
ownership: executor
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 失敗已連續開啟live research circuit，且跨current topic universe、歷史weekend rollup、map verifier與handoff exit契約；需先釐清真實partial-classification語意再最小修正
chain_id: FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT
cycle: 1
code_base_sha: a30ca944676ce7f780d7c0cead819df89f6ea09d
---

# FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01

## Role

你是本卡 Executor，不是 Reviewer、mainline Integrator或live operator。

- 在獨立clean worktree／branch先建立RED，再做最小實作與驗證。
- 交付單一candidate commit後停在`READY_FOR_INDEPENDENT_REVIEW`。
- 不得自審、整合、deploy、恢復或操作live runtime。

## Root question

當continuous topic supply使current registry比最近一份weekend burn-down rollup多出
topics時，research map如何誠實表示「歷史已分類子集合＋新增未分類delta」，且不把
有效的partial classification誤判為整條Fog handoff失敗？

## Preserved failure evidence

2026-08-01自然排程於00:07:08啟動，研究本身成功選出並完成1個development
topic；daily quota artifact為`OK`，quota verifier為`PARTIAL_NO_MORE_WORK`且
`failed_count=0`。其後research map verification唯一失敗檢查為：

- check：`burn_down_counts_classify_full_universe`
- current `expanded_universe_total`：`2,921,184`（322 topics）
- rollup `full_universe_total`／`classified_total`：`2,866,752`
- delta：`54,432`（6 topics）

worker對相同失敗重試3次後於00:09:59建立
`logs/fog_research_retry_20260801.state`，`circuit_open=1`。

主要證據：

- `artifacts/research_map/research_fog_map_verification_latest.json`
- `artifacts/research_map/research_fog_map_2026-08-01.json`
- `artifacts/autonomous_research/autonomous_research_daily_quota_2026-08-01.json`
- `artifacts/autonomous_research/daily_research_quota_verification_latest.json`
- `logs/fog_research_retry_20260801.context.log`

## Requirements

- `FR-MAP-01`：current map的`expanded_universe_total`是當下registry與canonical
  dimension contract算出的唯一current universe authority。
- `FR-MAP-02`：較舊、較小但內部一致的weekend rollup只能證明其實際分類範圍；
  不得被描述成已分類current full universe，也不得把新增delta偽造進任何category。
- `FR-MAP-03`：stale-smaller rollup的map輸出必須滿足：
  `full_universe_total == current expanded_universe_total`、
  `sum(counts) == classified_total`、`0 <= classified_total <= full_universe_total`、
  `classified_pending == full_universe_total - classified_total`。
- `FR-MAP-04`：research map verifier須接受上述誠實partial classification；同時對
  negative pending、classified超過current universe、category sum不守恆或
  source scope不明確保持fail closed。
- `FR-MAP-05`：有效的stale-smaller rollup不得使
  `scripts/run_daily_research_quota.sh`僅因map verification而exit 1；不得以
  放寬所有verification、吞錯或固定回傳0達成。
- `SC-MAP-01`：同scope且完整分類的rollup仍通過，顯示的classified progress為100%。
- `SC-MAP-02`：current topic universe與base／expanded／executed progress既有契約
  不退化，production ranking、model、promotion與closed/sealed registry零改動。

## Ranked hypotheses

1. `latest_weekend_rollup_path()`在當日rollup不存在時回退到最近歷史rollup，
   `build_burn_down_progress()`又直接採用該rollup的`full_universe_total`；current
   registry新增6 topics後，map producer與verifier使用不同scope authority。
2. verifier把「burn-down來源當時已完整分類」誤寫成「對current universe仍須完整
   分類」，缺少合法partial delta契約。
3. 若rollup counts本身不守恆，僅調整verifier會掩蓋真正資料錯誤；因此修正必須
   同時保留category conservation negative tests。

## Slices

### `SLICE-MAP-RED`

- `traces_to`: FR-MAP-01, FR-MAP-02, FR-MAP-03, FR-MAP-04
- `blocked_by`: none
- 先以public producer／verifier seam建立單一最小RED fixture：歷史rollup覆蓋
  `2,866,752`，current expanded universe為`2,921,184`。
- RED必須因本次scope mismatch症狀失敗，不得以缺fixture、import error或現成live
  circuit檔案作為RED。

### `SLICE-MAP-GREEN`

- `traces_to`: FR-MAP-01, FR-MAP-02, FR-MAP-03, FR-MAP-04, FR-MAP-05
- `blocked_by`: SLICE-MAP-RED
- 最小修正producer與verifier的current-universe／classified-subset契約；不得改變
  topic供應、dimension multiplier或worker retry次數。

### `CHECKPOINT-MAP`

- `traces_to`: SC-MAP-01, SC-MAP-02
- `blocked_by`: SLICE-MAP-GREEN
- 驗證完整分類、合法partial、新增delta、over-classified、count-sum mismatch與
  既有Fog map suites；再跑full suite、compile、DBG audit、allowlist與
  `git diff --check`。

Frontier：`SLICE-MAP-RED`。

## Exact changed-file allowlist

- 本卡狀態欄位
- `app/research/fog_map_domain.py`
- `scripts/build_research_fog_map.py`
- `scripts/verify_research_fog_map.py`
- `tests/test_research_fog_map_refactor.py`
- `tests/test_research_fog_map_burn_down.py`
- `docs/evidence/FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01/**`
- `.work/FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01/**`

若根因要求allowlist外檔案，停止並回報scope request；不得自行擴張。

## Forbidden

- 清除、旋轉、覆寫或刪除任何`fog_research_retry_*.state`／context。
- LaunchAgent load／unload／bootstrap／bootout／kickstart／restart或修改plist。
- 人工live Fog run、`--execute` probe、手動排程或deploy。
- 改topic供應、eligibility、queue ownership、retry上限、backoff、dimension values／
  multiplier，或以縮小current universe規避失配。
- 將未分類delta計入任一既有category，或把verification全面改成warning／永遠成功。
- 修改ranking、model、weights、promotion或closed／sealed registry。
- merge／push `main`、建立PR、cleanup任何thread／branch／worktree。

## Phase 0 RED

Production code修改前保存：

1. producer在stale-smaller rollup下錯誤沿用舊`full_universe_total`，使新增delta
   不可見或pending為0。
2. verifier對誠實partial classification錯誤回傳FAILED。
3. negative fixture證明over-classified或count-sum mismatch仍必須FAILED；不得先綠。

Evidence：

`docs/evidence/FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01/verification.md`

## Verification

- 精準RED／GREEN tests：producer與verifier public seam。
- `pytest`受影響Fog map／refactor suites。
- `.venv/bin/python -m pytest`
- `.venv/bin/python -m py_compile`所有changed Python files。
- `rg -n "DBG|DEBUG|pdb|breakpoint\\("` changed code／tests，預期無暫留debug碼。
- exact allowlist audit與`git diff --check`。

禁止使用live circuit recovery或人工run作candidate驗證；runtime acceptance由主線在
獨立Review、整合後等待自然排程執行。

## Candidate exit

只交付：

- exact base／candidate SHA
- FR／SC → RED → GREEN對照
- changed files與allowlist audit
- targeted／full驗證結果與remaining risks
- `READY_FOR_INDEPENDENT_REVIEW`

不得自審、整合、deploy、清circuit或宣稱live流程已恢復。

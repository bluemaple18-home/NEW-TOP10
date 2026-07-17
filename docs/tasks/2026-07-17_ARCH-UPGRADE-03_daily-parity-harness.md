---
id: ARCH-UPGRADE-03
status: blocked
type: implementation
priority: P0
thickness: strict
model: gpt-5.6-sol
reasoning: high
model_reason: 每日報牌 parity、失敗語意與 artifact contract 具高回退成本。
---

# Production daily 與 Daily V2 parity harness

## 目標

在隔離資料與 artifact root 中，以同一 run date/input 比較現行 production runner 與 Daily V2，不切換正式排程。

## 依賴

- blocking edges：`ARCH-UPGRADE-01`。
- frontier：01 完成後，可與 02 並行研究，但由單一 writer 依序提交。

## Parity contract

- step coverage、命令展開、輸入／輸出、日期、status、failure、timeout、resume、publish-ready 全部比較。
- mismatch taxonomy：`expected_difference/contract_gap/data_mismatch/status_mismatch/failure_semantics/unsafe_side_effect`。
- 不使用固定 0.8/0.85 分數；只輸出實際 signals 與 blocker。
- 禁止 live send、production artifact overwrite 與 workflow→manual 自動 fallback。

## 可改範圍

- `app/workflows/` parity/comparison contract。
- `scripts/run_daily_v2_parity.py`
- `scripts/verify_daily_v2_parity.py`
- `tests/test_daily_v2_parity.py`
- isolated fixture/config/docs。

## 驗收

- success、stale ranking、timeout、resume、partial output、publish-ready mismatch 均有測試。
- parity run 只能寫 temp 或明確 shadow root。
- 現行 production entrypoint 保持不變。

## Evidence

`.work/ARCH-UPGRADE-03/evidence/`

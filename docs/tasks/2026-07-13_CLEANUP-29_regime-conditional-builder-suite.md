# CLEANUP-29｜Regime conditional builder suite 收斂

- status: ready
- priority: P1
- task thickness: standard
- blocked_by: CLEANUP-28 已驗收

## 目標

把兩支 regime-conditional research builder 收斂為 `scripts/build_regime_conditional_suite.py` 的具名 profile／stage，同時逐項保留既有 JSON、CSV、Markdown、console、exit code 與 default path 語意。只有 parity 與 consumer gate 全通過才退休舊入口。

## 預計範圍

- 新增 `scripts/build_regime_conditional_suite.py`
- 新增 `tests/test_regime_conditional_suite.py`
- 更新 `config/script_lifecycle.yaml`
- parity 與 consumer gate 通過後才刪除：
  - `scripts/build_regime_conditional_shadow_rankings.py`
  - `scripts/build_regime_conditional_hybrid_report.py`
- 證據：`.work/CLEANUP-29/evidence/parity.json`、`status.md`、`result.md`

## 必須保留的 profiles

- `shadow_rankings`
  - production／shadow ranking 日期交集與 BIG_BULL 路由
  - 每日 `ranking_*.csv` 的欄位、排序、UTF-8 BOM、內容與來源標記
  - `regime_conditional_shadow_ranking.json` 的完整 payload、default summary path、console 與 exit code
- `hybrid_report`
  - capital matrix、summary、decision、missing 與 research-only boundary
  - JSON 與同名 Markdown 完整輸出
  - default output path、console 與 exit code

## 明確保留，不納入本卡

- `scripts/verify_regime_conditional_hybrid_report.py`
- `scripts/verify_regime_conditional_shadow_rankings.py`
- 所有 training-candidate risk builder／verifier
- 既有研究 artifact 與研究結論

## 不可改

- 每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation
- 不重新產生正式研究 artifact
- 不改 regime 定義、BIG_BULL 判定或 production/shadow routing policy
- 不以共用 helper 改變缺檔、unsupported family、空日期交集、failed payload 或例外語意
- 不刪除有 active repo/runtime consumer 或無等價替代證據的入口

## 契約與驗收

- TDD：先做 old/new parity 紅燈，再做最小實作。
- parity 至少鎖定：
  - 兩 profile 完整 normalized JSON payload（只排除 `generated_at`）
  - `shadow_rankings` 每支 CSV 的 bytes／欄位／列順序與 CLI 行為
  - `hybrid_report` JSON、Markdown、default path、console 與 exit code
  - valid 與 failure／edge fixture；unsupported family 的例外型別與訊息不得漂移
- 最終測試不得 import 已刪除舊模組；使用 frozen golden hash 或等價 durable contract。
- 先重查 repo/runtime consumer；未通過時保留舊入口，不可半套退休。
- 通過後跑 reference/lifecycle strict audits、focused tests、完整 pytest、`git diff --check` 與每日四檔 hash gate。
- 不提交大型 raw audit JSON；只保留精簡 parity 與驗收摘要。

## 回報

單一 atomic commit，不 merge、不 push；主線讀實際 diff 與證據後才整合，canonical 驗收通過即封存任務並回收 worktree。

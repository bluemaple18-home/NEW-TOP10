# REFACTOR-10｜Research Map Contract 依賴方向修復

- status: ready
- priority: P1
- task thickness: standard

## 目標

把 research map 的共用 contract 移到 `app/research`，消除 `app.research → scripts.research_map_contract` 的反向依賴；所有既有 script import 與 artifact schema 必須相容。

## 依賴與 frontier

- 依賴：REFACTOR-05 已完成 Fog Map 模組邊界。
- blocker：無。
- frontier：可立即開工。

## 可改檔案

- `app/research/map_contract.py`（可新增）
- `app/research/fog_map_domain.py`
- `scripts/research_map_contract.py`
- `scripts/build_research_fog_map.py`
- `tests/test_research_map_contract_boundary.py`（可新增）
- 必要的既有 research-map contract tests/verifier
- 本卡 status/result

## 不可改

- JSON／JSONL schema、combo id、dimension grid、排序與狀態語意
- daily、ranking、model、通知、launchd
- production artifacts

## 實作契約

1. `app/research/map_contract.py` 成為唯一實作 source of truth。
2. `scripts/research_map_contract.py` 保留薄 compatibility re-export，既有 `from research_map_contract import ...` 不得失效。
3. `app/research/fog_map_domain.py` 與新式 adapter 只能 import `app.research.map_contract`。
4. 以 public symbol／fixture 對照證明舊新 API、combo ids、schema payload、JSONL round-trip 等價。
5. 不新增第二份常數或複製演算法。

## 驗收

- `rg` 不再出現 `app/*` import `scripts.research_map_contract`。
- 既有 Fog Map 與 v2 schema verifier 通過。
- compatibility import subprocess 通過。
- 全部 targeted tests 與 `git diff --check` 通過。

## 回報

建立單一 atomic commit；回報 SHA、相容證據與剩餘風險，不 merge、不 push。

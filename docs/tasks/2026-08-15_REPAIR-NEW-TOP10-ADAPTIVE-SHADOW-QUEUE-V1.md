---
id: REPAIR-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: repair
priority: P1
role: repair
cycle: 9
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: fixed-contract strict repair for two reproducible P1 path and provenance boundary failures
date: 2026-08-15
source_sha: 8915a382a93d512235915a5400edfc78e62ea238
review_sha: d72dc4913b8a3aba429e046e80fb2c0e25832fe3
production_change_allowed: false
evidence_path: docs/evidence/REPAIR-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1/
---

# 修復 Adaptive Research Shadow Queue 邊界缺陷

## 目標

關閉 Reviewer 對 `8915a38` 提出的兩個 P1，使 Card B 只能從固定 committed replay evidence 與 policy 建立 shadow-only projection，並在任何非法輸入或輸出產生副作用前 fail closed。

## 固定 Findings

### P1-OUTPUT-PATH-BOUNDARY

- `--output-root` 目前可寫入 repo 外 absolute path、`../` traversal 與 `artifacts/autonomous_research` canonical artifact space。
- 必須在 `mkdir`、讀取 canonical queue、建立 projection 或任何寫入前驗證 output root。
- 正式 CLI output 必須綁定 Card B committed evidence directory；拒絕 absolute／traversal／symlink escape、canonical artifact alias與其他未核准位置。
- 非法路徑必須 controlled fail，目標不存在或保持原狀。

### P1-UNCOMMITTED-INPUT-AUTHORITY

- builder／verifier 目前接受 caller-controlled external `--bundle`、`--manifest`、`--policy`。
- 外部 JSON copy可通過 verifier；任意 policy priority band／action亦可產生 `PASS`。
- 正式 CLI 必須綁定固定 repo-relative committed bundle、manifest與policy，並驗證預期內容 hash／互相引用；外部、traversal、symlink、stale或內容漂移一律 fail closed。
- `priority_bands` 與 `actions` 必須是 committed policy允許的 exact schema／enum，不得接受任意新 band、action或未回測權重。

## Allowlist

- `app/research/adaptive_shadow_queue.py`
- `scripts/build_adaptive_shadow_queue.py`
- `scripts/verify_adaptive_shadow_queue.py`
- `tests/test_adaptive_shadow_queue.py`
- 本任務卡與 `docs/evidence/REPAIR-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1/`

不得修改 committed projection／comparison／receipt、replay bundle／manifest、canonical queue、manager、scheduler、ranking、model、signals、promotion或 production config。

## 驗收

1. 原 committed projection／comparison／receipt與獨立 rebuild保持 byte／identity／order／semantic hash一致。
2. builder對 repo 外 absolute、traversal、symlink escape及 canonical artifact alias，在任何 mkdir／write前 controlled fail且零副作用。
3. builder與verifier對 external／traversal／symlink bundle、manifest、policy均 fail；同內容 copy也不得取得 `PASS`。
4. stale或內容漂移的 committed-path bundle／manifest／policy fail；mutated priority band／action即使其餘 hash重算亦 fail。
5. 合法固定 paths仍可 build／verify；23 targeted tests、self-test、committed verifier、py_compile與`git diff --check`全綠。
6. canonical queue／manager／scheduler／production before／after hash與diff為零；`next_action_queue.json`缺失仍屬 PRE-EXISTING，不得補造。

## 邊界與停損

- 不 merge、push、deploy、啟 scheduler、live或 production write。
- 先以 CodeGraph取得 affected symbols；無結果才對固定 candidate限域 `rg`。
- 只修兩個固定 P1與必要 regression tests，不重寫 priority算法、不調權重。
- 若固定 committed path/hash契約需要改 schema或既有 evidence內容，立即停止並回報 scope fork。
- 完成後提交單一 repair candidate SHA，保留完整 repro與驗證 evidence，交回同一 Reviewer thread targeted re-review。

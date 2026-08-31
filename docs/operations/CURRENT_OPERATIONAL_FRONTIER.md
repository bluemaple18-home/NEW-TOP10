# NEW-TOP10 Current Operational Frontier

更新：2026-08-31

## Current state

- `#10`：等待 **2026-08-31 17:30（Asia/Taipei）natural-run observation**；在 observation 完成前不宣稱 close 或 promotion。
- `#9`：`OPEN / LONG-TERM HARDENING`。它不阻擋 read-only A0；Research lane（含 A0/research）不得執行 scheduler、publish 或 production mutation。#9 未來若需 operational hardening，須另行取得對應授權。
- Research Spine：`#2 A0 = COMPLETE / ACCEPTED`；`#3 A1 = COMPLETE / MAINLINE_ACCEPTED`，已隨 PR #12 merge 進入 `main@0b39937399eddd0535372ece51ddc25bc38fe6a6`；`#4 A2 = COMPLETE / MAINLINE_ACCEPTED / DIRECT_FF_MAIN`，原 candidate `3f7347f30b274201e5c66f649e5919de16d1f6e9` 的 run artifact `topic_runs` membership omission／duplicate P1 已修復於 `main@5edd87e7df75bb44517f6c2b46d48780cf3476f2`，無 PR直接 fast-forward，獨立 fixed-SHA re-review=`GO / no P0/P1`、驗證=`149 passed`、`git diff --check` pass。Issue #4 已 `CLOSED / REMOTE_CLOSEOUT_RECONCILED`。Owner 已明示 admission `#5 A3`；A3 implementation 與 `aea377e` Review 四項 P1 repair 已完成於本機，目前是 `LOCAL_CANDIDATE / REVIEW_PENDING`，尚未 accepted。`#6–#8 A4–A6 = BLOCKED / NOT_STARTED`，不得自行派工或開始。

## Authority baseline

- Reconciliation predecessor／observed baseline：`origin/main@0baeef6f7bd62c521e46a782b28a83940855d59f`；它不是 A0 execution base。A0 已接受；A1 的 canonical mainline merge 為 PR #12 `0b39937399eddd0535372ece51ddc25bc38fe6a6`。
- AI Core canonical authority：`aicore/docs/ai-core-backlog.md`；pinned remote baseline：`c896cbff126a57384f5f436b80ceaa2e14a22999`。
- `dated backlogs/old .work` 僅是 historical evidence，不得覆蓋 canonical authority。
- OMI：`lulu930128/open-market-intelligence@2d54c5983b8597babd804110f022a5f299e45a9d`，`authority=prior_art_only`。
- `aeae2c3` 僅是 historical draft/reference；不 merge，也不作 execution base。

## Operational boundary

Read-only observation、evidence mapping 與已完成 A2 的 closeout reconciliation 可繼續；A3 已取得個別 Owner admission，只能依 A3 task card進行一次性 legacy migration planning／bounded implementation。A4–A6 仍須個別 admission。Research lane 不得碰 scheduler、publish、production、runtime、config 或 operational data mutation；A3 只可最小延伸既有 migration evidence schema/seam。Issue #10 natural-run observation 與 A3 完全分離，不得由 A3 狀態推論或改寫 #9/#10。任何缺少個別證據的 claim 必須標示 `UNKNOWN` 或 `UNPINNED_RUNTIME_ARTIFACT`，不得用 projection receipt 或狀態文案宣稱 runtime load。

只有出現 governing-authority conflict、identity-grain ambiguity、terminal-boundary ambiguity，或需要 runtime mutation 時才停止並回報 blocker。

所有 lanes 使用 structured claim/evidence contract；Integrator 是唯一 cross-lane synthesis writer。Operational incident 不得順手修改 ranking math、模型、backtest、Research Spine identity 或 Card B/C。

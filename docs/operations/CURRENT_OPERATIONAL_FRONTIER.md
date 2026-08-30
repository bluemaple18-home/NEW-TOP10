# NEW-TOP10 Current Operational Frontier

更新：2026-08-30

## Current state

- `#10`：等待 **2026-08-31 17:30（Asia/Taipei）natural-run observation**；在 observation 完成前不宣稱 close 或 promotion。
- `#9`：`OPEN / LONG-TERM HARDENING`。它不阻擋 read-only A0；Research lane（含 A0/research）不得執行 scheduler、publish 或 production mutation。#9 未來若需 operational hardening，須另行取得對應授權。
- Research Spine：`#2 A0` 僅可做 read-only dispatch；`#3–#8` 維持 `BLOCKED`。

## Authority baseline

- Reconciliation predecessor／observed baseline：`origin/main@0baeef6f7bd62c521e46a782b28a83940855d59f`；它不是 A0 execution base。A0 execution base 必須是 reconciliation 進入 `origin/main` 後的新 SHA，並由 A0 baseline manifest 釘選。
- AI Core canonical authority：`aicore/docs/ai-core-backlog.md`；pinned remote baseline：`c896cbff126a57384f5f436b80ceaa2e14a22999`。
- `dated backlogs/old .work` 僅是 historical evidence，不得覆蓋 canonical authority。
- OMI：`lulu930128/open-market-intelligence@2d54c5983b8597babd804110f022a5f299e45a9d`，`authority=prior_art_only`。
- `aeae2c3` 僅是 historical draft/reference；不 merge，也不作 execution base。

## Operational boundary

Read-only observation、evidence mapping 與 A0 admission review 可繼續；Research lane（含 A0/research）不得碰 scheduler、publish、production、runtime、config、schema 與資料 mutation。任何缺少個別證據的 claim 必須標示 `UNKNOWN` 或 `UNPINNED_RUNTIME_ARTIFACT`，不得用 projection receipt 或狀態文案宣稱 runtime load。

只有出現 governing-authority conflict、identity-grain ambiguity、terminal-boundary ambiguity，或需要 runtime mutation 時才停止並回報 blocker。

所有 lanes 使用 structured claim/evidence contract；Integrator 是唯一 cross-lane synthesis writer。Operational incident 不得順手修改 ranking math、模型、backtest、Research Spine identity 或 Card B/C。

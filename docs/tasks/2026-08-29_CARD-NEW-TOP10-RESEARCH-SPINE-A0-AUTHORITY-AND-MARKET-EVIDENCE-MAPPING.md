---
id: CARD-NEW-TOP10-RESEARCH-SPINE-A0-AUTHORITY-AND-MARKET-EVIDENCE-MAPPING
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: READY_FOR_DISPATCH
type: architecture-mapping
priority: P1
owner: TOP10new research platform
role: precheck-and-prior-art
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
date: 2026-08-29
production_change_allowed: false
---

# NEW-TOP10 Research Spine A0 — Authority and Market Evidence Mapping

## Goal

在不改動 runtime 的前提下，建立可跨機審閱的 Research Spine A0 authority baseline：把市場證據、觀測命名、provider 選擇、dataset lifecycle 與 OMI prior art 對齊到現有 NEW-TOP10 架構，並釐清哪些是 immutable evidence、哪些是可刪除重建的 projection。A0 是 read-only mapping／ADR／acceptance revision，不是 Research Spine A1–A6 的實作卡。

## Root Question

NEW-TOP10 能否在既有執行邊界內，明確回答「哪個 provider 在何時、以何種 fallback 語意產生哪個 market evidence；該 evidence 如何形成 `features.parquet` lineage、支援 TrialSpec dataset reference、衍生 MarketObservation 與 ResearchObservation，並在刪除 registry／ledger projection 後由 immutable evidence 重建」，而不創造第二套 runtime authority？

## Blocker

目前 `features.parquet` 的 lineage、TrialSpec 的 dataset reference、provider-selection owner、fallback semantics，以及 `MarketObservation`／`ResearchObservation` 與 `Dataset Registry`／`Research Ledger` 的責任邊界尚未形成單一可接受的 authority map。若先做 A1/A2，會把未驗證的市場資料 authority、命名或 lifecycle 假設固化到 runtime。

## Required outputs（五份）

A0 必須產生可審閱的五份 mapping（可集中於 A0 evidence bundle 或 ADR，格式須可重建且有版本／日期）：

1. **Market Evidence Authority Map**：source/provider、market、instrument、trade date、取得時間、原始 payload、normalization、content hash、quality/status、owner 與 downstream consumer 的 authority 關係；明確標示 immutable evidence 與 derived projection。
2. **Observation Namespace Map**：定義 `MarketObservation`（市場事實／資料觀測）與 `ResearchObservation`（由已授權 TrialSpec／execution receipt 衍生的研究結果）之 namespace、identity、grain、lineage、sealed eligibility 與禁止互相冒充的規則。
3. **Provider Selection/Fallback Map**：定義 provider-selection owner、選擇輸入、優先序、health/eligibility 判定、fallback 觸發與停止條件；fallback 必須留下 requested provider、selected provider、reason、attempts、時間與 evidence hashes，不得靜默替換或把 fallback 當原始 authority。
4. **Dataset Lifecycle Map**：從 raw acquisition、normalized dataset、`features.parquet`、version/hash、retention、validation、publication 到 rebuild 的狀態與責任；說明 dataset artifact、Dataset Registry metadata 與 Research Ledger evidence index 的關係。
5. **OMI REUSE/ADAPT/REJECT Matrix**：逐項評估 Open Market Intelligence（OMI）prior art 與現有 NEW-TOP10 seam，至少使用 `USE_AS_IS`、`CONFIGURE`、`WRAP`、`ADAPT`、`COPY_CODE`、`CUSTOM_REQUIRED`、`REJECT`；每項記錄 evidence、邊界、why_not_less、why_not_more。OMI 僅作 prior art；不得在本卡實作 OMI runtime、provider adapter 或新的 market-intelligence service。

## Questions A0 must answer

### `features.parquet` lineage

Map 必須指出 `features.parquet` 的 canonical dataset identity、producer、輸入 evidence、normalization／feature transformation version、coverage（市場／股票／交易日）、content hash、validation receipt、publication owner 與 consumer。不得只以檔名或 filesystem path 當 lineage；若現況無法證明某段 lineage，標為 `UNKNOWN` 並列為 acceptance blocker，不得補猜。

### TrialSpec dataset reference

Map 必須定義 TrialSpec reference 的語意：requested dataset authority、dataset version/hash、market/date coverage、feature schema／lineage reference 與 execution 時的 executed dataset evidence。TrialSpec 是 requested definition，不等於執行事實；dataset substitution 或 fallback 必須在 immutable execution receipt 中顯式記錄，不能只改 TrialSpec 或事後掃檔案推定。

### Provider-selection owner and fallback semantics

Map 必須指定 provider-selection 的唯一責任邊界（domain owner、runtime seam、輸入 policy 與輸出 receipt），並區分：provider unavailable、provider ineligible、quality failure、rate limit、partial coverage 與 transient retry。每種 fallback 都要有 deterministic ordering、attempt budget、terminal failure、identity/correlation 與 replay evidence；缺 evidence 時 fail closed，不把 fallback 結果標成 primary provider 結果。

### Observation namespaces

`MarketObservation` 是由 market evidence 依市場資料 schema 衍生、描述「市場發生／被觀測到什麼」的資料事實；`ResearchObservation` 是由 accepted TrialSpec、ExecutionIntent、terminal receipt 與 dataset lineage 衍生、描述「研究執行產生什麼可學結果」的研究事實。兩者必須有不同 identity／owner／eligibility，並以 explicit lineage 關聯；不得以同一張表、同一個 id 或模糊 `observation` 欄位讓一者冒充另一者。

### Dataset Registry vs Research Ledger

Dataset Registry 只負責 dataset artifact 的版本、schema、content hash、coverage、producer／source、validation 與 lifecycle metadata；它不是 execution authority。Research Ledger 是以 immutable TrialSpec／Intent／receipt／artifact evidence 為基礎的可刪除重建 evidence index／projection，記錄研究 execution、observation eligibility、failure 與 learning linkage；它不是新的 AI Core runtime registry、scheduler 或 canonical writer。若 A0 證明兩者可由既有結構透過 `USE_AS_IS → CONFIGURE → WRAP → ADAPT` 滿足，必須拒絕新增 local registry／ledger authority。

## Boundaries

### In scope

- read-only repository／architecture mapping、ADR 與 acceptance revision。
- 現有 market data、`features.parquet`、TrialSpec／receipt／observation 證據的 lineage 與責任盤點。
- provider selection／fallback 的 authority contract 與 evidence requirements。
- OMI prior-art comparison，含最小必要的 reuse decision。
- 對 A1/A2 admission 所需的 measurable gaps、依賴與 stop/go 判定。

### Out of scope

- 任何 Python、config、schema migration、database、provider adapter、API fetch、OMI runtime 或 production artifact。
- ranking、model、features calculation、weights、backtest mathematics、strategy logic、priority、candidate ranking、queue、scheduler、daily quota、UI、LightGBM 或 promotion。
- A1–A6 implementation；Card B/C admission；daily recovery、#9、Issue #10 S2B、#10 隔離候選或 Fog 舊線的施工。

`#9`、Issue #10、Fog 舊線與 OMI runtime 只能作 boundary/reference；不得把其 identity、authority、dirty files、`.work` 或候選文件帶入本卡。任何 compatibility bridge 若被發現，必須記錄 owner、removal condition、removal test 與 target removal card/stage；本卡不得實作 bridge。

## Acceptance

A0 僅在主線明示接受後才算 accepted；Worker 不得自行宣告 accepted。主線驗收至少須確認：

- 五份 output 均存在，具有版本、scope、source/evidence reference、owner 與 open questions。
- 五份 map 對 `features.parquet` lineage、TrialSpec dataset reference、provider-selection owner、fallback semantics、兩個 observation namespace、Dataset Registry／Research Ledger 邊界給出一致且可追溯的答案。
- OMI matrix 每個採用或拒絕決策都有 evidence；`CUSTOM_REQUIRED` 必須證明 `USE_AS_IS → CONFIGURE → WRAP → ADAPT` 逐層不足，並寫出固定版本／固定 acceptance 下的失敗原因。
- 所有未知、衝突與 measured gap 都 fail closed；不得以 path、status 文案或 projection receipt 單獨宣稱 runtime load／execution truth。
- ADR 明確記錄「只做 read-only mapping／ADR／acceptance revision；不改 runtime」，且 A1/A2 僅在本卡 acceptance 後重新裁決 admission。
- repository diff 僅含本卡明示允許的文件；通過文件 lint／結構檢查與 `git diff --check`；不要求、不執行 production 或 runtime mutation。

## Stop conditions

立即停止並回報 blocker，不得自行補 workaround：

- authority order、parent #1 或 AI Core 2026-08-25 rebaseline 出現 material conflict。
- 無法以 committed evidence 證明 provider、dataset、lineage 或 fallback 的 owner／identity／terminal semantics。
- 需要修改 runtime、資料、schema、production artifact，或需要新增共用 authority ledger／registry／FSM／database 才能完成 map。
- OMI prior art 的版本、來源或 acceptance 不足以支撐 reuse decision；不得猜測或移植 runtime。
- 發現 #9、Issue #10、Fog 舊線或 dirty/main 候選會改變本卡 scope；隔離並回報，不得帶入。

## Dispatch and dependency rule

`A0` 是目前唯一 dispatchable Research Spine frontier。A1/A2 只有在上述 acceptance 由主線接受後才能重新裁決；A3–A6 依既有 backlog 順序維持 blocked。A0 完成不等於母卡 #1 完成，也不等於任何 runtime capability 已上線。

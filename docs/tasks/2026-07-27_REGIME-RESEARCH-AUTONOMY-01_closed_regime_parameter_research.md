---
id: REGIME-RESEARCH-AUTONOMY-01
status: DELIVERED_CANDIDATE
type: implementation
ownership: existing-visible-implementation-thread
chain_id: REGIME-RESEARCH-AUTONOMY-01
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 核心研究契約、盤勢資料隔離、sealed OOS、兩百萬級參數空間治理與 promotion 前證據會跨多個模組；錯誤可能系統性製造過度擬合與錯誤策略結論。
worktree_path: <codex-managed-worktree>/TOP10new
cwd: <codex-managed-worktree>/TOP10new
main_cwd: <repo-root>
worktree_exists: true
source_sha: 7efda43641118f36b10261b4a04e0278bba941a2
card_sha: ebfffbd5b926b169dde353c6f1a888fe04fbd159
implementation_branch: codex/regime-research-autonomy-01-ea64
evidence_path: artifacts/visible_thread/REGIME-RESEARCH-AUTONOMY-01/
---

# REGIME-RESEARCH-AUTONOMY-01：盤勢隔離的自主參數研究系統

## 5 行派工卡

```text
任務ID：REGIME-RESEARCH-AUTONOMY-01
卡片類型｜派工對象：Strict Implementation｜既有可見研究對話
請讀：docs/tasks/2026-07-27_REGIME-RESEARCH-AUTONOMY-01_closed_regime_parameter_research.md
任務目的：把現有 autonomous research 升級成依當前盤勢自主選題、同盤勢封閉回測、不可污染且可收斂完整參數空間的研究系統
證據路徑：artifacts/visible_thread/REGIME-RESEARCH-AUTONOMY-01/
```

## 接手第一拍

這張卡要交給使用者已存在的正式可見對話，不建立新的隱藏 sub-agent。

接手對話開始實作前必須：

1. 先讀本卡與 repo `AGENTS.md`，回報理解，不得先改碼。
2. 確認目前 thread 使用獨立 worktree，且 `cwd` 不等於主工作區。
3. 記錄 thread ID、worktree path、branch、source SHA、`git status --short`、是否存在 `.git/index.lock`。
4. 若目前正在處理另一張卡，不得把兩張卡混在同一 commit；先交付／停妥原卡，再由乾淨 source commit 接本卡。
5. 執行：

   ```bash
   bash ${AI_CORE_DIR:-$HOME/ai-core}/scripts/worktree_capability_preflight.sh \
     --check \
     --root <repo-root>
   ```

6. 任一 provisioning 證據不足時，狀態保持 `CARD_DRAFTED` 或標記 `BLOCKED / PROVISIONING_PREFLIGHT`，不得宣稱已執行。

## Root Question

如何讓研究團隊不依賴 PM 指定題目，而能根據當前盤勢，從兩百多萬個合法參數組合中自主挑選最相關、最有資訊價值的研究區域；同時只使用歷史上完全相同盤勢的資料，維持封閉、互不污染、不可事後拼接的驗證流程，最後收斂成少數可稽核的「盤勢 → 策略參數」政策？

## Goal

把目前偏向「依現有 ranking 目錄挑題並執行 strategy matrix」的 autonomous research manager，升級成可治理的盤勢專用研究系統：

1. 自主判斷當前盤勢與研究優先順序。
2. 建立完整參數宇宙、合法組合與覆蓋狀態。
3. 每個盤勢只使用歷史上完全相同盤勢的資料研究。
4. 每個實驗預先登記、封閉切分、不可污染或事後拼裝。
5. 沒有候選通過時，允許輸出 `NO_STRATEGY`。
6. 各盤勢研究完成後，才允許開啟通用策略候選驗證。
7. 研究 artifact 不得直接改 production 或授權 promotion。

## 使用者確認的研究憲法

### 產品硬限制

以下項目不能因短期回測較漂亮而自行犧牲：

- 服務沒時間盯盤的使用者。
- 做多、動能順勢、中期波段。
- 不以弱勢抄底、放空或當沖為主。
- 候選、排名與操作建議必須可解釋。
- 風險與回撤必須受控。
- 不得使用未來資訊或任何形式的 hindsight。
- 找不到合格策略時，允許觀察、暫停進場或 `NO_STRATEGY`。
- Agent 無權自行改變產品初衷；若發現結構性衝突，只能提出具證據的變更提案，由 PM 決定。

### 可由研究修正的假設

- 是否固定輸出 Top 10。
- 是否固定持有 10 天。
- 是否固定以 5% 為獲利目標。
- 是否最後恰好只剩六條盤勢策略。
- 不同盤勢是否可能共用同一組參數。

### 研究優先原則

在產品硬限制與風險底線下，優先找：

- 封閉樣本外表現穩定的組合。
- 回撤可控的組合。
- 對參數微小變動不敏感的組合。
- 在相同盤勢的不同歷史 episode 中可重現的組合。

最高單次報酬不得凌駕穩定性與可生存性。

## 盤勢隔離硬契約

研究某個盤勢的參數組合時，只能使用歷史上完全相同盤勢的資料，不得用全期間或其他盤勢的結果替它背書。

### Exact-match 定義

- `base_regime` 必須完全相同。
- 當前存在 family tags 時，正式證據的 family tag 集合也必須完全相同。
- 只有 base regime 相同、family tags 不同的資料，只能作診斷，不得用於通過判定。
- 盤勢轉換期、`UNKNOWN` 或無法可靠分類的日期必須獨立處理或排除，不得硬塞入最接近的盤勢。
- 盤勢分類必須遵守 as-of 原則，只能使用當時可取得的資料。

目前既有 taxonomy 至少包含：

- base regime：`BROAD_RISK_ON`、`NARROW_LEADER`、`CHOPPY_RANGE`、`RISK_OFF`、`PANIC_SELLING`、`EARLY_REVERSAL`、`MIXED_NEUTRAL`、`UNKNOWN`。
- family tags：`HIGH_CHOPPY`、`BIG_BULL`；兩者可以重疊。

### 切分原則

- 按完整盤勢 episode 切分，不得隨機打散每日資料。
- development、validation、embargo、sealed OOS 必須時間分離。
- embargo 至少覆蓋 label horizon／持有期可能造成的資訊穿越。
- baseline 也必須用相同盤勢、相同 episode 邊界與相同成本口徑。
- 某盤勢樣本不足時只能標記 `MONITOR_ONLY / INSUFFICIENT_EVIDENCE`，不得借用其他盤勢補樣本。
- 全期間統計最多作風險診斷，不得作為盤勢策略的 promotion 證據。

## 封閉實驗與防過度擬合契約

每個實驗必須：

1. 跑前固定單一 `research_question`。
2. 固定 baseline、盤勢、資料版本、episode、參數範圍、成本、metric、門檻與失敗條件。
3. 產生不可變的 experiment ID、parameter-space hash、dataset hash 與 split ID。
4. 只在 development／training 區間搜尋或挑選參數。
5. validation 只用於本實驗的預註冊選擇，不得在看完結果後追加 filter。
6. sealed OOS 在揭封前不可用於調參；揭封後不得回頭修改同一候選。
7. 已影響過選擇的資料不得再次冒充新實驗的 OOS。
8. 想把實驗 A 的進場、B 的出場、C 的盤勢濾網組合時，必須註冊成全新候選，使用新的未污染資料重新驗證。
9. 任一步失敗只能產生下一輪新假說，不得回頭修補本輪結論。
10. 大量組合必須處理 multiple testing、winner's curse 與 data snooping；不得只挑最高分宣稱有效。

## 自主選題契約

PM 不負責替 Agent 指定每日研究題目。

研究 manager 必須根據可稽核欄位，自主排序候選研究區域：

```text
priority =
  current_regime_relevance
  × evidence_gap
  × expected_information_gain
  × product_value
  × feasibility
  ÷ estimated_compute_cost
```

具體要求：

- 先讀當前 as-of market context，不得只看 ranking 目錄名稱。
- 優先研究當前 exact-match 盤勢尚未覆蓋、證據不足或接近決策邊界的參數區域。
- 已穩定拒絕、仍在 cooldown、資料不足或已完整覆蓋的區域應降權或停止。
- 每次選題 artifact 必須解釋「為什麼現在選這題」「它補哪個 coverage gap」「若成功／失敗會排除多少搜尋空間」。
- 不得使用 LLM 自評作為硬 gate；排序、資格與停止條件必須可由 deterministic code／schema／validator 重現。

## 完整參數宇宙

建立單一可機器讀取的參數空間契約，至少記錄：

- 維度 ID、名稱、研究層級與產品語意。
- 資料型別、允許值／範圍／步長。
- 預設值與 baseline 值。
- 維度間相依關係。
- 不合法或無意義的組合。
- 估算合法總組合數。
- 每個合法組合的穩定唯一 ID。
- 哪些維度已可執行、哪些因資料契約或 coverage 被阻擋。
- 每個盤勢的已研究、拒絕、待驗、樣本不足與通過數量。

不得把目前 strategy matrix 的四個維度誤稱為完整兩百萬組合空間。

## 研究漏斗與狀態機

每個盤勢的研究生命週期至少為：

```text
REGISTERED
→ COARSE_SCREEN
→ SAME_REGIME_VALIDATION
→ SEALED_OOS
→ FORWARD_SHADOW
→ REGIME_POLICY_CANDIDATE
```

允許終態：

- `REGIME_POLICY_CANDIDATE`
- `MONITOR_ONLY`
- `INSUFFICIENT_EVIDENCE`
- `REJECTED`
- `NO_STRATEGY`
- `BLOCKED`

硬規則：

- 不得跳階。
- `COARSE_SCREEN` 的勝出者不等於通過。
- sealed OOS 通過後仍不得直接改 production。
- forward shadow 必須持續使用未參與選題的新資料。
- 每個狀態轉換都要有 deterministic validator 與 evidence path。

## 通用策略／「聖杯」特殊閘門

通用組合不能從一開始用全期間混跑產生。

只有符合以下條件，才可開啟 universal candidate：

1. 所有合法維度與組合空間完成至少一輪可稽核覆蓋。
2. 每種盤勢都已完成封閉驗證，或明確標記樣本不足。
3. 不存在尚未處理的高價值研究區域。
4. 同一組參數在多個盤勢研究中獨立浮現。
5. 通用候選的參數先完全凍結，再開新實驗。
6. 每種盤勢都使用各自未使用的 sealed OOS 獨立驗證。
7. 看最差盤勢表現，不得用全期間平均掩蓋單一盤勢失敗。
8. 通過逐盤勢 sealed 後，還要經歷跨盤勢轉換的 forward shadow。

只要任一具足夠樣本的盤勢未通過，就不得稱為通用策略；最多標記為 multi-regime shared candidate。

## 現況證據與已知缺口

### 現有能力

- `scripts/run_autonomous_research.py`
  - 可掃描既有 ranking dirs、產生 topic、排序、從 queue 選題。
  - 有 runner allowlist、冷卻、執行次數上限、artifact 與 manager registry。
- `scripts/run_backtest_strategy_matrix.py`
  - 可排列 horizon、stop loss、take profit、group exposure。
  - 只讀既有 ranking 與 feature artifacts，不訓練模型。
- `scripts/compare_strategy_matrices.py`
  - 可比較 baseline／candidate 的 score、return、drawdown。
- `app/modeling/sealed_oos.py`
  - 已有 development／embargo／sealed split 基礎能力。
- `scripts/verify_half_year_walkforward_no_hindsight.py`
  - 已有部分 pre-registration 與 no-hindsight verifier。

### P0 缺口

1. 自主選題目前主要依 ranking 目錄名稱關鍵字、檔案數與外部 signal 加分，未強制讀取當前盤勢。
2. strategy matrix runner 沒有 exact-match regime filter；目前 replay args 使用 `market_regime_history=None`。
3. autonomous research 主流程沒有強制接入 sealed OOS／embargo。
4. 不存在跨實驗 dataset／split 使用登記，無法證明 sealed 資料從未影響過其他選擇。
5. 現有矩陣只覆蓋四個維度，缺完整參數宇宙與兩百萬級 coverage map。
6. 目前取矩陣 `best_score`，缺 multiple-testing／winner's-curse 防護。
7. 沒有機器可驗證的產品硬限制與 `NO_STRATEGY` 結論。
8. 沒有「各盤勢完成後才可研究通用組合」的 universal gate。

### 既有結果處理

- 既有 5913 combo 與其他未遵守本卡 exact-match／sealed isolation 契約的結果不得刪除。
- 這些結果應保留為歷史診斷資料，但標記為 legacy／diagnostic-only。
- 未經本卡新契約重驗，不得用於 `REGIME_POLICY_CANDIDATE` 或 universal candidate。

## 實作範圍

允許修改或新增：

- `scripts/run_autonomous_research.py`
- `scripts/run_backtest_strategy_matrix.py`
- `scripts/compare_strategy_matrices.py`
- `app/modeling/sealed_oos.py`，僅限本卡必要且不破壞既有模型流程的相容性修改
- 既有 market regime history／episode builder 與其直接 verifier
- `config/` 下本卡新增的研究憲法、參數宇宙、盤勢研究政策
- 本卡直接相關的 `scripts/verify_*.py`
- 本卡直接相關的 `tests/test_*.py`
- `docs/architecture/AUTONOMOUS_RESEARCH_MANAGER.md`
- `docs/architecture/MODEL_IMPROVEMENT_LOOP.md`
- `docs/evidence/REGIME-RESEARCH-AUTONOMY-01/**`
- `artifacts/visible_thread/REGIME-RESEARCH-AUTONOMY-01/**`
- 本卡狀態與結果欄位

若實際 needed files 超出 allowlist，先更新卡片並交主線核准，不得自行擴張。

## 禁止範圍

- 不得修改 `models/latest_lgbm.pkl` 或任何 production model。
- 不得修改正式 ranking、`risk_adjusted_score`、正式權重或 production promotion 狀態。
- 不得執行 live publish、Discord、Clawd 推播、交易或外部服務 write。
- 不得刪除、覆寫或重新解釋既有研究 artifacts 來製造通過。
- 不得放寬既有 verifier 以讓候選過關。
- 不得把不同盤勢混入正式研究證據。
- 不得用全期間平均替盤勢專用策略背書。
- 不得把 LLM 判斷當作 hard gate。
- 不得把某輪診斷結果回填成同輪 filter。
- 不得在本卡直接 promotion 或上 production。
- 不得 merge、push、deploy。

## 建議實作順序

### Phase 0：Baseline 與紅燈測試

- 保存現有 autonomous research 行為與最新 trace 的 bounded fixture。
- 先建立會抓出以下問題的 failing tests：
  - 名稱含 `regime` 但實際未過濾資料。
  - exact base regime 相同但 family tags 不同仍被納入。
  - transition／`UNKNOWN` 被硬塞。
  - sealed 日期被另一實驗使用後仍被當新 OOS。
  - 不同實驗零件事後拼接但沒有新 experiment ID。
  - 全期間平均通過、但某一盤勢失敗仍被標 universal。

### Phase 1：研究憲法與參數宇宙

- 建立 schema、config 與 verifier。
- 對現有實際維度做 inventory，不得猜兩百萬組合的來源。
- 產出 deterministic combination ID 與合法組合計數。

### Phase 2：盤勢 episode 與 exact-match dataset

- 建立 as-of regime episode artifact。
- 支援 base regime＋family tag set exact match。
- 建立 transition／unknown policy。
- 讓 baseline／candidate 使用完全相同的 episode split。

### Phase 3：封閉實驗 registry

- 建立 experiment pre-registration artifact。
- 建立 dataset hash、split hash、parameter-space hash。
- 建立 sealed reuse／contamination verifier。
- 實驗 registry 必須可追加、可稽核，不得靜默重寫歷史。

### Phase 4：自主選題與 coverage map

- 以 current regime relevance、evidence gap、information gain、product value、feasibility、compute cost 排序。
- 題目輸出必須附可重現 score breakdown。
- coverage map 能回答每個盤勢的剩餘研究區域與停止原因。

### Phase 5：封閉研究漏斗

- 將 coarse screen、same-regime validation、sealed OOS、forward shadow 串成不可跳階狀態機。
- 加入 multiple-testing／winner's-curse 防護。
- 樣本不足、無合格策略與失敗都要 fail-loud。

### Phase 6：Universal Gate

- 只有 coverage closure 通過後才解鎖。
- 逐盤勢獨立驗證固定參數。
- 以 worst-regime 與跨 regime transition shadow 作判定。

### Phase 7：文件、回歸與交付

- 更新架構文件與可重跑命令。
- 跑受影響測試、完整測試與 `git diff --check`。
- 產出 evidence、candidate commit 與完整 SHA。

## 功能需求

### FR-01：當前盤勢驅動選題

WHEN 研究 manager 建立當日題目時，系統 SHALL 讀取同日 as-of market context，並將 exact-match regime identity 寫入 topic。

### FR-02：相同盤勢資料限定

WHEN 執行盤勢專用研究時，系統 SHALL 只允許 exact-match base regime 與 family tag set 的歷史 episode。

### FR-03：封閉切分

WHEN 實驗進入 validation 或 sealed OOS 時，系統 SHALL 使用預註冊且不可變的 episode split，並驗證 embargo 與時間順序。

### FR-04：污染防護

IF 任一 sealed dataset／episode 已影響過參數、filter 或候選選擇，THEN 系統 SHALL 拒絕它再次作為新實驗的 sealed OOS。

### FR-05：禁止事後拼接

IF 候選組合使用不同實驗中挑出的零件，THEN 系統 SHALL 要求新的 experiment ID 與全新未污染驗證資料。

### FR-06：自主研究優先序

WHEN manager 排序題目時，系統 SHALL 輸出可重現的 relevance、gap、information gain、value、feasibility 與 cost score breakdown。

### FR-07：研究覆蓋

系統 SHALL 維護每個 exact-match regime 的參數空間 coverage、狀態、證據與剩餘高價值區域。

### FR-08：合法無策略結論

IF 沒有候選通過預註冊門檻，THEN 系統 SHALL 輸出 `NO_STRATEGY` 或證據不足狀態，不得降低門檻湊答案。

### FR-09：通用策略解鎖

WHEN universal candidate 被建立時，系統 SHALL 證明所有必要盤勢研究已完成或明確樣本不足，並逐盤勢獨立驗證固定參數。

### FR-10：Production 隔離

WHILE 本卡處於 research-only 階段，系統 SHALL 禁止修改模型、正式 ranking、權重、推播或 production promotion 狀態。

## 驗收條件

### AC-01：選題確實依盤勢

Given 當日盤勢為 `BIG_BULL + HIGH_CHOPPY`
When manager 產生研究題目
Then topic 必須記錄相同 regime identity，且其他盤勢題目不得因檔名關鍵字取得正式執行資格。

### AC-02：Exact-match

Given 歷史資料同時包含 exact match、base-only match、其他 family tag 與 transition episode
When 執行盤勢回測
Then 正式 metric 只能包含 exact-match episode，其他資料只能診斷或排除。

### AC-03：Episode 切分與 embargo

Given 多個相同盤勢 episode
When 建立 development／validation／sealed split
Then 同一 episode 不得跨 split，時間順序正確，且 embargo 足以覆蓋持有 horizon。

### AC-04：污染拒絕

Given sealed episode 已被某實驗用來決定參數
When 新實驗試圖再次宣稱它是 sealed OOS
Then verifier 必須 fail closed 並指出污染來源 experiment ID。

### AC-05：組合拼接拒絕

Given 新策略拼接先前實驗的進場、出場與 regime filter
When 沒有新 experiment ID 或新 sealed dataset
Then workflow 必須拒絕進入 validation。

### AC-06：完整參數空間

Given 參數宇宙 config
When 產生 coverage summary
Then 合法組合總數、各盤勢已處理／待處理／阻擋數與 hash 可重現一致。

### AC-07：多重比較防護

Given 大量候選只有最高分看似突出
When correction／robustness gate 未通過
Then 最高分候選不得進入 sealed OOS 或 policy candidate。

### AC-08：無策略

Given 某盤勢所有候選皆未過門檻
When 本輪研究結束
Then 結果為 `NO_STRATEGY`，不得修改門檻、混入其他盤勢或挑單一漂亮視窗。

### AC-09：Universal Gate

Given 某固定組合在多個盤勢中獨立浮現
When 尚有未完成的高價值盤勢研究，或任一具足夠樣本的盤勢未通過
Then universal candidate 必須保持 locked。

### AC-10：Production 不變

Given 本卡所有研究流程完成
When 比較工作前後
Then production model、ranking、score、權重、推播與 promotion 狀態均未被修改。

## 必要 verifier

至少建立或擴充：

- 參數宇宙 schema／合法組合 verifier。
- as-of regime episode verifier。
- exact-match regime dataset verifier。
- episode split／embargo verifier。
- experiment pre-registration verifier。
- sealed dataset reuse／contamination verifier。
- no-cross-experiment-composition verifier。
- research coverage closure verifier。
- autonomous topic score reproducibility verifier。
- multiple-testing／robustness gate verifier。
- universal candidate unlock verifier。
- production no-change verifier。

所有 verifier 必須有正例與合成反例測試；不得只測 happy path。

## 驗證命令

接手者應依實際新增測試補齊精確命令。最低要求：

```bash
uv run pytest -q <本卡受影響測試>
uv run pytest -q
git diff --check
```

若完整測試因既有 blocker 無法通過，必須：

- 提供失敗命令與完整錯誤摘要。
- 證明失敗是否與本卡變更相關。
- 不得用跳過測試宣稱完成。

## Evidence 契約

交付前在 `artifacts/visible_thread/REGIME-RESEARCH-AUTONOMY-01/` 保存：

- `preflight.md`
- `baseline.md`
- `changed_files.txt`
- `verification.md`
- `result.md`
- 測試輸出摘要
- 關鍵合成反例與 verifier 結果
- candidate commit 完整 SHA

`result.md` 至少回答：

- 當前盤勢如何進入選題。
- exact-match 歷史 episode 如何選取。
- 如何證明 split 未污染。
- 如何證明不同實驗沒有事後拼接。
- 參數宇宙與 coverage 如何計算。
- 如何處理樣本不足與 `NO_STRATEGY`。
- universal gate 何時解鎖。
- production 哪些內容確認未改。

## 停損與回退

- 同一 blocker 最多 3 次；第 3 次失敗即停，不進行第 4 次。
- 若無法證明 regime history 為 as-of，立即 `BLOCKED`，不得繼續回測。
- 若無法建立未污染 sealed split，立即 `BLOCKED`，不得改用全期間結果。
- 若完整參數空間來源不明，先輸出 inventory gap，不得猜總組合。
- 若需要改 production contract、刪除 runtime artifacts 或放寬 verifier，立即交回主線。
- 所有新研究配置必須 default-off 或 research-only，可透過單一 commit 回退。

## Active State

- 本卡由需求訪談與唯讀稽核產生。
- 目前尚未修改任何研究 code、config、workflow 或 production artifact。
- 主工作區在建立本卡前為 clean。
- 本卡不宣稱既有對話已完成 worktree preflight；該證據由接手對話補齊。

## Completed Actions

- 已確認產品硬限制與可研究假設。
- 已確認每個盤勢只能使用歷史 exact-match 盤勢資料。
- 已確認 base regime 與 family tag set 均需 exact match。
- 已確認實驗必須封閉、不可交錯、不可事後拼接。
- 已確認通用組合只能在所有盤勢研究完成後另開嚴格驗證。
- 已完成 autonomous research manager 靜態稽核與一份最新 run trace 抽查。

## Blocker

沒有需求 blocker。

實作前唯一 blocking condition 是：接手對話必須證明自己使用獨立 worktree，且不與原本正在修的卡混 commit。

## Candidate Forks

- Fork A：完整參數宇宙 inventory 發現目前「兩百多萬」估算與實際合法組合不一致。
- Fork B：某些盤勢歷史 episode 樣本不足，無法建立 sealed OOS。
- Fork C：現有 regime history 不符合 as-of 契約，需要先修資料來源。
- Fork D：multiple-testing 方法需要依參數搜尋結構選型；必須保守 fail closed，不得為求通過選寬鬆方法。

Fork 發生時先產具證據的 decision note，不得靜默改變本卡研究憲法。

## 下一步

Implementation Executor 已完成 candidate；下一步由主線建立獨立 Review 卡，檢查
candidate SHA、diff、verifier 與 artifacts。Review `GO` 前不得 merge、push、
deploy、promotion 或啟用 production。

## 等待條件

- 等待獨立 Reviewer。
- 等待代表性真實 features／ranking artifacts 的受控 replay evidence。
- 等待完整兩百萬級參數來源 inventory；目前只證明既有四維 720 組。

## Mainline Acceptance

本卡的 implementation thread 只能交付 `DELIVERED_CANDIDATE`。

主線必須：

1. 讀實際 diff、測試、artifact 與完整 candidate SHA。
2. 建立獨立 Review 卡／Reviewer thread。
3. Review `GO` 後才可接受。
4. 本卡不授權 merge、push、deploy、promotion 或 production 啟用。

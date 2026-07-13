# REFACTOR-05｜Research Fog Map 模組邊界

- status: done
- priority: P1
- owner: Codex worktree
- task thickness: standard

## 目標

把 `scripts/build_research_fog_map.py` 從 3,500+ 行單體拆成薄 CLI／adapter、domain payload builder、HTML renderer 三個責任；輸入、JSON schema、HTML 內容與 CLI 行為必須等價。此流程只屬研究面，不得影響每日報牌。

## 依賴與 frontier

- 依賴：REFACTOR-02 已完成研究 worker 狀態治理。
- blocker：無。
- frontier：可立即開工。

## 可改檔案

- `scripts/build_research_fog_map.py`
- `app/research/fog_map_domain.py`（可新增）
- `app/research/fog_map_render.py`（可新增）
- `app/research/__init__.py`（必要時）
- `scripts/verify_research_fog_map.py`
- `tests/test_research_fog_map_refactor.py`（可新增）
- 本卡 result/status

## 不可改

- `scripts/run_daily.sh`、`scripts/run_daily_publish.sh`
- `scripts/run_automation.py`
- ranking、model、通知與 launchd 設定
- 研究結果 schema、節點 ID、排序、座標、狀態語意

## 實作契約

1. 原 script 保留 CLI 與既有可被 import 的 public functions；必要時以 re-export 相容。
2. domain 模組只能處理輸入正規化、節點／queue／summary／payload，不含 CLI side effect。
3. renderer 只接受 payload 並回傳 HTML，不讀寫檔案、不讀環境變數。
4. I/O 與參數解析留在薄 script；不新增 template engine 或外部依賴。
5. 使用 fixture 對照 refactor 前後 JSON 與 HTML SHA／內容等價；動態時間欄位必須固定或排除後比較。

## 驗收

- 原 script 縮為明確 adapter，domain／render 可獨立 import。
- fixture JSON 深度相等，HTML 等價。
- `scripts/verify_research_fog_map.py` 通過。
- 相關 schema verifier 通過。
- `git diff --check` 通過；沒有 production/live 檔案變更。

## 回報

列出修改檔案、測試、未驗證原因與剩餘風險；建立單一 atomic commit，不 merge、不 push。

## 實作結果

- 原 script 已縮為 CLI／I/O adapter，既有 public functions 與輸出契約保留。
- payload domain 與 HTML renderer 已拆為可獨立 import 的模組。
- fixture JSON 深度相等、HTML 正規化後內容相等；fog map verifier 與 v2 schema verifier 通過。
- 未觸碰每日報牌、ranking、model、通知與 launchd 路徑。

# Retrain monitor production preactivation

日期：2026-09-08（Asia/Taipei）

狀態：`PREACTIVATION_GO`

## Fixed scope

- Accepted commit：`8fe93667e2673a366239aa84b36f481fba79d89e`
- Detached runtime：`/Users/mattkuo/TOP10-runtime-automation-8fe9366`
- 唯一 target：`com.new-top10.retrain`
- 唯一 workload：`/bin/bash <runtime>/scripts/daily_retrain.sh monitor --trigger scheduled`
- 明確排除：model retraining、Fog、其他 launchd job、manual run、`kickstart`、push、外部送出。

## Runtime preparation

- `git worktree add --detach` 固定於 accepted commit；HEAD detached，tracked worktree clean。
- `uv sync --frozen` 完成，共安裝 105 個 locked packages。
- 以前一個 production runtime 的 `data/`、`artifacts/`、`models/` 進行 no-overwrite merge；未複製 `logs/`、lock 或 denial marker。
- 合併後 mutable inventory 與來源同為：data `896M / 2670 files`、artifacts `2.2G / 28280 files`、models `17M / 11 files`。

## Safety and tests

- Candidate runtime activation suite：`95 passed`。
- Candidate runtime storage suite：`100 passed, 39 subtests passed`。
- `bash -n`、plist lint、`git diff --check`：PASS。
- retrain-monitor live capacity measure：`PASS`。
- Sample：host free=`26,373,304,320`、host total=`245,107,195,904`、project bytes=`3,241,729,137`、project files=`30,962`、memory pressure=`2`、RSS=`0`、swap=`11,561,336,832`。

## Review closure

- Initial candidate：`6985887`。
- Repair 1：`ad16417`。
- Reviewer 1：`GO`；`R1-P1-RETRAIN-DENIAL-IDENTITY-MIGRATION` resolved。
- Reviewer 2：`GO`；`R2-P1-01`、`R2-P1-02` resolved。
- 修補後 contract：舊 retrain marker／held lock、非明確 service-not-found 的 launchctl readback、非 canonical monitor argv 均在 mutation 前 fail closed；rollback readback unknown 不得宣稱回復成功。
- 首次 production precheck receipt 為 `PRECHECK_FAILED`，原因是 installed legacy plist 尚未經 storage guard；該次未發生 mutation。
- Repair 2：`64402be`；兩名 Reviewer 皆因 retrain label 仍可落入 generic identity parser 而 `NO-GO`。
- Repair 3：`8fe9366`；retrain label 只接受 exact legacy direct monitor 或 exact guarded `retrain` monitor argv，wrong／unknown／path-like identity 與 child argv drift 均 fail closed。兩名原 Reviewer bounded re-review 均 `GO`。

## Production prestate

- `com.new-top10.retrain`：disabled、unloaded。
- Installed plist SHA-256：`7e2523abb0bb1e0e443e491c5e5bebd938921d725c861b618ef0411a9a11a86b`。
- Installed command 仍是舊 root `/Users/mattkuo/TOP10new/scripts/daily_retrain.sh monitor --trigger scheduled`。
- 舊 `restart_denied/retrain.json` absent；舊 `retrain.lock` absent。
- 新 runtime `restart_denied/retrain-monitor.json` absent；新 `retrain-monitor.lock` absent。

## Authorized transaction

只允許執行一次 retrain-monitor selector transaction，使用 `--allow-dormant-target-activation --activate`；不得手動觸發 workload。成功只可進入 `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`，自然驗收留待 02:00 排程證據。

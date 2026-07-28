---
id: FOG-RUNTIME-TIME-AUTHORITY-01-I5-RECOVERY-PREFLIGHT
status: GO_BOUNDED_DRY
type: evidence
---

# I5 recovery preflight

## Contract

- Main SHA：
  `13c9faed686677fff45f30db636ad61445be00cf`
- Tag：
  `top10-2026-07-28-01-fog-exact-regime-topic-eligibility`
- Operation order：read-only preflight → bounded dry gate → explicit circuit
  recovery → single-job LaunchAgent load／kickstart → three-cycle acceptance。
- Rollback：任一 live gate失敗立即 unload Fog job，保存失敗 state／context／
  receipt／logs；不恢復 legacy receipt、不直接刪 circuit、不重放 queue。

## Evidence

### Lineage

- `HEAD`／`origin/main`／release tag：
  `13c9faed686677fff45f30db636ad61445be00cf`
- Worktree在本卡與本 evidence建立前為 clean。

### Installed runtime

- Repo plist與 installed plist均通過`plutil -lint`。
- Repo rendered plist SHA-256：
  `f63ae67c4ae7b437246d31f8122307b5a5726778d36d302794b80fa342f664cb`
- Installed plist SHA-256：
  `f63ae67c4ae7b437246d31f8122307b5a5726778d36d302794b80fa342f664cb`
- `launchctl print`：service不存在，exit `113`。
- Escalated process query：沒有 Fog worker、handoff或 autonomous research
  process。
- Fog／queue-owner／PM harness lock：皆不存在。

### Circuit

- State：`attempts=3`、`last_exit_code=1`、`circuit_open=1`。
- State SHA-256：
  `acfbfbc43bc02af51e5fb6b1d3e285616bf2fcf846e41ceda8ee3b79cd74096c`
- Context SHA-256：
  `528d5cca4482f0e9ccb9e6d2374e856ca57557ebd69df3deb87c858a787f3255`
- Active runtime receipt inventory：空；沒有 legacy v2需要 archive。

### Protected before hashes

| Role | Path | SHA-256 |
|---|---|---|
| model | `models/latest_lgbm.pkl` | `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d` |
| baseline | `models/baseline_stats.json` | `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7` |
| ranking | `app/agent_b_ranking.py` | `b3d44da02d2d6f34838dbe24a96b3611135d26e718bfcd54acc3561414db7cfe` |
| weights | `config/signals.yaml` | `b34c1a20a705bb67f107de870ddd0cec5a2e3419aa385258370d88ceb553d60a` |
| promotion | `app/modeling/model_runtime_promotion.py` | `2add0872011c47640f8acafc6e594f4186a33eb15a8640c8b4aa46924f78d9b1` |
| queue | `artifacts/autonomous_research/next_action_queue.json` | `099cfa7f86d86f4b0e9127518b89089aaf9d6bd99aeb836991d0ba224d378bce` |
| regime history | `artifacts/market_regime_history.json` | `96372f3e7fcfc8416d123496c4d2d3f32218b75d22e80fce70e394640b3527cd` |

### Deterministic gate

- `bash -n`：Fog worker與 daily quota均通過。
- Retry-circuit shell regression：通過。
- Runtime-time wiring shell regression：通過。
- I5 affected pytest：
  `96 passed in 3.01s`。

### Bounded dry frontier

Canonical market date是`2026-07-28`，但當日 weekend inventory尚未建立。
直接 recovery會被 verifier正確拒絕。因此 frontier是先以
`TOP10_WEEKEND_CLEANUP_ENABLED=0`執行 linkage-only controlled-grid host
runner；它只能建立／驗證 current inventory與 bounded frontier queue，不執行
replay、research、model mutation或 cleanup。

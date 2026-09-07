---
id: REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01
type: preflight-evidence
---

# Preflight

- Base commit：`8ddb7972bbebea04afefd138cbab0db6280c51ce`。
- Working tree：開卡前 clean；`main...origin/main [ahead 4]`。
- Production capacity measure：daily、external-review-preflight、fog-research-worker 均 `PASS`；memory pressure `1`，host free 約 38.6 GB。
- Production marker 保留，沒有 activation、kickstart 或 manual Fog run。
- RED command：Fog policy 對 `artifacts/external_review/{old,new}.json` 回傳兩條 registered-unmetered path，assertion exit `1`。
- Trace preflight：`verdict=OK`，無 critical／warning。
- Native delegation context gate：`PASS`；strict、clean context、shared sequential single writer，prompt `1371` bytes，SHA-256 `e1c773853945030071de79c1fb6e0f108d0616c37bfa95a835e9e24217ece8a8`。

## 假說順序

1. exact shared subtree 漏列（主假說）：加入後 RED 轉 GREEN且 inventory 納入 bytes/files。
2. Fog child 真越界（已由 sibling receipt/mtime 否證）。
3. 只改排程（不處理 deterministic contract，拒絕採用）。

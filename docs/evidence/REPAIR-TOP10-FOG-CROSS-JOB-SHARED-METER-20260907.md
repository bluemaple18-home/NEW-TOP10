---
id: REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-20260907
task: REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01
status: DEPLOYED_NATURAL_ACCEPTANCE_PENDING
date: 2026-09-07
---

# Fog cross-job shared meter 修復證據

## Production RED

- Active runtime：`/Users/mattkuo/TOP10-runtime-automation-26c8834`。
- Fog invocation：`fog-research-worker-20260907T090500Z-80610`。
- Stop marker：`REGISTERED_WRITE_OUTSIDE_METER`；child exit `143`；process group quiescent。
- 重疊的 `external-review-preflight-20260907T094000Z-1210` 在 Fog snapshot 期間刪除三個舊
  `artifacts/external_review` 檔案並寫入三個新檔。舊 Fog policy 將這六個合法 sibling changes
  判為 registered-unmetered。

## Bounded repair

只在 Fog 的既有 `meter_paths` 加入 exact `artifacts/external_review` subtree，並補上行為測試與
操作文件。未修改 production Python／shell／plist、hard ceilings、`launch_verified`、cleanup
allowlist、排程、自然驗收 counter 或 unknown-write gate；也未擴成整個 `artifacts`。

## RED / GREEN

```text
RED: exact test returned
('artifacts/external_review/new.json', 'artifacts/external_review/old.json') != ()

GREEN:
targeted shared-meter test: 1 passed
Storage Guard: 90 passed
Fog natural acceptance: 34 passed
Fog storage validation: 11 passed
activation failure-state: 58 passed
8-job policy load: PASS
observed production-path probe: changed=(), shared_meter_count=1
git diff --check: PASS
```

## Candidate identity 與容量

```text
top10-storage-policy.json  b9f6d822b2ce0bdf4694d3fd4640c3250cc3b019d2fec602b28df70148e4d8dd
top10-storage-safety.md    80f07d90a669708c3c02e260137950a41949e3f45dbb9cec0bf8870c345e6f91
test_storage_safety.py     1ebee4cf2ac2b5dcc5c9b6bea607c5039769f2b8cf269f45d87ba3714bc24fac
candidate inventory       1,291,575,653 bytes / 13,434 files
Fog hard ceilings         2,147,483,648 bytes / 30,000 files
headroom                   855,907,995 bytes / 16,566 files
```

主機 capacity preflight 對 Fog、daily、external-review-preflight 均為 PASS；memory pressure `1`，
free disk 約 `38.6 GB`。

## Review 與裁決

- Reviewer A（Anscombe）：`GO`，無 P0/P1；一項既存 fail-closed TOCTOU P2，另卡處理。
- Reviewer B（Kant）：`GO`，無 findings。
- Mainline：local candidate `MAINLINE_ACCEPTED_LOCAL`；production activation
  `ACTIVATED_PARTIAL_ACCEPTANCE_PENDING`。

2026-09-07 19:03（Asia/Taipei）已用既有 bounded transaction 把 daily、external-review-preflight、
Fog 三條 idle jobs 切到 detached runtime `/Users/mattkuo/TOP10-runtime-automation-bb55fc4`；CLI
exit `0`。舊 production marker 原檔及其 SHA 保留，新 runtime marker absent；未 manual run、
未 kickstart、未 push。

本 receipt 不宣告 Fog acceptance completed。production completion 必須由新 runtime 後續自然週期
receipt 明確達成 `acceptance_status=ACCEPTED` 與 `accepted_natural_cycles>=2`。

---
id: TSKG-SLC-01-mainline-acceptance
status: INTEGRATED
accepted_at: 2026-07-18
accepted_by: Codex 主線
accepted_successor: fbd8fa09ce570971b2ecbf6b18a92c47c42a8f5b
review_artifact_commit: 054f5c1b343e401b6bf9dbc420f7073253484ba6
integration_head_before_acceptance_record: 1e159f6
---

# TSKG-SLC-01 Mainline Acceptance

## Status

`REVIEW_GO / INTEGRATED`

本狀態只接受 synthetic/offline identity-to-company 垂直切片，不代表外部資料源、
crawler、LLM extraction、Neo4j、Postgres、Redis、production API 或 SLO 已完成。

## Evidence

- 原 candidate：`7e8006be813be627317a1087744615dafb547a81`。
- 初審：`REVIEW_NO_GO`，review commit `040f3806ecdcea9e7580f2586b9850312d48862a`。
- Repair successor：`fbd8fa09ce570971b2ecbf6b18a92c47c42a8f5b`。
- 同一 reviewer re-review：`REVIEW_GO`，review commit `054f5c1b343e401b6bf9dbc420f7073253484ba6`。
- F-01 temporal resolution、F-02 closed fixture schema、F-03 compound prohibited-key
  scanner、F-04 shared-path portability：全部 `RESOLVED`。
- 離線 focused tests：22/22；`py_compile`、allowlist、`git diff --check`、
  host-specific path scan 與 reviewer probes：全部通過。

## Mainline integration proof

- 整合前主線：`36e83750b39ae586cce8cad348fab79331c367cc`。
- implementation card、candidate、Repair card、Repair successor、最終 Review artifact
  五個 commits 依序 cherry-pick，無衝突；接受紀錄前 integration head 為 `1e159f6`。
- 使用者原有 `.gitignore`、research config/scripts 與元大輔助檔未被修改或納入整合。
- `app/api/main.py` 與 dependency manifests 未修改；router 維持 standalone。

## Environment note

原卡 `uv run --with-requirements requirements.txt` 在平台新 worktree 選到 Python 3.14，
與既有 `lxml==4.9.4` 不相容，因此沒有被誤記為 PASS。本輪使用 repo 既有 Python 3.11
環境完成離線驗證；此 caveat 不影響 SLC-01 行為契約，但後續應另卡處理 Python 3.13
toolchain 與 dependency compatibility。

## Next frontier

SLC-02 應先建立可稽核的 source snapshot／provenance ingestion，不得把本卡 synthetic
fixture 誤當真實公司或供應鏈事實，也不得直接把 standalone router 掛入 production API。

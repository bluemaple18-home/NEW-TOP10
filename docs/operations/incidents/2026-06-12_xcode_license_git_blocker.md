# 2026-06-12｜Xcode License 阻擋 Git 指令事件

## Root Cause

本機只找到 Apple 內建 Git：

```text
which -a git
/usr/bin/git

git --version
git version 2.50.1 (Apple Git-155)
```

Apple Git 依賴 Xcode / Command Line Tools license 狀態。當 license 未同意或系統更新後需要重新同意時，任何 Git 指令都會被擋下：

```text
You have not agreed to the Xcode license agreements.
Please run 'sudo xcodebuild -license' from within a Terminal window to review and agree to the Xcode and Apple SDKs license.
```

這不是 TOP10new repo 問題，也不是 commit 權限問題，而是 host-level toolchain 狀態問題。

## Impact

會影響同一台機器上所有使用 `/usr/bin/git` 的專案，包含：

- `git status`
- `git diff --check`
- `git add`
- `git commit`
- `git push`
- 任何 verifier 內部呼叫 Git 的檢查

本次直接影響：

- `git diff --check` 無法執行。
- `verify_liquidity_quality_strict_replay.py` 因 `git status --short` 非 0 而 fail-loud。
- 分包 commit / push 暫停，直到 license 被接受。

## Resolution

使用者在可見 macOS Terminal 中執行：

```bash
sudo xcodebuild -license accept
```

接受後驗證：

```text
git status --short: OK
git diff --check: OK
git --version: git version 2.50.1 (Apple Git-155)
```

## Why Codex Could Not Directly Finish It

Codex 的 sandbox escalation 只代表允許命令離開 sandbox 執行，不等於取得使用者 sudo 密碼。

第一次嘗試在 Codex PTY 內跑：

```bash
sudo xcodebuild -license accept
```

結果停在內部 `Password:`，使用者看不到可輸入密碼的視窗。

最後改用 macOS Terminal：

```bash
osascript -e 'tell application "Terminal" to activate' \
  -e 'tell application "Terminal" to do script "cd /Users/mattkuo/TOP10new && sudo xcodebuild -license accept"'
```

讓使用者在真正可見的 Terminal 輸入密碼後解決。

## AI-Core Follow-Up

建議 ai-core 加一個跨專案 host preflight：

```bash
git --version
git status --short
xcodebuild -license check
```

判定：

- 若 `git status` 出現 Xcode license 訊息，明確回報 host-level blocker。
- 不要把它誤判成 repo dirty / Git 權限 / commit 失敗。
- 指示使用者開 Terminal 跑 `sudo xcodebuild -license accept`。
- 若有 Homebrew Git，可評估是否在 toolchain path 中優先使用 `/opt/homebrew/bin/git`，避免 Apple Git license 狀態影響專案作業。

## Prevention

- 在所有會做 commit / push / verifier Git check 的流程前，先跑 Git availability preflight。
- 對 verifier 來說，Git 無法執行應該 fail-loud，不能吞掉。
- 對使用者說明時要分清楚：
  - 不是 commit 要密碼
  - 是 Apple Git 被 Xcode license 擋住
  - 這可能影響同機多個專案

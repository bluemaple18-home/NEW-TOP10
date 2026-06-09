#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$PROJECT_DIR/artifacts/external_review"
mkdir -p "$OUT_DIR"

MODE="probe"
PACKET_FILE=""
DATE_TEXT=""
URL_PART="${TOP10_GEMINI_URL_PART:-gemini.google.com/app}"
EXPECTED_TITLE="${TOP10_GEMINI_EXPECTED_TITLE:-}"
EXPECTED_ACCOUNT="${TOP10_GEMINI_EXPECTED_ACCOUNT:-}"
EXPECTED_PLAN="${TOP10_GEMINI_EXPECTED_PLAN:-}"
BROWSER_APP="${TOP10_GEMINI_BROWSER_APP:-Google Chrome}"
WAIT_SECONDS="${TOP10_REVIEW_WAIT_SECONDS:-45}"
TEST_PROMPT="${TOP10_GEMINI_TEST_PROMPT:-}"
COLLECT_RESPONSE_CONTAINS="${TOP10_GEMINI_COLLECT_RESPONSE_CONTAINS:-}"

JS_FILE=""
trap '[[ -n "$JS_FILE" ]] && rm -f "$JS_FILE"' EXIT

usage() {
  cat <<'EOF'
Usage:
  bash scripts/review_gemini_chrome.sh probe
  bash scripts/review_gemini_chrome.sh --date YYYY-MM-DD --packet artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.json
  bash scripts/review_gemini_chrome.sh collect --date YYYY-MM-DD --packet artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.json

Environment:
  TOP10_GEMINI_URL_PART        Chrome tab URL marker. Default: gemini.google.com/app
  TOP10_GEMINI_EXPECTED_TITLE  Optional visible title guard, e.g. 盤後選股檢討報告
  TOP10_GEMINI_EXPECTED_ACCOUNT Optional visible account guard, e.g. 風17 一年
  TOP10_GEMINI_EXPECTED_PLAN   Optional visible plan guard, e.g. Pro
  TOP10_GEMINI_BROWSER_APP     Browser app name. Default: Google Chrome
  TOP10_REVIEW_WAIT_SECONDS    Wait time after submit. Default: 45
  TOP10_GEMINI_TEST_PROMPT     Optional non-project prompt for smoke tests.
  TOP10_GEMINI_COLLECT_RESPONSE_CONTAINS Optional marker for collect mode.
EOF
}

python_bin() {
  local candidate="$PROJECT_DIR/.venv/bin/python"
  if [[ -x "$candidate" ]]; then
    printf '%s\n' "$candidate"
  else
    printf '%s\n' "python3"
  fi
}

verify_sendable_packet() {
  if [[ -n "$TEST_PROMPT" ]]; then
    return
  fi
  if [[ -z "$PACKET_FILE" ]]; then
    echo "send mode requires --packet so the exact payload can pass scripts/verify_external_review_packet.py" >&2
    exit 2
  fi
  if [[ "$URL_PART" == "gemini.google.com/app" || "$URL_PART" == "https://gemini.google.com/app" ]]; then
    echo "send mode requires TOP10_GEMINI_URL_PART to include the exact Gemini conversation id, not the broad gemini.google.com/app marker" >&2
    exit 2
  fi
  "$(python_bin)" "$PROJECT_DIR/scripts/verify_external_review_packet.py" --packet "$PACKET_FILE"
}

init_js_file() {
  if [[ -z "$JS_FILE" ]]; then
    JS_FILE="$(mktemp "${TMPDIR:-/tmp}/top10_gemini_review.XXXXXX")"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    probe|send|collect)
      MODE="$1"
      shift
      ;;
    --date)
      DATE_TEXT="${2:-}"
      shift 2
      ;;
    --packet)
      PACKET_FILE="${2:-}"
      if [[ "$MODE" == "probe" ]]; then
        MODE="send"
      fi
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

infer_date() {
  if [[ -n "$DATE_TEXT" ]]; then
    printf '%s\n' "$DATE_TEXT"
    return
  fi
  if [[ "$PACKET_FILE" =~ review_packet_([0-9]{4}-[0-9]{2}-[0-9]{2})\.json$ ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return
  fi
  echo "send mode requires --date YYYY-MM-DD or a review_packet_YYYY-MM-DD.json path" >&2
  exit 2
}

read_prompt() {
  if [[ -n "$TEST_PROMPT" ]]; then
    printf '%s\n' "$TEST_PROMPT"
    return
  fi
  if [[ -z "$PACKET_FILE" ]]; then
    echo "send mode requires --packet; TOP10_REVIEW_PROMPT/TOP10_REVIEW_PROMPT_FILE direct send is disabled" >&2
    exit 2
  fi
  "$(python_bin)" - "$PROJECT_DIR/docs/architecture/EXTERNAL_REVIEW_CONTRACT.md" "$PACKET_FILE" <<'PY'
import json
import re
import sys
from pathlib import Path

contract_path = Path(sys.argv[1])
packet_path = Path(sys.argv[2])
contract = contract_path.read_text(encoding="utf-8")
packet = json.loads(packet_path.read_text(encoding="utf-8"))
sendable_packet = {
    "packet_date": packet.get("packet_date"),
    "market": packet.get("market"),
    "market_overview": packet.get("market_overview"),
    "outcome_status": packet.get("outcome_status"),
    "recommendations": packet.get("recommendations"),
}

match = re.search(r"## Reviewer Prompt\b.*?```text\s+(.*?)\s+```", contract, flags=re.S)
if not match:
    raise SystemExit("Reviewer Prompt block not found in EXTERNAL_REVIEW_CONTRACT.md")
boundary = match.group(1).strip()
packet_date = packet.get("packet_date")

print(boundary)
print()
print(f"review_date={packet_date}, provider=gemini, market=TW。")
print("請用專業台股操盤手角度自由 review；請至少涵蓋：整體評分/信心、選股品質、主要優點、主要風險、可能誤判、強弱族群、隔日觀察重點、可回測研究假設。")
print("請優先回覆單一 JSON object，欄位名稱可以自然命名；如果資料不足，請明確寫出限制與需要人工判讀的地方。")
print("不要要求或推測內部演算法、權重、feature engineering、模型或未公開策略參數。")
print()
print("以下是已通過本地安全驗證的 review_packet 摘要，內容只取自 verified packet：")
print(json.dumps(sendable_packet, ensure_ascii=False, separators=(",", ":")))
PY
}

write_probe_js() {
  local expected_title_b64 expected_account_b64 expected_plan_b64
  expected_title_b64="$(printf '%s' "$EXPECTED_TITLE" | "$(python_bin)" -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())')"
  expected_account_b64="$(printf '%s' "$EXPECTED_ACCOUNT" | "$(python_bin)" -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())')"
  expected_plan_b64="$(printf '%s' "$EXPECTED_PLAN" | "$(python_bin)" -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())')"
  cat > "$JS_FILE" <<'JS'
(() => {
  const decode = (value) => new TextDecoder("utf-8").decode(Uint8Array.from(atob(value), (char) => char.charCodeAt(0)));
  const expectedTitle = decode("__EXPECTED_TITLE_B64__");
  const expectedAccount = decode("__EXPECTED_ACCOUNT_B64__");
  const expectedPlan = decode("__EXPECTED_PLAN_B64__");
  const bodyText = document.body.innerText || "";
  const guardFailures = [];
  if (expectedTitle && !document.title.includes(expectedTitle) && !bodyText.includes(expectedTitle)) guardFailures.push("expected_title_not_visible");
  if (expectedAccount && !bodyText.includes(expectedAccount)) guardFailures.push("expected_account_not_visible");
  if (expectedPlan && !bodyText.includes(expectedPlan)) guardFailures.push("expected_plan_not_visible");
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  };
  const composerSelectors = [
    "rich-textarea div[contenteditable='true']",
    "div.ql-editor[contenteditable='true']",
    "div[aria-label*='Enter a prompt']",
    "div[aria-label*='輸入提示']",
    "div[contenteditable='true']",
    "textarea"
  ];
  const sendSelectors = [
    "button[aria-label*='Send message']",
    "button[aria-label*='Send']",
    "button[aria-label*='傳送訊息']",
    "button[aria-label*='傳送']",
    "button[aria-label*='送出']",
    "button.send-button"
  ];
  const composer = composerSelectors.map((selector) => document.querySelector(selector)).find(visible);
  const sendButton = sendSelectors.map((selector) => document.querySelector(selector)).find(visible)
    || Array.from(document.querySelectorAll("button")).find((button) => visible(button) && /send|傳送|送出/i.test(`${button.getAttribute("aria-label") || ""} ${button.innerText || ""}`));
  return JSON.stringify({
    ok: guardFailures.length === 0,
    mode: "probe",
    reason: guardFailures.length ? "guard_failed" : null,
    guard_failures: guardFailures,
    expected_title: expectedTitle,
    expected_account: expectedAccount,
    expected_plan: expectedPlan,
    title: document.title,
    url: location.href,
    hasComposer: Boolean(composer),
    hasSendButton: Boolean(sendButton),
    bodySample: bodyText.slice(-500)
  });
})()
JS
  "$(python_bin)" - "$JS_FILE" "$expected_title_b64" "$expected_account_b64" "$expected_plan_b64" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
title, account, plan = sys.argv[2:]
text = path.read_text(encoding="utf-8")
text = text.replace("__EXPECTED_TITLE_B64__", title)
text = text.replace("__EXPECTED_ACCOUNT_B64__", account)
text = text.replace("__EXPECTED_PLAN_B64__", plan)
path.write_text(text, encoding="utf-8")
PY
}

write_send_js() {
  local prompt_b64
  local expected_title_b64 expected_account_b64 expected_plan_b64
  prompt_b64="$(read_prompt | "$(python_bin)" -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())')"
  expected_title_b64="$(printf '%s' "$EXPECTED_TITLE" | "$(python_bin)" -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())')"
  expected_account_b64="$(printf '%s' "$EXPECTED_ACCOUNT" | "$(python_bin)" -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())')"
  expected_plan_b64="$(printf '%s' "$EXPECTED_PLAN" | "$(python_bin)" -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())')"
  cat > "$JS_FILE" <<JS
(() => {
  const prompt = new TextDecoder("utf-8").decode(Uint8Array.from(atob("$prompt_b64"), (char) => char.charCodeAt(0)));
  const decode = (value) => new TextDecoder("utf-8").decode(Uint8Array.from(atob(value), (char) => char.charCodeAt(0)));
  const expectedTitle = decode("$expected_title_b64");
  const expectedAccount = decode("$expected_account_b64");
  const expectedPlan = decode("$expected_plan_b64");
  const bodyText = document.body.innerText || "";
  const guardFailures = [];
  if (expectedTitle && !document.title.includes(expectedTitle) && !bodyText.includes(expectedTitle)) guardFailures.push("expected_title_not_visible");
  if (expectedAccount && !bodyText.includes(expectedAccount)) guardFailures.push("expected_account_not_visible");
  if (expectedPlan && !bodyText.includes(expectedPlan)) guardFailures.push("expected_plan_not_visible");
  if (guardFailures.length) {
    return JSON.stringify({
      ok: false,
      mode: "fill",
      reason: "guard_failed",
      guard_failures: guardFailures,
      title: document.title,
      url: location.href,
      bodySample: bodyText.slice(-500)
    });
  }
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  };
  const textOf = (el) => (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
  const composerSelectors = [
    "rich-textarea div[contenteditable='true']",
    "div.ql-editor[contenteditable='true']",
    "div[aria-label*='Enter a prompt']",
    "div[aria-label*='輸入提示']",
    "div[contenteditable='true']",
    "textarea"
  ];

  const composer = composerSelectors.map((selector) => document.querySelector(selector)).find(visible);
  if (!composer) {
    return JSON.stringify({ ok: false, mode: "fill", reason: "composer_not_found", title: document.title, url: location.href });
  }

  composer.focus();
  if (composer.tagName === "TEXTAREA" || composer.tagName === "INPUT") {
    composer.value = prompt;
  } else {
    composer.replaceChildren(document.createTextNode(prompt));
    composer.classList.remove("ql-blank");
  }
  composer.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: prompt }));
  composer.dispatchEvent(new Event("change", { bubbles: true }));

  return JSON.stringify({
    ok: true,
    mode: "fill",
    title: document.title,
    url: location.href,
    promptChars: prompt.length,
    composerText: textOf(composer).slice(0, 200)
  });
})()
JS
}

write_submit_js() {
  cat > "$JS_FILE" <<'JS'
(() => {
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  };
  const sendSelectors = [
    "button[aria-label*='Send message']",
    "button[aria-label*='Send']",
    "button[aria-label*='傳送訊息']",
    "button[aria-label*='傳送']",
    "button[aria-label*='送出']",
    "button.send-button"
  ];
  const sendButton = sendSelectors.map((selector) => document.querySelector(selector)).find(visible)
    || Array.from(document.querySelectorAll("button")).filter(visible).slice(-1)[0];
  if (!sendButton) {
    return JSON.stringify({
      ok: false,
      mode: "submit",
      reason: "send_button_not_found",
      title: document.title,
      url: location.href
    });
  }
  sendButton.click();
  return JSON.stringify({
    ok: true,
    mode: "submit",
    submitted: true,
    title: document.title,
    url: location.href
  });
})()
JS
}

write_collect_js() {
  local collect_contains_b64
  collect_contains_b64="$(printf '%s' "$COLLECT_RESPONSE_CONTAINS" | "$(python_bin)" -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())')"
  cat > "$JS_FILE" <<'JS'
(() => {
  const textOf = (el) => (el.innerText || el.textContent || "").trim();
  const decode = (value) => new TextDecoder("utf-8").decode(Uint8Array.from(atob(value), (char) => char.charCodeAt(0)));
  const collectContains = decode("__COLLECT_RESPONSE_CONTAINS_B64__");
  const bodyText = document.body.innerText || "";
  const bodyTail = bodyText.slice(-12000);
  const userSaidMarker = String.fromCharCode(20320, 35498, 20102);
  const geminiSaidMarker = "Gemini " + String.fromCharCode(35498, 20102);
  const geminiDisclaimerMarker = "Gemini " + String.fromCharCode(26159) + " AI";
  const cleanResponse = (text) => {
    let response = (text || "").trim();
    for (const marker of ["\n\nFlash", "\nFlash", "\n\n" + geminiDisclaimerMarker, "\n" + geminiDisclaimerMarker]) {
      const index = response.indexOf(marker);
      if (index >= 0) {
        response = response.slice(0, index).trim();
      }
    }
    return response;
  };
  const transcriptResponses = bodyText.split(userSaidMarker).slice(1).map((segment) => {
    if (!segment.includes(geminiSaidMarker)) {
      return "";
    }
    return cleanResponse(segment.split(geminiSaidMarker).pop());
  }).filter(Boolean);
  const matchingTranscriptResponse = collectContains
    ? transcriptResponses.filter((text) => text.includes(collectContains)).pop() || ""
    : "";
  const latestTranscriptResponse = matchingTranscriptResponse || transcriptResponses[transcriptResponses.length - 1] || "";
  const responseSelectors = [
    "model-response",
    "[data-test-id='response']",
    "[data-testid='response']",
    ".model-response-text",
    ".response-container",
    ".markdown",
    "message-content"
  ];
  const responseNodes = responseSelectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)));
  const visibleResponses = responseNodes
    .filter((node, index, nodes) => nodes.indexOf(node) === index)
    .filter((node) => {
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
    })
    .map((node) => textOf(node))
    .filter((text) => text.length > 40);
  const lastAssistant = visibleResponses[visibleResponses.length - 1] || "";
  const rawResponse = latestTranscriptResponse || lastAssistant;
  return JSON.stringify({
    ok: Boolean(rawResponse),
    mode: "collect",
    title: document.title,
    url: location.href,
    assistant_count: visibleResponses.length,
    transcript_response_count: transcriptResponses.length,
    collect_response_contains: collectContains,
    transcript_response_chars: latestTranscriptResponse.length,
    raw_response: rawResponse,
    body_tail: bodyTail
  });
})()
JS
  "$(python_bin)" - "$JS_FILE" "$collect_contains_b64" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
collect_contains = sys.argv[2]
text = path.read_text(encoding="utf-8")
text = text.replace("__COLLECT_RESPONSE_CONTAINS_B64__", collect_contains)
path.write_text(text, encoding="utf-8")
PY
}

run_chrome_js() {
  osascript \
    -e 'set jsSource to read POSIX file "'"$JS_FILE"'"' \
    -e 'tell application "'"$BROWSER_APP"'"' \
    -e 'set targetURLPart to "'"$URL_PART"'"' \
    -e 'repeat with windowIndex from 1 to count of windows' \
    -e 'set w to window windowIndex' \
    -e 'repeat with tabIndex from 1 to count of tabs of w' \
    -e 'set t to tab tabIndex of w' \
    -e 'set tabUrl to URL of t' \
    -e 'if tabUrl contains targetURLPart then' \
    -e 'set active tab index of w to tabIndex' \
    -e 'set index of w to 1' \
    -e 'return execute t javascript jsSource' \
    -e 'end if' \
    -e 'end repeat' \
    -e 'end repeat' \
    -e 'error "Gemini review tab not found"' \
    -e 'end tell'
}

write_evidence() {
  local kind="$1"
  local payload="$2"
  local stamp
  stamp="$(date +"%Y%m%d_%H%M%S")"
  local path="$OUT_DIR/gemini_${kind}_${stamp}.json"
  "$(python_bin)" - "$path" "$payload" <<'PY'
import json
import sys

path, raw = sys.argv[1:]
try:
    payload = json.loads(raw)
except Exception:
    payload = {"ok": False, "reason": "invalid_json", "raw": raw[-4000:]}

with open(path, "w", encoding="utf-8") as file:
    json.dump(payload, file, ensure_ascii=False, indent=2)
    file.write("\n")

print(path)
PY
}

require_payload_ok() {
  local kind="$1"
  local payload="$2"
  "$(python_bin)" - "$kind" "$payload" <<'PY'
import json
import sys

kind, raw = sys.argv[1:]
try:
    payload = json.loads(raw)
except Exception as exc:
    print(f"{kind}: invalid JSON payload: {exc}", file=sys.stderr)
    raise SystemExit(1)

if payload.get("ok") is not True:
    print(f"{kind}: failed: {json.dumps(payload, ensure_ascii=False)}", file=sys.stderr)
    raise SystemExit(1)
PY
}

store_gemini_response() {
  local date_text="$1"
  local payload="$2"
  local review_dir="$OUT_DIR/$date_text"
  mkdir -p "$review_dir"
  if [[ -n "$TEST_PROMPT" ]]; then
    local smoke_path="$review_dir/gemini_smoke_${date_text}.json"
    "$(python_bin)" - "$payload" "$smoke_path" <<'PY'
import json
import sys
from pathlib import Path

payload_raw, smoke_path_raw = sys.argv[1:]
try:
    payload = json.loads(payload_raw)
except Exception as exc:
    payload = {"ok": False, "reason": "invalid_collect_payload", "error": str(exc), "raw": payload_raw}

path = Path(smoke_path_raw)
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"smoke={path}")
PY
    return
  fi
  local raw_path="$review_dir/gemini_raw_${date_text}.txt"
  local response_path="$review_dir/gemini_response_${date_text}.json"
  local status_path="$review_dir/gemini_collect_status_${date_text}.json"
  "$(python_bin)" - "$payload" "$raw_path" "$response_path" "$status_path" <<'PY'
import json
import sys
from pathlib import Path

payload_raw, raw_path_raw, response_path_raw, status_path_raw = sys.argv[1:]
raw_path = Path(raw_path_raw)
response_path = Path(response_path_raw)
status_path = Path(status_path_raw)

try:
    payload = json.loads(payload_raw)
except Exception as exc:
    payload = {"ok": False, "reason": "invalid_collect_payload", "error": str(exc), "raw": payload_raw}

raw_response = str(payload.get("raw_response") or "").strip()
if not raw_response and payload.get("body_tail"):
    raw_response = str(payload.get("body_tail") or "").strip()
raw_path.write_text(raw_response + ("\n" if raw_response else ""), encoding="utf-8")

status = {
    "ok": False,
    "raw_path": str(raw_path),
    "response_path": str(response_path),
    "reason": "raw_saved_pending_normalize",
    "assistant_count": payload.get("assistant_count"),
    "raw_chars": len(raw_response),
}
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(status, ensure_ascii=False))
PY

  if "$(python_bin)" "$PROJECT_DIR/scripts/normalize_external_review_response.py" \
    --provider gemini \
    --date "$date_text" \
    --raw "$raw_path" \
    --packet "$PACKET_FILE" \
    --out "$response_path"; then
    "$(python_bin)" - "$status_path" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
status = json.loads(path.read_text(encoding="utf-8"))
status["reason"] = "normalized_pending_contract"
path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  else
    "$(python_bin)" - "$status_path" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
status = json.loads(path.read_text(encoding="utf-8"))
status["ok"] = False
status["reason"] = "normalize_failed"
path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
    printf 'raw=%s\nresponse=%s\nstatus=%s\n' "$raw_path" "$response_path" "$status_path"
    return 1
  fi

  if "$(python_bin)" "$PROJECT_DIR/scripts/verify_external_review_contract.py" "$response_path"; then
    "$(python_bin)" - "$status_path" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
status = json.loads(path.read_text(encoding="utf-8"))
status["ok"] = True
status["reason"] = "normalized_contract_ok"
path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
  else
    "$(python_bin)" - "$status_path" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
status = json.loads(path.read_text(encoding="utf-8"))
status["ok"] = False
status["reason"] = "contract_failed"
path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
    printf 'raw=%s\nresponse=%s\nstatus=%s\n' "$raw_path" "$response_path" "$status_path"
    return 1
  fi
  printf 'raw=%s\nresponse=%s\nstatus=%s\n' "$raw_path" "$response_path" "$status_path"
}

case "$MODE" in
  probe)
    init_js_file
    write_probe_js
    result="$(run_chrome_js)"
    evidence_path="$(write_evidence probe "$result")"
    printf '%s\n' "$result"
    printf 'evidence=%s\n' "$evidence_path"
    require_payload_ok probe "$result"
    ;;
  send)
    date_text="$(infer_date)"
    verify_sendable_packet
    init_js_file
    write_send_js
    result="$(run_chrome_js)"
    evidence_path="$(write_evidence fill "$result")"
    printf '%s\n' "$result"
    printf 'evidence=%s\n' "$evidence_path"
    require_payload_ok fill "$result"
    sleep 1
    write_submit_js
    submit_result="$(run_chrome_js)"
    submit_path="$(write_evidence submit "$submit_result")"
    printf '%s\n' "$submit_result"
    printf 'submit_evidence=%s\n' "$submit_path"
    require_payload_ok submit "$submit_result"
    sleep "$WAIT_SECONDS"
    write_collect_js
    collect_result="$(run_chrome_js)"
    collect_path="$(write_evidence collect "$collect_result")"
    printf '%s\n' "$collect_result"
    printf 'collect_evidence=%s\n' "$collect_path"
    require_payload_ok collect "$collect_result"
    store_gemini_response "$date_text" "$collect_result"
    ;;
  collect)
    date_text="$(infer_date)"
    verify_sendable_packet
    init_js_file
    write_collect_js
    collect_result="$(run_chrome_js)"
    collect_path="$(write_evidence collect "$collect_result")"
    printf '%s\n' "$collect_result"
    printf 'collect_evidence=%s\n' "$collect_path"
    require_payload_ok collect "$collect_result"
    store_gemini_response "$date_text" "$collect_result"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

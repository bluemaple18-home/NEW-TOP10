#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$PROJECT_DIR/artifacts/external_review"
mkdir -p "$OUT_DIR"

MODE="probe"
PACKET_FILE=""
DATE_TEXT=""
URL_PART="${TOP10_CHATGPT_URL_PART:-chatgpt.com/c/6a27bb97}"
WAIT_SECONDS="${TOP10_REVIEW_WAIT_SECONDS:-45}"

JS_FILE=""
trap '[[ -n "$JS_FILE" ]] && rm -f "$JS_FILE"' EXIT

usage() {
  cat <<'EOF'
Usage:
  bash scripts/review_chatgpt_chrome.sh probe
  bash scripts/review_chatgpt_chrome.sh --date YYYY-MM-DD --packet artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.json

Environment:
  TOP10_CHATGPT_URL_PART       Chrome tab URL marker. Default: chatgpt.com/c/6a27bb97
  TOP10_REVIEW_WAIT_SECONDS    Wait time after submit. Default: 45
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
  if [[ -z "$PACKET_FILE" ]]; then
    echo "send mode requires --packet so the exact payload can pass scripts/verify_external_review_packet.py" >&2
    exit 2
  fi
  "$(python_bin)" "$PROJECT_DIR/scripts/verify_external_review_packet.py" --packet "$PACKET_FILE"
}

init_js_file() {
  if [[ -z "$JS_FILE" ]]; then
    JS_FILE="$(mktemp "${TMPDIR:-/tmp}/top10_chatgpt_review.XXXXXX")"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    probe|send)
      MODE="$1"
      shift
      ;;
    --date)
      DATE_TEXT="${2:-}"
      shift 2
      ;;
    --packet)
      PACKET_FILE="${2:-}"
      MODE="send"
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
print(f"review_date={packet_date}, provider=chatgpt, market=TW。")
print("請用專業台股操盤手角度自由 review；請至少涵蓋：整體評分/信心、選股品質、主要優點、主要風險、可能誤判、強弱族群、隔日觀察重點、可回測研究假設。")
print("請優先回覆單一 JSON object，欄位名稱可以自然命名；如果資料不足，請明確寫出限制與需要人工判讀的地方。")
print("不要要求或推測內部演算法、權重、feature engineering、模型或未公開策略參數。")
print()
print("以下是已通過本地安全驗證的 review_packet 摘要，內容只取自 verified packet：")
print(json.dumps(sendable_packet, ensure_ascii=False, separators=(",", ":")))
PY
}

write_probe_js() {
  cat > "$JS_FILE" <<'JS'
(() => {
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  };
  const composerSelectors = ["#prompt-textarea", "[data-testid='prompt-textarea']", "div[contenteditable='true']", "textarea"];
  const sendSelectors = [
    "[data-testid='send-button']",
    "button[data-testid='composer-submit-button']",
    "button[aria-label*='Send']",
    "button[aria-label*='傳送']",
    "button[aria-label*='送出']"
  ];
  const composer = composerSelectors.map((selector) => document.querySelector(selector)).find(visible);
  const sendButton = sendSelectors.map((selector) => document.querySelector(selector)).find(visible);
  return JSON.stringify({
    ok: true,
    mode: "probe",
    title: document.title,
    url: location.href,
    hasComposer: Boolean(composer),
    hasSendButton: Boolean(sendButton),
    bodySample: (document.body.innerText || "").slice(-500)
  });
})()
JS
}

write_send_js() {
  local prompt_b64
  prompt_b64="$(read_prompt | "$(python_bin)" -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())')"
  cat > "$JS_FILE" <<JS
(() => {
  const prompt = new TextDecoder("utf-8").decode(Uint8Array.from(atob("$prompt_b64"), (char) => char.charCodeAt(0)));
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  };
  const textOf = (el) => (el.innerText || el.textContent || "").replace(/\\s+/g, " ").trim();
  const composerSelectors = ["#prompt-textarea", "[data-testid='prompt-textarea']", "div[contenteditable='true']", "textarea"];

  const composer = composerSelectors.map((selector) => document.querySelector(selector)).find(visible);
  if (!composer) {
    return JSON.stringify({ ok: false, mode: "fill", reason: "composer_not_found", title: document.title, url: location.href });
  }

  composer.focus();
  if (composer.tagName === "TEXTAREA" || composer.tagName === "INPUT") {
    composer.value = prompt;
  } else {
    composer.textContent = "";
    composer.appendChild(document.createTextNode(prompt));
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
    "[data-testid='send-button']",
    "button[data-testid='composer-submit-button']",
    "button[aria-label*='Send']",
    "button[aria-label*='傳送']",
    "button[aria-label*='送出']"
  ];
  const sendButton = sendSelectors.map((selector) => document.querySelector(selector)).find(visible);
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
  cat > "$JS_FILE" <<'JS'
(() => {
  const textOf = (el) => (el.innerText || el.textContent || "").trim();
  const assistantNodes = Array.from(document.querySelectorAll("[data-message-author-role='assistant']"));
  const lastAssistantNode = assistantNodes[assistantNodes.length - 1] || null;
  const lastAssistant = lastAssistantNode ? textOf(lastAssistantNode) : "";
  const bodyTail = (document.body.innerText || "").slice(-12000);
  return JSON.stringify({
    ok: Boolean(lastAssistant),
    mode: "collect",
    title: document.title,
    url: location.href,
    assistant_count: assistantNodes.length,
    raw_response: lastAssistant,
    body_tail: bodyTail
  });
})()
JS
}

run_chrome_js() {
  osascript \
    -e 'set jsSource to read POSIX file "'"$JS_FILE"'"' \
    -e 'tell application "Google Chrome"' \
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
    -e 'error "ChatGPT review tab not found"' \
    -e 'end tell'
}

write_evidence() {
  local kind="$1"
  local payload="$2"
  local stamp
  stamp="$(date +"%Y%m%d_%H%M%S")"
  local path="$OUT_DIR/chatgpt_${kind}_${stamp}.json"
  python3 - "$path" "$payload" <<'PY'
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

store_chatgpt_response() {
  local date_text="$1"
  local payload="$2"
  local review_dir="$OUT_DIR/$date_text"
  mkdir -p "$review_dir"
  local raw_path="$review_dir/chatgpt_raw_${date_text}.txt"
  local response_path="$review_dir/chatgpt_response_${date_text}.json"
  local status_path="$review_dir/chatgpt_collect_status_${date_text}.json"
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
    --provider chatgpt \
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
    sleep 1
    write_submit_js
    submit_result="$(run_chrome_js)"
    submit_path="$(write_evidence submit "$submit_result")"
    printf '%s\n' "$submit_result"
    printf 'submit_evidence=%s\n' "$submit_path"
    sleep "$WAIT_SECONDS"
    write_collect_js
    collect_result="$(run_chrome_js)"
    collect_path="$(write_evidence collect "$collect_result")"
    printf '%s\n' "$collect_result"
    printf 'collect_evidence=%s\n' "$collect_path"
    store_chatgpt_response "$date_text" "$collect_result"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

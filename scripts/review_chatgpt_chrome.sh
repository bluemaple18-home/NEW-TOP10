#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_OUT_DIR="$PROJECT_DIR/artifacts/external_review"
OUTPUT_ROOT_OVERRIDE="${TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT:-}"
if [[ -n "$OUTPUT_ROOT_OVERRIDE" ]]; then
  if [[ "$OUTPUT_ROOT_OVERRIDE" != /* || "$OUTPUT_ROOT_OVERRIDE" == "/" || ! -d "$OUTPUT_ROOT_OVERRIDE" ]]; then
    echo "TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT must be an existing absolute non-root directory" >&2
    exit 64
  fi
  OUT_DIR="$(cd -P "$OUTPUT_ROOT_OVERRIDE" && pwd)"
  if [[ "$OUT_DIR" != "$OUTPUT_ROOT_OVERRIDE" ]]; then
    echo "TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT must not contain symlink or traversal components" >&2
    exit 64
  fi
else
  OUT_DIR="$DEFAULT_OUT_DIR"
  mkdir -p "$OUT_DIR"
fi

MODE="probe"
PACKET_FILE=""
DATE_TEXT=""
URL_PART="${TOP10_CHATGPT_URL_PART:-chatgpt.com/g/g-p-6a27bb719e708191bd6eefae64c7c08c/c/6a27bb97-8f80-8324-ab52-3f861a006ee3}"
WAIT_SECONDS="${TOP10_REVIEW_WAIT_SECONDS:-45}"
TEST_PROMPT="${TOP10_CHATGPT_TEST_PROMPT:-}"
PRINT_PROBE_CONFIG=false
MATERIALIZE_PROBE_JS_TEST_ONLY=false
MATERIALIZE_COLLECT_JS_TEST_ONLY=false
PROBE_JS_B64='KCgpID0+IHsKICBjb25zdCB2aXNpYmxlID0gKGVsKSA9PiB7CiAgICBpZiAoIWVsKSByZXR1cm4gZmFsc2U7CiAgICBjb25zdCByZWN0ID0gZWwuZ2V0Qm91bmRpbmdDbGllbnRSZWN0KCk7CiAgICBjb25zdCBzdHlsZSA9IGdldENvbXB1dGVkU3R5bGUoZWwpOwogICAgcmV0dXJuIHJlY3Qud2lkdGggPiAwICYmIHJlY3QuaGVpZ2h0ID4gMCAmJiBzdHlsZS5kaXNwbGF5ICE9PSAibm9uZSIgJiYgc3R5bGUudmlzaWJpbGl0eSAhPT0gImhpZGRlbiI7CiAgfTsKICBjb25zdCBjb21wb3NlclNlbGVjdG9ycyA9IFsiI3Byb21wdC10ZXh0YXJlYSIsICJbZGF0YS10ZXN0aWQ9J3Byb21wdC10ZXh0YXJlYSddIiwgImRpdltjb250ZW50ZWRpdGFibGU9J3RydWUnXSIsICJ0ZXh0YXJlYSJdOwogIGNvbnN0IHNlbmRTZWxlY3RvcnMgPSBbCiAgICAiW2RhdGEtdGVzdGlkPSdzZW5kLWJ1dHRvbiddIiwKICAgICJidXR0b25bZGF0YS10ZXN0aWQ9J2NvbXBvc2VyLXN1Ym1pdC1idXR0b24nXSIsCiAgICAiYnV0dG9uW2FyaWEtbGFiZWwqPSdTZW5kJ10iLAogICAgImJ1dHRvblthcmlhLWxhYmVsKj0n5YKz6YCBJ10iLAogICAgImJ1dHRvblthcmlhLWxhYmVsKj0n6YCB5Ye6J10iCiAgXTsKICBjb25zdCBjb21wb3NlciA9IGNvbXBvc2VyU2VsZWN0b3JzLm1hcCgoc2VsZWN0b3IpID0+IGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3Ioc2VsZWN0b3IpKS5maW5kKHZpc2libGUpOwogIGNvbnN0IHNlbmRCdXR0b24gPSBzZW5kU2VsZWN0b3JzLm1hcCgoc2VsZWN0b3IpID0+IGRvY3VtZW50LnF1ZXJ5U2VsZWN0b3Ioc2VsZWN0b3IpKS5maW5kKHZpc2libGUpOwogIHJldHVybiBKU09OLnN0cmluZ2lmeSh7CiAgICBvazogQm9vbGVhbihjb21wb3NlciksCiAgICBtb2RlOiAicHJvYmUiLAogICAgcmVhZGluZXNzOiBjb21wb3NlciA/ICJpbnB1dF9yZWFkeSIgOiAiY29tcG9zZXJfbWlzc2luZyIsCiAgICB0aXRsZTogZG9jdW1lbnQudGl0bGUsCiAgICB1cmw6IGxvY2F0aW9uLmhyZWYsCiAgICBoYXNDb21wb3NlcjogQm9vbGVhbihjb21wb3NlciksCiAgICBoYXNTZW5kQnV0dG9uOiBCb29sZWFuKHNlbmRCdXR0b24pLAogICAgYm9keVNhbXBsZTogKGRvY3VtZW50LmJvZHkuaW5uZXJUZXh0IHx8ICIiKS5zbGljZSgtNTAwKQogIH0pOwp9KSgpCg=='

JS_FILE=""
trap '[[ -n "$JS_FILE" && "$MATERIALIZE_PROBE_JS_TEST_ONLY" != "true" && "$MATERIALIZE_COLLECT_JS_TEST_ONLY" != "true" ]] && rm -f "$JS_FILE"' EXIT

usage() {
  cat <<'EOF'
Usage:
  bash scripts/review_chatgpt_chrome.sh probe
  bash scripts/review_chatgpt_chrome.sh --date YYYY-MM-DD --packet artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.json
  bash scripts/review_chatgpt_chrome.sh collect --date YYYY-MM-DD --packet artifacts/external_review/YYYY-MM-DD/review_packet_YYYY-MM-DD.json

Environment:
  TOP10_CHATGPT_URL_PART       Chrome tab URL marker. Default: current TOP10 ChatGPT project conversation.
  TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT Existing canonical absolute sandbox directory for local probe evidence.
  TOP10_REVIEW_WAIT_SECONDS    Wait time after submit. Default: 45
  TOP10_CHATGPT_TEST_PROMPT    Optional non-project prompt for smoke tests.
  TOP10_CHATGPT_COLLECT_MIN_CHARS Minimum correlated assistant chars. Default: 500
  TOP10_CHATGPT_COLLECT_STABLE_TIMEOUT Seconds to wait for a correlated stable response. Default: 150
  TOP10_CHATGPT_COLLECT_STABLE_INTERVAL Seconds between collect snapshots. Default: 5
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
  "$(python_bin)" "$PROJECT_DIR/scripts/verify_external_review_packet.py" --packet "$PACKET_FILE"
}

init_js_file() {
  if [[ -z "$JS_FILE" ]]; then
    if [[ -n "$OUTPUT_ROOT_OVERRIDE" ]]; then
      JS_FILE="$(mktemp "$OUT_DIR/.top10_chatgpt_probe.js.XXXXXX")"
    else
      JS_FILE="$(mktemp "${TMPDIR:-/tmp}/top10_chatgpt_review.XXXXXX")"
    fi
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
    --print-probe-config)
      PRINT_PROBE_CONFIG=true
      shift
      ;;
    --materialize-probe-js-test-only)
      MATERIALIZE_PROBE_JS_TEST_ONLY=true
      shift
      ;;
    --materialize-collect-js-test-only)
      MATERIALIZE_COLLECT_JS_TEST_ONLY=true
      shift
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

if [[ "$PRINT_PROBE_CONFIG" == "true" ]]; then
  "$(python_bin)" - "$OUT_DIR" "$URL_PART" <<'PY'
import json
import sys

print(json.dumps({"mode": "probe_only", "review_packet_sent": False, "output_root": sys.argv[1], "target_url_part": sys.argv[2]}))
PY
  exit 0
fi

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
  if [[ -n "$OUTPUT_ROOT_OVERRIDE" ]]; then
    printf '%s' "$PROBE_JS_B64" | "$(python_bin)" -c 'import base64,sys; from pathlib import Path; Path(sys.argv[1]).write_bytes(base64.b64decode(sys.stdin.buffer.read()))' "$JS_FILE"
    return
  fi
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
    ok: Boolean(composer),
    mode: "probe",
    readiness: composer ? "input_ready" : "composer_missing",
    title: document.title,
    url: location.href,
    hasComposer: Boolean(composer),
    hasSendButton: Boolean(sendButton),
    bodySample: (document.body.innerText || "").slice(-500)
  });
})()
JS
}

if [[ "$MATERIALIZE_PROBE_JS_TEST_ONLY" == "true" ]]; then
  if [[ -z "$OUTPUT_ROOT_OVERRIDE" ]]; then
    echo "--materialize-probe-js-test-only requires TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT" >&2
    exit 64
  fi
  init_js_file
  write_probe_js
  "$(python_bin)" -c 'import hashlib,json,sys; from pathlib import Path; path=Path(sys.argv[1]); print(json.dumps({"mode":"probe_only","review_packet_sent":False,"js_file":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}))' "$JS_FILE"
  exit 0
fi

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
  local collect_date="$1"
  local min_chars="${TOP10_CHATGPT_COLLECT_MIN_CHARS:-500}"
  cat > "$JS_FILE" <<'JS'
(() => {
  const reviewDate = "__TOP10_REVIEW_DATE__";
  const minChars = Number("__TOP10_MIN_CHARS__");
  const textOf = (el) => (el?.innerText || el?.textContent || "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .trim();
  const visible = (el) => {
    if (!el) return false;
    const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 1, height: 1 };
    const style = typeof getComputedStyle === "function" ? getComputedStyle(el) : { display: "block", visibility: "visible" };
    return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  };
  const generationBusy = () => {
    const busySelectors = [
      "[data-testid='stop-button']",
      "button[aria-label*='Stop']",
      "button[aria-label*='停止']",
      "[aria-busy='true']"
    ];
    return busySelectors.some((selector) => Array.from(document.querySelectorAll(selector)).some(visible));
  };
  const marker = {
    reviewDate: `review_date=${reviewDate}`,
    provider: "provider=chatgpt",
    market: "market=TW",
    packetDate: `"packet_date":"${reviewDate}"`
  };
  const hasAllMarkers = (text) => (
    text.includes(marker.reviewDate) &&
    text.includes(marker.provider) &&
    text.includes(marker.market) &&
    text.includes(marker.packetDate)
  );
  const rejectReason = (text) => {
    const trimmed = (text || "").trim();
    if (trimmed.length < minChars) return "assistant_response_too_short";
    if (trimmed === "{\"review" || trimmed.startsWith("{\"review") && trimmed.length < minChars) return "assistant_response_prefix_only";
    if (trimmed.includes("SPEC: Taiwan Stock Knowledge Graph") || trimmed.includes("Taiwan Stock Knowledge Graph (TSKG)")) return "stale_tskg_response";
    if (trimmed.includes("top10-browser") || trimmed.includes("top10-chatgpt-script-click")) return "smoke_marker_detected";
    if (!trimmed.includes("{") || !trimmed.includes("}")) return "assistant_response_not_complete_json_like";
    return null;
  };
  const nodes = Array.from(document.querySelectorAll("[data-message-author-role]"));
  const messages = nodes.map((node, index) => {
    const role = node.getAttribute("data-message-author-role");
    const text = textOf(node);
    const article = node.closest ? (node.closest("article, [data-testid^='conversation-turn'], [data-testid*='conversation-turn']") || node) : node;
    return {
      index,
      role,
      chars: text.length,
      preview: text.slice(0, 180),
      text,
      ariaLabel: node.getAttribute("aria-label") || article.getAttribute?.("aria-label") || "",
      testId: node.getAttribute("data-testid") || article.getAttribute?.("data-testid") || "",
      id: node.id || article.id || ""
    };
  }).filter((item) => item.role === "user" || item.role === "assistant");
  const correlatedUsers = messages.filter((item) => item.role === "user" && hasAllMarkers(item.text));
  const selectedUser = correlatedUsers.at(-1) || null;
  const assistantsAfter = selectedUser
    ? messages.filter((item) => item.role === "assistant" && item.index > selectedUser.index && item.text)
    : [];
  const selected = assistantsAfter.at(-1) || null;
  const rejection = selected ? rejectReason(selected.text) : "assistant_after_correlated_user_missing";
  const bodyTail = (document.body?.innerText || "").slice(-12000);
  const correlation = {
    marker,
    message_count: messages.length,
    correlated_user_count: correlatedUsers.length,
    selected_user_index: selectedUser ? selectedUser.index : null,
    selected_user_chars: selectedUser ? selectedUser.chars : 0,
    assistants_after_selected_user: assistantsAfter.length,
    selected_assistant_index: selected ? selected.index : null,
    selected_assistant_chars: selected ? selected.chars : 0,
    generation_busy: generationBusy(),
    rejection_reason: generationBusy() ? "generation_still_busy" : rejection,
    user_preview: selectedUser ? selectedUser.preview : "",
    assistant_preview: selected ? selected.preview : ""
  };
  return JSON.stringify({
    ok: Boolean(selected && !correlation.generation_busy && !rejection),
    mode: "collect",
    title: document.title,
    url: location.href,
    assistant_count: messages.filter((item) => item.role === "assistant").length,
    selected_assistant_index: selected ? selected.index : null,
    selected_assistant_chars: selected ? selected.chars : 0,
    assistant_candidates: assistantsAfter.map(({ index, chars, preview }) => ({ index, chars, preview })),
    correlation,
    raw_response: selected && !correlation.generation_busy && !rejection ? selected.text : "",
    body_tail: bodyTail
  });
})()
JS
  "$(python_bin)" - "$JS_FILE" "$collect_date" "$min_chars" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
contents = path.read_text(encoding="utf-8")
contents = contents.replace("__TOP10_REVIEW_DATE__", sys.argv[2])
contents = contents.replace("__TOP10_MIN_CHARS__", sys.argv[3])
path.write_text(contents, encoding="utf-8")
PY
}

if [[ "$MATERIALIZE_COLLECT_JS_TEST_ONLY" == "true" ]]; then
  if [[ -z "$OUTPUT_ROOT_OVERRIDE" ]]; then
    echo "--materialize-collect-js-test-only requires TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT" >&2
    exit 64
  fi
  if [[ -z "$DATE_TEXT" ]]; then
    echo "--materialize-collect-js-test-only requires --date YYYY-MM-DD" >&2
    exit 2
  fi
  init_js_file
  write_collect_js "$DATE_TEXT"
  "$(python_bin)" -c 'import hashlib,json,sys; from pathlib import Path; path=Path(sys.argv[1]); print(json.dumps({"mode":"collect_js_only","review_packet_sent":False,"js_file":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}))' "$JS_FILE"
  exit 0
fi

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

collect_stable_result() {
  local timeout_seconds="${TOP10_CHATGPT_COLLECT_STABLE_TIMEOUT:-150}"
  local interval_seconds="${TOP10_CHATGPT_COLLECT_STABLE_INTERVAL:-5}"
  local deadline=$((SECONDS + timeout_seconds))
  local previous_hash=""
  local attempt=0
  local last_result=""

  while (( SECONDS <= deadline )); do
    attempt=$((attempt + 1))
    last_result="$(run_chrome_js)"
    local summary
    summary="$(printf '%s' "$last_result" | "$(python_bin)" -c 'import hashlib,json,sys
try:
    payload=json.load(sys.stdin)
except Exception:
    payload={}
raw=str(payload.get("raw_response") or "")
correlation=payload.get("correlation") if isinstance(payload.get("correlation"), dict) else {}
print("\t".join([
    "true" if payload.get("ok") is True else "false",
    hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw else "",
    str(len(raw)),
    str(correlation.get("rejection_reason") or ""),
    "true" if correlation.get("generation_busy") is True else "false",
]))
')"
    local ok raw_hash raw_chars rejection_reason generation_busy
    IFS=$'\t' read -r ok raw_hash raw_chars rejection_reason generation_busy <<< "$summary"
    printf 'COLLECT_SNAPSHOT attempt=%s ok=%s raw_chars=%s generation_busy=%s rejection=%s\n' "$attempt" "$ok" "$raw_chars" "$generation_busy" "$rejection_reason" >&2
    if [[ "$ok" == "true" && -n "$raw_hash" && "$raw_hash" == "$previous_hash" ]]; then
      "$(python_bin)" -c '
import json
import sys

payload = json.loads(sys.argv[1])
payload["stability"] = {
    "stable": True,
    "required_stable_snapshots": 2,
    "attempts": int(sys.argv[2]),
}
print(json.dumps(payload, ensure_ascii=False))
' "$last_result" "$attempt"
      return 0
    fi
    if [[ "$ok" == "true" && -n "$raw_hash" ]]; then
      previous_hash="$raw_hash"
    else
      previous_hash=""
    fi
    if (( SECONDS < deadline )); then
      sleep "$interval_seconds"
    fi
  done

  "$(python_bin)" -c '
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception:
    payload = {"ok": False, "reason": "invalid_collect_payload"}
payload["stability"] = {
    "stable": False,
    "required_stable_snapshots": 2,
    "attempts": int(sys.argv[2]),
}
print(json.dumps(payload, ensure_ascii=False))
' "$last_result" "$attempt"
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
  if [[ -n "$TEST_PROMPT" ]]; then
    local smoke_path="$review_dir/chatgpt_smoke_${date_text}.json"
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
raw_path.write_text(raw_response + ("\n" if raw_response else ""), encoding="utf-8")

status = {
    "ok": False,
    "raw_path": str(raw_path),
    "response_path": str(response_path),
    "reason": "raw_saved_pending_normalize",
    "assistant_count": payload.get("assistant_count"),
    "correlation": payload.get("correlation"),
    "raw_chars": len(raw_response),
}
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(status, ensure_ascii=False))
PY

  if ! "$(python_bin)" - "$status_path" "$raw_path" <<'PY'
import json
import sys
from pathlib import Path

status_path = Path(sys.argv[1])
raw_path = Path(sys.argv[2])
status = json.loads(status_path.read_text(encoding="utf-8"))
raw = raw_path.read_text(encoding="utf-8").strip()
is_smoke = "top10-browser" in raw or "top10-chatgpt-script-click" in raw
if len(raw) >= 500 and not is_smoke:
    raise SystemExit(0)
status["ok"] = False
status["reason"] = "formal_raw_too_short_or_smoke"
status["min_raw_chars"] = 500
status["smoke_marker_detected"] = is_smoke
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
raise SystemExit(1)
PY
  then
    printf 'raw=%s\nresponse=%s\nstatus=%s\n' "$raw_path" "$response_path" "$status_path"
    return 1
  fi

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
    write_collect_js "$date_text"
    collect_result="$(collect_stable_result)"
    collect_path="$(write_evidence collect "$collect_result")"
    printf '%s\n' "$collect_result"
    printf 'collect_evidence=%s\n' "$collect_path"
    store_chatgpt_response "$date_text" "$collect_result"
    ;;
  collect)
    date_text="$(infer_date)"
    verify_sendable_packet
    init_js_file
    write_collect_js "$date_text"
    collect_result="$(collect_stable_result)"
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

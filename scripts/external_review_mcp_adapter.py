#!/usr/bin/env python3
"""原 review CLI 的薄契約入口；瀏覽器操作只交標準 MCP SDK。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from external_review_provider_contract import MIN_RAW_CHARS, has_smoke_marker

ROOT = Path(__file__).resolve().parents[1]
URLS = {
    "chatgpt": "https://chatgpt.com/g/g-p-6a27bb719e708191bd6eefae64c7c08c-gu-piao/c/6a27bb97-8f80-8324-ab52-3f861a006ee3",
    "gemini": "https://gemini.google.com/app/ea58b54eef550ded",
}


def build_prompt(contract: str, packet_bytes: bytes, provider: str, marker: str) -> str:
    """沿 W 原 read_prompt 的格式；正文只來自既有契約與公開 packet。"""
    packet = json.loads(packet_bytes)
    match = re.search(r"## Reviewer Prompt\b.*?```text\s+(.*?)\s+```", contract, flags=re.S)
    if not match:
        raise ValueError("Reviewer Prompt block missing")
    sendable = {key: packet.get(key) for key in
                ("packet_date", "market", "market_overview", "outcome_status", "recommendations")}
    return "\n".join([
        match.group(1).strip(),
        "packet_sha256=" + hashlib.sha256(packet_bytes).hexdigest(),
        "request_marker=" + marker, "",
        f"review_date={packet['packet_date']}, provider={provider}, market=TW。",
        "請用專業台股操盤手角度檢視：整體評分/信心、選股品質、主要優點、主要風險、可能誤判、強弱族群、隔日觀察重點、可回測研究假設。",
        "請嚴格依上列契約回覆單一完整 JSON object；欄位名稱不可改寫，資料不足時不可猜測或以自由文字替代。",
        "不要要求或推測內部演算法、權重、feature engineering、模型或未公開策略參數。", "",
        "以下是已通過本地安全驗證的 review_packet 摘要，內容只取自 verified packet：",
        json.dumps(sendable, ensure_ascii=False, separators=(",", ":")), "",
    ])


def canonical_root(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute() or raw == "/" or str(path.resolve()) != raw or not path.is_dir():
        raise ValueError("existing canonical TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT required")
    return path


def checked_script(name: str, *args: str) -> None:
    result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / name), *args],
                            text=True, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(name + ": " + (result.stdout + result.stderr)[-1500:])


def runtime_paths(output: Path) -> dict[str, str]:
    """只核既有外接路徑契約；不判親權、容量 admission、profile 或 GO。"""
    if os.environ.get("AI_CORE_CACHE_MODE") != "directory":
        raise ValueError("existing directory cache contract required")
    volume = canonical_root(os.environ.get("AI_CORE_CACHE_VOLUME", ""))
    if not str(volume).startswith("/Volumes/") or not volume.is_mount():
        raise ValueError("external cache volume missing")
    device = volume.stat().st_dev

    def external(raw: str) -> Path:
        path = canonical_root(raw)
        if not path.is_relative_to(volume) or path == volume or path.stat().st_dev != device:
            raise ValueError("output/tmp/cache must stay on existing external volume")
        return path

    external(str(output))
    cache = external(os.environ.get("AI_CORE_CACHE_ROOT", ""))
    if not re.fullmatch(r"[a-fA-F0-9-]{36}", os.environ.get("AI_CORE_CACHE_VOLUME_UUID", "")):
        raise ValueError("external cache UUID contract missing")
    for key in ("AI_CORE_CACHE_MAX_BYTES", "AI_CORE_CACHE_MAX_FILES", "AI_CORE_CACHE_RESERVED_OTHER_BYTES"):
        value = int(os.environ.get(key, "-1"))
        if value < (0 if key.endswith("RESERVED_OTHER_BYTES") else 1):
            raise ValueError(key + " contract missing")
    for key in ("TMPDIR", "TMP", "TEMP", "TEMPDIR", "XDG_CACHE_HOME"):
        external(os.environ.get(key, ""))
    for key in ("NODE_COMPILE_CACHE", "AI_CORE_CACHE_DIR", "UV_CACHE_DIR", "PNPM_STORE_DIR", "PNPM_CACHE_DIR"):
        if os.environ.get(key):
            external(os.environ[key])
    downloads = external(os.environ.get("AI_CORE_DOWNLOADS_DIR", str(cache / "downloads")))
    if not downloads.is_relative_to(cache):
        raise ValueError("downloads must stay under existing cache root")
    package = external(os.environ.get("TOP10_REVIEW_MCP_PACKAGE_ROOT", str(
        downloads / "chrome-devtools-mcp-1.13.0/node_modules/chrome-devtools-mcp")))
    if not package.is_relative_to(downloads):
        raise ValueError("MCP package must reuse existing external downloads")
    sdk_raw = os.environ.get("TOP10_REVIEW_MCP_SDK_ROOT", "")
    if not Path(sdk_raw).is_absolute():
        raise ValueError("TOP10_REVIEW_MCP_SDK_ROOT must locate existing standard SDK")
    sdk = Path(sdk_raw).resolve(strict=True)
    if not sdk.is_dir():
        raise ValueError("existing MCP SDK directory required")
    node_raw = os.environ.get("TOP10_REVIEW_MCP_NODE") or os.environ.get("NODE_BIN", "")
    if not Path(node_raw).is_absolute():
        raise ValueError("existing TOP10_REVIEW_MCP_NODE or toolchain NODE_BIN required")
    node = Path(node_raw).resolve(strict=True)
    if not node.is_file() or not os.access(node, os.X_OK):
        raise ValueError("existing executable Node required")
    core = Path(os.environ.get("AI_CORE_DIR", ""))
    if not core.is_absolute():
        raise ValueError("existing AI_CORE_DIR required")
    config = core / "config/mcp_servers.shared.json"
    if not config.is_file():
        raise ValueError("original shared MCP config missing")
    return {"node": str(node), "packageRoot": str(package), "sdkRoot": str(sdk), "configPath": str(config)}


def account_guards(provider: str) -> dict[str, str]:
    """兩方都須由 operator 明示帳號；probe 與送收共用相同身分契約。"""
    prefix = "TOP10_" + provider.upper() + "_EXPECTED_"
    guards = {key: os.environ.get(prefix + key.upper(), "") for key in ("title", "account", "plan")}
    if not guards["account"].strip():
        raise ValueError(prefix + "ACCOUNT required")
    return guards


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("probe", "send", "collect"))
    parser.add_argument("--provider", required=True, choices=URLS)
    parser.add_argument("--date")
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--packet-sha256", default=os.environ.get("TOP10_EXTERNAL_REVIEW_PACKET_SHA256", ""))
    parser.add_argument("--ws-endpoint", default=os.environ.get("TOP10_REVIEW_WS_ENDPOINT", ""))
    parser.add_argument("--print-probe-config", action="store_true")
    args = parser.parse_args()
    mode = args.mode or ("send" if args.packet else "probe")
    provider = args.provider
    guards = account_guards(provider)
    prefix = "TOP10_" + provider.upper()
    url = os.environ.get(prefix + "_URL_PART", URLS[provider])
    if not url.startswith("https://"):
        url = "https://" + url
    expected = (r"https://chatgpt\.com/(?:g/[^/]+/)?c/[^/?#]+" if provider == "chatgpt"
                else r"https://gemini\.google\.com/app/[^/?#]+")
    if not re.fullmatch(expected, url):
        raise ValueError("exact canonical conversation URL required")
    out = canonical_root(os.environ.get("TOP10_EXTERNAL_REVIEW_OUTPUT_ROOT", ""))
    if args.print_probe_config:
        print(json.dumps({"mode": "probe_only", "review_packet_sent": False,
                          "output_root": str(out), "target_url_part": url}))
        return 0
    if os.environ.get(prefix + "_TEST_PROMPT"):
        raise ValueError("formal adapter does not accept smoke prompt override")
    request = {"mode": mode, "provider": provider, "url": url, "outputRoot": str(out)}
    if mode != "probe" or args.packet:
        if not args.packet:
            raise ValueError("send/collect requires --packet")
        packet_bytes = args.packet.read_bytes()
        if args.packet_sha256 and hashlib.sha256(packet_bytes).hexdigest() != args.packet_sha256:
            raise ValueError("pinned packet bytes mismatch")
        packet = json.loads(packet_bytes)
        date = args.date or packet.get("packet_date")
        if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or date != packet.get("packet_date"):
            raise ValueError("packet_date mismatch")
        checked_script("verify_external_review_packet.py", "--packet", str(args.packet))
        if args.packet.read_bytes() != packet_bytes:
            raise ValueError("packet changed during verification")
        # collect 沿既有 fill 證據的 marker；send 的新 marker 由 SDK adapter 保留後插入。
        contract = (ROOT / "docs/architecture/EXTERNAL_REVIEW_CONTRACT.md").read_text()
        request.update(review_date=date, packet_sha256=hashlib.sha256(packet_bytes).hexdigest(),
                       promptTemplate=build_prompt(contract, packet_bytes, provider, "__REQUEST_MARKER__"),
                       minChars=max(MIN_RAW_CHARS, int(os.environ.get(prefix + "_COLLECT_MIN_CHARS", MIN_RAW_CHARS))))
    request.update(timeoutSeconds=int(os.environ.get(prefix + "_COLLECT_STABLE_TIMEOUT", "150")),
                   intervalSeconds=int(os.environ.get(prefix + "_COLLECT_STABLE_INTERVAL", "5")),
                   waitSeconds=int(os.environ.get("TOP10_REVIEW_WAIT_SECONDS", "45")),
                   guards=guards)
    runtime = runtime_paths(out)
    request.update(runtime=runtime, wsEndpoint=args.ws_endpoint)
    node = runtime["node"]
    result = subprocess.run([node, str(ROOT / "scripts/external_review_mcp_adapter.mjs")],
                            input=json.dumps(request, ensure_ascii=False), text=True,
                            capture_output=True, check=False)
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        raise ValueError("native MCP adapter failed without valid receipt") from None
    print(json.dumps(payload, ensure_ascii=False))
    if result.returncode or payload.get("ok") is not True or mode == "probe":
        return 0 if result.returncode == 0 and payload.get("ok") is True else 1
    review_dir = out / request["review_date"]
    raw_path = review_dir / f"{provider}_raw_{request['review_date']}.txt"
    response = review_dir / f"{provider}_response_{request['review_date']}.json"
    status_path = review_dir / f"{provider}_collect_status_{request['review_date']}.json"
    status = json.loads(status_path.read_text())
    try:
        raw = raw_path.read_text().strip()
        if len(raw) < request["minChars"] or has_smoke_marker(raw):
            raise ValueError("formal_raw_too_short_or_smoke")
        if args.packet.read_bytes() != packet_bytes:
            raise ValueError("packet changed after submit; collect evidence retained")
        checked_script("normalize_external_review_response.py", "--provider", provider, "--date", request["review_date"],
                       "--raw", str(raw_path), "--packet", str(args.packet), "--out", str(response))
        checked_script("verify_external_review_contract.py", str(response))
        status.update(ok=True, reason="normalized_contract_ok")
    except ValueError as exc:
        status.update(ok=False, reason=str(exc))
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
    print("status=" + str(status_path))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, IndexError) as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)

"""UI-MFR-01 CDP acceptance probe; listeners are installed before navigation."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from urllib.request import urlopen

from websockets.asyncio.client import connect


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "evidence" / "REPAIR-UI-MFR-01-01" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)


async def main() -> None:
    with urlopen(__import__("urllib.request").request.Request("http://127.0.0.1:9222/json/new?http://127.0.0.1:5173/", method="PUT"), timeout=5) as response:
        target = json.load(response)
    events: list[dict] = []
    request_urls: dict[str, str] = {}
    async with connect(target["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
        counter = 0
        pending: dict[int, asyncio.Future] = {}

        async def receiver() -> None:
            async for raw in ws:
                message = json.loads(raw)
                if "id" in message and message["id"] in pending:
                    pending.pop(message["id"]).set_result(message)
                    continue
                method = message.get("method", "")
                params = message.get("params", {})
                if method in {"Runtime.consoleAPICalled", "Runtime.exceptionThrown", "Network.requestWillBeSent", "Network.loadingFailed", "Network.responseReceived"}:
                    if method == "Network.requestWillBeSent":
                        request_urls[params["requestId"]] = params["request"]["url"]
                    if method == "Network.responseReceived" and params["response"]["status"] >= 400:
                        events.append({"kind": "http", "status": params["response"]["status"], "url": params["response"]["url"]})
                    elif method == "Network.loadingFailed":
                        events.append({"kind": "requestfailed", "error": params.get("errorText"), "url": request_urls.get(params["requestId"], "")})
                    elif method == "Runtime.consoleAPICalled":
                        events.append({"kind": "console", "level": params["type"], "args": [x.get("value", x.get("description")) for x in params.get("args", [])]})
                    elif method == "Runtime.exceptionThrown":
                        details = params["exceptionDetails"]
                        events.append({"kind": "pageerror", "text": details.get("text"), "description": (details.get("exception") or {}).get("description")})

        receiver_task = asyncio.create_task(receiver())

        async def call(method: str, params: dict | None = None) -> dict:
            nonlocal counter
            counter += 1
            future = asyncio.get_running_loop().create_future()
            pending[counter] = future
            await ws.send(json.dumps({"id": counter, "method": method, "params": params or {}}))
            return await asyncio.wait_for(future, 15)

        # Evidence hooks are enabled before Page.navigate.
        await call("Runtime.enable")
        await call("Page.enable")
        await call("Network.enable")
        await call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__mfrTrace = 'listeners-before-navigation'"})
        await call("Page.navigate", {"url": "http://127.0.0.1:5173/"})
        await asyncio.sleep(2)

        async def evaluate(expression: str) -> object:
            result = await call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
            return result.get("result", {}).get("result", {}).get("value")

        async def screenshot(name: str) -> None:
            result = await call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            (OUT / name).write_bytes(base64.b64decode(result["result"]["data"]))

        await screenshot("desktop-weekly.png")
        # Keyboard activation: focus the radar tab and dispatch Enter.
        await evaluate("[...document.querySelectorAll('button[aria-pressed]')].find((button) => button.textContent?.includes('市場雷達'))?.focus()")
        print(json.dumps({"focused_before_enter": await evaluate("document.activeElement?.textContent?.trim()")}, ensure_ascii=False))
        await call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "nativeVirtualKeyCode": 36, "text": "\r", "unmodifiedText": "\r"})
        await call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
        await asyncio.sleep(2)
        print(json.dumps({"keyboard_active_view": await evaluate("document.querySelector('.desk-tab--active')?.textContent?.trim()"), "radar_title": await evaluate("document.querySelector('#market-flow-title')?.textContent?.trim()")}, ensure_ascii=False))
        await screenshot("desktop-radar-live.png")
        for value, filename in [("loading", "desktop-loading.png"), ("empty", "desktop-empty.png"), ("error", "desktop-error.png"), ("stale", "desktop-stale.png"), ("partial", "desktop-partial.png")]:
            await evaluate(f"document.querySelector('select[aria-label=\"雷達狀態預覽\"]').value='{value}'; document.querySelector('select[aria-label=\"雷達狀態預覽\"]').dispatchEvent(new Event('change', {{bubbles:true}}))")
            await asyncio.sleep(0.15)
            await screenshot(filename)

        await call("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
        await asyncio.sleep(0.3)
        await evaluate("document.querySelector('select[aria-label=\"雷達狀態預覽\"]').value='live'; document.querySelector('select[aria-label=\"雷達狀態預覽\"]').dispatchEvent(new Event('change', {bubbles:true}))")
        await asyncio.sleep(0.2)
        await screenshot("mobile-radar-live.png")
        metrics = await evaluate("({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,viewport:document.documentElement.clientWidth,overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth})")
        print(json.dumps({"mobile_metrics": metrics, "events": events}, ensure_ascii=False))
        receiver_task.cancel()
        try:
            await receiver_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())

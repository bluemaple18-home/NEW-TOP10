"""Research Fog Map 的純 HTML renderer。"""

from __future__ import annotations

import html
import json
from typing import Any


def render_metric_card(label: str, key: str, suffix: str = "") -> str:
    return f"""
          <article class="metric-card">
            <span>{html.escape(label)}</span>
            <strong data-summary="{html.escape(key)}">0{html.escape(suffix)}</strong>
          </article>"""


def render_html(payload: dict[str, Any]) -> str:
    payload_json = (
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    fixture_banner = (
        '<div class="fixture-banner">範例模式：找不到來源研究 artifact，目前數字只供示意。</div>'
        if payload.get("fixture")
        else ""
    )
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>研究戰爭迷霧地圖</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #09111f;
      --panel: rgba(16, 27, 45, 0.86);
      --panel-strong: rgba(20, 35, 58, 0.96);
      --line: rgba(142, 176, 216, 0.22);
      --text: #e9f2ff;
      --muted: #8fa4be;
      --cyan: #5cc8ff;
      --red: #ff5f73;
      --yellow: #ffd166;
      --green: #73f7a4;
      --purple: #b28cff;
      --gold: #ffcc4d;
      --fog: #7c8797;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 28% 30%, rgba(92, 200, 255, 0.18), transparent 22%),
        radial-gradient(circle at 72% 18%, rgba(255, 209, 102, 0.11), transparent 20%),
        radial-gradient(circle at 78% 76%, rgba(178, 140, 255, 0.16), transparent 28%),
        linear-gradient(135deg, #050b15 0%, #091525 45%, #141827 100%);
      color: var(--text);
      letter-spacing: 0;
    }}
    .sr-only {{
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        radial-gradient(circle, rgba(255,255,255,0.7) 0 1px, transparent 1.2px),
        linear-gradient(rgba(92,200,255,0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(92,200,255,0.05) 1px, transparent 1px);
      background-size: 78px 78px, 64px 64px, 64px 64px;
      opacity: 0.34;
      mask-image: linear-gradient(to bottom, black, transparent 92%);
    }}
    .app-shell {{
      position: relative;
      width: min(1540px, calc(100vw - 28px));
      margin: 0 auto;
      padding: 22px 0 26px;
    }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: end;
      padding: 0 2px 16px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(28px, 4vw, 54px);
      line-height: 0.96;
      font-weight: 780;
      letter-spacing: 0;
    }}
    .subtitle {{
      margin: 10px 0 0;
      color: var(--muted);
      max-width: 780px;
      line-height: 1.55;
      font-size: 15px;
    }}
    .source-chip {{
      border: 1px solid var(--line);
      background: rgba(13, 23, 38, 0.78);
      padding: 10px 12px;
      border-radius: 8px;
      color: var(--muted);
      font-size: 12px;
      text-align: right;
      min-width: 220px;
    }}
    .source-chip strong {{
      display: block;
      color: var(--text);
      font-size: 14px;
      margin-top: 4px;
    }}
    .fixture-banner {{
      border: 1px solid rgba(255, 209, 102, 0.42);
      background: rgba(255, 209, 102, 0.12);
      color: #ffe3a3;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 14px;
      font-size: 13px;
    }}
    .dashboard-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 16px;
      align-items: start;
    }}
    .left-rail {{
      display: grid;
      gap: 14px;
    }}
    .hud {{
      border: 1px solid var(--line);
      background: linear-gradient(135deg, rgba(18, 32, 54, 0.92), rgba(8, 17, 31, 0.76));
      border-radius: 8px;
      padding: 14px;
      backdrop-filter: blur(14px);
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(6, minmax(118px, 1fr));
      gap: 10px;
    }}
    .metric-card {{
      min-height: 76px;
      border: 1px solid rgba(142,176,216,0.18);
      background: rgba(8, 17, 31, 0.62);
      border-radius: 8px;
      padding: 12px;
    }}
    .metric-card span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      line-height: 1.25;
    }}
    .metric-card strong {{
      display: block;
      margin-top: 8px;
      font-size: 24px;
      line-height: 1;
    }}
    .progress-wrap {{
      margin-top: 12px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
    }}
    .progress-track {{
      height: 14px;
      border-radius: 999px;
      background: rgba(124, 135, 151, 0.2);
      border: 1px solid rgba(142,176,216,0.2);
      overflow: hidden;
    }}
    .progress-fill {{
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--cyan), var(--green), var(--gold));
      box-shadow: 0 0 24px rgba(92, 200, 255, 0.5);
    }}
    .progress-label {{
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      font-size: 13px;
    }}
    .map-panel {{
      position: relative;
      min-height: 720px;
      border: 1px solid var(--line);
      background:
        radial-gradient(circle at 52% 50%, rgba(92, 200, 255, 0.16), transparent 16%),
        radial-gradient(circle at 73% 32%, rgba(255, 95, 115, 0.12), transparent 18%),
        radial-gradient(circle at 22% 68%, rgba(178, 140, 255, 0.1), transparent 20%),
        conic-gradient(from 210deg at 52% 51%, rgba(92,200,255,0.05), rgba(255,209,102,0.08), rgba(178,140,255,0.05), rgba(92,200,255,0.05)),
        rgba(8, 16, 30, 0.72);
      border-radius: 8px;
      overflow: hidden;
      cursor: grab;
      touch-action: none;
    }}
    .map-panel.is-dragging {{
      cursor: grabbing;
    }}
    .map-panel.is-point-hover {{
      cursor: pointer;
    }}
    .map-panel.is-point-hover .scenario-canvas {{
      cursor: pointer;
    }}
    .map-panel::before {{
      content: "";
      position: absolute;
      inset: 34px;
      border: 1px solid rgba(92, 200, 255, 0.12);
      border-radius: 50%;
      box-shadow:
        0 0 0 82px rgba(92, 200, 255, 0.025),
        0 0 0 164px rgba(178, 140, 255, 0.018),
        inset 0 0 80px rgba(92, 200, 255, 0.05);
      pointer-events: none;
    }}
    .map-panel::after {{
      content: "";
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(92, 200, 255, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(92, 200, 255, 0.035) 1px, transparent 1px);
      background-size: 88px 88px;
      mask-image: radial-gradient(circle at 52% 50%, black 0 58%, transparent 88%);
      pointer-events: none;
    }}
    .family-bands {{
      position: absolute;
      inset: 0;
      display: block;
      pointer-events: none;
      z-index: 2;
      transform-origin: center;
      transform: translateZ(0);
      transition: none;
      will-change: transform;
    }}
    .family-darkmatter {{
      position: absolute;
      transform: translate(-50%, -50%);
      width: var(--halo-w, 180px);
      height: var(--halo-h, 120px);
      border-radius: 50%;
      border: 1px dashed rgba(124, 135, 151, 0.34);
      background: radial-gradient(circle, rgba(124,135,151,0.12), rgba(92,200,255,0.035) 54%, transparent 72%);
      box-shadow: inset 0 0 54px rgba(124,135,151,0.08), 0 0 46px rgba(31,149,226,0.06);
      opacity: 0.82;
    }}
    .map-panel.is-dragging .family-bands,
    .map-panel.is-dragging .starmap {{
      transition: none;
    }}
    .family-band {{
      position: absolute;
      transform: translate(-50%, -50%);
      border: 1px solid rgba(142,176,216,0.16);
      background: rgba(8,17,31,0.62);
      border-radius: 8px;
      padding: 7px 9px;
      color: rgba(233,242,255,0.7);
      font-size: 10px;
      text-transform: uppercase;
      line-height: 1.25;
      white-space: nowrap;
      box-shadow: 0 0 22px rgba(92,200,255,0.07);
    }}
    .starmap {{
      position: absolute;
      inset: 0;
      z-index: 3;
      transform-origin: center;
      transform: translateZ(0);
      transition: none;
      will-change: transform;
      contain: layout paint style;
    }}
    .scenario-canvas {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      z-index: 3;
      pointer-events: auto;
    }}
    .universe-fog-canvas {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      z-index: 1;
      pointer-events: none;
      mix-blend-mode: screen;
      opacity: 1;
      filter: saturate(1.18) contrast(1.08);
    }}
    .star-links {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      overflow: visible;
      pointer-events: none;
      z-index: 4;
    }}
    .star-link {{
      stroke: rgba(92, 200, 255, 0.2);
      stroke-width: 0.34;
      vector-effect: non-scaling-stroke;
    }}
    .star-link.is-hot {{
      stroke: rgba(255, 209, 102, 0.48);
      stroke-width: 0.78;
    }}
    .map-core {{
      position: absolute;
      left: 52%;
      top: 51%;
      transform: translate(-50%, -50%);
      width: 132px;
      height: 132px;
      border-radius: 50%;
      border: 1px solid rgba(92, 200, 255, 0.28);
      background:
        radial-gradient(circle, rgba(92, 200, 255, 0.22), transparent 38%),
        rgba(8, 17, 31, 0.32);
      box-shadow: 0 0 42px rgba(92, 200, 255, 0.18), inset 0 0 28px rgba(255, 209, 102, 0.06);
      pointer-events: none;
      z-index: 5;
    }}
    .map-core span {{
      position: absolute;
      inset: 38px 18px auto;
      color: rgba(233,242,255,0.76);
      font-size: 10px;
      text-align: center;
      text-transform: uppercase;
      line-height: 1.25;
    }}
    .node {{
      --node-color: var(--fog);
      position: absolute;
      width: 14px;
      height: 14px;
      transform: translate(-50%, -50%);
      border: 0;
      border-radius: 50%;
      background: var(--node-color);
      box-shadow: 0 0 16px color-mix(in srgb, var(--node-color), transparent 25%);
      cursor: pointer;
      transition: transform 140ms ease, box-shadow 140ms ease, outline-color 140ms ease;
      z-index: 4;
    }}
    .node::after {{
      content: "";
      position: absolute;
      inset: -6px;
      border-radius: 50%;
      border: 1px solid color-mix(in srgb, var(--node-color), transparent 48%);
      opacity: 0.7;
      pointer-events: none;
    }}
    .node:hover,
    .node.is-selected {{
      transform: translate(-50%, -50%) scale(1.18);
      outline: 2px solid rgba(255,255,255,0.72);
      outline-offset: 6px;
      z-index: 7;
    }}
    .node[data-color="fog_gray"] {{ --node-color: #8fa0b6; opacity: calc(var(--o, 0.44) * 0.46); }}
    .node[data-color="blue"] {{ --node-color: #67d4ff; opacity: calc(var(--o, 0.44) * 0.66); }}
    .node[data-color="red"] {{ --node-color: #ff6e82; opacity: calc(var(--o, 0.44) * 0.58); }}
    .node[data-color="yellow"] {{ --node-color: #ffd66e; opacity: calc(var(--o, 0.44) * 0.68); }}
    .node[data-color="green"] {{ --node-color: var(--green); opacity: calc(var(--o, 0.44) * 0.66); }}
    .node[data-color="purple"] {{ --node-color: var(--purple); opacity: calc(var(--o, 0.44) * 0.66); }}
    .node[data-color="gold"] {{ --node-color: #ffd15c; opacity: calc(var(--o, 0.44) * 0.72); }}
    .map-footer {{
      position: absolute;
      left: 14px;
      right: 14px;
      bottom: 12px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: end;
      color: var(--muted);
      font-size: 12px;
      pointer-events: none;
      z-index: 5;
    }}
    .family-summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }}
    .family-pill {{
      border: 1px solid rgba(142,176,216,0.16);
      background: rgba(8,17,31,0.72);
      border-radius: 8px;
      padding: 8px;
      min-height: 48px;
    }}
    .family-pill strong {{
      display: block;
      color: var(--text);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    aside {{
      display: grid;
      gap: 14px;
    }}
    .panel {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 14px;
      backdrop-filter: blur(14px);
    }}
    .panel h2 {{
      margin: 0 0 12px;
      font-size: 15px;
      letter-spacing: 0;
    }}
    .inspector-title {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: start;
    }}
    .status-dot {{
      display: inline-flex;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--fog);
      box-shadow: 0 0 14px currentColor;
      flex: 0 0 auto;
      margin-top: 3px;
    }}
    .kv {{
      display: grid;
      grid-template-columns: 118px minmax(0, 1fr);
      gap: 8px;
      padding: 7px 0;
      border-bottom: 1px solid rgba(142,176,216,0.12);
      font-size: 12px;
      line-height: 1.35;
    }}
    .kv span:first-child {{
      color: var(--muted);
    }}
    .kv span:last-child {{
      overflow-wrap: anywhere;
    }}
    .mission-list {{
      display: grid;
      gap: 8px;
      max-height: 390px;
      overflow: auto;
      padding-right: 3px;
    }}
    .mission {{
      border: 1px solid rgba(142,176,216,0.16);
      background: rgba(8,17,31,0.58);
      border-radius: 8px;
      padding: 10px;
      cursor: pointer;
      text-align: left;
    }}
    .mission strong {{
      display: block;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .mission small {{
      display: block;
      color: var(--muted);
      margin-top: 5px;
      line-height: 1.35;
    }}
    .legend-grid {{
      display: grid;
      gap: 7px;
    }}
    .legend-item {{
      display: grid;
      grid-template-columns: 16px minmax(0, 1fr);
      gap: 8px;
      align-items: start;
      font-size: 12px;
      color: var(--muted);
    }}
    .legend-swatch {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
      margin-top: 2px;
      background: var(--fog);
      box-shadow: 0 0 12px currentColor;
    }}
    .legend-item strong {{
      color: var(--text);
      display: block;
      margin-bottom: 2px;
    }}
    @media (max-width: 1180px) {{
      .dashboard-grid {{ grid-template-columns: 1fr; }}
      aside {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .metrics {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}
    @media (max-width: 760px) {{
      .app-shell {{ width: min(100vw - 18px, 760px); padding-top: 14px; }}
      header {{ grid-template-columns: 1fr; }}
      .source-chip {{ text-align: left; min-width: 0; }}
      .metrics {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .map-panel {{ min-height: 560px; }}
      .family-band {{ font-size: 8px; padding: 5px 6px; max-width: 88px; white-space: normal; text-align: center; }}
      .map-core {{ width: 92px; height: 92px; }}
      .map-core span {{ inset: 28px 10px auto; font-size: 8px; }}
      .map-footer {{ grid-template-columns: 1fr; }}
      .family-summary {{ display: none; }}
      aside {{ grid-template-columns: 1fr; }}
      .kv {{ grid-template-columns: 96px minmax(0, 1fr); }}
    }}
    .command-shell {{
      width: min(1920px, calc(100vw - 18px));
      min-height: 100vh;
      margin: 0 auto;
      padding: 10px;
      display: grid;
      grid-template-rows: 112px minmax(590px, 1fr) 232px;
      gap: 10px;
    }}
    .command-top {{
      display: grid;
      grid-template-columns: 330px repeat(5, minmax(170px, 1fr)) 150px;
      grid-auto-rows: minmax(92px, auto);
      gap: 12px;
    }}
    .command-card {{
      position: relative;
      border: 1px solid rgba(31, 149, 226, 0.48);
      background: linear-gradient(135deg, rgba(7, 20, 34, 0.96), rgba(2, 8, 16, 0.92));
      box-shadow: inset 0 0 0 1px rgba(88, 198, 255, 0.06), 0 0 22px rgba(0, 146, 255, 0.08);
      border-radius: 4px;
      padding: 12px 14px;
      overflow: hidden;
      min-width: 0;
      isolation: isolate;
      transition: border-color 160ms ease, box-shadow 220ms ease, transform 180ms ease, background 220ms ease;
    }}
    .command-card::before,
    .command-card::after {{
      content: "";
      position: absolute;
      width: 18px;
      height: 18px;
      border-color: #25b7ff;
      opacity: 0.82;
    }}
    .command-card::before {{
      left: -1px;
      top: -1px;
      border-left: 2px solid;
      border-top: 2px solid;
    }}
    .command-card::after {{
      right: -1px;
      bottom: -1px;
      border-right: 2px solid;
      border-bottom: 2px solid;
    }}
    .command-card:hover {{
      border-color: rgba(104, 216, 255, 0.72);
      box-shadow: inset 0 0 0 1px rgba(126, 220, 255, 0.12), 0 0 28px rgba(0, 146, 255, 0.16);
      transform: translateY(-1px);
    }}
    .brand-card {{
      display: grid;
      grid-template-columns: 78px minmax(0, 1fr);
      align-items: center;
      gap: 18px;
    }}
    .brand-mark {{
      width: 64px;
      height: 64px;
      border: 2px solid rgba(120, 221, 255, 0.8);
      clip-path: polygon(50% 0, 94% 24%, 94% 76%, 50% 100%, 6% 76%, 6% 24%);
      display: grid;
      place-items: center;
      color: #9beaff;
      font-weight: 900;
      font-size: 24px;
      text-shadow: 0 0 18px rgba(92, 200, 255, 0.8);
      background: radial-gradient(circle, rgba(92, 200, 255, 0.18), transparent 70%);
    }}
    .brand-title {{
      margin: 0;
      font-size: 22px;
      line-height: 1.05;
      text-transform: uppercase;
      color: #bdeaff;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }}
    .brand-subtitle {{
      margin-top: 8px;
      color: #34caff;
      font-size: 15px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .kpi-card span,
    .system-card span {{
      display: block;
      color: #9dc9e6;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .kpi-main {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-top: 8px;
      min-width: 0;
    }}
    .kpi-main strong {{
      min-width: 0;
      font-size: clamp(22px, 1.55vw, 27px);
      line-height: 1;
      color: #a8e2ff;
      font-variant-numeric: tabular-nums;
      overflow-wrap: anywhere;
    }}
    .kpi-main em {{
      font-style: normal;
      font-size: 14px;
      color: #23c0ff;
    }}
    .kpi-note {{
      margin-top: 6px;
      color: #9dc9e6;
      font-size: 12px;
      font-variant-numeric: tabular-nums;
      line-height: 1.25;
      white-space: normal;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .burndown-line {{
      margin-top: 6px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 4px;
      font-size: 11px;
      color: #9dc9e6;
    }}
    .burndown-line b {{
      display: block;
      color: #a8e2ff;
      font-size: 12px;
      font-weight: 700;
      font-variant-numeric: tabular-nums;
    }}
    .seg-bar {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 3px;
      margin-top: 10px;
    }}
    .seg-bar i {{
      display: block;
      height: 8px;
      border: 1px solid rgba(71, 174, 255, 0.45);
      background: rgba(20, 54, 86, 0.55);
      border-radius: 2px;
    }}
    .seg-bar i.is-lit {{ background: linear-gradient(90deg, #2ed5ff, #2c78ff); }}
    .seg-bar.is-purple i.is-lit {{ background: linear-gradient(90deg, #b068ff, #7b45ff); }}
    .followup-line {{
      margin-top: 10px;
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      color: #9dc9e6;
      font-size: 14px;
    }}
    .followup-line strong {{ color: #4df58f; }}
    .system-card strong {{
      display: block;
      margin-top: 7px;
      color: #55f69a;
      font-size: 15px;
      text-transform: uppercase;
    }}
    .status-strip {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 9px;
      color: #8fb7d1;
      font-size: 11px;
    }}
    .status-strip b {{
      display: block;
      color: #c7edff;
      font-size: 13px;
      font-variant-numeric: tabular-nums;
    }}
    @keyframes softReveal {{
      from {{ opacity: 0; transform: translateY(5px); filter: blur(2px); }}
      to {{ opacity: 1; transform: translateY(0); filter: blur(0); }}
    }}
    @keyframes railSweep {{
      0% {{ transform: translateX(-120%); opacity: 0; }}
      35% {{ opacity: 0.55; }}
      100% {{ transform: translateX(120%); opacity: 0; }}
    }}
    @keyframes starPulse {{
      0%, 100% {{ filter: drop-shadow(0 0 2px rgba(122, 224, 255, 0.35)); }}
      50% {{ filter: drop-shadow(0 0 10px rgba(122, 224, 255, 0.72)); }}
    }}
    .command-card {{
      animation: softReveal 420ms ease both;
    }}
    .command-card:nth-child(2) {{ animation-delay: 40ms; }}
    .command-card:nth-child(3) {{ animation-delay: 80ms; }}
    .command-card:nth-child(4) {{ animation-delay: 120ms; }}
    .command-card:nth-child(5) {{ animation-delay: 160ms; }}
    .command-card:nth-child(6) {{ animation-delay: 200ms; }}
    .seg-bar {{
      position: relative;
      overflow: hidden;
    }}
    .seg-bar::after {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(90deg, transparent, rgba(153, 229, 255, 0.34), transparent);
      transform: translateX(-120%);
      animation: railSweep 3.8s ease-in-out infinite;
      pointer-events: none;
    }}
    .command-main {{
      display: grid;
      grid-template-columns: 205px minmax(660px, 1fr) 480px;
      gap: 10px;
      min-height: 0;
    }}
    .command-sidebar {{
      display: grid;
      grid-template-rows: auto auto auto;
      align-content: start;
      gap: 10px;
      min-height: 0;
    }}
    .nav-panel,
    .control-panel,
    .bottom-panel,
    .command-inspector {{
      border: 1px solid rgba(31, 149, 226, 0.42);
      background: rgba(4, 14, 26, 0.86);
      border-radius: 4px;
      box-shadow: inset 0 0 22px rgba(0, 136, 255, 0.04);
    }}
    .nav-list {{
      display: grid;
      gap: 6px;
      padding: 12px 10px;
    }}
    .nav-item {{
      display: flex;
      align-items: center;
      gap: 12px;
      min-height: 44px;
      padding: 0 12px;
      border: 1px solid transparent;
      color: #8aa5bc;
      text-transform: uppercase;
      font-size: 14px;
      cursor: pointer;
    }}
    .nav-item.is-active {{
      color: #c8f0ff;
      border-color: rgba(31, 149, 226, 0.54);
      background: linear-gradient(90deg, rgba(0, 132, 255, 0.42), rgba(0, 132, 255, 0.03));
      box-shadow: inset 3px 0 0 #2dc8ff;
    }}
    .nav-icon {{
      width: 22px;
      height: 22px;
      display: grid;
      place-items: center;
      color: #74d9ff;
      font-size: 17px;
    }}
    .panel-title {{
      margin: 0;
      padding: 12px 14px 8px;
      color: #8fd9ff;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.7px;
    }}
    .legend-compact {{
      padding: 4px 14px 12px;
      display: grid;
      gap: 7px;
    }}
    .legend-compact .legend-item {{
      grid-template-columns: 16px minmax(0, 1fr) auto;
      color: #b4c6d8;
      align-items: center;
      font-size: 12px;
      cursor: pointer;
    }}
    .legend-compact .legend-item strong {{
      display: inline;
      margin: 0;
    }}
    .legend-count {{
      color: #7fe7ff;
      font-variant-numeric: tabular-nums;
    }}
    .legend-item.is-active .legend-swatch {{
      outline: 2px solid rgba(255,255,255,0.72);
      outline-offset: 3px;
    }}
    .map-controls {{
      padding: 8px 14px 14px;
      display: grid;
      gap: 10px;
    }}
    .control-row {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
    }}
    .control-btn {{
      height: 32px;
      border: 1px solid rgba(71, 174, 255, 0.38);
      background: rgba(4, 22, 38, 0.8);
      color: #8fd9ff;
      border-radius: 3px;
      font-size: 14px;
      cursor: pointer;
    }}
    .goto-sector {{
      height: 28px;
      border: 1px solid rgba(71, 174, 255, 0.28);
      background: rgba(4, 22, 38, 0.74);
      color: #6fbbe2;
      border-radius: 3px;
      text-align: center;
      font-size: 11px;
      text-transform: uppercase;
      cursor: pointer;
    }}
    .map-panel {{
      min-height: 100%;
      border-color: rgba(31, 149, 226, 0.45);
      background:
        radial-gradient(circle at 67% 22%, rgba(89, 115, 255, 0.28), transparent 22%),
        radial-gradient(circle at 42% 52%, rgba(92, 200, 255, 0.16), transparent 20%),
        radial-gradient(circle at 18% 72%, rgba(20, 70, 128, 0.22), transparent 22%),
        #030814;
    }}
    .map-panel::after {{
      background-image:
        radial-gradient(circle, rgba(180, 230, 255, 0.88) 0 1px, transparent 1.4px),
        radial-gradient(circle, rgba(62, 164, 255, 0.8) 0 1px, transparent 1.2px),
        linear-gradient(rgba(92, 200, 255, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(92, 200, 255, 0.035) 1px, transparent 1px);
      background-size: 86px 86px, 132px 132px, 110px 110px, 110px 110px;
      opacity: 0.7;
      mask-image: none;
    }}
    .map-panel::before {{
      inset: 22px;
      border-style: dashed;
      opacity: 0.8;
    }}
    .family-band {{
      border-style: dashed;
      background: rgba(3, 12, 24, 0.72);
      color: #9bdcff;
      min-width: 190px;
      font-size: 16px;
      text-align: center;
      text-shadow: 0 0 14px rgba(75, 184, 255, 0.7);
    }}
    .family-band small {{
      display: block;
      margin-top: 4px;
      color: #c8edff;
      font-size: 13px;
    }}
    .family-band em {{
      display: block;
      margin-top: 3px;
      color: #8fb0c7;
      font-size: 10px;
      font-style: normal;
      text-transform: none;
    }}
    .node {{
      width: var(--s, 1.8px);
      height: var(--s, 1.8px);
      opacity: var(--o, 0.44);
      background: color-mix(in srgb, var(--node-color), #d8f5ff 12%);
      box-shadow: 0 0 3px color-mix(in srgb, var(--node-color), transparent 54%);
      pointer-events: none;
    }}
    .node.is-filtered-out,
    .topic-hub.is-filtered-out {{
      opacity: 0.08;
    }}
    .node::after {{ display: none; }}
    .node:hover,
    .node.is-selected {{
      transform: translate(-50%, -50%) scale(1.8);
      outline: none;
      z-index: 5;
    }}
    .topic-hub {{
      --node-color: var(--fog);
      position: absolute;
      width: 13px;
      height: 13px;
      transform: translate(-50%, -50%);
      border: 1px solid color-mix(in srgb, var(--node-color), white 22%);
      border-radius: 50%;
      background: radial-gradient(circle, #ffffff 0 8%, var(--node-color) 9% 46%, transparent 48%);
      box-shadow: 0 0 16px color-mix(in srgb, var(--node-color), transparent 36%), inset 0 0 8px color-mix(in srgb, var(--node-color), transparent 48%);
      cursor: pointer;
      z-index: 7;
    }}
    .topic-hub::after {{
      content: "";
      position: absolute;
      inset: -8px;
      border-radius: 50%;
      border: 1px solid color-mix(in srgb, var(--node-color), transparent 68%);
      opacity: 0.68;
      pointer-events: none;
    }}
    .topic-hub.is-star {{
      width: 26px;
      height: 26px;
      clip-path: polygon(50% 0, 61% 35%, 98% 35%, 68% 56%, 79% 91%, 50% 68%, 21% 91%, 32% 56%, 2% 35%, 39% 35%);
      border-radius: 0;
      background: var(--node-color);
    }}
    .topic-hub.is-star::after {{ display: none; }}
    .topic-hub:hover,
    .topic-hub.is-selected {{
      transform: translate(-50%, -50%) scale(1.18);
      outline: 2px solid rgba(255,255,255,0.72);
      outline-offset: 6px;
      z-index: 9;
    }}
    .topic-hub[data-color="fog_gray"] {{ --node-color: var(--fog); opacity: 0.7; }}
    .topic-hub[data-color="blue"] {{ --node-color: var(--cyan); }}
    .topic-hub[data-color="red"] {{ --node-color: var(--red); }}
    .topic-hub[data-color="yellow"] {{ --node-color: var(--yellow); }}
    .topic-hub[data-color="green"] {{ --node-color: var(--green); }}
    .topic-hub[data-color="purple"] {{ --node-color: var(--purple); }}
    .topic-hub[data-color="gold"] {{ --node-color: var(--gold); }}
    .map-toolstrip {{
      position: absolute;
      left: 50%;
      bottom: 12px;
      transform: translateX(-50%);
      display: grid;
      grid-template-columns: repeat(5, 104px);
      border: 1px solid rgba(31, 149, 226, 0.44);
      background: rgba(3, 13, 25, 0.86);
      border-radius: 5px;
      overflow: hidden;
      z-index: 8;
    }}
    .map-toolstrip span {{
      min-height: 46px;
      display: grid;
      place-items: center;
      border-right: 1px solid rgba(31, 149, 226, 0.22);
      color: #8bdcff;
      font-size: 12px;
      text-transform: uppercase;
      cursor: pointer;
      user-select: none;
    }}
    .map-toolstrip span:last-child {{ border-right: 0; }}
    .map-toolstrip span.is-off {{
      color: #62778c;
      background: rgba(255,255,255,0.035);
    }}
    .map-layer-key {{
      position: absolute;
      left: 14px;
      top: 14px;
      z-index: 9;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      max-width: min(760px, calc(100% - 28px));
      color: #9dc9e6;
      font-size: 12px;
      pointer-events: none;
    }}
    .map-layer-key span {{
      border: 1px solid rgba(31, 149, 226, 0.32);
      background: rgba(3, 13, 25, 0.74);
      border-radius: 4px;
      padding: 6px 8px;
      box-shadow: 0 0 18px rgba(0, 146, 255, 0.06);
    }}
    .map-layer-key b {{
      color: #a8e2ff;
      margin-right: 5px;
    }}
    .map-layer-key i {{
      color: #d5f0ff;
      font-style: normal;
      font-variant-numeric: tabular-nums;
      margin-right: 5px;
    }}
    .map-panel.hide-links .star-links {{ display: none; }}
    .map-panel.hide-names .family-bands {{ display: none; }}
    .map-panel.hide-fog::before,
    .map-panel.hide-fog .universe-fog-canvas {{ display: none; }}
    .map-panel.hide-grid::after {{ opacity: 0.18; }}
    .command-shell.focus-map {{
      width: min(2040px, calc(100vw - 10px));
      grid-template-rows: 138px minmax(610px, calc(100vh - 368px)) 210px;
    }}
    .command-shell.focus-map .command-bottom {{
      display: grid;
      grid-template-columns: minmax(520px, 1.35fr) repeat(3, minmax(230px, 1fr));
      min-height: 0;
    }}
    .command-shell.focus-map .command-main {{
      grid-template-columns: 156px minmax(0, 1fr) 300px;
    }}
    .command-shell.focus-map .command-top {{
      grid-template-columns: 260px repeat(4, minmax(150px, 1fr)) 134px;
      grid-template-rows: 72px 54px;
      gap: 8px;
    }}
    .command-shell.focus-map .command-card {{
      padding: 9px 11px;
    }}
    .command-shell.focus-map .brand-card {{
      grid-column: 1;
      grid-row: 1 / 3;
      grid-template-columns: 48px minmax(0, 1fr);
      gap: 12px;
    }}
    .command-shell.focus-map .command-card:nth-child(2) {{ grid-column: 2; grid-row: 1; }}
    .command-shell.focus-map .command-card:nth-child(3) {{ grid-column: 3; grid-row: 1; }}
    .command-shell.focus-map .command-card:nth-child(4) {{ grid-column: 4 / 6; grid-row: 1; }}
    .command-shell.focus-map .command-card:nth-child(5) {{ grid-column: 2; grid-row: 2; }}
    .command-shell.focus-map .command-card:nth-child(6) {{ grid-column: 3; grid-row: 2; }}
    .command-shell.focus-map .command-card:nth-child(7) {{ grid-column: 4 / 6; grid-row: 2; }}
    .command-shell.focus-map .command-card:nth-child(8) {{ grid-column: 6; grid-row: 1 / 3; }}
    .command-shell.focus-map .brand-mark {{
      width: 44px;
      height: 44px;
      font-size: 17px;
    }}
    .command-shell.focus-map .brand-title {{
      font-size: 18px;
      line-height: 1.15;
    }}
    .command-shell.focus-map .brand-subtitle {{
      font-size: 12px;
      margin-top: 5px;
    }}
    .command-shell.focus-map .kpi-main strong {{
      font-size: clamp(18px, 1.18vw, 23px);
    }}
    .command-shell.focus-map .kpi-card span,
    .command-shell.focus-map .system-card span {{
      font-size: 11px;
    }}
    .command-shell.focus-map .kpi-note {{
      font-size: 11px;
      white-space: nowrap;
    }}
    .command-shell.focus-map .kpi-main {{
      margin-top: 5px;
      gap: 8px;
    }}
    .command-shell.focus-map .seg-bar {{
      margin-top: 7px;
    }}
    .command-shell.focus-map .seg-bar i {{
      height: 6px;
    }}
    .command-shell.focus-map .progress-label {{
      margin-top: 5px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .command-shell.focus-map .command-card:nth-child(2) .progress-label {{
      display: none;
    }}
    .command-shell.focus-map .command-card:nth-child(2) .seg-bar {{
      margin-top: 11px;
    }}
    .command-shell.focus-map .burndown-line {{
      grid-template-columns: repeat(4, minmax(0, 1fr));
      margin-top: 5px;
    }}
    .command-shell.focus-map .burndown-line b {{
      font-size: 11px;
    }}
    .command-shell.focus-map .command-card:nth-child(4) .kpi-note:last-child {{
      display: none;
    }}
    .command-shell.focus-map .followup-line {{
      margin-top: 6px;
      gap: 18px;
      font-size: 12px;
    }}
    .command-shell.focus-map .command-sidebar .nav-panel {{
      display: none;
    }}
    .command-shell.focus-map .command-sidebar {{
      grid-template-rows: auto;
    }}
    .command-shell.focus-map .scenario-map {{
      display: none;
    }}
    .command-shell.focus-map .delta-grid {{
      grid-template-columns: 1fr 1fr;
    }}
    .command-shell.focus-map .node-notes {{
      max-height: 190px;
      overflow: auto;
    }}
    .map-footer {{ bottom: 12px; left: auto; right: 14px; z-index: 9; }}
    .family-summary {{ display: none; }}
    .topic-hub.is-star {{
      animation: starPulse 2.8s ease-in-out infinite;
    }}
    .scenario-canvas,
    .universe-fog-canvas {{
      animation: softReveal 560ms ease both;
    }}
    @media (prefers-reduced-motion: reduce) {{
      .command-card,
      .topic-hub.is-star,
      .scenario-canvas,
      .universe-fog-canvas,
      .seg-bar::after {{
        animation: none !important;
        transition: none !important;
      }}
      .command-card:hover {{
        transform: none;
      }}
    }}
    .command-inspector {{
      padding: 0;
      display: grid;
      grid-template-rows: auto auto auto 1fr auto;
      overflow: hidden;
    }}
    .inspector-hero {{
      display: grid;
      grid-template-columns: 62px minmax(0, 1fr) 96px;
      gap: 12px;
      align-items: center;
      padding: 12px 14px 10px;
      border-bottom: 1px solid rgba(31, 149, 226, 0.25);
    }}
    .hero-star {{
      width: 48px;
      height: 48px;
      clip-path: polygon(50% 0, 61% 35%, 98% 35%, 68% 56%, 79% 91%, 50% 68%, 21% 91%, 32% 56%, 2% 35%, 39% 35%);
      background: #ffd166;
      box-shadow: 0 0 28px rgba(255, 209, 102, 0.75);
    }}
    .inspector-hero h2 {{
      margin: 0;
      color: #fff;
      font-size: 15px;
      text-transform: uppercase;
      overflow-wrap: anywhere;
    }}
    .inspector-hero p {{
      margin: 6px 0 0;
      color: #a6c3d9;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .hero-meta {{
      color: #9dc9e6;
      font-size: 11px;
      text-transform: uppercase;
      line-height: 1.45;
      border-left: 1px solid rgba(31, 149, 226, 0.2);
      padding-left: 10px;
    }}
    .delta-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
      padding: 10px 14px;
    }}
    .delta-card {{
      border: 1px solid rgba(31, 149, 226, 0.35);
      background: rgba(0, 23, 28, 0.68);
      border-radius: 3px;
      padding: 9px;
    }}
    .delta-card span {{
      display: block;
      color: #9dc9e6;
      font-size: 11px;
      text-transform: uppercase;
    }}
    .delta-card strong {{
      display: block;
      margin-top: 6px;
      color: #52ff7d;
      font-size: 23px;
    }}
    .spark {{
      height: 22px;
      margin-top: 4px;
      background: linear-gradient(135deg, transparent 45%, rgba(82,255,125,0.75) 47% 52%, transparent 54%),
        repeating-linear-gradient(160deg, transparent 0 10px, rgba(82,255,125,0.35) 11px 13px, transparent 14px 18px);
      opacity: 0.8;
    }}
    .next-action-card {{
      margin: 0 14px 10px;
      border: 1px solid rgba(31, 149, 226, 0.38);
      background: linear-gradient(90deg, rgba(110, 62, 255, 0.2), rgba(4, 20, 36, 0.72));
      border-radius: 4px;
      padding: 12px;
      color: #c8f0ff;
      overflow-wrap: anywhere;
    }}
    .next-action-card small {{
      display: block;
      margin-top: 3px;
      overflow-wrap: anywhere;
    }}
    .scenario-map {{
      margin: 0 14px 10px;
      border: 1px solid rgba(31, 149, 226, 0.34);
      border-radius: 4px;
      padding: 10px;
    }}
    .scenario-dots {{
      display: grid;
      grid-template-columns: repeat(15, 1fr);
      gap: 6px;
      margin-top: 8px;
    }}
    .scenario-dots button {{
      display: block;
      aspect-ratio: 1;
      width: 100%;
      border: 0;
      padding: 0;
      border-radius: 50%;
      background: #44d066;
      box-shadow: 0 0 8px currentColor;
      cursor: pointer;
    }}
    .scenario-dots button:nth-child(3n) {{ background: #ffb13b; }}
    .scenario-dots button:nth-child(7n) {{ background: #ff554f; }}
    .scenario-dots button.is-active {{
      outline: 2px solid rgba(255,255,255,0.92);
      outline-offset: 2px;
    }}
    .node-notes {{
      margin: 0 14px 12px;
      border: 1px solid rgba(31, 149, 226, 0.28);
      border-radius: 4px;
      padding: 10px;
      color: #a6c3d9;
      font-size: 12px;
      line-height: 1.45;
    }}
    .command-bottom {{
      display: grid;
      grid-template-columns: minmax(650px, 1fr) 270px 270px 280px;
      gap: 10px;
    }}
    .queue-table {{
      width: 100%;
      border-collapse: collapse;
      color: #b7c8d8;
      font-size: 12px;
    }}
    .queue-table th,
    .queue-table td {{
      border-top: 1px solid rgba(31, 149, 226, 0.18);
      padding: 8px 10px;
      text-align: left;
      vertical-align: middle;
    }}
    .queue-table th {{
      color: #75bce5;
      font-size: 11px;
      text-transform: uppercase;
      font-weight: 500;
    }}
    .status-pill {{
      display: inline-flex;
      min-width: 76px;
      justify-content: center;
      border: 1px solid rgba(179, 104, 255, 0.46);
      color: #d69bff;
      border-radius: 4px;
      padding: 3px 8px;
      background: rgba(93, 31, 148, 0.22);
    }}
    .resource-list,
    .intel-list,
    .break-list {{
      padding: 0 14px 14px;
      display: grid;
      gap: 10px;
      color: #b7c8d8;
      font-size: 12px;
    }}
    .meter {{
      display: grid;
      grid-template-columns: 70px 1fr auto;
      gap: 10px;
      align-items: center;
    }}
    .meter-bar {{
      height: 5px;
      background: rgba(71, 174, 255, 0.18);
      border-radius: 999px;
      overflow: hidden;
    }}
    .meter-bar i {{
      display: block;
      height: 100%;
      width: var(--w);
      background: linear-gradient(90deg, #71f4ff, #49f0a0);
    }}
    .intel-row,
    .break-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: start;
      min-width: 0;
    }}
    .intel-row span,
    .break-row span {{
      min-width: 0;
      overflow-wrap: anywhere;
    }}
    .intel-row small {{
      display: block;
      margin-top: 3px;
      color: #83a7bd;
      font-size: 11px;
      line-height: 1.25;
    }}
    .intel-row b,
    .break-row b {{
      text-align: right;
      white-space: nowrap;
    }}
    .break-row strong {{ color: #ffd166; }}
    .break-row strong {{ overflow-wrap: anywhere; }}
    @media (max-width: 1200px) {{
      .command-shell {{ grid-template-rows: auto auto auto; }}
      .command-top {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .brand-card {{ grid-column: 1 / -1; }}
      .command-main {{ grid-template-columns: 1fr; }}
      .command-sidebar {{ grid-template-rows: auto auto auto; }}
      .command-bottom {{ grid-template-columns: 1fr; }}
      .command-shell.focus-map {{
        width: min(100vw - 10px, 1200px);
        grid-template-rows: auto minmax(720px, calc(100vh - 112px));
      }}
      .command-shell.focus-map .command-top {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .command-shell.focus-map .command-top > .command-card {{
        grid-column: auto !important;
        grid-row: auto !important;
      }}
      .command-shell.focus-map .command-main {{ grid-template-columns: 1fr; }}
      .command-shell.focus-map .command-sidebar,
      .command-shell.focus-map .command-inspector {{ display: none; }}
      .command-shell.focus-map .command-bottom {{ grid-template-columns: 1fr; }}
      .command-shell.focus-map .map-panel {{ min-height: min(860px, calc(100vh - 124px)); }}
    }}
    @media (max-width: 760px) {{
      .command-shell {{ width: min(100vw - 14px, 760px); padding: 8px 0; gap: 8px; }}
      .command-top {{ grid-template-columns: 1fr; }}
      .command-shell.focus-map .command-top {{ grid-template-columns: 1fr; }}
      .command-shell.focus-map .command-top > .command-card {{
        grid-column: 1 !important;
        grid-row: auto !important;
      }}
      .brand-card {{ grid-template-columns: 56px minmax(0, 1fr); }}
      .brand-mark {{ width: 48px; height: 48px; font-size: 18px; }}
      .brand-title {{ font-size: 19px; }}
      .command-card {{ padding: 12px; }}
      .command-shell.focus-map .burndown-line {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .command-main {{ gap: 8px; }}
      .nav-panel {{ display: none; }}
      .map-panel {{ min-height: 560px; }}
      .family-band {{ font-size: 9px; padding: 5px 6px; max-width: 100px; white-space: normal; }}
      .map-layer-key {{
        left: 10px;
        right: 10px;
        max-width: none;
        font-size: 11px;
      }}
      .map-layer-key span {{
        max-width: 100%;
        white-space: normal;
        line-height: 1.25;
      }}
      .map-layer-key span:nth-child(3) {{
        display: none;
      }}
      .map-toolstrip {{ display: none; }}
      .delta-grid {{ grid-template-columns: 1fr; }}
      .scenario-dots {{ grid-template-columns: repeat(9, 1fr); }}
      .queue-table th:nth-child(4),
      .queue-table td:nth-child(4),
      .queue-table th:nth-child(5),
      .queue-table td:nth-child(5) {{ display: none; }}
    }}
  </style>
</head>
<body>
  <main class="command-shell focus-map">
    {fixture_banner}
    <section class="command-top" aria-label="研究指揮狀態">
      <div class="command-card brand-card">
        <div class="brand-mark">QR</div>
        <div>
          <h1 class="brand-title">量化研究指揮中心</h1>
          <div class="brand-subtitle">台股策略自動化系統</div>
        </div>
      </div>
      <div class="command-card kpi-card" id="hud" aria-label="研究總覽">
        <span>研究進度</span>
        <div class="kpi-main"><strong id="campaign-percent">0%</strong></div>
        <div class="progress-label" id="progress-label">第 4 / 7 階段：最佳化</div>
        <div class="seg-bar"><i class="is-lit"></i><i class="is-lit"></i><i class="is-lit"></i><i></i><i></i></div>
      </div>
      <div class="command-card kpi-card">
        <span>已執行進度</span>
        <div class="kpi-main"><strong id="executed-progress-count">0</strong><em id="executed-progress-pct">0%</em></div>
        <div class="kpi-note">完整研究宇宙：<b id="executed-progress-total">0</b></div>
      </div>
      <div class="command-card kpi-card">
        <span>分類消化進度</span>
        <span class="sr-only">artifact blocker / baseline provenance gap / controlled drain</span>
        <div class="kpi-main"><strong id="burn-down-classified-count">0</strong><em id="burn-down-pct">0%</em></div>
        <div class="burndown-line">
          <span>實跑<b id="burn-down-replay-count">0</b></span>
          <span>繼承<b id="burn-down-inherited-count">0</b></span>
          <span>不支援<b id="burn-down-unsupported-count">0</b></span>
          <span>證據阻塞<b id="artifact-blocker-count">0</b></span>
        </div>
        <div class="kpi-note">基準來源缺口：<b id="baseline-provenance-gap-count">0</b></div>
        <div class="kpi-note">控制網格：<b id="controlled-grid-drain-status">未同步</b></div>
      </div>
      <div class="command-card kpi-card">
        <span>全宇宙完成度</span>
        <div class="kpi-main"><strong><b id="discovered-scenario-count">0</b> / <b id="scenario-universe-count">0</b></strong><em id="discovered-pct">0%</em></div>
        <div class="seg-bar"><i class="is-lit"></i><i class="is-lit"></i><i class="is-lit"></i><i></i><i></i></div>
      </div>
      <div class="command-card kpi-card">
        <span>未探索情境</span>
        <div class="kpi-main"><strong id="pending-scenario-count">0</strong><em id="pending-pct">0%</em></div>
        <div class="seg-bar is-purple"><i class="is-lit"></i><i class="is-lit"></i><i></i><i></i><i></i></div>
      </div>
      <div class="command-card kpi-card">
        <span>星星點亮</span>
        <div class="kpi-main"><strong id="followup-scenario-count">0</strong></div>
        <div class="followup-line"><span>突破：<strong id="high-count">0</strong></span><span>追蹤：<strong id="med-count">0</strong></span><span>低訊：<strong id="low-count">0</strong></span></div>
      </div>
      <div class="command-card system-card">
        <span>生成日期</span>
        <div id="source-mode">載入中</div>
        <span style="margin-top:8px">系統狀態</span>
        <strong>正常</strong>
      </div>
    </section>
    <section class="command-main">
      <aside class="command-sidebar">
        <section class="nav-panel">
          <div class="nav-list">
            <div class="nav-item is-active" data-nav="star-map"><span class="nav-icon">◎</span><span>星圖</span></div>
            <div class="nav-item" data-nav="dashboard"><span class="nav-icon">▦</span><span>總覽</span></div>
            <div class="nav-item" data-nav="tech-tree"><span class="nav-icon">⌬</span><span>研究樹</span></div>
            <div class="nav-item" data-nav="signals"><span class="nav-icon">≋</span><span>訊號</span></div>
            <div class="nav-item" data-nav="backtest-lab"><span class="nav-icon">◇</span><span>回測室</span></div>
            <div class="nav-item" data-nav="reports"><span class="nav-icon">▤</span><span>報告</span></div>
            <div class="nav-item" data-nav="settings"><span class="nav-icon">⚙</span><span>設定</span></div>
          </div>
        </section>
        <section class="nav-panel" id="legend" aria-label="節點燈號">
          <h2 class="panel-title">節點燈號</h2>
          <div class="legend-compact" id="legend-grid"></div>
        </section>
        <section class="control-panel">
          <h2 class="panel-title">地圖控制</h2>
          <div class="map-controls">
            <div class="control-row">
              <button class="control-btn" data-control="reset" title="重置視角">⌖</button>
              <button class="control-btn" data-control="zoom-in" title="放大">+</button>
              <button class="control-btn" data-control="zoom-out" title="縮小">−</button>
              <button class="control-btn" data-control="focus" title="專注星圖">⛶</button>
            </div>
            <button class="goto-sector" id="goto-sector">前往星區</button>
          </div>
        </section>
      </aside>
      <section class="map-panel" aria-label="研究星圖">
        <div class="family-bands" id="family-bands"></div>
        <div class="starmap" id="star-map"></div>
        <div class="map-toolstrip"><span data-tool="fov">視野 100%</span><span data-tool="grid">格線 開</span><span data-tool="names">名稱 開</span><span data-tool="links">連線 開</span><span data-tool="fog">迷霧 開</span></div>
        <div class="map-layer-key"><span><b>亮點</b><i id="lit-layer-count">0</i>已執行</span><span><b>未點亮</b><i id="unlit-layer-count">0</i>淡霧區</span><span><b>大星</b>主題節點與候選訊號</span></div>
        <div class="map-footer">
          <div class="family-summary" id="family-summary"></div>
          <div id="scenario-readout">0 個情境</div>
        </div>
      </section>
      <aside class="command-inspector" id="inspector" aria-label="策略作戰室">
        <h2 class="panel-title">策略作戰室</h2>
        <div class="inspector-hero">
          <span class="hero-star" id="inspector-dot"></span>
          <div>
            <h2 id="inspector-title">已選節點</h2>
            <p id="inspector-subtitle">點星圖節點或候選策略可切換這裡的證據</p>
          </div>
          <div class="hero-meta" id="inspector-meta">節點ID<br>-<br>執行次數<br>-</div>
        </div>
        <div class="delta-grid">
          <div class="delta-card"><span>Score Δ</span><strong id="score-delta-card">-</strong><div class="spark"></div></div>
          <div class="delta-card"><span>Return Δ</span><strong id="return-delta-card">-</strong><div class="spark"></div></div>
          <div class="delta-card"><span>Drawdown Δ</span><strong id="drawdown-delta-card">-</strong><div class="spark"></div></div>
          <div class="delta-card"><span>證據格</span><strong id="winrate-delta-card">-</strong><div class="spark"></div></div>
        </div>
        <div class="next-action-card" id="next-action-card">下一步載入中</div>
        <div class="scenario-map">
          <div class="panel-title" style="padding:0">星格點亮 <span id="scenario-count-label"></span></div>
          <div class="scenario-dots" id="scenario-dots"></div>
        </div>
        <div class="node-notes" id="inspector-body"></div>
      </aside>
    </section>
    <section class="command-bottom">
      <section class="bottom-panel" id="mission-queue" aria-label="候選策略隊列">
        <h2 class="panel-title">候選策略隊列 <span style="color:#b28cff; margin-left:40px">下一批：<b id="next-batch-scenario-count">0</b> 個情境節點</span></h2>
        <div class="mission-list" id="mission-list"></div>
      </section>
      <section class="bottom-panel">
        <h2 class="panel-title">研究團隊 Console</h2>
        <div class="intel-list" id="research-team-console">
          <div class="intel-row"><span>Fog Map Bot</span><b>載入中</b></div>
          <div class="intel-row"><span>Research Worker</span><b>載入中</b></div>
          <div class="intel-row"><span>Strategy Ops</span><b>載入中</b></div>
          <div class="intel-row"><span>Ops Reporter</span><b>載入中</b></div>
        </div>
      </section>
      <section class="bottom-panel">
        <h2 class="panel-title">證據閘門</h2>
        <div class="intel-list" id="evidence-gates">
          <div class="intel-row"><span>Research-only contract</span><b>載入中</b></div>
          <div class="intel-row"><span>Production write guard</span><b>載入中</b></div>
          <div class="intel-row"><span>Burn-down classification</span><b>載入中</b></div>
          <div class="intel-row"><span>Next-stage candidates</span><b>載入中</b></div>
        </div>
      </section>
      <section class="bottom-panel">
        <h2 class="panel-title">需要決策</h2>
        <div class="break-list" id="breakthrough-list"></div>
      </section>
    </section>
  </main>
  <script id="fog-map-data" type="application/json">{payload_json}</script>
  <script>
    let payload = JSON.parse(document.getElementById('fog-map-data').textContent);
    window.payload = payload;
    let nodesById = new Map(payload.nodes.map((node) => [node.topic_id, node]));
    const colors = {{
      fog_gray: '#7c8797',
      blue: '#5cc8ff',
      red: '#ff5f73',
      yellow: '#ffd166',
      green: '#73f7a4',
      purple: '#b28cff',
      gold: '#ffcc4d',
    }};
    const formatNumber = (value) => new Intl.NumberFormat('zh-TW').format(value ?? 0);
    const formatPct = (value) => `${{Math.round((value ?? 0) * 1000) / 10}}%`;
    const valueOrDash = (value) => value === null || value === undefined || value === '' ? '-' : value;
    const mapState = {{
      filter: null,
      zoom: 1.22,
      panX: 0,
      panY: 0,
      sectorIndex: -1,
      links: true,
      names: true,
      fog: true,
      grid: true,
      focus: true,
      hoverComboId: null,
    }};
    const dragState = {{ active: false, pointerId: null, startX: 0, startY: 0, baseX: 0, baseY: 0, moved: false }};
    let scenarioPoints = [];
    let scenarioCanvasState = '';
    const decisionLabels = {{
      REJECTED_BY_STRATEGY_MATRIX: '策略矩陣淘汰',
      PARTIAL_SCORE_ONLY: '僅有部分分數，需要追蹤',
      CONFIRMED_FOR_NEXT_REPLAY: '已確認可進下一輪 replay',
      FIXTURE: '範例資料',
      not_run: '尚未執行',
    }};
    const statusNames = Object.fromEntries((payload.legend || []).map((item) => [item.id, item.label]));
    let universeFogState = '';
    const signed = (value, suffix = '') => {{
      if (value === null || value === undefined || value === '') return '-';
      const number = Number(value);
      if (Number.isNaN(number)) return value;
      return `${{number > 0 ? '+' : ''}}${{number.toFixed(3)}}${{suffix}}`;
    }};
    function actionText(value) {{
      if (!value) return '人工檢查';
      return displayText(value)
        .replaceAll('_', ' ')
        .replace('rerun with larger window or add risk check', '放大回測視窗或補風險檢查')
        .replace('advance to longer replay candidate', '推進到長窗 replay 候選')
        .replace('run autonomous research execute smoke', '執行研究流程 smoke 檢查')
        .replace('execute smoke', '執行 smoke 檢查')
        .replace('archive or wait for new evidence', '歸檔或等待新證據')
        .replace('manual review', '人工檢查');
    }}
    function displayText(value) {{
      if (!value) return '';
      return String(value)
        .replaceAll('_', ' ')
        .replaceAll('sector/theme context', '產業/主題脈絡')
        .replaceAll('sector context constrained', '產業脈絡限制')
        .replaceAll('feature group', '特徵群組')
        .replaceAll('context constrained', '脈絡限制')
        .replaceAll('ranking variant', 'ranking 變體')
        .replaceAll('candidate ranking artifact', '候選 ranking 證據')
        .replaceAll('candidate ranking', '候選 ranking')
        .replaceAll('archive or wait for new evidence', '歸檔或等待新證據')
        .replaceAll('candidate', '候選')
        .replaceAll('rankings', '排名')
        .replaceAll('ranking', '排名')
        .replaceAll('shadow', '影子')
        .replaceAll('subset', '子集合')
        .replaceAll('recent 100', '近 100 檔')
        .replaceAll('external review has high-priority hypothesis', '外部檢核標記高優先假說')
        .replaceAll('external review signal matched: theme momentum', '外部檢核命中：主題動能')
        .replaceAll('external review', '外部檢核')
        .replaceAll('signal matched', '訊號命中')
        .replaceAll('theme momentum', '主題動能')
        .replaceAll('high-priority hypothesis', '高優先假說')
        .replaceAll('half year', '半年窗')
        .replaceAll('batch01', '第 1 批')
        .replaceAll('shadow rankings', 'shadow ranking')
        .replaceAll('current research', '研究進行中')
        .replaceAll('not run', '尚未執行');
    }}
    function nodeNotes(node, scenarioNumber = null, scenarioCell = null) {{
      const scenario = node.scenario || {{}};
      const artifactLine = scenarioCell && scenarioCell.artifactPath
        ? `<br>證據檔：${{scenarioCell.artifactPath}}`
        : '';
      const comboLine = scenarioCell && scenarioCell.comboId
        ? `<br>組合 ID：${{scenarioCell.comboId}}`
        : '';
      const dimensionLine = scenarioCell && scenarioCell.dimensions
        ? `<br>維度：h=${{scenarioCell.dimensions.horizon || '-'}} / stop=${{scenarioCell.dimensions.stop_loss || '-'}} / tp=${{scenarioCell.dimensions.take_profit || '-'}} / group=${{scenarioCell.dimensions.group_exposure || '-'}}`
        : '';
      const pendingLine = scenarioCell && !scenarioCell.artifactPath
        ? '<br>狀態：未執行；這格可定位 combo，但 runner 還沒有產生 artifact。'
        : '';
      const scenarioLabel = scenarioCell && scenarioCell.scenarioLabel
        ? scenarioCell.scenarioLabel
        : `第 ${{scenarioNumber}} 格`;
      const scenarioLine = scenarioNumber
        ? `<br><br><strong>已選情境</strong><br>${{scenarioLabel}}；顏色由 run_history.jsonl 的 insight_level 決定。${{comboLine}}${{dimensionLine}}${{artifactLine}}${{pendingLine}}`
        : '';
      return `<strong>研究備註</strong><br>${{node.reasons.map(displayText).join('<br>')}}${{scenarioLine}}<br><br>` +
        `最後判定：${{decisionLabels[node.last_decision] || node.last_decision}}<br>` +
        `ranking 檔案：${{node.ranking_file_count}} / 情境數：${{scenario.scenario_count || 81}}`;
    }}
    function renderHud() {{
      const basePct = payload.summary.base_progress_pct ?? payload.summary.progress_pct ?? 0;
      const progressPct = payload.summary.expanded_progress_pct ?? basePct;
      const scenarioUniverse = payload.summary.expanded_universe_total || payload.summary.estimated_scenario_universe || 0;
      const processedScenarios = payload.summary.expanded_processed || payload.summary.estimated_processed_scenarios || 0;
      const baseProcessed = payload.summary.base_processed || payload.summary.processed_combos || 0;
      const baseTotal = payload.summary.base_universe_total || payload.summary.total_combos || 0;
      const pendingScenarios = Math.max(0, scenarioUniverse - processedScenarios);
      const burnDown = payload.burn_down_progress || {{}};
      const burnCounts = burnDown.counts || {{}};
      const burnClassified = burnDown.classified_total || 0;
      const burnTotal = burnDown.full_universe_total || scenarioUniverse;
      const burnPct = burnDown.classified_progress_pct ?? (burnClassified / Math.max(1, burnTotal));
      const activeQueueCount = payload.summary.active_expansion_queue_count || (payload.active_expansion_queue || []).length || 0;
      const unlitRepresentativeCount = payload.summary.unlit_representative_count || (payload.unlit_representative_queue || []).length || 0;
      const followupScenarios = (payload.summary.followup_signal_topics || 0) * (payload.summary.scenario_count_per_topic || 81);
      document.getElementById('source-mode').textContent = `${{payload.date}}`;
      document.getElementById('campaign-percent').textContent = formatPct(progressPct);
      document.getElementById('executed-progress-count').textContent = formatNumber(processedScenarios);
      document.getElementById('executed-progress-total').textContent = formatNumber(scenarioUniverse);
      document.getElementById('executed-progress-pct').textContent = formatPct(progressPct);
      document.getElementById('burn-down-classified-count').textContent = formatNumber(burnClassified);
      document.getElementById('burn-down-pct').textContent = formatPct(burnPct);
      document.getElementById('burn-down-replay-count').textContent = formatNumber(burnCounts.executed_replay_count || 0);
      document.getElementById('burn-down-inherited-count').textContent = formatNumber(burnCounts.equivalence_inherited_count || 0);
      document.getElementById('burn-down-unsupported-count').textContent = formatNumber(burnCounts.unsupported_count || 0);
      document.getElementById('artifact-blocker-count').textContent = formatNumber(burnDown.artifact_blocker_count || 0);
      document.getElementById('baseline-provenance-gap-count').textContent =
        formatNumber((burnDown.artifact_blocker_category_counts || {{}}).ARTIFACT_BLOCKER_PROVENANCE_GAP || 0);
      const controlled = burnDown.controlled_grid_drain || {{}};
      const controlledText = controlled.baseline_blocker_cleared
        ? `已清除 baseline blocker；${{controlled.no_replay_required_after_alias ? '無代表格需跑' : '有代表格待跑'}}`
        : (controlled.status || '未同步');
      document.getElementById('controlled-grid-drain-status').textContent = controlledText;
      document.getElementById('discovered-scenario-count').textContent = formatNumber(processedScenarios);
      document.getElementById('scenario-universe-count').textContent = formatNumber(scenarioUniverse);
      document.getElementById('pending-scenario-count').textContent = formatNumber(pendingScenarios);
      document.getElementById('lit-layer-count').textContent = formatNumber(processedScenarios);
      document.getElementById('unlit-layer-count').textContent = formatNumber(pendingScenarios);
      document.getElementById('followup-scenario-count').textContent = formatNumber(followupScenarios);
      document.getElementById('next-batch-scenario-count').textContent = formatNumber(activeQueueCount || unlitRepresentativeCount || pendingScenarios);
      document.getElementById('discovered-pct').textContent = formatPct(progressPct);
      document.getElementById('pending-pct').textContent = formatPct(pendingScenarios / Math.max(1, scenarioUniverse));
      document.getElementById('high-count').textContent = payload.summary.breakthrough_topics || 0;
      document.getElementById('med-count').textContent = followupScenarios;
      document.getElementById('low-count').textContent = (payload.summary.low_information_topics || 0) * (payload.summary.scenario_count_per_topic || 81);
      document.querySelectorAll('[data-summary]').forEach((item) => {{
        const key = item.dataset.summary;
        item.textContent = formatNumber(payload.summary[key]);
      }});
      document.getElementById('progress-label').textContent =
        `基礎掃描 ${{formatNumber(baseProcessed)}} / ${{formatNumber(baseTotal)}}；executed ${{formatPct(progressPct)}}；burn-down ${{formatPct(burnPct)}}`;
      document.getElementById('scenario-readout').textContent =
        `亮點 ${{formatNumber(processedScenarios)}}；未點亮 ${{formatNumber(pendingScenarios)}}；完整 ${{formatNumber(scenarioUniverse)}}`;
    }}
    function renderFamilies() {{
      const bandRoot = document.getElementById('family-bands');
      bandRoot.innerHTML = payload.families.filter((family) => family.total > 0).map((family) => {{
        const center = payload.family_centers[family.id] || {{ x: 50, y: 50 }};
        const y = Math.max(12, Math.min(86, center.y - 10));
        const scenarioPerTopic = payload.summary.scenario_count_per_topic || 81;
        const explored = (family.total - (family.statuses.pending || 0)) * scenarioPerTopic;
        const universe = family.total * scenarioPerTopic;
        const multiplier = payload.summary.expansion_multiplier || 1;
        const fullUniverse = universe * multiplier;
        const executedRatio = Math.min(1, Math.max(0, (payload.summary.expanded_processed || 0) / Math.max(1, payload.summary.expanded_universe_total || 1)));
        const executedFull = Math.round(fullUniverse * executedRatio);
        const unlitFull = Math.max(0, fullUniverse - executedFull);
        const haloW = Math.max(160, Math.min(360, Math.sqrt(fullUniverse) * 0.9));
        const haloH = Math.max(112, Math.min(260, haloW * 0.68));
        return `<div class="family-darkmatter" style="left:${{center.x}}%; top:${{center.y}}%; --halo-w:${{haloW}}px; --halo-h:${{haloH}}px"></div><div class="family-band" style="left:${{center.x}}%; top:${{y}}%">${{family.label}}<small>完整已執行 ${{formatNumber(executedFull)}} / ${{formatNumber(fullUniverse)}}</small><em>未點亮 ${{formatNumber(unlitFull)}}；基礎 ${{formatNumber(explored)}} / ${{formatNumber(universe)}}</em></div>`;
      }}
      ).join('');
      const summaryRoot = document.getElementById('family-summary');
      summaryRoot.innerHTML = payload.families.map((family) =>
        `<div class="family-pill"><strong>${{family.label}}</strong><span>${{family.total}} 個主題</span></div>`
      ).join('');
    }}
    function starLinks() {{
      const byFamily = new Map();
      payload.nodes.forEach((node) => {{
        if (!byFamily.has(node.family)) byFamily.set(node.family, []);
        byFamily.get(node.family).push(node);
      }});
      const lines = [];
      byFamily.forEach((nodes, familyId) => {{
        const center = payload.family_centers[familyId] || {{ x: 50, y: 50 }};
        const ordered = [...nodes].sort((a, b) => (a.position.y - b.position.y) || (a.position.x - b.position.x));
        ordered.slice(0, 18).forEach((node, index) => {{
          const hot = ['follow_up_signal', 'next_stage_candidate', 'breakthrough_candidate'].includes(node.status);
          lines.push(`<line class="star-link${{hot ? ' is-hot' : ''}}" x1="${{center.x}}" y1="${{center.y}}" x2="${{node.position.x}}" y2="${{node.position.y}}"></line>`);
          if (index > 0 && index % 2 === 0) {{
            const previous = ordered[index - 1];
            lines.push(`<line class="star-link" x1="${{previous.position.x}}" y1="${{previous.position.y}}" x2="${{node.position.x}}" y2="${{node.position.y}}"></line>`);
          }}
        }});
      }});
      return `<svg class="star-links" viewBox="0 0 100 100" preserveAspectRatio="none">${{lines.join('')}}</svg>`;
    }}
    function scenarioColor(color) {{
      return {{
        fog_gray: [143, 160, 182],
        blue: [103, 212, 255],
        red: [255, 110, 130],
        yellow: [255, 214, 110],
        green: [118, 245, 160],
        purple: [182, 148, 255],
        gold: [255, 209, 92],
      }}[color] || [143, 160, 182];
    }}
    function scenarioOpacity(color, baseOpacity) {{
      const factor = {{
        fog_gray: 0.08,
        blue: 0.22,
        red: 0.18,
        yellow: 0.42,
        green: 0.52,
        purple: 0.58,
        gold: 0.68,
      }}[color] || 0.6;
      return baseOpacity * factor;
    }}
    function scenarioVisual(point) {{
      const status = point.status || 'pending';
      if (point.isUnlitRepresentative) return {{ alpha: 0.58, radius: 0.78, ring: true }};
      if (point.isExpansionQueue && status === 'pending') return {{ alpha: 0.48, radius: 0.9, ring: true }};
      if (status === 'pending') return {{ alpha: 0.04, radius: 0.42 }};
      if (status === 'rejected') return {{ alpha: 0.30, radius: 0.58 }};
      if (status === 'low_information') return {{ alpha: 0.28, radius: 0.55 }};
      if (status === 'follow_up_signal') return {{ alpha: 0.72, radius: 0.88 }};
      if (status === 'effective_insight') return {{ alpha: 0.82, radius: 0.96 }};
      if (status === 'next_stage_candidate') return {{ alpha: 0.92, radius: 1.08 }};
      if (status === 'breakthrough_candidate') return {{ alpha: 1, radius: 1.18 }};
      return {{ alpha: 0.42, radius: 0.68 }};
    }}
    function seededNoise(seed) {{
      const value = Math.sin(seed * 12.9898) * 43758.5453;
      return value - Math.floor(value);
    }}
    function familyAttractor(index) {{
      const families = payload.families || [];
      if (!families.length) return {{ x: 52, y: 50 }};
      const family = families[index % families.length];
      const center = payload.family_centers[family.id] || {{ x: 52, y: 50 }};
      return center;
    }}
    function drawUniverseFogCanvas(force = false) {{
      const canvas = document.getElementById('universe-fog-canvas');
      if (!canvas) return;
      const fog = payload.full_universe_fog || {{}};
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, Math.floor(rect.width * dpr));
      const height = Math.max(1, Math.floor(rect.height * dpr));
      const sampleCount = Math.max(0, Number(fog.sample_count || 0));
      const executedSampleCount = Math.max(0, Number(fog.executed_sample_count || 0));
      const state = `${{width}}:${{height}}:${{sampleCount}}:${{executedSampleCount}}:${{mapState.fog ? 'fog' : 'nofog'}}`;
      if (!force && universeFogState === state) return;
      universeFogState = state;
      canvas.width = width;
      canvas.height = height;
      canvas.dataset.fullUniverse = String(fog.full_universe_count || payload.summary.expanded_universe_total || 0);
      canvas.dataset.fogSampleCount = String(sampleCount);
      canvas.dataset.clickable = 'false';
      canvas.dataset.clickableScenarioCount = String(scenarioPoints.filter((point) => point.comboId || point.artifactPath || point.status !== 'pending').length);
      window.__fullUniverseFog = {{
        fullUniverse: Number(canvas.dataset.fullUniverse),
        fogSampleCount: sampleCount,
        executedSampleCount,
        clickableScenarioCount: Number(canvas.dataset.clickableScenarioCount),
        clickableUnexecutedQueueCount: Number(fog.clickable_unexecuted_queue_count || 0),
        clickableUnlitRepresentativeCount: Number(fog.clickable_unlit_representative_count || 0),
        visibleLayer: 'classified-dim-fog/executed-lit-density',
      }};
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, width, height);
      if (!mapState.fog || sampleCount <= 0) return;
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = 'rgba(24, 43, 68, 0.075)';
      ctx.fillRect(0, 0, width, height);
      const cloudCenters = [
        {{ x: 18, y: 35, rx: 30, ry: 22, color: [92, 170, 210], alpha: 0.07 }},
        {{ x: 42, y: 72, rx: 34, ry: 24, color: [174, 160, 120], alpha: 0.045 }},
        {{ x: 66, y: 39, rx: 38, ry: 26, color: [120, 120, 178], alpha: 0.06 }},
        {{ x: 76, y: 70, rx: 30, ry: 22, color: [92, 170, 140], alpha: 0.055 }},
        {{ x: 53, y: 52, rx: 48, ry: 34, color: [92, 170, 210], alpha: 0.045 }},
      ];
      for (const cloud of cloudCenters) {{
        const cx = cloud.x * width / 100;
        const cy = cloud.y * height / 100;
        const radius = Math.max(cloud.rx * width / 100, cloud.ry * height / 100);
        const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
        gradient.addColorStop(0, `rgba(${{cloud.color[0]}}, ${{cloud.color[1]}}, ${{cloud.color[2]}}, ${{cloud.alpha}})`);
        gradient.addColorStop(0.52, `rgba(${{cloud.color[0]}}, ${{cloud.color[1]}}, ${{cloud.color[2]}}, ${{cloud.alpha * 0.42}})`);
        gradient.addColorStop(1, `rgba(${{cloud.color[0]}}, ${{cloud.color[1]}}, ${{cloud.color[2]}}, 0)`);
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fill();
      }}
      ctx.globalCompositeOperation = 'screen';
      const baseAlpha = 0.012;
      for (let index = 0; index < sampleCount; index += 1) {{
        const attractor = familyAttractor(index);
        const r1 = seededNoise(index + 11);
        const r2 = seededNoise(index + 71);
        const r3 = seededNoise(index + 131);
        const angle = r1 * Math.PI * 2;
        const radius = Math.sqrt(r2) * (24 + r3 * 26);
        const spiral = index * 2.399963;
        const deepSpaceMix = seededNoise(index + 829);
        const xPct = deepSpaceMix < 0.28
          ? 2 + seededNoise(index + 911) * 96
          : Math.max(1, Math.min(99, attractor.x + Math.cos(angle + spiral) * radius + (seededNoise(index + 211) - 0.5) * 4.6));
        const yPct = deepSpaceMix < 0.28
          ? 5 + seededNoise(index + 977) * 90
          : Math.max(5, Math.min(95, attractor.y + Math.sin(angle + spiral) * radius * 0.72 + (seededNoise(index + 307) - 0.5) * 3.4));
        const px = xPct * width / 100;
        const py = yPct * height / 100;
        const size = (0.45 + seededNoise(index + 401) * 0.82) * dpr;
        const alpha = baseAlpha + seededNoise(index + 503) * 0.038;
        const tint = seededNoise(index + 619);
        const color = tint > 0.90 ? [166, 152, 112] : tint > 0.72 ? [112, 124, 168] : tint > 0.48 ? [86, 140, 174] : [112, 132, 154];
        ctx.fillStyle = `rgba(${{color[0]}}, ${{color[1]}}, ${{color[2]}}, ${{alpha}})`;
        if (seededNoise(index + 701) > 0.78) {{
          ctx.beginPath();
          ctx.arc(px, py, size * 0.62, 0, Math.PI * 2);
          ctx.fill();
        }} else {{
          ctx.fillRect(px, py, size, size);
        }}
      }}
      ctx.globalCompositeOperation = 'lighter';
      for (let index = 0; index < executedSampleCount; index += 1) {{
        const attractor = familyAttractor(index * 3 + 17);
        const r1 = seededNoise(index + 1201);
        const r2 = seededNoise(index + 1271);
        const r3 = seededNoise(index + 1331);
        const angle = r1 * Math.PI * 2;
        const radius = Math.sqrt(r2) * (16 + r3 * 22);
        const spiral = index * 2.399963;
        const xPct = Math.max(1, Math.min(99, attractor.x + Math.cos(angle + spiral) * radius + (seededNoise(index + 1411) - 0.5) * 3.8));
        const yPct = Math.max(5, Math.min(95, attractor.y + Math.sin(angle + spiral) * radius * 0.72 + (seededNoise(index + 1507) - 0.5) * 2.8));
        const px = xPct * width / 100;
        const py = yPct * height / 100;
        const size = (0.82 + seededNoise(index + 1601) * 1.15) * dpr;
        const alpha = 0.055 + seededNoise(index + 1703) * 0.11;
        const tint = seededNoise(index + 1811);
        const color = tint > 0.88 ? [255, 209, 92] : tint > 0.58 ? [118, 245, 160] : [103, 212, 255];
        ctx.fillStyle = `rgba(${{color[0]}}, ${{color[1]}}, ${{color[2]}}, ${{alpha}})`;
        ctx.beginPath();
        ctx.arc(px, py, size * 0.72, 0, Math.PI * 2);
        ctx.fill();
      }}
      ctx.globalCompositeOperation = 'source-over';
    }}
    function buildScenarioPoints() {{
      const scenarioCount = payload.summary.scenario_count_per_topic || 81;
      const parts = [];
      const scenarioByKey = new Map((payload.scenarios || []).map((scenario) => [`${{scenario.topic_id}}:${{scenario.scenario_index}}`, scenario]));
      payload.nodes.forEach((node, topicIndex) => {{
        const baseX = node.position.x;
        const baseY = node.position.y;
        const compact = node.family === 'sector_industry' || node.family === 'liquidity';
        const spread = compact ? 4.4 : 5.8;
        for (let scenarioIndex = 0; scenarioIndex < scenarioCount; scenarioIndex += 1) {{
          const seed = (topicIndex + 1) * 92821 + (scenarioIndex + 1) * 68917;
          const rand = (salt) => {{
            const value = Math.sin(seed + salt * 131.7) * 10000;
            return value - Math.floor(value);
          }};
          const angle = scenarioIndex * 2.399963 + topicIndex * 0.31 + rand(1) * 0.85;
          const radius = Math.sqrt((scenarioIndex + 0.5) / scenarioCount) * spread * (0.72 + rand(2) * 0.42);
          const ellipse = compact ? 0.66 : 0.82;
          const driftX = Math.cos((topicIndex + 1) * 0.73) * radius * 0.18;
          const driftY = Math.sin((topicIndex + 1) * 0.61) * radius * 0.12;
          const x = Math.max(2, Math.min(98, baseX + Math.cos(angle) * radius + driftX + (rand(3) - 0.5) * 0.28));
          const y = Math.max(7, Math.min(93, baseY + Math.sin(angle) * radius * ellipse + driftY + (rand(4) - 0.5) * 0.24));
          const scenario = scenarioByKey.get(`${{node.topic_id}}:${{scenarioIndex + 1}}`) || {{}};
          let color = scenario.status_color || node.status_color;
          const size = 1.25 + rand(5) * 1.25;
          const opacity = 0.24 + rand(6) * 0.36;
          parts.push({{
            topicId: node.topic_id,
            comboId: scenario.combo_id,
            scenarioIndex: scenarioIndex + 1,
            dimensions: scenario.dimensions || {{}},
            status: scenario.status || 'pending',
            insightLevel: scenario.insight_level || 'unexplored',
            artifactPath: scenario.artifact_path || null,
            decision: scenario.decision || null,
            scoreDelta: scenario.score_delta ?? null,
            returnDelta: scenario.return_delta ?? null,
            drawdownDelta: scenario.drawdown_delta ?? null,
            x,
            y,
            color,
            size,
            opacity,
          }});
        }}
      }});
      return parts;
    }}
    function buildExpansionPoints() {{
      const queue = payload.active_expansion_queue || [];
      const perTopic = new Map();
      return queue.map((item, index) => {{
        const node = nodesById.get(item.topic_id);
        if (!node) return null;
        const topicCount = perTopic.get(item.topic_id) || 0;
        perTopic.set(item.topic_id, topicCount + 1);
        const seed = (index + 1) * 87119 + (topicCount + 1) * 45131;
        const rand = (salt) => {{
          const value = Math.sin(seed + salt * 97.31) * 10000;
          return value - Math.floor(value);
        }};
        const ring = 8.4 + (topicCount % 18) * 0.42 + rand(1) * 1.8;
        const angle = topicCount * 2.399963 + rand(2) * 0.9;
        const x = Math.max(1, Math.min(99, node.position.x + Math.cos(angle) * ring + (rand(3) - 0.5) * 1.1));
        const y = Math.max(6, Math.min(94, node.position.y + Math.sin(angle) * ring * 0.72 + (rand(4) - 0.5) * 0.8));
        const status = item.status || (item.run_status === 'completed' ? 'low_information' : 'pending');
        return {{
          topicId: item.topic_id,
          comboId: item.combo_id,
          scenarioIndex: `queue-${{index + 1}}`,
          scenarioLabel: `擴展 queue 第 ${{index + 1}} 格`,
          dimensions: item.dimensions || {{}},
          status,
          insightLevel: item.insight_level || 'unexplored',
          artifactPath: item.artifact_path || null,
          decision: item.decision || null,
          scoreDelta: item.score_delta ?? null,
          returnDelta: item.return_delta ?? null,
          drawdownDelta: item.drawdown_delta ?? null,
          x,
          y,
          color: item.status_color || (status === 'pending' ? 'fog_gray' : 'blue'),
          size: 2.05 + rand(5) * 0.85,
          opacity: status === 'pending' ? 0.82 : 0.64,
          isExpansionQueue: true,
          queueStage: item.stage || 'active_expansion_queue',
        }};
      }}).filter(Boolean);
    }}
    function buildUnlitRepresentativePoints() {{
      const queue = payload.unlit_representative_queue || [];
      const perTopic = new Map();
      return queue.map((item, index) => {{
        const node = nodesById.get(item.topic_id);
        if (!node) return null;
        const topicCount = perTopic.get(item.topic_id) || 0;
        perTopic.set(item.topic_id, topicCount + 1);
        const seed = (index + 1) * 75169 + (topicCount + 1) * 61291;
        const rand = (salt) => {{
          const value = Math.sin(seed + salt * 83.17) * 10000;
          return value - Math.floor(value);
        }};
        const ring = 12.5 + (topicCount % 12) * 0.72 + rand(1) * 2.4;
        const angle = topicCount * 2.399963 + rand(2) * 1.2;
        const x = Math.max(1, Math.min(99, node.position.x + Math.cos(angle) * ring + (rand(3) - 0.5) * 1.6));
        const y = Math.max(6, Math.min(94, node.position.y + Math.sin(angle) * ring * 0.7 + (rand(4) - 0.5) * 1.1));
        return {{
          topicId: item.topic_id,
          comboId: item.combo_id,
          scenarioIndex: `unlit-${{index + 1}}`,
          scenarioLabel: `完整宇宙未點亮代表格 ${{item.representative_index || index + 1}}`,
          dimensions: item.dimensions || {{}},
          status: 'pending',
          insightLevel: item.insight_level || 'unexplored',
          artifactPath: null,
          decision: item.decision || 'not_run',
          scoreDelta: null,
          returnDelta: null,
          drawdownDelta: null,
          x,
          y,
          color: 'fog_gray',
          size: 2.15 + rand(5) * 0.75,
          opacity: 0.92,
          isUnlitRepresentative: true,
          queueStage: item.stage || 'FULL-UNIVERSE-UNLIT-REPRESENTATIVE',
        }};
      }}).filter(Boolean);
    }}
    function drawScenarioCanvas(force = false) {{
      const canvas = document.getElementById('scenario-canvas');
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, Math.floor(rect.width * dpr));
      const height = Math.max(1, Math.floor(rect.height * dpr));
      const state = `${{width}}:${{height}}:${{mapState.filter || 'all'}}:${{mapState.hoverComboId || 'none'}}`;
      if (!force && scenarioCanvasState === state) return;
      scenarioCanvasState = state;
      canvas.width = width;
      canvas.height = height;
      canvas.dataset.scenarioCount = String(scenarioPoints.length);
      window.__scenarioRenderCount = scenarioPoints.length;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = 'source-over';
      for (const point of scenarioPoints) {{
        const filtered = mapState.filter && point.status !== mapState.filter;
        const visual = scenarioVisual(point);
        const alpha = filtered ? 0.012 : scenarioOpacity(point.color, point.opacity) * visual.alpha;
        if (alpha <= 0.01) continue;
        const [r, g, b] = scenarioColor(point.color);
        const px = point.x * width / 100;
        const py = point.y * height / 100;
        const radius = Math.max(0.42, point.size * dpr * visual.radius * (filtered ? 0.42 : 1));
        const glow = ctx.createRadialGradient(px, py, 0, px, py, radius * 1.55);
        glow.addColorStop(0, `rgba(${{r}}, ${{g}}, ${{b}}, ${{Math.min(0.58, alpha * 1.45)}})`);
        glow.addColorStop(0.38, `rgba(${{r}}, ${{g}}, ${{b}}, ${{alpha}})`);
        glow.addColorStop(1, `rgba(${{r}}, ${{g}}, ${{b}}, 0)`);
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(px, py, radius * 1.55, 0, Math.PI * 2);
        ctx.fill();
        if (visual.ring && !filtered) {{
          ctx.save();
          ctx.globalCompositeOperation = 'source-over';
          ctx.strokeStyle = `rgba(${{r}}, ${{g}}, ${{b}}, ${{Math.min(0.7, alpha * 2.8)}})`;
          ctx.lineWidth = Math.max(0.8, 1.1 * dpr);
          ctx.setLineDash([2.2 * dpr, 2.4 * dpr]);
          ctx.beginPath();
          ctx.arc(px, py, Math.max(5 * dpr, radius * 2.25), 0, Math.PI * 2);
          ctx.stroke();
          ctx.restore();
        }}
      }}
      if (mapState.hoverComboId) {{
        const hoverPoint = scenarioPoints.find((point) => point.comboId === mapState.hoverComboId);
        if (hoverPoint) {{
          const [r, g, b] = scenarioColor(hoverPoint.color);
          const px = hoverPoint.x * width / 100;
          const py = hoverPoint.y * height / 100;
          const ring = Math.max(9 * dpr, hoverPoint.size * dpr * 5.2);
          ctx.strokeStyle = `rgba(${{r}}, ${{g}}, ${{b}}, 0.92)`;
          ctx.lineWidth = Math.max(1.4, 1.6 * dpr);
          ctx.beginPath();
          ctx.arc(px, py, ring, 0, Math.PI * 2);
          ctx.stroke();
          ctx.strokeStyle = 'rgba(232, 247, 255, 0.72)';
          ctx.lineWidth = Math.max(0.8, 0.9 * dpr);
          ctx.beginPath();
          ctx.arc(px, py, ring + 4 * dpr, 0, Math.PI * 2);
          ctx.stroke();
        }}
      }}
    }}
    function nearestScenarioPoint(event) {{
      const canvas = document.getElementById('scenario-canvas');
      if (!canvas) return null;
      const rect = canvas.getBoundingClientRect();
      const clickX = event.clientX - rect.left;
      const clickY = event.clientY - rect.top;
      let best = null;
      let bestDistance = Infinity;
      for (const point of scenarioPoints) {{
        const pointX = (point.x / 100) * rect.width;
        const pointY = (point.y / 100) * rect.height;
        const distance = Math.hypot(pointX - clickX, pointY - clickY);
        const hitRadius = Math.max(point.isUnlitRepresentative ? 24 : point.isExpansionQueue ? 22 : 16, point.size * mapState.zoom * (point.isUnlitRepresentative ? 11 : point.isExpansionQueue ? 10 : 7.5));
        if (distance <= hitRadius && distance < bestDistance) {{
          best = point;
          bestDistance = distance;
        }}
      }}
      return best;
    }}
    function handleScenarioCanvasClick(event) {{
      if (mapState.suppressClickUntil && performance.now() < mapState.suppressClickUntil) {{
        return;
      }}
      const point = nearestScenarioPoint(event);
      if (!point) return;
      renderInspector(point.topicId, point.scenarioIndex, point);
    }}
    function handleMapPanelClick(event) {{
      if (event.target.closest('.map-toolstrip, .topic-hub')) return;
      handleScenarioCanvasClick(event);
    }}
    function setScenarioHover(point) {{
      const panel = document.querySelector('.map-panel');
      const nextComboId = point ? point.comboId : null;
      if (mapState.hoverComboId === nextComboId) return;
      mapState.hoverComboId = nextComboId;
      if (panel) panel.classList.toggle('is-point-hover', Boolean(nextComboId));
      drawScenarioCanvas(true);
    }}
    function clampPan() {{
      const panel = document.querySelector('.map-panel');
      const rect = panel ? panel.getBoundingClientRect() : {{ width: 1200, height: 720 }};
      const limitX = Math.max(180, rect.width * 0.5 * mapState.zoom);
      const limitY = Math.max(140, rect.height * 0.5 * mapState.zoom);
      mapState.panX = Math.max(-limitX, Math.min(limitX, mapState.panX));
      mapState.panY = Math.max(-limitY, Math.min(limitY, mapState.panY));
    }}
    function resetViewport(zoom = 1) {{
      mapState.zoom = zoom;
      mapState.panX = 0;
      mapState.panY = 0;
    }}
    function setZoom(nextZoom, anchorEvent = null) {{
      const panel = document.querySelector('.map-panel');
      const oldZoom = mapState.zoom;
      const zoom = Math.max(0.55, Math.min(7, Math.round(nextZoom * 100) / 100));
      if (!panel || Math.abs(zoom - oldZoom) < 0.001) {{
        mapState.zoom = zoom;
        return;
      }}
      const rect = panel.getBoundingClientRect();
      const anchorX = anchorEvent ? anchorEvent.clientX : rect.left + rect.width / 2;
      const anchorY = anchorEvent ? anchorEvent.clientY : rect.top + rect.height / 2;
      const offsetX = anchorX - (rect.left + rect.width / 2);
      const offsetY = anchorY - (rect.top + rect.height / 2);
      const ratio = zoom / oldZoom;
      mapState.panX = mapState.panX * ratio + offsetX * (1 - ratio);
      mapState.panY = mapState.panY * ratio + offsetY * (1 - ratio);
      mapState.zoom = zoom;
      clampPan();
    }}
    function mapTransform() {{
      return `translate(${{Math.round(mapState.panX)}}px, ${{Math.round(mapState.panY)}}px) scale(${{mapState.zoom}})`;
    }}
    function wireViewportGestures() {{
      const panel = document.querySelector('.map-panel');
      if (!panel || panel.dataset.viewportGestures === 'wired') return;
      panel.dataset.viewportGestures = 'wired';
      panel.addEventListener('wheel', (event) => {{
        if (event.target.closest('.map-toolstrip')) return;
        event.preventDefault();
        const direction = event.deltaY > 0 ? -1 : 1;
        const factor = direction > 0 ? 1.18 : 0.84;
        setZoom(mapState.zoom * factor, event);
        applyMapState();
      }}, {{ passive: false }});
      panel.addEventListener('click', handleMapPanelClick);
      panel.addEventListener('pointerdown', (event) => {{
        if (event.button !== 0 || event.target.closest('.map-toolstrip, .topic-hub')) return;
        setScenarioHover(null);
        dragState.active = true;
        dragState.pointerId = event.pointerId;
        dragState.startX = event.clientX;
        dragState.startY = event.clientY;
        dragState.baseX = mapState.panX;
        dragState.baseY = mapState.panY;
        dragState.moved = false;
        panel.classList.add('is-dragging');
        try {{
          panel.setPointerCapture(event.pointerId);
        }} catch (error) {{
          // 合成 pointer event 可能沒有 active pointer；真人拖曳仍會正常 capture。
        }}
      }});
      panel.addEventListener('pointermove', (event) => {{
        if (!dragState.active || dragState.pointerId !== event.pointerId) {{
          if (!event.target.closest('.map-toolstrip, .topic-hub')) setScenarioHover(nearestScenarioPoint(event));
          return;
        }}
        const dx = event.clientX - dragState.startX;
        const dy = event.clientY - dragState.startY;
        if (Math.hypot(dx, dy) > 3) dragState.moved = true;
        mapState.panX = dragState.baseX + dx;
        mapState.panY = dragState.baseY + dy;
        clampPan();
        applyMapState();
      }});
      panel.addEventListener('mouseleave', () => setScenarioHover(null));
      const finishDrag = (event) => {{
        if (!dragState.active || dragState.pointerId !== event.pointerId) return;
        if (dragState.moved) mapState.suppressClickUntil = performance.now() + 250;
        dragState.active = false;
        dragState.pointerId = null;
        panel.classList.remove('is-dragging');
        try {{
          panel.releasePointerCapture(event.pointerId);
        }} catch (error) {{
          // pointer capture 可能已被瀏覽器自動釋放，這裡只需收斂狀態。
        }}
      }};
      panel.addEventListener('pointerup', finishDrag);
      panel.addEventListener('pointercancel', finishDrag);
      panel.addEventListener('lostpointercapture', () => {{
        dragState.active = false;
        dragState.pointerId = null;
        panel.classList.remove('is-dragging');
      }});
    }}
    function renderMap() {{
      const root = document.getElementById('star-map');
      scenarioPoints = buildScenarioPoints().concat(buildExpansionPoints(), buildUnlitRepresentativePoints());
      window.__scenarioPoints = scenarioPoints;
      scenarioCanvasState = '';
      universeFogState = '';
      root.innerHTML = '<canvas class="universe-fog-canvas" id="universe-fog-canvas" aria-hidden="true"></canvas>' + starLinks() + '<canvas class="scenario-canvas" id="scenario-canvas" aria-hidden="true"></canvas><div class="map-core"><span>研究<br>核心</span></div>' + payload.nodes.map((node, index) => `
        <button class="topic-hub ${{['follow_up_signal', 'next_stage_candidate', 'breakthrough_candidate'].includes(node.status) || index % 23 === 0 ? 'is-star' : ''}}" data-topic-id="${{node.topic_id}}" data-color="${{node.status_color}}"
          style="left:${{node.position.x}}%; top:${{node.position.y}}%;"
          title="${{node.title}} / ${{node.status_label}}" aria-label="${{node.title}}"></button>
      `).join('');
      root.querySelectorAll('.topic-hub').forEach((button) => {{
        button.addEventListener('click', (event) => {{
          if (mapState.suppressClickUntil && performance.now() < mapState.suppressClickUntil) {{
            event.preventDefault();
            event.stopPropagation();
            return;
          }}
          renderInspector(button.dataset.topicId);
        }});
      }});
      const canvas = document.getElementById('scenario-canvas');
      canvas.addEventListener('click', handleScenarioCanvasClick);
      wireViewportGestures();
      window.addEventListener('resize', () => drawScenarioCanvas(true), {{ once: false }});
      applyMapState();
    }}
    function kv(label, value) {{
      return `<div class="kv"><span>${{label}}</span><span>${{valueOrDash(value)}}</span></div>`;
    }}
    function renderInspector(topicId, selectedScenarioNumber = null, selectedScenarioCell = null) {{
      const node = nodesById.get(topicId) || payload.nodes[0];
      if (!node) return;
      document.querySelectorAll('.topic-hub').forEach((button) => {{
        button.classList.toggle('is-selected', button.dataset.topicId === node.topic_id);
      }});
      const dot = document.getElementById('inspector-dot');
      const isScenarioSelection = Boolean(selectedScenarioCell && (selectedScenarioCell.comboId || selectedScenarioCell.isExpansionQueue));
      const isUnexecutedSelection = Boolean(isScenarioSelection && !selectedScenarioCell.artifactPath && selectedScenarioCell.status === 'pending');
      const statusLabel = isScenarioSelection
        ? (statusNames[selectedScenarioCell.status] || selectedScenarioCell.status || node.status_label)
        : node.status_label;
      const dotColor = isScenarioSelection ? selectedScenarioCell.color : node.status_color;
      dot.style.background = colors[dotColor] || colors.fog_gray;
      dot.style.color = colors[dotColor] || colors.fog_gray;
      const metrics = isScenarioSelection
        ? {{
            score_delta: selectedScenarioCell.scoreDelta,
            return_delta: selectedScenarioCell.returnDelta,
            drawdown_delta: selectedScenarioCell.drawdownDelta,
          }}
        : (node.metrics || {{}});
      const scenario = node.scenario || {{}};
      document.getElementById('inspector-title').textContent = isScenarioSelection
        ? `${{isUnexecutedSelection ? '未點亮情境' : '情境節點'}} / ${{statusLabel}}`
        : `主題節點 / ${{node.family_label}} / ${{statusLabel}}`;
      document.getElementById('inspector-subtitle').textContent = isScenarioSelection
        ? `${{selectedScenarioCell.scenarioLabel || `第 ${{selectedScenarioNumber}} 格`}}｜${{displayText(node.title)}}`
        : displayText(node.title);
      document.getElementById('inspector-meta').innerHTML = isScenarioSelection
        ? `組合 ID<br>${{String(selectedScenarioCell.comboId || 'pending').split('|').slice(-2).join('|')}}<br>所屬主題<br>${{node.topic_id.split(':').pop().slice(-12)}}`
        : `主題 ID<br>${{node.topic_id.split(':').pop().slice(-12)}}<br>已跑情境<br>${{node.run_count}}`;
      document.getElementById('score-delta-card').textContent = signed(metrics.score_delta);
      document.getElementById('return-delta-card').textContent = signed(metrics.return_delta);
      document.getElementById('drawdown-delta-card').textContent = signed(metrics.drawdown_delta);
      document.getElementById('winrate-delta-card').textContent = formatNumber(scenario.artifact_count || node.run_count || 0);
      document.getElementById('next-action-card').innerHTML = isScenarioSelection
        ? (selectedScenarioCell.artifactPath
          ? `<strong>情境證據檔</strong><br>${{selectedScenarioCell.artifactPath}}<br><small>判定：${{decisionLabels[selectedScenarioCell.decision] || selectedScenarioCell.decision || '尚未執行'}}</small>`
          : `<strong>尚未產生 artifact</strong><br>runner 尚未完成這個 combo；可定位但不可回看證據。<br><small>${{selectedScenarioCell.queueStage || '等待 run_history.jsonl'}}</small>`)
        : `<strong>下一步</strong><br>${{actionText(node.next_action)}}<br><small>候選目錄：${{node.candidate_dir || '無'}}</small>`;
      const queueCount = scenarioPoints.filter((point) => point.topicId === node.topic_id && point.isExpansionQueue).length;
      const unlitCount = scenarioPoints.filter((point) => point.topicId === node.topic_id && point.isUnlitRepresentative).length;
      document.getElementById('scenario-count-label').textContent = `（基礎 ${{scenario.scenario_count || 81}} 格；擴展 queue ${{queueCount}} 格；未點亮代表 ${{unlitCount}} 格）`;
      const dots = Array.from({{ length: 81 }}, (_, index) => `<button type="button" data-scenario="${{index + 1}}" title="情境 ${{index + 1}}"></button>`).join('');
      const scenarioDots = document.getElementById('scenario-dots');
      scenarioDots.innerHTML = dots;
      scenarioDots.querySelectorAll('button').forEach((button) => {{
        button.classList.toggle('is-active', Number(button.dataset.scenario) === Number(selectedScenarioNumber));
        button.addEventListener('click', () => {{
          scenarioDots.querySelectorAll('button').forEach((item) => item.classList.remove('is-active'));
          button.classList.add('is-active');
          const scenarioNumber = Number(button.dataset.scenario);
          const scenarioCell = scenarioPoints.find((point) => point.topicId === node.topic_id && point.scenarioIndex === scenarioNumber);
          renderInspector(node.topic_id, scenarioNumber, scenarioCell);
        }});
      }});
      document.getElementById('inspector-body').innerHTML = nodeNotes(node, selectedScenarioNumber, selectedScenarioCell);
    }}
    function renderMissionQueue() {{
      const root = document.getElementById('mission-list');
      root.innerHTML = `<table class="queue-table"><thead><tr><th>優先</th><th>候選策略</th><th>星區</th><th>下一步</th><th>證據</th><th>狀態</th></tr></thead><tbody>` +
        payload.mission_queue.slice(0, 5).map((mission, index) => `
          <tr class="mission" data-topic-id="${{mission.topic_id}}">
            <td>${{index + 1}}</td>
            <td>${{mission.topic_id.split(':').pop().slice(0, 24)}}</td>
            <td>${{mission.family}}</td>
            <td>${{actionText(mission.next_action)}}</td>
            <td>${{mission.reason}}</td>
            <td><span class="status-pill">待作戰</span></td>
          </tr>
        `).join('') + `</tbody></table>`;
      root.querySelectorAll('.mission').forEach((button) => {{
        button.addEventListener('click', () => renderInspector(button.dataset.topicId));
      }});
    }}
    function renderLegend() {{
      const counts = payload.summary.status_counts || {{}};
      const legendNames = {{
        pending: '未探索（迷霧）',
        low_information: '已探索',
        rejected: '已淘汰',
        follow_up_signal: '高風險洞察',
        effective_insight: '有效洞察',
        next_stage_candidate: '下階候選',
        breakthrough_candidate: '突破候選',
      }};
      document.getElementById('legend-grid').innerHTML = payload.legend.map((item) => `
        <div class="legend-item" data-status="${{item.id}}">
          <span class="legend-swatch" style="background:${{item.hex}}; color:${{item.hex}}"></span>
          <span><strong>${{legendNames[item.id] || item.label}}</strong></span>
          <b class="legend-count">${{formatNumber(counts[item.id] || 0)}}</b>
        </div>
      `).join('');
      document.querySelectorAll('#legend-grid .legend-item').forEach((item) => {{
        item.addEventListener('click', () => {{
          mapState.filter = mapState.filter === item.dataset.status ? null : item.dataset.status;
          applyMapState();
        }});
      }});
    }}
    function renderResearchTeamConsole() {{
      const root = document.getElementById('research-team-console');
      const latest = (payload.history || {{}}).latest_run || {{}};
      const queueCount = (payload.mission_queue || []).length;
      const activeQueueCount = payload.summary.active_expansion_queue_count || (payload.active_expansion_queue || []).length || 0;
      const rows = [
        ['Fog Map Bot', payload.status === 'OK' ? 'OK' : payload.status || 'UNKNOWN', payload.sources && payload.sources.run_history_jsonl ? 'run history linked' : 'source missing'],
        ['Research Worker', latest.status || 'NO_RUN', latest.decision || 'waiting'],
        ['Strategy Ops', queueCount ? `${{queueCount}} candidates` : 'empty', activeQueueCount ? `${{activeQueueCount}} active grid` : 'no active grid'],
        ['Ops Reporter', 'READY', 'uses decision brief / progress message'],
      ];
      root.innerHTML = rows.map(([name, status, note]) =>
        `<div class="intel-row"><span>${{name}}<small>${{note}}</small></span><b>${{status}}</b></div>`
      ).join('');
    }}
    function renderEvidenceGates() {{
      const root = document.getElementById('evidence-gates');
      const contract = payload.contract || {{}};
      const burnDown = payload.burn_down_progress || {{}};
      const rows = [
        ['Research-only contract', contract.research_only ? 'LOCKED' : 'CHECK', 'fog map 不執行回測、不訓練、不改正式 ranking'],
        ['Production write guard', contract.does_not_change_production_ranking ? 'LOCKED' : 'CHECK', '策略作戰室只讀證據，不給 production promotion'],
        ['Burn-down classification', formatPct(burnDown.classified_progress_pct || payload.summary.burn_down_progress_pct || 0), `${{formatNumber(burnDown.classified_total || payload.summary.burn_down_classified_total || 0)}} classified`],
        ['Next-stage candidates', formatNumber(payload.summary.next_stage_topics || payload.summary.next_stage_combos || 0), '只允許 replay / shadow / review'],
      ];
      root.innerHTML = rows.map(([name, status, note]) =>
        `<div class="intel-row"><span>${{name}}<small>${{note}}</small></span><b>${{status}}</b></div>`
      ).join('');
    }}
    function renderBreakthroughs() {{
      const hot = payload.nodes.filter((node) => ['follow_up_signal', 'next_stage_candidate', 'breakthrough_candidate'].includes(node.status)).slice(0, 4);
      document.getElementById('breakthrough-list').innerHTML = (hot.length ? hot : payload.nodes.slice(0, 3)).map((node) =>
        `<div class="break-row" data-topic-id="${{node.topic_id}}"><strong>${{displayText(node.title).slice(0, 24)}}</strong><span>${{actionText(node.next_action)}}</span></div>`
      ).join('');
      document.querySelectorAll('#breakthrough-list .break-row').forEach((row) => {{
        row.addEventListener('click', () => renderInspector(row.dataset.topicId));
      }});
    }}
    function applyMapState() {{
      const root = document.getElementById('star-map');
      const familyBands = document.getElementById('family-bands');
      const panel = document.querySelector('.map-panel');
      const shell = document.querySelector('.command-shell');
      const transform = mapTransform();
      root.style.transform = transform;
      if (familyBands) familyBands.style.transform = transform;
      panel.classList.toggle('hide-links', !mapState.links);
      panel.classList.toggle('hide-names', !mapState.names);
      panel.classList.toggle('hide-fog', !mapState.fog);
      panel.classList.toggle('hide-grid', !mapState.grid);
      shell.classList.toggle('focus-map', mapState.focus === true);
      document.querySelectorAll('.topic-hub').forEach((item) => {{
        const topic = nodesById.get(item.dataset.topicId);
        const hidden = mapState.filter && topic && topic.status !== mapState.filter;
        item.classList.toggle('is-filtered-out', Boolean(hidden));
      }});
      drawScenarioCanvas();
      drawUniverseFogCanvas();
      document.querySelectorAll('#legend-grid .legend-item').forEach((item) => {{
        item.classList.toggle('is-active', mapState.filter === item.dataset.status);
      }});
      document.querySelector('[data-tool="fov"]').textContent = `視野 ${{Math.round(mapState.zoom * 100)}}%`;
      document.querySelector('[data-tool="grid"]').textContent = `格線 ${{mapState.grid ? '開' : '關'}}`;
      document.querySelector('[data-tool="names"]').textContent = `名稱 ${{mapState.names ? '開' : '關'}}`;
      document.querySelector('[data-tool="links"]').textContent = `連線 ${{mapState.links ? '開' : '關'}}`;
      document.querySelector('[data-tool="fog"]').textContent = `迷霧 ${{mapState.fog ? '開' : '關'}}`;
      document.querySelectorAll('.map-toolstrip span').forEach((item) => {{
        const key = item.dataset.tool;
        item.classList.toggle('is-off', key !== 'fov' && mapState[key] === false);
      }});
    }}
    function focusFamily(index) {{
      const family = payload.families[index % payload.families.length];
      const node = payload.nodes.find((item) => item.family === family.id) || payload.nodes[0];
      if (node) renderInspector(node.topic_id);
      mapState.filter = null;
      document.getElementById('goto-sector').textContent = family.label;
      applyMapState();
    }}
    function renderReportSummary() {{
      const burnDown = payload.burn_down_progress || {{}};
      const controlledDrain = burnDown.controlled_grid_drain || {{}};
      document.querySelectorAll('.topic-hub').forEach((button) => button.classList.remove('is-selected'));
      const dot = document.getElementById('inspector-dot');
      dot.style.background = colors.clear_green || colors.fog_gray;
      dot.style.color = colors.clear_green || colors.fog_gray;
      document.getElementById('inspector-title').textContent = '報告摘要';
      document.getElementById('inspector-subtitle').textContent = `Research fog map / ${{payload.date}}`;
      document.getElementById('inspector-meta').innerHTML = `日期<br>${{payload.date}}<br>來源<br>repo artifact`;
      document.getElementById('score-delta-card').textContent = formatNumber(payload.total_topics || 0);
      document.getElementById('return-delta-card').textContent = burnDown.controlled_grid_drain_ready ? 'OK' : '待同步';
      document.getElementById('drawdown-delta-card').textContent = burnDown.baseline_blocker_cleared ? '0' : formatNumber(burnDown.artifact_blocker_count || 0);
      document.getElementById('winrate-delta-card').textContent = controlledDrain.representative_replay_count === 0 ? '0' : formatNumber(controlledDrain.representative_replay_count);
      document.getElementById('next-action-card').innerHTML = `<strong>Canonical JSON</strong><br>artifacts/research_map/research_fog_map_${{payload.date}}.json<br><small>latest：artifacts/research_map/research_fog_map_latest.json</small>`;
      document.getElementById('scenario-count-label').textContent = '（報告狀態）';
      document.getElementById('scenario-dots').innerHTML = '';
      document.getElementById('inspector-body').innerHTML = [
        kv('controlled drain', burnDown.controlled_grid_drain_status || '未同步'),
        kv('baseline blocker cleared', burnDown.baseline_blocker_cleared ? 'true' : 'false'),
        kv('artifact blocker count', formatNumber(burnDown.artifact_blocker_count || 0)),
        kv('micro batch', controlledDrain.micro_batch_status || '-'),
        kv('resume batch', controlledDrain.unattended_resume_status || '-'),
      ].join('');
    }}
    function wireControls() {{
      document.querySelectorAll('.nav-item').forEach((item) => {{
        item.addEventListener('click', () => {{
          document.querySelectorAll('.nav-item').forEach((nav) => nav.classList.remove('is-active'));
          item.classList.add('is-active');
          const mode = item.dataset.nav;
          if (mode === 'star-map') {{ mapState.filter = null; resetViewport(1.22); mapState.focus = true; }}
          if (mode === 'dashboard') {{ mapState.filter = null; resetViewport(0.92); }}
          if (mode === 'tech-tree') {{ mapState.links = true; mapState.names = true; resetViewport(1.08); }}
          if (mode === 'signals') {{ mapState.filter = 'follow_up_signal'; }}
          if (mode === 'backtest-lab') {{ resetViewport(1.15); renderInspector(payload.default_selected_topic_id); }}
          if (mode === 'reports') renderReportSummary();
          if (mode === 'settings') {{ mapState.fog = !mapState.fog; }}
          applyMapState();
        }});
      }});
      document.querySelectorAll('.control-btn').forEach((button) => {{
        button.addEventListener('click', () => {{
          const action = button.dataset.control;
          if (action === 'reset') {{ resetViewport(1.22); mapState.filter = null; mapState.focus = true; }}
          if (action === 'zoom-in') setZoom(mapState.zoom * 1.28);
          if (action === 'zoom-out') setZoom(mapState.zoom / 1.28);
          if (action === 'focus') mapState.focus = !mapState.focus;
          applyMapState();
        }});
      }});
      document.getElementById('goto-sector').addEventListener('click', () => {{
        mapState.sectorIndex = (mapState.sectorIndex + 1) % payload.families.length;
        focusFamily(mapState.sectorIndex);
      }});
      document.querySelectorAll('.map-toolstrip span').forEach((item) => {{
        item.addEventListener('click', () => {{
          const tool = item.dataset.tool;
          if (tool === 'fov') {{
            if (mapState.zoom >= 3.5) resetViewport(1.22);
            else setZoom(mapState.zoom * 1.55);
          }}
          if (tool !== 'fov') mapState[tool] = !mapState[tool];
          applyMapState();
        }});
      }});
    }}
    async function loadLatestPayload() {{
      try {{
        const response = await fetch(`research_fog_map_latest.json?ts=${{Date.now()}}`, {{ cache: 'no-store' }});
        if (response.ok) payload = await response.json();
      }} catch (error) {{
        console.warn('使用 embedded fallback payload', error);
      }}
      window.payload = payload;
      nodesById = new Map(payload.nodes.map((node) => [node.topic_id, node]));
      renderHud();
      renderFamilies();
      renderMap();
      renderMissionQueue();
      renderLegend();
      renderResearchTeamConsole();
      renderEvidenceGates();
      renderBreakthroughs();
      renderInspector(payload.default_selected_topic_id || (payload.nodes[0] && payload.nodes[0].topic_id));
      wireControls();
    }}
    loadLatestPayload();
  </script>
</body>
</html>
"""

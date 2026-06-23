
"""
報告生成器格式化層：Markdown
將分析數據轉換為美觀的 Markdown 報告
"""
class MarkdownFormatter:
    def format(self, data: dict) -> str:
        md = f"# 每日選股分析報告\n\n日期: {data['report_date']}\n"
        for stock in data['recommendations']:
            brief = stock.get("daily_brief") or {}
            md += f"\n---\n\n## 個股：{stock['stock']}\n\n"
            md += f"- **結論**：**{stock['decision']['verdict']}**\n"
            md += f"- **核心摘要**：{brief.get('core_conclusion') or stock['decision']['reason_1']}\n"
            md += self._section("入選理由", brief.get("why_pick"))
            md += self._score_breakdown(brief.get("score_breakdown") or {})
            md += self._section("風險警報", brief.get("risk_alerts"))
            md += self._section("正向催化", brief.get("positive_catalysts"))
            md += self._section("操作檢查清單", brief.get("action_checklist"))
            md += self._coverage(brief.get("data_coverage") or [])
        return md

    def save(self, data: dict, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.format(data))

    def _section(self, title: str, items) -> str:
        if not items:
            return f"\n### {title}\n\n- 無明確資料。\n"
        lines = [f"\n### {title}\n"]
        lines.extend(f"- {item}" for item in items)
        return "\n".join(lines) + "\n"

    def _score_breakdown(self, scores: dict) -> str:
        if not scores:
            return ""
        fields = [
            ("模型勝率", "model_prob"),
            ("風險調整分數", "risk_adjusted_score"),
            ("prediction", "prediction_score"),
            ("setup", "setup_score"),
            ("quality", "quality_score"),
            ("risk_penalty", "risk_penalty"),
            ("risk_reward", "risk_reward"),
            ("execution_rr", "execution_risk_reward"),
        ]
        rows = []
        for label, key in fields:
            value = scores.get(key)
            if value is None:
                continue
            rows.append(f"| {label} | {value} |")
        if not rows:
            return ""
        return "\n### 分數拆解\n\n| 欄位 | 數值 |\n|------|------|\n" + "\n".join(rows) + "\n"

    def _coverage(self, coverage: list[dict]) -> str:
        if not coverage:
            return ""
        lines = ["\n### 資料覆蓋與降級\n", "| 欄位 | 狀態 | 說明 |", "|------|------|------|"]
        for item in coverage:
            lines.append(
                f"| {item.get('field', '')} | {item.get('status', '')} | {item.get('reason', '')} |"
            )
        return "\n".join(lines) + "\n"


"""
報告生成器格式化層：Markdown
將分析數據轉換為美觀的 Markdown 報告
"""
class MarkdownFormatter:
    def format(self, data: dict) -> str:
        # 重用原有的 Markdown 模板邏輯
        md = f"# 每日選股分析報告\n日期: {data['report_date']}\n"
        for stock in data['recommendations']:
            md += f"\n---\n## 個股：{stock['stock']}\n"
            md += f"- **結論**：**{stock['decision']['verdict']}**\n"
            md += f"- **為什麼**：{stock['decision']['reason_1']}\n"
            # ... (模板內容與原 report_generator.py 一致)
        return md

    def save(self, data: dict, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.format(data))

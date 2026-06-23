
"""
報告生成器調度器 (Orchestrator)
採用原子化組件生成符合 User Template 的報告
"""
import html
import json
import pandas as pd
from pathlib import Path
import yaml
from .logic.analyzer import StockAnalyzer
from .formatters.markdown_formatter import MarkdownFormatter
from .formatters.yaml_formatter import YAMLFormatter

class StockReportGenerator:
    """原子化股票分析報告生成器"""
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.analyzer = StockAnalyzer()
        self.md_formatter = MarkdownFormatter()
        self.yaml_formatter = YAMLFormatter()

    def generate_report(self, ranked_df: pd.DataFrame, features_df: pd.DataFrame):
        """生成完整分析報告 (Markdown + YAML)"""
        print("📝 生成原子化分析報告...")
        
        # 1. 數據分析與準備 (Logic Layer)
        report_data = self.analyzer.prepare_report_data(ranked_df, features_df)
        
        # 2. 生成 YAML (Formatter Layer)
        yaml_path = self.artifacts_dir / "analysis_report.yaml"
        self.yaml_formatter.save(report_data, yaml_path)
        
        # 3. 生成 Markdown (Formatter Layer)
        md_path = self.artifacts_dir / "analysis_report.md"
        self.md_formatter.save(report_data, md_path)

        # 4. 生成 JSON / HTML，作為通知與 Web 工作台的穩定 artifact。
        json_path = self.artifacts_dir / "analysis_report.json"
        json_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
        html_path = self.artifacts_dir / "analysis_report.html"
        html_path.write_text(self._render_html(self.md_formatter.format(report_data)), encoding="utf-8")
        
        # 5. 生成 CSV
        self._save_summary_csv(report_data)

    def _save_summary_csv(self, report_data: dict):
        csv_rows = []
        for stock in report_data.get('recommendations', []):
             csv_rows.append({
                 'stock': stock['stock'],
                 'verdict': stock['decision']['verdict'],
                 'p_win': stock['metrics']['p_win_5d'],
                 'entry': f"{stock['trade_plan']['entry_zone']['low']}-{stock['trade_plan']['entry_zone']['high']}",
                 'risk': stock['trade_plan']['invalidation']
             })
        pd.DataFrame(csv_rows).to_csv(self.artifacts_dir / "ranked_stocks_detailed.csv", index=False, encoding='utf-8-sig')

    def _render_html(self, markdown_text: str) -> str:
        escaped = html.escape(markdown_text)
        return (
            "<!doctype html>\n"
            "<html lang=\"zh-Hant\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "  <title>TOP10 每日選股分析報告</title>\n"
            "  <style>\n"
            "    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 32px; line-height: 1.6; }\n"
            "    pre { white-space: pre-wrap; word-break: break-word; }\n"
            "  </style>\n"
            "</head>\n"
            "<body><pre>"
            f"{escaped}"
            "</pre></body>\n"
            "</html>\n"
        )


"""
報告生成器格式化層：YAML
將分析數據轉換為結構化的 YAML 檔案
"""
import yaml

class YAMLFormatter:
    def save(self, data: dict, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

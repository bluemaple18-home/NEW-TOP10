import re
from pathlib import Path

stock_id = "1141"
report_path = Path("artifacts/analysis_report.md")

with open(report_path, 'r', encoding='utf-8') as f:
    full_report = f.read()

# Pattern used in UI
pattern = rf"## 個股：{stock_id}.*?(?=\n---\n|\Z)"
match = re.search(pattern, full_report, re.DOTALL)

print(f"Match found: {bool(match)}")
if match:
    print(f"Match length: {len(match.group(0))}")
    print("Preview:", match.group(0)[:50])
    
    stock_report_md = match.group(0)
    # Test sub-sections
    sec_pat = r"### (\d+\)) (.+?)\n(.*?)(?=\n### \d+\)|$)"
    sections = {}
    for m in re.finditer(sec_pat, stock_report_md, re.DOTALL):
        sec_key = f"{m.group(1)} {m.group(2)}"
        print(f"Found section: {sec_key}")
        sections[sec_key] = m.group(3).strip()
    
    print("Sections found:", list(sections.keys()))

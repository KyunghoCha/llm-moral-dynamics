import os
from pathlib import Path
from datetime import datetime
import json

class ThesisAssembler:
    def __init__(self, sections_dir, plots_dir, output_path):
        self.sections_dir = Path(sections_dir)
        self.plots_dir = Path(plots_dir)
        self.output_path = Path(output_path)
        self.sections = [
            "01_abstract.md", "02_introduction.md", "03_background.md", 
            "04_methodology.md", "05_results.md", "06_qualitative.md", 
            "07_discussion.md", "08_conclusion.md", "09_references.md"
        ]

    def read_markdown(self, filename):
        path = self.sections_dir / filename
        if not path.exists():
            return f"<p>Error: {filename} not found.</p>"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        html = ""
        lines = content.split("\n")
        in_table = False
        table_html = ""
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            if not line:
                if in_table:
                    html += table_html + "</tbody></table>"
                    table_html = ""
                    in_table = False
                continue
                
            # Inline formatting: Bold **text**
            if "**" in line:
                parts = line.split("**")
                new_line = ""
                for j, part in enumerate(parts):
                    if j % 2 == 1: # Odd index is inside **
                        new_line += f"<strong>{part}</strong>"
                    else:
                        new_line += part
                line = new_line
            
            # Inline formatting: Italic *text* (simple case)
            if "*" in line and "<strong>" not in line: # Avoid double processing if strong added *
                 # ... (existing italic logic)
                 pass 

            # Table handling
            if line.startswith("|"):
                if not in_table:
                    in_table = True
                    table_html = "<table>"
                    # Check if next line is separator |---|
                    if i + 1 < len(lines) and "---" in lines[i+1]:
                        # This is header
                        cols = [c.strip() for c in line.strip("|").split("|")]
                        table_html += "<thead><tr>"
                        for c in cols:
                            table_html += f"<th>{c}</th>"
                        table_html += "</tr></thead><tbody>"
                    else:
                        # Should not happen if standard markdown, but fallback
                        # Treat as body row
                        cols = [c.strip() for c in line.strip("|").split("|")]
                        table_html += "<tr>"
                        for c in cols:
                            table_html += f"<td>{c}</td>"
                        table_html += "</tr>"
                else:
                    # Inside table
                    if "---" in line:
                         continue # Skip separator line
                    cols = [c.strip() for c in line.strip("|").split("|")]
                    table_html += "<tr>"
                    for c in cols:
                        table_html += f"<td>{c}</td>"
                    table_html += "</tr>"
                continue
            
            # If we were in table and hit non-table line
            if in_table:
                html += table_html + "</tbody></table>"
                table_html = ""
                in_table = False
                
            if line.startswith("# "):
                html += f"<h1>{line[2:]}</h1>"
            elif line.startswith("## "):
                html += f"<h2>{line[3:]}</h2>"
            elif line.startswith("### "):
                html += f"<h3>{line[4:]}</h3>"
            elif line.startswith("- "):
                html += f"<li>{line[2:]}</li>"
            elif line.startswith("> "):
                html += f"<blockquote>{line[2:]}</blockquote>"
            elif line.startswith("!["):
                # Handle images: ![alt](path)
                try:
                    alt_text = line.split("[")[1].split("]")[0]
                    img_path = line.split("(")[1].split(")")[0]
                    # Fix relative path: ../plots/ -> ../../plots/ 
                    if img_path.startswith("../plots/"):
                        img_path = "../../plots/" + img_path.split("../plots/")[1]
                    html += f'<div class="figure-box"><img src="{img_path}" style="width:100%; max-width:800px;"><div class="caption">{alt_text}</div></div>'
                except:
                    html += f"<p>Image parsing error: {line}</p>"
            else:
                html += f"<p>{line}</p>"
        
        # Close table if file ended inside table
        if in_table:
            html += table_html + "</tbody></table>"
            
        return html

    def get_appendix(self, stats_file):
        if not os.path.exists(stats_file):
            return "<p>Appendix data not found.</p>"
        
        with open(stats_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        html = "<h2>Appendix: Dataset Details (N=115)</h2>"
        html += "<table><thead><tr><th>Condition</th><th>N</th><th>Init H</th><th>Final H</th><th>TTC</th></tr></thead><tbody>"
        # Skip header lines of analysis_txt
        for line in lines[10:14]: # The summary table part
            parts = line.split()
            if len(parts) >= 5:
                html += f"<tr><td>{parts[0]}</td><td>{parts[1]}</td><td>{parts[2]}</td><td>{parts[3]}</td><td>{parts[5]}</td></tr>"
        html += "</tbody></table>"
        
        html += "<p>전체 115개 시드 보충 데이터는 서버 로그 아카이브를 참조하십시오.</p>"
        return html

    def assemble(self):
        css = """
        @page { size: A4; margin: 25mm; }
        body { 
            font-family: 'Times New Roman', 'NanumMyeongjo', serif; 
            line-height: 1.8; 
            color: #1a1a1a; 
            max-width: 850px; 
            margin: 0 auto; 
            padding: 50px;
            background: #fff;
            text-align: justify;
        }
        h1 { font-size: 24pt; text-align: center; margin-top: 60px; border-bottom: 2px solid #000; padding-bottom: 10px; }
        h2 { font-size: 18pt; margin-top: 40px; border-bottom: 1px solid #ccc; padding-bottom: 5px; color: #333; }
        h3 { font-size: 14pt; margin-top: 25px; color: #444; }
        p { margin-bottom: 1.5em; text-indent: 1em; }
        blockquote { 
            background: #f9f9f9; 
            border-left: 5px solid #333; 
            padding: 15px 25px; 
            margin: 20px 0; 
            font-size: 10.5pt;
            font-style: italic;
        }
        .figure-box { margin: 30px 0; text-align: center; page-break-inside: avoid; }
        .caption { font-size: 9pt; color: #666; margin-top: 10px; }
        table { width: 100%; border-collapse: collapse; margin: 25px 0; font-size: 10pt; }
        th, td { border: 1px solid #333; padding: 10px; text-align: center; }
        th { background: #eee; }
        .title-page { text-align: center; margin-bottom: 100px; padding: 100px 0; }
        .title-main { font-size: 28pt; font-weight: bold; margin-bottom: 20px; color: #000; }
        .title-sub { font-size: 18pt; margin-bottom: 80px; color: #555; }
        .author-info { font-size: 14pt; margin-top: 50px; }
        .page-break { page-break-before: always; }
        footer { margin-top: 100px; text-align: center; font-size: 9pt; color: #aaa; }
        """

        full_html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>석사 학위 논문 - 차경호</title>
    <style>{css}</style>
</head>
<body>
    <div class="title-page">
        <div class="title-main">LLM 다중 에이전트 환경에서의 윤리적 의사결정 수렴 현상 연구</div>
        <div class="title-sub">사회적 정보 공개 수준에 따른 집단적 동조와 다양성 붕괴 분석</div>
        <div class="author-info">
            제출자: 차경호 (Kyungho Cha)<br>
            지도교수: Antigravity Assistant<br><br>
            2026년 1월
        </div>
    </div>
    <div class="page-break"></div>
"""
        for section_file in self.sections:
            full_html += self.read_markdown(section_file)
            # Add page break after major sections if needed
            if section_file in ["01_abstract.md", "04_methodology.md", "05_results.md"]:
                full_html += '<div class="page-break"></div>'

        # Append Appendix
        full_html += '<div class="page-break"></div>'
        full_html += self.get_appendix("logs/batch_Phase1_Trolley_Golden/batch_summary_analysis.txt")

        full_html += """
    <footer>
        © 2026 AI Ethics Research Group. All rights reserved.
    </footer>
</body>
</html>
"""
        # Fix image paths for the report location
        # The report is at docs/reports/Final_Thesis_v2.html
        # Plots are at plots/batch_.../
        # Relative path from docs/reports/ to plots/ is ../../plots/
        full_html = full_html.replace("../plots/", "../../plots/")

        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        print(f"Final Thesis assembled at: {self.output_path}")

if __name__ == "__main__":
    assembler = ThesisAssembler(
        sections_dir="docs/reports/phase1_thesis/drafts",
        plots_dir="plots/batch_Phase1_Trolley_Golden",
        output_path="docs/reports/phase1_thesis/Final_Thesis_Phase1_KR.html"
    )
    assembler.assemble()

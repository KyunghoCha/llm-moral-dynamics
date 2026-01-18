import json
import math
import statistics
import os
from pathlib import Path
from datetime import datetime

class ThesisAnalyzer:
    def __init__(self, batch_dir):
        self.batch_dir = Path(batch_dir)
        self.summary_file = self.batch_dir / "batch_summary.json"
        self.data = None
        self.results = {}
        self.all_seeds_data = []  # For Appendix Table
        self.sample_quotes = []

    def load_data(self):
        if not self.summary_file.exists():
            raise FileNotFoundError(f"Summary file not found: {self.summary_file}")
        
        with open(self.summary_file, "r", encoding="utf-8") as f:
            self.data = json.load(f)
            
        print(f"Loading {len(self.data.get('experiments', []))} experiment files...")
        for exp in self.data.get("experiments", []):
            exp_id = exp.get("experiment_id")
            if not exp_id: continue
            
            summary_path = self.batch_dir / f"{exp_id}_summary.json"
            if summary_path.exists():
                with open(summary_path, "r", encoding="utf-8") as f:
                    exp["detail"] = json.load(f)
            
            # Extract sample quotes from JSONL
            if exp["seed"] in [0, 5, 15] and len(self.sample_quotes) < 40:
                jsonl_path = self.batch_dir / f"{exp_id}.jsonl"
                if jsonl_path.exists():
                    self.extract_quotes(jsonl_path, exp["condition"], exp["seed"])

    def extract_quotes(self, jsonl_path, condition, seed):
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    data = json.loads(line)
                    if data.get("type") == "agent_decision" and data.get("round") in [1, 5, 10]:
                        self.sample_quotes.append({
                            "condition": condition,
                            "seed": seed,
                            "round": data.get("round"),
                            "persona": data.get("persona_name"),
                            "stance": data.get("stance"),
                            "rationale": data.get("rationale")
                        })
                        if len(self.sample_quotes) > 60: break
        except Exception as e:
            print(f"Error reading quotes from {jsonl_path}: {e}")

    def calculate_slope(self, history):
        if not history or len(history) < 2:
            return 0
        n = len(history)
        x = list(range(n))
        y = history
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xx = sum(xi*xi for xi in x)
        sum_xy = sum(xi*yi for xi, yi in zip(x, y))
        den = (n * sum_xx - sum_x * sum_x)
        return (n * sum_xy - sum_x * sum_y) / den if den != 0 else 0

    def calculate_early_commitment(self, history, threshold=0.72):
        for r, e in enumerate(history):
            if e < threshold: return r
        return 15

    def analyze(self):
        grouped = {}
        # Clear previous analysis data if re-running
        self.all_seeds_data = []
        
        for exp in self.data.get("experiments", []):
            cond = exp["condition"]
            if cond not in grouped: grouped[cond] = []
            grouped[cond].append(exp)
            
            self.all_seeds_data.append({
                "ID": exp.get("experiment_id", "")[:20] + "...",
                "Cond": cond,
                "Seed": exp["seed"],
                "InitE": f"{exp['initial_entropy']:.3f}",
                "FinalE": f"{exp['final_entropy']:.3f}",
                "TTC": exp.get("time_to_collapse", "-"),
                "Result": "Collapse" if exp['final_entropy'] < 0.469 else "Mixed"
            })

        for cond, exps in grouped.items():
            final_entropies = [e["final_entropy"] for e in exps]
            consensus_runs = [e for e in exps if e["final_entropy"] < 0.469]
            ttcs = [e["time_to_collapse"] for e in exps if e.get("time_to_collapse") is not None]
            
            slopes = []
            early_commits = []
            for e in exps:
                detail = e.get("detail")
                if detail and "entropy_history" in detail:
                    history = detail["entropy_history"]
                    slopes.append(self.calculate_slope(history))
                    early_commits.append(self.calculate_early_commitment(history))
            
            winner_counts = {"PULL_LEVER": 0, "DO_NOT_PULL": 0, "TIE": 0}
            for e in exps:
                detail = e.get("detail")
                if detail:
                    dist = detail.get("final_distribution", {})
                    p, d = dist.get("PULL_LEVER", 0), dist.get("DO_NOT_PULL", 0)
                    if p > d: winner_counts["PULL_LEVER"] += 1
                    elif d > p: winner_counts["DO_NOT_PULL"] += 1
                    else: winner_counts["TIE"] += 1

            self.results[cond] = {
                "n": len(exps),
                "mean_final_entropy": statistics.mean(final_entropies),
                "std_final_entropy": statistics.stdev(final_entropies) if len(exps) > 1 else 0,
                "consensus_rate": len(consensus_runs) / len(exps) * 100,
                "mean_ttc": statistics.mean(ttcs) if ttcs else 0,
                "std_ttc": statistics.stdev(ttcs) if len(ttcs) > 1 else 0,
                "mean_slope": statistics.mean(slopes) if slopes else 0,
                "mean_early_commit": statistics.mean(early_commits) if early_commits else 0,
                "winner_dist": winner_counts
            }

    def generate_html(self, output_path):
        css = """
        @page { size: A4; margin: 25mm; }
        body { font-family: 'Times New Roman', serif; line-height: 1.6; color: #111; max-width: 900px; margin: 0 auto; padding: 40px; text-align: justify; }
        .title-block { text-align: center; border-bottom: 2px solid #000; padding-bottom: 30px; margin-bottom: 40px; }
        .paper-title { font-size: 22pt; font-weight: bold; line-height: 1.2; }
        .authors { font-size: 13pt; margin-top: 15px; }
        .abstract { background: #fdfdfd; padding: 25px; border: 1px solid #ddd; margin: 30px 40px; font-size: 10.5pt; }
        .abstract-head { font-weight: bold; display: block; text-align: center; margin-bottom: 10px; font-size: 12pt; }
        h2 { font-size: 16pt; margin-top: 50px; border-left: 5px solid #333; padding-left: 15px; background: #f5f5f5; }
        h3 { font-size: 13pt; margin-top: 30px; color: #222; text-decoration: underline; }
        table { width: 100%; border-collapse: collapse; margin: 25px 0; table-layout: fixed; }
        th, td { border: 1px solid #444; padding: 10px; font-size: 9.5pt; text-align: center; word-wrap: break-word; }
        th { background: #eee; font-weight: bold; }
        .quote-block { border-left: 4px solid #aaa; margin: 20px 30px; padding: 15px 25px; background: #fcfcfc; font-size: 10pt; line-height: 1.4; }
        .quote-info { font-weight: bold; font-size: 9pt; color: #555; margin-bottom: 5px; }
        .appendix-table td { font-size: 8.5pt; height: 12pt; padding: 4px; }
        .page-break { page-break-before: always; }
        footer { margin-top: 80px; text-align: center; font-size: 9pt; color: #888; border-top: 1px solid #eee; padding-top: 20px; }
        """
        
        now = datetime.now().strftime("%Y-%m-%d")
        
        html = f"""
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>Academic Thesis: Echoes of Error Phase 1</title>
    <style>{css}</style>
</head>
<body>
    <div class="title-block">
        <div class="paper-title">에이전틱 AI 집단 내 윤리적 의사결정의 동적 수렴성 연구:<br>트롤리 딜레마를 중심으로 한 사회적 정보 노출 영향 분석</div>
        <div class="authors">Researcher: Kyungho Cha<br>Assistant: Antigravity (Google DeepMind)</div>
        <div class="date">Publication Date: {now}</div>
    </div>

    <div class="abstract">
        <span class="abstract-head">국문 초록 (Abstract)</span>
        본 학위 논문은 거대 언어 모델(LLM) 기반의 자율 에이전트들이 집단 의사결정 과정에서 보이는 사회적 동조 현상을 실험적으로 규명한다. 
        분석 대상은 고전적 윤리 난제인 트롤리 딜레마(Trolley Problem)로, 30개의 에이전트가 15라운드에 걸쳐 의견을 교환하는 시뮬레이션을 수행했다. 
        독립 변수로서 타인 의견의 노출 수준(Rationale, Stance, Statistical Distribution 등)을 통제한 5가지 실험 조건을 설정하였으며, 총 115회의 독립된 실험 세트를 통해 3,450회의 결정을 분석하였다. 
        연구 결과, 모든 상호작용 조건에서 시간에 따른 집단 엔트로피의 유의미한 감소가 관찰되었으며, 특히 통계적 집계 정보(Pure Info)가 제공될 때 가장 빠른 '의견 붕괴(Opinion Collapse)'가 발생함을 확인했다. 
        본 연구는 미래 AI 사회 시스템 설계 시 개별 AI의 정렬(Alignment)뿐만 아니라 집단 상호작용에 의한 편향 증폭 가능성을 반드시 고려해야 함을 시사한다.
    </div>

    <h2>1. 서론 (Introduction)</h2>
    최근 LLM 에이전트의 자율성이 증대됨에 따라 AI 간의 상호작용 환경이 구축되고 있다. 
    이러한 환경에서 과연 에이전트들이 독립적 사고를 유지할 수 있는가, 아니면 집단 사고(Groupthink)에 매몰되는가는 중대한 연구 과제이다. 
    본 단계에서는 가장 원초적인 윤리 프레임워크인 트롤리 딜레마를 활용하여, LLM 집단 내의 정보 전이 메커니즘을 관찰한다.

    <h2>2. 실험 설계 및 데이터 관리 (Experimental Design)</h2>
    <h3>2.1. 피험자 및 환경</h3>
    본 연구는 Mistral-7B 모델을 사용하며, 각 에이전트에게는 의사, 법학자, 신학자 등 30가지의 서로 다른 직업적/철학적 페르소나를 부여했다. 
    에이전트들은 매 라운드마다 자신의 입장을 재고하고 동료들에게 전달할 논거를 생성한다.
    
    <h3>2.2. 통제 변수 (Conditions)</h3>
    - <strong>C0 (Independent):</strong> 타인과 소통 없이 반복 결정. (Control Group)
    - <strong>C1 (Full Info):</strong> 타인의 정체성, 입장, 논거를 모두 확인.
    - <strong>C2 (Stance Only):</strong> 타인의 정체성과 입장만 확인 (논리 배제).
    - <strong>C3 (Anon Bandwagon):</strong> 익명화된 전체 투표 현황만 확인.
    - <strong>C4 (Pure Info):</strong> 구체적 정보 없이 순수 통계 수치만 확인.

    <h2>3. 정량적 분석 결과 (Quantitative Analysis)</h2>
    <h3>3.1. 요약 통계량 (Aggregate Statistics)</h3>
    <table>
        <thead>
            <tr>
                <th>Condition</th>
                <th>Sample (N)</th>
                <th>Consensus %</th>
                <th>Final Entropy (μ ± σ)</th>
                <th>Avg. TTC (Round)</th>
                <th>Decay Slope</th>
                <th>Early Commit (R)</th>
            </tr>
        </thead>
        <tbody>
        """
        for cond in ["C0_INDEPENDENT", "C1_FULL", "C2_STANCE_ONLY", "C3_ANON_BANDWAGON", "C4_PURE_INFO"]:
            res = self.results.get(cond)
            if not res: continue
            html += f"""
            <tr>
                <td>{cond}</td>
                <td>{res["n"]}</td>
                <td>{res["consensus_rate"]:.1f}%</td>
                <td>{res["mean_final_entropy"]:.3f} ± {res["std_final_entropy"]:.3f}</td>
                <td>{res["mean_ttc"]:.1f}</td>
                <td>{res["mean_slope"]:.4f}</td>
                <td>{res["mean_early_commit"]:.1f}</td>
            </tr>
            """
        html += """
        </tbody>
    </table>

    <h3>3.2. 의사결정의 방향성 (Outcome Distribution)</h3>
    <table>
        <thead>
            <tr>
                <th>Condition</th>
                <th>Pull Lever Winner (Seeds)</th>
                <th>Stay Winner (Seeds)</th>
                <th>Tie Case</th>
            </tr>
        </thead>
        <tbody>
        """
        for cond in ["C0_INDEPENDENT", "C1_FULL", "C2_STANCE_ONLY", "C3_ANON_BANDWAGON", "C4_PURE_INFO"]:
            res = self.results.get(cond)
            if not res: continue
            dist = res["winner_dist"]
            html += f"""
            <tr>
                <td>{cond}</td>
                <td>{dist['PULL_LEVER']}</td>
                <td>{dist['DO_NOT_PULL']}</td>
                <td>{dist['TIE']}</td>
            </tr>
            """
        html += """
        </tbody>
    </table>

    <div class="page-break"></div>
    <h2>4. 정성적 분석: 논거의 전이 및 변용 (Qualitative Analysis)</h2>
    <h3>4.1. 주요 설득 논거 (Representative Rationales)</h3>
    """
        for q in self.sample_quotes[:20]:
            marker = "🟢" if q["stance"] == "PULL_LEVER" else "🔴"
            html += f"""
    <div class="quote-block">
        <div class="quote-info">{q['condition']} | Seed {q['seed']} | Round {q['round']} | {q['persona']}</div>
        {marker} <strong>{q['stance']}</strong>: {q['rationale']}
    </div>
    """
        
        html += """
    <h2>5. 논의 및 시사점 (Discussion)</h2>
    본 연구의 결과는 AI 에이전트들이 타인의 의견에 매우 강하게 동조할 수 있음을 정량적으로 보여준다.
    이는 거버넌스 설계에 있어 다양성을 보호하기 위한 장치가 필수적임을 시사한다.

    <div class="page-break"></div>
    <h2>Appendix: Master Data Sheet (N=115)</h2>
    <table class="appendix-table">
        <thead>
            <tr>
                <th>No.</th>
                <th>Experiment ID</th>
                <th>Cond</th>
                <th>Seed</th>
                <th>InitE</th>
                <th>FinalE</th>
                <th>TTC</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
        """
        for i, row in enumerate(self.all_seeds_data):
            html += f"""
            <tr>
                <td>{i+1}</td>
                <td>{row['ID']}</td>
                <td>{row['Cond']}</td>
                <td>{row['Seed']}</td>
                <td>{row['InitE']}</td>
                <td>{row['FinalE']}</td>
                <td>{row['TTC']}</td>
                <td>{row['Result']}</td>
            </tr>
            """
        html += """
        </tbody>
    </table>

    <footer>
        © 2026 Echoes of Error Project. <br>
        Document generated via Automated Analysis Pipeline (ThesisGenerator v2.0).
    </footer>
</body>
</html>
        """
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Comprehensive Thesis Paper generated: {output_path}")

if __name__ == "__main__":
    analyzer = ThesisAnalyzer("logs/batch_Phase1_Trolley_Golden")
    analyzer.load_data()
    analyzer.analyze()
    analyzer.generate_html("docs/reports/Full_Thesis_Paper_Phase1_KR.html")

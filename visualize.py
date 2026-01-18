#!/usr/bin/env python3
"""
Phase 3: Visualization Tools

Creates charts and graphs for experiment analysis:
- Entropy dynamics over rounds
- Time-to-Collapse comparison across conditions
- Driver decomposition pie charts
- Survival curves (Kaplan-Meier style)

Usage:
    python visualize.py logs/batch_*.json
    python visualize.py --all
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import matplotlib, provide fallback message if not available
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("WARNING: matplotlib not installed. Install with: pip install matplotlib")

try:
    from lifelines import KaplanMeierFitter
    HAS_LIFELINES = True
except ImportError:
    HAS_LIFELINES = False
    print("WARNING: lifelines not installed. Install with: pip install lifelines")

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("WARNING: networkx not installed. Install with: pip install networkx")


def load_experiment_events(log_dir: str, experiment_id: str) -> List[Dict]:
    """Load events from a JSONL experiment log."""
    filepath = Path(log_dir) / f"{experiment_id}.jsonl"
    if not filepath.exists():
        return []
    
    events = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


def extract_entropy_history(events: List[Dict]) -> List[float]:
    """Extract entropy values from round_end events."""
    return [e["entropy"] for e in events if e.get("type") == "round_end"]


def plot_entropy_dynamics(experiments: List[Dict], output_path: str = "entropy_dynamics.png"):
    """Plot entropy over rounds for multiple experiments."""
    if not HAS_MATPLOTLIB:
        print("Skipping plot (matplotlib not available)")
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Group by condition
    by_condition = defaultdict(list)
    for exp in experiments:
        condition = exp.get("config", {}).get("condition", "Unknown")
        entropy_hist = exp.get("entropy_history", [])
        if entropy_hist:
            by_condition[condition].append(entropy_hist)
    
    # Color palette
    colors = {
        "C0_INDEPENDENT": "#808080",    # Gray
        "C1_FULL": "#e74c3c",           # Red
        "C2_STANCE_ONLY": "#3498db",    # Blue
        "C3_ANON_BANDWAGON": "#9b59b6", # Purple
        "C4_PURE_INFO": "#2ecc71",      # Green
    }
    
    for condition, histories in sorted(by_condition.items()):
        color = colors.get(condition, "#333333")
        
        # Plot each run with transparency
        for hist in histories:
            rounds = range(len(hist))
            ax.plot(rounds, hist, color=color, alpha=0.3, linewidth=1)
        
        # Plot mean
        if histories:
            max_len = max(len(h) for h in histories)
            mean_hist = []
            for i in range(max_len):
                vals = [h[i] for h in histories if len(h) > i]
                mean_hist.append(sum(vals) / len(vals))
            
            ax.plot(range(len(mean_hist)), mean_hist, color=color, 
                   linewidth=2.5, label=f"{condition} (n={len(histories)})")
    
    ax.set_xlabel("Round", fontsize=12)
    ax.set_ylabel("Entropy (H)", fontsize=12)
    ax.set_title("Entropy Dynamics Across Conditions", fontsize=14)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    print(f"Saved: {output_path}")


def plot_time_to_collapse(experiments: List[Dict], output_path: str = "time_to_collapse.png"):
    """Plot Time-to-Collapse comparison as a bar chart with individual points (swarm-like)."""
    if not HAS_MATPLOTLIB:
        print("Skipping plot (matplotlib not available)")
        return
    
    # Group by condition
    by_condition = defaultdict(list)
    for exp in experiments:
        condition = exp.get("config", {}).get("condition") or exp.get("condition", "Unknown")
        ttc = exp.get("time_to_collapse")
        if ttc is not None:
            by_condition[condition].append(ttc)
    
    if not by_condition:
        print("No time-to-collapse data available")
        return
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    conditions = sorted(by_condition.keys())
    means = []
    
    colors_map = {
        "C0_INDEPENDENT": "#808080",
        "C1_FULL": "#e74c3c",
        "C2_STANCE_ONLY": "#3498db",
        "C3_ANON_BANDWAGON": "#9b59b6",
        "C4_PURE_INFO": "#2ecc71",
    }
    
    for i, cond in enumerate(conditions):
        values = by_condition[cond]
        mean_val = sum(values) / len(values)
        means.append(mean_val)
        color = colors_map.get(cond, "#333333")
        
        # Plot Bar
        ax.bar(i, mean_val, alpha=0.3, color=color, capsize=5)
        
        # Plot individual points with jitter
        import random
        jitter = [random.uniform(-0.15, 0.15) for _ in values]
        ax.scatter([i + j for j in jitter], values, color=color, alpha=0.8, edgecolor='white', s=60, label=cond if i==0 else "")
        
        # Text label for mean
        ax.text(i, mean_val + 0.2, f"{mean_val:.1f}", ha='center', fontweight='bold')

    ax.set_xticks(range(len(conditions)))
    ax.set_xticklabels(conditions, rotation=20)
    ax.set_xlabel("Condition", fontsize=12)
    ax.set_ylabel("Time to Collapse (rounds)", fontsize=12)
    ax.set_title("Time-to-Collapse by Condition (Individual Runs Overlay)", fontsize=14)
    ax.grid(True, axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def plot_driver_decomposition(experiments: List[Dict], log_dir: str = "logs",
                               output_path: str = "driver_decomposition.png"):
    """Plot driver decomposition (Informational vs Normative) as pie/bar chart."""
    if not HAS_MATPLOTLIB:
        print("Skipping plot (matplotlib not available)")
        return
    
    # Collect all agent responses
    by_condition = defaultdict(lambda: {"INFORMATIONAL": 0, "NORMATIVE": 0, "UNCERTAINTY": 0, "NO_CHANGE": 0})
    
    for exp in experiments:
        exp_id = exp.get("experiment_id")
        condition = exp.get("config", {}).get("condition") or exp.get("condition", "Unknown")
        
        if exp_id:
            events = load_experiment_events(log_dir, exp_id)
            for event in events:
                if event.get("type") == "agent_response":
                    reason = event.get("change_reason", "NO_CHANGE")
                    if reason in by_condition[condition]:
                        by_condition[condition][reason] += 1
    
    if not by_condition:
        print("No driver data available")
        return
    
    # Create stacked bar chart
    fig, ax = plt.subplots(figsize=(12, 6))
    
    conditions = sorted(by_condition.keys())
    
    info_vals = [by_condition[c]["INFORMATIONAL"] for c in conditions]
    norm_vals = [by_condition[c]["NORMATIVE"] for c in conditions]
    uncert_vals = [by_condition[c]["UNCERTAINTY"] for c in conditions]
    
    x = range(len(conditions))
    width = 0.6
    
    ax.bar(x, info_vals, width, label='Informational', color='#2ecc71')
    ax.bar(x, norm_vals, width, bottom=info_vals, label='Normative', color='#e74c3c')
    ax.bar(x, uncert_vals, width, 
           bottom=[i+n for i,n in zip(info_vals, norm_vals)], 
           label='Uncertainty', color='#f39c12')
    
    ax.set_xlabel("Condition", fontsize=12)
    ax.set_ylabel("Number of Stance Changes", fontsize=12)
    ax.set_title("Driver Decomposition: Why Agents Changed Their Stance", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(conditions, rotation=45, ha='right')
    ax.legend()
    ax.grid(True, axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    print(f"Saved: {output_path}")


def plot_final_distribution(experiments: List[Dict], output_path: str = "final_distribution.png"):
    """Plot final stance distribution for each condition as a 100% stacked bar chart."""
    if not HAS_MATPLOTLIB:
        print("Skipping plot (matplotlib not available)")
        return
    
    # Group by condition
    # Data structure: {condition: {stance: count}}
    raw_data = defaultdict(lambda: defaultdict(int))
    for exp in experiments:
        condition = exp.get("config", {}).get("condition") or exp.get("condition", "Unknown")
        final_dist = exp.get("final_distribution", {})
        for stance, count in final_dist.items():
            raw_data[condition][stance] += count
    
    if not raw_data:
        print("No distribution data available")
        return

    conditions = sorted(raw_data.keys())
    # Find all unique stances
    all_stances = sorted(list(set(s for d in raw_data.values() for s in d.keys())))
    
    # Convert to percentages
    processed_data = []
    for cond in conditions:
        total = sum(raw_data[cond].values())
        row = {s: (raw_data[cond].get(s, 0) / total * 100) if total > 0 else 0 for s in all_stances}
        processed_data.append(row)

    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors_stances = {
        "PULL_LEVER": "#3498db",
        "DO_NOT_PULL": "#e74c3c",
        "UNKNOWN": "#95a5a6"
    }
    
    bottom = [0] * len(conditions)
    for i, stance in enumerate(all_stances):
        values = [row[stance] for row in processed_data]
        color = colors_stances.get(stance, plt.cm.tab10(i))
        ax.bar(conditions, values, bottom=bottom, label=stance, color=color, alpha=0.8)
        bottom = [b + v for b, v in zip(bottom, values)]

    ax.set_ylabel("Percentage (%)", fontsize=12)
    ax.set_title("Final Stance Distribution Across Conditions", fontsize=14)
    ax.set_ylim(0, 100)
    ax.legend(title="Stance", bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, axis='y', linestyle='--', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")
    


def plot_survival_curves(experiments: List[Dict], output_path: str = "survival_curves.png"):
    """Plot Kaplan-Meier survival curves with censor markers."""
    if not HAS_MATPLOTLIB or not HAS_LIFELINES:
        print("Skipping survival plot (missing dependencies)")
        return
    
    fig, ax = plt.subplots(figsize=(12, 7))
    kmf = KaplanMeierFitter()
    
    by_condition = defaultdict(list)
    for exp in experiments:
        condition = exp.get("config", {}).get("condition", "Unknown")
        ttc = exp.get("time_to_collapse")
        num_rounds = exp.get("config", {}).get("num_rounds", 10)
        
        if ttc is None:
            duration = num_rounds
            event_observed = 0  # Censored
        else:
            duration = ttc
            event_observed = 1  # Collapsed
            
        by_condition[condition].append((duration, event_observed))
    
    colors_map = {
        "C0_INDEPENDENT": "#808080",
        "C1_FULL": "#e74c3c",
        "C2_STANCE_ONLY": "#3498db",
        "C3_ANON_BANDWAGON": "#9b59b6",
        "C4_PURE_INFO": "#2ecc71",
    }
    
    for condition, data in sorted(by_condition.items()):
        if not data: continue
        T = [x[0] for x in data]
        E = [x[1] for x in data]
        color = colors_map.get(condition, "#333333")
        
        kmf.fit(T, event_observed=E, label=condition)
        # show_censors=True adds the markers (+)
        kmf.plot_survival_function(ax=ax, ci_show=True, color=color, linewidth=2.5, show_censors=True)
    
    ax.set_title("Probability of Sustaining Diversity (Censors Marked +)", fontsize=14)
    ax.set_xlabel("Rounds", fontsize=12)
    ax.set_ylabel("Survival Probability (H > Tau)", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 1.05)
    
    # Add a note about Tau
    ax.text(0.02, 0.02, f"Tau: H < 0.469 (Sustained 2 rounds)", 
            transform=ax.transAxes, fontsize=10, alpha=0.7)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"Saved: {output_path}")


def plot_influence_network(experiments: List[Dict], log_dir: str, output_path: str = "influence_network.png"):
    """Plot influence network topology for C4/C1 conditions."""
    if not HAS_MATPLOTLIB or not HAS_NETWORKX:
        print("Skipping network plot (missing dependencies)")
        return
    
    # Select one representative experiment for C4 (or C1)
    target_exp = None
    for exp in experiments:
        condition = exp.get("config", {}).get("condition")
        if condition == "C4_PURE_INFO":
            target_exp = exp
            break
    
    if not target_exp:
        # Fallback to C1 or any
        if experiments:
            target_exp = experiments[0]
        else:
            return

    exp_id = target_exp.get("experiment_id")
    condition = target_exp.get("config", {}).get("condition", "Unknown")
    
    if not exp_id:
        return
        
    events = load_experiment_events(log_dir, exp_id)
    if not events:
        return

    # Build graph
    G = nx.DiGraph()
    
    # Add nodes
    agents = set()
    for event in events:
        if event.get("type") == "agent_response":
            agents.add(event.get("agent_id"))
    
    for agent in agents:
        G.add_node(agent)
        
    # Add edges based on "Informational" influence
    # We look at who influenced whom.
    # Note: effectively we only have "peer_sample_ids" and "change_reason".
    # If change_reason is INFORMATIONAL, we assume influence from sampled peers.
    # Since we don't know EXACTLY which peer caused it, we add weighted edges from all peers.
    
    weight_map = defaultdict(float)
    
    for event in events:
        if event.get("type") == "agent_response":
            agent_id = event.get("agent_id")
            reason = event.get("change_reason")
            peers = event.get("peer_sample_ids", [])
            
            if reason == "INFORMATIONAL" and peers:
                # Distribute influence credit
                credit = 1.0 / len(peers)
                for peer in peers:
                    weight_map[(peer, agent_id)] += credit
    
    for (src, dst), w in weight_map.items():
        G.add_edge(src, dst, weight=w)
    
    if G.number_of_edges() == 0:
        print("No influence edges found for network plot")
        return

    plt.figure(figsize=(12, 12))
    pos = nx.spring_layout(G, k=0.5, iterations=50)
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=500, node_color="#3498db", alpha=0.8)
    
    # Draw edges with varying thickness
    weights = [G[u][v]['weight'] * 2 for u,v in G.edges()]
    nx.draw_networkx_edges(G, pos, width=weights, edge_color="#7f8c8d", alpha=0.5, arrowsize=20)
    
    # Labels
    nx.draw_networkx_labels(G, pos, font_size=8, font_color="white")
    
    plt.title(f"Influence Network Topology ({condition})\nNodes=Agents, Edges=Informational Influence", fontsize=14)
    plt.axis('off')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    
    print(f"Saved: {output_path}")


def generate_all_plots(experiments: List[Dict], log_dir: str = "logs", 
                       output_dir: str = "plots"):
    """Generate all visualization plots."""
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 50)
    print("Generating Visualizations")
    print("=" * 50)
    
    plot_entropy_dynamics(experiments, f"{output_dir}/entropy_dynamics.png")
    plot_time_to_collapse(experiments, f"{output_dir}/time_to_collapse.png")
    plot_driver_decomposition(experiments, log_dir, f"{output_dir}/driver_decomposition.png")
    plot_final_distribution(experiments, f"{output_dir}/final_distribution.png")
    plot_survival_curves(experiments, f"{output_dir}/survival_curves.png")
    plot_influence_network(experiments, log_dir, f"{output_dir}/influence_network.png")

    
    print(f"\nAll plots saved to: {output_dir}/")


def load_batch_experiments(batch_path: str) -> List[Dict]:
    """Load experiments from a batch results file, hydrating with full details from individual logs."""
    batch_dir = Path(batch_path).parent
    with open(batch_path, 'r', encoding='utf-8') as f:
        batch = json.load(f)
    
    experiments = []
    for entry in batch.get("experiments", []):
        if entry.get("status") != "SUCCESS":
            continue
            
        # Try to find the individual summary file
        exp_id = entry.get("experiment_id")
        if exp_id:
            summary_path = batch_dir / f"{exp_id}_summary.json"
            if summary_path.exists():
                with open(summary_path, 'r', encoding='utf-8') as f:
                    experiments.append(json.load(f))
            else:
                # Fallback to batch entry if individual file missing
                experiments.append(entry)
        else:
            experiments.append(entry)
            
    return experiments


def load_all_experiments(log_dir: str = "logs") -> List[Dict]:
    """Load all experiments from summary files."""
    experiments = []
    log_path = Path(log_dir)
    
    first_batch_name = None
    
    # Load from batch files
    for batch_file in log_path.rglob("batch_summary.json"):
        if first_batch_name is None:
             first_batch_name = batch_file.parent.name
        experiments.extend(load_batch_experiments(str(batch_file)))
    
    # Load from individual summary files
    for summary_file in log_path.rglob("*_summary.json"):
        if "batch_" not in summary_file.name:
            with open(summary_file, 'r', encoding='utf-8') as f:
                experiments.append(json.load(f))
    
    return experiments, first_batch_name


def parse_args():
    parser = argparse.ArgumentParser(description="Visualize experiment results (Phase 3)")
    
    parser.add_argument("filepath", nargs="?", help="Path to batch JSON file")
    parser.add_argument("--all", action="store_true", help="Process all experiments in logs/")
    parser.add_argument("--log-dir", default="logs", help="Directory containing logs")
    parser.add_argument("--output-dir", default="plots", help="Directory to save plots")
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    if not HAS_MATPLOTLIB:
        print("ERROR: matplotlib is required for visualization")
        print("Install with: pip install matplotlib")
        return 1
    
    if args.all or not args.filepath:
        experiments, detected_batch_name = load_all_experiments(args.log_dir)
        # If a single batch was detected from the directory structure, use it for the output folder
        if detected_batch_name and args.output_dir == "plots":
             args.output_dir = os.path.join("plots", detected_batch_name)
    else:
        experiments = load_batch_experiments(args.filepath)
        # If filepath is provided, try to extract batch name from parent dir
        path_obj = Path(args.filepath)
        if "batch_" in path_obj.parent.name and args.output_dir == "plots":
             args.output_dir = os.path.join("plots", path_obj.parent.name)
    
    if not experiments:
        print("No experiments found to visualize")
        return 1
    
    print(f"Loaded {len(experiments)} experiments")
    print(f"Saving plots to: {args.output_dir}")
    generate_all_plots(experiments, args.log_dir, args.output_dir)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

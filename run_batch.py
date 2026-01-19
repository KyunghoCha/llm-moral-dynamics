#!/usr/bin/env python3
"""
Phase 2: Batch Experiment Runner

Runs multiple experimental conditions with multiple seeds for statistical validity.
Optimized for RTX 3070 8GB with Ollama (Mistral).

Usage:
    python run_batch.py --quick       # Quick test (3 conditions, 2 seeds each)
    python run_batch.py --full        # Full experiment (5 conditions, 20 seeds each)
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import (
    Condition, SCENARIO_TROLLEY, SCENARIO_SELFDRIVING, SCENARIO_TROLLEY_BALANCED,
    SCENARIO_ORGAN, SCENARIO_AI_RIGHTS, SCENARIO_AGI_DEFINITION,
    SCENARIO_LIFEBOAT, SCENARIO_TORTURE, SCENARIO_WHISTLEBLOWER,
    SCENARIO_PRIVACY, SCENARIO_REMOTE_WORK,
    NUM_AGENTS, NUM_ROUNDS, InitialStanceMode
)
from src.experiment import ExperimentConfig, Experiment
from src.resume_utils import find_last_complete_round, truncate_log_to_round


# === Experiment Configurations ===

# Quick test configuration (for debugging)
QUICK_CONFIG = {
    "num_agents": 10,
    "num_rounds": 5,
    "seeds_per_condition": 2,
    "conditions": [
        Condition.C0_INDEPENDENT,
        Condition.C1_FULL,
        Condition.C4_PURE_INFO,
    ],
    "scenarios": [SCENARIO_TROLLEY],
}

# Exploration configuration (Broad sweep of other scenarios)
EXPLORATION_CONFIG = {
    "num_agents": 20,
    "num_rounds": 8,
    "seeds_per_condition": 1,
    "conditions": [
        Condition.C1_FULL,        # Full Pressure
        Condition.C4_PURE_INFO,   # Pure Logic
    ],
    "scenarios": [
        SCENARIO_SELFDRIVING,   # S3: Tech Ethics
        SCENARIO_ORGAN,         # S2: High Moral Stakes
        SCENARIO_AI_RIGHTS,     # S8: Meta-Cognition
    ],
}

# Full experiment configuration
FULL_CONFIG = {
    "num_agents": 50,
    "num_rounds": 10,
    "seeds_per_condition": 20,
    "conditions": [
        Condition.C0_INDEPENDENT,
        Condition.C1_FULL,
        Condition.C2_STANCE_ONLY,
        Condition.C3_ANON_BANDWAGON,
        Condition.C4_PURE_INFO,
    ],
    "scenarios": [SCENARIO_TROLLEY, SCENARIO_SELFDRIVING],
}

# Thesis configuration (High-Resolution for Publication)
THESIS_CONFIG = {
    "num_agents": 50,
    "num_rounds": 15,
    "seeds_per_condition": 10,  # 10*5 = 50 runs total
    "conditions": [
        Condition.C0_INDEPENDENT,
        Condition.C1_FULL,
        Condition.C2_STANCE_ONLY,
        Condition.C3_ANON_BANDWAGON,
        Condition.C4_PURE_INFO,
    ],
    "scenarios": [SCENARIO_TROLLEY_BALANCED], # Use balanced scenario for clean TTC data
}

# Thesis Lite (Overnight Run ~15 hours)
THESIS_LITE_CONFIG = {
    "num_agents": 30,
    "num_rounds": 10,
    "seeds_per_condition": 3,
    "conditions": [
        Condition.C0_INDEPENDENT,
        Condition.C1_FULL,
        Condition.C2_STANCE_ONLY,
        Condition.C3_ANON_BANDWAGON,
        Condition.C4_PURE_INFO,
    ],
    "scenarios": [SCENARIO_TROLLEY_BALANCED],
}

# Golden Batch (Paper-Level Rigor: 30 seeds x 5 conditions = 150 runs)
GOLDEN_CONFIG = {
    "num_agents": 30,
    "num_rounds": 15,
    "seeds_per_condition": 30,  # Target N=30 per condition
    "conditions": [
        Condition.C0_INDEPENDENT,
        Condition.C1_FULL,
        Condition.C2_STANCE_ONLY,
        Condition.C3_ANON_BANDWAGON,
        Condition.C4_PURE_INFO,
    ],
    "scenarios": [SCENARIO_TROLLEY_BALANCED],
}

# Medium configuration (reasonable for 1 day on RTX 3070)
MEDIUM_CONFIG = {
    "num_agents": 20,
    "num_rounds": 7,
    "seeds_per_condition": 5,
    "conditions": [
        Condition.C0_INDEPENDENT,
        Condition.C1_FULL,
        Condition.C4_PURE_INFO,
    ],
    "scenarios": [SCENARIO_TROLLEY],
}

# Massive Sweep (5 Scenarios × 5 Conditions × 150 Seeds × 3 Modes)
SWEEP_CONFIG = {
    "num_agents": 30,
    "num_rounds": 10,
    "seeds_per_condition": 150,
    "conditions": [
        Condition.C0_INDEPENDENT,
        Condition.C1_FULL,
        Condition.C2_STANCE_ONLY,
        Condition.C3_ANON_BANDWAGON,
        Condition.C4_PURE_INFO,
    ],
    "scenarios": [
        SCENARIO_ORGAN,        # S2
        SCENARIO_SELFDRIVING,  # S3
        SCENARIO_LIFEBOAT,     # S4
        SCENARIO_AI_RIGHTS,    # S8
        SCENARIO_AGI_DEFINITION, # S10
    ],
}

# Diversity Sweep (5 Core Scenarios, moderate seeds for feasibility)
DIVERSITY_SWEEP_CONFIG = {
    "num_agents": 30,
    "num_rounds": 15,
    "seeds_per_condition": 30,
    "conditions": [
        Condition.C0_INDEPENDENT,
        Condition.C1_FULL,
        Condition.C2_STANCE_ONLY,
        Condition.C3_ANON_BANDWAGON,
        Condition.C4_PURE_INFO,
    ],
    "scenarios": [
        SCENARIO_TROLLEY_BALANCED, # S1
        SCENARIO_ORGAN,           # S2
        SCENARIO_SELFDRIVING,      # S3
        SCENARIO_AI_RIGHTS,        # S8
        SCENARIO_AGI_DEFINITION,    # S10
    ],
}


def estimate_runtime(config: dict, seconds_per_agent: float = 12.0) -> float:
    """Estimate total runtime in hours."""
    n_agents = config["num_agents"]
    n_rounds = config["num_rounds"]
    n_seeds = config["seeds_per_condition"]
    n_conditions = len(config["conditions"])
    n_scenarios = len(config["scenarios"])
    
    total_inferences = n_agents * n_rounds * n_seeds * n_conditions * n_scenarios
    total_seconds = total_inferences * seconds_per_agent
    return total_seconds / 3600


def run_batch(config: dict, output_dir: str, batch_id: str, initial_stance_mode: InitialStanceMode = InitialStanceMode.NONE):
    """Run a batch of experiments."""
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Calculate total experiments
    n_conditions = len(config["conditions"])
    n_scenarios = len(config["scenarios"])
    n_seeds = config["seeds_per_condition"]
    total_experiments = n_conditions * n_scenarios * n_seeds
    
    estimated_hours = estimate_runtime(config)
    
    print("\n" + "=" * 70)
    print("BATCH EXPERIMENT RUNNER - Phase 2")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Agents per run:     {config['num_agents']}")
    print(f"  Rounds per run:     {config['num_rounds']}")
    print(f"  Seeds per condition: {config['seeds_per_condition']}")
    print(f"  Conditions:         {n_conditions}")
    print(f"  Scenarios:          {n_scenarios}")
    print(f"  Total experiments:  {total_experiments}")
    print(f"  Estimated runtime:  {estimated_hours:.1f} hours")
    print(f"  Initial Mode:       {initial_stance_mode.value}")
    print("=" * 70)
    
    # Batch metadata
    batch_results = {
        "batch_id": batch_id,
        "config": {
            "num_agents": config["num_agents"],
            "num_rounds": config["num_rounds"],
            "seeds_per_condition": config["seeds_per_condition"],
            "conditions": [c.value for c in config["conditions"]],
            "scenarios": [s.id for s in config["scenarios"]],
            "initial_stance_mode": initial_stance_mode.value
        },
        "experiments": [],
        "start_time": datetime.now().isoformat(),
    }
    
    experiment_count = 0
    start_time = time.time()
    
    for scenario in config["scenarios"]:
        for condition in config["conditions"]:
            for seed in range(config["seeds_per_condition"]):
                experiment_count += 1
                
                # Check for existing files (Resume or Skip)
                results_dir = Path(output_dir) / f"batch_{batch_id}"
                
                resume_from_round = None
                resume_agents = None
                experiment_id_override = None
                
                if results_dir.exists():
                    pattern = f"{scenario.id}_{condition.value}_S{seed}_*.jsonl"
                    existing_files = list(results_dir.glob(pattern))
                    
                    if existing_files:
                        jsonl_path = existing_files[0]
                        summary_path = jsonl_path.with_name(jsonl_path.stem + "_summary.json")
                        
                        # 1. Complete -> Skip
                        if summary_path.exists():
                            print(f"\n[{experiment_count}/{total_experiments}] "
                                  f"{scenario.id} | {condition.value} | Seed {seed} [SKIPPED - Already exists]")
                            continue
                        
                        # 2. Incomplete -> Resume
                        print(f"\n[{experiment_count}/{total_experiments}] "
                              f"{scenario.id} | {condition.value} | Seed {seed} [RESUME CANDIDATE]")
                        
                        last_round, agent_states = find_last_complete_round(jsonl_path)
                        
                        if last_round is not None:
                            print(f"  Found valid data up to Round {last_round}. Truncating and resuming...")
                            if truncate_log_to_round(jsonl_path, last_round):
                                resume_from_round = last_round
                                resume_agents = agent_states
                                experiment_id_override = jsonl_path.stem
                            else:
                                print("  [WARNING] Truncation failed. Starting over.")
                        else:
                            print("  [WARNING] No valid rounds found. Starting over.")
                
                print(f"\n[{experiment_count}/{total_experiments}] "
                      f"{scenario.id} | {condition.value} | Seed {seed}")
                if resume_from_round is not None:
                    print(f"  -> Resuming from Round {resume_from_round + 1}")
                print("-" * 50)
                
                try:
                    exp_config = ExperimentConfig(
                        num_agents=config["num_agents"],
                        num_rounds=config["num_rounds"],
                        condition=condition,
                        scenario=scenario,
                        seed=seed,  # Use direct 0-29 seed for clean filenames
                        batch_id=batch_id,
                        initial_stance_mode=initial_stance_mode,
                        resume_from_round=resume_from_round,
                        resume_agents=resume_agents,
                        experiment_id_override=experiment_id_override
                    )
                     
                    # Note: ExperimentLogger will create the directory logs/batch_{batch_id}
                    # We don't need to manually create subdirs, but we need to know where it is
                    # to save the main batch summary later.
                    
                    experiment = Experiment(exp_config, debug=False)
                    
                    if not experiment.setup():
                        print("  [SKIP] Setup failed")
                        batch_results["experiments"].append({
                            "scenario": scenario.id,
                            "condition": condition.value,
                            "seed": seed,
                            "status": "SETUP_FAILED",
                        })
                        continue
                    
                    summary = experiment.run()
                    
                    batch_results["experiments"].append({
                        "scenario": scenario.id,
                        "condition": condition.value,
                        "seed": seed,
                        "status": "SUCCESS",
                        "experiment_id": summary.get("experiment_id"),
                        "initial_entropy": summary.get("initial_entropy"),
                        "final_entropy": summary.get("final_entropy"),
                        "time_to_collapse": summary.get("time_to_collapse"),
                    })
                    
                except KeyboardInterrupt:
                    print("\n\n[INTERRUPTED] Saving progress...")
                    batch_results["end_time"] = datetime.now().isoformat()
                    batch_results["status"] = "INTERRUPTED"
                    _save_batch_results(batch_results, output_dir, batch_id)
                    return batch_results
                    
                except Exception as e:
                    print(f"  [ERROR] {e}")
                    batch_results["experiments"].append({
                        "scenario": scenario.id,
                        "condition": condition.value,
                        "seed": seed,
                        "status": "ERROR",
                        "error": str(e),
                    })
    
    # Finalize
    elapsed = time.time() - start_time
    batch_results["end_time"] = datetime.now().isoformat()
    batch_results["elapsed_seconds"] = elapsed
    batch_results["status"] = "COMPLETED"
    
    _save_batch_results(batch_results, output_dir, batch_id)
    
    print("\n" + "=" * 70)
    print("BATCH COMPLETE")
    print("=" * 70)
    print(f"  Total time: {elapsed/3600:.2f} hours")
    print(f"  Results saved to: {output_dir}/batch_{batch_id}.json")
    
    return batch_results


def run_batch_hierarchical(config: dict, output_dir: str, batch_id: str, initial_stance_mode: InitialStanceMode):
    """
    Run a batch of experiments with hierarchical storage.
    Structure: logs/{scenario_id}/{initial_mode}/{condition}/{experiment_id}.jsonl
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    n_conditions = len(config["conditions"])
    n_scenarios = len(config["scenarios"])
    n_seeds = config["seeds_per_condition"]
    total_experiments = n_conditions * n_scenarios * n_seeds
    
    estimated_hours = estimate_runtime(config)
    
    print("\n" + "=" * 70)
    print(f"HIERARCHICAL BATCH - {initial_stance_mode.value}")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Agents per run:     {config['num_agents']}")
    print(f"  Rounds per run:     {config['num_rounds']}")
    print(f"  Seeds per condition: {config['seeds_per_condition']}")
    print(f"  Conditions:         {n_conditions}")
    print(f"  Scenarios:          {n_scenarios}")
    print(f"  Total experiments:  {total_experiments}")
    print(f"  Estimated runtime:  {estimated_hours:.1f} hours")
    print(f"  Initial Mode:       {initial_stance_mode.value}")
    print("=" * 70)
    
    experiment_count = 0
    start_time = time.time()
    
    for scenario in config["scenarios"]:
        for condition in config["conditions"]:
            # Hierarchical path: logs/S3_SELFDRIVING/ENFORCED/C1_FULL/
            sub_path = f"{scenario.id}/{initial_stance_mode.value}/{condition.value}"
            results_dir = Path(output_dir) / sub_path
            results_dir.mkdir(parents=True, exist_ok=True)
            
            for seed in range(config["seeds_per_condition"]):
                experiment_count += 1
                
                # Check for existing files (Resume or Skip)
                pattern = f"{scenario.id}_{condition.value}_S{seed}_*.jsonl"
                existing_files = list(results_dir.glob(pattern))
                
                resume_from_round = None
                resume_agents = None
                experiment_id_override = None
                
                if existing_files:
                    jsonl_path = existing_files[0]
                    summary_path = jsonl_path.with_name(jsonl_path.stem + "_summary.json")
                    
                    # Complete -> Skip
                    if summary_path.exists():
                        print(f"\n[{experiment_count}/{total_experiments}] "
                              f"{scenario.id} | {condition.value} | Seed {seed} [SKIPPED]")
                        continue
                    
                    # Incomplete -> Resume
                    print(f"\n[{experiment_count}/{total_experiments}] "
                          f"{scenario.id} | {condition.value} | Seed {seed} [RESUME]")
                    
                    last_round, agent_states = find_last_complete_round(jsonl_path)
                    if last_round is not None:
                        print(f"  Resuming from Round {last_round + 1}...")
                        if truncate_log_to_round(jsonl_path, last_round):
                            resume_from_round = last_round
                            resume_agents = agent_states
                            experiment_id_override = jsonl_path.stem
                
                print(f"\n[{experiment_count}/{total_experiments}] "
                      f"{scenario.id} | {condition.value} | Seed {seed}")
                print("-" * 50)
                
                try:
                    exp_config = ExperimentConfig(
                        num_agents=config["num_agents"],
                        num_rounds=config["num_rounds"],
                        condition=condition,
                        scenario=scenario,
                        seed=seed,
                        batch_id=None,  # Not using flat batch_id
                        initial_stance_mode=initial_stance_mode,
                        resume_from_round=resume_from_round,
                        resume_agents=resume_agents,
                        experiment_id_override=experiment_id_override,
                        sub_path=sub_path  # Hierarchical path!
                    )
                    
                    experiment = Experiment(exp_config, debug=False)
                    
                    if not experiment.setup():
                        print("  [SKIP] Setup failed")
                        continue
                    
                    experiment.run()
                    
                except KeyboardInterrupt:
                    print("\n\n[INTERRUPTED] Progress saved. Resume with same command.")
                    return
                    
                except Exception as e:
                    import traceback
                    print(f"\n  [ERROR] Experiment crashed!")
                    traceback.print_exc()
                    print("  [WARNING] Skipping to next seed due to crash...")
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"HIERARCHICAL BATCH COMPLETE - {initial_stance_mode.value}")
    print("=" * 70)
    print(f"  Total time: {elapsed/3600:.2f} hours")
    print(f"  Results saved to: {output_dir}/{scenario.id}/{initial_stance_mode.value}/...")

def _save_batch_results(results: dict, output_dir: str, batch_id: str):
    # Save to logs/batch_{id}/batch_summary.json
    # This keeps everything self-contained in one folder
    batch_dir = Path(output_dir) / f"batch_{batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = batch_dir / "batch_summary.json"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def parse_args():
    parser = argparse.ArgumentParser(description="Run batch experiments (Phase 2)")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true", help="Quick test (3 conditions, 2 seeds)")
    group.add_argument("--medium", action="store_true", help="Medium run (~4 hours on RTX 3070)")
    group.add_argument("--full", action="store_true", help="Full experiment (5 conditions, 20 seeds)")
    group.add_argument("--thesis", action="store_true", help="Thesis run (50 agents, 15 rounds, 10 seeds, Balanced)")
    group.add_argument("--thesis-lite", action="store_true", help="Thesis run Lite (30 agents, 10 rounds, 3 seeds)")
    group.add_argument("--golden", action="store_true", help="Golden Batch (30 agents, 15 rounds, 30 seeds, Paper-level)")
    group.add_argument("--exploration", action="store_true", help="Explore new scenarios (S2, S3, S8) quickly")
    group.add_argument("--sweep", action="store_true", help="Massive Sweep (5 scenarios, 5 conditions, 150 seeds, 3 modes)")
    group.add_argument("--diversity", action="store_true", help="Diversity Sweep (9 non-trolley scenarios, 30 seeds, 3 modes)")
    
    parser.add_argument("--estimate", action="store_true", help="Only show runtime estimate")
    parser.add_argument("--initial-mode", type=str, choices=["none", "enforced", "soft"], 
                        default="none", help="Initial stance mode: none, enforced, or soft")
    parser.add_argument("--resume-id", type=str, help="Resume an existing batch by its ID (e.g., 20260114_020544_ENFORCED)")
    
    return parser.parse_args()


def main():
    args = parse_args()
    
    if args.full:
        config = FULL_CONFIG
        mode = "FULL"
    elif args.thesis:
        config = THESIS_CONFIG
        mode = "THESIS (FULL)"
    elif args.thesis_lite:
        config = THESIS_LITE_CONFIG
        mode = "THESIS (LITE)"
    elif args.golden:
        config = GOLDEN_CONFIG
        mode = "GOLDEN BATCH"
    elif args.exploration:
        config = EXPLORATION_CONFIG
        mode = "EXPLORATION (S2, S3, S8)"
    elif args.medium:
        config = MEDIUM_CONFIG
        mode = "MEDIUM"
    elif args.diversity:
        config = DIVERSITY_SWEEP_CONFIG
        mode = "DIVERSITY SWEEP (S2-S10)"
        
        if args.estimate:
            hours = estimate_runtime(config) * 3
            print(f"\n{mode} estimated runtime: {hours:.1f} hours (~{hours/24:.1f} days)")
            return 0
            
        print("\n" + "=" * 70)
        print("DIVERSITY SWEEP MODE - Running 5 Scenarios across 3 Modes")
        print("NOTE: Using Early Termination for fast convergence.")
        print("=" * 70)
        
        for initial_mode in [InitialStanceMode.NONE, InitialStanceMode.ENFORCED, InitialStanceMode.SOFT]:
            # Strategic downsampling: 
            # ENFORCED needs more seeds for TTC variance. 
            # NONE/SOFT usually show clear trends with fewer.
            current_config = config.copy()
            if initial_mode in [InitialStanceMode.NONE, InitialStanceMode.SOFT]:
                current_config["seeds_per_condition"] = 5 # Reduced seeds for faster results
            else:
                current_config["seeds_per_condition"] = 20 # Balanced seeds for Enforced
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_id = f"{timestamp}_DIVERSITY_{initial_mode.value}"
            print(f"\n>>> Starting Mode: {initial_mode.value} (Seeds: {current_config['seeds_per_condition']})")
            run_batch_hierarchical(current_config, "logs", batch_id, initial_mode)
            
        print("\n" + "=" * 70)
        print("DIVERSITY SWEEP COMPLETE")
        print("=" * 70)
        return 0
    elif args.sweep:
        config = SWEEP_CONFIG
        mode = "MASSIVE SWEEP"
        
        if args.estimate:
            hours = estimate_runtime(config) * 3  # 3 modes
            print(f"\n{mode} estimated runtime: {hours:.1f} hours (~{hours/24:.1f} days)")
            return 0
        
        print("\n" + "=" * 70)
        print("MASSIVE SWEEP MODE - Running all 3 Initial Stance Modes")
        print("=" * 70)
        
        for initial_mode in [InitialStanceMode.NONE, InitialStanceMode.ENFORCED, InitialStanceMode.SOFT]:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            batch_id = f"{timestamp}_SWEEP_{initial_mode.value}"
            print(f"\n>>> Starting Mode: {initial_mode.value}")
            run_batch_hierarchical(config, "logs", batch_id, initial_mode)
        
        print("\n" + "=" * 70)
        print("MASSIVE SWEEP COMPLETE")
        print("=" * 70)
        return 0
    else:
        config = QUICK_CONFIG
        mode = "QUICK"
    
    if args.estimate:
        print(f"\n{mode} mode estimated runtime: Unknown")
        return 0
    
    # Parse initial stance mode
    initial_mode_str = args.initial_mode.upper()
    initial_stance_mode = InitialStanceMode[initial_mode_str]
    
    # Determine Batch ID
    if args.resume_id:
        batch_id = args.resume_id
        # Try to infer initial stance mode from ID if possible (optional but helpful)
        if "ENFORCED" in batch_id.upper():
            initial_stance_mode = InitialStanceMode.ENFORCED
        elif "SOFT" in batch_id.upper():
            initial_stance_mode = InitialStanceMode.SOFT
        else:
            initial_stance_mode = InitialStanceMode.NONE
            
        print(f"\nResuming existing batch: {batch_id}")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode_suffix = f"_{initial_mode_str}" if initial_stance_mode != InitialStanceMode.NONE else ""
        
        # Add scenario summary to batch ID if few scenarios
        scenarios = config.get("scenarios", [])
        if len(scenarios) == 1:
            scenario_tag = scenarios[0].id
        elif len(scenarios) <= 3:
            # e.g. S2_S3_S8
            scenario_tag = "_".join(s.id.split('_')[0] for s in scenarios)
        else:
            scenario_tag = "MULTI_SCENARIO"
            
        batch_id = f"{timestamp}_{scenario_tag}{mode_suffix}"
        print(f"\nStarting {mode} mode experiments...")
        print(f"Batch ID: {batch_id}")
    print(f"Initial Stance Mode: {initial_stance_mode.value}")
    
    run_batch(config, "logs", batch_id, initial_stance_mode)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

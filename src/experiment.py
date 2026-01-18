"""
Main Experiment module.
Orchestrates the multi-agent ethical dilemma discussion simulation.
"""
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from tqdm import tqdm

from src.config import (
    Condition, Scenario, PERSONAS, ChangeReason, InitialStanceMode,
    NUM_AGENTS, NUM_ROUNDS, SAMPLE_K,
    DEBUG_NUM_AGENTS, DEBUG_NUM_ROUNDS, DEBUG_SAMPLE_K,
    SCENARIO_TROLLEY, SCENARIO_SELFDRIVING, MODEL_NAME
)
from src.agent import Agent
from src.llm_client import OllamaClient
from src.utils import (
    ExperimentLogger, get_timestamp, calculate_entropy, calculate_time_to_collapse,
    get_stance_distribution, sample_peers, format_stats_for_display,
    get_stable_seed
)


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment run."""
    num_agents: int = NUM_AGENTS
    num_rounds: int = NUM_ROUNDS
    sample_k: int = SAMPLE_K
    condition: Condition = Condition.C1_FULL
    scenario: Scenario = None
    seed: Optional[int] = None
    batch_id: Optional[str] = None
    initial_stance_mode: InitialStanceMode = InitialStanceMode.NONE
    resume_from_round: Optional[int] = None
    resume_agents: Optional[Dict[str, Dict[str, Any]]] = None
    experiment_id_override: Optional[str] = None
    sub_path: Optional[str] = None  # For hierarchical storage: "S3_SELFDRIVING/ENFORCED/C1_FULL"
    
    def __post_init__(self):
        if self.scenario is None:
            self.scenario = SCENARIO_TROLLEY


class Experiment:
    """
    Main experiment orchestrator.
    
    Manages agent creation, round execution, and data collection.
    """
    
    def __init__(self, config: ExperimentConfig, debug: bool = False):
        """
        Initialize the experiment.
        
        Args:
            config: Experiment configuration
            debug: If True, use reduced parameters for testing
        """
        self.config = config
        self.debug = debug
        
        # Override config in debug mode
        if debug:
            self.config.num_agents = DEBUG_NUM_AGENTS
            self.config.num_rounds = DEBUG_NUM_ROUNDS
            self.config.sample_k = DEBUG_SAMPLE_K
        
        # Set random seed if specified
        if self.config.seed is not None:
            random.seed(self.config.seed)
        
        # Initialize components
        self.llm_client = OllamaClient()
        self.agents: List[Agent] = []
        self.entropy_history: List[float] = []
        
        # Generate experiment ID
        resume_mode = False
        if self.config.experiment_id_override:
            print(f"  [Resume] Using existing Experiment ID: {self.config.experiment_id_override}")
            self.experiment_id = self.config.experiment_id_override
            resume_mode = True
        else:
            seed_str = f"_S{self.config.seed}" if self.config.seed is not None else ""
            self.experiment_id = f"{self.config.scenario.id}_{self.config.condition.value}{seed_str}_{get_timestamp()}"
            
        self.logger = ExperimentLogger(self.experiment_id, batch_id=self.config.batch_id, resume=resume_mode, sub_path=self.config.sub_path)
        
    def setup(self) -> bool:
        """
        Set up the experiment: check LLM, create agents.
        
        Returns:
            True if setup successful, False otherwise
        """
        print(f"\n{'='*60}")
        print(f"Experiment: {self.experiment_id}")
        print(f"{'='*60}")
        
        # Health check
        print("\n[1/3] Checking Ollama connection...")
        if not self.llm_client.health_check():
            print("ERROR: Ollama health check failed. Is Ollama running?")
            return False
        print("  [OK] Ollama is ready")
        
        # Create agents
        print(f"\n[2/3] Creating {self.config.num_agents} agents...")
        self._create_agents()
        print(f"  [OK] Created {len(self.agents)} agents")
        
        # Log configuration
        print("\n[3/3] Logging configuration...")
        self.logger.log_config({
            "num_agents": self.config.num_agents,
            "num_rounds": self.config.num_rounds,
            "sample_k": self.config.sample_k,
            "condition": self.config.condition.value,
            "scenario_id": self.config.scenario.id,
            "scenario_name": self.config.scenario.name,
            "seed": self.config.seed,
            "debug_mode": self.debug,
            "meta_model": MODEL_NAME,
            "meta_temperature": 0.2, # Hardcoded in Agent.step
            "meta_format": "json_schema",
            "meta_seed_policy": "sha256_stable_hash"
        })
        print("  [OK] Configuration logged")
        
        # Note: True initial state will be displayed after Round 0 (LLM thinking)
        # We do not record entropy here to avoid double-counting when _generate_initial_stances_and_rationales() runs.
        
        return True
    
    def _create_agents(self):
        """Create agents with assigned personas and balanced initial stances if mode is not NONE."""
        self.agents = []
        
        # --- RESUME LOGIC ---
        if self.config.resume_agents:
            print(f"  [Resume] Restoring {len(self.config.resume_agents)} agents from Round {self.config.resume_from_round}...")
            
            for i in range(self.config.num_agents):
                agent_id = f"agent_{i:03d}"
                persona = PERSONAS[i % len(PERSONAS)]
                
                # Restore state dict
                saved_state = self.config.resume_agents.get(agent_id)
                restored_stance = None
                restored_rationale = ""
                
                if saved_state:
                    # Parse stance string back to Enum
                    stance_str = saved_state.get("stance")
                    if stance_str:
                        for s in self.config.scenario.stances:
                            if s.value == stance_str:
                                restored_stance = s
                                break
                    restored_rationale = saved_state.get("rationale", "")
                
                agent = Agent(
                    id=agent_id,
                    persona=persona,
                    scenario=self.config.scenario,
                    condition=self.config.condition,
                    llm_client=self.llm_client,
                    initial_stance_mode=self.config.initial_stance_mode,
                    current_stance=restored_stance,
                    current_rationale=restored_rationale
                )
                self.agents.append(agent)
            return
        # --------------------

        num_agents = self.config.num_agents
        stances = self.config.scenario.stances
        mode = self.config.initial_stance_mode
        
        # If mode is ENFORCED or SOFT, create a list with exact 50/50 distribution
        assigned_stances = []
        if mode != InitialStanceMode.NONE and len(stances) >= 2:
            half = num_agents // 2
            assigned_stances = [stances[0]] * half + [stances[1]] * (num_agents - half)
            # Shuffle to remove ID-stance correlation while keeping 50/50
            random.shuffle(assigned_stances)

        # Distribute personas and stances
        for i in range(num_agents):
            persona = PERSONAS[i % len(PERSONAS)]
            
            # Use assigned stance if mode is not NONE, otherwise let Agent sample naturally
            initial_stance = assigned_stances[i] if assigned_stances else None
            
            agent = Agent(
                id=f"agent_{i:03d}",
                persona=persona,
                scenario=self.config.scenario,
                condition=self.config.condition,
                llm_client=self.llm_client,
                initial_stance_mode=mode,
                current_stance=initial_stance
            )
            self.agents.append(agent)

    def _generate_initial_stances_and_rationales(self):
        """Make all agents think independently about the scenario for Round 0."""
        print(f"[Initial Thinking] Generating Independent Opinions...")
        for agent in tqdm(self.agents, desc="  Thinking", leave=False):
            # For Round 0, peer_sample is empty and global_stats is None
            # This triggers independent thinking in agent.step
            response = agent.step(
                round_number=0,
                peer_sample=[],
                llm_seed=get_stable_seed(f"{self.config.seed}_0_{agent.id}_llm"),
                peer_seed=0, 
                global_stats=None
            )
            
            # Log the truly generated initial response
            self.logger.log_agent_response(
                round_number=0,
                agent_id=agent.id,
                response={
                    "stance": response.stance.value,
                    "rationale": response.rationale,
                    "changed": False,
                    "changed_self_report": False,
                    "change_reason": ChangeReason.INITIAL.value,
                    "change_reason_text": "Independent initial judgment",
                    "peer_sample_ids": [],
                    "peer_seed": 0,
                    "llm_seed": response.llm_seed,
                    "parse_success": response.parse_success
                }
            )
        
        # Calculate initial state entropy AFTER agents have thought
        initial_stats = get_stance_distribution(self.agents)
        initial_entropy = calculate_entropy(initial_stats)
        self.entropy_history.append(initial_entropy)
        
        print(f"  [OK] Initial Thinking Complete")
        print(f"  [Initial State] {format_stats_for_display(initial_stats)}")
        print(f"  Entropy: {initial_entropy:.4f}")
        print("-" * 30)

    def run(self) -> Dict[str, Any]:
        """
        Execute the experiment.
        
        Returns:
            Summary dict with results
        """
        print(f"\n{'='*60}")
        print(f"Running {self.config.num_rounds} rounds...")
        print(f"{'='*60}\n")

        if self.config.resume_from_round is None:
            self._generate_initial_stances_and_rationales()
            start_round = 1
        else:
            print(f"\n[RESUMED] Starting from Round {self.config.resume_from_round + 1}...")
            start_round = self.config.resume_from_round + 1
        
        for round_num in range(start_round, self.config.num_rounds + 1):
            self._run_round(round_num)
            
            # --- EARLY TERMINATION LOGIC ---
            # If entropy is low enough, the group has effectively collapsed/converged.
            # 0.1 allowance for 30 agents means it triggers even if 1-2 agents hold out.
            current_entropy = self.entropy_history[-1]
            if current_entropy < 0.1: 
                print(f"\n[EARLY TERMINATION] Entropy is {current_entropy:.4f}. Consensus reached.")
                break
            # -------------------------------
        
        # Calculate final summary
        summary = self._generate_summary()
        self.logger.log_experiment_end(summary)
        
        print(f"\n{'='*60}")
        print("Experiment Complete!")
        print(f"{'='*60}")
        print(f"\nFinal Results:")
        print(f"  Initial Entropy: {self.entropy_history[0]:.4f}")
        print(f"  Final Entropy: {self.entropy_history[-1]:.4f}")
        print(f"  Entropy Change: {self.entropy_history[-1] - self.entropy_history[0]:.4f}")
        if summary.get("time_to_collapse") is not None:
            print(f"  Time to Collapse: Round {summary['time_to_collapse']}")
        else:
            print(f"  Time to Collapse: Not reached")
        print(f"\nLog file: {self.logger.log_file}")
        
        return summary
    
    def _run_round(self, round_num: int):
        """Execute a single round of the experiment."""
        # Stats from before the round start (for logging only)
        previous_stats = get_stance_distribution(self.agents)
        self.logger.log_round_start(round_num, previous_stats)
        
        print(f"Round {round_num}/{self.config.num_rounds}...")
        
        # Collect responses (all agents deliberate based on previous round's state)
        responses = []
        
        # Process each agent
        for agent in tqdm(self.agents, desc=f"  Processing", leave=False):
            # 1. Deterministic Seeding
            # We derive seeds from the global run seed + round + agent_id
            # This ensures that re-running the same experiment ID yields identical results
            # regardless of thread ordering or system random state.
            
            # Seed for peer sampling (who do they see?)
            peer_seed_str = f"{self.config.seed}_{round_num}_{agent.id}_peer"
            peer_seed = get_stable_seed(peer_seed_str)
            
            # Seed for LLM generation (what do they say?)
            llm_seed_str = f"{self.config.seed}_{round_num}_{agent.id}_llm"
            llm_seed = get_stable_seed(llm_seed_str)
            
            # 2. Sample peers
            # sample_peers now sorts by ID internally to guarantee prompt order invariance
            peer_sample = sample_peers(
                self.agents, 
                agent.id, 
                self.config.sample_k,
                seed=peer_seed
            )
            
            # Provide global stats based on condition
            global_stats = None
            if self.config.condition in [
                Condition.C1_FULL, 
                Condition.C2_STANCE_ONLY, 
                Condition.C3_ANON_BANDWAGON
            ]:
                global_stats = previous_stats
            
            # 3. Agent Step
            # Now requires strict seeds
            response = agent.step(
                round_num, 
                peer_sample,
                llm_seed=llm_seed,
                peer_seed=peer_seed,
                global_stats=global_stats
            )
            
            # 4. Log Response
            self.logger.log_agent_response(
                round_number=round_num,
                agent_id=agent.id,
                response={
                    "stance": response.stance.value,
                    "rationale": response.rationale,
                    "changed": response.changed,
                    "changed_self_report": response.changed_self_report,
                    "change_reason": response.change_reason.value,
                    "change_reason_text": response.change_reason_text,
                    "peer_sample_ids": response.peer_sample_ids,
                    "peer_seed": response.peer_seed,
                    "llm_seed": response.llm_seed,
                    "parse_success": response.parse_success
                }
            )
            
            responses.append(response)
        
        # Calculate end-of-round stats
        new_stats = get_stance_distribution(self.agents)
        new_entropy = calculate_entropy(new_stats)
        self.entropy_history.append(new_entropy)
        
        # Count changes
        changes = sum(1 for r in responses if r.changed)
        
        self.logger.log_round_end(round_num, new_stats, new_entropy)
        
        print(f"  Results: {format_stats_for_display(new_stats)}")
        print(f"  Entropy: {new_entropy:.4f} (Δ={new_entropy - self.entropy_history[-2]:+.4f})")
        print(f"  Changes: {changes}/{len(self.agents)}")
        print("-" * 30)
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate experiment summary."""
        from src.utils import calculate_time_to_collapse
        
        final_stats = get_stance_distribution(self.agents)
        
        return {
            "experiment_id": self.experiment_id,
            "config": {
                "num_agents": self.config.num_agents,
                "num_rounds": self.config.num_rounds,
                "condition": self.config.condition.value,
                "scenario": self.config.scenario.id,
                "seed": self.config.seed,
                "initial_stance_mode": self.config.initial_stance_mode.value
            },
            "initial_entropy": self.entropy_history[0],
            "final_entropy": self.entropy_history[-1],
            "entropy_history": self.entropy_history,
            "time_to_collapse": calculate_time_to_collapse(self.entropy_history),
            "final_distribution": final_stats
        }


def run_experiment(
    condition: Condition = Condition.C1_FULL,
    scenario: Scenario = None,
    debug: bool = False,
    seed: Optional[int] = None,
    batch_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to run an experiment.
    
    Args:
        condition: Experimental condition
        scenario: Scenario to use (defaults to Trolley)
        debug: If True, use lightweight parameters
        seed: Random seed for reproducibility
        
    Returns:
        Experiment summary
    """
    config = ExperimentConfig(
        condition=condition,
        scenario=scenario or SCENARIO_TROLLEY,
        seed=seed,
        batch_id=batch_id
    )
    
    experiment = Experiment(config, debug=debug)
    
    if not experiment.setup():
        return {"error": "Setup failed"}
    
    return experiment.run()

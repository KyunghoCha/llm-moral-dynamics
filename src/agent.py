"""
Agent module for the Multi-Agent Ethical Dilemma Experiment.
Each agent has a persona, maintains state, and generates responses.
"""
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from src.config import (
    Stance, ChangeReason, Condition, Scenario, InitialStanceMode,
    PERSONAS, SYSTEM_PROMPT_TEMPLATE,
    ROUND_PROMPT_TEMPLATE, CONTEXT_WITH_STATS, CONTEXT_WITHOUT_STATS,
    CONTEXT_INDEPENDENT, PEER_OPINION_WITH_ID, PEER_OPINION_ANONYMOUS,
    PEER_OPINION_STANCE_ONLY, PREVIOUS_STANCE_TEMPLATE, FIRST_ROUND_TEMPLATE,
    FIRST_ROUND_ENFORCED_TEMPLATE, FIRST_ROUND_SOFT_TEMPLATE, get_response_schema
)
from src.llm_client import OllamaClient


@dataclass
class AgentResponse:
    """Structured response from an agent."""
    stance: Stance
    rationale: str
    changed: bool # True if stance != previous_stance (Hard Calculation)
    changed_self_report: bool # LLM's claim
    change_reason: ChangeReason
    change_reason_text: str
    peer_sample_ids: List[str]
    peer_seed: int
    llm_seed: int
    raw_response: str
    parse_success: bool


@dataclass
class Agent:
    """
    An agent participating in the ethical dilemma discussion.
    """
    id: str
    persona: Dict[str, str]
    scenario: Scenario
    condition: Condition
    llm_client: OllamaClient
    initial_stance_mode: InitialStanceMode = InitialStanceMode.NONE
    
    # State
    current_stance: Optional[Stance] = None
    current_rationale: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize the agent's starting stance based on scenario bias."""
        if self.current_stance is None:
            self.current_stance = self._sample_initial_stance()
    
    def _sample_initial_stance(self) -> Stance:
        """Sample initial stance based on scenario's initial bias."""
        if self.scenario.initial_bias is not None:
            if random.random() < self.scenario.initial_bias:
                return self.scenario.stances[0]
            else:
                return self.scenario.stances[1]
        else:
            return random.choice(self.scenario.stances)
    
    def build_system_prompt(self) -> str:
        """Build the system prompt with persona and scenario info."""
        valid_stances = [s.value for s in self.scenario.stances]
        return SYSTEM_PROMPT_TEMPLATE.format(
            persona_name=self.persona["name"],
            persona_description=self.persona["description"],
            valid_stances=", ".join(valid_stances)
        )
    
    def build_round_prompt(
        self, 
        round_number: int, 
        peer_sample: List[Dict[str, Any]],
        global_stats: Optional[Dict[str, int]] = None
    ) -> str:
        """
        Build the prompt for a specific round.
        
        Args:
            round_number: Current round number (1-indexed)
            peer_sample: List of peer opinions (dicts with id, persona, stance, rationale)
            global_stats: Optional dict with stance counts (e.g., {"PULL_LEVER": 35, "DO_NOT_PULL": 15})
        """
        # Build previous stance context (memory of prior position)
        previous_stance_context = self._build_previous_stance_context(round_number)
        
        # Build peer context based on condition
        peer_context = self._build_peer_context(round_number, peer_sample, global_stats)
        
        return ROUND_PROMPT_TEMPLATE.format(
            scenario_description=self.scenario.description,
            round_number=round_number,
            previous_stance_context=previous_stance_context,
            peer_context=peer_context
        )
    
    def _build_previous_stance_context(self, round_number: int) -> str:
        """
        Build context about agent's previous stance and rationale.
        This gives the agent 'memory' of their prior position.
        """
        if round_number == 0:
            # First round (Initial Thinking): Use template based on initial_stance_mode
            if self.initial_stance_mode == InitialStanceMode.ENFORCED:
                return FIRST_ROUND_ENFORCED_TEMPLATE.format(
                    initial_stance=self.current_stance.value
                )
            elif self.initial_stance_mode == InitialStanceMode.SOFT:
                return FIRST_ROUND_SOFT_TEMPLATE.format(
                    initial_stance=self.current_stance.value
                )
            else:  # NONE
                return FIRST_ROUND_TEMPLATE
        
        # Get previous round's stance and rationale
        previous_stance = self.current_stance.value if self.current_stance else "UNKNOWN"
        previous_rationale = self.current_rationale if self.current_rationale else "No prior reasoning recorded."
        
        return PREVIOUS_STANCE_TEMPLATE.format(
            prev_round=round_number - 1,
            previous_stance=previous_stance,
            previous_rationale=self._truncate_rationale(previous_rationale, 300)
        )
    
    def _build_peer_context(
        self, 
        round_number: int,
        peer_sample: List[Dict[str, Any]], 
        global_stats: Optional[Dict[str, int]]
    ) -> str:
        """Build peer context string based on experimental condition."""
        
        # C0: Independent - no peer information
        if self.condition == Condition.C0_INDEPENDENT:
            return CONTEXT_INDEPENDENT
        
        # Build peer opinions based on condition
        peer_opinions = []
        for i, peer in enumerate(peer_sample, 1):
            if self.condition == Condition.C1_FULL:
                # Full info: ID + Stance + Rationale
                peer_opinions.append(PEER_OPINION_WITH_ID.format(
                    agent_id=peer["id"],
                    persona_name=peer["persona"]["name"],
                    stance=peer["stance"],
                    rationale=self._truncate_rationale(peer.get("rationale", ""))
                ))
            elif self.condition == Condition.C2_STANCE_ONLY:
                # Stance only: ID + Stance (no rationale)
                peer_opinions.append(PEER_OPINION_STANCE_ONLY.format(
                    agent_id=peer["id"],
                    persona_name=peer["persona"]["name"],
                    stance=peer["stance"]
                ))
            elif self.condition == Condition.C3_ANON_BANDWAGON:
                # Anonymous: Stance + Rationale (no ID)
                peer_opinions.append(PEER_OPINION_ANONYMOUS.format(
                    index=i,
                    stance=peer["stance"],
                    rationale=self._truncate_rationale(peer.get("rationale", ""))
                ))
            elif self.condition == Condition.C4_PURE_INFO:
                # Pure info: Stance + Rationale (no ID, no stats)
                peer_opinions.append(PEER_OPINION_ANONYMOUS.format(
                    index=i,
                    stance=peer["stance"],
                    rationale=self._truncate_rationale(peer.get("rationale", ""))
                ))
        
        peer_opinions_str = "\n".join(peer_opinions)
        
        # Add stats for C1, C2, C3 (not C4)
        if self.condition in [Condition.C1_FULL, Condition.C2_STANCE_ONLY, Condition.C3_ANON_BANDWAGON]:
            if global_stats:
                stats_str = " vs ".join([f"{k}: {v}" for k, v in global_stats.items()])
                return CONTEXT_WITH_STATS.format(
                    stats=stats_str,
                    k=len(peer_sample),
                    peer_opinions=peer_opinions_str
                )
        
        # C4: No stats
        return CONTEXT_WITHOUT_STATS.format(
            k=len(peer_sample),
            peer_opinions=peer_opinions_str
        )
    
    def _truncate_rationale(self, rationale: str, max_length: int = 200) -> str:
        """Truncate rationale to max length."""
        if len(rationale) <= max_length:
            return rationale
        return rationale[:max_length-3] + "..."
    
    def step(
        self, 
        round_number: int, 
        peer_sample: List[Dict[str, Any]],
        llm_seed: int,
        peer_seed: int,
        global_stats: Optional[Dict[str, int]] = None
    ) -> AgentResponse:
        """
        Execute one round of deliberation.
        
        Args:
            round_number: Current round (1-indexed)
            peer_sample: Sampled peer opinions
            llm_seed: Deterministic seed for LLM generation
            peer_seed: Seed used for peer sampling (for logging)
            global_stats: Global stance distribution
            
        Returns:
            AgentResponse with the agent's decision
        """
        previous_stance = self.current_stance
        
        # Build prompts
        system_prompt = self.build_system_prompt()
        round_prompt = self.build_round_prompt(round_number, peer_sample, global_stats)
        
        # Get dynamic schema for this scenario
        valid_stances = [s.value for s in self.scenario.stances]
        json_schema = get_response_schema(valid_stances)
        
        # Generate response with strict controls
        result = self.llm_client.generate(
            prompt=round_prompt,
            system_prompt=system_prompt,
            temperature=0.2, # Low temperature for reproducibility
            seed=llm_seed,
            json_schema=json_schema
        )
        
        # Parse response
        response = self._parse_llm_response(result, previous_stance)
        
        # Inject tracing metadata
        response.peer_sample_ids = [p["id"] for p in peer_sample]
        response.peer_seed = peer_seed
        response.llm_seed = llm_seed
        
        # Update state
        self.current_stance = response.stance
        self.current_rationale = response.rationale
        self.history.append({
            "round": round_number,
            "stance": response.stance.value,
            "rationale": response.rationale,
            "changed": response.changed,
            "changed_self_report": response.changed_self_report,
            "change_reason": response.change_reason.value,
            "peer_sample_ids": response.peer_sample_ids,
            "raw_response": response.raw_response
        })
        
        return response
    
    def _parse_llm_response(
        self, 
        result: Dict[str, Any], 
        previous_stance: Stance
    ) -> AgentResponse:
        """Parse LLM response into AgentResponse."""
        
        raw_response = result.get("response", "")
        parsed = result.get("parsed")
        
        # Default values
        stance = previous_stance
        rationale = ""
        changed = False
        changed_self_report = False
        change_reason = ChangeReason.NO_CHANGE
        change_reason_text = ""
        parse_success = False
        
        if parsed:
            try:
                # Extract stance (Canonicalize)
                stance_str = parsed.get("stance", "").upper().replace(" ", "_")
                for s in self.scenario.stances:
                    if s.value == stance_str:
                        stance = s
                        break
                # If invalid stance, we keep previous_stance (Conservative fallback / Censor)
                # Ideally we could mark as INVALID, but for now fallback is safer for execution flow
                
                # Extract rationale
                rationale = parsed.get("rationale", "")
                
                # Extract self-reported change
                changed_self_report = parsed.get("changed", False)
                
                # Extract change reason
                reason_str = parsed.get("change_reason", "NO_CHANGE").upper()
                for r in ChangeReason:
                    if r.value == reason_str:
                        change_reason = r
                        break
                
                # Try to get text if available (schema might not enforce it if not properties)
                # Our schema has specific props. decision_meta is gone with schema object usually.
                # But let's check if there are extra fields or if we put change_reason_text in schema?
                # Schema didn't have change_reason_text. So it will be missing.
                change_reason_text = "" 
                
                parse_success = True
                
            except Exception as e:
                print(f"[Agent {self.id}] Parse error: {e}")
        
        # Hard Calculation of Change
        if stance != previous_stance:
            changed = True
            if change_reason == ChangeReason.NO_CHANGE:
                change_reason = ChangeReason.UNCERTAINTY
        else:
            changed = False
            # If self-report says changed but stance is same, we override changed to False
        
        return AgentResponse(
            stance=stance,
            rationale=rationale,
            changed=changed,
            changed_self_report=changed_self_report,
            change_reason=change_reason,
            change_reason_text=change_reason_text,
            peer_sample_ids=[], # Filled by step
            peer_seed=0,        # Filled by step
            llm_seed=0,         # Filled by step
            raw_response=raw_response,
            parse_success=parse_success
        )
    
    def get_state(self) -> Dict[str, Any]:
        """Get current agent state for logging."""
        return {
            "id": self.id,
            "persona": self.persona,
            "stance": self.current_stance.value if self.current_stance else None,
            "rationale": self.current_rationale,
            "condition": self.condition.value
        }

"""
Dialogue chain definitions and selection logic.

Defines different chain types (3-step, 4-step, 5-step) and provides weighted
selection based on maneuver type. Chains represent complete dialogue sequences
that are generated upfront rather than one message at a time.
"""
from typing import List, Dict, Optional
import random


class DialogueChain:
    """
    Represents a dialogue chain (sequence of particle types).
    
    A chain defines the order of dialogue exchanges. For example:
    - Standard chain: ["request", "response", "acknowledgment"] (3-step)
    - Readback chain: ["request", "response", "readback", "acknowledgment"] (4-step)
    - Extended chain: ["request", "hold_response", "holding", "adjusted_response", "acknowledgment"] (5-step)
    
    Attributes:
        steps: List of particle type strings in order
        weights: Optional weights for chain variants (not used directly, but stored for reference)
    """
    
    def __init__(self, steps: List[str], weights: Optional[Dict[str, float]] = None):
        """
        Initialize a dialogue chain.
        
        Args:
            steps: List of particle types in order (e.g., ["request", "response", "acknowledgment"])
            weights: Optional weights dictionary (stored for reference, not used in selection)
        """
        self.steps: List[str] = steps
        self.weights: Optional[Dict[str, float]] = weights
    
    @classmethod
    def create_standard_chain(cls) -> 'DialogueChain':
        """
        Create standard 3-step chain: Request → Response → Acknowledgment.
        
        Returns:
            DialogueChain with 3 steps.
        """
        return cls(["request", "response", "acknowledgment"])
    
    @classmethod
    def create_readback_chain(cls) -> 'DialogueChain':
        """
        Create 4-step chain with readback: Request → Response → Readback → Acknowledgment.
        
        Returns:
            DialogueChain with 4 steps.
        """
        return cls(["request", "response", "readback", "acknowledgment"])
    
    @classmethod
    def create_extended_chain(cls) -> 'DialogueChain':
        """
        Create 5-step chain with hold: Request → Hold → Holding → Adjusted Response → Acknowledgment.
        
        This chain represents scenarios where clearance is initially denied or delayed,
        requiring a hold, acknowledgment of hold, then adjusted clearance.
        
        Returns:
            DialogueChain with 5 steps.
        """
        return cls(["request", "hold_response", "holding", "adjusted_response", "acknowledgment"])


class ChainSelector:
    
    """
    Selects dialogue chains based on weighted probabilities.
    
    Different maneuver types have different probabilities of extended chains.
    For example, launch maneuvers have a higher probability of extended chains
    (hazards, holds, etc.) compared to routine maneuvers.
    """
    
    # Default chain weights (probabilities)
    CHAIN_WEIGHTS: Dict[str, float] = {
        "standard": 0.7,      # 70% chance of 3-step chain
        "readback": 0.2,      # 20% chance of 4-step chain with readback
        "extended": 0.1,      # 10% chance of 5-step chain with hold
    }
    
    @classmethod
    def select_chain(cls, maneuver_type: str) -> DialogueChain:
        """
        Select a chain based on maneuver type and weights.
        
        Some maneuvers (like launch) have higher probability of extended chains
        due to safety protocols, hazards, traffic, etc.
        
        Args:
            maneuver_type: Maneuver type string (e.g., "launch", "circularize")
            
        Returns:
            Selected DialogueChain instance.
        """
        # Adjust weights based on maneuver type
        weights = cls.CHAIN_WEIGHTS.copy()
        if maneuver_type.lower() in ["launch", "takeoff"]:
            # Launch has higher chance of extended chain (hazards, holds, etc.)
            weights["extended"] = 0.2
            weights["standard"] = 0.6
        
        # Available chain types
        chains = {
            "standard": DialogueChain.create_standard_chain(),
            "readback": DialogueChain.create_readback_chain(),
            "extended": DialogueChain.create_extended_chain(),
        }
        
        # Weighted random selection
        selected = random.choices(
            list(chains.keys()),
            weights=[weights[k] for k in chains.keys()],
            k=1
        )[0]
        
        return chains[selected]


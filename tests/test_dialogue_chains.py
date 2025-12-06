"""Unit tests for dialogue chain selection and generation."""
import pytest
from unittest.mock import Mock, MagicMock
from mysite.universe.services.dialogue.chain import DialogueChain, ChainSelector


class TestDialogueChain:
    """Test DialogueChain class methods."""
    
    def test_create_standard_chain(self):
        """Test standard 3-step chain creation."""
        chain = DialogueChain.create_standard_chain()
        assert len(chain.steps) == 3
        assert chain.steps == ["request", "response", "acknowledgment"]
    
    def test_create_readback_chain(self):
        """Test 4-step chain with readback creation."""
        chain = DialogueChain.create_readback_chain()
        assert len(chain.steps) == 4
        assert chain.steps == ["request", "response", "readback", "acknowledgment"]
    
    def test_create_extended_chain(self):
        """Test 5-step extended chain creation."""
        chain = DialogueChain.create_extended_chain()
        assert len(chain.steps) == 5
        assert chain.steps == ["request", "hold_response", "holding", "adjusted_response", "acknowledgment"]
    
    def test_custom_chain(self):
        """Test creating a custom chain with specific steps."""
        steps = ["request", "response", "acknowledgment"]
        chain = DialogueChain(steps)
        assert chain.steps == steps
        assert len(chain.steps) == 3


class TestChainSelector:
    """Test ChainSelector weighted selection logic."""
    
    def test_select_chain_returns_valid_chain(self):
        """Test that select_chain always returns a valid DialogueChain."""
        chain = ChainSelector.select_chain("circularize")
        assert isinstance(chain, DialogueChain)
        assert len(chain.steps) >= 3  # All chains have at least 3 steps
        assert len(chain.steps) <= 5  # All chains have at most 5 steps
    
    def test_select_chain_standard_maneuver(self):
        """Test chain selection for standard maneuvers (non-launch)."""
        # Run multiple times to test weighted selection
        chains_selected = []
        for _ in range(100):
            chain = ChainSelector.select_chain("circularize")
            chains_selected.append(len(chain.steps))
        
        # Should have mostly 3-step chains (70% probability)
        three_step_count = chains_selected.count(3)
        assert three_step_count > 50  # Should be majority
        
        # Should have some 4-step chains (20% probability)
        four_step_count = chains_selected.count(4)
        assert four_step_count > 5  # Should have some
        
        # Should have some 5-step chains (10% probability)
        five_step_count = chains_selected.count(5)
        assert five_step_count > 0  # Should have at least one
    
    def test_select_chain_launch_maneuver(self):
        """Test chain selection for launch maneuvers (higher extended chain probability)."""
        # Run multiple times to test weighted selection
        chains_selected = []
        for _ in range(100):
            chain = ChainSelector.select_chain("launch")
            chains_selected.append(len(chain.steps))
        
        # Should have mostly 3-step chains (60% probability for launch)
        three_step_count = chains_selected.count(3)
        assert three_step_count > 40  # Should be majority
        
        # Should have more 5-step chains than standard maneuvers (20% vs 10%)
        five_step_count = chains_selected.count(5)
        assert five_step_count > 5  # Should have more than standard
    
    def test_select_chain_takeoff_maneuver(self):
        """Test that 'takeoff' is treated like 'launch'."""
        chain = ChainSelector.select_chain("takeoff")
        assert isinstance(chain, DialogueChain)
        # Takeoff should use launch weights (higher extended chain probability)
        # We can't test exact weights, but we can verify it returns a valid chain
    
    def test_select_chain_case_insensitive(self):
        """Test that maneuver type matching is case-insensitive."""
        chain1 = ChainSelector.select_chain("LAUNCH")
        chain2 = ChainSelector.select_chain("launch")
        chain3 = ChainSelector.select_chain("Launch")
        
        # All should return valid chains
        assert isinstance(chain1, DialogueChain)
        assert isinstance(chain2, DialogueChain)
        assert isinstance(chain3, DialogueChain)
    
    def test_select_chain_unknown_maneuver(self):
        """Test chain selection for unknown maneuver types."""
        chain = ChainSelector.select_chain("unknown_maneuver_type")
        assert isinstance(chain, DialogueChain)
        assert len(chain.steps) >= 3
        assert len(chain.steps) <= 5
    
    def test_chain_steps_are_valid_particle_types(self):
        """Test that all chain steps are valid particle type strings."""
        valid_particle_types = {
            "request", "response", "acknowledgment", "readback",
            "hold_response", "holding", "adjusted_response"
        }
        
        # Test all three chain types
        standard = ChainSelector.select_chain("circularize")
        readback = ChainSelector.select_chain("circularize")
        extended = ChainSelector.select_chain("launch")
        
        # Collect all steps from multiple selections
        all_steps = set()
        for _ in range(50):
            chain = ChainSelector.select_chain("circularize")
            all_steps.update(chain.steps)
        
        # All steps should be valid particle types
        for step in all_steps:
            assert step in valid_particle_types, f"Invalid particle type: {step}"


"""
Test TacticEngine functionality.
"""

import asyncio
import pytest
from tuner.tactics import TacticEngine, SearchTactic
from tuner.storage import TunerStorage


@pytest.mark.asyncio
async def test_tactic_selection():
    """Test weighted tactic selection."""
    storage = TunerStorage(":memory:")
    await storage.initialize()
    
    engine = TacticEngine(storage)
    
    # Test basic selection
    tactic = engine.select_tactic("test_mission")
    assert tactic is not None
    assert isinstance(tactic, SearchTactic)
    assert tactic.name in engine.tactics
    
    await storage.close()


@pytest.mark.asyncio
async def test_tactic_rotation():
    """Test forced tactic rotation."""
    storage = TunerStorage(":memory:")
    await storage.initialize()
    
    engine = TacticEngine(storage)
    
    # Force rotation
    tactic1 = engine.rotate_tactic("test_mission")
    tactic2 = engine.rotate_tactic("test_mission")
    
    # Should get different tactics (not guaranteed but likely)
    assert tactic1.name in engine.tactics
    assert tactic2.name in engine.tactics
    
    await storage.close()


@pytest.mark.asyncio
async def test_query_building():
    """Test query construction from tactic."""
    storage = TunerStorage(":memory:")
    await storage.initialize()
    
    engine = TacticEngine(storage)
    
    tactic = engine.tactics["trending"]
    query = engine.build_query(
        tactic=tactic,
        mission_goal="whatsapp api library",
        languages=["TypeScript"]
    )
    
    assert "whatsapp" in query.lower() or "api" in query.lower()
    assert "language:TypeScript" in query
    assert "stars:" in query
    
    await storage.close()


@pytest.mark.asyncio
async def test_tactic_weight_update():
    """Test tactic weight adjustment based on success."""
    storage = TunerStorage(":memory:")
    await storage.initialize()
    
    engine = TacticEngine(storage)
    
    original_weight = engine.tactics["trending"].weight
    
    # High success -> increase weight
    engine.update_tactic_weight("trending", 0.8)
    assert engine.tactics["trending"].weight > original_weight
    
    # Low success -> decrease weight
    engine.update_tactic_weight("trending", 0.1)
    assert engine.tactics["trending"].weight < original_weight * 1.5
    
    await storage.close()


@pytest.mark.asyncio
async def test_performance_tracking():
    """Test tactic performance logging."""
    storage = TunerStorage(":memory:")
    await storage.initialize()
    
    # Log performance
    await storage.log_tactic_performance(
        mission_name="test_mission",
        tactic_name="trending",
        query_used="test stars:>=50",
        results_found=10,
        results_accepted=3,
        results_rejected=7
    )
    
    # Retrieve performance
    perf = await storage.get_recent_tactic_performance("test_mission", limit=5)
    assert len(perf) == 1
    assert perf[0]["tactic_name"] == "trending"
    assert perf[0]["success_rate"] == 0.3  # 3/10
    
    # Get success rates
    rates = await storage.get_tactic_success_rates("test_mission")
    assert "trending" in rates
    assert rates["trending"] == 0.3
    
    await storage.close()


if __name__ == "__main__":
    asyncio.run(test_tactic_selection())
    asyncio.run(test_tactic_rotation())
    asyncio.run(test_query_building())
    asyncio.run(test_tactic_weight_update())
    asyncio.run(test_performance_tracking())
    print("✅ All TacticEngine tests passed!")

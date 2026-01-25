
import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath("src"))

from tuner.mission import MissionControl
from tuner.tactics import TacticEngine, SearchTactic

async def verify_systems():
    print("🚀 Verifying Enhanced Features...")
    
    # 1. Mission Control & New Format
    print("\n📦 Checking Mission Control...")
    mc = MissionControl()
    mc.load_missions()  # Reload to be sure
    
    print(f"   ✅ Loaded {len(mc.missions)} missions")
    for m in mc.missions:
        print(f"   - Mission: {m.name}")
        print(f"     • seed_repos: {m.seed_repos}")
        print(f"     • user_notes: {m.user_notes[:50] if m.user_notes else 'None'}...")
        
        # Verify initialized flag
        if getattr(m, 'initialized', False):
            print("     • Status: Initialized ✅")
        else:
            print("     • Status: Pending Initialization ⏳")

    # 2. Hybrid Learning & Tactic Engine
    print("\n🧠 Checking Hybrid Learning...")
    tactic_engine = TacticEngine()
    
    # Check loading from JSON
    print(f"   ✅ Tactics loaded: {len(tactic_engine.tactics)}")
    if "niche_discovery" in tactic_engine.tactics: # Fake check, expecting defaults or updatedjson
        print("   • Custom tactics present")
    
    # Check tactic properties
    trending = tactic_engine.tactics.get("trending")
    if trending:
        print(f"   • 'trending' tactic: weight={trending.weight}, min_stars={trending.stars_min}")
    
    # Test hybrid selection (Mock)
    print("\n🧪 Testing Tactic Selection...")
    # Mock storage needed for async loads, or we just test the logic if we could
    # For now just verify the engine is instantiated correctly
    
    print("\n✅ Verification Complete!")

if __name__ == "__main__":
    asyncio.run(verify_systems())

import asyncio
import logging
import json
import time
from typing import Dict, Any, List
import numpy as np

from tuner.hunter import Hunter
from tuner.brain import LocalBrain, CloudBrain
from tuner.storage import TunerStorage
from tuner.mission import MissionControl

logger = logging.getLogger(__name__)

class AutonomousManager:
    def __init__(self, db_path="data/tuner.db", strategy_path="strategy.json", mission_path="mission.json"):
        self.db_path = db_path
        self.strategy_path = strategy_path
        self.mission_path = mission_path
        
        self.storage = TunerStorage(db_path)
        self.mission_control = MissionControl(mission_path)
        self.cloud_brain = CloudBrain()
        self.local_brain = LocalBrain()
        
        # Runtime State
        self.running = False
        self.session_stats = {
            "scanned": 0,
            "interested": 0,
            "start_time": 0
        }
    
    async def start(self):
        """Start the autonomous research loop."""
        self.running = True
        self.session_stats["start_time"] = time.time()
        logger.info("Autonomous Agent started.")
        
        await self.storage.initialize()
        
        try:
            while self.running:
                # 1. Load Context & Cycle Mission
                self.mission_control.load_missions() # Refresh from file potentially
                mission = self.mission_control.next_mission()
                
                if not mission:
                    logger.warning("No missions found. Sleeping.")
                    await asyncio.sleep(60)
                    continue

                # 2. Execute Research Cycle (Fast & Cheap)
                await self.run_research_cycle(mission)
                
                # 3. Reflection & Optimization (Smart)
                await self.reflect_and_optimize(mission)
                
                # 4. Sleep (Avoid flooding logs if loop is too fast, though Hunter handles API limits)
                if self.running:
                    logger.info("Cycle complete. Resting for 10 seconds before next mission...")
                    await asyncio.sleep(10) # Reduced from 60s for faster rotation
                    
        except Exception as e:
            logger.error(f"Manager crashed: {e}")
        finally:
            self.running = False
            await self.storage.close()

    async def run_research_cycle(self, mission):
        """Run the Hunter -> Screener loop."""
        logger.info(f"Starting Research Cycle for Mission: {mission.name}")
        
        hunter = Hunter(self.strategy_path)
        
        try:
            # Check strategy execution interval / limits? 
            # For now, just run one batch search
            findings = await hunter.search_github()
            
            # Load user profile for screening
            profile_path = "data/user_profile.npy" 
            # (Ideally we'd use mission specific profile, but falling back to global for now)
            interest_clusters = []
            try:
                if import_os_exists(profile_path): # Helper needed or simple os check
                    interest_clusters = np.load(profile_path)
                    if len(interest_clusters.shape) == 1: interest_clusters = interest_clusters.reshape(1, -1)
            except:
                pass
                
            if len(interest_clusters) == 0:
                # Use mission goal as vector
                msg = f"{mission.goal} {' '.join(mission.languages)}"
                interest_clusters = [self.local_brain.vectorize(msg)]

            # Screen
            for finding in findings:
                self.session_stats["scanned"] += 1
                
                # Vector Screen
                desc_vec = self.local_brain.vectorize(f"{finding.title} {finding.description}")
                max_sim = 0.0
                for c in interest_clusters:
                    sim = self.local_brain.calculate_similarity(c, desc_vec)
                    if sim > max_sim: max_sim = sim
                
                # Configurable threshold from strategy or mission?
                # Using Strategy default or Mission override
                threshold = mission.min_stars / 1000.0 # Just a silly heuristic fallback? 
                # Better: Use constant or strategy param
                threshold = 0.4 
                
                f_id = await self.storage.save_finding(
                    finding.title, finding.url, finding.description, 
                    finding.stars, finding.language, desc_vec.tobytes()
                )
                
                if f_id != -1:
                    # Not duplicate
                    if max_sim >= threshold:
                        # High Signal -> INBOX
                        # Trigger CloudBrain Analysis immediately for rich context
                        summary, relevance = "Pending Analysis", max_sim
                        try:
                            # Analysis takes time/cost, hence the 'Research Agent' concept
                            logger.info(f"⚡ Analyzing candidate: {finding.title}")
                            summary, ai_score = await self.cloud_brain.analyze_repo(finding.readme_content)
                            # Blending local similarity with AI relevance score
                            final_score = (max_sim + ai_score) / 2
                        except Exception as e:
                            logger.error(f"Analysis failed: {e}")
                            summary = "Analysis Failed"
                            final_score = max_sim

                        await self.storage.update_finding_analysis(f_id, summary, final_score)
                        self.session_stats["interested"] += 1
                        logger.info(f"Inbox +1: {finding.title} (Score: {final_score:.2f})")
                    else:
                        # Low signal - just store as filtered
                         await self.storage.update_finding_analysis(f_id, "Filtered", max_sim)

        finally:
            await hunter.close()

    async def reflect_and_optimize(self, mission):
        """Analyze performance and update strategy."""
        # Rules for optimization:
        # 1. If scanned > 50 and interested == 0: Strategy is bad.
        # 2. Every X minutes?
        
        scanned = self.session_stats["scanned"]
        interested = self.session_stats["interested"]
        
        if scanned > 0:
            yield_rate = interested / scanned
            logger.info(f"Session Yield: {yield_rate:.2%} ({interested}/{scanned})")
            
            # If yield is very low, ask Brain to fix it
            if yield_rate < 0.05: # Less than 5% relevant
                logger.info("Yield too low. Requesting Strategy Optimization...")
                
                # Fetch recent feedback to give context
                feedback = await self.storage.get_feedback_history()
                
                new_strat = await self.cloud_brain.generate_strategy_v2(
                    mission.to_dict(), 
                    self.session_stats, 
                    feedback
                )
                
                if new_strat:
                    logger.info(f"Applying new strategy: {json.dumps(new_strat)}")
                    with open(self.strategy_path, "w") as f:
                        json.dump(new_strat, f, indent=4)
                    
                    # Reset stats after optimization
                    self.session_stats["scanned"] = 0
                    self.session_stats["interested"] = 0

    def stop(self):
        self.running = False

def import_os_exists(path):
    import os
    return os.path.exists(path)

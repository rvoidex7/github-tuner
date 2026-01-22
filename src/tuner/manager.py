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
from tuner.analytics import AnalyticsEngine
from tuner.tactics import TacticEngine

logger = logging.getLogger(__name__)


class AdaptiveThresholds:
    """
    Dynamic threshold management.
    Automatically adjusts thresholds based on performance.
    """
    
    def __init__(self, storage: TunerStorage):
        self.storage = storage
        self.defaults = {
            "similarity_threshold": 0.25,
            "ai_analysis_threshold": 0.4,
        }
        self._cache: Dict[str, Dict[str, float]] = {}
    
    async def get_threshold(self, mission_name: str, key: str) -> float:
        """Return dynamic threshold per mission."""
        # Check cache
        if mission_name in self._cache and key in self._cache[mission_name]:
            return self._cache[mission_name][key]
        
        # Calculate from performance data
        try:
            success_rates = await self.storage.get_tactic_success_rates(mission_name)
            if success_rates:
                avg_success = sum(success_rates.values()) / len(success_rates)
                
                # Lower threshold on low success, raise on high success
                if key == "similarity_threshold":
                    # If success is low, let more repos through
                    adjusted = self.defaults[key] * (0.6 + 0.8 * (1 - avg_success))
                    return max(0.1, min(0.5, adjusted))
        except:
            pass
        
        return self.defaults.get(key, 0.25)
    
    async def adjust_threshold(self, mission_name: str, key: str, direction: str):
        """Adjust threshold (up/down)."""
        current = await self.get_threshold(mission_name, key)
        
        if direction == "down":
            new_val = max(0.1, current * 0.85)
        else:
            new_val = min(0.6, current * 1.15)
        
        if mission_name not in self._cache:
            self._cache[mission_name] = {}
        self._cache[mission_name][key] = new_val
        
        logger.info(f"📊 Adjusted {key} for {mission_name}: {current:.2f} → {new_val:.2f}")


class AutonomousManager:
    def __init__(self, db_path="data/tuner.db", strategy_path="strategy.json", mission_path="mission.json"):
        self.db_path = db_path
        self.strategy_path = strategy_path
        self.mission_path = mission_path
        
        self.storage = TunerStorage(db_path)
        self.mission_control = MissionControl(mission_path)
        self.cloud_brain = CloudBrain()
        self.local_brain = LocalBrain()
        self.analytics = AnalyticsEngine(db_path)
        self.tactic_engine = TacticEngine(self.storage)
        self.thresholds = AdaptiveThresholds(self.storage)
        
        # Runtime State
        self.running = False
        self.session_stats = {
            "scanned": 0,
            "interested": 0,
            "start_time": 0
        }
        self._cycle_count = 0
        self._ai_optimization_interval = 50  # Her 50 döngüde bir AI kullan
    
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
        """Run the Hunter -> Screener loop with TacticEngine."""
        logger.info(f"🎯 Starting Research Cycle for Mission: {mission.name}")
        
        hunter = Hunter(self.strategy_path)
        
        # Load tactic performance data
        perf_data = await self.storage.get_tactic_success_rates(mission.name)
        
        # Select tactic (weighted random based on performance)
        tactic = self.tactic_engine.select_tactic(mission.name, perf_data)
        
        # Dinamik eşik al
        threshold = await self.thresholds.get_threshold(mission.name, "similarity_threshold")
        
        logger.info(f"📊 Using threshold: {threshold:.2f} for {mission.name}")
        
        results_found = 0
        results_accepted = 0
        results_rejected = 0
        query_used = ""
        
        try:
            # Search with tactic
            findings, query_used = await hunter.search_with_tactic(
                mission_goal=mission.goal,
                languages=mission.languages,
                tactic=tactic,
                tactic_engine=self.tactic_engine
            )
            
            results_found = len(findings)
            
            # Load user profile for screening
            profile_path = "data/user_profile.npy" 
            interest_clusters = []
            try:
                if import_os_exists(profile_path):
                    interest_clusters = np.load(profile_path)
                    if len(interest_clusters.shape) == 1: 
                        interest_clusters = interest_clusters.reshape(1, -1)
            except:
                pass
                
            if len(interest_clusters) == 0:
                # Use mission goal as vector
                msg = f"{mission.goal} {' '.join(mission.languages)}"
                interest_clusters = [self.local_brain.vectorize(msg)]

            # Screen findings
            for finding in findings:
                self.session_stats["scanned"] += 1
                
                # Vector similarity check
                desc_vec = self.local_brain.vectorize(f"{finding.title} {finding.description}")
                max_sim = 0.0
                for c in interest_clusters:
                    sim = self.local_brain.calculate_similarity(c, desc_vec)
                    if sim > max_sim: max_sim = sim
                
                # Save to DB
                f_id = await self.storage.save_finding(
                    finding.title, finding.url, finding.description, 
                    finding.stars, finding.language, desc_vec.tobytes()
                )
                
                if f_id != -1:  # Not duplicate
                    if max_sim >= threshold:
                        # High signal -> Analyze with AI (minimal usage)
                        summary, relevance = "Auto-Accepted", max_sim
                        
                        # AI analizi sadece yüksek belirsizlik durumunda
                        if 0.3 <= max_sim <= 0.5:  # Belirsiz alan
                            try:
                                logger.info(f"🧠 AI analyzing uncertain case: {finding.title}")
                                summary, ai_score = await self.cloud_brain.analyze_repo(finding.readme_content)
                                final_score = (max_sim + ai_score) / 2
                            except Exception as e:
                                logger.error(f"AI analysis failed: {e}")
                                final_score = max_sim
                        else:
                            final_score = max_sim
                        
                        await self.storage.update_finding_analysis(f_id, summary, final_score)
                        self.session_stats["interested"] += 1
                        results_accepted += 1
                        logger.info(f"✅ Inbox +1: {finding.title} (Score: {final_score:.2f})")
                    else:
                        # Low signal - filtered
                        await self.storage.update_finding_analysis(f_id, "Filtered", max_sim)
                        results_rejected += 1

        finally:
            # Log tactic performance
            await self.storage.log_tactic_performance(
                mission_name=mission.name,
                tactic_name=tactic.name,
                query_used=query_used,
                results_found=results_found,
                results_accepted=results_accepted,
                results_rejected=results_rejected
            )
            
            # Update tactic weight based on success
            if results_found > 0:
                success_rate = results_accepted / results_found
                self.tactic_engine.update_tactic_weight(tactic.name, success_rate)
            
            await hunter.close()

    async def reflect_and_optimize(self, mission):
        """
        Analyze performance and autonomously optimize.
        AI kullanımı minimal - sadece kritik durumlarda.
        """
        self._cycle_count += 1
        scanned = self.session_stats["scanned"]
        interested = self.session_stats["interested"]
        
        if scanned > 0:
            yield_rate = interested / scanned
            logger.info(f"📈 Session Yield: {yield_rate:.2%} ({interested}/{scanned})")
            
            # Son 10 döngünün performansını al
            recent_perf = await self.storage.get_recent_tactic_performance(mission.name, limit=10)
            
            if len(recent_perf) >= 3:
                # Son 3 döngünün ortalama başarısı
                recent_success = sum(p['success_rate'] for p in recent_perf[:3]) / 3
                
                logger.info(f"📊 Recent 3 cycles avg success: {recent_success:.2%}")
                
                # OTONOM TAKTİK DEĞİŞİMİ (AI kullanmadan)
                if recent_success < 0.1:  # %10'dan az başarı
                    logger.info("⚡ AUTO-ROTATING TACTIC (low success rate)")
                    self.tactic_engine.rotate_tactic(mission.name)
                    
                elif recent_success < 0.2:  # %20'dan az - eşiği düşür
                    logger.info("📉 LOWERING THRESHOLD (moderate success)")
                    await self.thresholds.adjust_threshold(mission.name, "similarity_threshold", "down")
                
                elif recent_success > 0.6:  # %60'dan fazla - eşiği yükselt
                    logger.info("📈 RAISING THRESHOLD (high success - being selective)")
                    await self.thresholds.adjust_threshold(mission.name, "similarity_threshold", "up")
            
            # AI OPTIMIZATION - sadece periyodik veya kritik durumlarda
            should_use_ai = self._should_use_ai_optimization(mission.name, recent_perf)
            
            if should_use_ai:
                logger.info("🧠 TRIGGERING AI OPTIMIZATION (periodic/critical)")
                
                analytics_report = await self.analytics.generate_report()
                feedback = await self.storage.get_feedback_history()
                
                try:
                    new_strat = await self.cloud_brain.generate_strategy_v2(
                        mission.to_dict(), 
                        self.session_stats, 
                        feedback,
                        analytics_report
                    )
                    
                    if new_strat:
                        logger.info(f"✨ Applying AI-generated strategy: {json.dumps(new_strat)}")
                        with open(self.strategy_path, "w") as f:
                            json.dump(new_strat, f, indent=4)
                        
                        # Reset stats
                        self.session_stats["scanned"] = 0
                        self.session_stats["interested"] = 0
                except Exception as e:
                    logger.error(f"AI optimization failed: {e}")

    def _should_use_ai_optimization(self, mission_name: str, recent_perf: List[Dict]) -> bool:
        """AI kullanılmalı mı?"""
        # Her 50 döngüde bir
        if self._cycle_count % self._ai_optimization_interval == 0:
            return True
        
        # Kritik durum: sürekli düşük performans
        if len(recent_perf) >= 5:
            avg_last_5 = sum(p['success_rate'] for p in recent_perf[:5]) / 5
            if avg_last_5 < 0.05:  # %5'ten az
                logger.warning(f"⚠️ Critical low performance detected: {avg_last_5:.2%}")
                return True
        
        return False

    def stop(self):
        self.running = False

def import_os_exists(path):
    import os
    return os.path.exists(path)

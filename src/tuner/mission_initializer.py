"""
Mission Initialization System.

This module handles the AI-driven initialization of new missions.
It analyzes user notes, seed repos, and starred repositories to
generate internal strategy and initial tactic weights.
"""

import logging
import json
from typing import Dict, Any, List

from tuner.mission import Mission, MissionControl
from tuner.brain import CloudBrain
from tuner.hunter import Hunter
from tuner.storage import TunerStorage

logger = logging.getLogger(__name__)

class MissionInitializer:
    def __init__(self, mission_control: MissionControl, hunter: Hunter, cloud_brain: CloudBrain):
        self.mission_control = mission_control
        self.hunter = hunter
        self.cloud_brain = cloud_brain
    
    async def initialize_pending_missions(self):
        """Scans for uninitialized missions and initializes them."""
        for mission in self.mission_control.missions:
            if not getattr(mission, 'initialized', False):
                logger.info(f"✨ Initializing Mission: {mission.name}")
                await self._initialize_mission(mission)
                
        # Save changes
        self.mission_control.save_missions()
        
    async def _initialize_mission(self, mission: Mission):
        """
        AI analysis for a single mission.
        Generates ai_strategy and learned_tactics.
        """
        # 1. Gather Context
        context_data = await self._gather_context(mission)
        
        # 2. Ask Brain
        strategy = await self._generate_ai_strategy(mission, context_data)
        
        if strategy:
            mission.ai_strategy = strategy
            
            # 3. Apply initial tactic weights
            mission.learned_tactics = strategy.get("initial_tactic_weights", {
                "trending": 0.5,
                "established": 0.5
            })
            
            logger.info(f"🧠 AI generated strategy for {mission.name}")
            logger.debug(f"Strategy: {json.dumps(strategy, indent=2)}")
            
        mission.initialized = True
        
    async def _gather_context(self, mission: Mission) -> Dict[str, Any]:
        """Gather data from seed repos and starred repos."""
        context = {
            "seed_data": [],
            "user_intent": mission.user_notes or "No user notes provided."
        }
        
        # Analyze Seed Repos
        if mission.seed_repos:
            for repo_url in mission.seed_repos:
                try:
                    # Parse owner/repo
                    if "github.com/" in repo_url:
                        parts = repo_url.split("github.com/")[1].split("/")
                        owner, repo = parts[0], parts[1]
                    else:
                        owner, repo = repo_url.split("/")
                        
                    # Fetch minimal metadata
                    # (In a real scenario we'd call GitHub API, here we simulate or minimal fetch)
                    # For now just passing the names is enough context for the LLM
                    context["seed_data"].append(f"{owner}/{repo}")
                except:
                    pass
        
        # Analyze Starred Repos (Context)
        # For simplicity, we assume we might have some local knowledge or just skip network call for now
        # to keep initialization fast.
        
        return context

    async def _generate_ai_strategy(self, mission: Mission, context: Dict) -> Dict:
        """Call CloudBrain to strategize."""
        prompt = f"""
        MISSION INITIALIZATION
        
        Name: {mission.name}
        Goal: {mission.goal}
        Languages: {mission.languages}
        User Notes: {context['user_intent']}
        Seed Repos: {context['seed_data']}
        
        TASK:
        Generate a search strategy based on seed repos and user notes.
        CRITICAL: Analyze 'Seed Repos' to extract specific topics/keywords.
        
        OUTPUT (JSON structure):
        {{
            "analysis": "Brief analysis of what the user wants",
            "keywords": ["MUST include specific topics/libs from seed repos", "list", "of", "keywords"],
            "avoid_keywords": ["terms", "to", "avoid"],
            "initial_tactic_weights": {{
                "trending": 0.0-1.0,
                "rising_stars": 0.0-1.0,
                "established": 0.0-1.0,
                "deep_dive": 0.0-1.0
            }}
        }}
        """
        
        try:
            # Simulate or call actual brain
            response = await self.cloud_brain.generate_text(prompt)
            
            # Clean JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
                
            return json.loads(response.strip())
        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            return None

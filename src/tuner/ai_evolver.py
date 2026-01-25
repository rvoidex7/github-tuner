"""
Safe AI Tactic Evolver.

This module handles the safe evolution of search tactics by the AI.
It ensures that AI-generated changes are validated, backed up, and
can be rolled back if necessary.
"""

import json
import logging
import shutil
import glob
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from tuner.tactics import SearchTactic, TacticEngine
from tuner.brain import CloudBrain

logger = logging.getLogger(__name__)


class SafeAITacticEvolver:
    """
    Safely evolves tactics based on performance.
    AI can create/modify tactics WITHOUT touching Python code.
    """
    
    def __init__(self, storage=None, cloud_brain: CloudBrain = None):
        self.storage = storage
        self.cloud_brain = cloud_brain
        self.tactics_file = "tactics.json"
        self.backup_dir = "backups/tactics"
        
        # Ensure backup dir exists
        os.makedirs(self.backup_dir, exist_ok=True)
    
    async def propose_and_apply_evolution(self, performance_report: Dict[str, Any]) -> bool:
        """
        Main entry point: Analyze performance -> Propose -> Validate -> Apply.
        """
        logger.info("🧬 Starting Safe AI Tactic Evolution...")
        
        # 1. Ask AI for new tactics JSON
        proposed_tactics = await self._generate_proposal(performance_report)
        if not proposed_tactics:
            logger.warning("❌ AI failed to generate valid tactics proposal")
            return False
            
        # 2. Safely apply
        success = self.safely_apply_evolution(proposed_tactics)
        return success

    async def _generate_proposal(self, report: Dict) -> Optional[Dict]:
        """Ask Brain to generate new tactics list."""
        if not self.cloud_brain:
            logger.error("CloudBrain not available for evolution")
            return None
            
        # Context prompt
        prompt = f"""
        You are the Strategic Optimizer for a GitHub Research Agent.
        
        PERFORMANCE REPORT:
        {json.dumps(report, indent=2)}
        
        TASK:
        1. Analyze which tactics are performing well/poorly.
        2. Propose a NEW list of tactics.
        3. You can modify existing tactics (e.g. adjust stars_min, date_filters).
        4. You can CREATE new tactics (e.g. 'niche_discovery', 'keyword_explorer').
        5. You can REMOVE ineffective tactics.
        
        CONSTRAINTS:
        - Output MUST be a valid JSON object matching the 'tactics.json' schema.
        - Root object must have "tactics": [ ... list of tactic objects ... ]
        - Each tactic must have: name, description, weight (0.1-2.0), sort_by
        - Optional fields: stars_min, stars_max, date_filter, page_range, keyword_strategy
        
        EXISTING TACTICS (for reference):
        {open("tactics.json", "r", encoding="utf-8").read()}
        
        Return ONLY valid JSON.
        """
        
        try:
            # We assume cloud_brain has a generic generate_json method or similar
            # For now, we simulate using generate_text and parsing
            response = await self.cloud_brain.generate_text(prompt) 
            
            # Simple cleanup for markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
                
            data = json.loads(response.strip())
            return data
        except Exception as e:
            logger.error(f"Failed to generate proposal: {e}")
            return None
    
    def safely_apply_evolution(self, proposed_data: Dict) -> bool:
        """
        Validates and applies proposed changes with rollback support.
        """
        logger.info("🛡️ Validating proposed tactics...")
        
        # 1. Backup current
        self._backup_tactics()
        
        # 2. Validate Schema
        if not self._validate_tactics_schema(proposed_data):
            logger.error("❌ Invalid tactics schema - Proposal rejected")
            return False
        
        # 3. Write new file (Atomic-ish)
        return self._write_and_verify(proposed_data)
    
    def _write_and_verify(self, data: Dict) -> bool:
        """Write to file and verify it loads correctly."""
        try:
            # Add metadata
            data["last_modified"] = datetime.utcnow().isoformat() + "Z"
            data["last_modified_by"] = "ai_evolver"
            
            with open(self.tactics_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            # 4. Test Load (Verification)
            engine = TacticEngine() # Should default load from file
            # If we reached here, TacticEngine loaded it successfully
            
            logger.info(f"✅ Evolution Applied! {len(engine.tactics)} tactics active.")
            return True
            
        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            logger.info("🔄 Rolling back changes...")
            self._rollback_tactics()
            return False
            
    def _validate_tactics_schema(self, data: Dict) -> bool:
        """Check if JSON matches expected structure."""
        if not isinstance(data, dict): return False
        if "tactics" not in data: return False
        if not isinstance(data["tactics"], list): return False
        
        # Check at least one tactic
        if len(data["tactics"]) == 0: return False
        
        # Check defining fields
        required = {"name", "description"}
        for t in data["tactics"]:
            if not all(field in t for field in required):
                return False
                
        return True
    
    def _backup_tactics(self):
        """Keep versioned backups."""
        if not os.path.exists(self.tactics_file):
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(self.backup_dir, f"tactics_{timestamp}.json")
        shutil.copy(self.tactics_file, dest)
        
        # Cleanup old backups (keep last 10)
        backups = sorted(glob.glob(os.path.join(self.backup_dir, "*.json")))
        for old in backups[:-10]:
            try:
                os.remove(old)
            except: pass
            
    def _rollback_tactics(self):
        """Restore last working version."""
        backups = sorted(glob.glob(os.path.join(self.backup_dir, "*.json")))
        if backups:
            last_good = backups[-1]
            shutil.copy(last_good, self.tactics_file)
            logger.info(f"✅ Rolled back to {last_good}")
        else:
            logger.warning("⚠️ No backups found to rollback to!")


import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass
class Mission:
    name: str  # e.g., "Python AI Research"
    goal: str  # e.g., "Find autonomous agent libraries"
    languages: List[str]
    min_stars: int
    context_path: Optional[str] = None # For Project Match mode

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(data):
        return Mission(**data)

class MissionControl:
    def __init__(self, mission_path: str = "missions.json"):
        self.mission_path = mission_path
        self.legacy_path = "mission.json"
        
        self.missions: List[Mission] = []
        self.current_index = 0
        
        self.load_missions()

    def load_missions(self):
        """Load missions from file or create default."""
        self.missions = []
        
        # 1. Try missions.json (List)
        if os.path.exists(self.mission_path):
            try:
                with open(self.mission_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.missions = [Mission.from_dict(m) for m in data]
                    else:
                        # Fallback if user put a single dict in missions.json?
                        self.missions = [Mission.from_dict(data)]
            except Exception as e:
                print(f"Error loading missions.json: {e}")
        
        # 2. Try legacy mission.json (Single) if list is empty
        if not self.missions and os.path.exists(self.legacy_path):
            try:
                with open(self.legacy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.missions = [Mission.from_dict(data)]
            except Exception:
                pass
                
        # 3. Default if still empty
        if not self.missions:
            self.create_default_mission()

    @property
    def current_mission(self) -> Optional[Mission]:
        if not self.missions: 
            return None
        return self.missions[self.current_index]

    def next_mission(self) -> Optional[Mission]:
        """Cycle to the next mission."""
        if not self.missions:
             return None
        self.current_index = (self.current_index + 1) % len(self.missions)
        return self.current_mission

    def create_default_mission(self):
        """Create a default mission."""
        default = Mission(
            name="General Exploration",
            goal="Find interesting open source tools",
            languages=["Python"],
            min_stars=50
        )
        self.missions = [default]
        self.save_missions()

    def save_missions(self):
        """Save current missions to file."""
        if self.missions:
            data = [m.to_dict() for m in self.missions]
            with open(self.mission_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

    def update_mission(self, name: str, goal: str, languages: List[str]):
        """Update the active mission (legacy support - updates current)."""
        if self.current_mission:
             self.current_mission.name = name
             self.current_mission.goal = goal
             self.current_mission.languages = languages
             self.save_missions()

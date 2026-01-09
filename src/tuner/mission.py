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
    def __init__(self, mission_path: str = "mission.json"):
        self.mission_path = mission_path
        self.current_mission: Optional[Mission] = None
        self.load_mission()

    def load_mission(self):
        """Load mission from file or create default."""
        if os.path.exists(self.mission_path):
            try:
                with open(self.mission_path, "r") as f:
                    data = json.load(f)
                    self.current_mission = Mission.from_dict(data)
            except Exception:
                self.create_default_mission()
        else:
            self.create_default_mission()

    def create_default_mission(self):
        """Create a default mission."""
        self.current_mission = Mission(
            name="General Exploration",
            goal="Find interesting open source tools",
            languages=["Python"],
            min_stars=50
        )
        self.save_mission()

    def save_mission(self):
        """Save current mission to file."""
        if self.current_mission:
            with open(self.mission_path, "w") as f:
                json.dump(self.current_mission.to_dict(), f, indent=4)

    def update_mission(self, name: str, goal: str, languages: List[str]):
        """Update the active mission."""
        if self.current_mission:
             self.current_mission.name = name
             self.current_mission.goal = goal
             self.current_mission.languages = languages
             self.save_mission()

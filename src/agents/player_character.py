from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import random

from .base_agent import BaseAgent
from ..utils.llm_client import LLMClient
from ..utils.schemas import CharacterAction

class Stat(Enum):
    STRENGTH = "STR"
    DEXTERITY = "DEX"
    CONSTITUTION = "CON"
    INTELLIGENCE = "INT"
    WISDOM = "WIS"
    CHARISMA = "CHA"

@dataclass
class CharacterStats:
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    level: int = 1
    hp_max: int = 10
    hp_current: int = 10

    def get_modifier(self, stat: Stat) -> int:
        """Calculate D&D style modifier from stat."""
        stat_value = getattr(self, stat.value.lower())
        return (stat_value - 10) // 2

@dataclass
class Item:
    name: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    equipped: bool = False

class PlayerCharacter(BaseAgent):
    def __init__(
        self, 
        name: str, 
        character_class: str,
        race: str = "Human",
        background: str = "Adventurer"
    ):
        super().__init__(name)
        self.character_class = character_class
        self.race = race
        self.background = background
        self.stats = CharacterStats()
        self.inventory: List[Item] = []
        self.current_goal = "Explore"
        self.personality = {
            "traits": [],
            "ideals": [],
            "bonds": [],
            "flaws": []
        }
        self.llm_client = LLMClient()

    async def initialize_character(self, config: Dict[str, Any]) -> None:
        """Initialize character with provided configuration."""
        # Set basic stats
        stats_config = config.get("stats", {})
        for stat in Stat:
            setattr(self.stats, stat.value.lower(), stats_config.get(stat.value, 10))

        # Set personality
        self.personality.update(config.get("personality", {}))

        # Set initial inventory
        for item_data in config.get("inventory", []):
            self.add_item(Item(**item_data))

        # Set initial goal
        self.current_goal = config.get("initial_goal", "Explore")

    async def decideNextAction(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Decide next action based on context and character personality."""
        try:
            # Get structured action from LLM
            action = await self.llm_client.generate_character_action(
                character_info=self.get_character_sheet(),
                context={
                    "scene": context.get("world_state", {}).get("current_location", {}),
                    "available_actions": context.get("world_state", {}).get("possible_actions", []),
                    "current_goal": self.current_goal,
                    "last_action_result": context.get("world_state", {}).get("last_action", {})
                }
            )
            
            # Convert structured action to game format
            return {
                "type": action.action_type,
                "target": action.target,
                "content": action.description,
                "reasoning": action.reasoning,
                "source": self.name
            }
        
        except Exception as e:
            return self._get_fallback_action()

    def add_item(self, item: Item) -> None:
        """Add item to inventory."""
        self.inventory.append(item)

    def remove_item(self, item_name: str) -> Optional[Item]:
        """Remove and return item from inventory."""
        for i, item in enumerate(self.inventory):
            if item.name == item_name:
                return self.inventory.pop(i)
        return None

    def get_character_sheet(self) -> Dict[str, Any]:
        """Get complete character information."""
        return {
            "name": self.name,
            "class": self.character_class,
            "race": self.race,
            "background": self.background,
            "stats": {stat.value: getattr(self.stats, stat.value.lower()) for stat in Stat},
            "inventory": [item.__dict__ for item in self.inventory],
            "current_goal": self.current_goal,
            "personality": self.personality
        }

    def roll_check(self, stat: Stat) -> Dict[str, Any]:
        """Perform a D&D style ability check."""
        d20 = random.randint(1, 20)
        modifier = self.stats.get_modifier(stat)
        total = d20 + modifier
        
        return {
            "roll": d20,
            "modifier": modifier,
            "total": total,
            "critical": d20 in (1, 20)
        }

    def _build_action_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for LLM to decide action."""
        scene = context.get("world_state", {}).get("current_location", {})
        available_actions = scene.get("possible_actions", [])
        
        return f"""
        As {self.name}, a {self.race} {self.character_class}, you need to choose your next action.
        
        Current goal: {self.current_goal}
        Available actions: {', '.join(available_actions)}
        
        Location description: {scene.get('description', 'unknown location')}
        Visible NPCs: {', '.join(scene.get('visible_npcs', []))}
        Visible objects: {', '.join(scene.get('visible_objects', []))}
        
        Choose one of the available actions that best fits your personality and goal.
        Your personality traits are:
        - Traits: {', '.join(self.personality['traits'])}
        - Ideals: {', '.join(self.personality['ideals'])}
        """

    def _enhance_action_with_stats(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Add relevant stat modifiers to action."""
        action_stats = {
            "attack": Stat.STRENGTH,
            "talk": Stat.CHARISMA,
            "look": Stat.WISDOM,
            "move": Stat.DEXTERITY
        }
        
        if action["type"] in action_stats:
            relevant_stat = action_stats[action["type"]]
            action["modifier"] = self.stats.get_modifier(relevant_stat)
            
        return action

    def _get_fallback_action(self) -> Dict[str, Any]:
        """Return a safe fallback action if decision-making fails."""
        return {
            "type": "look",
            "content": "Looking around cautiously",
            "source": self.name,
            "fallback": True
        }

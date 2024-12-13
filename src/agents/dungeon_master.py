from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

from .base_agent import BaseAgent
from ..utils.llm_client import LLMClient

@dataclass
class Location:
    name: str
    description: str
    connected_to: List[str]
    npcs: List[str]
    items: List[str]
    atmosphere: str = "neutral"
    visited: bool = False

@dataclass
class NPC:
    name: str
    role: str
    location: str
    dialog_state: Dict[str, Any] = field(default_factory=dict)
    inventory: List[str] = field(default_factory=list)

class DungeonMaster(BaseAgent):
    def __init__(self, name: str):
        super().__init__(name)
        self.world_state: Dict[str, Any] = {
            "current_location": "tavern",
            "time_of_day": "morning",
            "weather": "clear",
            "active_quests": [],
            "global_state": {"threat_level": "low", "main_quest_progress": 0}
        }
        self.locations: Dict[str, Location] = {}
        self.npcs: Dict[str, NPC] = {}
        self.player_states: Dict[str, Dict[str, Any]] = {}
        self.llm_client = LLMClient()

    async def initialize_world(self, config: Dict[str, Any]) -> None:
        """Initialize world with provided configuration."""
        # Set up initial locations
        for loc_data in config.get("locations", []):
            self.locations[loc_data["name"]] = Location(**loc_data)
        
        # Set up NPCs
        for npc_data in config.get("npcs", []):
            self.npcs[npc_data["name"]] = NPC(**npc_data)

        # Initialize world state
        self.world_state.update(config.get("initial_state", {}))

    async def describeScene(self) -> str:
        """Generate description of the current scene using LLM."""
        current_loc = self.locations.get(self.world_state["current_location"])
        if not current_loc:
            return "You are in an undefined location."

        scene_context = {
            "location": current_loc.name,
            "time": self.world_state["time_of_day"],
            "atmosphere": current_loc.atmosphere,
            "elements": (
                [f"NPC: {npc}" for npc in current_loc.npcs] +
                [f"Item: {item}" for item in current_loc.items]
            )
        }

        return await self.llm_client.generate_scene_description(scene_context)

    async def handlePlayerAction(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Process player action and return result."""
        # Получаем контекст для интерпретации действия
        context = {
            "location": self.world_state["current_location"],
            "time": self.world_state["time_of_day"],
            "action": action,
            "current_npcs": [npc for npc in self.npcs.values() 
                           if npc.location == self.world_state["current_location"]],
            "current_location": self.locations[self.world_state["current_location"]],
            "quest_state": self.world_state.get("global_state", {})
        }

        try:
            # Генерируем ответ с помощью LLM
            response = await self.llm_client.generate_dm_response(context)
            
            # Применяем изменения к миру
            world_updates = await self._apply_action_consequences(action, response)
            
            # Обновляем состояние NPCs если нужно
            if "npc_responses" in response:
                await self._update_npc_states(response["npc_responses"])
            
            # Проверяем прогресс квестов
            quest_updates = self._check_quest_progress(action, response)
            
            # Формируем финальный ответ с учетом всех изменений
            final_response = {
                "success": True,
                "message": response["message"],
                "details": response["details"],
                "world_changes": world_updates,
                "quest_updates": quest_updates,
                "npc_reactions": response.get("npc_responses", {})
            }

            return final_response

        except Exception as e:
            logger.error(f"Error processing action: {e}", exc_info=True)
            return self._generate_fallback_response(action)

    async def _apply_action_consequences(self, action: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        """Apply action consequences to world state."""
        updates = {}
        
        # Обработка изменения локации
        if "location_change" in response:
            new_location = response["location_change"]
            if new_location in self.locations:
                self.world_state["current_location"] = new_location
                self.locations[new_location].visited = True
                updates["location"] = new_location

        # Обработка изменений состояния NPC
        if "npc_state_change" in response:
            for npc_name, changes in response["npc_state_change"].items():
                if npc_name in self.npcs:
                    self.npcs[npc_name].dialog_state.update(changes)
                    updates["npcs"] = updates.get("npcs", {})
                    updates["npcs"][npc_name] = changes

        # Обработка изменений предметов
        if "item_changes" in response:
            for item_change in response["item_changes"]:
                location = self.locations[self.world_state["current_location"]]
                if item_change["action"] == "remove":
                    if item_change["item"] in location.items:
                        location.items.remove(item_change["item"])
                elif item_change["action"] == "add":
                    location.items.append(item_change["item"])
                updates["items"] = item_change

        # Обновляем время если нужно
        if response.get("time_passed", False):
            self._advance_time()
            updates["time"] = self.world_state["time_of_day"]

        return updates

    def _generate_fallback_response(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a fallback response when normal processing fails."""
        return {
            "success": True,
            "message": f"You try to {action.get('type', 'do something')}.",
            "details": action.get('content', 'Nothing special happens.'),
            "world_changes": {},
            "quest_updates": {},
            "npc_reactions": {}
        }

    def _advance_time(self) -> None:
        """Advance time of day."""
        times = ["morning", "afternoon", "evening", "night"]
        current_idx = times.index(self.world_state["time_of_day"])
        self.world_state["time_of_day"] = times[(current_idx + 1) % len(times)]

    async def update_world_state(self) -> None:
        """Update world state based on time passage and events."""
        # Update time of day
        times = ["morning", "afternoon", "evening", "night"]
        current_idx = times.index(self.world_state["time_of_day"])
        self.world_state["time_of_day"] = times[(current_idx + 1) % len(times)]

        # Update NPC positions and states
        await self._update_npcs()

    async def _update_npcs(self) -> None:
        """Update NPC states and positions."""
        for npc in self.npcs.values():
            # Simple NPC movement between connected locations
            if self.world_state["time_of_day"] in ["morning", "afternoon"]:
                connected_locs = self.locations[npc.location].connected_to
                if connected_locs:
                    npc.location = connected_locs[0]  # Simple movement logic

    async def _update_world_state(self, action_type: str, result: Dict[str, Any]) -> None:
        """Update world state based on action results."""
        self.world_state["last_action"] = {
            "type": action_type,
            "timestamp": datetime.now().isoformat(),
            "result": True  # Всегда True, так как любое действие возможно
        }

        # Обновляем базовые параметры мира
        if "location_change" in result:
            self.world_state["current_location"] = result["location_change"]
        
        if "npc_state_change" in result:
            for npc_name, state in result["npc_state_change"].items():
                if npc_name in self.npcs:
                    self.npcs[npc_name].dialog_state.update(state)

    def _check_quest_progress(self, action_type: str, result: Dict[str, Any]) -> None:
        """Check and update quest progress based on actions."""
        if not result.get("success"):
            return

        current_location = self.world_state["current_location"]
        active_quests = self.world_state["active_quests"]

        # Example quest progress check
        if "Find the missing shipment" in active_quests:
            if (action_type == "talk" and 
                result.get("target") == "barkeep" and 
                "shipment" in result.get("message", "").lower()):
                self.world_state["global_state"]["main_quest_progress"] += 1

    def get_world_state(self) -> Dict[str, Any]:
        """Get current world state for external use."""
        return {
            "world_state": self.world_state.copy(),
            "current_location": self.locations.get(self.world_state["current_location"]).__dict__,
            "active_npcs": [
                npc.__dict__ 
                for npc in self.npcs.values() 
                if npc.location == self.world_state["current_location"]
            ],
            "possible_actions": [
                "talk to " + npc.name 
                for npc in self.npcs.values() 
                if npc.location == self.world_state["current_location"]
            ] + [
                "examine " + item 
                for item in self.locations[self.world_state["current_location"]].items
            ] + [
                "move to " + loc 
                for loc in self.locations[self.world_state["current_location"]].connected_to
            ]
        }

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

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
        action_type = action.get("type", "")
        player_id = action.get("player_id")
        
        # Validate player exists
        if player_id and player_id not in self.player_states:
            return {"success": False, "message": "Invalid player"}

        result = await self._process_action(action_type, action, player_id)
        await self._update_world_state(action_type, result)
        
        return result

    def get_world_state(self) -> Dict[str, Any]:
        """Get current world state for external use."""
        return {
            "world_state": self.world_state.copy(),
            "current_location": self.locations.get(self.world_state["current_location"]).__dict__,
            "active_npcs": [npc.__dict__ for npc in self.npcs.values() 
                          if npc.location == self.world_state["current_location"]]
        }

    async def update_world_state(self) -> None:
        """Update world state based on time passage and events."""
        # Update time of day
        times = ["morning", "afternoon", "evening", "night"]
        current_idx = times.index(self.world_state["time_of_day"])
        self.world_state["time_of_day"] = times[(current_idx + 1) % len(times)]

        # Update NPC positions and states
        await self._update_npcs()

    async def _process_action(
        self, 
        action_type: str, 
        action: Dict[str, Any], 
        player_id: Optional[str]
    ) -> Dict[str, Any]:
        """Process specific action types and return results."""
        handlers = {
            "look": self._handle_look,
            "move": self._handle_move,
            "talk": self._handle_talk,
            "interact": self._handle_interact,
            "use": self._handle_use
        }

        handler = handlers.get(action_type, self._handle_unknown)
        return await handler(action, player_id)

    async def _handle_look(self, action: Dict[str, Any], player_id: Optional[str]) -> Dict[str, Any]:
        """Handle look/examine actions."""
        target = action.get("target", "around")
        if target == "around":
            description = await self.describeScene()
            return {"success": True, "description": description}
        
        # Handle looking at specific targets (NPCs, items, etc.)
        return {"success": True, "description": f"You examine the {target}."}

    async def _handle_move(self, action: Dict[str, Any], player_id: Optional[str]) -> Dict[str, Any]:
        """Handle movement between locations."""
        destination = action.get("destination")
        current_loc = self.locations.get(self.world_state["current_location"])
        
        if not destination or not current_loc or destination not in current_loc.connected_to:
            return {"success": False, "message": "Invalid movement"}

        self.world_state["current_location"] = destination
        return {"success": True, "message": f"Moved to {destination}"}

    async def _handle_talk(self, action: Dict[str, Any], player_id: Optional[str]) -> Dict[str, Any]:
        """Handle conversation with NPCs."""
        npc_name = action.get("target")
        npc = self.npcs.get(npc_name)
        
        if not npc or npc.location != self.world_state["current_location"]:
            return {"success": False, "message": "Cannot talk to that person"}

        dialog_context = {
            "name": npc.name,
            "role": npc.role,
            "dialog_state": npc.dialog_state
        }
        
        response = await self.llm_client.generate_character_response(
            dialog_context,
            action.get("dialog", "Hello")
        )
        
        return {"success": True, "message": response}

    async def _handle_interact(self, action: Dict[str, Any], player_id: Optional[str]) -> Dict[str, Any]:
        """Handle interaction with objects or environment."""
        target = action.get("target", "")
        current_loc = self.locations.get(self.world_state["current_location"])
        
        # Check if target is an item in current location
        if target in current_loc.items:
            return {
                "success": True,
                "message": f"You interact with the {target}.",
                "details": f"It seems to be a normal {target}."
            }
        
        # Check if it's a general environment interaction
        return {
            "success": True,
            "message": f"You try to interact with {target or 'the surroundings'}.",
            "details": "Nothing special happens."
        }

    async def _handle_use(self, action: Dict[str, Any], player_id: Optional[str]) -> Dict[str, Any]:
        """Handle using items or abilities."""
        content = action.get("content", "")
        
        # For now, interpret 'use' actions that look like dialog as 'talk' actions
        if "barkeep" in content.lower() or "speak" in content.lower():
            return await self._handle_talk({
                "type": "talk",
                "target": "barkeep",
                "dialog": content
            }, player_id)
        
        # Generic use action response
        return {
            "success": True,
            "message": "You try to use something.",
            "details": content
        }

    async def _handle_unknown(self, action: Dict[str, Any], player_id: Optional[str]) -> Dict[str, Any]:
        """Handle unknown action types."""
        return {
            "success": False,
            "message": f"Unknown action type: {action.get('type')}"
        }

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
        # Update last action timestamp
        self.world_state["last_action"] = {
            "type": action_type,
            "timestamp": datetime.now().isoformat(),
            "result": result.get("success", False)
        }

        # Update specific states based on action type
        if action_type == "move" and result.get("success"):
            self.world_state["current_location"] = result.get("destination", self.world_state["current_location"])
        
        elif action_type == "talk" and result.get("success"):
            npc_name = result.get("target")
            if npc_name in self.npcs:
                self.npcs[npc_name].dialog_state["last_conversation"] = datetime.now().isoformat()
                
        elif action_type == "interact" and result.get("success"):
            current_loc = self.locations.get(self.world_state["current_location"])
            if current_loc:
                # Update location state if needed
                target = result.get("target")
                if target in current_loc.items:
                    # Mark item as interacted with
                    if "interacted_items" not in current_loc.__dict__:
                        current_loc.__dict__["interacted_items"] = set()
                    current_loc.__dict__["interacted_items"].add(target)

        # Update quest progress if applicable
        self._check_quest_progress(action_type, result)

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

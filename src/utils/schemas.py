from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SceneDescription(BaseModel):
    description: str
    visible_objects: List[str]
    visible_npcs: List[str]
    atmosphere: str
    possible_actions: List[str]

class DialogResponse(BaseModel):
    speech: str
    tone: str
    actions: List[str]
    npc_state: str
    reveals_quest_info: bool

class CharacterAction(BaseModel):
    action_type: str = Field(
        ...,
        description="Type of action to perform. Must be one of the available actions in the scene."
    )
    target: Optional[str] = Field(
        None,
        description="Specific target of the action (NPC name, item, location, etc)"
    )
    description: str = Field(
        ...,
        description="Brief description of how the action is performed"
    )
    reasoning: str = Field(
        ...,
        description="Why this action was chosen based on character's personality and goals"
    )
    uses_ability: Optional[str] = None
    required_roll: Optional[str] = None

class CombatAction(BaseModel):
    action_type: str
    target: str
    weapon: Optional[str]
    ability: Optional[str]
    tactics: str
    estimated_difficulty: int

class QuestInfo(BaseModel):
    title: str
    description: str
    importance: str
    suggested_level: int
    rewards: List[str]
    related_npcs: List[str]

class NPCResponse(BaseModel):
    npc_name: str
    reaction: str
    attitude_change: Optional[str]
    reveals_info: bool

class ItemChange(BaseModel):
    item: str
    action: str  # "add" or "remove"
    reason: str

class DMResponse(BaseModel):
    success: bool
    message: str = Field(..., description="Main response text describing what happens")
    details: Optional[str] = Field(None, description="Additional details or consequences")
    location_change: Optional[str] = Field(None, description="New location if player moved")
    npc_responses: Optional[Dict[str, NPCResponse]] = Field(
        None,
        description="NPC reactions to the action"
    )
    item_changes: Optional[List[ItemChange]] = Field(
        None,
        description="Changes to items in the scene"
    )
    time_passed: bool = Field(
        False,
        description="Whether the action takes enough time to advance the clock"
    )
    quest_progress: Optional[Dict[str, Any]] = Field(
        None,
        description="Updates to quest progress"
    )
    npc_state_change: Optional[Dict[str, Dict[str, Any]]] = Field(
        None, 
        description="Changes to NPC states"
    )

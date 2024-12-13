import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
import json
import logging

from .base_agent import BaseAgent
from .dungeon_master import DungeonMaster
from .player_character import PlayerCharacter
from ..utils.llm_client import LLMClient

# Configure logging for the coordinator
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add file handler for detailed logging
fh = logging.FileHandler('game_session.log')
fh.setLevel(logging.DEBUG)
fh_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)

@dataclass
class GameSession:
    session_id: str
    start_time: datetime = field(default_factory=datetime.now)
    game_state: Dict[str, Any] = field(default_factory=dict)
    round_number: int = 0
    active: bool = True

class GameCoordinator:
    def __init__(self):
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.broadcast_queue: asyncio.Queue = asyncio.Queue()
        self.dm: Optional[DungeonMaster] = None
        self.players: List[PlayerCharacter] = []
        self.session: Optional[GameSession] = None
        self.llm_client = LLMClient()
        logger.info("Game Coordinator initialized")
        self.start_time = datetime.now()

    async def initialize_game(self, scenario_config: Dict[str, Any]) -> None:
        """Initialize a new game session with DM and players."""
        logger.info("Initializing new game session")
        logger.debug(f"Scenario config: {json.dumps(scenario_config, indent=2)}")

        self.session = GameSession(
            session_id=f"game_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            game_state=scenario_config
        )
        logger.info(f"Created new session with ID: {self.session.session_id}")

        # Initialize Dungeon Master
        logger.info("Initializing Dungeon Master")
        self.dm = DungeonMaster("DungeonMaster")
        await self.dm.initialize_world(scenario_config.get("world_config", {}))
        logger.debug("DM world state initialized")

        # Initialize Players
        logger.info("Initializing Players")
        for player_config in scenario_config.get("players", []):
            logger.debug(f"Creating player: {player_config['name']}")
            player = PlayerCharacter(
                name=player_config["name"],
                character_class=player_config["class"]
            )
            self.players.append(player)
            await player.initialize_character(player_config)
            logger.debug(f"Player {player.name} initialized with class {player.character_class}")

        # Start message handling tasks
        logger.info("Starting message handling tasks")
        asyncio.create_task(self._handle_messages())
        asyncio.create_task(self._handle_broadcasts())

    async def start_game(self) -> None:
        """Start the game session and initial scene."""
        if not self.session or not self.dm:
            logger.error("Attempted to start game without initialization")
            raise ValueError("Game not initialized")

        logger.info("Starting game session")
        
        # Get initial scene description
        logger.debug("Requesting initial scene description")
        initial_scene = await self.dm.describeScene()
        logger.info("Initial scene generated")
        logger.debug(f"Scene description: {initial_scene}")

        await self.broadcast_message({
            "type": "scene_description",
            "content": initial_scene,
            "timestamp": datetime.now().isoformat()
        })

        # Start game loop
        logger.info("Starting main game loop")
        await self._game_loop()

    async def _game_loop(self) -> None:
        """Main game loop handling rounds and turns."""
        while self.session and self.session.active:
            self.session.round_number += 1
            logger.info(f"Starting round {self.session.round_number}")

            await self.broadcast_message({
                "type": "round_start",
                "round": self.session.round_number
            })

            # Handle each player's turn
            for player in self.players:
                logger.debug(f"Processing turn for player: {player.name}")
                
                # Get player action
                action = await self._handle_player_turn(player)
                logger.debug(f"Player {player.name} action: {action}")
                
                # Process action through DM
                logger.debug(f"Sending action to DM: {action}")
                result = await self.dm.handlePlayerAction(action)
                logger.debug(f"DM response: {result}")
                
                # Broadcast results
                await self.broadcast_message({
                    "type": "action_result",
                    "player": player.name,
                    "action": action,
                    "result": result
                })

            # End of round processing
            logger.info(f"Completing round {self.session.round_number}")
            await self._process_end_of_round()

    async def _handle_player_turn(self, player: PlayerCharacter) -> Dict[str, Any]:
        """Handle individual player turn."""
        logger.debug(f"Starting turn for {player.name}")
        
        # Get current game context
        context = self._build_turn_context(player)
        logger.debug(f"Turn context for {player.name}: {context}")
        
        # Get player's action
        action = await player.decideNextAction(context)
        logger.debug(f"Player {player.name} decided action: {action}")
        
        # Validate action
        if not self._validate_action(action):
            logger.warning(f"Invalid action from {player.name}: {action}")
            return {"type": "invalid_action", "original_action": action}
        
        return action

    async def _handle_messages(self) -> None:
        """Process messages in the queue."""
        logger.debug("Message handler started")
        while True:
            message = await self.message_queue.get()
            logger.debug(f"Processing message: {message}")
            try:
                if message.get("type") == "player_action":
                    await self._process_player_action(message)
                elif message.get("type") == "dm_response":
                    await self._process_dm_response(message)
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
                await self.broadcast_message({
                    "type": "error",
                    "content": f"Error processing message: {str(e)}"
                })
            finally:
                self.message_queue.task_done()

    async def _handle_broadcasts(self) -> None:
        """Handle broadcasting messages to all participants."""
        while True:
            message = await self.broadcast_queue.get()
            try:
                # Send to DM
                if self.dm:
                    await self.dm.process_message(message, "Coordinator")
                
                # Send to all players
                for player in self.players:
                    await player.process_message(message, "Coordinator")
                
            finally:
                self.broadcast_queue.task_done()

    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        """Add message to broadcast queue."""
        logger.debug(f"Broadcasting message: {message}")
        await self.broadcast_queue.put(message)

    def _build_turn_context(self, player: PlayerCharacter) -> Dict[str, Any]:
        """Build context for player turn."""
        return {
            "round": self.session.round_number,
            "game_state": self.session.game_state,
            "player_state": player.get_state(),
            "world_state": self.dm.get_world_state() if self.dm else {}
        }

    def _validate_action(self, action: Dict[str, Any]) -> bool:
        """Validate player action against game rules."""
        required_fields = ["type", "content"]
        return all(field in action for field in required_fields)

    async def _process_end_of_round(self) -> None:
        """Process end of round updates and checks."""
        # Update game state
        await self.dm.update_world_state()
        
        # Check for game ending conditions
        if await self._check_game_end_conditions():
            self.session.active = False
            await self.broadcast_message({
                "type": "game_end",
                "round": self.session.round_number
            })

    async def _check_game_end_conditions(self) -> bool:
        """Check if game should end."""
        # Add your game ending conditions here
        return False

    def save_game_state(self, filepath: str) -> None:
        """Save current game state to file."""
        if not self.session:
            logger.error("Attempted to save game state without active session")
            raise ValueError("No active session to save")
        
        try:
            logger.info(f"Saving game state to {filepath}")
            state = {
                "session": {
                    "id": self.session.session_id,
                    "round": self.session.round_number,
                    "start_time": self.session.start_time.isoformat(),
                    "game_state": self.session.game_state
                },
                "dm_state": self.dm.get_state() if self.dm else None,
                "players": [player.get_state() for player in self.players]
            }
            
            with open(filepath, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info("Game state saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving game state: {str(e)}", exc_info=True)
            raise

import asyncio
import logging
import traceback
from datetime import datetime
from .agents.game_coordinator import GameCoordinator

# Configure root logger with more detailed formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'game_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()  # Also output to console
    ]
)
logger = logging.getLogger(__name__)

async def main():
    # Initial scenario configuration
    scenario_config = {
        "world_config": {
            "locations": [
                {
                    "name": "tavern",
                    "description": "A cozy tavern with wooden tables and a warm fireplace",
                    "connected_to": ["street", "cellar"],
                    "npcs": ["barkeep"],
                    "items": ["mug", "chair"],
                    "atmosphere": "warm and welcoming"
                },
                {
                    "name": "street",
                    "description": "A cobblestone street with various shops",
                    "connected_to": ["tavern", "market"],
                    "npcs": ["guard"],
                    "items": ["barrel"],
                    "atmosphere": "busy"
                }
            ],
            "npcs": [
                {
                    "name": "barkeep",
                    "role": "merchant",
                    "location": "tavern",
                    "dialog_state": {"quest_given": False}
                },
                {
                    "name": "guard",
                    "role": "guard",
                    "location": "street"
                }
            ],
            "initial_state": {
                "time_of_day": "morning",
                "weather": "sunny",
                "active_quests": ["Find the missing shipment"]
            }
        },
        "players": [
            {
                "name": "Thorgar",
                "class": "Fighter",
                "race": "Dwarf",
                "stats": {
                    "STR": 16,
                    "DEX": 12,
                    "CON": 14,
                    "INT": 10,
                    "WIS": 12,
                    "CHA": 8
                },
                "personality": {
                    "traits": ["Brave", "Direct"],
                    "ideals": ["Honor", "Duty"],
                    "bonds": ["Protect the town"],
                    "flaws": ["Stubborn"]
                },
                "inventory": [
                    {"name": "Short Sword", "type": "weapon"}
                ],
                "initial_goal": "Find information about the missing shipment"
            }
        ]
    }

    try:
        # Initialize game coordinator
        coordinator = GameCoordinator()
        logger.info("Game coordinator initialized")

        # Initialize game with scenario
        await coordinator.initialize_game(scenario_config)
        logger.info("Game initialized with scenario")

        # Start the game
        logger.info("Starting game session")
        await coordinator.start_game()

    except Exception as e:
        logger.error(
            "Error during game execution",
            exc_info=True,  # This will include the full traceback
            stack_info=True  # This will include the current stack frame
        )
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Game terminated by user")
    except Exception as e:
        logger.error(
            "Unexpected error occurred",
            exc_info=True,
            stack_info=True
        )
        # Print the full traceback to console as well
        print("\nFull traceback:")
        traceback.print_exc()

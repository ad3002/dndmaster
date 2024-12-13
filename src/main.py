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

async def print_round_summary(coordinator: GameCoordinator, round_num: int) -> None:
    """Print a summary of what happened in the current round."""
    print("\n" + "="*50)
    print(f"\nRound {round_num} Summary:")
    print("-"*20)
    
    current_state = coordinator.dm.get_world_state()
    
    # Time and location info
    print(f"Time of day: {current_state['world_state']['time_of_day']}")
    print(f"Location: {current_state['world_state']['current_location']}")
    
    # Last actions and their results
    print("\nActions taken this round:")
    for player in coordinator.players:
        last_actions = player.get_recent_memories(1)
        if last_actions:
            action = last_actions[0].content
            print(f"\n{player.name}:")
            print(f"- Action: {action.get('type', 'unknown')}")
            print(f"- Description: {action.get('content', 'No description')}")
            if 'result' in action:
                print(f"- Outcome: {action['result'].get('message', 'No result')}")
                if 'details' in action['result']:
                    print(f"- Details: {action['result']['details']}")

    # Quest progress
    if 'active_quests' in current_state['world_state']:
        print("\nActive Quests:")
        for quest in current_state['world_state']['active_quests']:
            progress = current_state['world_state']['global_state'].get('main_quest_progress', 0)
            print(f"- {quest} (Progress: {progress})")
    
    print("\nCurrent Scene:")
    print(f"- NPCs present: {', '.join(npc['name'] for npc in current_state['active_npcs'])}")
    print(f"- Available actions: {', '.join(current_state.get('possible_actions', []))}")
    
    print("\n" + "="*50)
    
    print("\nPress Enter to continue to next round...")
    await asyncio.get_event_loop().run_in_executor(None, input)

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
        print("\nWelcome to the D&D game session!")
        print("Press Enter to begin the adventure...")
        await asyncio.get_event_loop().run_in_executor(None, input)

        # Start game loop
        current_round = 0
        await coordinator.start_game()

        while coordinator.session and coordinator.session.active:
            if coordinator.session.round_number > current_round:
                # Print summary of completed round
                await print_round_summary(coordinator, current_round)
                current_round = coordinator.session.round_number
            
            await asyncio.sleep(0.1)  # Prevent CPU overload

        # Print final game summary
        print("\nGame Completed!")
        await print_round_summary(coordinator, current_round)
        
        print("\nPress Enter to exit...")
        await asyncio.get_event_loop().run_in_executor(None, input)

    except Exception as e:
        logger.error(
            "Error during game execution",
            exc_info=True,
            stack_info=True
        )
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Game terminated by user")
        print("\nGame terminated by user")
    except Exception as e:
        logger.error(
            "Unexpected error occurred",
            exc_info=True,
            stack_info=True
        )
        # Print the full traceback to console as well
        print("\nFull traceback:")
        traceback.print_exc()

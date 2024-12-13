import asyncio
from agents.game_coordinator import GameCoordinator

async def main():
    coordinator = GameCoordinator()
    await coordinator.run_game_loop()

if __name__ == "__main__":
    asyncio.run(main())

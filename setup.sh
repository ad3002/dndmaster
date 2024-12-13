#!/bin/bash

# Create main project directory structure
mkdir -p src/agents src/utils tests docs

# Create main Python files
touch src/__init__.py
touch src/agents/__init__.py
touch src/utils/__init__.py

# Create agent files
cat > src/agents/base_agent.py << EOL
from typing import Dict, Any, List

class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.memory: List[Dict[str, Any]] = []
        self.state: Dict[str, Any] = {}
EOL

cat > src/agents/dungeon_master.py << EOL
from .base_agent import BaseAgent
EOL

cat > src/agents/player_character.py << EOL
from .base_agent import BaseAgent
EOL

cat > src/agents/game_coordinator.py << EOL
import asyncio
EOL

# Create utility files
cat > src/utils/llm_client.py << EOL
async def call_llm(prompt: str) -> str:
    # TODO: Implement actual LLM call
    return f"[LLM response to '{prompt}']"
EOL

# Create test files
touch tests/__init__.py
touch tests/test_base_agent.py
touch tests/test_dungeon_master.py
touch tests/test_player_character.py
touch tests/test_game_coordinator.py

# Create documentation files
touch docs/api.md
touch docs/user_guide.md

# Create requirements file
cat > requirements.txt << EOL
pytest
asyncio
EOL

# Create main game script
cat > src/main.py << EOL
import asyncio
from agents.game_coordinator import GameCoordinator

async def main():
    coordinator = GameCoordinator()
    await coordinator.run_game_loop()

if __name__ == "__main__":
    asyncio.run(main())
EOL

# Make setup.sh executable
chmod +x setup.sh

echo "Project structure created successfully!"

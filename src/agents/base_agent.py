from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
import json

@dataclass
class Message:
    content: Dict[str, Any]
    sender: str
    timestamp: datetime
    message_type: str

class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.memory: List[Message] = []
        self.state: Dict[str, Any] = {
            "status": "active",
            "last_action_timestamp": None,
            "current_context": {},
        }
        self.max_memory_size = 100

    async def process_message(self, message: Dict[str, Any], sender: str) -> None:
        """Process incoming message and store it in memory."""
        new_message = Message(
            content=message,
            sender=sender,
            timestamp=datetime.now(),
            message_type=message.get("type", "default")
        )
        self._add_to_memory(new_message)
        await self._update_state(new_message)

    async def generate_response(self, message: Dict[str, Any], sender: str) -> Dict[str, Any]:
        """Generate a response to a received message."""
        context = self._build_context(message, sender)
        response = {
            "type": "response",
            "sender": self.name,
            "timestamp": datetime.now().isoformat(),
            "content": f"{self.name} acknowledges message from {sender}",
            "context": context
        }
        return response

    def get_recent_memories(self, limit: int = 5, message_type: Optional[str] = None) -> List[Message]:
        """Retrieve recent memories, optionally filtered by message type."""
        if message_type:
            filtered_memories = [m for m in self.memory if m.message_type == message_type]
            return filtered_memories[-limit:]
        return self.memory[-limit:]

    def get_state(self) -> Dict[str, Any]:
        """Get current agent state."""
        return self.state.copy()

    def update_state(self, updates: Dict[str, Any]) -> None:
        """Update agent state with new values."""
        self.state.update(updates)
        self.state["last_updated"] = datetime.now().isoformat()

    def save_state(self, filepath: str) -> None:
        """Save agent state to file."""
        state_data = {
            "name": self.name,
            "state": self.state,
            "memory": [
                {
                    "content": msg.content,
                    "sender": msg.sender,
                    "timestamp": msg.timestamp.isoformat(),
                    "message_type": msg.message_type
                }
                for msg in self.memory
            ]
        }
        with open(filepath, 'w') as f:
            json.dump(state_data, f, indent=2)

    def load_state(self, filepath: str) -> None:
        """Load agent state from file."""
        with open(filepath, 'r') as f:
            state_data = json.load(f)
        
        self.name = state_data["name"]
        self.state = state_data["state"]
        self.memory = [
            Message(
                content=msg["content"],
                sender=msg["sender"],
                timestamp=datetime.fromisoformat(msg["timestamp"]),
                message_type=msg["message_type"]
            )
            for msg in state_data["memory"]
        ]

    def _add_to_memory(self, message: Message) -> None:
        """Add message to memory, maintaining size limit."""
        self.memory.append(message)
        if len(self.memory) > self.max_memory_size:
            self.memory = self.memory[-self.max_memory_size:]

    async def _update_state(self, message: Message) -> None:
        """Update internal state based on received message."""
        self.state["last_action_timestamp"] = message.timestamp.isoformat()
        self.state["last_interaction"] = {
            "with": message.sender,
            "type": message.message_type
        }

    def _build_context(self, message: Dict[str, Any], sender: str) -> Dict[str, Any]:
        """Build context for response generation."""
        return {
            "recent_interactions": [
                {"sender": m.sender, "type": m.message_type}
                for m in self.get_recent_memories(3)
            ],
            "current_state": self.get_state(),
            "current_message": {
                "sender": sender,
                "type": message.get("type", "default")
            }
        }

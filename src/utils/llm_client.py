import os
import json
import asyncio
from typing import Dict, Any, Optional, List, Type, TypeVar
from openai import AsyncOpenAI, OpenAIError, APIError, RateLimitError
from dataclasses import dataclass
from dotenv import load_dotenv

from .schemas import (
    SceneDescription, 
    DialogResponse, 
    CharacterAction, 
    CombatAction, 
    QuestInfo,
    DMResponse,
    NPCResponse,
    ItemChange
)

T = TypeVar('T')

@dataclass
class LLMConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 1000
    retry_attempts: int = 3
    retry_delay: float = 1.0

class LLMClient:
    def __init__(self, config: Optional[LLMConfig] = None):
        load_dotenv()  # Load environment variables from .env file
        
        # Load API key from environment variable
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.config = config or LLMConfig()

    async def call_llm(
        self, 
        prompt: str,
        system_prompt: str = "You are a helpful AI assistant.",
        **kwargs
    ) -> str:
        """
        Call the LLM with retry logic and error handling.
        
        Args:
            prompt: The user's prompt
            system_prompt: The system message to set context
            **kwargs: Additional parameters to override defaults
        
        Returns:
            Generated text response
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(self.config.retry_attempts):
            try:
                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=kwargs.get('temperature', self.config.temperature),
                    max_tokens=kwargs.get('max_tokens', self.config.max_tokens)
                )
                return response.choices[0].message.content

            except RateLimitError as e:
                if attempt == self.config.retry_attempts - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                
            except (APIError, OpenAIError) as e:
                if attempt == self.config.retry_attempts - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay)

    async def chat_with_schema(
        self,
        prompt: str,
        response_format: Type[T],
        system_prompt: str = "You are a helpful AI assistant.",
        **kwargs
    ) -> T:
        """Generic method for structured chat completion."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        for attempt in range(self.config.retry_attempts):
            try:
                completion = await self.client.beta.chat.completions.parse(
                    model=self.config.model,
                    messages=messages,
                    response_format=response_format,
                    temperature=kwargs.get('temperature', self.config.temperature),
                    max_tokens=kwargs.get('max_tokens', self.config.max_tokens)
                )
                
                response = completion.choices[0].message
                if response.parsed:
                    return response.parsed
                elif response.refusal:
                    raise ValueError(f"Model refused to respond: {response.refusal}")
                
            except RateLimitError as e:
                if attempt == self.config.retry_attempts - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
            
            except (APIError, OpenAIError) as e:
                if attempt == self.config.retry_attempts - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay)

    async def generate_scene_description(self, scene_context: Dict[str, Any]) -> SceneDescription:
        """Generate structured scene description."""
        system_prompt = """
        You are a skilled Dungeon Master narrating a D&D game.
        Provide vivid, atmospheric descriptions that engage players' imagination.
        Structure your response to include visible elements and possible actions.
        """
        
        prompt = f"""
        Describe the following scene in a D&D style:
        Location: {scene_context.get('location', 'unknown')}
        Time: {scene_context.get('time', 'day')}
        Atmosphere: {scene_context.get('atmosphere', 'neutral')}
        Elements: {', '.join(scene_context.get('elements', []))}
        """
        
        return await self.chat_with_schema(
            prompt=prompt,
            response_format=SceneDescription,
            system_prompt=system_prompt,
            temperature=0.8
        )

    async def generate_character_response(
        self,
        character_info: Dict[str, Any],
        situation: str
    ) -> DialogResponse:
        """Generate structured in-character responses."""
        system_prompt = f"""
        You are role-playing a D&D character with the following traits:
        Name: {character_info.get('name')}
        Class: {character_info.get('class')}
        Personality: {character_info.get('personality')}
        Background: {character_info.get('background')}
        
        Respond in character with structured information about the response.
        """
        
        return await self.chat_with_schema(
            prompt=situation,
            response_format=DialogResponse,
            system_prompt=system_prompt,
            temperature=0.9
        )

    async def generate_character_action(
        self,
        character_info: Dict[str, Any],
        context: Dict[str, Any]
    ) -> CharacterAction:
        """Generate structured character action decision."""
        system_prompt = f"""
        You are deciding actions for a D&D character with these traits:
        Name: {character_info.get('name')}
        Class: {character_info.get('class')}
        Current Goal: {character_info.get('current_goal')}
        
        Choose an action that fits the character's personality and current situation.
        """
        
        prompt = f"""
        Consider the current situation:
        Scene: {context.get('scene')}
        Available Actions: {context.get('available_actions', [])}
        Recent Events: {context.get('recent_events', [])}
        
        What would this character do next?
        """
        
        return await self.chat_with_schema(
            prompt=prompt,
            response_format=CharacterAction,
            system_prompt=system_prompt,
            temperature=0.8
        )

    async def generate_dm_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate DM's response to player action."""
        system_prompt = """
        You are a Dungeon Master in a D&D game. Interpret the player's action and generate an appropriate response.
        Consider the current context and generate a response that:
        1. Acknowledges the player's intended action
        2. Provides appropriate consequences
        3. Maintains game flow and narrative
        4. Keeps responses concise but descriptive
        
        Your response should be natural and avoid saying "invalid action" - interpret any action in a way that makes sense
        in the context of the game world.
        """
        
        prompt = f"""
        Current context:
        Location: {context['location']}
        Time: {context['time']}
        
        Player's action:
        Type: {context['action'].get('type')}
        Description: {context['action'].get('content')}
        
        Available NPCs: {[npc.name for npc in context['current_npcs']]}
        
        How does this action play out in the scene?
        """
        
        response = await self.chat_with_schema(
            prompt=prompt,
            response_format=DMResponse,  # Новая схема, определенная ниже
            system_prompt=system_prompt,
            temperature=0.7
        )
        
        return response.dict()

# Create a global instance for easy import
default_client = LLMClient()
call_llm = default_client.call_llm

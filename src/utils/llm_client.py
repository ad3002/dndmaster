import os
import json
import asyncio
from typing import Dict, Any, Optional, List
import openai
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class LLMConfig:
    model: str = "4o-mini"
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
        
        openai.api_key = self.api_key
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
                response = await openai.ChatCompletion.acreate(
                    model=self.config.model,
                    messages=messages,
                    temperature=kwargs.get('temperature', self.config.temperature),
                    max_tokens=kwargs.get('max_tokens', self.config.max_tokens)
                )
                return response.choices[0].message.content

            except openai.error.RateLimitError:
                if attempt == self.config.retry_attempts - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                
            except openai.error.APIError as e:
                if attempt == self.config.retry_attempts - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay)

    async def generate_scene_description(self, scene_context: Dict[str, Any]) -> str:
        """Special method for generating D&D scene descriptions."""
        system_prompt = """
        You are a skilled Dungeon Master narrating a D&D game.
        Provide vivid, atmospheric descriptions that engage players' imagination.
        Keep descriptions concise but evocative.
        """
        
        prompt = f"""
        Describe the following scene in a D&D style:
        Location: {scene_context.get('location', 'unknown')}
        Time: {scene_context.get('time', 'day')}
        Atmosphere: {scene_context.get('atmosphere', 'neutral')}
        Key elements: {', '.join(scene_context.get('elements', []))}
        """
        
        return await self.call_llm(prompt, system_prompt, temperature=0.8)

    async def generate_character_response(
        self,
        character_info: Dict[str, Any],
        situation: str
    ) -> str:
        """Generate in-character responses for NPCs or PCs."""
        system_prompt = f"""
        You are role-playing a D&D character with the following traits:
        Name: {character_info.get('name')}
        Class: {character_info.get('class')}
        Personality: {character_info.get('personality')}
        Background: {character_info.get('background')}
        
        Respond in character, maintaining consistent personality and speech patterns.
        """
        
        return await self.call_llm(situation, system_prompt, temperature=0.9)

# Create a global instance for easy import
default_client = LLMClient()
call_llm = default_client.call_llm

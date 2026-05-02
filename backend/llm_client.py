"""
llm_client.py
Unified LLM client factory that supports multiple providers (Groq, OpenAI, Gemini).
Allows switching providers by changing a single env variable: LLM_PROVIDER
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv(override=True)


class LLMClient:
    """
    Unified interface for different LLM providers.
    Supports: Groq, OpenAI, Google Gemini
    """
    
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize LLM client based on provider.
        
        Args:
            provider: Override the LLM_PROVIDER env var (groq, openai, gemini)
            model: Override the provider-specific model env var
        """
        self.provider = (provider or os.getenv("LLM_PROVIDER", "groq")).lower()
        self.client = None
        self.model = model
        
        if self.provider == "groq":
            self._init_groq()
        elif self.provider == "openai":
            self._init_openai()
        elif self.provider == "gemini":
            self._init_gemini()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}. Supported: groq, openai, gemini")
    
    def _init_groq(self):
        """Initialize Groq client"""
        from groq import Groq
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        self.client = Groq(api_key=api_key)
        self.model = self.model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        self.model = self.model or os.getenv("OPENAI_MODEL", "gpt-4o")
    
    def _init_gemini(self):
        """Initialize Google Gemini client"""
        import google.generativeai as genai
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        genai.configure(api_key=api_key)
        self.model = self.model or os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        self.client = genai.GenerativeModel(self.model)
    
    def chat_completion(
        self,
        messages: list,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Unified chat completion interface across providers.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Response format (e.g., {"type": "json_object"})
        
        Returns:
            Generated text response
        """
        if self.provider in ["groq", "openai"]:
            return self._openai_style_completion(messages, temperature, max_tokens, response_format)
        elif self.provider == "gemini":
            return self._gemini_completion(messages, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _openai_style_completion(
        self,
        messages: list,
        temperature: float,
        max_tokens: Optional[int],
        response_format: Optional[Dict[str, Any]]
    ) -> str:
        """OpenAI/Groq style completion (both use same API format)"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        
        if response_format:
            kwargs["response_format"] = response_format
        
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()
    
    def _gemini_completion(
        self,
        messages: list,
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """Google Gemini style completion"""
        # Convert OpenAI-style messages to Gemini format
        # Gemini uses a different message format
        system_instruction = None
        chat_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                chat_messages.append({"role": "user", "parts": [msg["content"]]})
            elif msg["role"] == "assistant":
                chat_messages.append({"role": "model", "parts": [msg["content"]]})
        
        # Recreate model with system instruction if provided
        if system_instruction:
            import google.generativeai as genai
            self.client = genai.GenerativeModel(
                self.model,
                system_instruction=system_instruction
            )
        
        generation_config = {
            "temperature": temperature,
        }
        
        if max_tokens:
            generation_config["max_output_tokens"] = max_tokens
        
        # For single-turn conversations (most common case)
        if len(chat_messages) == 1 and chat_messages[0]["role"] == "user":
            response = self.client.generate_content(
                chat_messages[0]["parts"][0],
                generation_config=generation_config
            )
        else:
            # For multi-turn conversations
            chat = self.client.start_chat(history=chat_messages[:-1])
            response = chat.send_message(
                chat_messages[-1]["parts"][0],
                generation_config=generation_config
            )
        
        return response.text.strip()
    
    def get_model_name(self) -> str:
        """Return the current model name"""
        return self.model
    
    def get_provider(self) -> str:
        """Return the current provider name"""
        return self.provider


def get_llm_client(provider: Optional[str] = None, model: Optional[str] = None) -> LLMClient:
    """
    Factory function to get an LLM client instance.
    
    Args:
        provider: Override LLM_PROVIDER env var (groq, openai, gemini)
        model: Override provider-specific model env var
    
    Returns:
        LLMClient instance
    
    Example:
        # Use default from env
        client = get_llm_client()
        
        # Override provider
        client = get_llm_client(provider="openai")
        
        # Override both
        client = get_llm_client(provider="groq", model="llama-3.1-70b-versatile")
    """
    return LLMClient(provider=provider, model=model)


# Convenience function for backward compatibility
def create_chat_completion(
    messages: list,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    response_format: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None
) -> str:
    """
    Create a chat completion using the configured LLM provider.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        response_format: Response format (e.g., {"type": "json_object"})
        provider: Override LLM_PROVIDER env var
        model: Override provider-specific model env var
    
    Returns:
        Generated text response
    """
    client = get_llm_client(provider=provider, model=model)
    return client.chat_completion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format
    )

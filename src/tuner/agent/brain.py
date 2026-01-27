import litellm
import os
from typing import List, Dict, Any, Optional

class AgentBrain:
    def __init__(self, model: str = "gpt-4o", fallbacks: List[str] = None):
        self.model = model
        self.fallbacks = fallbacks or [
            "gemini/gemini-1.5-flash",
            "claude-3-5-sonnet-20240620"
        ]

        # Configure LiteLLM
        litellm.drop_params = True
        # litellm.set_verbose = True # For debugging

        # Context window mapping for intelligent fallback
        self.context_window_fallback_dict = {
            "ollama/qwen2.5-coder": "gemini/gemini-1.5-flash",
            "gemini/gemini-1.5-flash": "gpt-4o-128k",
            "gpt-4o": "gpt-4o-128k"
        }

    async def think(self, messages: List[Dict[str, str]], tools: Optional[List[Dict]] = None) -> Any:
        """
        Execute the thinking process (Async).
        Returns the LiteLLM response object.
        """
        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto" if tools else None,
                fallbacks=self.fallbacks,
                context_window_fallback_dict=self.context_window_fallback_dict
            )
            return response
        except Exception as e:
            # Just re-raise for now, the agent loop should handle it
            raise e

    def get_token_usage(self, response: Any) -> Dict[str, int]:
        """Extract token usage from response."""
        if hasattr(response, "usage"):
            return {
                "input": response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
                "total": response.usage.total_tokens
            }
        return {"input": 0, "output": 0, "total": 0}

    def get_tool_calls(self, response: Any) -> List[Dict]:
        """Extract tool calls from response safely."""
        try:
            message = response.choices[0].message
            if hasattr(message, "tool_calls") and message.tool_calls:
                return [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        },
                        "type": tc.type
                    }
                    for tc in message.tool_calls
                ]
        except (AttributeError, IndexError):
            pass
        return []

    def get_content(self, response: Any) -> str:
        """Extract text content."""
        try:
            return response.choices[0].message.content or ""
        except (AttributeError, IndexError):
            return ""

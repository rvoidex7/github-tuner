import asyncio
import json
import logging
from typing import List, Dict, Any, Optional

from tuner.agent.brain import AgentBrain
from tuner.agent.tools import AgentTools
from tuner.agent.memory import AgentMemory
from tuner.agent.analysis import HeuristicGuard, CodeAnalyzer
from tuner.storage import TunerStorage

logger = logging.getLogger(__name__)

class EngineerAgent:
    def __init__(self, db_path: str = "data/tuner.db"):
        self.storage = TunerStorage(db_path)
        self.memory = AgentMemory(self.storage)
        self.brain = AgentBrain()

        # Perception & Analysis
        self.guard = HeuristicGuard()
        self.analyzer = CodeAnalyzer()

        # Tools
        self.tools = AgentTools(guard=self.guard)
        self.tool_definitions = self.tools.get_definitions()

        # State
        self.max_turns = 15
        self.session_id: Optional[str] = None
        self.running = False

        # Stats
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

        # Initialize
        self.analyzer.index_project(".") # Index self for clone detection

    async def start_mission(self, mission_goal: str):
        """Start the autonomous engineering loop."""
        self.running = True
        self.session_id = await self.memory.create_session(
            target_repo=mission_goal,
            model_config={"model": self.brain.model}
        )

        # System Prompt
        system_message = {
            "role": "system",
            "content": f"""You are an Autonomous Software Engineer for the GitHub Tuner project.
Your goal is: {mission_goal}

You operate in a continuous loop: OBSERVE -> THINK -> ACT.
1. Use `run_shell` to explore the codebase (ls, grep, etc.).
2. Use `read_file` to understand specific files.
3. Analyze the code structure.
4. If you find issues or improvements, use `write_file` to modify code safely.
5. Always verify your changes with tests (`pytest`) before committing.
6. Use `git_commit` when a sub-task is complete and verified.

Constraints:
- Do NOT hallucinate file paths. Check with `ls` first.
- If a file is large, read it in chunks or use `grep`.
- Respect the existing code style.
- Create a .bak backup before overwriting critical files (the tool does this automatically).
"""
        }

        # Context History
        messages = [system_message]

        turn_count = 0
        try:
            while self.running and turn_count < self.max_turns:
                turn_count += 1
                logger.info(f"🔄 Turn {turn_count}/{self.max_turns}")

                # 1. THINK
                # Call LLM with current history + tools
                response = await self.brain.think(messages, tools=self.tool_definitions)

                # Process Response
                response_message = response.choices[0].message
                content = response_message.content or ""
                tool_calls = self.brain.get_tool_calls(response)

                # Add to history
                messages.append(response_message)

                # Update Stats
                in_tok = response.usage.prompt_tokens
                out_tok = response.usage.completion_tokens
                self.total_input_tokens += in_tok
                self.total_output_tokens += out_tok
                # Rough cost est (GPT-4o)
                self.total_cost += (in_tok / 1_000_000 * 5.00) + (out_tok / 1_000_000 * 15.00)

                # Log to Memory (DB)
                await self.memory.log_turn(
                    self.session_id,
                    "assistant",
                    content,
                    tool_calls,
                    input_tokens=in_tok,
                    output_tokens=out_tok
                )

                # Emit UI event (if hooked)
                self.on_thought(content)

                # 2. ACT
                if tool_calls:
                    for tool_call in tool_calls:
                        func_name = tool_call["function"]["name"]
                        args_str = tool_call["function"]["arguments"]
                        call_id = tool_call["id"]

                        try:
                            args = json.loads(args_str)
                            self.on_action(func_name, args)

                            # Execute Tool
                            result = await self.tools.execute(func_name, args)

                            # 3. OBSERVE
                            # Feed result back to LLM
                            tool_message = {
                                "role": "tool",
                                "tool_call_id": call_id,
                                "name": func_name,
                                "content": result
                            }
                            messages.append(tool_message)

                            await self.memory.log_turn(
                                self.session_id,
                                "tool",
                                result[:1000] # Truncate log
                            )

                        except json.JSONDecodeError:
                            err_msg = "Error: Invalid JSON arguments."
                            messages.append({
                                "role": "tool",
                                "tool_call_id": call_id,
                                "name": func_name,
                                "content": err_msg
                            })
                else:
                    # No tool calls - just a thought or question
                    if "MISSION COMPLETE" in content:
                        logger.info("✅ Mission completed by agent.")
                        self.running = False
                        break

                # Safety break
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Agent crashed: {e}")
            raise e
        finally:
            self.running = False
            await self.storage.close()

    # UI Hooks (Overridden by TUI)
    def on_thought(self, text: str):
        pass

    def on_action(self, tool: str, args: Dict):
        pass

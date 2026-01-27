import os
import shutil
import asyncio
from typing import Dict, Any, List
from tuner.hunter import Hunter
from tuner.agent.perception import RSSReader, WebScraper
# Type hint only
# from tuner.agent.analysis import HeuristicGuard

class AgentTools:
    def __init__(self, guard=None):
        self.guard = guard
        self.rss_reader = RSSReader()
        self.web_scraper = WebScraper()

    def get_definitions(self) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the content of a file. Returns error if file not found.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path to file"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file. Creates a backup .bak file if it exists.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path to file"},
                            "content": {"type": "string", "description": "New content for the file"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_shell",
                    "description": "Run a safe shell command (ls, grep, git status, pytest, cat, find, pwd, git diff).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Shell command to execute"}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "classic_search",
                    "description": "Search GitHub using the legacy Hunter strategy.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query keywords"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_commit",
                    "description": "Commit changes to the current branch.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Commit message"}
                        },
                        "required": ["message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_web_page",
                    "description": "Fetch content from a URL using a stealth browser.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to fetch"}
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_rss",
                    "description": "Fetch latest entries from an RSS feed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "RSS Feed URL"}
                        },
                        "required": ["url"]
                    }
                }
            }
        ]

    async def read_file(self, path: str) -> str:
        if ".." in path or path.startswith("/"):
            return "Error: Path must be relative and cannot contain '..'"

        if not os.path.exists(path):
            return f"Error: File {path} not found."

        # Heuristic Check
        if self.guard:
            try:
                size = os.path.getsize(path)
                if not self.guard.should_analyze_file(path, size):
                    return f"Error: File blocked by Heuristic Guard (too large or invalid extension). Path: {path}, Size: {size} bytes."
            except OSError:
                pass

        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            return "Error: File is binary or not UTF-8."
        except Exception as e:
            return f"Error reading file: {e}"

    async def write_file(self, path: str, content: str) -> str:
        if ".." in path or path.startswith("/"):
            return "Error: Path must be relative and cannot contain '..'"

        try:
            # Create backup
            if os.path.exists(path):
                shutil.copy2(path, f"{path}.bak")

            # Ensure dir exists
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Success: Written to {path} (Backup created at {path}.bak)"
        except Exception as e:
            return f"Error writing file: {e}"

    async def run_shell(self, command: str) -> str:
        allowed_commands = ["ls", "grep", "git status", "pytest", "cat", "find", "pwd", "git diff"]

        is_allowed = False
        for allowed in allowed_commands:
            if command.strip().startswith(allowed):
                is_allowed = True
                break

        if not is_allowed:
            return f"Error: Command '{command}' is not in allowed list: {allowed_commands}"

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode() + stderr.decode()
            return output[:2000] if output else "Command executed with no output."
        except Exception as e:
            return f"Error executing command: {e}"

    async def classic_search(self, query: str) -> str:
        """Wraps Hunter search."""
        hunter = Hunter()
        try:
            items, _ = await hunter.search_raw(query, per_page=5)

            results = []
            for item in items:
                results.append(f"- {item['full_name']} (Stars: {item['stargazers_count']}): {item['html_url']}")

            return "\n".join(results) if results else "No results found."
        except Exception as e:
            return f"Error in search: {e}"
        finally:
            await hunter.close()

    async def git_commit(self, message: str) -> str:
        try:
            # git add .
            proc = await asyncio.create_subprocess_shell("git add .", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await proc.communicate()

            # git commit -m "message"
            # Using subprocess_exec to avoid shell injection in message
            proc = await asyncio.create_subprocess_exec("git", "commit", "-m", message, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()

            return (stdout.decode() + stderr.decode()) or "Commit successful."
        except Exception as e:
            return f"Error committing: {e}"

    async def fetch_web_page(self, url: str) -> str:
        result = await self.web_scraper.scrape_page(url)
        if "error" in result:
            return f"Error fetching page: {result['error']}"
        return f"Title: {result.get('title')}\n\nContent:\n{result.get('content')}"

    async def read_rss(self, url: str) -> str:
        entries = self.rss_reader.fetch_feed(url)
        if not entries:
            return "No entries found or error fetching feed."

        output = [f"Found {len(entries)} entries:"]
        for e in entries[:5]: # Limit to 5
            output.append(f"- {e['title']} ({e['link']})")
        return "\n".join(output)

    async def execute(self, tool_name: str, arguments: Dict) -> str:
        if tool_name == "read_file":
            return await self.read_file(arguments.get("path"))
        elif tool_name == "write_file":
            return await self.write_file(arguments.get("path"), arguments.get("content"))
        elif tool_name == "run_shell":
            return await self.run_shell(arguments.get("command"))
        elif tool_name == "classic_search":
            return await self.classic_search(arguments.get("query"))
        elif tool_name == "git_commit":
            return await self.git_commit(arguments.get("message"))
        elif tool_name == "fetch_web_page":
            return await self.fetch_web_page(arguments.get("url"))
        elif tool_name == "read_rss":
            return await self.read_rss(arguments.get("url"))
        else:
            return f"Error: Tool {tool_name} not found."

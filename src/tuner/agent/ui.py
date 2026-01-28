from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Log, Static
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from tuner.agent.core import EngineerAgent

class AgentDashboard(App):
    CSS = """
    Screen {
        layout: horizontal;
    }
    #left-panel {
        width: 65%;
        height: 100%;
        border: solid green;
    }
    #right-panel {
        width: 35%;
        height: 100%;
        border: solid blue;
    }
    Log {
        height: 1fr;
    }
    #stats-box {
        height: auto;
        border-bottom: solid white;
        padding: 1;
        background: $boost;
    }
    .stat-label {
        color: yellow;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, agent: EngineerAgent, mission: str):
        super().__init__()
        self.agent = agent
        self.mission = mission

        # Hook agent events
        self.agent.on_thought = self.on_thought_hook
        self.agent.on_action = self.on_action_hook

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Horizontal(
            Vertical(
                Log(id="thought_log", highlight=True, markup=True),
                id="left-panel",
            ),
            Vertical(
                Vertical(
                    Static("📊 Session Metrics", classes="stat-label"),
                    Static("Input Tokens: 0", id="in_tok"),
                    Static("Output Tokens: 0", id="out_tok"),
                    Static("Est. Cost: $0.00", id="cost_val"),
                    id="stats-box"
                ),
                Log(id="action_log", markup=True),
                id="right-panel"
            )
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#thought_log").write("🚀 System initialized.")
        self.query_one("#thought_log").write(f"🎯 Mission: [bold cyan]{self.mission}[/]")

        # Start agent
        self.run_worker(self.run_agent_loop(), exclusive=True)

    async def run_agent_loop(self):
        try:
            await self.agent.start_mission(self.mission)
            self.query_one("#thought_log").write("\n[bold green]🏁 Mission Ended.[/]")
        except Exception as e:
            self.query_one("#thought_log").write(f"\n[bold red]❌ Critical Error: {e}[/]")

    def on_thought_hook(self, text: str):
        self.call_from_thread(self.write_thought, text)
        self.call_from_thread(self.update_stats)

    def on_action_hook(self, tool: str, args: dict):
        self.call_from_thread(self.write_action, tool, args)
        self.call_from_thread(self.update_stats)

    def write_thought(self, text: str):
        self.query_one("#thought_log").write(f"🤖 {text}\n")

    def write_action(self, tool: str, args: dict):
        self.query_one("#action_log").write(f"🛠️ [bold magenta]{tool}[/]: {args}\n")

    def update_stats(self):
        self.query_one("#in_tok", Static).update(f"Input Tokens: {self.agent.total_input_tokens}")
        self.query_one("#out_tok", Static).update(f"Output Tokens: {self.agent.total_output_tokens}")
        self.query_one("#cost_val", Static).update(f"Est. Cost: [green]${self.agent.total_cost:.4f}[/]")

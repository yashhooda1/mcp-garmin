"""Run Garmin MCP locally through the OpenAI Agents SDK (read-only demo).

Install: pip install -e . && pip install openai-agents
Set OPENAI_API_KEY in your environment. No Garmin writes are enabled here.
"""
import asyncio
import os

from agents import Agent, Runner
from agents.mcp import MCPServerStdio, create_static_tool_filter


async def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY in your shell (never in source code)")
    async with MCPServerStdio(
        name="Garmin workouts",
        params={"command": "garmin-mcp", "args": [],
                "env": {**os.environ, "TRANSPORT": "stdio"}},
        tool_filter=create_static_tool_filter(allowed_tool_names=[
            "list_activities", "get_activity", "get_athlete_zones",
            "list_scheduled", "assess_fitness", "list_marathons",
            "pick_random_marathon",
        ]),
        client_session_timeout_seconds=30,
    ) as server:
        agent = Agent(
            name="Garmin training assistant",
            instructions=(
                "Use the Garmin MCP tools only to read the runner's history and calendar. "
                "Do not claim to have modified workouts or scheduled anything."
            ),
            mcp_servers=[server],
        )
        prompt = os.getenv(
            "RUNNER_PROMPT", "Summarize my latest runs and what's on my Garmin calendar."
        )
        result = await Runner.run(agent, prompt)
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())

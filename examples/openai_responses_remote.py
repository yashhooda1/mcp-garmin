"""OpenAI Responses API example for a hosted Garmin MCP server.

Install: pip install openai
Requires HTTPS /mcp endpoint and MCP_AUTH_TOKEN, no credentials in source.
The example never automatically approves MCP tool calls or writes.
"""
import os

from openai import OpenAI


def main() -> None:
    url = os.getenv("GARMIN_MCP_URL", "")
    token = os.getenv("GARMIN_MCP_TOKEN", "")
    if not url.startswith("https://") or not url.endswith("/mcp") or not token:
        raise SystemExit("Set GARMIN_MCP_URL=https://your-host/mcp and GARMIN_MCP_TOKEN")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY in your environment")

    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-6.1-sol"),
        input=os.getenv(
            "RUNNER_PROMPT", "What are my recent Garmin running activities?"
        ),
        tools=[{
            "type": "mcp",
            "server_label": "garmin",
            "server_url": url,
            "authorization": token,
            "require_approval": "always",
        }],
    )
    # An mcp_approval_request must be reviewed and approved by your application
    # in a separate call. This demonstration does not auto-approve.
    print(response.output_text or response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

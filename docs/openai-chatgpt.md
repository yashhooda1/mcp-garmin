# OpenAI Agents, Responses API, and ChatGPT

**This repository is not Claude-only.** Garmin MCP uses standard Model Context
Protocol and keeps all existing Garmin/Claude tools and configurations.

## 1. OpenAI Agents SDK — local stdio (no public server)

```bash
pip install -e ".[dev]"
pip install openai-agents
# First run garmin-mcp-auth locally to cache your Garmin session.
export OPENAI_API_KEY="your-openai-api-key"
python examples/openai_agents_local.py
```

The example only grants **read** tools. It does not allow the agent to
schedule, replace, or delete anything. Set `OPENAI_MODEL` to select a supported model; the example defaults to
`gpt-6.1-sol`.

## 2. OpenAI Responses API — remote Streamable HTTP

For a host you control, deploy over HTTPS and configure:

```bash
TRANSPORT=streamable-http
HOST=0.0.0.0
MCP_AUTH_TOKEN=<unique-random-secret>  # e.g., openssl rand -hex 32
GARMINTOKENS=/data/.garminconnect
```

Attach **persistent private storage** to the host and provision your existing
Garmin session there securely. Do not place Garmin passwords, Garmin session
tokens, OpenAI API keys, or MCP authentication secrets into the Git repository.

Then from your trusted machine:

```bash
pip install openai
export OPENAI_API_KEY="your-openai-api-key"
export GARMIN_MCP_URL="https://your-host.example/mcp"
export GARMIN_MCP_TOKEN="your-MCP_AUTH_TOKEN"
export OPENAI_MODEL="gpt-6.1-sol"
python examples/openai_responses_remote.py
```

The Responses API uses a remote MCP tool with `server_url`,
`authorization`, and `require_approval="always"`. Review any
`mcp_approval_request` before approving in your own application. The sample
does not publish or modify workouts. You can select another model that supports
MCP (e.g., `gpt-6-astra` or `gpt-6-luna`) by changing `OPENAI_MODEL`.

**Privacy:** the OpenAI API service receives tool descriptions, requested
arguments and returned Garmin data for the selected tool calls. Avoid hosting
an unauthenticated Garmin MCP server or passing access tokens in prompts.

## 3. ChatGPT custom MCP plugin — OAuth

ChatGPT web cannot directly launch a local stdio subprocess. For workspaces
that offer custom MCP plugins, use your public HTTPS `/mcp` endpoint or a
supported Secure MCP Tunnel.

For password-backed OAuth on your host add:

```bash
PUBLIC_BASE_URL=https://your-host.example
OAUTH_OWNER_PASSWORD=<unique-long-password>
OAUTH_STATE_DIR=/data/oauth
OAUTH_ALLOWED_REDIRECT_HOSTS=chatgpt.com,chat.openai.com,claude.ai,claude.com,localhost,127.0.0.1
```

Keep `MCP_AUTH_TOKEN` set; it continues to work for existing bearer clients
while connector users sign in with OAuth. The server now exposes:

- `/.well-known/oauth-protected-resource` (also supports the `/mcp` suffix)
- `/.well-known/oauth-authorization-server`
- `POST /oauth/register` (dynamic client registration with allowed redirect URIs)
- `GET/POST /oauth/authorize` (server-password sign-in, PKCE S256)
- `POST /oauth/token` (authorization-code and rotating refresh-token grants)

Advertised scopes include `workouts` and `offline_access`; refresh tokens
are issued, hashed at rest, and rotated. OAuth state must be on a **persistent,
private volume**, or connectors will lose their sessions after a restart.

In ChatGPT web, if your workspace is eligible and allows adding a custom MCP
server, go to **Plugins → Add custom MCP server** and provide
`https://your-host.example/mcp`, then choose the supported OAuth login.
This is an account/workspace permission, not a feature the Python repository
can grant. A verified live ChatGPT sign-in still requires deployment and
testing in your own workspace.

> **Important:** Garmin access through this repository is a **single-owner
> account**, not a multi-tenant service. Every authorized connector can read
> the same Garmin account and, subject to client approvals, can modify its
> training calendar. Do not give the OAuth password to other people.

## Verify without touching Garmin

```bash
pip install -e ".[dev]"
pytest -q tests/test_http_auth.py tests/test_oauth.py
ruff check .
```

Check the remote discovery endpoint over HTTPS:

```bash
curl -i https://your-host.example/.well-known/oauth-authorization-server
curl -i https://your-host.example/mcp
```

The second should return HTTP 401 without an access token, with a
`WWW-Authenticate` challenge pointing to protected-resource metadata.
Authenticated MCP tool discovery should work, but **do not run mutation
tools** when validating a personal Garmin account.

Read more:
- https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
- https://openai.github.io/openai-agents-python/mcp/

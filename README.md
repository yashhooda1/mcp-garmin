# garmin-mcp

[![ci](https://github.com/yashhooda1/mcp-garmin/actions/workflows/ci.yml/badge.svg)](https://github.com/yashhooda1/mcp-garmin/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![license: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> Replace `OWNER` in the badge and clone URLs with your GitHub username.

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant
(Claude, or any MCP client) **read your Garmin activities** and **create and
schedule structured workouts and multi-week training plans** directly on your
Garmin Connect calendar — where they sync to your watch with guided, rep-by-rep
prompts.

Describe a session in plain language and it lands on your watch:

```
"Schedule a 4×1mi threshold workout for Tuesday and a 16-miler with 4
 marathon-pace miles on Saturday."   →   built, scheduled, synced.
```

Built on [`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect)
(garth SSO auth) and the official MCP Python SDK. Activities are **read-only by
design**; write access is scoped to workouts and the training calendar.

---

## ⚠️ Read this first (security & terms)

- **No official individual API.** Garmin's API program is enterprise-only, so
  this uses Garmin's unofficial SSO via `garth`, like every Garmin automation
  tool. It can break if Garmin changes their login flow.
- **Long-lived tokens.** Auth caches a ~1-year token that grants full account
  access. Treat `GARMINTOKENS` like a production secret — it is git-ignored here.
- **Your own risk.** This may be against Garmin's Terms of Service. It's intended
  for personal use on your own account.
- **Lock down the HTTP transport.** A publicly reachable server that can write to
  a Garmin account is dangerous. The remote transport requires a bearer token
  (below). For most people, local `stdio` with Claude Desktop is the right
  choice.

---

## Quick start

```bash
git clone https://github.com/yashhooda1/mcp-garmin
cd mcp-garmin
pip install -e ".[dev]"

# one-time login — caches tokens to $GARMINTOKENS (default ~/.garminconnect)
export GARMINTOKENS="$HOME/.garminconnect"
garmin-mcp-auth          # prompts for email / password / MFA

pytest -q                # offline sanity check (no Garmin calls)
```

After auth, the server runs with **no credentials** in its environment — it
resumes from the cached tokens.

## Connect it to Claude

**Local (Claude Desktop, `stdio`)** — add to your Claude Desktop MCP config
(see `examples/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "garmin": {
      "command": "garmin-mcp",
      "env": { "TRANSPORT": "stdio", "GARMINTOKENS": "/Users/you/.garminconnect" }
    }
  }
}
```

**Remote (claude.ai custom connector, HTTP)** — deploy with the included
`Dockerfile` / `railway.toml`, then add the server URL (`https://<host>/mcp`) as
a custom connector. Required env on the host:

```
TRANSPORT=streamable-http
MCP_AUTH_TOKEN=<openssl rand -hex 32>      # clients must send Authorization: Bearer <token>
GARMINTOKENS=/data/.garminconnect          # mount a volume; upload tokens you generated locally
```

Without `MCP_AUTH_TOKEN` the server logs a loud warning and stays open — so set
it. Every HTTP request is checked with a constant-time bearer comparison; missing
or wrong tokens get a `401`.

---

## Tools

| Tool | Access | Description |
|---|---|---|
| `list_activities` | read | Recent activities (id, type, distance, HR…) |
| `get_activity` | read | Full detail for one activity |
| `get_athlete_zones` | read | Heart-rate zones / settings |
| `list_scheduled` | read | Workouts on the calendar |
| `create_workout` | write | Build a structured workout from a spec; optionally schedule |
| `schedule_workout` | write | Put an existing workout on a date |
| `delete_workout` | write | Delete a workout template |
| `unschedule_workout` | write | Remove a calendar occurrence |
| `create_training_plan` | write | Build + schedule a whole multi-week plan |
| `create_boulderthon_demo` | write | A bundled 13-week example plan |

## Workout spec

The format the assistant fills in — readable and unit-aware:

```python
WorkoutSpec(name="4x1mi threshold", steps=[
    StepSpec(kind="warmup",   duration="15:00", target="hr:2"),
    RepeatSpec(repeat=4, steps=[
        StepSpec(kind="run",      duration="1mi",  target="pace:6:35-6:55"),
        StepSpec(kind="recovery", duration="2:30", target="hr:2"),
    ]),
    StepSpec(kind="cooldown", duration="10:00", target="hr:2"),
])
```

- **Durations:** `"15:00"`/`"90s"` = time · `"1mi"`/`"1.5mi"`/`"400m"`/`"1km"` = distance
- **Targets:** `null` · `"hr:2"` (HR zone) · `"pace:6:35-6:55"` (pace window, min/mi)

Everything compiles to Garmin's exact `workout-service` JSON schema (validated
against `garminconnect` 0.3.6).

## Example: a full marathon block

`plans/boulderthon.py` is a complete 13-week marathon build expressed in this
spec — pace-targeted quality sessions, HR-zone easy/long runs, down weeks, two
20-milers, a marathon-pace rehearsal, and a taper. It's the worked example that
proves the plan engine. Dry-run it without touching Garmin:

```bash
python -c "from plans.boulderthon import build_plan; from garmin_mcp.plans import preview_plan; \
[print(r['date'], r['name']) for r in preview_plan(build_plan())]"
```

Write your own plan the same way: a list of `(date, WorkoutSpec)` via the
`week()` helper in `garmin_mcp.plans`, then `create_training_plan` (or
`push_plan`) schedules the lot, idempotently.

---

## Project structure

```
garmin-mcp/
├── src/garmin_mcp/
│   ├── server.py      FastMCP app + tools
│   ├── workouts.py    spec models + validated Garmin compiler
│   ├── plans.py       plan engine (week() helper, push/preview)
│   ├── auth.py        garth login + token cache + MFA
│   ├── http_auth.py   bearer-token gate for the HTTP transport
│   └── cli.py         garmin-mcp-auth
├── plans/boulderthon.py   example 13-week build as data
├── examples/          Claude Desktop config
├── tests/             offline build/serialize/auth tests (CI-safe, no network)
├── Dockerfile · railway.toml   remote deploy
└── .github/workflows/ci.yml
```

## Tests

```bash
pytest -q       # offline — compiles + serializes workouts, checks the auth gate
```

CI runs `ruff` + `pytest` on every push. No test makes a network call, so the
suite is safe to run anywhere without Garmin credentials.

---

## Why I built this

I wanted my running coach and my watch to be the same workflow. I follow
structured marathon training, but turning a coach's plan into Garmin workouts
meant tediously hand-building every interval session in the Garmin web UI, week
after week. Garmin has no individual API, so "just script it" isn't an option
out of the box.

So I reverse-engineered the workout schema, wrapped it in a typed,
LLM-friendly spec, and exposed it through MCP — so an assistant can take "give me
a 13-week sub-3 block" and turn it into 60+ scheduled, structured sessions on my
watch. Along the way it became a small but complete piece of engineering:

- **Protocol integration** — a real MCP server (stdio + streamable-HTTP) with
  least-privilege tool design (activities read-only, writes scoped to workouts).
- **Schema reverse-engineering** — a validated compiler from a friendly spec to
  Garmin's exact `workout-service` JSON, with pace/HR/distance targets and
  nested repeat groups.
- **Auth & security** — garth SSO with cached-token resumption and MFA, plus a
  constant-time bearer gate for safe remote deployment.
- **Operability** — typed Pydantic models, an offline test suite, CI, and
  one-command Docker/Railway deploy.

It scratched a real itch and doubles as a reference for building MCP servers
around closed, unofficial APIs.

## License

MIT. Not affiliated with or endorsed by Garmin.

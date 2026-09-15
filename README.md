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
| `assess_fitness` | read | Summarise recent training; size the gap to a goal time |
| `list_marathons` | read | Marathons in the catalogue inside a date window |
| `pick_random_marathon` | read | "Surprise me" — draw a race to train for |
| `create_workout` | write | Build a structured workout from a spec; optionally schedule |
| `create_strength_workout` | write | Build a guided strength/core session |
| `schedule_workout` | write | Put an existing workout on a date |
| `delete_workout` | write | Delete a workout template |
| `unschedule_workout` | write | Remove a calendar occurrence |
| `create_training_plan` | write | Build + schedule a whole multi-week plan |
| `create_marathon_plan` | plan | Any race, any goal — built from your actual fitness |
| `create_hs_track_plan` | plan | High-school 800 / 1600 / 3200 / 5K blocks |
| `create_houston_block` | plan | The bundled 24-week Chevron Houston build |
| `clear_scheduled` | plan | Wipe a date range off the calendar (dry-run first) |

Every plan-building tool schedules **two strength/core sessions a week** and
returns per-week nutrition, hydration and recovery guidance with the schedule.

## Training plans

### Marathon — any race, any goal, scaled to you

`create_marathon_plan` doesn't hand out a generic 16-week template. It reads
your recent Garmin activities, works out where you actually are (weekly mileage,
longest run, run frequency, best recent effort), and compares that to what the
goal time demands:

```
"Pick me a random marathon at least 20 weeks out and build me a 3:15 plan."
  → pick_random_marathon → assess_fitness → create_marathon_plan
```

- **Gap analysis.** A 3:15 marathon wants a ~50 mpw peak. If you're running 18
  and the race is 14 weeks out, an 8%/week ramp doesn't get you there — so the
  plan is built toward the goal the runway *does* support, and the report states
  plainly what the original goal would have needed. `force_goal=True` overrides
  this if you want it anyway.
- **Paces follow fitness, not the goal.** Base and build phases are paced off
  current fitness and converge on goal pace in the specific phase, so week 1
  isn't paced at week-20 fitness.
- **Structure.** 3-up-1-down cycles, a 3-week taper, long-run progression capped
  against current longest, and `heat_penalty_s_per_mile` (25–40 for a Gulf Coast
  summer) to soften early quality paces.

The race catalogue resolves each marathon's *next* running from its scheduling
rule (Boston = Patriots' Day, Berlin = last Sunday in September, …) and returns a
`date_certainty` flag — always confirm with the organiser before booking.

### High-school track — the four barriers

`create_hs_track_plan` builds toward **sub-2:00 800**, **sub-4:30 1600**,
**sub-10:00 3200** and **sub-15:00 5K** (or any goal you pass):

- `training_age` (`new` / `developing` / `experienced`) sets a hard weekly
  mileage ceiling; Sunday is a full rest day in every week; no doubles are ever
  scheduled; quality is capped at two sessions plus a meet.
- Supply `current_pr` and the gap analysis is honest: if sub-4:30 off a 5:05 PR
  is a two-season project, it says so and builds toward the PR this season can
  actually deliver.
- Nutrition guidance at this level is **adequacy-only** — eat enough, eat often,
  no calorie counts, no weight targets, no body-composition talk.
- The plan is a starting point to bring to the athlete's actual coach, not a
  replacement for one.

### Strength, nutrition and recovery — in every plan

- **2×/week strength**, scheduled on quality days so easy days stay easy and
  nothing lands the day before a long run. Day A is posterior chain (RDL, split
  squat, single-leg calf raise, row) plus anti-extension core; Day B is
  hip/pelvis control plus anti-rotation core. Down and race weeks swap the heavy
  day for a mobility reset — the habit never breaks, the load does. Dumbbells and
  a band are enough.
- **Fuelling and recovery per session.** Each workout's description carries its
  own fuel note (carbs/hour on a long run, protein window after a lift) and a
  recovery line, so the guidance is on the watch, not in a doc you never open.
- **Weekly brief.** Carbohydrate, protein, fat, timing, iron, hydration, sleep
  and load-watch guidance per week, returned with the plan.

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
against `garminconnect` 0.3.7).

## Example: a full marathon block

`plans/houston.py` is a complete 24-week Chevron Houston Marathon build
expressed in this spec — pace-targeted quality sessions with a Houston heat
allowance, HR-capped easy and long runs, eight real tune-up races on their
actual dates, down weeks, a 30K dress rehearsal, two strength days a week, and a
taper. It's the worked example that proves the plan engine. Dry-run it without
touching Garmin:

```bash
python -c "from plans.houston import build_plan; from garmin_mcp.plans import preview_plan; \
[print(r['date'], r['sport'], r['name']) for r in preview_plan(build_plan())]"
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
│   ├── workouts.py    running spec models + validated Garmin compiler
│   ├── strength.py    strength/core specs + compiler + the 2x/week prescription
│   ├── fitness.py     fitness snapshot, Riegel paces, gap analysis, mileage ramp
│   ├── fueling.py     per-session fuel/recovery notes + weekly nutrition briefs
│   ├── plans.py       plan engine (week() helper, push/preview, mixed sports)
│   ├── auth.py        garth login + token cache + MFA
│   ├── http_auth.py   bearer-token gate for the HTTP transport
│   └── cli.py         garmin-mcp-auth
├── plans/
│   ├── marathon.py    fitness-scaled marathon generator (any race, any goal)
│   ├── track_hs.py    high-school 800/1600/3200/5K generator
│   ├── races.py       marathon catalogue with date rules
│   └── houston.py     worked example: 24-week Houston build as data
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

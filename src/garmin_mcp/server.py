"""garmin-mcp server.

Tools (least-privilege):
  read   — list_activities, get_activity, get_athlete_zones, list_scheduled
  write  — create_workout, schedule_workout, delete_workout, unschedule_workout
  plan   — create_training_plan, create_boulderthon_demo

Activities are read-only: no tool creates, edits, or deletes an activity.
"""
from __future__ import annotations

import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .auth import get_client
from .workouts import WorkoutSpec, compile_workout
from .plans import push_plan, preview_plan

mcp = FastMCP("garmin-mcp")


# --------------------------------------------------------------------------- #
# read (activities) — strictly read-only
# --------------------------------------------------------------------------- #
@mcp.tool()
def list_activities(limit: int = 20, start: int = 0) -> list:
    """List recent activities (id, name, type, start time, distance, duration)."""
    acts = get_client().get_activities(start, limit)
    return [
        {
            "activityId": a.get("activityId"),
            "name": a.get("activityName"),
            "type": a.get("activityType", {}).get("typeKey"),
            "start": a.get("startTimeLocal"),
            "distance_m": a.get("distance"),
            "duration_s": a.get("duration"),
            "avg_hr": a.get("averageHR"),
        }
        for a in acts
    ]


@mcp.tool()
def get_activity(activity_id: int) -> dict:
    """Full detail for one activity by id."""
    return get_client().get_activity(activity_id)


@mcp.tool()
def get_athlete_zones() -> dict:
    """Heart-rate zones and related training settings for the athlete."""
    return get_client().get_heart_rate_zones() if hasattr(
        get_client(), "get_heart_rate_zones"
    ) else {"note": "zone endpoint not available in this garminconnect version"}


@mcp.tool()
def list_scheduled() -> list:
    """List workouts currently scheduled on the Garmin calendar."""
    return get_client().get_scheduled_workouts()


# --------------------------------------------------------------------------- #
# write (workouts + calendar) — scoped
# --------------------------------------------------------------------------- #
@mcp.tool()
def create_workout(spec: WorkoutSpec, schedule_date: Optional[str] = None,
                   replace: bool = True) -> dict:
    """Create a structured running workout from a spec; optionally schedule it.

    schedule_date is 'YYYY-MM-DD'. With replace=True a same-named workout is
    overwritten instead of duplicated.
    """
    client = get_client()
    if replace:
        existing = {w["workoutName"]: w["workoutId"] for w in client.get_workouts()}
        if spec.name in existing:
            client.delete_workout(existing[spec.name])
    result = client.upload_running_workout(compile_workout(spec))
    workout_id = result["workoutId"]
    out = {"workoutId": workout_id, "name": spec.name}
    if schedule_date:
        client.schedule_workout(workout_id, schedule_date)
        out["scheduled"] = schedule_date
    return out


@mcp.tool()
def schedule_workout(workout_id: int, date: str) -> dict:
    """Schedule an existing workout id on a date ('YYYY-MM-DD')."""
    return get_client().schedule_workout(workout_id, date)


@mcp.tool()
def delete_workout(workout_id: int) -> dict:
    """Delete a workout template by id."""
    get_client().delete_workout(workout_id)
    return {"deleted": workout_id}


@mcp.tool()
def unschedule_workout(schedule_id: int) -> dict:
    """Remove a scheduled workout occurrence from the calendar."""
    get_client().unschedule_workout(schedule_id)
    return {"unscheduled": schedule_id}


# --------------------------------------------------------------------------- #
# plan
# --------------------------------------------------------------------------- #
@mcp.tool()
def create_training_plan(name: str, items: list, replace: bool = True,
                         dry_run: bool = False) -> dict:
    """Create + schedule a multi-week plan.

    `items` is a list of {"date": "YYYY-MM-DD", "spec": <WorkoutSpec>}.
    dry_run=True validates and reports without sending anything to Garmin.
    """
    from .plans import TrainingPlan

    plan = TrainingPlan(
        name=name,
        items=[(it["date"], WorkoutSpec.model_validate(it["spec"])) for it in items],
    )
    if dry_run:
        return {"plan": name, "dry_run": True, "sessions": preview_plan(plan)}
    results = push_plan(get_client(), plan, replace=replace)
    return {"plan": name, "scheduled": len(results), "items": results}


@mcp.tool()
def create_boulderthon_demo(dry_run: bool = True) -> dict:
    """Build (and optionally push) the bundled 13-week Boulderthon sub-3 plan."""
    from plans.boulderthon import build_plan  # noqa: PLC0415

    plan = build_plan()
    if dry_run:
        return {"plan": plan.name, "dry_run": True, "sessions": preview_plan(plan)}
    results = push_plan(get_client(), plan, replace=True)
    return {"plan": plan.name, "scheduled": len(results), "items": results}


# --------------------------------------------------------------------------- #
# entrypoint
# --------------------------------------------------------------------------- #
def main() -> None:
    transport = os.environ.get("TRANSPORT", "stdio")
    if transport in ("sse", "streamable-http"):
        from .http_auth import serve_http

        host = os.environ.get("HOST", "0.0.0.0")
        port = int(os.environ.get("PORT", "8000"))
        token = os.environ.get("MCP_AUTH_TOKEN")
        serve_http(mcp, transport, host, port, token)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

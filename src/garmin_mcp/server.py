"""garmin-mcp server.

Tools (least-privilege):
  read   — list_activities, get_activity, get_athlete_zones, list_scheduled,
           assess_fitness, list_marathons, pick_random_marathon
  write  — create_workout, create_strength_workout, schedule_workout,
           delete_workout, unschedule_workout
  plan   — create_training_plan, create_marathon_plan, create_hs_track_plan,
           create_houston_block, clear_scheduled

Activities are read-only: no tool creates, edits, or deletes an activity.

Every plan-building tool here schedules two strength/core sessions a week and
returns nutrition and recovery guidance alongside the schedule.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .auth import get_client
from .fitness import summarize_fitness
from .plans import preview_plan, push_plan
from .strength import StrengthSpec, compile_strength
from .workouts import WorkoutSpec, compile_workout

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
def create_strength_workout(spec: StrengthSpec, schedule_date: Optional[str] = None,
                            replace: bool = True) -> dict:
    """Create a structured strength/core workout from a spec; optionally schedule it.

    Exercises are Garmin category/exerciseName pairs (e.g. category 'PLANK',
    exercise 'SIDE_PLANK'). Each exercise takes either `reps` or `hold`
    ('45s'), plus sets and rest_s. Lands on the watch as a guided strength
    workout with named exercises and a rep/hold counter.
    """
    client = get_client()
    if replace:
        existing = {w["workoutName"]: w["workoutId"] for w in client.get_workouts()}
        if spec.name in existing:
            client.delete_workout(existing[spec.name])
    result = client.upload_strength_workout(compile_strength(spec))
    workout_id = result["workoutId"]
    out = {"workoutId": workout_id, "name": spec.name, "sport": "strength"}
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


def _snapshot(weeks: int = 8):
    """Pull recent activities and reduce them to a fitness snapshot."""
    acts = get_client().get_activities(0, max(40, weeks * 7))
    rows = [
        {"type": a.get("activityType", {}).get("typeKey"),
         "start": a.get("startTimeLocal"),
         "distance_m": a.get("distance"),
         "duration_s": a.get("duration"),
         "name": a.get("activityName")}
        for a in acts
    ]
    return summarize_fitness(rows, weeks=weeks)


@mcp.tool()
def assess_fitness(goal_time: Optional[str] = None, race_date: Optional[str] = None,
                   weeks_of_history: int = 8,
                   current_weekly_miles: Optional[float] = None) -> dict:
    """Read-only: summarise recent training, and size the gap to a marathon goal.

    With no goal, returns the fitness snapshot alone (weekly mileage, longest
    run, run frequency, best recent effort). With `goal_time` ('3:15:00') and
    `race_date` ('2027-04-19'), also returns what the goal asks for, what a safe
    ramp from here actually reaches, and — when those disagree — the goal this
    runway does support.
    """
    from .fitness import assess_gap

    snap = _snapshot(weeks_of_history)
    out = {"fitness": snap.as_dict()}
    if goal_time and race_date:
        out["assessment"] = assess_gap(
            snap, goal_time, race_date, current_weekly_miles=current_weekly_miles
        ).as_dict()
    return out


@mcp.tool()
def list_marathons(min_weeks_out: int = 0, max_weeks_out: int = 104) -> list:
    """Marathons in the catalogue whose next running falls inside the window.

    Dates are computed from each race's usual scheduling rule and carry a
    `date_certainty` — confirm with the organiser before entering or booking.
    """
    from plans.races import list_races

    return list_races(min_weeks_out, max_weeks_out)


@mcp.tool()
def pick_random_marathon(min_weeks_out: int = 16, max_weeks_out: int = 104,
                         seed: Optional[int] = None) -> dict:
    """Pick a marathon at random from the catalogue — the 'surprise me' path.

    The 16-week floor keeps the draw to races there is still time to build for;
    lower it deliberately if you want a short-runway race.
    """
    from plans.races import random_race

    return random_race(min_weeks_out, max_weeks_out, seed=seed) or {
        "error": "no races in that window"
    }


@mcp.tool()
def create_marathon_plan(race_name: str, race_date: str, goal_time: str,
                         current_weekly_miles: Optional[float] = None,
                         days_per_week: int = 5, start_date: Optional[str] = None,
                         heat_penalty_s_per_mile: float = 0.0,
                         use_garmin_history: bool = True,
                         force_goal: bool = False, replace: bool = True,
                         dry_run: bool = True) -> dict:
    """Build a marathon block for ANY race and ANY goal, scaled to current fitness.

    Reads recent Garmin activity (unless `use_garmin_history=False` or
    `current_weekly_miles` is supplied), compares that to what the goal asks
    for, and builds a plan that ramps from where the runner actually is —
    8%/week ceiling, 3-up-1-down, 3-week taper, ending on race day.

    When the goal doesn't fit the weeks available, the plan is built toward the
    goal that does, and the report says exactly what the original would have
    needed. `force_goal=True` overrides that.

    Two strength sessions land on the calendar every week. The report carries
    weekly nutrition, hydration and recovery guidance. `heat_penalty_s_per_mile`
    (25-40 for a Gulf Coast summer) softens early-phase quality paces.

    dry_run=True validates and reports without sending anything to Garmin.
    """
    from plans.marathon import build_marathon_plan

    snap = _snapshot() if use_garmin_history and current_weekly_miles is None else None
    plan, report = build_marathon_plan(
        race_name=race_name, race_date=race_date, goal_time=goal_time,
        snapshot=snap, current_weekly_miles=current_weekly_miles,
        days_per_week=days_per_week, start_date=start_date,
        heat_penalty=heat_penalty_s_per_mile, force_goal=force_goal,
    )
    if dry_run:
        return {"plan": plan.name, "dry_run": True,
                "sessions": preview_plan(plan), "report": report}
    results = push_plan(get_client(), plan, replace=replace)
    return {"plan": plan.name, "scheduled": len(results), "items": results,
            "report": report}


@mcp.tool()
def create_hs_track_plan(event: str = "1600", goal_time: Optional[str] = None,
                         weeks: int = 16, start_date: Optional[str] = None,
                         current_pr: Optional[str] = None,
                         current_weekly_miles: float = 0.0,
                         training_age: str = "developing",
                         meet_days: Optional[list] = None,
                         replace: bool = True, dry_run: bool = True) -> dict:
    """Build a high-school track block: 800 / 1600 / 3200 / 5k.

    `goal_time` defaults to that event's barrier — sub-2:00 800, sub-4:30 1600,
    sub-10:00 3200, sub-15:00 5K — but any goal can be passed. Supply
    `current_pr` and the report sizes the gap honestly: if the goal is a
    two-season project, it says so and builds toward the PR this block can
    actually deliver.

    `training_age` is 'new' | 'developing' | 'experienced' and sets a hard weekly
    mileage ceiling. Sunday is a full rest day in every week; no doubles are ever
    scheduled; quality is capped at two sessions plus a meet.

    Nutrition guidance for this level is adequacy-only — eat enough, eat often,
    no calorie or weight targets — and the plan should be taken to the athlete's
    actual school coach before it is run.

    dry_run=True validates and reports without sending anything to Garmin.
    """
    from plans.track_hs import build_track_plan

    plan, report = build_track_plan(
        event=event, goal_time=goal_time, weeks=weeks, start_date=start_date,
        current_pr=current_pr, current_weekly_miles=current_weekly_miles,
        training_age=training_age, meet_days=meet_days,
    )
    if dry_run:
        return {"plan": plan.name, "dry_run": True,
                "sessions": preview_plan(plan), "report": report}
    results = push_plan(get_client(), plan, replace=replace)
    return {"plan": plan.name, "scheduled": len(results), "items": results,
            "report": report}


@mcp.tool()
def create_houston_block(start_date: Optional[str] = None, replace: bool = True,
                         dry_run: bool = True) -> dict:
    """Build + schedule the full 24-week Chevron Houston Marathon block.

    start_date must be a Monday ('YYYY-MM-DD'); defaults to 2026-08-03.

    Like every plan here, the block schedules two strength sessions a week on
    the quality days and returns per-week nutrition, hydration and recovery
    guidance alongside the schedule.

    dry_run=True validates and reports without sending anything to Garmin.
    """
    from plans.houston import build_plan, weekly_briefs

    plan = build_plan(date.fromisoformat(start_date) if start_date else None)
    report = {"weeks": weekly_briefs()}
    if dry_run:
        return {"plan": plan.name, "dry_run": True,
                "sessions": preview_plan(plan), "report": report}
    results = push_plan(get_client(), plan, replace=replace)
    return {"plan": plan.name, "scheduled": len(results), "items": results,
            "report": report}


def _sched_id(item: dict):
    """Garmin's scheduled-workout payload has drifted across versions."""
    for k in ("scheduleId", "workoutScheduleId", "id"):
        if item.get(k) is not None:
            return item[k]
    return None


def _sched_date(item: dict) -> str:
    for k in ("calendarDate", "date", "scheduledDate"):
        if item.get(k):
            return str(item[k])[:10]
    return ""


def _sched_name(item: dict) -> str:
    w = item.get("workout") or {}
    return w.get("workoutName") or item.get("workoutName") or "(unnamed)"


@mcp.tool()
def clear_scheduled(start_date: str, end_date: str, dry_run: bool = True) -> dict:
    """Unschedule every workout on the calendar in [start_date, end_date] inclusive.

    Destructive. Defaults to dry_run=True — call again with dry_run=False to commit.
    Removes calendar occurrences only; workout templates are left intact.
    """
    client = get_client()
    hits = []
    for item in client.get_scheduled_workouts():
        d = _sched_date(item)
        if d and start_date <= d <= end_date and _sched_id(item) is not None:
            hits.append({"date": d, "name": _sched_name(item),
                         "schedule_id": _sched_id(item)})
    hits.sort(key=lambda h: h["date"])

    if not hits:
        return {"range": [start_date, end_date], "found": 0, "unscheduled": 0}
    if dry_run:
        return {"range": [start_date, end_date], "found": len(hits),
                "dry_run": True, "would_unschedule": hits}

    for h in hits:
        client.unschedule_workout(h["schedule_id"])
    return {"range": [start_date, end_date], "found": len(hits),
            "unscheduled": len(hits), "items": hits}


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

"""Training-plan engine: take a list of (date, WorkoutSpec) and push them to
Garmin Connect as scheduled, structured workouts.

Idempotent: when replace=True, a same-named workout is deleted before re-upload,
so a plan can be tweaked and re-pushed without duplicates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Tuple

from .workouts import WorkoutSpec, compile_workout

# Mon..Sun offsets for readability
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)

PlanItem = Tuple[str, WorkoutSpec]  # (ISO date, spec)


@dataclass
class TrainingPlan:
    name: str
    items: List[PlanItem]

    def dates(self) -> List[str]:
        return [d for d, _ in self.items]


def week(monday: str, *sessions: Tuple[int, WorkoutSpec]) -> List[PlanItem]:
    """Expand (weekday_offset, spec) pairs anchored on a Monday into dated items."""
    y, m, d = map(int, monday.split("-"))
    base = date(y, m, d)
    return [((base + timedelta(days=off)).isoformat(), spec) for off, spec in sessions]


def push_plan(client, plan: TrainingPlan, replace: bool = True) -> List[dict]:
    """Upload + schedule every item. Returns a list of result records."""
    existing = {w["workoutName"]: w["workoutId"] for w in client.get_workouts()}
    results = []
    for iso_date, spec in plan.items:
        if replace and spec.name in existing:
            client.delete_workout(existing[spec.name])
        workout = compile_workout(spec)
        res = client.upload_running_workout(workout)
        workout_id = res["workoutId"]
        client.schedule_workout(workout_id, iso_date)
        results.append({"date": iso_date, "name": spec.name, "workoutId": workout_id})
    return results


def preview_plan(plan: TrainingPlan) -> List[dict]:
    """Build (but don't upload) every workout; useful for dry runs/tests."""
    out = []
    for iso_date, spec in plan.items:
        payload = compile_workout(spec).to_dict()
        out.append({
            "date": iso_date,
            "name": spec.name,
            "segments": len(payload["workoutSegments"]),
            "steps": len(payload["workoutSegments"][0]["workoutSteps"]),
        })
    return out

"""Training-plan engine: take a list of (date, spec) and push them to Garmin
Connect as scheduled, structured workouts.

A spec is either a `WorkoutSpec` (running) or a `StrengthSpec` (strength/core);
`_compile` dispatches on type and `push_plan` picks the matching upload method,
so a plan can interleave runs and lifts on the same calendar. Every plan in this
repo carries two strength sessions a week.

Idempotent: when replace=True, a same-named workout is deleted before re-upload,
so a plan can be tweaked and re-pushed without duplicates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Tuple, Union

from .strength import StrengthSpec, compile_strength
from .workouts import WorkoutSpec, compile_workout

# Mon..Sun offsets for readability
MON, TUE, WED, THU, FRI, SAT, SUN = range(7)

AnySpec = Union[WorkoutSpec, StrengthSpec]
PlanItem = Tuple[str, AnySpec]  # (ISO date, spec)


def _compile(spec: AnySpec):
    """Compile either kind of spec into its Garmin workout model."""
    return compile_strength(spec) if isinstance(spec, StrengthSpec) \
        else compile_workout(spec)


def _upload(client, spec: AnySpec) -> dict:
    """Upload via the sport-specific endpoint for this spec type."""
    workout = _compile(spec)
    if isinstance(spec, StrengthSpec):
        return client.upload_strength_workout(workout)
    return client.upload_running_workout(workout)


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
    """Upload + schedule every item. Returns a list of result records.

    A name that recurs across the block — "Easy 6mi", or either strength day —
    is uploaded ONCE and then scheduled on each of its dates. Re-uploading per
    occurrence would orphan the earlier schedules, since `existing` is only read
    at the start and the second delete would target an id that is already gone.
    """
    existing = {w["workoutName"]: w["workoutId"] for w in client.get_workouts()}
    uploaded: dict[str, int] = {}
    results = []
    for iso_date, spec in plan.items:
        workout_id = uploaded.get(spec.name)
        if workout_id is None:
            if replace and spec.name in existing:
                client.delete_workout(existing.pop(spec.name))
            workout_id = _upload(client, spec)["workoutId"]
            uploaded[spec.name] = workout_id
        client.schedule_workout(workout_id, iso_date)
        results.append({
            "date": iso_date,
            "name": spec.name,
            "workoutId": workout_id,
            "sport": "strength" if isinstance(spec, StrengthSpec) else "running",
        })
    return results


def preview_plan(plan: TrainingPlan) -> List[dict]:
    """Build (but don't upload) every workout; useful for dry runs/tests."""
    out = []
    for iso_date, spec in plan.items:
        payload = _compile(spec).to_dict()
        out.append({
            "date": iso_date,
            "name": spec.name,
            "sport": "strength" if isinstance(spec, StrengthSpec) else "running",
            "segments": len(payload["workoutSegments"]),
            "steps": len(payload["workoutSegments"][0]["workoutSteps"]),
        })
    return out

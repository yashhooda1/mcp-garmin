"""Validated builders that compile a friendly workout spec into the exact JSON
schema Garmin's workout-service expects. Verified against garminconnect 0.3.6.

A "spec" is what an LLM (or YAML/JSON) provides:

    WorkoutSpec(
        name="4x1mi threshold",
        steps=[
            StepSpec(kind="warmup",  duration="15:00", target="hr:2"),
            RepeatSpec(repeat=4, steps=[
                StepSpec(kind="run",      duration="1mi",  target="pace:6:35-6:55"),
                StepSpec(kind="recovery", duration="2:30", target="hr:2"),
            ]),
            StepSpec(kind="cooldown", duration="10:00", target="hr:2"),
        ],
    )

Durations:  "15:00"/"90s" = time, "1mi"/"1.5mi"/"400m"/"1km" = distance.
Targets:    None/"none", "hr:2"/"z2" = HR zone, "pace:6:35-6:55" = pace window.
"""
from __future__ import annotations

from typing import List, Optional, Union

from pydantic import BaseModel, Field

from garminconnect.workout import (
    ConditionType,
    ExecutableStep,
    RunningWorkout,
    SportType,
    StepType,
    TargetType,
    WorkoutSegment,
    create_repeat_group,
)

M_PER_MILE = 1609.34
M_PER_KM = 1000.0


# --------------------------------------------------------------------------- #
# parsing helpers
# --------------------------------------------------------------------------- #
def pace_to_mps(pace: str) -> float:
    """'6:52' (min/mi) -> metres/sec."""
    minutes, seconds = pace.strip().split(":")
    return M_PER_MILE / (int(minutes) * 60 + int(seconds))


def parse_duration(text: str):
    """Return ('time', seconds) or ('distance', metres)."""
    t = text.strip().lower()
    if t.endswith("mi"):
        return "distance", float(t[:-2]) * M_PER_MILE
    if t.endswith("km"):
        return "distance", float(t[:-2]) * M_PER_KM
    if t.endswith("m"):
        return "distance", float(t[:-1])
    if t.endswith("s"):
        return "time", float(t[:-1])
    if ":" in t:
        mm, ss = t.split(":")
        return "time", float(int(mm) * 60 + int(ss))
    return "time", float(t)


def parse_target(text: Optional[str]):
    """Return (target_type_dict, extra_step_fields_dict)."""
    if not text or text.strip().lower() == "none":
        return (
            {"workoutTargetTypeId": TargetType.NO_TARGET,
             "workoutTargetTypeKey": "no.target", "displayOrder": 1},
            {},
        )
    t = text.strip().lower()
    if t.startswith("hr:") or (t.startswith("z") and t[1:].isdigit()):
        zone = int(t.split(":")[1]) if ":" in t else int(t[1:])
        return (
            {"workoutTargetTypeId": TargetType.HEART_RATE_ZONE,
             "workoutTargetTypeKey": "heart.rate.zone", "displayOrder": 1},
            {"zoneNumber": zone},
        )
    if t.startswith("pace:"):
        lo_s, hi_s = t.split(":", 1)[1].split("-")
        speeds = sorted([pace_to_mps(lo_s), pace_to_mps(hi_s)])  # low speed (slow pace) first
        return (
            {"workoutTargetTypeId": TargetType.PACE_ZONE,
             "workoutTargetTypeKey": "pace.zone", "displayOrder": 1},
            {"targetValueOne": round(speeds[0], 3),
             "targetValueTwo": round(speeds[1], 3)},
        )
    raise ValueError(f"Unrecognised target: {text!r}")


# --------------------------------------------------------------------------- #
# spec models (the tool-facing schema)
# --------------------------------------------------------------------------- #
class StepSpec(BaseModel):
    kind: str = Field(description="warmup | run | recovery | cooldown | rest")
    duration: str = Field(
        description="'15:00'/'90s' for time, '1mi'/'400m'/'1km' for distance"
    )
    target: Optional[str] = Field(
        default=None, description="'hr:2', 'pace:6:35-6:55', or null"
    )


class RepeatSpec(BaseModel):
    repeat: int = Field(description="number of iterations")
    steps: List[StepSpec]


class WorkoutSpec(BaseModel):
    name: str
    steps: List[Union[StepSpec, RepeatSpec]]
    description: Optional[str] = None
    estimated_minutes: Optional[int] = None


# --------------------------------------------------------------------------- #
# compilation
# --------------------------------------------------------------------------- #
_STEP_ID = {
    "warmup": StepType.WARMUP,
    "run": StepType.INTERVAL,
    "interval": StepType.INTERVAL,
    "recovery": StepType.RECOVERY,
    "cooldown": StepType.COOLDOWN,
    "rest": StepType.REST,
}


def _executable(spec: StepSpec, order: int) -> ExecutableStep:
    kind = spec.kind.lower()
    sid = _STEP_ID[kind]
    cond_kind, value = parse_duration(spec.duration)
    if cond_kind == "time":
        cond = {"conditionTypeId": ConditionType.TIME, "conditionTypeKey": "time",
                "displayOrder": 2, "displayable": True}
    else:
        cond = {"conditionTypeId": ConditionType.DISTANCE, "conditionTypeKey": "distance",
                "displayOrder": 2, "displayable": True}
    target, extra = parse_target(spec.target)
    step = ExecutableStep(
        stepOrder=order,
        stepType={"stepTypeId": sid,
                  "stepTypeKey": "interval" if kind == "run" else kind,
                  "displayOrder": sid},
        endCondition=cond,
        endConditionValue=float(value),
        targetType=target,
    )
    for key, val in extra.items():
        setattr(step, key, val)
    return step


def compile_workout(spec: WorkoutSpec) -> RunningWorkout:
    """Turn a WorkoutSpec into a Garmin RunningWorkout with sequential step orders."""
    steps: list = []
    order = 1
    for item in spec.steps:
        if isinstance(item, RepeatSpec):
            group_order = order
            inner = []
            for child in item.steps:
                order += 1
                inner.append(_executable(child, order))
            steps.append(create_repeat_group(item.repeat, inner, step_order=group_order))
            order += 1
        else:
            steps.append(_executable(item, order))
            order += 1
    est = (spec.estimated_minutes or 45) * 60
    return RunningWorkout(
        workoutName=spec.name,
        description=spec.description,
        estimatedDurationInSecs=int(est),
        workoutSegments=[
            WorkoutSegment(
                segmentOrder=1,
                sportType={"sportTypeId": SportType.RUNNING,
                           "sportTypeKey": "running", "displayOrder": 1},
                workoutSteps=steps,
            )
        ],
    )


# --------------------------------------------------------------------------- #
# ergonomic session builders (used by plans/)
# --------------------------------------------------------------------------- #
def easy(name: str, miles: float, strides: int = 0, hr_zone: int = 2) -> WorkoutSpec:
    steps: list = [StepSpec(kind="run", duration=f"{miles}mi", target=f"hr:{hr_zone}")]
    if strides:
        steps.append(
            RepeatSpec(repeat=strides, steps=[
                StepSpec(kind="run", duration="20s", target=None),
                StepSpec(kind="recovery", duration="60s", target=f"hr:{hr_zone}"),
            ])
        )
    return WorkoutSpec(name=name, steps=steps, estimated_minutes=int(miles * 8.5))


def long_run(name: str, miles: float, mp_pace: Optional[str] = None,
             mp_miles: float = 0) -> WorkoutSpec:
    easy_miles = round(miles - mp_miles, 2)
    steps: list = [StepSpec(kind="run", duration=f"{easy_miles}mi", target="hr:2")]
    if mp_miles:
        steps.append(StepSpec(kind="run", duration=f"{mp_miles}mi", target=f"pace:{mp_pace}"))
    return WorkoutSpec(name=name, steps=steps, estimated_minutes=int(miles * 8.5))


def intervals(name: str, n: int, rep: str, rep_pace: str, rec: str,
              wu: str = "15:00", cd: str = "10:00", est_min: int = 60) -> WorkoutSpec:
    return WorkoutSpec(
        name=name,
        estimated_minutes=est_min,
        steps=[
            StepSpec(kind="warmup", duration=wu, target="hr:2"),
            RepeatSpec(repeat=n, steps=[
                StepSpec(kind="run", duration=rep, target=f"pace:{rep_pace}"),
                StepSpec(kind="recovery", duration=rec, target="hr:2"),
            ]),
            StepSpec(kind="cooldown", duration=cd, target="hr:2"),
        ],
    )

"""Offline tests: parsing, compilation, serialization. No Garmin network calls."""
from garmin_mcp.workouts import (
    RepeatSpec,
    StepSpec,
    WorkoutSpec,
    compile_workout,
    pace_to_mps,
    parse_duration,
    parse_target,
)


def test_parse_duration():
    assert parse_duration("1mi") == ("distance", 1609.34)
    assert parse_duration("400m") == ("distance", 400.0)
    assert parse_duration("1.5km") == ("distance", 1500.0)
    assert parse_duration("15:00") == ("time", 900.0)
    assert parse_duration("90s") == ("time", 90.0)


def test_parse_target_hr_and_pace():
    t, extra = parse_target("hr:2")
    assert t["workoutTargetTypeKey"] == "heart.rate.zone" and extra["zoneNumber"] == 2
    t, extra = parse_target("pace:6:35-6:55")
    assert t["workoutTargetTypeKey"] == "pace.zone"
    # low speed (slower pace) stored first
    assert extra["targetValueOne"] < extra["targetValueTwo"]


def test_pace_round_trip():
    mps = pace_to_mps("6:52")
    back = 1609.34 / mps
    assert abs(back - 412) < 1  # 6:52 == 412s


def test_compile_threshold_workout():
    spec = WorkoutSpec(name="4x1mi", estimated_minutes=60, steps=[
        StepSpec(kind="warmup", duration="15:00", target="hr:2"),
        RepeatSpec(repeat=4, steps=[
            StepSpec(kind="run", duration="1mi", target="pace:6:35-6:55"),
            StepSpec(kind="recovery", duration="2:30", target="hr:2"),
        ]),
        StepSpec(kind="cooldown", duration="10:00", target="hr:2"),
    ])
    payload = compile_workout(spec).to_dict()
    steps = payload["workoutSegments"][0]["workoutSteps"]
    assert len(steps) == 3
    grp = steps[1]
    assert grp["type"] == "RepeatGroupDTO"
    assert grp["numberOfIterations"] == 4
    rep = grp["workoutSteps"][0]
    assert rep["endCondition"]["conditionTypeKey"] == "distance"
    assert rep["targetType"]["workoutTargetTypeKey"] == "pace.zone"

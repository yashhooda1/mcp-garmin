"""Offline tests: strength compilation, exercise-id validity, and the 2x/week rule."""
import pytest
from garminconnect import exercises as gc_exercises

from garmin_mcp.strength import (
    Hold,
    Lift,
    StrengthSpec,
    compile_strength,
    mobility_reset,
    parse_seconds,
    strength_a,
    strength_b,
    strength_for_week,
)

VALID = {(e["category"], e["exercise"]) for e in gc_exercises.EXERCISES}

ALL_SESSIONS = [strength_a("base"), strength_a("specific"), strength_b("build"),
                mobility_reset(), strength_a("base", "hs"), strength_b("base", "hs")]


def test_parse_seconds():
    assert parse_seconds("45s") == 45.0
    assert parse_seconds("1:00") == 60.0
    assert parse_seconds("90") == 90.0


@pytest.mark.parametrize("spec", ALL_SESSIONS, ids=lambda s: s.name)
def test_library_exercise_ids_are_real(spec):
    """Every category/exercise pair in the library exists in garminconnect's table.

    This is the test that catches a garminconnect bump renaming an exercise —
    without it, an invalid id uploads as a blank step and nobody notices until
    they're standing in a gym.
    """
    for ex in spec.exercises:
        assert (ex.category, ex.exercise) in VALID, \
            f"{spec.name}: {ex.category}/{ex.exercise} is not a Garmin exercise"


@pytest.mark.parametrize("spec", ALL_SESSIONS, ids=lambda s: s.name)
def test_library_compiles(spec):
    payload = compile_strength(spec).to_dict()
    assert payload["sportType"]["sportTypeKey"] == "strength_training"
    steps = payload["workoutSegments"][0]["workoutSteps"]
    assert len(steps) == len(spec.exercises)
    orders = []
    for group in steps:
        assert group["type"] == "RepeatGroupDTO"
        orders.append(group["stepOrder"])
        orders += [s["stepOrder"] for s in group["workoutSteps"]]
    assert len(orders) == len(set(orders)), "stepOrder values must be unique"


def test_reps_and_holds_use_the_right_end_condition():
    spec = StrengthSpec(name="mixed", exercises=[
        Lift("DEADLIFT", "ROMANIAN_DEADLIFT", sets=3, reps=8),
        Hold("PLANK", "PLANK", sets=2, hold="45s"),
    ])
    groups = compile_strength(spec).to_dict()["workoutSegments"][0]["workoutSteps"]
    lift_step = groups[0]["workoutSteps"][0]
    hold_step = groups[1]["workoutSteps"][0]
    assert lift_step["endCondition"]["conditionTypeKey"] == "reps"
    assert lift_step["endConditionValue"] == 8.0
    assert lift_step["category"] == "DEADLIFT"
    assert hold_step["endCondition"]["conditionTypeKey"] == "time"
    assert hold_step["endConditionValue"] == 45.0
    assert hold_step["exerciseName"] == "PLANK"


def test_reps_and_hold_are_mutually_exclusive():
    spec = StrengthSpec(name="bad", exercises=[
        StrengthSpec.model_fields and Lift("PLANK", "PLANK", sets=1, reps=5),
    ])
    spec.exercises[0].hold = "30s"
    with pytest.raises(ValueError):
        compile_strength(spec)


def test_weight_is_sent_in_grams():
    spec = StrengthSpec(name="loaded", exercises=[
        Lift("SQUAT", "GOBLET_SQUAT", sets=1, reps=5, weight_kg=24),
    ])
    step = compile_strength(spec).to_dict()["workoutSegments"][0]["workoutSteps"][0]
    assert step["workoutSteps"][0]["weightValue"] == 24000.0


def test_two_sessions_every_normal_week():
    assert len(strength_for_week("build")) == 2
    assert len(strength_for_week("build", down_week=True)) == 2
    # Race week drops to a single mobility session on purpose.
    assert len(strength_for_week("build", race_week=True)) == 1


def test_cues_land_in_the_description():
    """Cues sync to the watch via the description field — they aren't decoration."""
    payload = compile_strength(strength_a("build")).to_dict()
    assert "hamstrings" in payload["description"].lower()

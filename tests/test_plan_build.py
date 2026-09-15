"""Offline test: the bundled Houston plan builds + serializes end to end."""
from datetime import date

from garmin_mcp.plans import preview_plan
from garmin_mcp.strength import StrengthSpec
from plans.houston import (
    BLOCK_START,
    STRENGTH_DAYS,
    WEEKS,
    build_plan,
    is_race_week,
    weekly_briefs,
)


def test_houston_builds():
    plan = build_plan()
    assert plan.items[0][0] == "2026-08-03"
    assert plan.items[-1][0] == "2027-01-17"
    rows = preview_plan(plan)            # compiles every workout
    assert len(rows) == len(plan.items)
    assert all(r["steps"] >= 1 for r in rows)
    assert all(r["date"][:4] in ("2026", "2027") for r in rows)


def test_block_shape():
    assert len(WEEKS) == 24
    assert BLOCK_START.weekday() == 0   # must be a Monday


def test_races_land_on_real_dates():
    """The whole point of the block: these dates are real races, not arithmetic."""
    by_date: dict[str, list] = {}
    for iso, spec in build_plan().items:       # a date can hold a run AND a lift
        by_date.setdefault(iso, []).append(spec)
    expected = {
        "2026-09-19": "UH 10K",
        "2026-10-11": "Space City",
        "2026-11-05": "1 Mile",
        "2026-11-08": "Cypress",
        "2026-11-26": "Turkey Trot",
        "2026-12-05": "Santa",
        "2026-12-13": "30K",
        "2027-01-17": "Marathon",
    }
    for iso, fragment in expected.items():
        assert iso in by_date, f"no session scheduled on {iso}"
        names = [s.name for s in by_date[iso]]
        assert any(fragment in n for n in names), f"{iso}: expected {fragment!r}, got {names}"


def test_houston_carries_two_strength_days_a_week():
    """Same rule as every other plan here: 2x/week, quality days, never pre-long-run."""
    plan = build_plan()
    per_week: dict[int, list[date]] = {}
    for iso, spec in plan.items:
        if not isinstance(spec, StrengthSpec):
            continue
        day = date.fromisoformat(iso)
        per_week.setdefault((day - BLOCK_START).days // 7, []).append(day)

    assert len(per_week) == len(WEEKS), "a week went without strength work"
    for w, days in per_week.items():
        expected = 1 if is_race_week(WEEKS[w]) else 2      # race weeks: mobility only
        assert len(days) == expected, f"week {w + 1}: {len(days)} lifts"
        assert all(d.weekday() in STRENGTH_DAYS for d in days), f"week {w + 1}: wrong day"
        assert all(d.weekday() != 5 for d in days), "never the day before the long run"


def test_every_houston_session_carries_fuelling_and_recovery():
    for _, spec in build_plan().items:
        text = (spec.description or "").lower()
        assert "fuel" in text, f"{spec.name}: no fuelling note"
        assert "recovery" in text or "movement quality" in text, f"{spec.name}: no recovery note"


def test_weekly_briefs_cover_the_block():
    briefs = weekly_briefs()
    assert len(briefs) == len(WEEKS)
    for b in briefs:
        assert b["brief"]["nutrition"]["carbohydrate"]
        assert "sleep" in str(b["brief"]["recovery"]).lower()
        assert 1 <= len(b["strength_sessions"]) <= 2

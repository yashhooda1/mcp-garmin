"""Offline test: the bundled Houston plan builds + serializes end to end."""
from garmin_mcp.plans import preview_plan
from plans.houston import BLOCK_START, WEEKS, build_plan


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
    by_date = dict(build_plan().items)
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
        assert fragment in by_date[iso].name, f"{iso}: expected {fragment!r}"

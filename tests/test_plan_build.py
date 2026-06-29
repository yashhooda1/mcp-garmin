"""Offline test: the bundled Boulderthon plan builds + serializes end to end."""
from garmin_mcp.plans import preview_plan
from plans.boulderthon import build_plan


def test_boulderthon_builds():
    plan = build_plan()
    assert plan.items[0][0] == "2026-06-29"
    rows = preview_plan(plan)            # compiles every workout
    assert len(rows) >= 60
    # every session has at least one step and a valid date
    assert all(r["steps"] >= 1 for r in rows)
    assert all(r["date"].startswith("2026-") for r in rows)

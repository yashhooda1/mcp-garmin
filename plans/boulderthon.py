"""The bundled example: a 13-week, sub-3 Boulderthon build (Houston heat ->
altitude race, Sun 2026-09-27). All paces are heat-adjusted; easy/long/recovery
run by HR Zone 2. This doubles as documentation of the plan engine.

    from plans.boulderthon import build_plan
    plan = build_plan()            # -> TrainingPlan
"""
from __future__ import annotations

from garmin_mcp.plans import MON, TUE, WED, THU, FRI, SAT, SUN, TrainingPlan, week
from garmin_mcp.workouts import easy, intervals, long_run

# heat-adjusted target windows (min/mi)
THRESHOLD = "6:35-6:55"
CRUISE = "6:35-6:50"
FARTLEK = "6:30-6:55"
MP = "7:05-7:30"
TAPER_MP = "6:45-7:05"


def build_plan() -> TrainingPlan:
    items = []

    items += week("2026-06-29",
        (MON, easy("W1 Mon · Easy + strides", 7, strides=5)),
        (TUE, intervals("W1 Tue · 6x(2min/2min) fartlek", 6, "2:00", FARTLEK, "2:00")),
        (THU, easy("W1 Thu · Medium-long", 8)),
        (SAT, long_run("W1 Sat · Long run", 11)),
        (SUN, easy("W1 Sun · Recovery", 6)))

    items += week("2026-07-06",
        (MON, easy("W2 Mon · Easy + strides", 7, strides=5)),
        (TUE, intervals("W2 Tue · 4x1mi threshold", 4, "1mi", THRESHOLD, "2:30")),
        (THU, easy("W2 Thu · Medium-long", 9)),
        (SAT, long_run("W2 Sat · Long run", 13)),
        (SUN, easy("W2 Sun · Recovery", 6)))

    items += week("2026-07-13",
        (MON, easy("W3 Mon · Easy + strides", 8, strides=6)),
        (TUE, intervals("W3 Tue · 2x3mi threshold", 2, "3mi", THRESHOLD, "3:00")),
        (THU, easy("W3 Thu · Medium-long", 9)),
        (SAT, long_run("W3 Sat · Long run", 15)),
        (SUN, easy("W3 Sun · Recovery", 7)))

    items += week("2026-07-20",  # DOWN
        (MON, easy("W4 Mon · Easy + strides", 6, strides=4)),
        (TUE, intervals("W4 Tue · 5x(3min/2min) fartlek", 5, "3:00", FARTLEK, "2:00")),
        (THU, easy("W4 Thu · Medium", 8)),
        (SAT, long_run("W4 Sat · Long run (cutback)", 12)),
        (SUN, easy("W4 Sun · Recovery", 6)))

    items += week("2026-07-27",
        (MON, easy("W5 Mon · Easy + strides", 8, strides=6)),
        (TUE, intervals("W5 Tue · 3x2mi threshold", 3, "2mi", THRESHOLD, "3:00")),
        (THU, easy("W5 Thu · Medium-long", 9)),
        (SAT, long_run("W5 Sat · Long run w/ 4mi MP", 16, mp_pace=MP, mp_miles=4)),
        (SUN, easy("W5 Sun · Recovery", 7)))

    items += week("2026-08-03",
        (MON, easy("W6 Mon · Easy + strides", 8, strides=6)),
        (TUE, intervals("W6 Tue · 6x1mi cruise", 6, "1mi", CRUISE, "1:30")),
        (THU, easy("W6 Thu · Medium-long", 10)),
        (SAT, long_run("W6 Sat · Long run", 18)),
        (SUN, easy("W6 Sun · Recovery", 8)))

    items += week("2026-08-10",  # DOWN
        (MON, easy("W7 Mon · Easy + strides", 7, strides=4)),
        (TUE, intervals("W7 Tue · 4x(3min/2min) fartlek", 4, "3:00", FARTLEK, "2:00")),
        (THU, easy("W7 Thu · Medium", 8)),
        (SAT, long_run("W7 Sat · Long run (cutback)", 14)),
        (SUN, easy("W7 Sun · Recovery", 7)))

    items += week("2026-08-17",  # PEAK long run
        (MON, easy("W8 Mon · Easy + strides", 8, strides=6)),
        (TUE, intervals("W8 Tue · 2x3mi threshold", 2, "3mi", THRESHOLD, "3:00")),
        (THU, easy("W8 Thu · Medium-long", 10)),
        (SAT, long_run("W8 Sat · Long run 20", 20)),
        (SUN, easy("W8 Sun · Recovery", 8)))

    items += week("2026-08-24",
        (MON, easy("W9 Mon · Easy + strides", 8, strides=6)),
        (TUE, intervals("W9 Tue · 4x1.5mi threshold", 4, "1.5mi", THRESHOLD, "2:30")),
        (THU, easy("W9 Thu · Medium-long", 9)),
        (SAT, long_run("W9 Sat · Long run w/ 8mi MP", 16, mp_pace=MP, mp_miles=8)),
        (SUN, easy("W9 Sun · Recovery", 8)))

    items += week("2026-08-31",  # MP dress rehearsal
        (MON, easy("W10 Mon · Easy + strides", 8, strides=6)),
        (TUE, intervals("W10 Tue · 3x2mi threshold", 3, "2mi", THRESHOLD, "3:00")),
        (THU, easy("W10 Thu · Medium-long", 9)),
        (SAT, long_run("W10 Sat · 20 w/ 10mi MP (rehearsal)", 20, mp_pace=MP, mp_miles=10)),
        (SUN, easy("W10 Sun · Recovery", 6)))

    items += week("2026-09-07",  # TAPER begins
        (MON, easy("W11 Mon · Easy + strides", 7, strides=6)),
        (TUE, intervals("W11 Tue · 5x1mi threshold", 5, "1mi", THRESHOLD, "2:00")),
        (THU, easy("W11 Thu · Medium", 8)),
        (SAT, long_run("W11 Sat · Long run w/ 5mi MP", 14, mp_pace=MP, mp_miles=5)),
        (SUN, easy("W11 Sun · Recovery", 6)))

    items += week("2026-09-14",  # TAPER
        (MON, easy("W12 Mon · Easy + strides", 6, strides=6)),
        (TUE, intervals("W12 Tue · 4x1km MP->threshold", 4, "1km", TAPER_MP, "2:00")),
        (THU, easy("W12 Thu · Easy", 6)),
        (SAT, long_run("W12 Sat · Long run w/ 4mi MP", 10, mp_pace=MP, mp_miles=4)),
        (SUN, easy("W12 Sun · Recovery", 5)))

    items += week("2026-09-21",  # RACE WEEK — race Sun 09-27
        (MON, easy("W13 Mon · Easy + strides", 6, strides=6)),
        (WED, long_run("W13 Wed · Shakeout w/ 2mi MP", 5, mp_pace=MP, mp_miles=2)),
        (FRI, easy("W13 Fri · Shakeout", 3, strides=4)))

    return TrainingPlan(name="Boulderthon Sub-3 (13wk)", items=items)


if __name__ == "__main__":
    plan = build_plan()
    print(f"{plan.name}: {len(plan.items)} sessions, "
          f"{plan.items[0][0]} -> race 2026-09-27")

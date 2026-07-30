"""Chevron Houston Marathon build — full 24-week block.

Mon 3 Aug 2026 -> Sun 17 Jan 2027.  Goal: sub-3:00 (6:52/mi) marathon debut.

Race calendar baked in
----------------------
  Sat 19 Sep 2026   Run Houston UH 10K              rust-buster        W7
  Sun 11 Oct 2026   Space City 10 Miler             threshold test     W10
  Thu  5 Nov 2026   Harriers Night of PRs — 1 mile  sub-5 attempt      W14  (date TBD)
  Sun  8 Nov 2026   Run Houston Cypress 5K          5K PR attempt      W14  (date TBD)
  Thu 26 Nov 2026   Sugar Land Turkey Trot 8K       8K PR attempt      W17
  Sat  5 Dec 2026   Run Houston Sugar Land Santa 5K sharpener          W18
  Sun 13 Dec 2026   Coach Andy Stewart's 30K        dress rehearsal    W19
  Sun 17 Jan 2027   Chevron Houston Marathon        GOAL               W24

Deliberately NOT on the calendar (date conflicts, don't sign up by accident):
  Sat 10 Oct 2026   Houston Heights Fun Run 5K   — day before Space City 10M
  Sat 12 Dec 2026   Santa's Sleigh 5K, Friendswood — day before the 30K

Structural constraints
----------------------
  * ATP ACPP fast track, M-F.  Every weekday session is pre-dawn (05:00-05:30).
    Saturday is a deliberate zero: flight-block buffer / stage-check prep.
    The Night of PRs mile is the one evening session in the block (18:00 track).
  * Houston Aug-Sep: dewpoints 74-80F.  Quality paces in phase 1 carry a
    +25-40 s/mi heat allowance and step down to true values in October.
  * Easy and long runs are ALWAYS HR-capped (zone 2), never pace-targeted.
    This is the guardrail that keeps 50-mile weeks survivable on 6h sleep.
  * Athlete is speed-rich / endurance-limited (5K 18:15, half 1:24:31, mile 4:58
    vs a 6:52 goal pace).  The block therefore weights marathon-pace volume and
    long-run duration over VO2 work.  Interval sessions exist to maintain
    turnover, not to build the goal.

Priority order when the flight schedule collapses a week:
    1. Sunday long run          (never cut — this is what buys sub-3)
    2. One quality session
    3. Easy mileage
    4. Lifts
"""

from __future__ import annotations

from datetime import date, timedelta

from garmin_mcp.workouts import RepeatSpec, StepSpec, WorkoutSpec

BLOCK_START = date(2026, 8, 3)      # Monday
RACE_DAY = date(2027, 1, 17)        # Chevron Houston Marathon

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------
# Phase 1 (Aug-Sep) runs the HOT variants.  Phase 2 onward uses true values.

EASY = "hr:2"

THRESH_HOT = "pace:6:40-6:55"   # Aug-Sep heat allowance
THRESH = "pace:6:28-6:42"       # true threshold, Oct onward
TEN_K_HOT = "pace:6:10-6:25"
TEN_K = "pace:6:05-6:18"
FIVE_K_HOT = "pace:5:55-6:10"
FIVE_K = "pace:5:50-6:02"
MILE = "pace:4:50-5:00"

MP = "pace:6:48-6:56"           # marathon goal pace
STEADY = "pace:7:10-7:25"       # MP + 20-30s, long-run finishes
REP_200 = "pace:5:25-5:40"


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def easy(mi: float, strides: int = 0, name: str | None = None) -> WorkoutSpec:
    steps = [StepSpec(kind="run", duration=f"{mi}mi", target=EASY)]
    if strides:
        steps.append(
            RepeatSpec(
                repeat=strides,
                steps=[
                    StepSpec(kind="run", duration="20s", target=None),
                    StepSpec(kind="recovery", duration="60s", target=EASY),
                ],
            )
        )
    label = name or f"Easy {mi}mi" + (f" + {strides}x20s hill strides" if strides else "")
    return WorkoutSpec(name=label, steps=steps)


def intervals(
    name: str,
    reps: int,
    work: str,
    rec: str,
    target: str,
    wu: float = 2,
    cd: float = 2,
) -> WorkoutSpec:
    return WorkoutSpec(
        name=name,
        steps=[
            StepSpec(kind="warmup", duration=f"{wu}mi", target=EASY),
            RepeatSpec(
                repeat=reps,
                steps=[
                    StepSpec(kind="run", duration=work, target=target),
                    StepSpec(kind="recovery", duration=rec, target=EASY),
                ],
            ),
            StepSpec(kind="cooldown", duration=f"{cd}mi", target=EASY),
        ],
    )


def tempo(name: str, blocks: list[tuple[str, str]], wu: float = 2, cd: float = 2) -> WorkoutSpec:
    """blocks = [(duration, target), ...] with 1mi float recoveries between."""
    steps: list = [StepSpec(kind="warmup", duration=f"{wu}mi", target=EASY)]
    for i, (dur, tgt) in enumerate(blocks):
        if i:
            steps.append(StepSpec(kind="recovery", duration="1mi", target=EASY))
        steps.append(StepSpec(kind="run", duration=dur, target=tgt))
    steps.append(StepSpec(kind="cooldown", duration=f"{cd}mi", target=EASY))
    return WorkoutSpec(name=name, steps=steps)


def long_run(mi: float, finish: float = 0, target: str = STEADY) -> WorkoutSpec:
    steps = [StepSpec(kind="run", duration=f"{mi - finish}mi", target=EASY)]
    label = f"Long {mi}mi"
    if finish:
        steps.append(StepSpec(kind="run", duration=f"{finish}mi", target=target))
        label += f" w/ last {finish} @ {'MP' if target == MP else 'steady'}"
    return WorkoutSpec(name=label, steps=steps)


def long_with_mp(mi: float, reps: int, work: str, rec: str) -> WorkoutSpec:
    """Long run with embedded MP repeats, e.g. 20mi w/ 3x3mi @ MP."""
    body = RepeatSpec(
        repeat=reps,
        steps=[
            StepSpec(kind="run", duration=work, target=MP),
            StepSpec(kind="recovery", duration=rec, target=EASY),
        ],
    )
    return WorkoutSpec(
        name=f"Long {mi}mi w/ {reps}x{work} @ MP",
        steps=[
            StepSpec(kind="warmup", duration="4mi", target=EASY),
            body,
            StepSpec(kind="cooldown", duration="2mi", target=EASY),
        ],
    )


def race(name: str, dist: str, target: str, wu: float = 2, cd: float = 2) -> WorkoutSpec:
    return WorkoutSpec(
        name=f"RACE — {name}",
        steps=[
            StepSpec(kind="warmup", duration=f"{wu}mi", target=EASY),
            StepSpec(kind="run", duration=dist, target=target),
            StepSpec(kind="cooldown", duration=f"{cd}mi", target=EASY),
        ],
    )


# ---------------------------------------------------------------------------
# The block.  Keys are weekday indices: 0=Mon .. 6=Sun.
# A missing key = rest day.  Saturday (5) is absent except race weeks.
# ---------------------------------------------------------------------------

WEEKS: list[dict[int, WorkoutSpec]] = [
    # ===================== PHASE 1 — HEAT BASE (W1-7) =====================
    # W1  Aug 3-9   40mi   acclimation, zero hard running by design
    {0: easy(6, strides=6), 1: easy(7), 2: easy(5), 3: easy(7, strides=8),
     4: easy(5), 6: long_run(10)},

    # W2  Aug 10-16  42mi  turnover in
    {0: easy(6, strides=6),
     1: intervals("6x2:00 @ 5K effort", 6, "2:00", "2:00", FIVE_K_HOT, wu=3),
     2: easy(5), 3: easy(6), 4: easy(5), 6: long_run(12)},

    # W3  Aug 17-23  44mi  threshold in
    {0: easy(6, strides=6),
     1: intervals("4x1mi threshold", 4, "1mi", "2:30", THRESH_HOT),
     2: easy(5), 3: easy(7), 4: easy(5), 6: long_run(13)},

    # W4  Aug 24-30  45mi  phase peak
    {0: easy(6, strides=6),
     1: tempo("20min + 10min tempo", [("20:00", THRESH_HOT), ("10:00", THRESH_HOT)]),
     2: easy(5), 3: easy(7), 4: easy(5), 6: long_run(13, finish=3)},

    # W5  Aug 31-Sep 6  38mi  DOWN WEEK — one lift only
    {0: easy(5, strides=6),
     1: intervals("5x800 @ 10K", 5, "800m", "90s", TEN_K_HOT),
     2: easy(4), 3: easy(6), 4: easy(4), 6: long_run(12)},

    # W6  Sep 7-13  44mi  sharpen
    {0: easy(6, strides=6),
     1: intervals("5x1mi @ 10K", 5, "1mi", "2:00", TEN_K_HOT),
     2: easy(5), 3: easy(7, strides=6), 4: easy(5), 6: long_run(12)},

    # W7  Sep 14-20  RACE WEEK — UH 10K Sat
    {0: easy(6),
     1: intervals("3x1mi @ 10K — race prep", 3, "1mi", "2:30", TEN_K_HOT, cd=1.5),
     2: easy(5),
     3: intervals("4x200 sharpener", 4, "200m", "200m", FIVE_K_HOT, wu=3, cd=1),
     4: easy(3, name="Shakeout 3mi"),
     5: race("Run Houston UH 10K", "10km", "pace:6:12-6:25"),
     6: easy(6)},

    # ================= PHASE 2 — AEROBIC STRENGTH (W8-13) =================
    # W8  Sep 21-27  44mi  absorb the race
    {0: easy(6), 1: easy(7, strides=8), 2: easy(5), 3: easy(7), 4: easy(5),
     6: long_run(14)},

    # W9  Sep 28-Oct 4  47mi  first true-pace threshold
    {0: easy(6, strides=6),
     1: tempo("2x3mi @ threshold", [("3mi", THRESH), ("3mi", THRESH)]),
     2: easy(5), 3: easy(7), 4: easy(5), 6: long_run(15)},

    # W10 Oct 5-11  42mi  RACE — Space City 10 Miler Sun
    {0: easy(6),
     1: intervals("4x1mi @ 10K", 4, "1mi", "2:00", TEN_K, cd=1.5),
     2: easy(5), 3: easy(5, strides=6), 4: easy(3, name="Shakeout 3mi"),
     6: race("Space City 10 Miler", "10mi", "pace:6:30-6:40", wu=2, cd=2)},

    # W11 Oct 12-18  46mi  recover, first MP touch
    {0: easy(6), 1: easy(7, strides=8), 2: easy(5), 3: easy(7), 4: easy(5),
     6: long_run(16, finish=4, target=MP)},

    # W12 Oct 19-25  50mi
    {0: easy(6, strides=6),
     1: intervals("5x1mi @ threshold", 5, "1mi", "2:00", THRESH),
     2: easy(5),
     3: long_run(8, finish=4, target=MP),
     4: easy(5), 6: long_run(17)},

    # W13 Oct 26-Nov 1  50mi
    {0: easy(6, strides=6),
     1: tempo("2x2mi @ threshold + 4x400", [("2mi", THRESH), ("2mi", THRESH)]),
     2: easy(5), 3: easy(8), 4: easy(5), 6: long_run(18, finish=4, target=STEADY)},

    # ================ PHASE 3 — MARATHON SPECIFIC (W14-19) ================
    # W14 Nov 2-8  39mi  DOUBLE RACE WEEK — mile Thu 18:00 (date TBD), 5K Sun.
    # No long run by design: two sharp races is the week's whole stimulus, and
    # this doubles as the mini-down week between W13 and W16.
    {0: easy(6),
     1: intervals("4x200 mile prep", 4, "200m", "400m", REP_200, wu=3, cd=2),
     2: easy(5),
     3: race("Harriers Night of PRs — 1 Mile", "1mi", MILE, wu=2.5, cd=2),
     4: easy(4),
     6: race("Run Houston Cypress 5K", "5km", "pace:5:45-5:52")},

    # W15 Nov 9-15  50mi  absorbs the long run W14 gave up
    {0: easy(6, strides=6),
     1: tempo("3x2mi @ threshold", [("2mi", THRESH)] * 3),
     2: easy(5),
     3: long_run(8, finish=4, target=MP),
     4: easy(5), 6: long_with_mp(18, 2, "3mi", "1mi")},

    # W16 Nov 16-22  54mi  BLOCK PEAK VOLUME
    {0: easy(7, strides=6),
     1: intervals("6x1mi @ threshold", 6, "1mi", "2:00", THRESH),
     2: easy(5), 3: easy(8), 4: easy(5), 6: long_run(20, finish=6, target=MP)},

    # W17 Nov 23-29  46mi  DOWN + RACE — Turkey Trot 8K Thu (Thanksgiving)
    {0: easy(6),
     1: intervals("5x3:00 @ 10K", 5, "3:00", "2:00", TEN_K, cd=1.5),
     2: easy(4, strides=6),
     3: race("Sugar Land Turkey Trot 8K", "8km", "pace:5:45-5:58"),
     4: easy(4), 6: long_run(14)},

    # W18 Nov 30-Dec 6  52mi  RACE — Sugar Land Santa 5K Sat, 8 days out from
    # the 30K. Sunday's long run follows a raced 5K on purpose: running long on
    # pre-fatigued legs is the closest thing to the back half of a marathon.
    {0: easy(5, strides=6),
     1: tempo("2x4mi @ MP", [("4mi", MP), ("4mi", MP)]),
     2: easy(5), 3: easy(5), 4: easy(3, name="Shakeout 3mi"),
     5: race("Run Houston Sugar Land Santa 5K", "5km", "pace:5:48-5:58"),
     6: long_run(14, finish=4, target=STEADY)},

    # W19 Dec 7-13  44mi  taper into the 30K
    {0: easy(6),
     1: intervals("4x1mi @ MP", 4, "1mi", "2:00", MP, cd=1.5),
     2: easy(5), 3: easy(6, strides=6), 4: easy(3, name="Shakeout 3mi"),
     6: WorkoutSpec(name="RACE — Coach Andy Stewart's 30K (dress rehearsal)", steps=[
         StepSpec(kind="warmup", duration="1mi", target=EASY),
         StepSpec(kind="run", duration="11mi", target=STEADY),
         StepSpec(kind="run", duration="7.6mi", target=MP),
         StepSpec(kind="cooldown", duration="1mi", target=EASY)])},

    # ================== PHASE 4 — PEAK + TAPER (W20-24) ==================
    # W20 Dec 14-20  44mi  absorb the 30K
    {0: easy(5), 1: easy(7, strides=8), 2: easy(5), 3: easy(7), 4: easy(5),
     6: long_run(14)},

    # W21 Dec 21-27  52mi  last big week — final long run exactly 3wk out
    {0: easy(6, strides=6),
     1: tempo("3x2mi @ threshold", [("2mi", THRESH)] * 3),
     2: easy(5),
     3: long_run(8, finish=4, target=MP),
     4: easy(5), 6: long_with_mp(20, 2, "5mi", "1mi")},

    # W22 Dec 28-Jan 3  44mi  taper begins
    {0: easy(6),
     1: intervals("5x1mi @ threshold", 5, "1mi", "2:00", THRESH),
     2: easy(5), 3: easy(7), 4: easy(4),
     6: long_run(16, finish=6, target=MP)},

    # W23 Jan 4-10  34mi
    {0: easy(5),
     1: intervals("4x1mi @ MP + 4x200", 4, "1mi", "2:00", MP, cd=1.5),
     2: easy(4), 3: easy(5, strides=6), 4: easy(4), 6: long_run(12)},

    # W24 Jan 11-17  24mi + RACE
    {0: easy(5),
     1: intervals("3x1mi @ MP — final tune", 3, "1mi", "2:00", MP, cd=1),
     2: easy(4),
     3: intervals("4x200 sharpener", 4, "200m", "200m", REP_200, wu=2, cd=1),
     4: easy(3, name="Shakeout 3mi"),
     5: easy(2, strides=4, name="Pre-race 2mi + strides"),
     6: WorkoutSpec(name="RACE — Chevron Houston Marathon (sub-3:00)", steps=[
         StepSpec(kind="run", duration="6mi", target="pace:6:54-7:00"),
         StepSpec(kind="run", duration="14mi", target=MP),
         StepSpec(kind="run", duration="6.2mi", target="pace:6:40-6:52")])},
]


def build_plan(start: date | None = None) -> list[tuple[date, WorkoutSpec]]:
    """Expand the block into (date, WorkoutSpec) pairs.

    `start` must be a Monday; defaults to BLOCK_START (3 Aug 2026).
    """
    monday = start or BLOCK_START
    if monday.weekday() != 0:
        raise ValueError(f"start must be a Monday, got {monday} ({monday:%A})")
    out: list[tuple[date, WorkoutSpec]] = []
    for w, days in enumerate(WEEKS):
        for dow, spec in sorted(days.items()):
            out.append((monday + timedelta(days=w * 7 + dow), spec))
    return out


def phase_of(week_index: int) -> str:
    if week_index < 7:
        return "1 — heat base"
    if week_index < 13:
        return "2 — aerobic strength"
    if week_index < 19:
        return "3 — marathon specific"
    return "4 — peak + taper"


if __name__ == "__main__":  # dry run: python -m plans.houston
    plan = build_plan()
    print(f"{len(plan)} sessions across {len(WEEKS)} weeks "
          f"({plan[0][0]} -> {plan[-1][0]})")
    for d, spec in plan:
        print(f"{d:%Y-%m-%d} {d:%a}  {spec.name}")

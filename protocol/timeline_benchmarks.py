"""Scenario-first onboarding benchmarks for the trajectory game."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Benchmark:
    id: str
    level: int
    title: str
    horizon_label: str
    horizon_days: int
    observation: str
    prompt: str
    vocabulary: tuple[str, ...]
    suggested_moves: tuple[str, ...] = ()
    hidden: bool = False

    def payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class Challenge:
    id: str
    number: int
    title: str
    prompt: str
    horizon_label: str
    horizon_days: int
    exercise_minutes: int | None
    constraints: tuple[str, ...]
    private: bool = False

    def payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["level"] = 0
        payload["observation"] = "A compact mission for learning the visual language."
        payload["vocabulary"] = self.constraints
        payload["suggested_moves"] = ()
        payload["hidden"] = False
        payload["kind"] = "challenge"
        return payload


LEVELS: dict[int, tuple[str, str]] = {
    1: (
        "Immediate action",
        "Short, familiar trajectories with few dependencies.",
    ),
    2: (
        "Personal projects",
        "Uncertainty and dependencies become meaningful.",
    ),
    3: (
        "Collective organisation",
        "Different imagined sequences begin to converge—or conflict.",
    ),
    4: (
        "Creative work",
        "Iteration, flattening and repeated redirection become normal.",
    ),
    5: (
        "Startup",
        "Releases, contributors, forks and pivots stress the vocabulary.",
    ),
    6: (
        "Societal",
        "Many trajectories interact and convergence becomes the object.",
    ),
    7: (
        "Historical reconstruction",
        "Draw the trajectory you might have imagined from inside history.",
    ),
    8: (
        "Impossible problems",
        "Uncertainty dominates; plans begin to look like landscapes.",
    ),
}


BENCHMARKS: tuple[Benchmark, ...] = (
    Benchmark(
        id="cook-dinner",
        level=1,
        title="Cook dinner for friends",
        horizon_label="2 hours",
        horizon_days=1,
        observation="Almost deterministic: very little uncertainty and mostly smooth.",
        prompt="How would you draw the path from deciding to cook to serving dinner?",
        vocabulary=("Smooth", "Low uncertainty", "Milestone"),
        suggested_moves=(
            "Action · buy ingredients",
            "Event · friends arrive",
            "Milestone · dinner served",
            "Update · someone is vegetarian",
            "Release · dessert appears",
        ),
    ),
    Benchmark(
        id="bicycle-puncture",
        level=1,
        title="Fix a bicycle puncture",
        horizon_label="30–60 minutes",
        horizon_days=1,
        observation="Usually smooth until one unexpected condition creates uncertainty.",
        prompt="Where does diagnosis end and decisive repair begin?",
        vocabulary=("Smooth", "Uncertainty", "Action", "Milestone"),
    ),
    Benchmark(
        id="birthday-dinner",
        level=2,
        title="Organise a birthday dinner",
        horizon_label="2 weeks",
        horizon_days=14,
        observation="Attendance, confirmation and responsibilities create local uncertainty.",
        prompt="Draw the path before you know who will come, where, or with the cake.",
        vocabulary=("Uncertainty chunks", "Actions", "Release", "Milestone"),
    ),
    Benchmark(
        id="new-apartment",
        level=2,
        title="Move into a new apartment",
        horizon_label="1 month",
        horizon_days=30,
        observation="Many dependencies make natural kinks visible.",
        prompt="What happens to the whole trajectory when you discover there is no lift?",
        vocabulary=("Dependencies", "Kink", "Actions", "Threshold"),
        suggested_moves=("Update · no lift",),
    ),
    Benchmark(
        id="neighbourhood-picnic",
        level=3,
        title="Organise a neighbourhood picnic",
        horizon_label="1–2 months",
        horizon_days=60,
        observation="Participants usually imagine different sequences before convergence is revealed.",
        prompt="Draw your own roadmap first. What would neighbours place in another order?",
        vocabulary=("Personal path", "Convergence", "Collective events"),
    ),
    Benchmark(
        id="scientific-workshop",
        level=3,
        title="Organise a scientific workshop",
        horizon_label="6 months",
        horizon_days=180,
        observation="Funding, venue and programme expose where alignment matters.",
        prompt="Draw the path from first commitment to publication after the workshop.",
        vocabulary=("Alignment", "Dependencies", "Release", "Milestones"),
        suggested_moves=(
            "Milestone · funding",
            "Milestone · venue",
            "Action · invited speakers",
            "Release · registration",
            "Update · programme",
            "Event · workshop",
            "Release · publication",
        ),
    ),
    Benchmark(
        id="short-documentary",
        level=4,
        title="Produce a short documentary",
        horizon_label="6 months",
        horizon_days=180,
        observation="Ideas emerge, editing changes the ending, and kinks become common.",
        prompt="Where does the planned film stop being the film that is actually made?",
        vocabulary=("Repeated uncertainty", "Kinks", "Iteration"),
    ),
    Benchmark(
        id="write-book",
        level=4,
        title="Write a book",
        horizon_label="3 years",
        horizon_days=1095,
        observation="The path may flatten for long periods before sudden breakthroughs.",
        prompt="How do you represent slow work without pretending that nothing happens?",
        vocabulary=("Long uncertainty", "Flat segments", "Breakthroughs"),
    ),
    Benchmark(
        id="open-source-project",
        level=5,
        title="Build an open-source project",
        horizon_label="1 year",
        horizon_days=365,
        observation="Releases, contributors, forks and pivots make an excellent stress test.",
        prompt="Draw the first year of a project whose community changes the plan.",
        vocabulary=("Releases", "Contributors", "Forks", "Pivots", "Uncertainty"),
    ),
    Benchmark(
        id="public-initiative",
        level=6,
        title="Design a new public initiative",
        horizon_label="2 years",
        horizon_days=730,
        observation="Many paths interact; convergence is no longer an overlay but the main object.",
        prompt="Where must different actors align, and where can their paths remain distinct?",
        vocabulary=("Convergence", "Alignment", "Collective uncertainty"),
    ),
    Benchmark(
        id="apollo-programme",
        level=7,
        title="Reconstruct the Apollo programme",
        horizon_label="1961–1972",
        horizon_days=4018,
        observation="Reconstruct a historic path from the viewpoint of someone living through it.",
        prompt="What trajectory would you have drawn before the outcome was known?",
        vocabulary=("Reconstruction", "Milestones", "Regime changes"),
    ),
    Benchmark(
        id="wikipedia",
        level=7,
        title="Reconstruct Wikipedia",
        horizon_label="2001–today",
        horizon_days=9125,
        observation="A small release becomes global infrastructure through collective action.",
        prompt="Where would your imagined trajectory have underestimated participation?",
        vocabulary=("Release", "Convergence", "Emergence"),
    ),
    Benchmark(
        id="linux",
        level=7,
        title="Reconstruct Linux",
        horizon_label="1991–today",
        horizon_days=12775,
        observation="Forks, releases and distributed contribution challenge a single centreline.",
        prompt="How would you draw a project whose authorship continually expands?",
        vocabulary=("Forks", "Releases", "Collective trajectory"),
    ),
    Benchmark(
        id="human-genome",
        level=7,
        title="Reconstruct the Human Genome Project",
        horizon_label="1990–2003",
        horizon_days=4745,
        observation="Coordination, technical acceleration and public milestones interact.",
        prompt="Where did uncertainty shrink, and where did capability suddenly climb?",
        vocabulary=("Alignment", "Energy", "Milestones"),
    ),
    Benchmark(
        id="internet",
        level=7,
        title="Reconstruct the Internet",
        horizon_label="Several decades",
        horizon_days=10950,
        observation="No single roadmap can explain an infrastructure made by many trajectories.",
        prompt="Can one centreline represent this history—or only its convergence?",
        vocabulary=("Distributed paths", "Convergence", "Open landing"),
    ),
    Benchmark(
        id="climate-transition",
        level=8,
        title="Climate transition",
        horizon_label="25 years",
        horizon_days=9125,
        observation="Uncertainty dominates and the result resembles a landscape more than a plan.",
        prompt="Draw a trajectory without pretending that one actor controls it.",
        vocabulary=("Large uncertainty", "Multiple regimes", "Convergence"),
    ),
    Benchmark(
        id="european-ai-infrastructure",
        level=8,
        title="European AI infrastructure",
        horizon_label="10 years",
        horizon_days=3650,
        observation="Technical, political and institutional trajectories must become compatible.",
        prompt="Where must energy, alignment and chronology meet?",
        vocabulary=("Alignment", "Thresholds", "Collective uncertainty"),
    ),
    Benchmark(
        id="peace-negotiation",
        level=8,
        title="Peace negotiation",
        horizon_label="Unknown · test with 10 years",
        horizon_days=3650,
        observation="The admissible landing region matters more than a fixed endpoint.",
        prompt="How do you draw progress when rupture remains possible?",
        vocabulary=("Guided landing", "Kinks", "High uncertainty"),
    ),
    Benchmark(
        id="mars-mission",
        level=8,
        title="Mars mission",
        horizon_label="15 years",
        horizon_days=5475,
        observation="Long preparation converges on narrow launch and landing conditions.",
        prompt="Where does uncertainty transfer from design to operation?",
        vocabulary=("Planned landing", "Thresholds", "Long horizon"),
    ),
    Benchmark(
        id="paris-bicycle-friendly",
        level=8,
        title="Make Paris bicycle-friendly",
        horizon_label="Deliberately unresolved · test with 10 years",
        horizon_days=3650,
        observation="There is no correct answer; collective patterns are the result.",
        prompt="Draw a plausible path while knowing that no participant controls the whole system.",
        vocabulary=("Hidden benchmark", "Social cognition", "Convergence"),
        hidden=True,
    ),
)


CHALLENGES: tuple[Challenge, ...] = (
    Challenge(
        id="morning",
        number=1,
        title="Represent your morning",
        prompt="Compress an ordinary morning into a readable trajectory.",
        horizon_label="One morning",
        horizon_days=1,
        exercise_minutes=15,
        constraints=("Maximum 3 moves",),
    ),
    Challenge(
        id="dinner-friends",
        number=2,
        title="Organise dinner with friends",
        prompt="Show coordination without over-describing the plan.",
        horizon_label="One evening",
        horizon_days=1,
        exercise_minutes=None,
        constraints=("Maximum 5 moves", "Maximum 1 uncertainty"),
    ),
    Challenge(
        id="last-holiday",
        number=3,
        title="Represent your last holiday",
        prompt="Reconstruct the trip from its geometry rather than its itinerary.",
        horizon_label="The duration of the holiday",
        horizon_days=14,
        exercise_minutes=None,
        constraints=("Include 1 kink", "Include 1 uncertainty", "Include 1 milestone"),
    ),
    Challenge(
        id="phd",
        number=4,
        title="Represent your PhD",
        prompt="Draw the project as it felt, not as the final thesis describes it.",
        horizon_label="5 years",
        horizon_days=1825,
        exercise_minutes=None,
        constraints=("Use the whole horizon",),
    ),
    Challenge(
        id="next-year",
        number=5,
        title="Represent the next year of your life",
        prompt="Make a private trajectory. Nothing is shared.",
        horizon_label="1 year",
        horizon_days=365,
        exercise_minutes=None,
        constraints=("Private", "Nothing is shared"),
        private=True,
    ),
    Challenge(
        id="this-initiative",
        number=6,
        title="Represent this initiative",
        prompt="Draw independently, then compare with another participant.",
        horizon_label="2 years",
        horizon_days=730,
        exercise_minutes=None,
        constraints=("Compare after drawing",),
    ),
)


def benchmarks_for_level(level: int) -> tuple[Benchmark, ...]:
    return tuple(
        benchmark
        for benchmark in BENCHMARKS
        if benchmark.level == level and not benchmark.hidden
    )


def benchmark_by_id(benchmark_id: str) -> Benchmark:
    for benchmark in BENCHMARKS:
        if benchmark.id == benchmark_id:
            return benchmark
    raise KeyError(benchmark_id)


def challenge_by_id(challenge_id: str) -> Challenge:
    for challenge in CHALLENGES:
        if challenge.id == challenge_id:
            return challenge
    raise KeyError(challenge_id)

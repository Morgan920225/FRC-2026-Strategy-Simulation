"""
Statistics & Output (Agent 5) for the FRC 2026 REBUILT match simulation.

Provides:
- MonteCarloRunner: runs N simulations with different seeds, collects results
- Statistical analysis: win rates, score distributions, RP rates
- Output formatting: human-readable summary, JSON export, CSV row
"""

from __future__ import annotations

import json
import statistics
from typing import Any, Dict, List

from src.models import AllianceConfig, SimulationResult
from src.match_engine import MatchEngine


class MonteCarloRunner:
    """Runs multiple match simulations and collects statistics."""

    def __init__(
        self,
        red_alliance: AllianceConfig,
        blue_alliance: AllianceConfig,
        num_simulations: int = 100,
        base_seed: int = 42,
    ) -> None:
        self.red_alliance = red_alliance
        self.blue_alliance = blue_alliance
        self.num_simulations = num_simulations
        self.base_seed = base_seed

    def run(self) -> Dict[str, Any]:
        """Run all simulations and return aggregated statistics."""
        results: List[SimulationResult] = []

        for i in range(self.num_simulations):
            engine = MatchEngine(
                red_alliance=self.red_alliance,
                blue_alliance=self.blue_alliance,
                seed=self.base_seed + i,
            )
            result = engine.run()
            results.append(result)

        return compute_statistics(results)


def compute_statistics(results: List[SimulationResult]) -> Dict[str, Any]:
    """Compute aggregate statistics from a list of simulation results."""
    n = len(results)
    if n == 0:
        return {"error": "No simulation results to analyze"}

    # Extract score lists
    red_scores = [r.red_total_score for r in results]
    blue_scores = [r.blue_total_score for r in results]
    red_fuel = [r.red_fuel_scored for r in results]
    blue_fuel = [r.blue_fuel_scored for r in results]
    red_tower = [r.red_tower_points for r in results]
    blue_tower = [r.blue_tower_points for r in results]
    red_penalties = [r.red_penalties_drawn for r in results]
    blue_penalties = [r.blue_penalties_drawn for r in results]
    red_rps = [r.red_rp for r in results]
    blue_rps = [r.blue_rp for r in results]

    # Win rates
    red_wins = sum(1 for r in results if r.winner == "red")
    blue_wins = sum(1 for r in results if r.winner == "blue")
    ties = sum(1 for r in results if r.winner == "tie")

    # RP bonus rates
    red_energized_rate = sum(1 for r in results if r.red_energized) / n
    red_supercharged_rate = sum(1 for r in results if r.red_supercharged) / n
    red_traversal_rate = sum(1 for r in results if r.red_traversal) / n
    blue_energized_rate = sum(1 for r in results if r.blue_energized) / n
    blue_supercharged_rate = sum(1 for r in results if r.blue_supercharged) / n
    blue_traversal_rate = sum(1 for r in results if r.blue_traversal) / n

    def _safe_stdev(data: List[float]) -> float:
        return statistics.stdev(data) if len(data) >= 2 else 0.0

    return {
        "num_simulations": n,
        # Win rates
        "red_win_pct": red_wins / n * 100,
        "blue_win_pct": blue_wins / n * 100,
        "tie_pct": ties / n * 100,
        # Scores
        "red_avg_score": statistics.mean(red_scores),
        "blue_avg_score": statistics.mean(blue_scores),
        "red_score_stdev": _safe_stdev(red_scores),
        "blue_score_stdev": _safe_stdev(blue_scores),
        "red_score_min": min(red_scores),
        "red_score_max": max(red_scores),
        "blue_score_min": min(blue_scores),
        "blue_score_max": max(blue_scores),
        # Fuel
        "red_fuel_avg": statistics.mean(red_fuel),
        "blue_fuel_avg": statistics.mean(blue_fuel),
        "red_fuel_min": min(red_fuel),
        "red_fuel_max": max(red_fuel),
        "blue_fuel_min": min(blue_fuel),
        "blue_fuel_max": max(blue_fuel),
        # Tower
        "red_tower_avg": statistics.mean(red_tower),
        "blue_tower_avg": statistics.mean(blue_tower),
        # Penalties
        "red_penalty_avg": statistics.mean(red_penalties),
        "blue_penalty_avg": statistics.mean(blue_penalties),
        # RPs
        "red_rp_avg": statistics.mean(red_rps),
        "blue_rp_avg": statistics.mean(blue_rps),
        # RP bonus rates
        "red_energized_rate": red_energized_rate * 100,
        "red_supercharged_rate": red_supercharged_rate * 100,
        "red_traversal_rate": red_traversal_rate * 100,
        "blue_energized_rate": blue_energized_rate * 100,
        "blue_supercharged_rate": blue_supercharged_rate * 100,
        "blue_traversal_rate": blue_traversal_rate * 100,
        # Score distribution (histogram)
        "red_score_histogram": _histogram(red_scores),
        "blue_score_histogram": _histogram(blue_scores),
    }


def _histogram(scores: List[int], bucket_size: int = 10) -> Dict[str, int]:
    """Create a histogram of scores with the given bucket size."""
    if not scores:
        return {}
    buckets: Dict[str, int] = {}
    for score in scores:
        bucket = (score // bucket_size) * bucket_size
        key = f"{bucket}-{bucket + bucket_size - 1}"
        buckets[key] = buckets.get(key, 0) + 1
    return dict(sorted(buckets.items(), key=lambda x: int(x[0].split("-")[0])))


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_summary(stats: Dict[str, Any]) -> str:
    """Format statistics as a human-readable text summary."""
    lines = [
        "=" * 60,
        "FRC 2026 REBUILT - Match Simulation Results",
        "=" * 60,
        f"Simulations: {stats['num_simulations']}",
        "",
        "--- Win Rates ---",
        f"  Red:  {stats['red_win_pct']:.1f}%",
        f"  Blue: {stats['blue_win_pct']:.1f}%",
        f"  Tie:  {stats['tie_pct']:.1f}%",
        "",
        "--- Scores ---",
        f"  Red:  {stats['red_avg_score']:.1f} avg "
        f"(+/- {stats['red_score_stdev']:.1f}) "
        f"[{stats['red_score_min']}-{stats['red_score_max']}]",
        f"  Blue: {stats['blue_avg_score']:.1f} avg "
        f"(+/- {stats['blue_score_stdev']:.1f}) "
        f"[{stats['blue_score_min']}-{stats['blue_score_max']}]",
        "",
        "--- Fuel Scored ---",
        f"  Red:  {stats['red_fuel_avg']:.1f} avg "
        f"[{stats['red_fuel_min']}-{stats['red_fuel_max']}]",
        f"  Blue: {stats['blue_fuel_avg']:.1f} avg "
        f"[{stats['blue_fuel_min']}-{stats['blue_fuel_max']}]",
        "",
        "--- Tower Points ---",
        f"  Red:  {stats['red_tower_avg']:.1f} avg",
        f"  Blue: {stats['blue_tower_avg']:.1f} avg",
        "",
        "--- Penalties (awarded to opponent) ---",
        f"  Red:  {stats['red_penalty_avg']:.1f} avg",
        f"  Blue: {stats['blue_penalty_avg']:.1f} avg",
        "",
        "--- Ranking Points ---",
        f"  Red:  {stats['red_rp_avg']:.2f} avg",
        f"  Blue: {stats['blue_rp_avg']:.2f} avg",
        "",
        "--- RP Bonus Rates ---",
        f"  Red  Energized:    {stats['red_energized_rate']:.1f}%",
        f"  Red  Supercharged: {stats['red_supercharged_rate']:.1f}%",
        f"  Red  Traversal:    {stats['red_traversal_rate']:.1f}%",
        f"  Blue Energized:    {stats['blue_energized_rate']:.1f}%",
        f"  Blue Supercharged: {stats['blue_supercharged_rate']:.1f}%",
        f"  Blue Traversal:    {stats['blue_traversal_rate']:.1f}%",
        "=" * 60,
    ]
    return "\n".join(lines)


def to_json(stats: Dict[str, Any]) -> str:
    """Export statistics as a JSON string."""
    return json.dumps(stats, indent=2)


def to_csv_header() -> str:
    """Return CSV header row."""
    fields = [
        "num_simulations",
        "red_win_pct", "blue_win_pct", "tie_pct",
        "red_avg_score", "blue_avg_score",
        "red_score_stdev", "blue_score_stdev",
        "red_fuel_avg", "blue_fuel_avg",
        "red_tower_avg", "blue_tower_avg",
        "red_penalty_avg", "blue_penalty_avg",
        "red_rp_avg", "blue_rp_avg",
        "red_energized_rate", "red_supercharged_rate", "red_traversal_rate",
        "blue_energized_rate", "blue_supercharged_rate", "blue_traversal_rate",
    ]
    return ",".join(fields)


def to_csv_row(stats: Dict[str, Any]) -> str:
    """Export key statistics as a CSV row."""
    values = [
        stats["num_simulations"],
        f"{stats['red_win_pct']:.1f}", f"{stats['blue_win_pct']:.1f}",
        f"{stats['tie_pct']:.1f}",
        f"{stats['red_avg_score']:.1f}", f"{stats['blue_avg_score']:.1f}",
        f"{stats['red_score_stdev']:.1f}", f"{stats['blue_score_stdev']:.1f}",
        f"{stats['red_fuel_avg']:.1f}", f"{stats['blue_fuel_avg']:.1f}",
        f"{stats['red_tower_avg']:.1f}", f"{stats['blue_tower_avg']:.1f}",
        f"{stats['red_penalty_avg']:.1f}", f"{stats['blue_penalty_avg']:.1f}",
        f"{stats['red_rp_avg']:.2f}", f"{stats['blue_rp_avg']:.2f}",
        f"{stats['red_energized_rate']:.1f}", f"{stats['red_supercharged_rate']:.1f}",
        f"{stats['red_traversal_rate']:.1f}",
        f"{stats['blue_energized_rate']:.1f}", f"{stats['blue_supercharged_rate']:.1f}",
        f"{stats['blue_traversal_rate']:.1f}",
    ]
    return ",".join(str(v) for v in values)

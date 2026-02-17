"""
CLI Entry Point for the FRC 2026 REBUILT match simulation.

Usage:
    python -m src.main [OPTIONS]

Examples:
    # Default match: everybot vs everybot
    python -m src.main

    # Custom alliances
    python -m src.main --red elite_turret,strong_scorer,everybot --blue elite_multishot,everybot,defense_bot

    # With strategy presets
    python -m src.main --red elite_turret,strong_scorer,everybot --red-strategy full_offense \
                       --blue elite_multishot,everybot,defense_bot --blue-strategy 2_score_1_defend

    # Monte Carlo mode
    python -m src.main --red elite_turret,strong_scorer,everybot --blue everybot,everybot,kitbot_plus \
                       --num-sims 1000 --seed 42

    # Output JSON
    python -m src.main --output json

    # Single match mode (no Monte Carlo)
    python -m src.main --single
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import ARCHETYPE_DEFAULTS
from src.strategy import (
    create_alliance_config,
    parse_alliance_string,
    select_counter_strategy,
)
from src.stats import MonteCarloRunner, format_summary, to_json, to_csv_header, to_csv_row
from src.match_engine import MatchEngine


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="frc-sim",
        description="FRC 2026 REBUILT Match Simulation",
    )

    # Alliance composition
    parser.add_argument(
        "--red",
        type=str,
        default="everybot,everybot,everybot",
        help="Red alliance archetypes (comma-separated). "
             f"Valid: {', '.join(sorted(ARCHETYPE_DEFAULTS.keys()))}",
    )
    parser.add_argument(
        "--blue",
        type=str,
        default="everybot,everybot,everybot",
        help="Blue alliance archetypes (comma-separated).",
    )

    # Strategy presets
    parser.add_argument(
        "--red-strategy",
        type=str,
        default="full_offense",
        help="Red alliance strategy preset (default: full_offense).",
    )
    parser.add_argument(
        "--blue-strategy",
        type=str,
        default="full_offense",
        help="Blue alliance strategy preset (default: full_offense).",
    )

    # Auto counter-strategy
    parser.add_argument(
        "--auto-strategy",
        action="store_true",
        help="Automatically select counter-strategies based on opponent composition.",
    )

    # Simulation parameters
    parser.add_argument(
        "--num-sims", "-n",
        type=int,
        default=100,
        help="Number of Monte Carlo simulations (default: 100).",
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Base random seed (default: 42).",
    )

    # Single match mode
    parser.add_argument(
        "--single",
        action="store_true",
        help="Run a single match instead of Monte Carlo.",
    )

    # Output format
    parser.add_argument(
        "--output", "-o",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format (default: text).",
    )

    # Output file
    parser.add_argument(
        "--file", "-f",
        type=str,
        default=None,
        help="Write output to file instead of stdout.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Parse alliance compositions
    try:
        red_archetypes = parse_alliance_string(args.red)
        blue_archetypes = parse_alliance_string(args.blue)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Determine strategies
    red_strategy = args.red_strategy
    blue_strategy = args.blue_strategy

    if args.auto_strategy:
        # Auto-select counter strategies
        red_alliance_temp = create_alliance_config(red_archetypes, "full_offense")
        blue_strategy = select_counter_strategy(red_alliance_temp, red_archetypes)
        blue_alliance_temp = create_alliance_config(blue_archetypes, "full_offense")
        red_strategy = select_counter_strategy(blue_alliance_temp, blue_archetypes)
        print(f"Auto-selected strategies: Red={red_strategy}, Blue={blue_strategy}")

    # Create alliance configs
    try:
        red_alliance = create_alliance_config(red_archetypes, red_strategy)
        blue_alliance = create_alliance_config(blue_archetypes, blue_strategy)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Print match setup
    print(f"Red Alliance:  {', '.join(red_archetypes)} ({red_strategy})")
    print(f"Blue Alliance: {', '.join(blue_archetypes)} ({blue_strategy})")
    print()

    if args.single:
        # Single match mode
        engine = MatchEngine(red_alliance, blue_alliance, seed=args.seed)
        result = engine.run()

        print(f"Red Score:  {result.red_total_score}")
        print(f"Blue Score: {result.blue_total_score}")
        print(f"Winner:     {result.winner}")
        print(f"Red RP:     {result.red_rp}")
        print(f"Blue RP:    {result.blue_rp}")
        print(f"Red Fuel:   {result.red_fuel_scored}")
        print(f"Blue Fuel:  {result.blue_fuel_scored}")
        print(f"Red Tower:  {result.red_tower_points}")
        print(f"Blue Tower: {result.blue_tower_points}")

        if result.phase_scores:
            print("\nPhase Scores:")
            for phase, scores in result.phase_scores.items():
                print(f"  {phase}: Red={scores.get('red', 0)}, Blue={scores.get('blue', 0)}")

        return 0

    # Monte Carlo mode
    print(f"Running {args.num_sims} simulations (seed={args.seed})...")
    runner = MonteCarloRunner(
        red_alliance=red_alliance,
        blue_alliance=blue_alliance,
        num_simulations=args.num_sims,
        base_seed=args.seed,
    )
    stats = runner.run()

    # Format output
    if args.output == "json":
        output = to_json(stats)
    elif args.output == "csv":
        output = to_csv_header() + "\n" + to_csv_row(stats)
    else:
        output = format_summary(stats)

    # Write output
    if args.file:
        path = Path(args.file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output)
        print(f"Output written to {path}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())

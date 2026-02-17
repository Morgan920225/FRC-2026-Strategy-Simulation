"""
Strategy & Alliance Manager (Agent 4) for the FRC 2026 REBUILT match simulation.

Responsible for:
- Alliance composition (assign archetypes to robots)
- Strategy preset selection and application
- Per-robot role assignment per shift (scorer / stockpiler / defender)
- Human player mode configuration
- Endgame climb order optimisation
- Counter-strategy selection based on opponent alliance composition

Depends on: models, config
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.config import ARCHETYPE_DEFAULTS, RP_TRAVERSAL_THRESHOLD, TOWER_L1_TELEOP_POINTS, TOWER_L2_POINTS, TOWER_L3_POINTS
from src.models import (
    ActiveShiftRole,
    AllianceConfig,
    Archetype,
    AutoAction,
    DrivetrainType,
    GearRatio,
    HopperType,
    HumanPlayerMode,
    InactiveShiftRole,
    IndexerType,
    IntakeQuality,
    IntakeRobustness,
    IntakeType,
    RobotConfig,
    ShooterAngle,
    ShooterType,
    StrategyPreset,
    SwerveModule,
)


# ---------------------------------------------------------------------------
# Auto strategy presets
# ---------------------------------------------------------------------------

AUTO_PRESETS: Dict[str, List[AutoAction]] = {
    "all_score": [AutoAction.SCORE_FUEL] * 3,
    "2_score_1_climb": [AutoAction.SCORE_FUEL, AutoAction.SCORE_FUEL, AutoAction.CLIMB_L1],
    "2_score_1_disrupt": [AutoAction.SCORE_FUEL, AutoAction.SCORE_FUEL, AutoAction.DISRUPT_NEUTRAL],
    "1_score_1_climb_1_disrupt": [AutoAction.SCORE_FUEL, AutoAction.CLIMB_L1, AutoAction.DISRUPT_NEUTRAL],
}


# ---------------------------------------------------------------------------
# Mapping between ARCHETYPE_DEFAULTS keys and Archetype enum values
# ---------------------------------------------------------------------------
# The ARCHETYPE_DEFAULTS dict uses descriptive keys like "strong_scorer" and
# "defense_bot", while the Archetype enum uses shorter values like "strong"
# and "defense".  This mapping bridges the two.

_CONFIG_KEY_TO_ENUM: Dict[str, Archetype] = {
    "elite_turret": Archetype.ELITE_TURRET,
    "elite_multishot": Archetype.ELITE_MULTISHOT,
    "strong_scorer": Archetype.STRONG,
    "everybot": Archetype.EVERYBOT,
    "kitbot_plus": Archetype.KITBOT_PLUS,
    "kitbot_base": Archetype.KITBOT_BASE,
    "defense_bot": Archetype.DEFENSE,
}

_ENUM_TO_CONFIG_KEY: Dict[Archetype, str] = {v: k for k, v in _CONFIG_KEY_TO_ENUM.items()}


# ---------------------------------------------------------------------------
# Scoring-potential heuristic used for sorting robots within an alliance
# ---------------------------------------------------------------------------

def _get_archetype_defaults(archetype: Archetype) -> Dict[str, Any]:
    """Look up ARCHETYPE_DEFAULTS for a given Archetype enum member."""
    config_key = _ENUM_TO_CONFIG_KEY.get(archetype)
    if config_key and config_key in ARCHETYPE_DEFAULTS:
        return ARCHETYPE_DEFAULTS[config_key]
    # Fallback: try the enum value directly (works for most archetypes)
    return ARCHETYPE_DEFAULTS.get(archetype.value, {})


def _scoring_potential(cfg: RobotConfig) -> float:
    """Return a heuristic score representing a robot's offensive capability.

    Higher is better.  Used to rank robots within an alliance so that
    strategy presets can assign the *best* scorers to scoring roles and
    the *worst* to defense.
    """
    defaults = _get_archetype_defaults(cfg.archetype)
    accuracy: float = defaults.get("accuracy", 0.0)
    cycle_mean: float = defaults.get("cycle_time_mean", 99.0)

    # Avoid division by zero for defense bots (cycle_time_mean == 0)
    if cycle_mean <= 0:
        return 0.0

    # fuel scored per second (rough throughput) scaled by accuracy
    return (cfg.storage_capacity * accuracy) / cycle_mean


def _climb_capability(cfg: RobotConfig) -> float:
    """Return a numeric score for how well this robot can climb.

    Used to rank robots for endgame climb-target assignment.
    Weights higher levels more heavily, scaled by success probability.
    """
    defaults = _get_archetype_defaults(cfg.archetype)
    l1 = defaults.get("climb_success_L1", 0.0)
    l2 = defaults.get("climb_success_L2", 0.0)
    l3 = defaults.get("climb_success_L3", 0.0)

    # Weighted sum: L3 is most valuable, L1 least
    return l3 * TOWER_L3_POINTS + l2 * TOWER_L2_POINTS + l1 * TOWER_L1_TELEOP_POINTS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_alliance_string(alliance_str: str) -> List[str]:
    """Parse a CLI input string into a list of archetype names.

    Parameters
    ----------
    alliance_str : str
        Comma-separated archetype names, e.g.
        ``"elite_turret,strong_scorer,defense_bot"``.

    Returns
    -------
    list of str
        Validated archetype name strings.

    Raises
    ------
    ValueError
        If the string does not contain exactly 3 names, or if any name is
        not a key in ``ARCHETYPE_DEFAULTS``.
    """
    names = [n.strip() for n in alliance_str.split(",") if n.strip()]
    if len(names) != 3:
        raise ValueError(
            f"Expected exactly 3 archetype names separated by commas, got {len(names)}: {names}"
        )
    valid_keys = set(ARCHETYPE_DEFAULTS.keys())
    for name in names:
        if name not in valid_keys:
            raise ValueError(
                f"Unknown archetype '{name}'. Valid archetypes: {sorted(valid_keys)}"
            )
    return names


def create_robot_config(archetype_name: str) -> RobotConfig:
    """Create a ``RobotConfig`` from ``ARCHETYPE_DEFAULTS``.

    Parameters
    ----------
    archetype_name : str
        Key into ``ARCHETYPE_DEFAULTS`` (e.g. ``"elite_turret"``).

    Returns
    -------
    RobotConfig
        Fully populated configuration dataclass.

    Raises
    ------
    ValueError
        If *archetype_name* is not a valid key in ``ARCHETYPE_DEFAULTS``.
    """
    if archetype_name not in ARCHETYPE_DEFAULTS:
        raise ValueError(
            f"Unknown archetype '{archetype_name}'. "
            f"Valid archetypes: {sorted(ARCHETYPE_DEFAULTS.keys())}"
        )

    d: Dict[str, Any] = ARCHETYPE_DEFAULTS[archetype_name]

    # Map the config key to the Archetype enum member.
    archetype_enum = _CONFIG_KEY_TO_ENUM.get(archetype_name)
    if archetype_enum is None:
        raise ValueError(
            f"No Archetype enum mapping for config key '{archetype_name}'."
        )

    # Map string values to their respective enums, handling the special
    # case where defense_bot has shooter_angle = "none" (not in the enum).
    shooter_angle_str = d.get("shooter_angle", "fixed_high")
    if shooter_angle_str == "none":
        shooter_angle_val = ShooterAngle.FIXED_LOW  # placeholder for robots with no shooter
    else:
        shooter_angle_val = ShooterAngle(shooter_angle_str)

    drivetrain_type = DrivetrainType(d["drivetrain"])

    # Swerve module: assign a reasonable default based on drivetrain
    if drivetrain_type == DrivetrainType.SWERVE:
        swerve_module = SwerveModule.SDS_MK4I
    else:
        swerve_module = SwerveModule.NONE

    # Gear ratio: infer from free speed
    free_speed = d.get("free_speed_fps", 14.0)
    if free_speed >= 17.0:
        gear_ratio = GearRatio.L3
    elif free_speed >= 14.0:
        gear_ratio = GearRatio.L2
    else:
        gear_ratio = GearRatio.L1

    # Map indexer_type string to enum
    indexer_str = d.get("indexer_type", "conveyor")
    indexer_val = IndexerType(indexer_str)

    storage_cap = d.get("storage_capacity", d["fuel_capacity"])

    return RobotConfig(
        archetype=archetype_enum,
        # Drivetrain
        drivetrain=drivetrain_type,
        swerve_module=swerve_module,
        gear_ratio=gear_ratio,
        free_speed_fps=free_speed,
        can_fit_trench=True,
        # Shooter
        shooter_type=ShooterType(d["shooter_type"]),
        shooter_angle=shooter_angle_val,
        hopper_type=HopperType(d["hopper_type"]),
        indexer_type=indexer_val,
        fuel_capacity=storage_cap,
        storage_capacity=storage_cap,
        effective_range=d["effective_range"],
        can_shoot_while_moving=d["can_shoot_while_moving"],
        intake_rate=d.get("intake_rate", 4.0),
        shoot_rate=d.get("shoot_rate", 6.0),
        # Intake
        intake_type=IntakeType(d["intake_type"]),
        intake_quality=IntakeQuality(d["intake_quality"]),
        intake_robustness=IntakeRobustness(d["intake_robustness"]),
        # Strategy defaults (overridden by apply_strategy_preset)
        auto_fuel_target=d["auto_fuel"],
        auto_action=AutoAction.SCORE_FUEL,
        auto_cycles=d.get("auto_cycles", 1),
        auto_climb=d.get("auto_climb", False),
        climb_target=d["climb_level"],
        climb_start_time=d.get("climb_start_time", 10.0),
        active_shift_role=ActiveShiftRole.SCORE,
        inactive_shift_role=InactiveShiftRole.STOCKPILE,
        defense_target=None,
        preposition_before_shift=True,
    )


def create_alliance_config(
    archetype_names: List[str],
    strategy_preset: str = "full_offense",
    auto_plan: Optional[List[str]] = None,
) -> AllianceConfig:
    """Build an ``AllianceConfig`` from archetype names and a strategy preset.

    Parameters
    ----------
    archetype_names : list of str
        Exactly 3 archetype name strings (keys in ``ARCHETYPE_DEFAULTS``).
    strategy_preset : str, optional
        One of the five strategy presets defined in the spec (Section 10).
        Defaults to ``"full_offense"``.
    auto_plan : list of str, optional
        Per-robot auto actions (length 3).  Valid values:
        ``"score_fuel"``, ``"climb_l1"``, ``"disrupt"``.
        Defaults to all ``"score_fuel"``.

    Returns
    -------
    AllianceConfig
        Fully configured alliance ready to hand to the Match Engine.

    Raises
    ------
    ValueError
        If the number of archetypes is not 3, or if an invalid preset is
        given.
    """
    if len(archetype_names) != 3:
        raise ValueError(
            f"An alliance requires exactly 3 robots, got {len(archetype_names)}."
        )

    # Validate preset early
    try:
        preset_enum = StrategyPreset(strategy_preset)
    except ValueError:
        valid = [p.value for p in StrategyPreset]
        raise ValueError(
            f"Unknown strategy preset '{strategy_preset}'. Valid presets: {valid}"
        )

    robots = [create_robot_config(name) for name in archetype_names]

    # Parse auto plan
    if auto_plan is not None:
        if len(auto_plan) != 3:
            raise ValueError(f"auto_plan must have exactly 3 entries, got {len(auto_plan)}")
        auto_actions = [AutoAction(a) for a in auto_plan]
        # Validate: at most 1 robot does CLIMB_L1
        climb_count = sum(1 for a in auto_actions if a == AutoAction.CLIMB_L1)
        if climb_count > 1:
            raise ValueError("At most 1 robot per alliance can do CLIMB_L1 in auto")
        # Apply to individual robot configs
        for i, action in enumerate(auto_actions):
            robots[i].auto_action = action
    else:
        auto_actions = [AutoAction.SCORE_FUEL] * 3

    alliance = AllianceConfig(
        robots=robots,
        strategy_preset=preset_enum,
        human_player_mode=HumanPlayerMode.MIXED,
        endgame_plan=[0, 0, 0],
        auto_plan=auto_actions,
    )

    apply_strategy_preset(alliance, strategy_preset)
    assign_endgame_plan(alliance)

    return alliance


def apply_strategy_preset(alliance: AllianceConfig, preset: str) -> None:
    """Apply a strategy preset to an alliance, setting per-robot roles.

    This mutates the ``RobotConfig`` objects inside *alliance* in place.

    Parameters
    ----------
    alliance : AllianceConfig
        Alliance whose robots will be configured.
    preset : str
        One of ``"full_offense"``, ``"2_score_1_defend"``,
        ``"1_score_2_defend"``, ``"deny_and_score"``, or ``"surge"``.

    Raises
    ------
    ValueError
        If *preset* is not recognised.
    """
    robots = alliance.robots
    if len(robots) != 3:
        raise ValueError("Alliance must have exactly 3 robots.")

    # Sort indices by scoring potential (descending).  Index 0 = best scorer.
    indexed = sorted(range(3), key=lambda i: _scoring_potential(robots[i]), reverse=True)
    best, mid, worst = indexed

    # Default opponent defense target: opponent robot index 0 (their best scorer).
    opponent_best = "opponent_0"

    if preset == StrategyPreset.FULL_OFFENSE.value:
        _apply_full_offense(alliance, robots)

    elif preset == StrategyPreset.TWO_SCORE_ONE_DEFEND.value:
        _apply_2_score_1_defend(alliance, robots, best, mid, worst, opponent_best)

    elif preset == StrategyPreset.ONE_SCORE_TWO_DEFEND.value:
        _apply_1_score_2_defend(alliance, robots, best, mid, worst, opponent_best)

    elif preset == StrategyPreset.DENY_AND_SCORE.value:
        _apply_deny_and_score(alliance, robots, best, mid, worst)

    elif preset == StrategyPreset.SURGE.value:
        _apply_surge(alliance, robots)

    else:
        valid = [p.value for p in StrategyPreset]
        raise ValueError(
            f"Unknown strategy preset '{preset}'. Valid presets: {valid}"
        )

    alliance.strategy_preset = StrategyPreset(preset)


def assign_endgame_plan(alliance: AllianceConfig) -> None:
    """Assign climb targets to each robot to maximise tower points.

    Sorts robots by climb capability (best climber first) and assigns the
    highest feasible climb level to each.  The goal is to meet or exceed
    ``RP_TRAVERSAL_THRESHOLD`` (50 tower points) if the alliance has the
    mechanical ability to do so.

    This mutates ``RobotConfig.climb_target`` and ``alliance.endgame_plan``
    in place.

    Parameters
    ----------
    alliance : AllianceConfig
        Alliance whose endgame plan will be set.
    """
    robots = alliance.robots

    # Sort indices by climb capability descending
    indexed = sorted(range(len(robots)), key=lambda i: _climb_capability(robots[i]), reverse=True)

    # Available climb levels to assign, highest first
    available_levels = [3, 2, 1]

    plan = [0] * len(robots)

    for rank, robot_idx in enumerate(indexed):
        defaults = _get_archetype_defaults(robots[robot_idx].archetype)
        if rank < len(available_levels):
            target_level = available_levels[rank]
        else:
            target_level = 0

        # Only assign a level if the robot has a non-zero success rate for it
        success_key = f"climb_success_L{target_level}"
        success_rate = defaults.get(success_key, 0.0)

        if success_rate > 0.0:
            plan[robot_idx] = target_level
            robots[robot_idx].climb_target = target_level
        else:
            # Try lower levels until one works
            assigned = False
            for fallback in range(target_level - 1, 0, -1):
                fb_key = f"climb_success_L{fallback}"
                if defaults.get(fb_key, 0.0) > 0.0:
                    plan[robot_idx] = fallback
                    robots[robot_idx].climb_target = fallback
                    assigned = True
                    break
            if not assigned:
                plan[robot_idx] = 0
                robots[robot_idx].climb_target = 0

    # Check if we meet the traversal threshold and try to optimise if not
    expected_points = _expected_tower_points(robots, plan)
    if expected_points < RP_TRAVERSAL_THRESHOLD:
        # Try bumping any robot that could go higher
        for robot_idx in indexed:
            defaults = _get_archetype_defaults(robots[robot_idx].archetype)
            current = plan[robot_idx]
            for higher in range(current + 1, 4):
                hk = f"climb_success_L{higher}"
                if defaults.get(hk, 0.0) > 0.05:  # at least 5% chance
                    plan[robot_idx] = higher
                    robots[robot_idx].climb_target = higher
                    break
            if _expected_tower_points(robots, plan) >= RP_TRAVERSAL_THRESHOLD:
                break

    alliance.endgame_plan = plan


def select_counter_strategy(
    our_alliance: AllianceConfig,
    opponent_archetypes: List[str],
) -> str:
    """Recommend a strategy preset based on opponent alliance composition.

    Parameters
    ----------
    our_alliance : AllianceConfig
        Our alliance configuration (used for context but not currently
        mutated).
    opponent_archetypes : list of str
        The 3 archetype names of the opposing alliance.

    Returns
    -------
    str
        The recommended strategy preset name (a ``StrategyPreset`` value).
    """
    # Categorise opponent robots
    elite_turrets = sum(1 for a in opponent_archetypes if a == "elite_turret")
    elite_multishots = sum(1 for a in opponent_archetypes if a == "elite_multishot")
    strong_scorers = sum(1 for a in opponent_archetypes if a == "strong_scorer")
    low_tier = sum(
        1 for a in opponent_archetypes
        if a in ("kitbot_base", "kitbot_plus", "defense_bot")
    )
    everybots = sum(1 for a in opponent_archetypes if a == "everybot")

    total_strong_or_better = elite_turrets + elite_multishots + strong_scorers

    # Rule 1: If opponent has an elite turret, defense is less effective
    # against it (turret compensates).  Prefer outscoring them.
    if elite_turrets >= 1:
        # If they also have multiple other strong scorers we still might
        # want some defense against the NON-turret scorers.
        if total_strong_or_better >= 3:
            return StrategyPreset.SURGE.value
        return StrategyPreset.FULL_OFFENSE.value

    # Rule 2: If opponent has multiple strong+ scorers (but no turret),
    # defense is very effective against fixed-shooter robots.
    if total_strong_or_better >= 2:
        return StrategyPreset.TWO_SCORE_ONE_DEFEND.value

    # Rule 3: If opponent has one dominant scorer and weaker partners
    if total_strong_or_better == 1:
        return StrategyPreset.TWO_SCORE_ONE_DEFEND.value

    # Rule 4: If opponent is all low-tier, no need for defense
    if low_tier + everybots == 3:
        return StrategyPreset.FULL_OFFENSE.value

    # Fallback
    return StrategyPreset.FULL_OFFENSE.value


# ---------------------------------------------------------------------------
# Private helpers -- one per strategy preset
# ---------------------------------------------------------------------------

def _apply_full_offense(
    alliance: AllianceConfig,
    robots: List[RobotConfig],
) -> None:
    """Full Offense: All 3 robots score during active shifts, stockpile during inactive."""
    alliance.human_player_mode = HumanPlayerMode.MIXED

    for robot in robots:
        robot.active_shift_role = ActiveShiftRole.SCORE
        robot.inactive_shift_role = InactiveShiftRole.STOCKPILE
        robot.defense_target = None
        robot.preposition_before_shift = True


def _apply_2_score_1_defend(
    alliance: AllianceConfig,
    robots: List[RobotConfig],
    best: int,
    mid: int,
    worst: int,
    opponent_target: str,
) -> None:
    """2 Score + 1 Defend: 2 best scorers score/stockpile; worst defends."""
    alliance.human_player_mode = HumanPlayerMode.FEED

    # Best two scorers
    for idx in (best, mid):
        robots[idx].active_shift_role = ActiveShiftRole.SCORE
        robots[idx].inactive_shift_role = InactiveShiftRole.STOCKPILE
        robots[idx].defense_target = None
        robots[idx].preposition_before_shift = True

    # Worst scorer / defense bot defends full-time
    robots[worst].active_shift_role = ActiveShiftRole.DEFEND
    robots[worst].inactive_shift_role = InactiveShiftRole.DEFEND
    robots[worst].defense_target = opponent_target
    robots[worst].preposition_before_shift = False


def _apply_1_score_2_defend(
    alliance: AllianceConfig,
    robots: List[RobotConfig],
    best: int,
    mid: int,
    worst: int,
    opponent_target: str,
) -> None:
    """1 Score + 2 Defend: Only best scorer scores; other 2 defend."""
    alliance.human_player_mode = HumanPlayerMode.THROW

    # Best scorer
    robots[best].active_shift_role = ActiveShiftRole.SCORE
    robots[best].inactive_shift_role = InactiveShiftRole.STOCKPILE
    robots[best].defense_target = None
    robots[best].preposition_before_shift = True

    # Two defenders
    for idx in (mid, worst):
        robots[idx].active_shift_role = ActiveShiftRole.DEFEND
        robots[idx].inactive_shift_role = InactiveShiftRole.DEFEND
        robots[idx].defense_target = opponent_target
        robots[idx].preposition_before_shift = False


def _apply_deny_and_score(
    alliance: AllianceConfig,
    robots: List[RobotConfig],
    best: int,
    mid: int,
    worst: int,
) -> None:
    """Deny & Score: All 3 score during active; inactive: 2 stockpile, 1 denies neutral zone."""
    alliance.human_player_mode = HumanPlayerMode.FEED

    # During active shifts all three score
    for robot in robots:
        robot.active_shift_role = ActiveShiftRole.SCORE
        robot.preposition_before_shift = True
        robot.defense_target = None

    # During inactive shifts: best two stockpile, worst camps neutral zone
    robots[best].inactive_shift_role = InactiveShiftRole.STOCKPILE
    robots[mid].inactive_shift_role = InactiveShiftRole.STOCKPILE
    robots[worst].inactive_shift_role = InactiveShiftRole.DENY_NEUTRAL
    robots[worst].preposition_before_shift = True  # still needs to get to Hub when shift changes


def _apply_surge(
    alliance: AllianceConfig,
    robots: List[RobotConfig],
) -> None:
    """Surge: All 3 score during active (dump stockpile first); all stockpile at outpost during inactive."""
    alliance.human_player_mode = HumanPlayerMode.FEED

    for robot in robots:
        robot.active_shift_role = ActiveShiftRole.SCORE
        robot.inactive_shift_role = InactiveShiftRole.STOCKPILE
        robot.defense_target = None
        robot.preposition_before_shift = True


# ---------------------------------------------------------------------------
# Endgame helper
# ---------------------------------------------------------------------------

def _expected_tower_points(robots: List[RobotConfig], plan: List[int]) -> float:
    """Compute expected tower points given a climb plan.

    Parameters
    ----------
    robots : list of RobotConfig
        The three robot configs.
    plan : list of int
        Climb target per robot (0/1/2/3).

    Returns
    -------
    float
        Expected tower points (probability-weighted).
    """
    total = 0.0
    level_points = {
        0: 0,
        1: TOWER_L1_TELEOP_POINTS,
        2: TOWER_L2_POINTS,
        3: TOWER_L3_POINTS,
    }
    for i, level in enumerate(plan):
        if level == 0:
            continue
        defaults = _get_archetype_defaults(robots[i].archetype)
        success_key = f"climb_success_L{level}"
        prob = defaults.get(success_key, 0.0)
        total += prob * level_points[level]
    return total

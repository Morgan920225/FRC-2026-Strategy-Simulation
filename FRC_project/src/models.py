"""
Shared dataclasses and enums for the FRC 2026 REBUILT match simulation.

All modules import their data structures from here. This file has no
internal dependencies -- it relies only on the Python standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Alliance(str, Enum):
    RED = "red"
    BLUE = "blue"


class Phase(str, Enum):
    AUTO = "auto"
    TRANSITION = "transition"
    SHIFT1 = "shift1"
    SHIFT2 = "shift2"
    SHIFT3 = "shift3"
    SHIFT4 = "shift4"
    ENDGAME = "endgame"


class RobotZone(str, Enum):
    ALLIANCE = "alliance"
    MIDFIELD = "midfield"
    NEUTRAL = "neutral"
    HUB = "hub"
    TOWER = "tower"
    OUTPOST = "outpost"
    OPPONENT_ZONE = "opponent_zone"
    TRENCH = "trench"


class RobotAction(str, Enum):
    IDLE = "idle"
    INTAKING = "intaking"
    DRIVING = "driving"
    SHOOTING = "shooting"
    CLIMBING = "climbing"
    DEFENDING = "defending"
    STOCKPILING = "stockpiling"
    PRE_POSITIONING = "pre_positioning"
    DUMPING = "dumping"
    PUSHING_FUEL = "pushing_fuel"
    CLEARING_JAM = "clearing_jam"
    WAITING_FOR_FUEL = "waiting_for_fuel"


class ShiftRole(str, Enum):
    SCORER = "scorer"
    STOCKPILER = "stockpiler"
    DEFENDER = "defender"
    PUSHER = "pusher"


class Archetype(str, Enum):
    ELITE_TURRET = "elite_turret"
    ELITE_MULTISHOT = "elite_multishot"
    STRONG = "strong"
    EVERYBOT = "everybot"
    KITBOT_PLUS = "kitbot_plus"
    KITBOT_BASE = "kitbot_base"
    DEFENSE = "defense"


class DrivetrainType(str, Enum):
    SWERVE = "swerve"
    TANK = "tank"
    MECANUM = "mecanum"


class SwerveModule(str, Enum):
    SDS_MK4I = "sds_mk4i"
    SDS_MK4N = "sds_mk4n"
    SDS_MK5N = "sds_mk5n"
    WCP_X2 = "wcp_x2"
    WCP_X2S = "wcp_x2s"
    REV_MAX = "rev_max"
    NONE = "none"


class GearRatio(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    X1 = "X1"
    X2 = "X2"
    X3 = "X3"


class ShooterType(str, Enum):
    SINGLE_TURRET = "single_turret"
    DOUBLE_FIXED = "double_fixed"
    TRIPLE_FIXED = "triple_fixed"
    SINGLE_FIXED = "single_fixed"
    DUMPER = "dumper"
    NONE = "none"


class ShooterAngle(str, Enum):
    FIXED_LOW = "fixed_low"
    FIXED_HIGH = "fixed_high"
    ADJUSTABLE = "adjustable"
    FULL_VARIABLE = "full_variable"


class HopperType(str, Enum):
    LARGE = "large"
    MEDIUM = "medium"
    SMALL = "small"
    SERIALIZER = "serializer"
    SPINDEXER = "spindexer"


class IndexerType(str, Enum):
    SPINDEXER = "spindexer"        # Fast serialization, low jam (elite turret)
    SERIALIZER = "serializer"      # Belt-fed, reliable (elite multishot)
    CONVEYOR = "conveyor"          # Simple belt, medium speed
    GRAVITY_FED = "gravity_fed"    # Dump from top, fast but less controlled
    NONE = "none"                  # No indexer (defense bot)


class AutoAction(str, Enum):
    SCORE_FUEL = "score_fuel"       # Drive, intake, shoot - multiple cycles
    CLIMB_L1 = "climb_l1"          # Climb L1 (15 pts) then descend - costs ~6-8s
    DISRUPT_NEUTRAL = "disrupt"    # Push/scatter neutral zone fuel


class IntakeType(str, Enum):
    OVER_BUMPER = "over_bumper"
    FUNNEL = "funnel"
    NONE = "none"


class IntakeQuality(str, Enum):
    TOUCH_AND_GO = "touch_and_go"
    SLOW_PICKUP = "slow_pickup"
    PUSH_AROUND = "push_around"
    NO_GROUND_PICKUP = "no_ground_pickup"


class IntakeRobustness(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MechanismStatus(str, Enum):
    NOMINAL = "nominal"
    DEGRADED = "degraded"
    BROKEN = "broken"


class TurretStatus(str, Enum):
    NOMINAL = "nominal"
    STUCK = "stuck"


class HumanPlayerMode(str, Enum):
    FEED = "feed"
    THROW = "throw"
    MIXED = "mixed"


class StrategyPreset(str, Enum):
    FULL_OFFENSE = "full_offense"
    TWO_SCORE_ONE_DEFEND = "2_score_1_defend"
    ONE_SCORE_TWO_DEFEND = "1_score_2_defend"
    DENY_AND_SCORE = "deny_and_score"
    SURGE = "surge"


class ActiveShiftRole(str, Enum):
    SCORE = "score"
    DEFEND = "defend"
    SCORE_AND_DEFEND = "score_and_defend"


class InactiveShiftRole(str, Enum):
    STOCKPILE = "stockpile"
    DEFEND = "defend"
    DENY_NEUTRAL = "deny_neutral"
    PUSH_FUEL = "push_fuel"


class PhaseActionType(str, Enum):
    SCORING_CYCLE = "scoring_cycle"
    STOCKPILE_CYCLE = "stockpile_cycle"
    DEFENDING = "defending"
    PRE_POSITIONING = "pre_positioning"
    CLIMBING = "climbing"
    DUMP_STOCKPILE = "dump_stockpile"
    PUSHING_FUEL = "pushing_fuel"
    HP_FED_SCORING = "hp_fed_scoring"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MatchState:
    """Central match state, owned by the Match Engine (Agent 1)."""

    time_remaining: float = 160.0
    current_phase: Phase = Phase.AUTO
    red_hub_active: bool = True
    blue_hub_active: bool = True
    red_score: int = 0
    blue_score: int = 0
    red_fuel_scored: int = 0
    blue_fuel_scored: int = 0
    red_tower_points: int = 0
    blue_tower_points: int = 0
    red_penalties: int = 0        # penalty points awarded TO blue FROM red fouls
    blue_penalties: int = 0       # penalty points awarded TO red FROM blue fouls


@dataclass
class RobotState:
    """Per-robot state tracked every tick, owned by Robot Behavior (Agent 2)."""

    id: str = ""                                       # e.g. "red_1", "blue_3"
    alliance: Alliance = Alliance.RED
    archetype: Archetype = Archetype.EVERYBOT
    position: RobotZone = RobotZone.ALLIANCE
    fuel_held: int = 0
    fuel_capacity: int = 6                             # kept for compat
    storage_capacity: int = 6                          # realistic capacity
    is_stockpiling: bool = False
    is_climbing: bool = False
    climb_level: int = 0                               # 0=none, 1/2/3
    is_defending: bool = False
    is_pushing_fuel: bool = False
    fuel_being_pushed: int = 0                         # fuel being bulldozed (not in robot)
    current_action: RobotAction = RobotAction.IDLE
    action_timer: float = 0.0                          # seconds until current action completes
    shift_role: ShiftRole = ShiftRole.SCORER
    intake_status: MechanismStatus = MechanismStatus.NOMINAL
    shooter_status: MechanismStatus = MechanismStatus.NOMINAL
    fouls_drawn_this_match: int = 0


@dataclass
class RobotConfig:
    """Static robot configuration set before match start (Agent 4 -> Agent 2)."""

    # Identity
    archetype: Archetype = Archetype.EVERYBOT

    # -- Drivetrain --
    drivetrain: DrivetrainType = DrivetrainType.SWERVE
    swerve_module: SwerveModule = SwerveModule.SDS_MK4I
    gear_ratio: GearRatio = GearRatio.L2
    free_speed_fps: float = 14.0
    can_fit_trench: bool = True

    # -- Shooter --
    shooter_type: ShooterType = ShooterType.SINGLE_FIXED
    shooter_angle: ShooterAngle = ShooterAngle.FIXED_HIGH
    hopper_type: HopperType = HopperType.MEDIUM
    indexer_type: IndexerType = IndexerType.CONVEYOR
    fuel_capacity: int = 6                             # alias kept for compat
    storage_capacity: int = 6                          # realistic capacity (1-55)
    effective_range: float = 8.0                       # max distance (ft) from Hub
    can_shoot_while_moving: bool = False
    intake_rate: float = 4.0                           # fuel per second intake speed
    shoot_rate: float = 6.0                            # fuel per second shooting speed

    # -- Intake --
    intake_type: IntakeType = IntakeType.OVER_BUMPER
    intake_quality: IntakeQuality = IntakeQuality.SLOW_PICKUP
    intake_robustness: IntakeRobustness = IntakeRobustness.MEDIUM

    # -- Strategy --
    auto_fuel_target: int = 2
    auto_action: AutoAction = AutoAction.SCORE_FUEL
    auto_cycles: int = 1                               # how many score cycles in auto (1-3)
    auto_climb: bool = False
    climb_target: int = 2                              # 0/1/2/3 for endgame
    climb_start_time: float = 10.0                     # seconds remaining to start climbing (0=never)
    active_shift_role: ActiveShiftRole = ActiveShiftRole.SCORE
    inactive_shift_role: InactiveShiftRole = InactiveShiftRole.STOCKPILE
    defense_target: Optional[str] = None               # opponent robot id to defend
    preposition_before_shift: bool = True


@dataclass
class RobotRuntimeState:
    """Tracks mid-match mechanism degradation and failures."""

    intake_status: MechanismStatus = MechanismStatus.NOMINAL
    shooter_status: MechanismStatus = MechanismStatus.NOMINAL
    turret_status: TurretStatus = TurretStatus.NOMINAL
    current_archetype_override: Optional[Archetype] = None
    fouls_drawn: int = 0
    fuel_pushed_to_zone: int = 0


@dataclass
class FieldState:
    """Global field state, owned by the Field State Manager (Agent 3)."""

    neutral_fuel_available: int = 20
    red_outpost_fuel: int = 10
    blue_outpost_fuel: int = 10
    fuel_in_flight: int = 0
    fuel_in_transit: int = 0
    transit_queue: List[Tuple[float, int]] = field(default_factory=list)
    red_tower_occupants: List[str] = field(default_factory=list)
    blue_tower_occupants: List[str] = field(default_factory=list)
    congestion_red_hub: float = 0.0                    # 0.0 - 1.0
    congestion_blue_hub: float = 0.0                   # 0.0 - 1.0

    def total_fuel_check(self, robots: List[RobotState]) -> int:
        """Conservation invariant -- must always equal TOTAL_FUEL (60).

        Parameters
        ----------
        robots : list of RobotState
            All robots on the field (both alliances).

        Returns
        -------
        int
            The total fuel accounted for across all states.
        """
        fuel_in_robots = sum(r.fuel_held + r.fuel_being_pushed for r in robots)
        return (
            self.neutral_fuel_available
            + self.red_outpost_fuel
            + self.blue_outpost_fuel
            + self.fuel_in_flight
            + self.fuel_in_transit
            + fuel_in_robots
        )


@dataclass
class AllianceConfig:
    """Alliance-level configuration (Agent 4 -> Agent 1, Agent 2)."""

    robots: List[RobotConfig] = field(default_factory=list)
    strategy_preset: StrategyPreset = StrategyPreset.FULL_OFFENSE
    human_player_mode: HumanPlayerMode = HumanPlayerMode.MIXED
    endgame_plan: List[int] = field(default_factory=lambda: [3, 2, 1])
    auto_plan: List[AutoAction] = field(
        default_factory=lambda: [AutoAction.SCORE_FUEL] * 3
    )


@dataclass
class PhaseAction:
    """Snapshot of what a robot is doing at a given moment, driven by shift state."""

    phase: Phase = Phase.AUTO
    hub_active: bool = True
    action: PhaseActionType = PhaseActionType.SCORING_CYCLE
    fuel_held: int = 0
    position: RobotZone = RobotZone.ALLIANCE
    time_in_action: float = 0.0


@dataclass
class SimulationResult:
    """Final output of a single simulated match (Agent 5)."""

    red_total_score: int = 0
    blue_total_score: int = 0
    red_rp: int = 0
    blue_rp: int = 0
    winner: str = "tie"                                # "red" | "blue" | "tie"
    red_fuel_scored: int = 0
    blue_fuel_scored: int = 0
    red_tower_points: int = 0
    blue_tower_points: int = 0
    red_penalties_drawn: int = 0
    blue_penalties_drawn: int = 0
    red_energized: bool = False
    red_supercharged: bool = False
    red_traversal: bool = False
    blue_energized: bool = False
    blue_supercharged: bool = False
    blue_traversal: bool = False
    phase_scores: Dict[str, Dict[str, int]] = field(default_factory=dict)

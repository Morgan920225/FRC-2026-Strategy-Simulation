"""
FRC 2026 REBUILT Match Simulation -- Configuration Constants

All constants are derived from the game specification (FRC simulation.md).
Grouped by category exactly as they appear in Section 15 "Key Constants Reference",
with archetype defaults derived from Sections 7.5 and 7.6.
"""

from typing import Dict, Any, List

# =============================================================================
# Match timing (seconds)
# =============================================================================
AUTO_DURATION: float = 20.0
TRANSITION_DURATION: float = 10.0
SHIFT_DURATION: float = 25.0
ENDGAME_DURATION: float = 30.0
TOTAL_MATCH_DURATION: float = 160.0
TICK_INTERVAL: float = 0.5

# =============================================================================
# Scoring
# =============================================================================
FUEL_ACTIVE_HUB_POINTS: int = 1
FUEL_INACTIVE_HUB_POINTS: int = 0
TOWER_L1_AUTO_POINTS: int = 15
TOWER_L1_TELEOP_POINTS: int = 10
TOWER_L2_POINTS: int = 20
TOWER_L3_POINTS: int = 30
FOUL_POINTS: int = 5
TECH_FOUL_POINTS: int = 12

# =============================================================================
# Ranking Points
# =============================================================================
RP_WIN: int = 3
RP_TIE: int = 1
RP_ENERGIZED_THRESHOLD: int = 100     # fuel points scored
RP_SUPERCHARGED_THRESHOLD: int = 360  # fuel points scored
RP_TRAVERSAL_THRESHOLD: int = 50      # tower points

# =============================================================================
# Human Player
# =============================================================================
HP_THROW_INTERVAL: float = 4.0       # seconds between throws
HP_FEED_INTERVAL: float = 2.5        # seconds between feeds to robot
HP_THROW_ACCURACY: float = 0.55      # 55% base accuracy

# =============================================================================
# Field
# =============================================================================
INITIAL_NEUTRAL_FUEL: int = 20
INITIAL_OUTPOST_FUEL: int = 10        # per alliance
INITIAL_PRELOAD_FUEL: int = 10        # per alliance (split across 3 robots)
TOTAL_FUEL: int = 60                  # conserved quantity -- never changes

# =============================================================================
# Fuel Physics (closed-loop recycling)
# =============================================================================
FUEL_FLIGHT_TIME: float = 1.0        # seconds: shot leaves robot -> enters Hub
FUEL_HUB_TRANSIT_TIME: float = 1.5   # seconds: Hub fall-through -> available on field
FUEL_TOTAL_RECYCLE_TIME: float = 2.5  # FLIGHT + TRANSIT
FUEL_MISS_RECOVERY_TIME: float = 3.0  # seconds: missed shot -> ball settles on field
HP_THROW_FLIGHT_TIME: float = 1.5    # seconds: HP throw -> enters Hub

# =============================================================================
# Robot limits
# =============================================================================
MAX_TOWER_OCCUPANTS: int = 3          # per alliance tower

# =============================================================================
# Shooter parameters
# =============================================================================
TURRET_ALIGN_TIME: float = 0.0       # turret tracks automatically
FIXED_ALIGN_TIME: float = 1.5        # seconds to rotate robot to face Hub
DUMPER_ALIGN_TIME: float = 0.0       # must already be at Hub
SHOOT_RATE_SINGLE: float = 3.0       # fuel per second (single barrel)
SHOOT_RATE_DOUBLE: float = 6.5       # fuel per second (double barrel)
SHOOT_RATE_TRIPLE: float = 9.0       # fuel per second (triple barrel)
SHOOT_RATE_DUMPER: float = 15.0      # fuel per second (all at once, gravity dump)

# =============================================================================
# Hopper parameters
# =============================================================================
JAM_RATE_LARGE_HOPPER: float = 0.075  # 7.5% per dump cycle
JAM_RATE_SERIALIZER: float = 0.005    # 0.5% per dump cycle
JAM_CLEAR_TIME: float = 3.5           # seconds to clear a jam

# =============================================================================
# Auto phase constants
# =============================================================================
AUTO_L1_CLIMB_TIME: float = 4.0       # seconds to climb L1 in auto
AUTO_L1_DESCEND_TIME: float = 3.0     # seconds to descend back to field
AUTO_PRELOAD_MAX: int = 8             # max fuel preloaded before match

# =============================================================================
# Indexer parameters
# =============================================================================
INDEXER_RATES: Dict[str, float] = {   # fuel/second throughput to shooter
    "spindexer": 10.0,
    "serializer": 8.0,
    "conveyor": 6.0,
    "gravity_fed": 15.0,
    "none": 0.0,
}
INDEXER_JAM_RATES: Dict[str, float] = {
    "spindexer": 0.005,
    "serializer": 0.005,
    "conveyor": 0.01,
    "gravity_fed": 0.075,
    "none": 0.0,
}

# =============================================================================
# Reliability -- mechanism failures
# =============================================================================
TURRET_FAILURE_RATE: float = 0.12     # 12% per match
MULTISHOT_FAILURE_RATE: float = 0.12  # 12% per match (one barrel)
BASIC_FAILURE_RATE: float = 0.04      # 4% per match

# =============================================================================
# Intake failure & degradation
# =============================================================================
INTAKE_BREAK_RATE_COMPLEX: float = 0.06    # 6% per match (under-bumper, exposed)
INTAKE_BREAK_RATE_SIMPLE: float = 0.02     # 2% per match (over-bumper, protected)
INTAKE_DEGRADE_RATE_COMPLEX: float = 0.15  # 15% per match
INTAKE_DEGRADE_RATE_SIMPLE: float = 0.07   # 7% per match
INTAKE_JAM_RATE: float = 0.10             # 10% per match
INTAKE_JAM_CLEAR_TIME: float = 3.0        # seconds to reverse and clear jam
DEGRADED_INTAKE_SPEED_MULT: float = 0.5   # 50% of normal intake speed
DEGRADED_INTAKE_SUCCESS_RATE: float = 0.60  # 60% chance of picking up fuel per attempt

# =============================================================================
# Fuel pushing mechanics
# =============================================================================
PUSH_SPEED_FPS: float = 6.0               # feet/second while pushing fuel cluster
PUSH_FUEL_PER_TRIP: int = 5               # average fuel pushed per trip
PUSH_SCATTER_RATE: float = 0.20           # 20% of pushed fuel scatters away
PUSH_TRIP_TIME: float = 7.0               # seconds per push trip (push + return)
TRENCH_PUSH_TIME: float = 4.0             # seconds to push fuel through trench

# =============================================================================
# Defense penalty rates by zone
# =============================================================================
FOUL_RATE_NEUTRAL_ZONE: float = 0.08      # 8% per shift
FOUL_RATE_OPPONENT_ALLIANCE: float = 0.20  # 20% per shift (higher scrutiny)
FOUL_RATE_NEAR_TOWER: float = 0.25        # 25% per shift
TECH_FOUL_RATE_NEUTRAL: float = 0.015     # 1.5% per shift
TECH_FOUL_RATE_ALLIANCE: float = 0.06     # 6% per shift
TECH_FOUL_RATE_TOWER: float = 0.10        # 10% per shift
PENALTY_ESCALATION_MULT: List[float] = [1.0, 1.5, 2.0]  # indexed by fouls_drawn

# =============================================================================
# Defense impact on shooter types
# =============================================================================
DEFENSE_CYCLE_HIT_TURRET: float = 0.35    # +35% cycle time
DEFENSE_CYCLE_HIT_FIXED: float = 0.50     # +50% cycle time
DEFENSE_ACCURACY_HIT_TURRET: float = 0.08  # -8% accuracy
DEFENSE_ACCURACY_HIT_FIXED: float = 0.20   # -20% accuracy

# =============================================================================
# Phase-aware strategy timing
# =============================================================================
PREPOSITION_TIME_FROM_NEUTRAL: float = 2.5   # seconds: Neutral Zone -> own Hub
PREPOSITION_TIME_FROM_OUTPOST: float = 3.0   # seconds: Outpost -> own Hub
CROSSFIELD_DRIVE_TIME: float = 5.0           # seconds: opponent zone -> own Hub
DUMP_TIME_PER_FUEL: float = 0.3              # seconds per fuel when dumping stockpile
SHIFT_ANTICIPATION_TIME: float = 3.0         # seconds before shift change to start pre-positioning

# =============================================================================
# Drivetrain speeds (practical, not free speed)
# =============================================================================
SWERVE_PRACTICAL_SPEED_FPS: float = 13.0    # typical L2 swerve
TANK_PRACTICAL_SPEED_FPS: float = 10.0      # typical AM14U tank
SWERVE_ALIGN_TIME: float = 0.0              # can strafe, no rotation needed
TANK_ALIGN_TIME: float = 1.5                # must rotate to face Hub


# =============================================================================
# Archetype Default Configurations
# =============================================================================
# Derived from Section 7.6 Archetype Summary Table, Section 7.5 Community Robot
# Baselines, and Section 7.9 Climb Success Rates.
#
# cycle_time_mean / cycle_time_stddev follow the spec rule: stddev = 15% of mean.
# Accuracy is the midpoint of the range from the archetype summary table.
# auto_fuel is the midpoint of the range.
# fuel_capacity is the midpoint of the range (rounded).
# climb_level is the highest level the archetype targets.
# =============================================================================

ARCHETYPE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "elite_turret": {
        # Section 7.5: Custom Elite / Section 7.6 row 1
        "fuel_capacity": 14,                 # realistic storage
        "storage_capacity": 14,
        "cycle_time_mean": 8.5,              # 7-10s
        "cycle_time_stddev": 1.275,          # 15% of 8.5
        "auto_fuel": 8,                      # full preload (1 cycle)
        "auto_cycles": 1,
        "climb_level": 3,                    # L3
        "accuracy": 0.90,                    # 85-95%, midpoint
        "climb_success_L1": 0.99,
        "climb_success_L2": 0.95,
        "climb_success_L3": 0.85,
        "shooter_type": "single_turret",
        "shooter_angle": "full_variable",
        "hopper_type": "spindexer",
        "indexer_type": "spindexer",
        "intake_rate": 8.0,                  # fuel/s
        "shoot_rate": 10.0,                  # fuel/s
        "effective_range": 20.0,             # 4-20+ ft
        "can_shoot_while_moving": True,
        "intake_type": "over_bumper",
        "intake_quality": "touch_and_go",
        "intake_robustness": "medium",       # under-bumper is more exposed
        "drivetrain": "swerve",
        "free_speed_fps": 16.0,              # L2/L3 tier swerve
        "auto_climb": False,
        "climb_start_time": 12.0,            # L3 target: start climb with 12s left
    },
    "elite_multishot": {
        # Section 7.5: WCP CC "Big Dumper" / Section 7.6 row 2
        "fuel_capacity": 20,                 # realistic storage
        "storage_capacity": 20,
        "cycle_time_mean": 12.0,             # 10-14s
        "cycle_time_stddev": 1.8,            # 15% of 12.0
        "auto_fuel": 8,                      # full preload (1 cycle)
        "auto_cycles": 1,
        "climb_level": 3,                    # L2-L3, targets L3
        "accuracy": 0.775,                   # 70-85%, midpoint
        "climb_success_L1": 0.99,
        "climb_success_L2": 0.90,
        "climb_success_L3": 0.75,
        "shooter_type": "triple_fixed",
        "shooter_angle": "fixed_high",
        "hopper_type": "serializer",
        "indexer_type": "serializer",
        "intake_rate": 8.0,                  # fuel/s
        "shoot_rate": 15.0,                  # fuel/s
        "effective_range": 12.0,             # 4-12 ft
        "can_shoot_while_moving": False,
        "intake_type": "over_bumper",
        "intake_quality": "touch_and_go",
        "intake_robustness": "high",
        "drivetrain": "swerve",
        "free_speed_fps": 15.0,              # L2 swerve
        "auto_climb": False,
        "climb_start_time": 12.0,            # L3 target
    },
    "strong_scorer": {
        # Section 7.6 row 3: Upgraded Everybot
        "fuel_capacity": 14,                 # realistic storage
        "storage_capacity": 14,
        "cycle_time_mean": 14.0,             # 12-16s
        "cycle_time_stddev": 2.1,            # 15% of 14.0
        "auto_fuel": 6,                      # 6 preloaded
        "auto_cycles": 1,
        "climb_level": 2,                    # L2
        "accuracy": 0.725,                   # 65-80%, midpoint
        "climb_success_L1": 0.98,
        "climb_success_L2": 0.85,
        "climb_success_L3": 0.55,
        "shooter_type": "double_fixed",
        "shooter_angle": "adjustable",
        "hopper_type": "medium",
        "indexer_type": "conveyor",
        "intake_rate": 6.0,                  # fuel/s
        "shoot_rate": 8.0,                   # fuel/s
        "effective_range": 10.0,             # 4-10 ft
        "can_shoot_while_moving": False,
        "intake_type": "over_bumper",
        "intake_quality": "touch_and_go",
        "intake_robustness": "high",
        "drivetrain": "swerve",
        "free_speed_fps": 14.0,              # L2 swerve
        "auto_climb": False,
        "climb_start_time": 8.0,             # L2 target
    },
    "everybot": {
        # Section 7.5: Robonauts 118 Everybot / Section 7.6 row 4
        "fuel_capacity": 10,                 # realistic storage
        "storage_capacity": 10,
        "cycle_time_mean": 18.5,             # 15-22s
        "cycle_time_stddev": 2.775,          # 15% of 18.5
        "auto_fuel": 4,                      # 4 preloaded
        "auto_cycles": 1,
        "climb_level": 2,                    # L1-L2, targets L2
        "accuracy": 0.575,                   # 50-65%, midpoint
        "climb_success_L1": 0.95,
        "climb_success_L2": 0.70,
        "climb_success_L3": 0.25,
        "shooter_type": "single_fixed",
        "shooter_angle": "fixed_high",
        "hopper_type": "medium",
        "indexer_type": "conveyor",
        "intake_rate": 4.0,                  # fuel/s
        "shoot_rate": 6.0,                   # fuel/s
        "effective_range": 8.0,              # 3-8 ft
        "can_shoot_while_moving": False,
        "intake_type": "over_bumper",
        "intake_quality": "slow_pickup",
        "intake_robustness": "high",
        "drivetrain": "swerve",
        "free_speed_fps": 13.0,              # L2 swerve (or tank)
        "auto_climb": False,
        "climb_start_time": 8.0,             # L2 target
    },
    "kitbot_plus": {
        # Section 7.5: Iterated KitBot / Section 7.6 row 5
        "fuel_capacity": 20,                 # realistic storage
        "storage_capacity": 20,
        "cycle_time_mean": 24.0,             # 20-28s
        "cycle_time_stddev": 3.6,            # 15% of 24.0
        "auto_fuel": 3,                      # 3 preloaded
        "auto_cycles": 1,
        "climb_level": 1,                    # L1
        "accuracy": 0.475,                   # 40-55%, midpoint
        "climb_success_L1": 0.80,
        "climb_success_L2": 0.30,
        "climb_success_L3": 0.0,
        "shooter_type": "single_fixed",
        "shooter_angle": "fixed_low",
        "hopper_type": "large",
        "indexer_type": "gravity_fed",
        "intake_rate": 3.0,                  # fuel/s
        "shoot_rate": 4.0,                   # fuel/s
        "effective_range": 6.0,              # 2-6 ft
        "can_shoot_while_moving": False,
        "intake_type": "over_bumper",
        "intake_quality": "slow_pickup",
        "intake_robustness": "high",
        "drivetrain": "tank",
        "free_speed_fps": 12.0,              # AM14U tank
        "auto_climb": False,
        "climb_start_time": 5.0,             # L1 target
    },
    "kitbot_base": {
        # Section 7.5: Stock KitBot / Section 7.6 row 6
        "fuel_capacity": 15,                 # realistic storage
        "storage_capacity": 15,
        "cycle_time_mean": 30.0,             # 25-35s
        "cycle_time_stddev": 4.5,            # 15% of 30.0
        "auto_fuel": 1,                      # 1 preloaded
        "auto_cycles": 1,
        "climb_level": 0,                    # None
        "accuracy": 0.375,                   # 30-45%, midpoint
        "climb_success_L1": 0.0,
        "climb_success_L2": 0.0,
        "climb_success_L3": 0.0,
        "shooter_type": "single_fixed",
        "shooter_angle": "fixed_low",
        "hopper_type": "large",
        "indexer_type": "gravity_fed",
        "intake_rate": 2.0,                  # fuel/s
        "shoot_rate": 3.0,                   # fuel/s
        "effective_range": 4.0,              # 2-6 ft (shorter end)
        "can_shoot_while_moving": False,
        "intake_type": "funnel",
        "intake_quality": "push_around",
        "intake_robustness": "medium",
        "drivetrain": "tank",
        "free_speed_fps": 10.0,              # AM14U tank, slow
        "auto_climb": False,
        "climb_start_time": 0.0,             # no climb
    },
    "defense_bot": {
        # Section 7.6 row 7
        "fuel_capacity": 2,                  # 0-3, midpoint ~2
        "storage_capacity": 2,
        "cycle_time_mean": 0.0,              # N/A -- does not score cycles
        "cycle_time_stddev": 0.0,
        "auto_fuel": 0,                      # 0-1, low end
        "auto_cycles": 0,
        "climb_level": 1,                    # L1
        "accuracy": 0.275,                   # 20-35%, midpoint
        "climb_success_L1": 0.75,
        "climb_success_L2": 0.10,
        "climb_success_L3": 0.0,
        "shooter_type": "none",
        "shooter_angle": "none",
        "hopper_type": "small",
        "indexer_type": "none",
        "intake_rate": 0.0,                  # no intake
        "shoot_rate": 0.0,                   # no shooter
        "effective_range": 0.0,
        "can_shoot_while_moving": False,
        "intake_type": "none",
        "intake_quality": "no_ground_pickup",
        "intake_robustness": "high",         # minimal mechanisms to fail
        "drivetrain": "swerve",
        "free_speed_fps": 14.0,              # fast for chasing opponents
        "auto_climb": True,                  # defense bots may attempt L1 in auto
        "climb_start_time": 5.0,             # L1 target
    },
}

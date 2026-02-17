"""
Robot Behavior Engine (Agent 2) for FRC 2026 REBUILT match simulation.

Implements per-tick robot behavior including scoring cycles, stockpiling,
defense, fuel pushing, climbing, intake quality, mid-match failures,
autonomous routines, and shift-change role transitions.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, Optional

from .models import (
    Alliance,
    Archetype,
    ActiveShiftRole,
    AutoAction,
    DrivetrainType,
    HopperType,
    InactiveShiftRole,
    IndexerType,
    IntakeQuality,
    MatchState,
    MechanismStatus,
    Phase,
    RobotAction,
    RobotConfig,
    RobotRuntimeState,
    RobotState,
    RobotZone,
    ShiftRole,
    ShooterType,
    TurretStatus,
)
from .config import (
    ARCHETYPE_DEFAULTS,
    AUTO_L1_CLIMB_TIME,
    AUTO_L1_DESCEND_TIME,
    CROSSFIELD_DRIVE_TIME,
    DEFENSE_ACCURACY_HIT_FIXED,
    DEFENSE_ACCURACY_HIT_TURRET,
    DEFENSE_CYCLE_HIT_FIXED,
    DEFENSE_CYCLE_HIT_TURRET,
    DEGRADED_INTAKE_SPEED_MULT,
    DEGRADED_INTAKE_SUCCESS_RATE,
    DUMP_TIME_PER_FUEL,
    FIXED_ALIGN_TIME,
    FOUL_POINTS,
    FOUL_RATE_NEUTRAL_ZONE,
    FOUL_RATE_NEAR_TOWER,
    FOUL_RATE_OPPONENT_ALLIANCE,
    INDEXER_JAM_RATES,
    INDEXER_RATES,
    INTAKE_BREAK_RATE_SIMPLE,
    INTAKE_DEGRADE_RATE_SIMPLE,
    INTAKE_JAM_CLEAR_TIME,
    INTAKE_JAM_RATE,
    JAM_CLEAR_TIME,
    JAM_RATE_LARGE_HOPPER,
    JAM_RATE_SERIALIZER,
    MULTISHOT_FAILURE_RATE,
    BASIC_FAILURE_RATE,
    PENALTY_ESCALATION_MULT,
    PREPOSITION_TIME_FROM_NEUTRAL,
    PREPOSITION_TIME_FROM_OUTPOST,
    PUSH_FUEL_PER_TRIP,
    PUSH_SCATTER_RATE,
    PUSH_TRIP_TIME,
    SHOOT_RATE_DOUBLE,
    SHOOT_RATE_DUMPER,
    SHOOT_RATE_SINGLE,
    SHOOT_RATE_TRIPLE,
    TECH_FOUL_POINTS,
    TECH_FOUL_RATE_ALLIANCE,
    TECH_FOUL_RATE_NEUTRAL,
    TECH_FOUL_RATE_TOWER,
    TICK_INTERVAL,
    TURRET_ALIGN_TIME,
    TURRET_FAILURE_RATE,
)

if TYPE_CHECKING:
    pass  # field_manager type would go here


# ---------------------------------------------------------------------------
# Intake quality parameters: (success_rate_range, time_per_fuel_range)
# ---------------------------------------------------------------------------
_INTAKE_QUALITY_PARAMS: Dict[str, Dict[str, tuple]] = {
    IntakeQuality.TOUCH_AND_GO.value: {
        "success_range": (0.95, 0.99),
        "time_range": (0.2, 0.4),
    },
    IntakeQuality.SLOW_PICKUP.value: {
        "success_range": (0.80, 0.90),
        "time_range": (0.5, 1.0),
    },
    IntakeQuality.PUSH_AROUND.value: {
        "success_range": (0.50, 0.70),
        "time_range": (1.0, 3.0),
    },
    IntakeQuality.NO_GROUND_PICKUP.value: {
        "success_range": (0.0, 0.0),
        "time_range": (0.0, 0.0),
    },
}


def _shoot_rate_for_type(shooter_type: ShooterType) -> float:
    """Return fuel-per-second for the given shooter type."""
    return {
        ShooterType.SINGLE_TURRET: SHOOT_RATE_SINGLE,
        ShooterType.SINGLE_FIXED: SHOOT_RATE_SINGLE,
        ShooterType.DOUBLE_FIXED: SHOOT_RATE_DOUBLE,
        ShooterType.TRIPLE_FIXED: SHOOT_RATE_TRIPLE,
        ShooterType.DUMPER: SHOOT_RATE_DUMPER,
        ShooterType.NONE: 0.0,
    }.get(shooter_type, SHOOT_RATE_SINGLE)


def _align_time_for_shooter(
    shooter_type: ShooterType, turret_status: TurretStatus
) -> float:
    """Return alignment time in seconds.

    Turret robots skip alignment unless the turret is stuck.
    Dumper robots have zero align time (must already be at hub).
    Fixed-shooter robots require FIXED_ALIGN_TIME.
    """
    if shooter_type == ShooterType.SINGLE_TURRET:
        if turret_status == TurretStatus.STUCK:
            return FIXED_ALIGN_TIME
        return TURRET_ALIGN_TIME
    if shooter_type == ShooterType.DUMPER:
        return 0.0
    # All fixed variants
    return FIXED_ALIGN_TIME


def _jam_rate_for_hopper(hopper_type: HopperType) -> float:
    """Return jam probability per dump cycle for the given hopper type."""
    if hopper_type == HopperType.LARGE:
        return JAM_RATE_LARGE_HOPPER
    if hopper_type in (HopperType.SERIALIZER, HopperType.SPINDEXER):
        return JAM_RATE_SERIALIZER
    # Medium / small -- in between, use low jam rate
    return JAM_RATE_SERIALIZER * 2  # ~1%


class Robot:
    """Simulates a single FRC robot throughout a match.

    The robot does NOT directly score -- it sets its state (action, fuel_held,
    etc.) and the Match Engine reads that state to coordinate with the
    Field Manager.  However, the robot DOES call ``field_manager.try_intake()``
    when intaking fuel from the field.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        robot_id: str,
        alliance: Alliance,
        config: RobotConfig,
        rng: random.Random,
    ) -> None:
        self.robot_id = robot_id
        self.alliance = alliance
        self.config = config
        self.rng = rng

        # Archetype defaults for convenience.
        # Map Archetype enum values to ARCHETYPE_DEFAULTS keys, which may
        # differ (e.g. Archetype.STRONG="strong" -> key "strong_scorer",
        # Archetype.DEFENSE="defense" -> key "defense_bot").
        _ARCH_KEY_MAP = {
            "strong": "strong_scorer",
            "defense": "defense_bot",
        }
        arch_key = config.archetype.value
        mapped_key = _ARCH_KEY_MAP.get(arch_key, arch_key)
        self._arch: Dict = ARCHETYPE_DEFAULTS.get(
            mapped_key,
            ARCHETYPE_DEFAULTS.get(arch_key, {}),
        )

        # Build RobotState
        self.state = RobotState(
            id=robot_id,
            alliance=alliance,
            archetype=config.archetype,
            position=RobotZone.ALLIANCE,
            fuel_held=0,
            fuel_capacity=config.storage_capacity,
            storage_capacity=config.storage_capacity,
            current_action=RobotAction.IDLE,
            action_timer=0.0,
            shift_role=ShiftRole.SCORER,
            intake_status=MechanismStatus.NOMINAL,
            shooter_status=MechanismStatus.NOMINAL,
        )

        # Build RobotRuntimeState (tracks mid-match degradation)
        self.runtime = RobotRuntimeState()

        # Internal bookkeeping
        self._cycle_time_mean: float = self._arch.get("cycle_time_mean", 18.0)
        self._cycle_time_stddev: float = self._arch.get("cycle_time_stddev", 2.7)
        self._accuracy: float = self._arch.get("accuracy", 0.50)
        # Shoot rate: min of config shoot_rate and indexer throughput (bottleneck)
        indexer_rate = INDEXER_RATES.get(config.indexer_type.value, 6.0)
        self._shoot_rate: float = min(config.shoot_rate, indexer_rate) if config.shoot_rate > 0 else _shoot_rate_for_type(config.shooter_type)
        self._intake_rate: float = config.intake_rate
        self._effective_shooter: ShooterType = config.shooter_type
        self._intake_quality: IntakeQuality = config.intake_quality
        self._failures_checked: bool = False

        # Auto routine tracking
        self._auto_fuel_scored: int = 0
        self._auto_cycles_completed: int = 0
        self._auto_climb_attempted: bool = False
        self._auto_climb_scored: bool = False  # Track if L1 was scored in auto
        self._auto_shooting_started: bool = False
        self._auto_descending: bool = False

        # Stockpile tracking
        self._stockpile_ready: bool = False  # True when full & pre-positioned

        # Cycle sub-phase tracking for multi-step cycles
        self._cycle_phase: str = "idle"  # idle/drive_to_fuel/intaking/drive_to_hub/aligning/shooting

        # Defense tracking
        self._defense_foul_checked_this_shift: bool = False
        self._current_shift_phase: Optional[Phase] = None

        # Climb tracking
        self._climb_attempted_teleop: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_state(self) -> RobotState:
        """Return the current robot state snapshot."""
        return self.state

    def tick(self, match_state: MatchState, field_manager, dt: float = TICK_INTERVAL) -> None:
        """Main update, called every simulation tick.

        Parameters
        ----------
        match_state : MatchState
            Current match state from the Match Engine.
        field_manager :
            Field State Manager instance (Agent 3).  The robot calls
            ``field_manager.try_intake(alliance, zone, count)`` when intaking.
        dt : float
            Tick duration in seconds (default 0.5).
        """
        # Run one-time failure check at match start
        if not self._failures_checked:
            self.check_failures()
            self._failures_checked = True

        # Detect shift change -> call on_shift_change
        self._detect_shift_change(match_state)

        phase = match_state.current_phase

        # Phase-specific top-level behavior
        if phase == Phase.AUTO:
            self._tick_auto(match_state, field_manager, dt)
        elif phase == Phase.TRANSITION:
            self._tick_transition(match_state, dt)
        elif phase == Phase.ENDGAME:
            self._tick_endgame(match_state, field_manager, dt)
        else:
            # Teleop shifts 1-4
            self._tick_teleop_shift(match_state, field_manager, dt)

    def on_shift_change(self, hub_active: bool) -> None:
        """Handle a shift change event.

        Switch the robot's role based on whether its alliance Hub is now active,
        using the configured active/inactive shift roles from RobotConfig.

        Parameters
        ----------
        hub_active : bool
            True if this robot's alliance Hub is active in the new shift.
        """
        if hub_active:
            self._apply_active_role()
        else:
            self._apply_inactive_role()

        # Reset per-shift defense foul tracking
        self._defense_foul_checked_this_shift = False

    def check_failures(self) -> None:
        """Roll for mid-match mechanism failures.

        Called once at match start.  Modifies ``self.runtime`` and
        ``self.state`` to reflect any failures.
        """
        self._check_intake_failure()
        self._check_shooter_failure()
        self._check_turret_failure()

    def dump_stockpile(self) -> None:
        """Begin rapid-fire scoring of held fuel (stockpile dump).

        Transitions the robot to DUMPING action with a timer based on
        fuel held * DUMP_TIME_PER_FUEL.
        """
        if self.state.fuel_held <= 0:
            return
        dump_time = self.state.fuel_held * DUMP_TIME_PER_FUEL
        self.state.current_action = RobotAction.DUMPING
        self.state.action_timer = dump_time
        self.state.is_stockpiling = False
        self._stockpile_ready = False
        self._cycle_phase = "dumping"

    def get_defense_effects(self) -> Dict[str, float]:
        """Return the defense disruption this robot inflicts on its target.

        Returns a dict with ``cycle_hit`` (fractional increase to cycle time)
        and ``accuracy_hit`` (absolute accuracy reduction) based on the
        target's shooter type.  Only meaningful when this robot is defending.

        The caller (Match Engine) is responsible for looking up the target
        robot and applying these effects.
        """
        if not self.state.is_defending:
            return {"cycle_hit": 0.0, "accuracy_hit": 0.0}

        # Determine target's shooter type from defense_target config.
        # We return generic values keyed by fixed vs turret -- the match engine
        # resolves the actual target shooter type.
        return {
            "cycle_hit_turret": DEFENSE_CYCLE_HIT_TURRET,
            "cycle_hit_fixed": DEFENSE_CYCLE_HIT_FIXED,
            "accuracy_hit_turret": DEFENSE_ACCURACY_HIT_TURRET,
            "accuracy_hit_fixed": DEFENSE_ACCURACY_HIT_FIXED,
        }

    # ------------------------------------------------------------------
    # Shift change helpers
    # ------------------------------------------------------------------

    def _detect_shift_change(self, match_state: MatchState) -> None:
        """Detect when the phase changes and trigger on_shift_change."""
        phase = match_state.current_phase
        if phase != self._current_shift_phase:
            old_phase = self._current_shift_phase
            self._current_shift_phase = phase

            # Only trigger shift change for teleop shifts and endgame
            if phase in (Phase.SHIFT1, Phase.SHIFT2, Phase.SHIFT3, Phase.SHIFT4):
                hub_active = self._is_hub_active(match_state)
                self.on_shift_change(hub_active)
            elif phase == Phase.ENDGAME:
                # Endgame: both hubs active, switch to scoring + climb prep
                self.on_shift_change(hub_active=True)

    def _is_hub_active(self, match_state: MatchState) -> bool:
        """Check whether this robot's alliance Hub is active."""
        if self.alliance == Alliance.RED:
            return match_state.red_hub_active
        return match_state.blue_hub_active

    def _apply_active_role(self) -> None:
        """Set role for an active-hub shift."""
        role = self.config.active_shift_role

        if role == ActiveShiftRole.SCORE:
            self.state.shift_role = ShiftRole.SCORER
            self.state.is_defending = False
            self.state.is_pushing_fuel = False
            # If we have stockpiled fuel, dump it first
            if self.state.fuel_held > 0 and self.state.is_stockpiling:
                self.dump_stockpile()
            else:
                self._start_scoring_cycle()

        elif role == ActiveShiftRole.DEFEND:
            self.state.shift_role = ShiftRole.DEFENDER
            self.state.is_defending = True
            self.state.is_stockpiling = False
            self.state.is_pushing_fuel = False
            self._start_defense()

        elif role == ActiveShiftRole.SCORE_AND_DEFEND:
            # Dump stockpile first if available, then defend
            if self.state.fuel_held > 0 and self.state.is_stockpiling:
                self.state.shift_role = ShiftRole.SCORER
                self.dump_stockpile()
            else:
                self.state.shift_role = ShiftRole.DEFENDER
                self.state.is_defending = True
                self._start_defense()

    def _apply_inactive_role(self) -> None:
        """Set role for an inactive-hub shift."""
        role = self.config.inactive_shift_role

        if role == InactiveShiftRole.STOCKPILE:
            self.state.shift_role = ShiftRole.STOCKPILER
            self.state.is_stockpiling = True
            self.state.is_defending = False
            self.state.is_pushing_fuel = False
            self._start_stockpile_cycle()

        elif role == InactiveShiftRole.DEFEND:
            self.state.shift_role = ShiftRole.DEFENDER
            self.state.is_defending = True
            self.state.is_stockpiling = False
            self.state.is_pushing_fuel = False
            self._start_defense()

        elif role == InactiveShiftRole.DENY_NEUTRAL:
            # Camp neutral zone and grab fuel before opponents
            self.state.shift_role = ShiftRole.STOCKPILER
            self.state.is_stockpiling = True
            self.state.is_defending = False
            self.state.is_pushing_fuel = False
            self._start_stockpile_cycle()

        elif role == InactiveShiftRole.PUSH_FUEL:
            self.state.shift_role = ShiftRole.PUSHER
            self.state.is_pushing_fuel = True
            self.state.is_stockpiling = False
            self.state.is_defending = False
            self._start_push_cycle()

    # ------------------------------------------------------------------
    # Phase tick handlers
    # ------------------------------------------------------------------

    def _tick_auto(
        self, match_state: MatchState, field_manager, dt: float
    ) -> None:
        """Handle autonomous period behavior.

        Behavior depends on auto_action from config:
        - SCORE_FUEL: shoot preloaded fuel, optionally do multiple cycles
        - CLIMB_L1: drive to tower, climb L1, descend
        - DISRUPT_NEUTRAL: drive to neutral zone and scatter fuel
        """
        # If we're still counting down an action, decrement and maybe complete
        if self.state.action_timer > 0:
            self.state.action_timer -= dt
            if self.state.action_timer <= 0:
                self._complete_auto_action(match_state, field_manager)
            return

        auto_action = self.config.auto_action

        if auto_action == AutoAction.SCORE_FUEL:
            self._tick_auto_score(match_state, field_manager)
        elif auto_action == AutoAction.CLIMB_L1:
            self._tick_auto_climb(match_state)
        elif auto_action == AutoAction.DISRUPT_NEUTRAL:
            self._tick_auto_disrupt(match_state, field_manager)

    def _tick_auto_score(self, match_state: MatchState, field_manager) -> None:
        """Auto SCORE_FUEL: shoot preloaded, optionally cycle back for more."""
        max_cycles = self.config.auto_cycles

        if self._auto_fuel_scored < self.config.auto_fuel_target or (
            self._auto_cycles_completed < max_cycles
            and self.state.fuel_held > 0
        ):
            if not self._auto_shooting_started:
                self._auto_shooting_started = True
                # Drive to shooting position (1-2s)
                self.state.current_action = RobotAction.DRIVING
                self.state.position = RobotZone.HUB
                drive_time = self.rng.uniform(1.0, 2.0)
                self.state.action_timer = drive_time
                self._cycle_phase = "auto_drive"
            else:
                # Shoot all held fuel at once
                self._start_auto_shot_burst()
        elif (
            self._auto_cycles_completed > 0
            and self._auto_cycles_completed < max_cycles
            and self.state.fuel_held == 0
        ):
            # Drive to neutral for another cycle
            self.state.current_action = RobotAction.DRIVING
            self.state.position = RobotZone.NEUTRAL
            self.state.action_timer = self.rng.uniform(2.0, 3.0)
            self._cycle_phase = "auto_drive_to_neutral"
        else:
            # Auto routine complete
            self.state.current_action = RobotAction.IDLE
            self._cycle_phase = "idle"

    def _tick_auto_climb(self, match_state: MatchState) -> None:
        """Auto CLIMB_L1: drive to tower, climb, then descend."""
        if self._auto_climb_scored and not self._auto_descending:
            # Already done
            self.state.current_action = RobotAction.IDLE
            self._cycle_phase = "idle"
            return

        if not self._auto_climb_attempted:
            # Drive to tower
            self._auto_climb_attempted = True
            self.state.current_action = RobotAction.DRIVING
            self.state.position = RobotZone.TOWER
            self.state.action_timer = self.rng.uniform(1.5, 2.5)
            self._cycle_phase = "auto_climb_drive"
        else:
            self.state.current_action = RobotAction.IDLE
            self._cycle_phase = "idle"

    def _tick_auto_disrupt(self, match_state: MatchState, field_manager) -> None:
        """Auto DISRUPT_NEUTRAL: drive to neutral zone and push fuel."""
        if self._cycle_phase == "idle" or self._cycle_phase == "":
            # Drive to neutral zone
            self.state.current_action = RobotAction.DRIVING
            self.state.position = RobotZone.NEUTRAL
            self.state.action_timer = self.rng.uniform(1.5, 2.5)
            self._cycle_phase = "auto_disrupt_drive"
        elif self._cycle_phase == "auto_disrupting":
            # Continue disrupting -- push fuel each tick
            pushed = field_manager.try_intake(
                self.alliance, RobotZone.NEUTRAL, PUSH_FUEL_PER_TRIP
            )
            scattered = int(round(pushed * PUSH_SCATTER_RATE))
            net = max(0, pushed - scattered)
            if net > 0 and hasattr(field_manager, "add_fuel_to_alliance_zone"):
                field_manager.add_fuel_to_alliance_zone(self.alliance, net)
            if scattered > 0 and hasattr(field_manager, "return_fuel_to_field"):
                field_manager.return_fuel_to_field(scattered)
            self.state.current_action = RobotAction.PUSHING_FUEL
            self.state.action_timer = TICK_INTERVAL  # continue each tick
            self._cycle_phase = "auto_disrupting"

    def _start_auto_shot_burst(self) -> None:
        """Begin shooting all held fuel during auto (burst mode)."""
        if self.state.fuel_held <= 0:
            # No fuel to shoot
            self._auto_cycles_completed += 1
            self.state.current_action = RobotAction.IDLE
            self._cycle_phase = "idle"
            return

        # Align if needed
        align = _align_time_for_shooter(
            self._effective_shooter, self.runtime.turret_status
        )
        # Time to shoot all held fuel
        rate = max(self._shoot_rate, 0.1)
        shoot_time = self.state.fuel_held / rate
        self.state.current_action = RobotAction.SHOOTING
        self.state.action_timer = align + shoot_time
        self._cycle_phase = "auto_shoot"

    def _complete_auto_action(
        self, match_state: MatchState, field_manager
    ) -> None:
        """Handle completion of an auto action."""
        if self._cycle_phase == "auto_drive":
            # At hub, now shoot
            self._start_auto_shot_burst()

        elif self._cycle_phase == "auto_shoot":
            # All fuel shot -- match engine resolves accuracy per tick
            # Mark fuel as expended (match engine handles scoring)
            self._auto_fuel_scored += self.state.fuel_held
            self.state.fuel_held = 0
            self._auto_cycles_completed += 1
            self._auto_shooting_started = False  # Allow another cycle
            self.state.action_timer = 0.0
            self.state.current_action = RobotAction.IDLE
            self._cycle_phase = "idle"

        elif self._cycle_phase == "auto_drive_to_neutral":
            # At neutral, intake fuel
            fuel_needed = self.state.storage_capacity - self.state.fuel_held
            if fuel_needed > 0:
                got = field_manager.try_intake(
                    self.alliance, RobotZone.NEUTRAL, fuel_needed
                )
                self.state.fuel_held += got
            # Intake time based on intake_rate
            if self._intake_rate > 0 and self.state.fuel_held > 0:
                intake_time = self.state.fuel_held / self._intake_rate
            else:
                intake_time = 0.5
            self.state.current_action = RobotAction.INTAKING
            self.state.action_timer = intake_time
            self._cycle_phase = "auto_intake"

        elif self._cycle_phase == "auto_intake":
            # Done intaking, drive back to hub
            self.state.current_action = RobotAction.DRIVING
            self.state.position = RobotZone.HUB
            self.state.action_timer = self.rng.uniform(1.5, 2.5)
            self._cycle_phase = "auto_drive"

        elif self._cycle_phase == "auto_climb_drive":
            # At tower, start climbing
            self.state.current_action = RobotAction.CLIMBING
            self.state.is_climbing = True
            self.state.action_timer = AUTO_L1_CLIMB_TIME
            self._cycle_phase = "auto_climb"

        elif self._cycle_phase == "auto_climb":
            # Resolve climb attempt
            success_rate = self._arch.get("climb_success_L1", 0.0)
            if self.rng.random() < success_rate:
                self.state.climb_level = 1
                self._auto_climb_scored = True
            self.state.is_climbing = False
            # Now descend
            self._auto_descending = True
            self.state.current_action = RobotAction.DRIVING
            self.state.position = RobotZone.TOWER
            self.state.action_timer = AUTO_L1_DESCEND_TIME
            self._cycle_phase = "auto_descend"

        elif self._cycle_phase == "auto_descend":
            # Back on field
            self._auto_descending = False
            self.state.position = RobotZone.ALLIANCE
            self.state.current_action = RobotAction.IDLE
            self._cycle_phase = "idle"

        elif self._cycle_phase == "auto_disrupt_drive":
            # At neutral, start disrupting
            self.state.current_action = RobotAction.PUSHING_FUEL
            self.state.position = RobotZone.NEUTRAL
            self.state.is_pushing_fuel = True
            self.state.action_timer = TICK_INTERVAL
            self._cycle_phase = "auto_disrupting"

        elif self._cycle_phase == "auto_disrupting":
            # Continue disrupting
            self._tick_auto_disrupt(match_state, field_manager)

    def _tick_transition(self, match_state: MatchState, dt: float) -> None:
        """Handle the 10s transition between auto and teleop.

        Robots drive to position for the first shift.
        """
        self.state.current_action = RobotAction.DRIVING
        self.state.position = RobotZone.ALLIANCE
        self._cycle_phase = "transition"
        # Just idle through transition -- no scoring allowed

    def _tick_teleop_shift(
        self, match_state: MatchState, field_manager, dt: float
    ) -> None:
        """Handle a teleop shift (Shift 1-4).

        Behavior depends on shift_role (set by on_shift_change).
        """
        role = self.state.shift_role

        if role == ShiftRole.SCORER:
            self._tick_scoring(match_state, field_manager, dt)
        elif role == ShiftRole.STOCKPILER:
            self._tick_stockpiling(match_state, field_manager, dt)
        elif role == ShiftRole.DEFENDER:
            self._tick_defending(match_state, dt)
        elif role == ShiftRole.PUSHER:
            self._tick_pushing(match_state, field_manager, dt)

    def _tick_endgame(
        self, match_state: MatchState, field_manager, dt: float
    ) -> None:
        """Handle endgame period (30s, both hubs active).

        Score remaining fuel, then attempt climb based on climb_start_time.
        climb_start_time = 0 means never climb (score only).
        """
        # If climbing, count down
        if self.state.is_climbing:
            if self.state.action_timer > 0:
                self.state.action_timer -= dt
                if self.state.action_timer <= 0:
                    self._resolve_climb()
            return

        time_remaining = match_state.time_remaining
        climb_threshold = self.config.climb_start_time

        # Attempt climb when time_remaining <= climb_start_time
        should_climb = (
            not self._climb_attempted_teleop
            and self.config.climb_target > 0
            and climb_threshold > 0
            and time_remaining <= climb_threshold
        )

        if should_climb:
            self._start_climb()
        else:
            # Score fuel
            self._tick_scoring(match_state, field_manager, dt)

    # ------------------------------------------------------------------
    # Scoring cycle
    # ------------------------------------------------------------------

    def _start_scoring_cycle(self) -> None:
        """Begin a new scoring cycle: drive to fuel -> intake -> drive to hub -> align -> shoot."""
        # Generate cycle time from normal distribution
        cycle_time = max(
            self._cycle_time_mean * 0.5,
            self.rng.gauss(self._cycle_time_mean, self._cycle_time_stddev),
        )

        # Break cycle into phases (approximate proportions from spec)
        # Drive to fuel: ~25%, Intake: ~20%, Drive to hub: ~20%, Align: ~15%, Shoot: ~20%
        self._cycle_total_time = cycle_time
        self._start_drive_to_fuel(cycle_time)

    def _start_drive_to_fuel(self, total_cycle: float) -> None:
        """Start driving to a fuel source."""
        drive_time = total_cycle * 0.25
        self.state.current_action = RobotAction.DRIVING
        self.state.position = RobotZone.NEUTRAL
        self.state.action_timer = drive_time
        self._cycle_phase = "drive_to_fuel"

    def _tick_scoring(
        self, match_state: MatchState, field_manager, dt: float
    ) -> None:
        """Progress through the scoring cycle state machine."""
        # Count down current action timer
        if self.state.action_timer > 0:
            self.state.action_timer -= dt
            if self.state.action_timer > 0:
                return
            # Action completed -- transition
            self._on_scoring_action_complete(match_state, field_manager)
            return

        # No action running -- start a new cycle
        if self.state.current_action == RobotAction.IDLE:
            if self._effective_shooter == ShooterType.NONE:
                # Defense bot or broken shooter can't score
                self.state.current_action = RobotAction.IDLE
                return
            self._start_scoring_cycle()

    def _on_scoring_action_complete(
        self, match_state: MatchState, field_manager
    ) -> None:
        """Handle completion of a scoring cycle sub-phase."""
        phase = self._cycle_phase

        if phase == "drive_to_fuel":
            self._begin_intake(field_manager)

        elif phase == "intaking":
            self._finish_intake()

        elif phase == "drive_to_hub":
            self._begin_align()

        elif phase == "aligning":
            self._begin_shooting()

        elif phase == "shooting":
            self._finish_shooting()

        elif phase == "dumping":
            self._finish_dumping()

    def _begin_intake(self, field_manager) -> None:
        """Start intaking fuel from the field."""
        # Check intake status
        quality = self._get_effective_intake_quality()

        if quality == IntakeQuality.NO_GROUND_PICKUP:
            # Can't pickup from ground -- go to outpost for HP feed
            self.state.current_action = RobotAction.DRIVING
            self.state.position = RobotZone.OUTPOST
            self.state.action_timer = 2.0  # drive to outpost
            self._cycle_phase = "drive_to_outpost"
            return

        params = _INTAKE_QUALITY_PARAMS[quality.value]
        success_lo, success_hi = params["success_range"]

        # Determine how many fuel to attempt to pick up (fill to capacity)
        fuel_needed = self.state.storage_capacity - self.state.fuel_held
        if fuel_needed <= 0:
            # Already full, skip to drive to hub
            self._begin_drive_to_hub()
            return

        # Attempt intake -- call field_manager.try_intake for fuel availability
        fuel_picked = 0

        for _ in range(fuel_needed):
            # Bernoulli trial for pickup success
            success_rate = self.rng.uniform(success_lo, success_hi)

            # Apply degradation
            if self.runtime.intake_status == MechanismStatus.DEGRADED:
                success_rate = min(success_rate, DEGRADED_INTAKE_SUCCESS_RATE)

            if self.rng.random() < success_rate:
                # Try to get fuel from field
                got = field_manager.try_intake(
                    self.alliance, self.state.position, 1
                )
                if got > 0:
                    fuel_picked += got
                else:
                    break  # No fuel available

        self.state.fuel_held += fuel_picked

        # Intake time based on intake_rate (fuel/s) from config
        effective_rate = self._intake_rate
        if self.runtime.intake_status == MechanismStatus.DEGRADED:
            effective_rate *= DEGRADED_INTAKE_SPEED_MULT
        if effective_rate > 0 and fuel_picked > 0:
            total_intake_time = fuel_picked / effective_rate
        else:
            total_intake_time = TICK_INTERVAL

        self.state.current_action = RobotAction.INTAKING
        self.state.action_timer = max(total_intake_time, TICK_INTERVAL)
        self._cycle_phase = "intaking"

    def _finish_intake(self) -> None:
        """Intake phase complete, move to drive to hub."""
        self._begin_drive_to_hub()

    def _begin_drive_to_hub(self) -> None:
        """Drive from fuel source to hub."""
        # Time depends on cycle total -- ~20% of cycle
        drive_time = self._cycle_total_time * 0.20
        self.state.current_action = RobotAction.DRIVING
        self.state.position = RobotZone.HUB
        self.state.action_timer = drive_time
        self._cycle_phase = "drive_to_hub"

    def _begin_align(self) -> None:
        """Align to hub (if fixed shooter)."""
        align_time = _align_time_for_shooter(
            self._effective_shooter, self.runtime.turret_status
        )
        if align_time > 0:
            self.state.current_action = RobotAction.DRIVING  # rotating in place
            self.state.action_timer = align_time
            self._cycle_phase = "aligning"
        else:
            # No alignment needed (turret or dumper), go straight to shooting
            self._begin_shooting()

    def _begin_shooting(self) -> None:
        """Start shooting fuel at the hub."""
        if self.state.fuel_held <= 0:
            # Nothing to shoot, restart cycle
            self.state.current_action = RobotAction.IDLE
            self._cycle_phase = "idle"
            return

        # Check for jam -- use indexer jam rate (primary bottleneck)
        indexer_jam = INDEXER_JAM_RATES.get(self.config.indexer_type.value, 0.01)
        if self.rng.random() < indexer_jam:
            # Jam! Spend time clearing
            self.state.current_action = RobotAction.CLEARING_JAM
            self.state.action_timer = JAM_CLEAR_TIME
            self._cycle_phase = "shooting"  # will resume shooting after jam
            return

        # Calculate shoot time for all held fuel
        rate = self._shoot_rate
        if self.runtime.shooter_status == MechanismStatus.DEGRADED:
            rate *= 0.67  # lose ~33% throughput (one barrel jammed)

        if rate <= 0:
            self.state.current_action = RobotAction.IDLE
            self._cycle_phase = "idle"
            return

        shoot_time = self.state.fuel_held / rate
        self.state.current_action = RobotAction.SHOOTING
        self.state.action_timer = shoot_time
        self._cycle_phase = "shooting"

    def _finish_shooting(self) -> None:
        """Shooting complete -- fuel results are resolved by the match engine.

        The match engine reads current_action == SHOOTING and fuel_held to
        perform Bernoulli accuracy trials and update scores.  Here we just
        mark the fuel as expended and return to idle.
        """
        # The match engine is expected to have decremented fuel_held during
        # the SHOOTING action ticks.  If it hasn't (standalone mode), we
        # clear it here.
        self.state.fuel_held = 0
        self.state.current_action = RobotAction.IDLE
        self.state.position = RobotZone.HUB
        self._cycle_phase = "idle"

    def _finish_dumping(self) -> None:
        """Stockpile dump complete."""
        self.state.fuel_held = 0
        self.state.current_action = RobotAction.IDLE
        self.state.is_stockpiling = False
        self._stockpile_ready = False
        self._cycle_phase = "idle"

    # ------------------------------------------------------------------
    # Stockpile cycle
    # ------------------------------------------------------------------

    def _start_stockpile_cycle(self) -> None:
        """Begin stockpiling: drive to fuel source -> intake to capacity -> pre-position."""
        if self.state.fuel_held >= self.state.storage_capacity:
            # Already full, pre-position
            self._start_preposition()
            return
        # Drive to fuel source
        drive_time = self.rng.uniform(2.0, 3.5)
        self.state.current_action = RobotAction.DRIVING
        self.state.position = RobotZone.NEUTRAL
        self.state.action_timer = drive_time
        self._cycle_phase = "stockpile_drive"

    def _tick_stockpiling(
        self, match_state: MatchState, field_manager, dt: float
    ) -> None:
        """Progress through the stockpiling cycle."""
        if self.state.action_timer > 0:
            self.state.action_timer -= dt
            if self.state.action_timer > 0:
                return
            self._on_stockpile_action_complete(field_manager)
            return

        if self.state.current_action == RobotAction.IDLE:
            if self._stockpile_ready:
                # Waiting for shift change, do nothing
                return
            self._start_stockpile_cycle()

    def _on_stockpile_action_complete(self, field_manager) -> None:
        """Handle stockpile cycle sub-phase completion."""
        phase = self._cycle_phase

        if phase == "stockpile_drive":
            # At fuel source, start intaking
            self._stockpile_intake(field_manager)

        elif phase == "stockpile_intake":
            # Done intaking, pre-position if configured
            if self.config.preposition_before_shift:
                self._start_preposition()
            else:
                self.state.current_action = RobotAction.IDLE
                self.state.is_stockpiling = True
                self._stockpile_ready = True
                self._cycle_phase = "idle"

        elif phase == "pre_positioning":
            # In position, wait for shift change
            self.state.current_action = RobotAction.IDLE
            self.state.position = RobotZone.HUB
            self.state.is_stockpiling = True
            self._stockpile_ready = True
            self._cycle_phase = "idle"

    def _stockpile_intake(self, field_manager) -> None:
        """Intake fuel up to capacity for stockpiling."""
        quality = self._get_effective_intake_quality()
        fuel_needed = self.state.storage_capacity - self.state.fuel_held

        if quality == IntakeQuality.NO_GROUND_PICKUP or fuel_needed <= 0:
            # Go to outpost for HP feed or already full
            self.state.current_action = RobotAction.STOCKPILING
            self.state.action_timer = fuel_needed * 2.5  # HP feed rate
            self.state.position = RobotZone.OUTPOST
            # Attempt to get fuel from outpost
            got = field_manager.try_intake(self.alliance, RobotZone.OUTPOST, fuel_needed)
            self.state.fuel_held += got
            self._cycle_phase = "stockpile_intake"
            return

        params = _INTAKE_QUALITY_PARAMS[quality.value]
        success_lo, success_hi = params["success_range"]

        fuel_picked = 0
        for _ in range(fuel_needed):
            success_rate = self.rng.uniform(success_lo, success_hi)
            if self.runtime.intake_status == MechanismStatus.DEGRADED:
                success_rate = min(success_rate, DEGRADED_INTAKE_SUCCESS_RATE)

            if self.rng.random() < success_rate:
                got = field_manager.try_intake(self.alliance, self.state.position, 1)
                if got > 0:
                    self.state.fuel_held += got
                    fuel_picked += 1
                else:
                    break

        # Time based on intake_rate
        effective_rate = self._intake_rate
        if self.runtime.intake_status == MechanismStatus.DEGRADED:
            effective_rate *= DEGRADED_INTAKE_SPEED_MULT
        if effective_rate > 0 and fuel_picked > 0:
            total_time = fuel_picked / effective_rate
        else:
            total_time = TICK_INTERVAL

        self.state.current_action = RobotAction.STOCKPILING
        self.state.action_timer = max(total_time, TICK_INTERVAL)
        self._cycle_phase = "stockpile_intake"

    def _start_preposition(self) -> None:
        """Drive to pre-position near the hub."""
        if self.state.position == RobotZone.HUB:
            time_needed = 0.0
        elif self.state.position == RobotZone.OUTPOST:
            time_needed = PREPOSITION_TIME_FROM_OUTPOST
        elif self.state.position == RobotZone.OPPONENT_ZONE:
            time_needed = CROSSFIELD_DRIVE_TIME
        else:
            time_needed = PREPOSITION_TIME_FROM_NEUTRAL

        if time_needed <= 0:
            self.state.current_action = RobotAction.IDLE
            self.state.position = RobotZone.HUB
            self.state.is_stockpiling = True
            self._stockpile_ready = True
            self._cycle_phase = "idle"
            return

        self.state.current_action = RobotAction.PRE_POSITIONING
        self.state.action_timer = time_needed
        self._cycle_phase = "pre_positioning"

    # ------------------------------------------------------------------
    # Defense
    # ------------------------------------------------------------------

    def _start_defense(self) -> None:
        """Begin defense: drive to opponent zone and shadow target."""
        # Drive time depends on current position
        if self.state.position == RobotZone.OPPONENT_ZONE:
            drive_time = 0.0
        else:
            drive_time = CROSSFIELD_DRIVE_TIME

        if drive_time > 0:
            self.state.current_action = RobotAction.DRIVING
            self.state.action_timer = drive_time
            self._cycle_phase = "defense_drive"
        else:
            self.state.current_action = RobotAction.DEFENDING
            self.state.position = RobotZone.OPPONENT_ZONE
            self.state.is_defending = True
            self.state.action_timer = 0.0
            self._cycle_phase = "defending"

    def _tick_defending(self, match_state: MatchState, dt: float) -> None:
        """Continue defense behavior. Generate fouls if not already checked this shift."""
        if self.state.action_timer > 0:
            self.state.action_timer -= dt
            if self.state.action_timer <= 0:
                if self._cycle_phase == "defense_drive":
                    # Arrived at opponent zone
                    self.state.current_action = RobotAction.DEFENDING
                    self.state.position = RobotZone.OPPONENT_ZONE
                    self.state.is_defending = True
                    self._cycle_phase = "defending"
            return

        # Defending -- check for fouls once per shift
        if not self._defense_foul_checked_this_shift:
            self._defense_foul_checked_this_shift = True
            self._check_defense_fouls(match_state)

    def _check_defense_fouls(self, match_state: MatchState) -> None:
        """Bernoulli trials for foul and tech foul while defending.

        Rates depend on the zone where defense is played, with penalty
        escalation based on fouls already drawn this match.
        """
        zone = self.state.position
        fouls = self.runtime.fouls_drawn

        # Get escalation multiplier
        escalation_idx = min(fouls, len(PENALTY_ESCALATION_MULT) - 1)
        escalation = PENALTY_ESCALATION_MULT[escalation_idx]

        # Determine base rates by zone
        if zone == RobotZone.OPPONENT_ZONE:
            foul_rate = FOUL_RATE_OPPONENT_ALLIANCE
            tech_rate = TECH_FOUL_RATE_ALLIANCE
        elif zone == RobotZone.TOWER:
            foul_rate = FOUL_RATE_NEAR_TOWER
            tech_rate = TECH_FOUL_RATE_TOWER
        else:
            foul_rate = FOUL_RATE_NEUTRAL_ZONE
            tech_rate = TECH_FOUL_RATE_NEUTRAL

        # Apply escalation
        foul_rate = min(foul_rate * escalation, 1.0)
        tech_rate = min(tech_rate * escalation, 1.0)

        # Bernoulli trials
        if self.rng.random() < foul_rate:
            self.runtime.fouls_drawn += 1
            self.state.fouls_drawn_this_match += 1
            # Foul points awarded to opponent -- tracked in state for match engine

        if self.rng.random() < tech_rate:
            self.runtime.fouls_drawn += 1
            self.state.fouls_drawn_this_match += 1

    def get_pending_fouls(self) -> Dict[str, int]:
        """Return fouls accumulated this shift for the match engine to process.

        Returns dict with ``fouls`` and ``tech_fouls`` counts.
        The match engine should call this and reset after processing.
        """
        # This is a simplified approach -- the actual foul tracking is done
        # in _check_defense_fouls and the match engine reads fouls_drawn_this_match
        return {
            "fouls_drawn_total": self.runtime.fouls_drawn,
        }

    # ------------------------------------------------------------------
    # Fuel pushing
    # ------------------------------------------------------------------

    def _start_push_cycle(self) -> None:
        """Begin fuel pushing: drive into neutral zone fuel, push toward alliance zone."""
        self.state.current_action = RobotAction.PUSHING_FUEL
        self.state.position = RobotZone.NEUTRAL
        self.state.is_pushing_fuel = True
        self.state.action_timer = PUSH_TRIP_TIME
        self._cycle_phase = "pushing"

    def _tick_pushing(
        self, match_state: MatchState, field_manager, dt: float
    ) -> None:
        """Progress through fuel pushing cycle."""
        if self.state.action_timer > 0:
            self.state.action_timer -= dt
            if self.state.action_timer <= 0:
                self._complete_push_trip(field_manager)
            return

        if self.state.current_action == RobotAction.IDLE:
            self._start_push_cycle()

    def _complete_push_trip(self, field_manager) -> None:
        """Complete a push trip: move fuel from neutral zone to alliance zone."""
        # Attempt to push PUSH_FUEL_PER_TRIP fuel
        pushed = field_manager.try_intake(
            self.alliance, RobotZone.NEUTRAL, PUSH_FUEL_PER_TRIP
        )

        # Scatter loss
        scattered = int(round(pushed * PUSH_SCATTER_RATE))
        net_pushed = max(0, pushed - scattered)

        # Return scattered fuel to field (field_manager handles this)
        if scattered > 0 and hasattr(field_manager, "return_fuel_to_field"):
            field_manager.return_fuel_to_field(scattered)

        # Track pushed fuel
        self.runtime.fuel_pushed_to_zone += net_pushed
        self.state.fuel_being_pushed = 0

        # Return pushed fuel to alliance zone for teammates
        if net_pushed > 0 and hasattr(field_manager, "add_fuel_to_alliance_zone"):
            field_manager.add_fuel_to_alliance_zone(self.alliance, net_pushed)

        # Reset for next trip
        self.state.current_action = RobotAction.IDLE
        self.state.is_pushing_fuel = False
        self._cycle_phase = "idle"

    # ------------------------------------------------------------------
    # Climbing
    # ------------------------------------------------------------------

    def _start_climb(self) -> None:
        """Begin a climb attempt at the configured target level."""
        target = self.config.climb_target
        if target <= 0:
            return

        self._climb_attempted_teleop = True
        self.state.is_climbing = True
        self.state.current_action = RobotAction.CLIMBING
        self.state.position = RobotZone.TOWER

        # Climb time scales with level
        base_time = {1: 3.0, 2: 5.0, 3: 7.0}.get(target, 3.0)
        climb_time = self.rng.uniform(base_time * 0.8, base_time * 1.2)
        self.state.action_timer = climb_time
        self._cycle_phase = "climbing"

    def _resolve_climb(self) -> None:
        """Resolve the climb attempt with a Bernoulli trial."""
        target = self.config.climb_target
        success_key = f"climb_success_L{target}"
        success_rate = self._arch.get(success_key, 0.0)

        if self.rng.random() < success_rate:
            self.state.climb_level = target
        else:
            # Failed -- might still get a lower level
            # Try one level lower as a fallback
            if target >= 2:
                fallback_key = f"climb_success_L{target - 1}"
                fallback_rate = self._arch.get(fallback_key, 0.0)
                if self.rng.random() < fallback_rate:
                    self.state.climb_level = target - 1

        self.state.is_climbing = False
        self.state.current_action = RobotAction.IDLE
        self._cycle_phase = "idle"

    # ------------------------------------------------------------------
    # Intake quality model
    # ------------------------------------------------------------------

    def _get_effective_intake_quality(self) -> IntakeQuality:
        """Return the effective intake quality accounting for degradation."""
        if self.runtime.intake_status == MechanismStatus.BROKEN:
            return IntakeQuality.NO_GROUND_PICKUP
        if self.runtime.intake_status == MechanismStatus.DEGRADED:
            # Degraded intake downgrades quality by one tier
            quality = self._intake_quality
            if quality == IntakeQuality.TOUCH_AND_GO:
                return IntakeQuality.SLOW_PICKUP
            if quality == IntakeQuality.SLOW_PICKUP:
                return IntakeQuality.PUSH_AROUND
            return quality
        return self._intake_quality

    # ------------------------------------------------------------------
    # Mid-match failures
    # ------------------------------------------------------------------

    def _check_intake_failure(self) -> None:
        """Roll for intake failure at match start.

        Possible outcomes: total breakdown, partial degradation, or jam tendency.
        """
        break_rate = INTAKE_BREAK_RATE_SIMPLE
        degrade_rate = INTAKE_DEGRADE_RATE_SIMPLE

        # Total breakdown
        if self.rng.random() < break_rate:
            self.runtime.intake_status = MechanismStatus.BROKEN
            self.state.intake_status = MechanismStatus.BROKEN
            # Robot switches to defense or HP-fed
            if self.config.active_shift_role == ActiveShiftRole.SCORE:
                self.runtime.current_archetype_override = Archetype.DEFENSE
            return

        # Partial degradation
        if self.rng.random() < degrade_rate:
            self.runtime.intake_status = MechanismStatus.DEGRADED
            self.state.intake_status = MechanismStatus.DEGRADED
            return

    def _check_shooter_failure(self) -> None:
        """Roll for shooter failure at match start."""
        shooter = self.config.shooter_type

        if shooter == ShooterType.NONE:
            return

        if shooter in (ShooterType.DOUBLE_FIXED, ShooterType.TRIPLE_FIXED):
            failure_rate = MULTISHOT_FAILURE_RATE
        else:
            failure_rate = BASIC_FAILURE_RATE

        if self.rng.random() < failure_rate:
            self.runtime.shooter_status = MechanismStatus.DEGRADED
            self.state.shooter_status = MechanismStatus.DEGRADED
            # Degraded shooter: lose throughput
            if shooter == ShooterType.TRIPLE_FIXED:
                self._shoot_rate = SHOOT_RATE_DOUBLE  # one barrel down
            elif shooter == ShooterType.DOUBLE_FIXED:
                self._shoot_rate = SHOOT_RATE_SINGLE  # one barrel down

    def _check_turret_failure(self) -> None:
        """Roll for turret getting stuck (turret bots only)."""
        if self.config.shooter_type != ShooterType.SINGLE_TURRET:
            return

        if self.rng.random() < TURRET_FAILURE_RATE:
            self.runtime.turret_status = TurretStatus.STUCK
            # Turret stuck: become effectively a fixed shooter
            self._effective_shooter = ShooterType.SINGLE_FIXED
            # Accuracy penalty: -20%
            self._accuracy = max(0.0, self._accuracy - 0.20)

    # ------------------------------------------------------------------
    # Accuracy & shooting helpers
    # ------------------------------------------------------------------

    def get_accuracy(self) -> float:
        """Return the current effective accuracy for Bernoulli shot trials.

        The match engine calls this when resolving shots.
        """
        return self._accuracy

    def get_shoot_rate(self) -> float:
        """Return current shooting rate in fuel per second."""
        return self._shoot_rate

    def get_cycle_time_mean(self) -> float:
        """Return the mean cycle time (seconds), useful for the match engine."""
        return self._cycle_time_mean

    def is_turret(self) -> bool:
        """Return True if the robot's effective shooter is a turret."""
        return (
            self._effective_shooter == ShooterType.SINGLE_TURRET
            and self.runtime.turret_status == TurretStatus.NOMINAL
        )

    def is_fixed_shooter(self) -> bool:
        """Return True if the robot's effective shooter is a fixed type."""
        return self._effective_shooter in (
            ShooterType.SINGLE_FIXED,
            ShooterType.DOUBLE_FIXED,
            ShooterType.TRIPLE_FIXED,
        ) or (
            self._effective_shooter == ShooterType.SINGLE_TURRET
            and self.runtime.turret_status == TurretStatus.STUCK
        )

    def apply_defense_penalty(self, cycle_hit: float, accuracy_hit: float) -> None:
        """Apply defense disruption effects to this robot.

        Called by the match engine when another robot is defending this one.

        Parameters
        ----------
        cycle_hit : float
            Fractional increase to cycle time (e.g. 0.35 = +35%).
        accuracy_hit : float
            Absolute reduction in accuracy (e.g. 0.08 = -8%).
        """
        self._cycle_time_mean *= (1.0 + cycle_hit)
        self._accuracy = max(0.0, self._accuracy - accuracy_hit)

    def reset_defense_penalty(self) -> None:
        """Remove defense disruption effects (when defender leaves).

        Restores cycle time and accuracy to archetype defaults.
        """
        self._cycle_time_mean = self._arch.get("cycle_time_mean", 18.0)
        self._cycle_time_stddev = self._arch.get("cycle_time_stddev", 2.7)
        self._accuracy = self._arch.get("accuracy", 0.50)

        # Re-apply turret stuck penalty if applicable
        if self.runtime.turret_status == TurretStatus.STUCK:
            self._accuracy = max(0.0, self._accuracy - 0.20)

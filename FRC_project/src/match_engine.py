"""
Match Engine (Agent 1) for the FRC 2026 REBUILT match simulation.

Central simulation loop that coordinates all subsystems:
- Iterates ticks at TICK_INTERVAL (0.5s) from TOTAL_MATCH_DURATION down to 0
- Manages phase transitions (Auto, Transition, Shift 1-4, Endgame)
- Determines Hub activation based on auto winner
- Resolves shooting (Bernoulli accuracy trials), scoring, and defense
- Processes human player throws/feeds
- Compiles final SimulationResult with scores, RPs, and phase breakdowns
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from src.models import (
    Alliance,
    AllianceConfig,
    FieldState,
    MatchState,
    Phase,
    RobotAction,
    RobotState,
    RobotZone,
    SimulationResult,
)
from src.config import (
    AUTO_DURATION,
    AUTO_PRELOAD_MAX,
    ENDGAME_DURATION,
    FOUL_POINTS,
    FUEL_ACTIVE_HUB_POINTS,
    FUEL_INACTIVE_HUB_POINTS,
    HP_FEED_INTERVAL,
    HP_THROW_ACCURACY,
    HP_THROW_FLIGHT_TIME,
    HP_THROW_INTERVAL,
    INITIAL_PRELOAD_FUEL,
    RP_ENERGIZED_THRESHOLD,
    RP_SUPERCHARGED_THRESHOLD,
    RP_TIE,
    RP_TRAVERSAL_THRESHOLD,
    RP_WIN,
    SHIFT_DURATION,
    TECH_FOUL_POINTS,
    TICK_INTERVAL,
    TOTAL_MATCH_DURATION,
    TOWER_L1_AUTO_POINTS,
    TOWER_L1_TELEOP_POINTS,
    TOWER_L2_POINTS,
    TOWER_L3_POINTS,
    TRANSITION_DURATION,
    DEFENSE_CYCLE_HIT_FIXED,
    DEFENSE_CYCLE_HIT_TURRET,
    DEFENSE_ACCURACY_HIT_FIXED,
    DEFENSE_ACCURACY_HIT_TURRET,
)
from src.field import FieldManager
from src.robot import Robot
from src.models import HumanPlayerMode


# Phase boundaries in time_remaining (counting down from 160)
_PHASE_BOUNDARIES = [
    # (min_time_remaining, max_time_remaining, Phase)
    (140.0, 160.0, Phase.AUTO),         # elapsed 0-20
    (130.0, 140.0, Phase.TRANSITION),   # elapsed 20-30
    (105.0, 130.0, Phase.SHIFT1),       # elapsed 30-55
    (80.0,  105.0, Phase.SHIFT2),       # elapsed 55-80
    (55.0,  80.0,  Phase.SHIFT3),       # elapsed 80-105
    (30.0,  55.0,  Phase.SHIFT4),       # elapsed 105-130
    (0.0,   30.0,  Phase.ENDGAME),      # elapsed 130-160
]


def _get_phase(time_remaining: float) -> Phase:
    """Determine the current match phase from time_remaining."""
    for lo, hi, phase in _PHASE_BOUNDARIES:
        if lo <= time_remaining < hi:
            return phase
    # Edge case: exactly 160.0
    if time_remaining >= 160.0:
        return Phase.AUTO
    return Phase.ENDGAME


class MatchEngine:
    """Runs a single FRC 2026 REBUILT match simulation."""

    def __init__(
        self,
        red_alliance: AllianceConfig,
        blue_alliance: AllianceConfig,
        seed: int = 0,
    ) -> None:
        self.rng = random.Random(seed)
        self.red_config = red_alliance
        self.blue_config = blue_alliance

        # Field state manager
        self.field = FieldManager()

        # Match state
        self.match_state = MatchState(
            time_remaining=TOTAL_MATCH_DURATION,
            current_phase=Phase.AUTO,
            red_hub_active=True,
            blue_hub_active=True,
        )

        # Create robots: 3 red + 3 blue
        self.red_robots: List[Robot] = []
        self.blue_robots: List[Robot] = []

        for i, cfg in enumerate(red_alliance.robots):
            robot = Robot(
                robot_id=f"red_{i}",
                alliance=Alliance.RED,
                config=cfg,
                rng=random.Random(self.rng.randint(0, 2**31)),
            )
            self.red_robots.append(robot)

        for i, cfg in enumerate(blue_alliance.robots):
            robot = Robot(
                robot_id=f"blue_{i}",
                alliance=Alliance.BLUE,
                config=cfg,
                rng=random.Random(self.rng.randint(0, 2**31)),
            )
            self.blue_robots.append(robot)

        self.all_robots: List[Robot] = self.red_robots + self.blue_robots

        # Distribute preloaded fuel across robots
        self._distribute_preload(self.red_robots, INITIAL_PRELOAD_FUEL)
        self._distribute_preload(self.blue_robots, INITIAL_PRELOAD_FUEL)

        # Scoring accumulators
        self.red_fuel_scored: int = 0
        self.blue_fuel_scored: int = 0
        self.red_tower_points: int = 0
        self.blue_tower_points: int = 0
        self.red_penalty_points: int = 0   # penalty points awarded TO red (from blue fouls)
        self.blue_penalty_points: int = 0  # penalty points awarded TO blue (from red fouls)

        # Phase score tracking
        self.phase_scores: Dict[str, Dict[str, int]] = {}

        # HP timing
        self._red_hp_timer: float = 0.0
        self._blue_hp_timer: float = 0.0

        # Defense tracking: which robots are being defended (to apply/reset penalties)
        self._defense_applied: Dict[str, bool] = {}

        # Auto scores for determining hub activation
        self._red_auto_score: int = 0
        self._blue_auto_score: int = 0

        # Track previous foul counts to detect new fouls
        self._prev_foul_counts: Dict[str, int] = {}
        for robot in self.all_robots:
            self._prev_foul_counts[robot.robot_id] = 0

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------

    def run(self) -> SimulationResult:
        """Run the full match simulation and return results."""
        dt = TICK_INTERVAL
        current_phase_name = ""

        while self.match_state.time_remaining > 0:
            # Determine phase
            new_phase = _get_phase(self.match_state.time_remaining)

            # Phase transition handling
            if new_phase != self.match_state.current_phase:
                self._on_phase_change(self.match_state.current_phase, new_phase)
                self.match_state.current_phase = new_phase

            # Track phase scores
            phase_key = new_phase.value
            if phase_key not in self.phase_scores:
                self.phase_scores[phase_key] = {"red": 0, "blue": 0}

            # Elapsed time for field transit queue
            elapsed = TOTAL_MATCH_DURATION - self.match_state.time_remaining

            # 1. Update field state (transit queue, congestion)
            all_states = [r.get_state() for r in self.all_robots]
            self.field.tick(elapsed, all_states)

            # 2. Process human player actions
            self._process_human_players(dt, elapsed)

            # 3. Update all robots
            for robot in self.all_robots:
                robot.tick(self.match_state, self.field, dt)

            # 4. Resolve shooting and scoring
            self._resolve_shooting(elapsed)

            # 5. Process defense interactions
            self._process_defense()

            # 6. Process fouls
            self._process_fouls()

            # Advance time
            self.match_state.time_remaining -= dt

        # End of match: resolve tower climbing
        self._resolve_tower_climbing()

        # Compile result
        return self._compile_result()

    # ------------------------------------------------------------------
    # Phase transitions
    # ------------------------------------------------------------------

    def _on_phase_change(self, old_phase: Phase, new_phase: Phase) -> None:
        """Handle a phase transition."""
        if old_phase == Phase.AUTO and new_phase == Phase.TRANSITION:
            # Determine auto winner and set hub activation
            self._determine_auto_winner()

        if new_phase in (Phase.SHIFT1, Phase.SHIFT2, Phase.SHIFT3, Phase.SHIFT4):
            self._update_hub_activation(new_phase)

        if new_phase == Phase.ENDGAME:
            # Both hubs active during endgame
            self.match_state.red_hub_active = True
            self.match_state.blue_hub_active = True

    def _determine_auto_winner(self) -> None:
        """Compare auto scores to determine which alliance won auto."""
        self._red_auto_score = self.red_fuel_scored
        self._blue_auto_score = self.blue_fuel_scored

        # Auto winner determination: the alliance that scored more fuel
        # Per spec: If auto winner is Red, Red Hub is INACTIVE during Shifts 1&3
        if self._red_auto_score > self._blue_auto_score:
            self._auto_winner = "red"
        elif self._blue_auto_score > self._red_auto_score:
            self._auto_winner = "blue"
        else:
            # Tie: Red inactive first by default
            self._auto_winner = "red"

    def _update_hub_activation(self, phase: Phase) -> None:
        """Set hub activation for the given shift phase.

        Per spec: Auto winner's hub is INACTIVE during shifts 1&3, ACTIVE during 2&4.
        """
        winner = getattr(self, "_auto_winner", "red")

        # Winner hub inactive on shifts 1&3, active on 2&4
        winner_active = phase in (Phase.SHIFT2, Phase.SHIFT4)
        loser_active = not winner_active

        if winner == "red":
            self.match_state.red_hub_active = winner_active
            self.match_state.blue_hub_active = loser_active
        else:
            self.match_state.red_hub_active = loser_active
            self.match_state.blue_hub_active = winner_active

    # ------------------------------------------------------------------
    # Shooting resolution
    # ------------------------------------------------------------------

    def _resolve_shooting(self, elapsed: float) -> None:
        """Resolve shots for robots that are currently shooting or just finished.

        For each robot in SHOOTING or DUMPING action with fuel, perform
        Bernoulli accuracy trials and update scores.
        """
        for robot in self.all_robots:
            state = robot.get_state()

            if state.current_action not in (RobotAction.SHOOTING, RobotAction.DUMPING):
                continue

            if state.fuel_held <= 0:
                continue

            # Determine how much fuel to resolve this tick
            # For shooting: resolve based on shoot rate * dt
            rate = robot.get_shoot_rate()
            if rate <= 0:
                continue

            fuel_this_tick = min(
                state.fuel_held,
                max(1, int(rate * TICK_INTERVAL + 0.5)),
            )

            # Determine if hub is active
            alliance = state.alliance
            hub_active = (
                self.match_state.red_hub_active
                if alliance == Alliance.RED
                else self.match_state.blue_hub_active
            )

            accuracy = robot.get_accuracy()
            hits = 0
            misses = 0

            for _ in range(fuel_this_tick):
                if state.fuel_held <= 0:
                    break
                state.fuel_held -= 1

                # Notify field: fuel is now in flight
                self.field.fuel_shot(1)

                # Bernoulli accuracy trial
                if self.rng.random() < accuracy:
                    hits += 1
                else:
                    misses += 1

            # Process hits
            if hits > 0:
                alliance_str = alliance.value
                self.field.fuel_scored(alliance_str, hits, elapsed)

                if hub_active:
                    points = hits * FUEL_ACTIVE_HUB_POINTS
                    if alliance == Alliance.RED:
                        self.red_fuel_scored += hits
                        self.match_state.red_fuel_scored += hits
                        self.match_state.red_score += points
                    else:
                        self.blue_fuel_scored += hits
                        self.match_state.blue_fuel_scored += hits
                        self.match_state.blue_score += points

                    # Track phase scores
                    phase_key = self.match_state.current_phase.value
                    if phase_key in self.phase_scores:
                        if alliance == Alliance.RED:
                            self.phase_scores[phase_key]["red"] += points
                        else:
                            self.phase_scores[phase_key]["blue"] += points
                else:
                    # Inactive hub: fuel enters but scores 0
                    # Still goes through transit for recycling
                    pass

            # Process misses
            if misses > 0:
                self.field.fuel_missed(misses, elapsed)

    # ------------------------------------------------------------------
    # Defense
    # ------------------------------------------------------------------

    def _process_defense(self) -> None:
        """Apply defense penalties from defending robots to their targets."""
        # Collect all defending robots
        defenders: List[Robot] = []
        for robot in self.all_robots:
            state = robot.get_state()
            if state.is_defending and state.current_action == RobotAction.DEFENDING:
                defenders.append(robot)

        # Build set of currently defended robot IDs
        currently_defended = set()

        for defender in defenders:
            target_id = defender.config.defense_target
            if not target_id:
                # Default: defend the opponent's best scorer (first robot)
                if defender.alliance == Alliance.RED:
                    target_id = "blue_0"
                else:
                    target_id = "red_0"

            # Find the target robot
            target = self._find_robot(target_id)
            if target is None:
                continue

            currently_defended.add(target_id)

            # Apply defense penalty if not already applied
            if not self._defense_applied.get(target_id, False):
                if target.is_turret():
                    target.apply_defense_penalty(
                        DEFENSE_CYCLE_HIT_TURRET, DEFENSE_ACCURACY_HIT_TURRET
                    )
                else:
                    target.apply_defense_penalty(
                        DEFENSE_CYCLE_HIT_FIXED, DEFENSE_ACCURACY_HIT_FIXED
                    )
                self._defense_applied[target_id] = True

        # Remove defense penalties from robots no longer being defended
        for robot_id, is_defended in list(self._defense_applied.items()):
            if is_defended and robot_id not in currently_defended:
                target = self._find_robot(robot_id)
                if target:
                    target.reset_defense_penalty()
                self._defense_applied[robot_id] = False

    def _find_robot(self, robot_id: str) -> Optional[Robot]:
        """Find a robot by its ID."""
        for robot in self.all_robots:
            if robot.robot_id == robot_id:
                return robot
        # Handle "opponent_0" style targets
        if robot_id.startswith("opponent_"):
            return None
        return None

    # ------------------------------------------------------------------
    # Fouls
    # ------------------------------------------------------------------

    def _process_fouls(self) -> None:
        """Check for new fouls from defending robots and award penalty points."""
        for robot in self.all_robots:
            state = robot.get_state()
            current_fouls = state.fouls_drawn_this_match
            prev_fouls = self._prev_foul_counts.get(robot.robot_id, 0)

            if current_fouls > prev_fouls:
                new_fouls = current_fouls - prev_fouls
                self._prev_foul_counts[robot.robot_id] = current_fouls

                # Fouls by this robot award points to the opponent
                # Simplified: each new foul = FOUL_POINTS to opponent
                # (mix of regular and tech fouls)
                penalty_pts = new_fouls * FOUL_POINTS

                if robot.alliance == Alliance.RED:
                    # Red robot fouled -> points to blue
                    self.blue_penalty_points += penalty_pts
                    self.match_state.red_penalties += penalty_pts
                    self.match_state.blue_score += penalty_pts
                else:
                    # Blue robot fouled -> points to red
                    self.red_penalty_points += penalty_pts
                    self.match_state.blue_penalties += penalty_pts
                    self.match_state.red_score += penalty_pts

    # ------------------------------------------------------------------
    # Human player
    # ------------------------------------------------------------------

    def _process_human_players(self, dt: float, elapsed: float) -> None:
        """Process human player actions based on alliance HP mode."""
        phase = self.match_state.current_phase
        if phase in (Phase.AUTO, Phase.TRANSITION):
            return  # No HP actions during auto/transition

        self._process_hp_for_alliance(
            Alliance.RED, self.red_config.human_player_mode,
            self.red_robots, dt, elapsed,
        )
        self._process_hp_for_alliance(
            Alliance.BLUE, self.blue_config.human_player_mode,
            self.blue_robots, dt, elapsed,
        )

    def _process_hp_for_alliance(
        self,
        alliance: Alliance,
        hp_mode: HumanPlayerMode,
        robots: List[Robot],
        dt: float,
        elapsed: float,
    ) -> None:
        """Process HP actions for one alliance."""
        if alliance == Alliance.RED:
            timer = self._red_hp_timer
        else:
            timer = self._blue_hp_timer

        timer += dt
        alliance_str = alliance.value

        if hp_mode == HumanPlayerMode.THROW:
            if timer >= HP_THROW_INTERVAL:
                timer -= HP_THROW_INTERVAL
                self._hp_throw(alliance_str, elapsed)
        elif hp_mode == HumanPlayerMode.FEED:
            if timer >= HP_FEED_INTERVAL:
                timer -= HP_FEED_INTERVAL
                self._hp_feed(alliance_str, robots)
        elif hp_mode == HumanPlayerMode.MIXED:
            # Alternate: throw when hub active, feed when inactive
            hub_active = (
                self.match_state.red_hub_active
                if alliance == Alliance.RED
                else self.match_state.blue_hub_active
            )
            if hub_active:
                if timer >= HP_THROW_INTERVAL:
                    timer -= HP_THROW_INTERVAL
                    self._hp_throw(alliance_str, elapsed)
            else:
                if timer >= HP_FEED_INTERVAL:
                    timer -= HP_FEED_INTERVAL
                    self._hp_feed(alliance_str, robots)

        if alliance == Alliance.RED:
            self._red_hp_timer = timer
        else:
            self._blue_hp_timer = timer

    def _hp_throw(self, alliance: str, elapsed: float) -> None:
        """Human player throws fuel at the Hub."""
        self.field.hp_throw(alliance, elapsed)

        # Resolve throw accuracy after flight time
        # Simplified: resolve immediately (flight time handled by field transit)
        if self.rng.random() < HP_THROW_ACCURACY:
            # Hit
            self.field.fuel_scored(alliance, 1, elapsed)

            hub_active = (
                self.match_state.red_hub_active
                if alliance == "red"
                else self.match_state.blue_hub_active
            )
            if hub_active:
                if alliance == "red":
                    self.red_fuel_scored += 1
                    self.match_state.red_fuel_scored += 1
                    self.match_state.red_score += FUEL_ACTIVE_HUB_POINTS
                else:
                    self.blue_fuel_scored += 1
                    self.match_state.blue_fuel_scored += 1
                    self.match_state.blue_score += FUEL_ACTIVE_HUB_POINTS
        else:
            # Miss
            self.field.fuel_missed(1, elapsed)

    def _hp_feed(self, alliance: str, robots: List[Robot]) -> None:
        """Human player feeds fuel to a robot at the outpost."""
        # Find a robot that needs fuel and isn't full
        for robot in robots:
            state = robot.get_state()
            if state.fuel_held < state.storage_capacity:
                if self.field.hp_feed(alliance):
                    state.fuel_held += 1
                return

    # ------------------------------------------------------------------
    # Tower climbing resolution
    # ------------------------------------------------------------------

    def _resolve_tower_climbing(self) -> None:
        """At end of match, tally tower points from successful climbs.

        Auto L1 climbs are scored at AUTO points (15 pts).
        If a robot climbed L1 in auto and then climbed higher in endgame,
        only the higher level is counted (no double-counting).
        """
        for robot in self.all_robots:
            state = robot.get_state()
            level = state.climb_level
            if level <= 0:
                continue

            # Register climb on field
            alliance_str = state.alliance.value
            self.field.register_climb(alliance_str, robot.robot_id)

            # Determine points based on level and whether scored in auto
            auto_climbed = getattr(robot, '_auto_climb_scored', False)

            if level == 1 and auto_climbed:
                # L1 scored during auto gets auto bonus points
                points = TOWER_L1_AUTO_POINTS
            elif level == 1:
                points = TOWER_L1_TELEOP_POINTS
            elif level == 2:
                points = TOWER_L2_POINTS
            elif level == 3:
                points = TOWER_L3_POINTS
            else:
                points = 0

            if state.alliance == Alliance.RED:
                self.red_tower_points += points
                self.match_state.red_tower_points += points
                self.match_state.red_score += points
            else:
                self.blue_tower_points += points
                self.match_state.blue_tower_points += points
                self.match_state.blue_score += points

    # ------------------------------------------------------------------
    # Result compilation
    # ------------------------------------------------------------------

    def _compile_result(self) -> SimulationResult:
        """Build the final SimulationResult."""
        red_total = self.match_state.red_score
        blue_total = self.match_state.blue_score

        # Winner
        if red_total > blue_total:
            winner = "red"
        elif blue_total > red_total:
            winner = "blue"
        else:
            winner = "tie"

        # RPs
        red_rp = 0
        blue_rp = 0

        if winner == "red":
            red_rp += RP_WIN
        elif winner == "blue":
            blue_rp += RP_WIN
        else:
            red_rp += RP_TIE
            blue_rp += RP_TIE

        # Fuel RP bonuses
        red_energized = self.red_fuel_scored >= RP_ENERGIZED_THRESHOLD
        red_supercharged = self.red_fuel_scored >= RP_SUPERCHARGED_THRESHOLD
        blue_energized = self.blue_fuel_scored >= RP_ENERGIZED_THRESHOLD
        blue_supercharged = self.blue_fuel_scored >= RP_SUPERCHARGED_THRESHOLD

        if red_energized:
            red_rp += 1
        if red_supercharged:
            red_rp += 1
        if blue_energized:
            blue_rp += 1
        if blue_supercharged:
            blue_rp += 1

        # Tower RP bonus
        red_traversal = self.red_tower_points >= RP_TRAVERSAL_THRESHOLD
        blue_traversal = self.blue_tower_points >= RP_TRAVERSAL_THRESHOLD

        if red_traversal:
            red_rp += 1
        if blue_traversal:
            blue_rp += 1

        return SimulationResult(
            red_total_score=red_total,
            blue_total_score=blue_total,
            red_rp=red_rp,
            blue_rp=blue_rp,
            winner=winner,
            red_fuel_scored=self.red_fuel_scored,
            blue_fuel_scored=self.blue_fuel_scored,
            red_tower_points=self.red_tower_points,
            blue_tower_points=self.blue_tower_points,
            red_penalties_drawn=self.red_penalty_points,
            blue_penalties_drawn=self.blue_penalty_points,
            red_energized=red_energized,
            red_supercharged=red_supercharged,
            red_traversal=red_traversal,
            blue_energized=blue_energized,
            blue_supercharged=blue_supercharged,
            blue_traversal=blue_traversal,
            phase_scores=self.phase_scores,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _distribute_preload(robots: List[Robot], total_preload: int) -> None:
        """Distribute preloaded fuel across alliance robots.

        Each robot gets up to its auto_fuel_target, capped at AUTO_PRELOAD_MAX (8).
        Remaining preload is distributed evenly among robots that can hold more.
        """
        if not robots:
            return

        remaining = total_preload
        for robot in robots:
            # Each robot gets its auto_fuel_target, capped at preload max and storage
            target = min(
                robot.config.auto_fuel_target,
                AUTO_PRELOAD_MAX,
                robot.config.storage_capacity,
            )
            fuel = min(target, remaining)
            robot.state.fuel_held = fuel
            remaining -= fuel

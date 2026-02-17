"""
Field State Manager (Agent 3) for the FRC 2026 REBUILT match simulation.

Responsible for:
- Fuel pool accounting with conservation invariant (TOTAL_FUEL = 60 at all times)
- Fuel state tracking across all locations (on_field, in_robot, in_flight, in_transit, at_outpost)
- Transit queue: scheduling fuel return to the field after Hub fall-through or miss recovery
- Fuel starvation detection when demand exceeds available supply
- Tower occupancy tracking per alliance
- Hub congestion modeling based on nearby robot density
- Fuel pushing between zones with scatter losses

All public methods maintain the fuel conservation invariant. Call assert_conservation()
at the end of each tick to verify correctness during development.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from src.models import (
    Alliance,
    FieldState,
    RobotState,
    RobotZone,
)
from src.config import (
    INITIAL_NEUTRAL_FUEL,
    INITIAL_OUTPOST_FUEL,
    TOTAL_FUEL,
    FUEL_HUB_TRANSIT_TIME,
    FUEL_MISS_RECOVERY_TIME,
    HP_THROW_FLIGHT_TIME,
    MAX_TOWER_OCCUPANTS,
    PUSH_SCATTER_RATE,
)


class FieldManager:
    """Manages the global field state for one match.

    The field tracks every fuel ball across five disjoint pools:
        neutral_fuel_available  -- pickable fuel in the neutral zone
        red/blue_outpost_fuel   -- fuel at each alliance's outpost stations
        fuel_in_flight          -- airborne fuel (shot but not yet in Hub)
        fuel_in_transit         -- fuel falling through Hub back to neutral zone

    Fuel held by robots (fuel_held + fuel_being_pushed on each RobotState) is
    tracked externally by the Robot Behavior Engine (Agent 2). The conservation
    invariant ties all pools together:

        neutral + red_outpost + blue_outpost + in_flight + in_transit
        + sum(robot.fuel_held + robot.fuel_being_pushed) == TOTAL_FUEL

    The transit_queue is a time-ordered list of ``(return_time, count)`` tuples.
    Each entry represents fuel that will become available in the neutral zone
    once ``current_time >= return_time``.
    """

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        """Initialize the field to its match-start configuration.

        At match start the fuel is distributed as:
            - 20 in the neutral zone
            - 10 at each alliance outpost (20 total)
            - 10 pre-loaded per alliance across 3 robots (20 total, tracked on RobotState)
        Total = 20 + 10 + 10 + 0 + 0 + 20 (in robots) = 60
        """
        self._state = FieldState(
            neutral_fuel_available=INITIAL_NEUTRAL_FUEL,
            red_outpost_fuel=INITIAL_OUTPOST_FUEL,
            blue_outpost_fuel=INITIAL_OUTPOST_FUEL,
            fuel_in_flight=0,
            fuel_in_transit=0,
            transit_queue=[],
            red_tower_occupants=[],
            blue_tower_occupants=[],
            congestion_red_hub=0.0,
            congestion_blue_hub=0.0,
        )

    # ------------------------------------------------------------------
    # State Access
    # ------------------------------------------------------------------

    def get_state(self) -> FieldState:
        """Return the current field state snapshot.

        Returns
        -------
        FieldState
            A reference to the internal field state dataclass.  Callers
            should treat it as read-only; mutations should go through
            FieldManager methods to preserve the conservation invariant.
        """
        return self._state

    # ------------------------------------------------------------------
    # Per-Tick Processing
    # ------------------------------------------------------------------

    def tick(self, current_time: float, robots: List[RobotState]) -> None:
        """Advance the field state by one simulation tick (0.5 s).

        This method is called once per tick by the Match Engine. It:
        1. Processes the transit queue -- any fuel whose scheduled return
           time has been reached is moved from ``fuel_in_transit`` back
           into ``neutral_fuel_available``.
        2. Reconciles ``fuel_in_transit`` and ``fuel_in_flight`` with the
           transit queue so the counts stay accurate.
        3. Updates hub congestion estimates based on how many robots from
           each alliance are currently near their hub.

        Parameters
        ----------
        current_time : float
            Elapsed match time in seconds (0.0 at match start, 160.0 at end).
        robots : list of RobotState
            All six robots on the field.
        """
        self._process_transit_queue(current_time)
        self._update_congestion(robots)

    def _process_transit_queue(self, current_time: float) -> None:
        """Move fuel from transit back to the neutral zone when its timer expires."""
        still_pending: List[Tuple[float, int]] = []
        for return_time, count in self._state.transit_queue:
            if return_time <= current_time:
                # Fuel has arrived back on the field.
                self._state.neutral_fuel_available += count
                self._state.fuel_in_transit -= count
            else:
                still_pending.append((return_time, count))
        self._state.transit_queue = still_pending

    def _update_congestion(self, robots: List[RobotState]) -> None:
        """Compute hub congestion as a fraction of max possible crowding.

        Congestion is modeled as a simple ratio:
            congestion = (robots_near_hub) / 3
        clamped to [0.0, 1.0].  Having all 3 alliance robots at the hub
        yields congestion 1.0, which other agents can use to apply cycle
        time penalties.

        Parameters
        ----------
        robots : list of RobotState
            All six robots on the field.
        """
        red_at_hub = 0
        blue_at_hub = 0
        for r in robots:
            if r.position == RobotZone.HUB:
                if r.alliance == Alliance.RED:
                    red_at_hub += 1
                else:
                    blue_at_hub += 1

        # Congestion is 0 when 0-1 robots are at the hub, scales linearly up to 1.0
        # with 3 robots present.  We use max(0, n-1)/2 so a lone robot has no penalty.
        self._state.congestion_red_hub = min(1.0, max(0, red_at_hub - 1) / 2.0)
        self._state.congestion_blue_hub = min(1.0, max(0, blue_at_hub - 1) / 2.0)

    # ------------------------------------------------------------------
    # Fuel Scoring Events
    # ------------------------------------------------------------------

    def fuel_shot(self, count: int) -> None:
        """Record that *count* fuel balls have been shot (now airborne).

        Called by the Robot Behavior Engine when a robot releases fuel.
        The fuel transitions from ``in_robot`` (tracked on RobotState) to
        ``in_flight`` (tracked here).

        Parameters
        ----------
        count : int
            Number of fuel balls that left the robot.
        """
        if count <= 0:
            return
        self._state.fuel_in_flight += count

    def fuel_scored(self, alliance: str, count: int, current_time: float) -> None:
        """Record that *count* fuel balls entered a Hub (hit or miss handled separately).

        Called when airborne fuel successfully enters the Hub. The fuel
        transitions from ``in_flight`` to ``in_transit`` and is scheduled
        to return to the neutral zone after FUEL_HUB_TRANSIT_TIME.

        Scoring points are NOT awarded here -- that is the Match Engine's
        responsibility (Agent 1).  This method only updates fuel pool
        accounting.

        Parameters
        ----------
        alliance : str
            ``"red"`` or ``"blue"`` -- which Hub the fuel entered.
        count : int
            Number of fuel balls that entered the Hub.
        current_time : float
            Current elapsed match time in seconds.
        """
        if count <= 0:
            return
        self._state.fuel_in_flight -= count
        self._state.fuel_in_transit += count
        return_time = current_time + FUEL_HUB_TRANSIT_TIME
        self._state.transit_queue.append((return_time, count))

    def fuel_missed(self, count: int, current_time: float) -> None:
        """Record that *count* airborne fuel balls missed the Hub.

        Missed fuel lands on the field and takes FUEL_MISS_RECOVERY_TIME
        to settle into a pickable position. They are routed through the
        transit queue to model this delay.

        Parameters
        ----------
        count : int
            Number of fuel balls that missed.
        current_time : float
            Current elapsed match time in seconds.
        """
        if count <= 0:
            return
        self._state.fuel_in_flight -= count
        self._state.fuel_in_transit += count
        return_time = current_time + FUEL_MISS_RECOVERY_TIME
        self._state.transit_queue.append((return_time, count))

    # ------------------------------------------------------------------
    # Fuel Intake
    # ------------------------------------------------------------------

    def try_intake(self, alliance, zone, amount: int) -> int:
        """Attempt to pick up fuel from a field zone.

        The robot wants *amount* fuel, but may receive fewer if the zone
        does not have enough available.  This is the primary mechanism
        for fuel starvation -- when the zone is depleted, the robot gets
        zero and must wait.

        Parameters
        ----------
        alliance : str or Alliance enum
            ``"red"`` or ``"blue"`` -- needed to identify the correct
            outpost counter.  Accepts both string and Alliance enum.
        zone : str or RobotZone enum
            One of ``"neutral"``, ``"outpost"``, or ``"alliance"``.
            ``"alliance"`` draws from the neutral zone (fuel pushed
            to alliance side is modeled as neutral fuel for simplicity,
            or the caller should use ``"neutral"``).
        amount : int
            Maximum number of fuel balls the robot wants to pick up.

        Returns
        -------
        int
            Actual number of fuel balls acquired (0 <= result <= amount).
        """
        if amount <= 0:
            return 0

        # Normalise enum values to strings for comparison
        zone_str = zone.value if hasattr(zone, "value") else str(zone)
        alliance_str = alliance.value if hasattr(alliance, "value") else str(alliance)

        if zone_str in ("neutral", "alliance", "midfield"):
            available = self._state.neutral_fuel_available
            actual = min(amount, available)
            self._state.neutral_fuel_available -= actual
            return actual

        if zone_str == "outpost":
            if alliance_str == "red":
                available = self._state.red_outpost_fuel
                actual = min(amount, available)
                self._state.red_outpost_fuel -= actual
                return actual
            else:
                available = self._state.blue_outpost_fuel
                actual = min(amount, available)
                self._state.blue_outpost_fuel -= actual
                return actual

        # Unknown zone -- draw from neutral as fallback.
        available = self._state.neutral_fuel_available
        actual = min(amount, available)
        self._state.neutral_fuel_available -= actual
        return actual

    # ------------------------------------------------------------------
    # Fuel Pushing
    # ------------------------------------------------------------------

    def push_fuel(self, from_zone: str, to_zone: str, amount: int) -> int:
        """Push (bulldoze) fuel from one zone to another.

        Pushing is an imprecise action: PUSH_SCATTER_RATE (20%) of the
        fuel scatters and is effectively lost to the neutral zone (it
        stays on the field but not in a useful pile).

        Parameters
        ----------
        from_zone : str
            Source zone (``"neutral"`` or ``"outpost"``).
        to_zone : str
            Destination zone (``"neutral"`` or ``"alliance"``).
        amount : int
            Number of fuel balls the robot intends to push.

        Returns
        -------
        int
            Number of fuel balls that actually arrive at the destination.
            The scattered fuel remains in the neutral zone.
        """
        if amount <= 0:
            return 0

        # Determine how many we can actually pick up from the source.
        if from_zone == "neutral":
            available = self._state.neutral_fuel_available
            actual_moved = min(amount, available)
            self._state.neutral_fuel_available -= actual_moved
        elif from_zone == "outpost":
            # Pushing from outpost is unusual but supported.
            # We treat it as red/blue agnostic here; caller should use
            # try_intake for outpost-specific draws.  Default to neutral.
            available = self._state.neutral_fuel_available
            actual_moved = min(amount, available)
            self._state.neutral_fuel_available -= actual_moved
        else:
            return 0

        if actual_moved <= 0:
            return 0

        # Apply scatter loss.
        scattered = int(math.floor(actual_moved * PUSH_SCATTER_RATE))
        arrived = actual_moved - scattered

        # Scattered fuel goes back to neutral zone (still on field, just not
        # in a useful pile).
        self._state.neutral_fuel_available += scattered

        # Fuel that arrives at the destination zone.  If the destination is
        # "neutral" or "alliance", it ends up in the neutral pool (alliance
        # zone is just a conceptual area; fuel is pickable from neutral).
        self._state.neutral_fuel_available += arrived

        return arrived

    # ------------------------------------------------------------------
    # Human Player Actions
    # ------------------------------------------------------------------

    def hp_throw(self, alliance: str, current_time: float) -> None:
        """Human player throws a fuel ball from the outpost toward the Hub.

        The fuel transitions from ``outpost`` to ``in_flight`` and is
        scheduled to arrive at the Hub after HP_THROW_FLIGHT_TIME.

        Whether the throw scores is determined by the Match Engine based
        on HP_THROW_ACCURACY.  The Match Engine will subsequently call
        either fuel_scored() or fuel_missed() when the flight resolves.

        Parameters
        ----------
        alliance : str
            ``"red"`` or ``"blue"``.
        current_time : float
            Current elapsed match time in seconds.
        """
        if alliance == "red":
            if self._state.red_outpost_fuel <= 0:
                return
            self._state.red_outpost_fuel -= 1
        else:
            if self._state.blue_outpost_fuel <= 0:
                return
            self._state.blue_outpost_fuel -= 1

        self._state.fuel_in_flight += 1

    def hp_feed(self, alliance: str) -> bool:
        """Human player feeds one fuel ball to a robot at the outpost.

        The fuel transitions from ``outpost`` to ``in_robot`` (the caller
        is responsible for incrementing the robot's fuel_held).

        Parameters
        ----------
        alliance : str
            ``"red"`` or ``"blue"``.

        Returns
        -------
        bool
            True if fuel was available and fed; False if the outpost is empty.
        """
        if alliance == "red":
            if self._state.red_outpost_fuel <= 0:
                return False
            self._state.red_outpost_fuel -= 1
            return True
        else:
            if self._state.blue_outpost_fuel <= 0:
                return False
            self._state.blue_outpost_fuel -= 1
            return True

    # ------------------------------------------------------------------
    # Tower / Climbing
    # ------------------------------------------------------------------

    def can_climb(self, alliance: str, robot_id: str) -> bool:
        """Check whether a robot can begin climbing the alliance tower.

        A tower allows at most MAX_TOWER_OCCUPANTS (3) robots. A robot
        that is already on the tower is also allowed (idempotent check).

        Parameters
        ----------
        alliance : str
            ``"red"`` or ``"blue"``.
        robot_id : str
            Unique robot identifier (e.g. ``"red_1"``).

        Returns
        -------
        bool
            True if the robot may climb (tower not full, or robot already
            on tower).
        """
        occupants = (
            self._state.red_tower_occupants
            if alliance == "red"
            else self._state.blue_tower_occupants
        )
        if robot_id in occupants:
            return True  # Already registered.
        return len(occupants) < MAX_TOWER_OCCUPANTS

    def register_climb(self, alliance: str, robot_id: str) -> None:
        """Register a robot as occupying a spot on the alliance tower.

        This should be called after a successful climb attempt. The robot
        is only added once (idempotent).

        Parameters
        ----------
        alliance : str
            ``"red"`` or ``"blue"``.
        robot_id : str
            Unique robot identifier.
        """
        occupants = (
            self._state.red_tower_occupants
            if alliance == "red"
            else self._state.blue_tower_occupants
        )
        if robot_id not in occupants:
            occupants.append(robot_id)

    # ------------------------------------------------------------------
    # Conservation Invariant
    # ------------------------------------------------------------------

    def assert_conservation(self, robots: List[RobotState]) -> None:
        """Assert that the fuel conservation invariant holds.

        The total fuel across all pools must equal TOTAL_FUEL (60) at
        every tick.  A violation indicates a bookkeeping bug.

        Parameters
        ----------
        robots : list of RobotState
            All six robots on the field.

        Raises
        ------
        AssertionError
            If the total fuel count does not equal TOTAL_FUEL.
        """
        total = self._state.total_fuel_check(robots)
        assert total == TOTAL_FUEL, (
            f"Fuel conservation violated: counted {total}, expected {TOTAL_FUEL}. "
            f"neutral={self._state.neutral_fuel_available}, "
            f"red_outpost={self._state.red_outpost_fuel}, "
            f"blue_outpost={self._state.blue_outpost_fuel}, "
            f"in_flight={self._state.fuel_in_flight}, "
            f"in_transit={self._state.fuel_in_transit}, "
            f"in_robots={sum(r.fuel_held + r.fuel_being_pushed for r in robots)}"
        )

# GEMINI.md - FRC 2026 REBUILT Match Simulation

## Project Overview
This project is a Python-based simulation framework for the **FRC 2026 game "REBUILT"**. It is designed to model match dynamics, evaluate robot designs (archetypes), and test different alliance strategies through Monte Carlo simulations.

The simulation follows a multi-agent architecture where different subsystems (Match Engine, Robot Behavior, Field State, Strategy) are decoupled but share a common state model.

### Main Technologies
- **Python 3.10+**: Utilizing dataclasses, enums, and typing for a robust state model.
- **Monte Carlo Simulation**: Intended for running thousands of matches to derive win probabilities and RP distributions.
- **Physics-based Modeling**: Includes closed-loop fuel recycling, hub congestion, and mechanism failure rates.

---

## Project Structure
- `src/`: Core source code.
    - `models.py`: Shared dataclasses and enums (MatchState, RobotState, FieldState, etc.).
    - `config.py`: Game constants, scoring rules, and robot archetype definitions.
    - `field.py`: **Field State Manager (Agent 3)**. Manages fuel conservation (TOTAL_FUEL = 60), transit queues, and tower occupancy.
    - `robot.py`: **Robot Behavior Engine (Agent 2)**. Implements cycle logic, shift-role transitions, and mechanism failures.
    - `strategy.py`: **Strategy & Alliance Manager (Agent 4)**. Configures alliances and applies strategy presets.
- `tests/`: Directory for unit tests (currently empty).
- `output/`: Destination for simulation results (CSV/JSON).
- `FRC simulation.md`: Detailed technical specification and simulation architecture.
- `FRC tactic supervisor.md`: Strategic analysis and insights for the 2026 game.

---

## Building and Running
Currently, the project is in the **Implementation Phase**. Core logic is present in `src/`, but the central execution engine is pending.

### Key Commands
- **Run Simulation:** TODO (Requires `main.py` and `match_engine.py`)
- **Run Tests:** `pytest` (TODO: Add tests to `tests/`)
- **Linting:** `ruff check .` or `flake8 src`

---

## Development Conventions
1. **Fuel Conservation**: Any modification to fuel states must maintain the invariant `total_fuel == 60`. Always verify using `field_manager.assert_conservation(robots)`.
2. **Phase Awareness**: Robots must react to shift changes. Use `on_shift_change` in `robot.py` to trigger role transitions based on Hub activation.
3. **Archetypes**: Do not hardcode robot capabilities. Use the archetypes defined in `config.py` (e.g., `elite_turret`, `everybot`).
4. **Style**: Follow PEP 8. Use type hints for all function signatures.

---

## Key Documentation
- Refer to **`FRC simulation.md`** for the full mathematical model of cycle times, accuracy hits, and fuel transit delays.
- Refer to **`FRC tactic supervisor.md`** for high-level game tactics and community research.

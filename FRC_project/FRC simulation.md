# FRC 2026 REBUILT Match Simulation

## Overview

This document specifies a simulation framework for the FRC 2026 game **REBUILT**. It is designed so that multiple agents can independently implement, test, and extend different subsystems of the simulation.

---

## 1. Game Summary

Two alliances (Red and Blue), each with **3 robots**, compete on a 27ft x 54ft field for **2 minutes 40 seconds (160 seconds)**. Robots collect **Fuel** (ball game pieces) and score them into their alliance's **Hub** when it is active. Robots can also climb the **Tower** for bonus points. Human players at **Outposts** can feed fuel to robots or throw fuel directly into an active Hub.

---

## 2. Match Timeline

| Phase       | Duration | Start (s) | End (s) | Notes                                          |
|-------------|----------|-----------|---------|------------------------------------------------|
| Auto        | 20s      | 0         | 20      | Pre-programmed only. Both Hubs active.         |
| Transition  | 10s      | 20        | 30      | No scoring. Drivers take control.              |
| Shift 1     | 25s      | 30        | 55      | Hub status determined by Auto winner.          |
| Shift 2     | 25s      | 55        | 80      | Hub status swaps from Shift 1.                 |
| Shift 3     | 25s      | 80        | 105     | Same Hub status as Shift 1.                    |
| Shift 4     | 25s      | 105       | 130     | Same Hub status as Shift 2.                    |
| Endgame     | 30s      | 130       | 160     | Both Hubs active. Tower climbing window.       |

### Hub Activation Rules

- **Auto winner** = alliance that scores more Fuel during Auto.
- If Auto winner is Red: Red Hub is **Inactive** during Shifts 1 & 3, **Active** during Shifts 2 & 4. Blue Hub is the inverse.
- If Auto is tied: both Hubs follow same alternating pattern (Red inactive first by default, or coin flip).
- During **Auto** and **Endgame**: both Hubs are **Active**.

---

## 3. Scoring Table

| Action                            | Points | Phase Restriction             |
|-----------------------------------|--------|-------------------------------|
| Fuel scored in **Active** Hub     | 1      | Any phase (when Hub is active)|
| Fuel scored in **Inactive** Hub   | 0      | Wasted shot                   |
| Human Player fuel in Active Hub   | 1      | Teleop shifts + Endgame       |
| Tower Level 1 (Auto)              | 15     | Auto only                     |
| Tower Level 1 (Teleop/Endgame)    | 10     | Teleop/Endgame only           |
| Tower Level 2                     | 20     | Teleop/Endgame only           |
| Tower Level 3                     | 30     | Teleop/Endgame only           |

### Scoring Rules

- Fuel into an inactive Hub = **0 match points** and does **not** count toward Ranking Point thresholds.
- A robot may only earn Tower points for **Level 1** during Auto.
- A robot may only earn Tower points for **a single Level** during Teleop (choose one: L1, L2, or L3).
- There is **no way to lose points**. Penalties add points to the opposing alliance.

### Ranking Points (Qualification Matches)

| RP Category   | Threshold                  | RP Earned |
|---------------|----------------------------|-----------|
| Match Win     | Higher total score          | 3         |
| Match Tie     | Equal total score           | 1 each    |
| Energized     | Score >= 100 Fuel points    | 1         |
| Supercharged  | Score >= 360 Fuel points    | 1         |
| Traversal     | Earn >= 50 Tower points     | 1         |

Maximum RP per match: **6** (Win + Energized + Supercharged + Traversal).

---

## 4. Field Layout

```
+------------------------------------------------------------------+
|  [BLUE ALLIANCE STATION]                                          |
|  [Blue Outpost L]    [Blue Tower]    [Blue Outpost R]            |
|                                                                   |
|                         [Blue Hub]                                |
|                                                                   |
|  ======================== MIDFIELD =============================  |
|                      [Neutral Fuel Zone]                         |
|  ======================== MIDFIELD =============================  |
|                                                                   |
|                         [Red Hub]                                 |
|                                                                   |
|  [Red Outpost L]     [Red Tower]     [Red Outpost R]             |
|  [RED ALLIANCE STATION]                                           |
+------------------------------------------------------------------+
```

### Key Field Elements

| Element          | Description                                                    |
|------------------|----------------------------------------------------------------|
| Hub              | Scoring target for Fuel. Has Active/Inactive states per shift. |
| Tower            | 3 rungs (Low, Mid, High) in alliance area for climbing.        |
| Outpost          | Human player stations on field sides. Feed fuel to robots.     |
| Neutral Zone     | Center field area with shared Fuel supply.                     |
| Alliance Station | Driver station behind the alliance wall.                       |

---

## 5. Game Pieces

### Fuel

| Property    | Value                            |
|-------------|----------------------------------|
| Type        | Foam ball                        |
| Diameter    | ~7 inches (~18 cm)               |
| Weight      | Light (< 0.5 lbs)               |
| Quantity    | ~60 on field at match start      |
| Refeed      | Human players can introduce more |

### Fuel Locations at Match Start

- ~20 in Neutral Zone (center field)
- ~10 pre-loaded per alliance (split across 3 robots)
- ~10 at each alliance's Outpost stations

### Fuel Physics & Recycling Model

Fuel operates as a **closed-loop system** -- the ~60 fuel on the field are the same balls all match. When scored into a Hub, fuel falls out the bottom and returns to the Neutral Zone. This creates critical physical constraints:

#### Fuel State Machine

Each individual fuel ball is always in exactly one state:

```
┌──────────┐   Robot     ┌──────────┐   Robot      ┌──────────┐
│  On Field │──intake───>│ In Robot  │──shoots────>│ In Flight │
│ (pickable)│            │ (carried) │             │ (airborne)│
└──────────┘            └──────────┘             └─────┬─────┘
     ^                                                  │
     │                  ┌──────────┐    Gravity         │
     │<────returns──────│ In Transit│<───falls───────────┘
     │   to field       │ (Hub->NZ) │   into Hub
     │                  └──────────┘
     │
     │   HP feeds       ┌──────────┐
     │<────────────────│ At Outpost│  (HP can also throw -> In Flight)
                        └──────────┘
```

#### Transit Times

| Transition                        | Duration    | Notes                                           |
|-----------------------------------|-------------|------------------------------------------------|
| In Flight (robot shot -> Hub)     | 0.5 - 1.5s  | Depends on distance and shot arc               |
| Hub fall-through to Neutral Zone  | 1.0 - 2.0s  | Gravity + rolling back to pickable position    |
| **Total: shot to available**      | **1.5 - 3.5s** | Ball is **unavailable** during this window  |
| Missed shot recovery              | 2.0 - 4.0s  | Ball bounces and settles somewhere on field    |
| HP throw (Outpost -> Hub)         | 1.0 - 2.0s  | Shorter arc from fixed position               |

#### Fuel Pool Accounting

At any tick, the total fuel is conserved:

```
TOTAL_FUEL = fuel_on_field + fuel_in_robots + fuel_in_flight + fuel_in_transit + fuel_at_outposts
```

Where `TOTAL_FUEL` is constant (~60) throughout the match.

#### Scoring Rate Cap (Throughput Limit)

The recycling delay creates a **hard ceiling** on alliance scoring rate:

| Scenario                          | Max Fuel Throughput            |
|-----------------------------------|-------------------------------|
| 1 robot shooting, ~3s recycle     | ~20 fuel/min (1 every 3s)     |
| 3 robots shooting, ~3s recycle    | ~40-50 fuel/min (limited by fuel availability, not robots) |
| With HP throwing simultaneously   | +10-15 fuel/min additional    |
| **Practical field-wide cap**      | **~50-60 fuel/min** (all fuel constantly cycling) |

When multiple robots try to score rapidly, they can **starve each other** -- there simply aren't enough balls on the field to sustain all robots at max cycle speed simultaneously.

#### Fuel Starvation Model

The simulation must track fuel availability and apply starvation when demand exceeds supply:

```python
# Per tick, check if robot wants to intake but no fuel available at its location
if robot.current_action == "intaking" and field.fuel_at(robot.position) <= 0:
    robot.action = "waiting_for_fuel"
    # Robot idles until fuel recycles back to a pickable location
```

**Starvation probability increases when:**
- Both alliances are scoring at high rates (fuel is "in the air" more often)
- One alliance hoards fuel (holds max capacity without shooting)
- Robots cluster at the same fuel source (congestion + depletion)

#### Impact on Strategy

- **Collecting during inactive Hub**: Smart teams collect fuel while their Hub is inactive, so they have a full load ready when it activates. This doesn't remove fuel from the pool since they're holding it, not scoring it.
- **Burst scoring**: Dumping 6-8 fuel rapidly into an active Hub temporarily depletes the available pool, creating a ~10-20s scarcity window.
- **Human Player throughput**: HP-thrown fuel that scores also enters the recycle loop. HP fuel that misses lands on the field immediately (no transit delay).
- **Defense value increases**: Slowing opponents means fewer fuel in transit, which paradoxically makes more fuel available for pickup -- defense disrupts cycle efficiency, not fuel supply.

---

## 6. Robot Specifications & Physical Constraints

| Constraint             | Value                       |
|------------------------|-----------------------------|
| Weight limit           | 125.5 lbs (56.9 kg)        |
| Frame perimeter        | <= 110 in (2.79 m)         |
| Starting height        | <= 30 in (76.2 cm)         |
| Horizontal extension   | <= 12 in beyond perimeter  |
| Bumper height (zone)   | 2.5 - 8.5 in from floor   |
| Alliance size          | 3 robots per alliance      |
| Trench clearance       | 40.25 in tall opening       |

### 6.1 Drivetrain / Chassis Options

The drivetrain determines a robot's speed, agility, pushing power, and whether it can fit through the trench. Most competitive teams in 2026 run swerve drive. The simulation should assign a drivetrain type to each robot.

#### Swerve Drive Modules (Most Common in Competition)

| Module              | Vendor | Wheel  | Weight (per module) | Gear Ratios Available | Notes                                    |
|---------------------|--------|--------|--------------------|-----------------------|------------------------------------------|
| **SDS MK4i**        | SDS    | 4" OD  | ~6.0-6.3 lbs       | L1, L2 (most popular), L3 | Inverted motors, corner-biased. Proven reliability. Most widely used. |
| **SDS MK4n**        | SDS    | 4" OD  | ~6.0-6.5 lbs       | L1+, L2, L3+          | Narrow (4" wide inside frame). Enables wider intakes between modules. |
| **SDS MK5n**        | SDS    | 4" OD  | ~5.5-6.0 lbs       | 3 ratios              | Smallest inverted SDS module. 5"x7.5" footprint. Newest. |
| **WCP SwerveX2**    | WCP    | 4" OD  | ~3.3-4.3 lbs       | X1, X2, X3 (9 configs)| No belts. Kraken X60 optimized. Lightest. |
| **WCP SwerveX2S**   | WCP    | 4" OD  | ~3.0-3.6 lbs       | Multiple               | SplineXS bore. Kraken/NEO/Vortex compatible. |
| **REV MAXSwerve**   | REV    | 3" OD  | ~5.5 lbs            | Multiple               | Supported code base. Good for beginners.  |

#### Free Speed Ranges (approximate, with Kraken X60 motors)

| Gear Ratio Tier | Free Speed      | Practical Speed  | Best For                              |
|-----------------|-----------------|------------------|---------------------------------------|
| L1 / X1 (slow)  | ~12-13 ft/s     | ~10-11 ft/s      | Heavy robots, high-push defense bots  |
| L2 / X2 (mid)   | ~14-16 ft/s     | ~12-13 ft/s      | **Standard competition** (most teams) |
| L3 / X3 (fast)  | ~17-19 ft/s     | ~14-16 ft/s      | Lightweight fast-cycle robots         |

#### Other Drivetrain Types

| Drivetrain      | Max Speed  | Agility     | Trench Fit | Pushing Power | Who Uses It              |
|-----------------|------------|-------------|------------|---------------|--------------------------|
| **Swerve**      | 12-19 ft/s | Excellent   | Depends on height | Medium   | ~60-70% of competitive teams |
| **Tank (AM14U)** | 10-14 ft/s | Low (skid steer) | Usually fits | High  | KitBot, rookie teams     |
| **Mecanum**     | 8-12 ft/s  | Good (strafe)| Fits       | Very Low      | Rare in 2026             |

#### Drivetrain Impact on Simulation

| Parameter                   | Swerve              | Tank                  |
|-----------------------------|---------------------|-----------------------|
| Drive time (cross field)    | 2.5-4s              | 3.5-5.5s              |
| Alignment to Hub            | Instant (can strafe)| Must rotate (1-2s)    |
| Defense evasion             | Can strafe away     | Must drive around      |
| Defense pushing power       | Medium              | High (more traction)   |
| Trench traversal            | If height allows    | Usually fits           |

---

## 7. Robot Mechanical Configurations & Archetypes

Each simulated robot is defined by two layers: a **mechanical configuration** (hardware capabilities) and a **performance tier** (how well the team executes). Together they determine what the robot can physically do and how consistently it does it.

### 7.1 Shooter Subsystem Types

The shooter is the most impactful mechanism choice. It determines shooting rate, accuracy at range, and whether the robot can shoot while moving.

| Shooter Type           | Barrels | Can Rotate (Turret) | Shooting Rate | Accuracy at Range | Shoot While Moving | Complexity |
|------------------------|---------|---------------------|---------------|-------------------|---------------------|------------|
| **Single Turret**      | 1       | Yes (360 continuous) | 3-5 fuel/s   | High (tracks Hub)  | Yes                 | High       |
| **Double Fixed**       | 2       | No (fixed angle)     | 5-8 fuel/s   | Medium (must align) | No (must face Hub) | Medium     |
| **Triple Fixed**       | 3       | No (fixed angle)     | 8-10 fuel/s  | Medium (must align) | No (must face Hub) | High       |
| **Single Fixed**       | 1       | No (fixed angle)     | 2-4 fuel/s   | Medium-Low         | No (must face Hub)  | Low        |
| **Dumper/Gravity**     | N/A     | No                   | All at once   | High (close range) | No (must be at Hub) | Low        |

#### Turret vs Fixed Tradeoffs

**Single Turret (rotatable):**
- Can track the Hub while driving, enabling **shoot-on-the-move** -- the robot doesn't need to stop and align
- Reduces effective cycle time by ~2-3s (no alignment phase)
- More mechanically complex, heavier, higher failure risk
- Typical teams: elite/strong tier with vision tracking (e.g., Limelight/PhotonVision)

**Multi-Barrel Fixed (double/triple):**
- Higher instantaneous throughput (dump fuel faster when aligned)
- Robot must **face the Hub** to shoot -- requires a drive-and-align phase adding ~1-2s per cycle
- Each barrel has its own flywheel/motor (e.g., WCP CC uses 3 independent Kraken-powered shooters)
- Best for **burst scoring** at shift boundaries (dump stockpile fast)
- Cannot shoot while moving or while facing away from Hub

**Dumper (gravity-fed):**
- Must drive right up to the Hub and release fuel over the edge
- Highest accuracy (near 100% at point-blank) but zero range
- Slowest cycle because of the drive-to-Hub requirement
- Simplest mechanism, most reliable

### 7.2 Shooting Angle & Range

The shooter's adjustable angle determines how far from the Hub a robot can score:

| Angle Capability       | Effective Range    | Description                                          |
|------------------------|--------------------|------------------------------------------------------|
| **Fixed low angle**    | 0-4 ft from Hub    | Must be very close. Typical of dumpers/basic shooters |
| **Fixed high angle**   | 4-10 ft from Hub   | Set once, optimized for one distance                 |
| **Adjustable hood**    | 2-15 ft from Hub   | Can change angle mid-match. Enables multi-range shots |
| **Full variable**      | 2-20+ ft from Hub  | Continuous angle adjustment. Elite teams only         |

**Impact on simulation:**
- Robots with longer range can shoot from the Neutral Zone area, saving drive time to Hub
- Short-range robots must drive all the way to the Hub zone, adding ~2-4s per cycle
- Adjustable angle + turret = shoot from anywhere on your half of the field

### 7.3 Intake Subsystem

| Intake Type           | Pickup Speed  | Ground Pickup | Outpost Pickup | Notes                                |
|-----------------------|---------------|---------------|----------------|--------------------------------------|
| **Over-bumper roller**| 0.3-0.5s/fuel | Yes           | Yes            | Standard for most competitive robots |
| **Under-bumper**      | 0.2-0.4s/fuel | Yes           | Requires align | Faster but harder to package         |
| **Funnel/passive**    | 0.5-1.0s/fuel | Slow          | Yes            | Simple, less consistent              |
| **None (HP fed only)**| N/A           | No            | Yes            | Relies entirely on Human Players     |

### 7.4 Hopper / Fuel Storage

| Hopper Type          | Capacity     | Feed Consistency | Notes                                          |
|----------------------|-------------|------------------|------------------------------------------------|
| **Large hopper**     | 10-15 fuel  | Can jam at high throughput | KitBot-style open top. Shaking may lose fuel |
| **Medium hopper**    | 6-8 fuel    | Good             | Typical competitive robot                      |
| **Small hopper**     | 3-5 fuel    | Reliable         | Simpler, less jamming                          |
| **Serializer/indexer**| 4-6 fuel   | Excellent        | Queues fuel one-by-one to shooter. No jams     |
| **Spindexer**        | 5-8 fuel    | Excellent        | Rotary indexed magazine. High throughput       |

**Jam probability per cycle:**
- Large hopper: 5-10% chance per dump
- Serializer/spindexer: <1% chance
- A jam costs 2-5 seconds to clear

### 7.5 Community Robot Baselines

These are real community-published robot designs that represent distinct performance floors. They serve as **baseline tiers** in the simulation.

#### KitBot (FIRST Official)

The minimum viable robot provided by FIRST. Every team can build one.

| Property          | Value                                                    |
|-------------------|----------------------------------------------------------|
| Fuel capacity     | 10-15 fuel (large open-top hopper)                       |
| Shooter           | Single fixed, low-angle flywheel                         |
| Shooting rate     | ~2 fuel/s                                                |
| Effective range   | 2-6 ft (close to Hub)                                   |
| Intake            | Basic over-bumper roller                                 |
| Drivetrain        | Tank drive (AM14U chassis)                               |
| Climb             | None (base). L1 with iteration.                          |
| Auto capability   | Drive forward + dump pre-loaded fuel (0-3 fuel)          |
| Cycle time        | 20-30s (slow drive, close-range only)                    |
| Shot accuracy     | 40-55% (fixed angle, no vision tracking)                 |
| Reliability       | High (simple mechanisms)                                 |

#### Everybot (Robonauts 118)

Low-resource but competitive robot. Designed to do *everything* at a basic level.

| Property          | Value                                                    |
|-------------------|----------------------------------------------------------|
| Fuel capacity     | 5-8 fuel (enclosed hopper)                               |
| Shooter           | Single fixed, medium-angle flywheel                      |
| Shooting rate     | ~3 fuel/s                                                |
| Effective range   | 3-8 ft                                                   |
| Intake            | Over-bumper roller with funnel                           |
| Drivetrain        | Swerve (MK4i) or tank (team choice)                      |
| Climb             | L1-L2 (designed for L2, L3 possible with iteration)     |
| Auto capability   | 2-4 fuel scored                                          |
| Cycle time        | 15-22s                                                   |
| Shot accuracy     | 50-65%                                                   |
| Reliability       | High                                                     |

#### WCP CC "Big Dumper" (West Coast Products)

Competitive concept showcasing COTS components. Represents a strong-to-elite tier.

| Property          | Value                                                    |
|-------------------|----------------------------------------------------------|
| Fuel capacity     | 8-12 fuel (large indexed hopper)                         |
| Shooter           | Triple fixed flywheels (3x independent Kraken motors)    |
| Shooting rate     | 8-10 fuel/s (rapid burst dump)                           |
| Effective range   | 4-12 ft                                                  |
| Intake            | Wide over-bumper roller                                  |
| Drivetrain        | Swerve                                                   |
| Climb             | L2-L3                                                    |
| Auto capability   | 4-6 fuel scored                                          |
| Cycle time        | 10-14s                                                   |
| Shot accuracy     | 70-85% (fixed angle, must align to Hub)                  |
| Reliability       | Medium (complex multi-shooter)                           |

#### Custom Elite (e.g., 2826 Wave Robotics style)

Top-tier custom design with turret, vision tracking, and spindexer.

| Property          | Value                                                    |
|-------------------|----------------------------------------------------------|
| Fuel capacity     | 6-8 fuel (spindexer magazine)                            |
| Shooter           | Single turret (360 continuous rotation), adjustable hood |
| Shooting rate     | 3-5 fuel/s (but continuous while moving)                 |
| Effective range   | 4-20+ ft (full-field shooting with angle adjustment)     |
| Intake            | Under-bumper or wide over-bumper                         |
| Drivetrain        | Swerve with odometry + vision                            |
| Climb             | L3 (dedicated climb mechanism)                           |
| Auto capability   | 5-8 fuel scored (shoot while moving in auto paths)       |
| Cycle time        | 7-10s (no alignment needed, shoot-on-the-move)           |
| Shot accuracy     | 85-95% (turret tracks Hub via vision, adjustable angle)  |
| Reliability       | Medium-Low (complex turret + spindexer can fail)         |

### 7.6 Archetype Summary Table

Combining mechanical config with performance tier:

| Archetype           | Based On         | Capacity | Shooter Type         | Cycle Time (s) | Auto Fuel | Climb | Accuracy |
|---------------------|------------------|----------|----------------------|-----------------|-----------|-------|----------|
| **Elite Turret**    | Custom Elite     | 6-8      | Single Turret + Hood | 7-10            | 5-8       | L3    | 85-95%   |
| **Elite Multi-Shot**| WCP CC style     | 8-12     | Triple Fixed         | 10-14           | 4-6       | L2-L3 | 70-85%   |
| **Strong Scorer**   | Upgraded Everybot| 5-8      | Single/Double Fixed  | 12-16           | 3-5       | L2    | 65-80%   |
| **Everybot**        | 118 Everybot     | 5-8      | Single Fixed         | 15-22           | 2-4       | L1-L2 | 50-65%   |
| **KitBot+**         | Iterated KitBot  | 10-15    | Single Fixed (low)   | 20-28           | 1-3       | L1    | 40-55%   |
| **KitBot Base**     | Stock KitBot     | 10-15    | Single Fixed (low)   | 25-35           | 0-2       | None  | 30-45%   |
| **Defense Bot**     | Any chassis      | 0-3      | None or minimal      | N/A             | 0-1       | L1    | 20-35%   |

### 7.7 How Shooter Type Affects Cycle Time

The shooter type changes the **scoring phase** of each cycle. This is the breakdown of where time is spent:

```
Full Cycle = Drive to Fuel + Intake + Drive to Hub + [Align] + Shoot + [Hub Transit]
```

| Phase              | Turret Robot      | Fixed Multi-Shot  | Fixed Single     | Dumper           |
|--------------------|-------------------|-------------------|------------------|------------------|
| Drive to fuel      | 2-3s              | 2-3s              | 2-3s             | 2-3s             |
| Intake (fill up)   | 1.5-3s            | 2-4s              | 2-4s             | 3-5s             |
| Drive to Hub       | 1-2s (can be far) | 2-3s              | 2-4s             | 3-5s (must be close)|
| Align to Hub       | **0s** (turret tracks)| **1-2s**       | **1-2s**         | **0s** (at Hub)  |
| Shoot all fuel     | 1.5-2.5s          | 0.8-1.5s          | 1.5-3s           | 0.5-1s           |
| **Total cycle**    | **6-10s**         | **8-13s**         | **9-16s**        | **9-15s**        |

Key insight: the **turret robot has a shorter cycle not because it shoots faster** (multi-shot is faster at dumping), but because it **eliminates the alignment phase** and can **shoot from farther away** (shorter drive-to-Hub).

The **multi-shot robot** excels at **burst scoring** -- when pre-positioned at the Hub with a full stockpile, it can dump 8-12 fuel in ~1 second, far faster than a turret's 3-5 fuel/s.

### 7.8 Cycle Definition (Updated)

A **scoring cycle** consists of:
1. Drive to fuel source (Neutral Zone or Outpost)
2. Intake fuel (capacity and speed vary by intake type)
3. Drive toward Hub (distance depends on shooter range)
4. **Align to Hub** (turret: 0s, fixed: 1-2s, dumper: must be at Hub)
5. Score fuel (rate depends on shooter type)

A **stockpiling cycle** (during inactive Hub shifts) consists of:
1. Drive to fuel source (Neutral Zone or Outpost)
2. Intake fuel up to capacity
3. Hold fuel and **pre-position** near Hub for burst dump at shift change

A **defense cycle** consists of:
1. Drive to opponent's zone
2. Shadow/block the opponent's best scorer
3. Continue until shift changes or strategy dictates otherwise

### 7.9 Climb Success Rate (by Archetype)

| Archetype            | L1 Success | L2 Success | L3 Success |
|----------------------|------------|------------|------------|
| Elite Turret         | 99%        | 95%        | 85%        |
| Elite Multi-Shot     | 99%        | 90%        | 75%        |
| Strong Scorer        | 98%        | 85%        | 55%        |
| Everybot             | 95%        | 70%        | 25%        |
| KitBot+              | 80%        | 30%        | 0%         |
| KitBot Base          | 0%         | 0%         | 0%         |
| Defense Bot          | 75%        | 10%        | 0%         |

### 7.10 Reliability & Failure Model

More complex mechanisms have higher failure risk during a match:

| Archetype            | Mechanism Failure Rate (per match) | Failure Cost       |
|----------------------|------------------------------------|---------------------|
| Elite Turret         | 8-15%                              | Turret stuck: lose turret tracking, become fixed shooter. -20% accuracy, +2s align time |
| Elite Multi-Shot     | 10-15%                             | 1 barrel jams: lose 33% throughput. All jam: 5s clear time |
| Strong Scorer        | 5-10%                              | Shooter jam: 3-5s to clear                                |
| Everybot             | 3-5%                               | Intake stall: 2-3s to unjam                               |
| KitBot+              | 5-8%                               | Fuel falls out of hopper (open top): lose 1-3 fuel        |
| KitBot Base          | 3-5%                               | Minimal mechanisms to fail                                |
| Defense Bot          | 2-3%                               | Drivetrain issue: reduced speed                           |

### 7.11 Intake Failure & Degradation Model

Intakes are one of the most failure-prone mechanisms on an FRC robot. They extend beyond the frame perimeter, take repeated impacts from game pieces and field elements, and are the first thing to hit during collisions.

#### Intake Failure Modes

| Failure Type               | Probability (per match) | Trigger                                      | Effect                                        |
|----------------------------|-------------------------|----------------------------------------------|-----------------------------------------------|
| **Total intake breakdown** | 3-8% (complex), 1-3% (simple) | Impact with field element, motor burnout, chain/belt snap | Robot **cannot pick up fuel from ground**. Must rely entirely on HP feed at Outpost, or become defense-only. |
| **Partial degradation**    | 10-20% (complex), 5-10% (simple) | Rollers slow, alignment shifts, bent mounting | Intake speed drops 50%. "Touch and go" fails -- robot **pushes fuel around** instead of grabbing it cleanly. |
| **Jam / stall**            | 5-15% per match         | Fuel wedged in intake, double-feed           | Robot must stop and reverse intake for 2-4s to clear. |

#### "Touch and Go" vs "Push Around" Intake Quality

Not all intakes can reliably grab fuel on the first contact while driving at speed. This is a critical differentiator:

| Intake Quality    | Pickup Behavior                                              | Fuel Acquired per Attempt | Time per Fuel | Who Has It     |
|-------------------|--------------------------------------------------------------|--------------------------|---------------|----------------|
| **Touch and go**  | Drives over fuel at full speed, fuel is sucked in instantly  | 95-99%                   | 0.2-0.4s      | Elite, Strong scorers with tuned intakes |
| **Slow pickup**   | Must slow down, align with fuel, then intake                 | 80-90%                   | 0.5-1.0s      | Everybot, well-built KitBot+ |
| **Push around**   | Robot pushes fuel ahead/sideways before eventually grabbing it. Multiple attempts needed. | 50-70% per attempt | 1.0-3.0s | KitBot base, degraded intakes, poorly tuned |
| **No ground pickup** | Cannot intake from ground at all. HP feed only.           | 0%                       | N/A           | Broken intake, some defense bots |

#### Post-Failure Robot Behavior

When an intake breaks mid-match, the robot's strategy must adapt:

| Intake State After Failure | Available Actions                                          | Effective Archetype Change |
|----------------------------|------------------------------------------------------------|---------------------------|
| **Fully broken**           | HP feed at Outpost only, or switch to full defense         | Becomes "Defense Bot" or "HP-Fed Scorer" (~50% original output) |
| **Degraded (push around)** | Can still acquire fuel but very slowly. Better to play defense. | Drops 1-2 tiers in scoring, +50-100% cycle time |
| **Jammed (temporary)**     | Stop, reverse intake, clear jam (2-4s), resume normal      | Brief pause, no tier change |

#### Intake Robustness by Design

| Design Feature                | Robustness Rating | Notes                                      |
|-------------------------------|-------------------|--------------------------------------------|
| Polycarbonate/lexan guards    | High              | Protects rollers from side impacts         |
| Pneumatic deployment          | Medium-High       | Can retract intake to protect it           |
| Spring-loaded / compliant     | High              | Absorbs impacts without bending            |
| Rigid fixed mount             | Low-Medium        | First hard hit can bend mounting brackets  |
| Over-bumper (protected)       | High              | Bumpers shield the intake from most hits   |
| Under-bumper (exposed)        | Low               | Directly contacts field elements & robots  |

### 7.12 Fuel Pushing & Neutral Zone Denial Tactics

Robots with degraded intakes -- or robots intentionally playing a denial role -- can **push fuel** instead of picking it up. This is a legitimate tactic:

#### The Push Tactic

Instead of intaking fuel, a robot drives into fuel balls and pushes them along the field:

```
Neutral Zone                    Field Wall               Alliance Zone
  [Fuel] [Fuel] [Fuel]  -->  pushed along wall  -->  [Fuel pile in your zone]
      ^                       through trench             for later pickup
      |
  Robot drives into fuel cluster,
  bulldozes them toward alliance side
```

#### Push Mechanics

| Parameter                    | Value                                         |
|------------------------------|-----------------------------------------------|
| Push speed                   | 4-8 ft/s (slower than free driving due to fuel resistance) |
| Fuel per push (cluster)      | 3-8 fuel can be bulldozed at once             |
| Push distance (NZ to alliance)| ~12-15 ft                                    |
| Time per push trip           | 3-5s (push) + 2-3s (return) = 5-8s total     |
| Fuel loss during push        | 10-30% scatter (fuel rolls away from cluster) |
| Trench push                  | Fuel can be pushed through the trench opening to alliance zone |

#### Strategic Value of Pushing

| Scenario                          | Value                                                       |
|-----------------------------------|-------------------------------------------------------------|
| **Neutral zone denial**           | Push fuel away from opponent access. They waste time chasing scattered fuel. |
| **Stockpile building**            | Push 5-8 fuel to your alliance zone during inactive shift. Scorers pick up from the pile during active shift. |
| **Broken intake backup**          | Robot with broken intake can still contribute by pushing fuel to teammates near Outpost/Hub. |
| **Defense + denial combo**        | 1 robot defends opponent scorer while also pushing nearby fuel out of their reach. |

#### Push vs Intake Efficiency Comparison

| Action                         | Fuel Moved to Alliance Zone per 25s Shift | Notes                              |
|--------------------------------|-------------------------------------------|------------------------------------|
| Elite intake + drive cycles    | 18-24 fuel (intaked and scored)           | Best case, direct scoring          |
| Push (dedicated pusher robot)  | 10-15 fuel (pushed to alliance zone)      | Fuel still needs to be picked up by a teammate |
| Push (broken intake fallback)  | 8-12 fuel                                 | Slower, less controlled            |
| No action (idle)               | 0 fuel                                    | Worst case                         |

**Important limitation:** Pushed fuel is NOT scored. It must still be picked up by a robot with a working intake and then shot. Pushing is a **support action** that pre-positions fuel for teammates.

---

## 8. Human Player Model

| Parameter              | Value                            |
|------------------------|----------------------------------|
| Fuel throw accuracy    | 40-70% (into active Hub)         |
| Throw rate             | 1 fuel every 3-5 seconds         |
| Feed rate (to robot)   | 1 fuel every 2-3 seconds         |
| Available fuel supply  | Unlimited (reintroduction)       |

Human players can either:
- **Feed** fuel to robots at Outposts (assists robot cycling)
- **Throw** fuel directly into the Hub (lower accuracy but parallel scoring)

---

## 9. Defense Model

### 9.1 Defense Disruption Effects

When a robot plays defense, it disrupts opposing robots. The impact depends on WHERE defense is played and WHAT shooter type the target has.

#### Base Defense Effects

| Effect                    | Value                                       |
|---------------------------|---------------------------------------------|
| Cycle time increase       | +30-60% to defended robot's cycle time      |
| Accuracy reduction (fixed shooter) | -15-25% (disrupts alignment phase) |
| Accuracy reduction (turret shooter) | -5-10% (turret compensates, but bumping still hurts) |
| Accuracy reduction (dumper) | -5-10% (must still reach Hub)             |

**Why fixed shooters suffer more from defense:** A fixed-shooter robot must stop, rotate to face the Hub, and hold steady while shooting. A defender bumping during the alignment phase forces re-alignment, wasting 1-3 extra seconds AND reducing accuracy. Turret robots can track the Hub through contact, so defense primarily slows their drive, not their shooting.

#### Shooter-Specific Defense Impact

| Target Shooter Type | Cycle Time Hit | Accuracy Hit | Missed Shots Increase | Notes |
|---------------------|----------------|--------------|----------------------|-------|
| Single Turret       | +30-40%        | -5-10%       | +5-10%               | Turret compensates; defender mainly slows driving |
| Double/Triple Fixed | +40-60%        | -15-25%      | +15-25%              | Alignment phase is vulnerable; re-alignment wastes time |
| Single Fixed        | +40-55%        | -15-20%      | +15-20%              | Same alignment vulnerability as multi-fixed |
| Dumper              | +30-50%        | -5-10%       | +5-10%               | Must reach Hub; defender blocks path but accuracy is close-range |

### 9.2 Alliance Zone Defense Penalties

**Defending in the opponent's alliance zone carries elevated penalty risk.** Referees watch alliance zone defense more closely because aggressive contact near scoring areas is more likely to interfere with game rules.

| Defense Location        | Foul Rate (per 25s shift) | Tech Foul Rate (per shift) | Notes |
|-------------------------|---------------------------|----------------------------|-------|
| Neutral Zone            | 5-10%                     | 1-2%                       | Standard defense, lower scrutiny |
| **Opponent Alliance Zone** | **15-25%**              | **4-8%**                   | Near Hub/Tower. Refs watch closely. Blocking Hub access or pinning = tech foul |
| Near Opponent Tower     | 20-30%                    | 8-12%                      | Highest risk. Interfering with climb attempts is heavily penalized |

#### Penalty Escalation

Repeated fouls in the same match increase the chance of tech fouls:

| Fouls Already Drawn | Tech Foul Probability Multiplier |
|---------------------|----------------------------------|
| 0                   | 1.0x (base rate)                 |
| 1                   | 1.5x                            |
| 2+                  | 2.0x (refs are watching you)     |

### 9.3 Penalty Points

| Penalty      | Points (awarded to opponent) |
|--------------|------------------------------|
| Foul         | 5                            |
| Tech Foul    | 12                           |

---

## 10. Phase-Aware Strategy Model

The alternating Hub shifts are the core strategic driver of REBUILT. Each robot should have a **per-phase behavior plan**, not a single match-long role.

### The Strategic Dilemma Per Shift

During each 25-second shift, **only one alliance's Hub is active**. This means:
- The **active alliance** should be scoring as fast as possible (limited window).
- The **inactive alliance** must choose how to spend its 25 seconds productively.

### Inactive-Hub Actions (What To Do When You Can't Score)

| Action               | Description                                                    | Who Should Do It       |
|----------------------|----------------------------------------------------------------|------------------------|
| **Stockpile**        | Collect fuel from Neutral Zone / Outpost, fill to capacity.    | Scorers (all types)    |
| **Pre-position**     | Drive to Hub area with full load, ready to dump at shift swap. | Fast scorers           |
| **Cross-field Defense** | Enter opponent's zone and disrupt their active-Hub scoring. Higher foul risk in their alliance zone (see 9.2). | Defense bots, or 1 scorer assigned to defend |
| **Deny Neutral Fuel** | Camp Neutral Zone to grab fuel before opponents can.          | Any robot              |
| **Push Fuel to Alliance Zone** | Bulldoze neutral fuel through trench/along walls to your side. Builds a fuel reserve for teammates. | Broken-intake robots, dedicated pushers, defense bots between shifts |
| **Push + Deny Combo** | Push fuel away from opponent access AND toward your zone simultaneously. | Any robot with working drivetrain |

### Active-Hub Actions (What To Do When You Can Score)

| Action               | Description                                                    | Who Should Do It       |
|----------------------|----------------------------------------------------------------|------------------------|
| **Dump stockpile**   | Immediately score pre-loaded fuel at shift start.              | Pre-positioned scorers |
| **Full cycles**      | Intake -> drive -> score as many times as possible in 25s.     | All scorers            |
| **Continue defense** | Stay on defense even during own active shift (rare, risky).    | Only if opponent is very dangerous |

### Per-Phase Robot Behavior Table

This table defines what each robot does per phase based on alliance strategy:

```
Phase         | Hub Status | Scorer Behavior              | Defense Bot Behavior
──────────────|────────────|──────────────────────────────|──────────────────────
Auto (20s)    | Both ON    | Score pre-loaded fuel        | Score 0-1 fuel, maybe L1 climb
Transition    | --         | Drive to position            | Drive to position
Shift (own ON)| ACTIVE     | Dump stockpile + full cycles | Defend in opponent zone OR score
Shift (own OFF)| INACTIVE  | Stockpile + pre-position    | Defend in opponent zone
Endgame (30s) | Both ON    | Score remaining + climb      | Climb (L1)
```

### Strategy Presets

| Strategy Name              | Active Shift Plan                   | Inactive Shift Plan                     | Best For               |
|----------------------------|-------------------------------------|-----------------------------------------|------------------------|
| **Full Offense**           | All 3 robots score                  | All 3 stockpile + pre-position          | Strong scoring alliance |
| **2 Score + 1 Defend**     | 2 score, 1 crosses to defend        | 2 stockpile, 1 defends opponent scoring | Balanced alliance      |
| **1 Score + 2 Defend**     | 1 scores, 2 cross to defend         | 1 stockpiles, 2 defend                  | Weak scoring, strong defense |
| **Deny & Score**           | All 3 score                         | 2 stockpile, 1 camps Neutral Zone       | Fuel-starving opponent |
| **Surge**                  | All 3 dump stockpile + cycle        | All 3 stockpile at Outpost (HP feed)    | Maximize burst scoring |

### Stockpile Burst Dynamics

The **Surge** strategy exploits the shift structure:

```
Inactive Shift (25s):
  - 3 robots each fill to capacity at Outpost (HP feeds them)
  - Elite(8) + Strong(6) + Mid(4) = 18 fuel stockpiled
  - All 3 pre-position near Hub

Active Shift starts (t=0):
  - All 3 dump simultaneously: 18 fuel scored in ~3-5 seconds
  - Then resume normal cycling for remaining ~20s
  - Total: 18 (burst) + ~15-25 (cycling) = 33-43 fuel in one 25s window
```

This creates a **huge burst** at shift boundaries but also temporarily depletes the fuel pool (18 fuel go through Hub transit at once, ~2.5s before they recycle back).

### Shift-Transition Timing

Critical detail: robots should begin **driving toward their Hub** ~3-5 seconds before the shift changes to their active window. This "pre-positioning" time is part of the strategy model.

| Pre-position Timing | Drive Distance        | Time Needed  |
|---------------------|-----------------------|-------------|
| From Neutral Zone   | Mid-field to Hub      | 2-3s        |
| From Outpost        | Side-field to Hub     | 2-4s        |
| From Opponent Zone  | Cross-field to Hub    | 4-6s        |
| Already at Hub      | None                  | 0s          |

Robots that are defending in the opponent zone during an inactive shift **sacrifice 4-6s** of their next active shift driving back -- this is a real tradeoff the strategy engine must model.

### Defense Timing Tradeoffs

| Decision                                | Benefit                        | Cost                                    |
|-----------------------------------------|--------------------------------|-----------------------------------------|
| Defend during opponent's active shift   | Reduce their scoring by 30-60% | Your robot not stockpiling              |
| Defend during YOUR active shift         | Continue reducing opponent     | You lose a scorer for 25s               |
| Switch from defense to offense at shift | Maximize your active-shift scoring | 4-6s lost driving back from opponent zone |
| Never defend                            | All 3 robots always scoring/stockpiling | Opponent scores freely            |

### Robot Action State Machine (Phase-Aware)

```
                    ┌──────────────────────────────────────────┐
                    │           SHIFT CHANGE EVENT             │
                    └──────────┬───────────────┬───────────────┘
                               │               │
                    ┌──────────▼──────┐ ┌──────▼──────────────┐
                    │  My Hub ACTIVE   │ │  My Hub INACTIVE     │
                    └──────────┬──────┘ └──────┬──────────────┘
                               │               │
              ┌────────────────┼────────┐      ├──────────────────┐
              │                │        │      │                  │
        ┌─────▼─────┐  ┌──────▼──┐ ┌───▼───┐ ┌▼──────────┐ ┌────▼──────┐
        │ Dump       │  │ Full    │ │ Score │ │ Stockpile │ │ Cross-    │
        │ Stockpile  │  │ Cycle   │ │ + Def │ │ + Pre-pos │ │ field Def │
        │ (if loaded)│  │         │ │(rare) │ │           │ │           │
        └─────┬──────┘  └────┬────┘ └───┬───┘ └─────┬─────┘ └─────┬─────┘
              │              │          │            │              │
              └──────────────┴──────────┴────────────┴──────────────┘
                                        │
                              ┌─────────▼─────────┐
                              │   ENDGAME (30s)    │
                              │ Score + Climb      │
                              └───────────────────┘
```

---

## 11. Simulation Architecture

### Agent Responsibilities

The simulation is divided into modules that can be developed by independent agents:

```
Agent 1: Match Engine
    - Match timer and phase management
    - Hub activation state machine
    - Score tracking and RP calculation
    - Final results output

Agent 2: Robot Behavior Engine
    - Robot archetype instantiation
    - Phase-aware behavior: switch role on shift change events
    - Scoring cycle simulation (intake -> drive -> score)
    - Stockpile cycle simulation (intake -> hold -> pre-position)
    - Dump stockpile at shift boundary (burst scoring)
    - Autonomous routine execution
    - Climb decision and execution
    - Defense behavior (cross-field movement, disruption)
    - Drive-back time penalty when switching from defense to scoring

Agent 3: Field State Manager
    - Fuel pool accounting (conservation invariant)
    - Fuel state tracking (on_field / in_robot / in_flight / in_transit / at_outpost)
    - Transit queue: schedule fuel return to field after Hub fall-through delay
    - Fuel starvation detection (robots waiting for unavailable fuel)
    - Robot positions (simplified grid/zones)
    - Collision/congestion modeling
    - Tower occupancy tracking

Agent 4: Strategy & Alliance Manager
    - Alliance composition (assign archetypes)
    - Strategy preset selection (full_offense, 2_score_1_defend, surge, etc.)
    - Per-robot role assignment per shift (scorer / stockpiler / defender)
    - Shift-transition planning (pre-positioning, drive-back cost)
    - Human player strategy (feed during inactive shift, throw during active)
    - Endgame climb order optimization
    - Counter-strategy selection based on opponent alliance composition

Agent 5: Statistics & Output
    - Monte Carlo simulation runner (N matches)
    - Win probability calculation
    - RP distribution analysis
    - Alliance comparison reports
    - CSV/JSON output
```

### Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Alliance Mgr   │────>│   Match Engine    │<───>│  Field State    │
│  (Agent 4)      │     │   (Agent 1)       │     │  (Agent 3)      │
└─────────────────┘     └────────┬──────────┘     └─────────────────┘
                                 │
                        ┌────────▼──────────┐
                        │  Robot Behavior   │
                        │  (Agent 2)        │
                        └────────┬──────────┘
                                 │
                        ┌────────▼──────────┐
                        │  Stats & Output   │
                        │  (Agent 5)        │
                        └───────────────────┘
```

### Interfaces Between Agents

#### MatchState (Agent 1 -> All)
```python
class MatchState:
    time_remaining: float        # seconds remaining
    current_phase: str           # "auto"|"transition"|"shift1"|"shift2"|"shift3"|"shift4"|"endgame"
    red_hub_active: bool
    blue_hub_active: bool
    red_score: int
    blue_score: int
    red_fuel_scored: int         # count for RP tracking
    blue_fuel_scored: int
    red_tower_points: int
    blue_tower_points: int
    red_penalties: int           # points awarded to blue from red fouls
    blue_penalties: int
```

#### RobotState (Agent 2 -> Agent 1, Agent 3)
```python
class RobotState:
    id: str                      # e.g. "red_1", "blue_3"
    alliance: str                # "red" | "blue"
    archetype: str               # archetype name (may change mid-match on failure)
    position: str                # zone: "alliance"|"midfield"|"neutral"|"hub"|"tower"|"outpost"|"opponent_zone"|"trench"
    fuel_held: int               # current fuel in robot
    fuel_capacity: int           # max fuel
    is_stockpiling: bool         # holding fuel, waiting for active shift
    is_climbing: bool
    climb_level: int             # 0=none, 1/2/3
    is_defending: bool
    is_pushing_fuel: bool        # bulldozing fuel toward alliance zone
    fuel_being_pushed: int       # how many fuel balls being pushed (not in robot)
    current_action: str          # "idle"|"intaking"|"driving"|"shooting"|"climbing"|"defending"|"stockpiling"|"pre_positioning"|"dumping"|"pushing_fuel"|"clearing_jam"
    action_timer: float          # seconds until current action completes
    shift_role: str              # current role: "scorer"|"stockpiler"|"defender"|"pusher" (changes per shift)
    intake_status: str           # "nominal"|"degraded"|"broken" (can change mid-match)
    shooter_status: str          # "nominal"|"degraded"|"broken"
    fouls_drawn_this_match: int  # affects penalty escalation
```

#### FieldState (Agent 3 -> Agent 2)
```python
class FieldState:
    neutral_fuel_available: int
    red_outpost_fuel: int
    blue_outpost_fuel: int
    fuel_in_flight: int          # fuel currently airborne (shot but not yet in Hub)
    fuel_in_transit: int         # fuel falling through Hub back to Neutral Zone
    transit_queue: list          # list of (tick_available, count) for fuel returning to field
    red_tower_occupants: list    # robot IDs on tower
    blue_tower_occupants: list
    congestion_red_hub: float    # 0.0-1.0, affects cycle time
    congestion_blue_hub: float

    def total_fuel_check(self, robots: list) -> int:
        """Conservation invariant -- must always equal TOTAL_FUEL."""
        fuel_in_robots = sum(r.fuel_held for r in robots)
        return (self.neutral_fuel_available + self.red_outpost_fuel +
                self.blue_outpost_fuel + self.fuel_in_flight +
                self.fuel_in_transit + fuel_in_robots)
```

#### AllianceConfig (Agent 4 -> Agent 1, Agent 2)
```python
class AllianceConfig:
    robots: list                 # 3 RobotConfig objects
    strategy_preset: str         # "full_offense"|"2_score_1_defend"|"1_score_2_defend"|"deny_and_score"|"surge"
    human_player_mode: str       # "feed"|"throw"|"mixed"
    endgame_plan: list           # climb targets per robot, e.g. [3, 2, 1]

class RobotConfig:
    archetype: str               # "elite_turret"|"elite_multishot"|"strong"|"everybot"|"kitbot_plus"|"kitbot_base"|"defense"
    # Drivetrain
    drivetrain: str              # "swerve"|"tank"|"mecanum"
    swerve_module: str           # "sds_mk4i"|"sds_mk4n"|"sds_mk5n"|"wcp_x2"|"wcp_x2s"|"rev_max"|"none"
    gear_ratio: str              # "L1"|"L2"|"L3" (or X1/X2/X3 for WCP)
    free_speed_fps: float        # feet per second free speed
    can_fit_trench: bool         # robot height allows trench passage
    # Shooter
    shooter_type: str            # "single_turret"|"double_fixed"|"triple_fixed"|"single_fixed"|"dumper"|"none"
    shooter_angle: str           # "fixed_low"|"fixed_high"|"adjustable"|"full_variable"
    hopper_type: str             # "large"|"medium"|"small"|"serializer"|"spindexer"
    fuel_capacity: int           # max fuel held at once
    effective_range: float       # max shooting distance from Hub in feet
    can_shoot_while_moving: bool # True only for turret robots with vision
    # Intake
    intake_type: str             # "over_bumper"|"under_bumper"|"funnel"|"none"
    intake_quality: str          # "touch_and_go"|"slow_pickup"|"push_around"|"no_ground_pickup"
    intake_robustness: str       # "high"|"medium"|"low" -- affects mid-match failure probability
    # Strategy
    auto_fuel_target: int        # fuel to score in auto
    auto_climb: bool             # attempt L1 climb in auto?
    climb_target: int            # 0/1/2/3 for endgame
    active_shift_role: str       # "score"|"defend"|"score_and_defend"
    inactive_shift_role: str     # "stockpile"|"defend"|"deny_neutral"|"push_fuel"
    defense_target: str          # which opponent robot to defend (if defending)
    preposition_before_shift: bool  # drive to Hub before active shift starts?

class RobotRuntimeState:
    """Tracks mid-match degradation and failures."""
    intake_status: str           # "nominal"|"degraded"|"broken"
    shooter_status: str          # "nominal"|"degraded"|"broken"
    turret_status: str           # "nominal"|"stuck" (turret bots only)
    current_archetype_override: str  # if intake breaks, robot may downgrade to "defense" or "hp_fed_scorer"
    fouls_drawn: int             # affects penalty escalation probability
    fuel_pushed_to_zone: int     # fuel pushed (not intaked) to alliance zone this match

class PhaseAction:
    """What a robot is doing at any given moment, driven by shift state."""
    phase: str                   # current match phase
    hub_active: bool             # is this robot's Hub active?
    action: str                  # "scoring_cycle"|"stockpile_cycle"|"defending"|"pre_positioning"|"climbing"|"dump_stockpile"|"pushing_fuel"|"hp_fed_scoring"
    fuel_held: int               # fuel currently held (for stockpile tracking)
    position: str                # current zone
    time_in_action: float        # seconds spent on current action
```

#### SimulationResult (Agent 5 output)
```python
class SimulationResult:
    red_total_score: int
    blue_total_score: int
    red_rp: int
    blue_rp: int
    winner: str                  # "red"|"blue"|"tie"
    red_fuel_scored: int
    blue_fuel_scored: int
    red_tower_points: int
    blue_tower_points: int
    red_penalties_drawn: int
    blue_penalties_drawn: int
    red_energized: bool
    red_supercharged: bool
    red_traversal: bool
    blue_energized: bool
    blue_supercharged: bool
    blue_traversal: bool
    phase_scores: dict           # per-phase breakdown
```

---

## 12. Simulation Parameters

### Time Resolution
- Simulation tick: **0.5 seconds** (320 ticks per match)
- All durations rounded to nearest tick

### Randomness
- Use seeded RNG for reproducibility
- Each robot action uses archetype-based probability distributions
- Shot accuracy: Bernoulli trial per fuel with archetype accuracy rate
- Climb success: single Bernoulli trial at climb attempt
- Cycle time: Normal distribution around archetype mean (stddev = 15% of mean)
- Defense penalties: Bernoulli per shift

### Match Count
- Default: **1000 matches** per simulation run for Monte Carlo analysis
- Configurable via CLI argument

---

## 13. Example Simulation Scenario

### Alliance Compositions

**Red Alliance:**
| Robot | Archetype        | Shooter         | Capacity | Range   | Auto Plan    | Endgame |
|-------|------------------|-----------------|----------|---------|--------------|---------|
| Red 1 | Elite Turret     | Single Turret + Adj Hood | 7 | 4-20 ft | 6 fuel + L1 | L3      |
| Red 2 | Elite Multi-Shot | Triple Fixed    | 10       | 4-12 ft | 4 fuel       | L2      |
| Red 3 | Defense Bot      | None            | 0        | N/A     | 1 fuel       | L1      |

**Blue Alliance:**
| Robot  | Archetype     | Shooter         | Capacity | Range   | Auto Plan    | Endgame |
|--------|---------------|-----------------|----------|---------|--------------|---------|
| Blue 1 | Strong Scorer | Double Fixed    | 6        | 4-10 ft | 4 fuel       | L3      |
| Blue 2 | Everybot      | Single Fixed    | 6        | 3-8 ft  | 2 fuel       | L2      |
| Blue 3 | KitBot+       | Single Fixed (low) | 12    | 2-6 ft  | 1 fuel       | L1      |

### Strategy Assignments

**Red Alliance: "2 Score + 1 Defend" preset**
| Robot | Active Shift Role | Inactive Shift Role | Shooter Advantage                          |
|-------|-------------------|---------------------|--------------------------------------------|
| Red 1 | Score (shoot-on-move, no align needed) | Stockpile 7 + pre-position | Turret tracks Hub while driving. Dumps at ~4 fuel/s |
| Red 2 | Score (must align, burst dump) | Stockpile 10 + pre-position | Triple fixed dumps 10 fuel in ~1.1s at shift start |
| Red 3 | Cross-field defense | Cross-field defense | Disrupts Blue 1; L1 endgame only |

**Blue Alliance: "Full Offense" preset**
| Robot  | Active Shift Role | Inactive Shift Role | Shooter Advantage                          |
|--------|-------------------|---------------------|--------------------------------------------|
| Blue 1 | Score (must align, decent burst) | Stockpile 6 + pre-position | Double fixed dumps 6 fuel in ~1s |
| Blue 2 | Score (must align, moderate)     | Stockpile at Outpost (HP feed) | Single fixed, 3 fuel/s, reliable |
| Blue 3 | Score (close range, slow)        | Stockpile at Outpost (HP feed) | KitBot+ must drive to Hub, 2 fuel/s |

### Phase-by-Phase Score Estimation (Single Match)

**Assume Red wins Auto** (10 fuel vs 6 fuel) -> Red Hub inactive Shifts 1 & 3, active Shifts 2 & 4.

**Red Alliance:**
| Phase     | Hub  | Red 1 (Elite Turret)     | Red 2 (Triple Fixed)    | Red 3 (Defense)    | Fuel Scored | Points |
|-----------|------|--------------------------|-------------------------|--------------------|-------------|--------|
| Auto      | ON   | Score 6 (shoot-on-move)  | Score 4 (align + dump)  | Score 1            | 11          | 11     |
| Auto      | --   | --                       | --                      | L1 climb (15pts)   | --          | 15     |
| Shift 1   | OFF  | Stockpile 7 from NZ      | Stockpile 10 at Outpost | Defend Blue 1      | 0           | 0      |
| Shift 2   | ON   | Dump 7 (1.8s) + cycle: ~12 more | Dump 10 (1.1s!) + cycle: ~8 more | Defend Blue | ~37 | 37  |
| Shift 3   | OFF  | Stockpile 7              | Stockpile 10            | Defend Blue 1      | 0           | 0      |
| Shift 4   | ON   | Dump 7 + cycle: ~12      | Dump 10 + cycle: ~8     | Defend Blue        | ~37         | 37     |
| Endgame   | ON   | Score ~8 + L3 climb      | Score ~5 + L2 climb     | L1 climb           | ~13         | 13     |
| Tower     | --   | L3 = 30                  | L2 = 20                 | L1(auto)=15,L1=10  | --          | 75     |
| **Total** |      |                          |                         |                    | **~98**     |**~188**|

- Red 2's triple shooter is the star: dumps 10 fuel in 1.1 seconds at each shift boundary
- Red 1's turret enables shoot-on-the-move, eliminating alignment time = more cycles
- Energized RP: Almost (98 ~ 100) -- turret + triple burst just barely hits it
- Traversal RP: Yes (75 >= 50)

**Blue Alliance (impacted by Red 3 defense on Blue 1):**
| Phase     | Hub  | Blue 1 (Strong, defended!) | Blue 2 (Everybot)  | Blue 3 (KitBot+)        | Fuel Scored | Points |
|-----------|------|----------------------------|--------------------|-----------------------------|-------------|--------|
| Auto      | ON   | Score 3 (def disrupts align)| Score 2           | Score 1 (slow, close range) | ~6          | 6      |
| Shift 1   | ON   | Cycle ~6 (def: -35%, needs align) | Cycle ~5    | Cycle ~3 (must drive to Hub)| ~14         | 14     |
| Shift 2   | OFF  | Try to stockpile (defended)| Stockpile 6 at Outpost | Stockpile 12 at Outpost | 0           | 0      |
| Shift 3   | ON   | Dump ~3 + cycle ~4 (def)  | Dump 6 + cycle ~4  | Dump 12 (hopper jam risk 8%) + cycle ~2 | ~21 (+jam?) | 21 |
| Shift 4   | OFF  | Stockpile (defended)      | Stockpile 6        | Stockpile 12               | 0           | 0      |
| Endgame   | ON   | Score ~3 + L3 attempt     | Score ~3 + L2      | Score ~2 + L1              | ~8          | 8      |
| Tower     | --   | L3=30 (55% success)       | L2=20 (70%)        | L1=10 (80%)                | --          | ~44    |
| **Total** |      |                           |                    |                            | **~49**     |**~93** |

- Blue 3's KitBot+ holds 12 fuel but cycles slowly (must drive to Hub every time, 2 fuel/s, 25-28s cycles)
- Blue 3's large hopper has 8% jam risk per dump -- a jam at shift start wastes ~3.5s of the 25s window
- Blue 1's double fixed shooter needs 1.5s align time each shot, AND Red defense adds +50% cycle time
- Energized RP: No (49 << 100)
- Traversal RP: No (~44 < 50, and Blue 1 L3 only 55%)

**Key mechanical insights from this example:**
- **Turret vs Fixed:** Red 1's turret saves ~1.5s per cycle (no alignment) = 2-3 extra cycles per 25s shift
- **Triple burst:** Red 2 dumps 10 fuel in 1.1s vs Blue 1's 6 fuel in 1.0s -- raw throughput advantage at shift boundaries
- **KitBot capacity trap:** Blue 3 holds 12 fuel but cycles at 25-28s -- high capacity is wasted when cycle time is slow. The fuel sits in the hopper instead of scoring.
- **Jam risk:** Blue 3's large open-top hopper has 8% jam rate. Over 4 dump events per match, that's ~28% chance of at least one jam costing 3.5s
- **Defense on fixed-shooter is more effective** than defense on turret: fixed shooters need alignment time, so disrupting alignment is devastating. Turret robots can shoot while being bumped.

**Key insights from this example:**
- Red's defense bot on Blue 1 reduces Blue's best scorer by ~35%, worth ~20-30 points denied
- Stockpile-and-dump at shift boundaries creates concentrated burst scoring
- Having only 50s of active Hub (2 x 25s shifts) severely limits fuel count vs. the 100 fuel Energized threshold
- Endgame (30s, both active) is critical -- both alliances need these seconds for fuel AND climbing
- Fuel recycling limits burst potential: dumping 14 fuel at once means ~2.5s before those balls are available again

---

## 14. Implementation Guide

### Recommended Tech Stack
- **Language:** Python 3.10+
- **Libraries:** `dataclasses`, `random`, `statistics`, `json`, `csv`
- **Optional:** `matplotlib` for visualization, `numpy` for distributions

### File Structure
```
FRC_project/
├── FRC simulation.md          # This specification
├── src/
│   ├── __init__.py
│   ├── match_engine.py        # Agent 1: Match timer, scoring, phases
│   ├── robot.py               # Agent 2: Robot behavior, cycles, climbing
│   ├── field.py               # Agent 3: Field state, fuel tracking
│   ├── strategy.py            # Agent 4: Alliance config, phase-aware strategy, role assignment
│   ├── stats.py               # Agent 5: Monte Carlo runner, output
│   ├── models.py              # Shared data classes (MatchState, RobotState, etc.)
│   └── config.py              # Constants (points, timings, thresholds)
├── tests/
│   ├── test_match_engine.py
│   ├── test_robot.py
│   ├── test_field.py
│   ├── test_strategy.py
│   └── test_stats.py
├── output/
│   └── (simulation results go here)
└── main.py                    # Entry point
```

### Build Order (Agent Dependencies)

1. **`models.py`** + **`config.py`** -- no dependencies, build first
2. **`field.py`** -- depends on models
3. **`robot.py`** -- depends on models, config
4. **`match_engine.py`** -- depends on models, robot, field
5. **`strategy.py`** -- depends on models, config
6. **`stats.py`** -- depends on match_engine, strategy
7. **`main.py`** -- ties everything together

### Running the Simulation

```bash
# Single match
python main.py --matches 1 --seed 42

# Monte Carlo (1000 matches)
python main.py --matches 1000 --seed 42 --output output/results.json

# Custom alliances
python main.py --red "elite,strong,defense" --blue "strong,mid,mid" --matches 500
```

---

## 15. Key Constants Reference

```python
# Match timing (seconds)
AUTO_DURATION = 20
TRANSITION_DURATION = 10
SHIFT_DURATION = 25
ENDGAME_DURATION = 30
TOTAL_MATCH_DURATION = 160
TICK_INTERVAL = 0.5

# Scoring
FUEL_ACTIVE_HUB_POINTS = 1
FUEL_INACTIVE_HUB_POINTS = 0
TOWER_L1_AUTO_POINTS = 15
TOWER_L1_TELEOP_POINTS = 10
TOWER_L2_POINTS = 20
TOWER_L3_POINTS = 30
FOUL_POINTS = 5
TECH_FOUL_POINTS = 12

# Ranking Points
RP_WIN = 3
RP_TIE = 1
RP_ENERGIZED_THRESHOLD = 100    # fuel points
RP_SUPERCHARGED_THRESHOLD = 360 # fuel points
RP_TRAVERSAL_THRESHOLD = 50     # tower points

# Human Player
HP_THROW_INTERVAL = 4.0         # seconds between throws
HP_FEED_INTERVAL = 2.5          # seconds between feeds
HP_THROW_ACCURACY = 0.55        # 55% base

# Field
INITIAL_NEUTRAL_FUEL = 20
INITIAL_OUTPOST_FUEL = 10       # per alliance
INITIAL_PRELOAD_FUEL = 10       # per alliance (split across 3 robots)
TOTAL_FUEL = 60                 # conserved quantity -- never changes

# Fuel Physics (closed-loop recycling)
FUEL_FLIGHT_TIME = 1.0          # seconds: shot leaves robot -> enters Hub
FUEL_HUB_TRANSIT_TIME = 1.5     # seconds: Hub fall-through -> available on field
FUEL_TOTAL_RECYCLE_TIME = 2.5   # FLIGHT + TRANSIT = time a scored ball is unavailable
FUEL_MISS_RECOVERY_TIME = 3.0   # seconds: missed shot -> ball settles on field
HP_THROW_FLIGHT_TIME = 1.5      # seconds: HP throw -> enters Hub

# Robot limits
MAX_TOWER_OCCUPANTS = 3         # per alliance tower

# Shooter parameters
TURRET_ALIGN_TIME = 0.0         # turret tracks automatically
FIXED_ALIGN_TIME = 1.5          # seconds to rotate robot to face Hub
DUMPER_ALIGN_TIME = 0.0         # must already be at Hub
SHOOT_RATE_SINGLE = 3.0         # fuel per second (single barrel)
SHOOT_RATE_DOUBLE = 6.5         # fuel per second (double barrel)
SHOOT_RATE_TRIPLE = 9.0         # fuel per second (triple barrel)
SHOOT_RATE_DUMPER = 15.0        # fuel per second (all at once, gravity dump)

# Hopper parameters
JAM_RATE_LARGE_HOPPER = 0.075   # 7.5% per dump cycle
JAM_RATE_SERIALIZER = 0.005     # 0.5% per dump cycle
JAM_CLEAR_TIME = 3.5            # seconds to clear a jam

# Reliability - mechanism failures
TURRET_FAILURE_RATE = 0.12      # 12% per match
MULTISHOT_FAILURE_RATE = 0.12   # 12% per match (one barrel)
BASIC_FAILURE_RATE = 0.04       # 4% per match

# Intake failure & degradation
INTAKE_BREAK_RATE_COMPLEX = 0.06      # 6% per match (under-bumper, exposed)
INTAKE_BREAK_RATE_SIMPLE = 0.02       # 2% per match (over-bumper, protected)
INTAKE_DEGRADE_RATE_COMPLEX = 0.15    # 15% per match
INTAKE_DEGRADE_RATE_SIMPLE = 0.07     # 7% per match
INTAKE_JAM_RATE = 0.10                # 10% per match
INTAKE_JAM_CLEAR_TIME = 3.0           # seconds to reverse and clear jam
DEGRADED_INTAKE_SPEED_MULT = 0.5      # 50% of normal intake speed
DEGRADED_INTAKE_SUCCESS_RATE = 0.60   # 60% chance of picking up fuel per attempt (vs 95%+ nominal)

# Fuel pushing mechanics
PUSH_SPEED_FPS = 6.0                  # feet/second while pushing fuel cluster
PUSH_FUEL_PER_TRIP = 5                # average fuel pushed per trip
PUSH_SCATTER_RATE = 0.20              # 20% of pushed fuel scatters away
PUSH_TRIP_TIME = 7.0                  # seconds per push trip (push + return)
TRENCH_PUSH_TIME = 4.0               # seconds to push fuel through trench

# Defense penalty rates by zone
FOUL_RATE_NEUTRAL_ZONE = 0.08        # 8% per shift
FOUL_RATE_OPPONENT_ALLIANCE = 0.20   # 20% per shift (higher scrutiny)
FOUL_RATE_NEAR_TOWER = 0.25          # 25% per shift
TECH_FOUL_RATE_NEUTRAL = 0.015       # 1.5% per shift
TECH_FOUL_RATE_ALLIANCE = 0.06       # 6% per shift
TECH_FOUL_RATE_TOWER = 0.10          # 10% per shift
PENALTY_ESCALATION_MULT = [1.0, 1.5, 2.0]  # indexed by fouls_drawn

# Defense impact on shooter types
DEFENSE_CYCLE_HIT_TURRET = 0.35      # +35% cycle time
DEFENSE_CYCLE_HIT_FIXED = 0.50       # +50% cycle time
DEFENSE_ACCURACY_HIT_TURRET = 0.08   # -8% accuracy
DEFENSE_ACCURACY_HIT_FIXED = 0.20    # -20% accuracy

# Phase-aware strategy timing
PREPOSITION_TIME_FROM_NEUTRAL = 2.5   # seconds to drive from Neutral Zone to own Hub
PREPOSITION_TIME_FROM_OUTPOST = 3.0   # seconds to drive from Outpost to own Hub
CROSSFIELD_DRIVE_TIME = 5.0           # seconds to drive from opponent zone to own Hub
DUMP_TIME_PER_FUEL = 0.3              # seconds per fuel when dumping stockpile (rapid fire)
SHIFT_ANTICIPATION_TIME = 3.0         # seconds before shift change to start pre-positioning

# Drivetrain speeds (practical, not free speed)
SWERVE_PRACTICAL_SPEED_FPS = 13.0    # typical L2 swerve
TANK_PRACTICAL_SPEED_FPS = 10.0      # typical AM14U tank
SWERVE_ALIGN_TIME = 0.0              # can strafe, no rotation needed
TANK_ALIGN_TIME = 1.5                # must rotate to face Hub
```

---

## 16. Validation Criteria

A correct simulation should satisfy these sanity checks:

1. **Score range:** Typical match scores between 40-200 points per alliance.
2. **Elite alliance ceiling:** An all-elite alliance should average 150-200+ points.
3. **Low alliance floor:** An all-low alliance should average 20-50 points.
4. **Energized RP:** Achievable by strong+ alliances (~60-80% of matches).
5. **Supercharged RP:** Rare, only elite alliances (~5-20% of matches).
6. **Traversal RP:** Achievable when 2+ robots climb L2+ (~40-70% for strong alliances).
7. **Defense impact:** Defense bot should reduce opponent scoring by 15-30%.
8. **Hub timing matters:** Alliance with inactive hub during high-fuel shifts scores fewer fuel points.
9. **No negative scores:** Penalties only add to opponent, never subtract.
10. **Tower constraint:** Each robot earns at most 1 tower level in teleop.
11. **Fuel conservation:** `total_fuel_check()` must equal `TOTAL_FUEL` (60) at every tick. If not, there is a bug.
12. **Fuel starvation:** When 3+ elite robots all shoot rapidly, fuel starvation events should occur (~5-15% of ticks during peak scoring windows).
13. **Recycle delay:** A single fuel ball cannot be scored more than once per ~2.5s. An alliance's max theoretical throughput is ~60 fuel / 2.5s = 24 fuel per second (impossible in practice due to intake/drive time).
14. **Intake failures happen:** Over 1000 matches, ~5-15% of robots should experience intake degradation or breakage mid-match. Broken-intake robots should either switch to defense, HP-fed scoring, or fuel pushing.
15. **Defense on fixed > defense on turret:** Defense against fixed-shooter robots should reduce their scoring by 35-50%, while defense against turret robots should only reduce scoring by 20-35%.
16. **Alliance zone defense draws more fouls:** Robots defending in opponent alliance zone should draw fouls at ~2-3x the rate of neutral zone defense.
17. **Fuel pushing contributes:** In matches with a dedicated pusher, ~10-15 fuel per inactive shift should be repositioned to the alliance zone, providing a stockpile for teammates.
18. **Swerve vs tank cycle time:** Swerve-drive robots should cycle ~20-30% faster than tank-drive robots of the same archetype, due to strafing (no alignment) and faster field traversal.
19. **KitBot capacity trap:** KitBot robots holding 12-15 fuel should NOT outscore Everybot robots holding 6-8 fuel, because KitBot's slower cycle time means fuel sits idle in the hopper. Score = fuel_scored, not fuel_held.

---

## Sources

- [FIRST Robotics Competition - REBUILT Game & Season](https://www.firstinspires.org/programs/frc/game-and-season)
- [2026 Game Manual (PDF)](https://firstfrc.blob.core.windows.net/frc2026/Manual/2026GameManual.pdf)
- [FRC REBUILT Points Calculator](https://dunkirk.sh/blog/frc-rebuilt-calculator/)
- [Talon Robotics Game Breakdown](https://team2502.com/game-breakdown/)
- [FRC 2026 Simulator](https://www.frc2026sim.com/)
- [Rebuilt Scoring Calculator](https://frc.ohlinis.me/)
- [2026 Robot Rules Preview](https://community.firstinspires.org/2025-robot-rules-preview-for-2026)
- [Chief Delphi - REBUILT Hubs Discussion](https://www.chiefdelphi.com/t/2026-rebuilt-hubs/510719)
- [FRC Strategy Repository](https://github.com/grevelle/frc-2026-strategy)
- [SDS MK4i Swerve Module](https://www.swervedrivespecialties.com/products/mk4i-swerve-module)
- [SDS MK4n Swerve Module](https://www.swervedrivespecialties.com/products/mk4n-swerve-module)
- [SDS MK5n Swerve Module](https://www.swervedrivespecialties.com/products/mk5n-swerve-module)
- [WCP Swerve Modules](https://docs.wcproducts.com/welcome/frc-build-system/gearboxes/swerve)
- [WCP CC 2026 "Big Dumper"](https://docs.wcproducts.com/welcome/competitive-concepts/wcp-cc-2026)
- [2026 Robonauts Everybot](https://www.chiefdelphi.com/t/the-2026-robonauts-frc-everybot-low-resource-build/510331)
- [2026 KitBot Fuel Capacity](https://www.chiefdelphi.com/t/2026-kitbot-fuel-capacity/510528)
- [2826 Wave Robotics Triple Turret Build Thread](https://www.chiefdelphi.com/t/frc-2826-wave-robotics-2026-open-alliance-build-thread/508460)
- [REV MAXSwerve Module](https://www.revrobotics.com/rev-21-3005/)

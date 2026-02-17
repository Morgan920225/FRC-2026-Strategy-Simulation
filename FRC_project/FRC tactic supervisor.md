# FRC Tactic Supervisor: 2026 REBUILT Strategy Analysis

**Season:** 2026 FIRST Robotics Competition  
**Game Name:** REBUILT (Presented by Haas)  
**Date:** February 16, 2026

---

## 1. Game Overview: REBUILT
The 2026 game, **REBUILT**, focuses on resource management, dynamic scoring cycles, and vertical mobility. Alliances compete to score **Fuel** (balls) into alternating **Hubs** and ascend a central **Tower**.

### Key Match Periods
- **Autonomous (20s):** Both Alliance Hubs are active. Robots can earn Level 1 Tower points.
- **Teleoperated (220s):** Includes a 30-second **Endgame**.
    - *Dynamic Hubs:* Only one Hub is active at a time during most of Teleop.
    - *Transition:* Hub activation is determined by Autonomous performance (the alliance scoring more fuel gets the first active cycle).

---

## 2. Scoring Table & Ranking Points (RP)
| Action | Points (Auto) | Points (Teleop) |
| :--- | :--- | :--- |
| **Fuel in Hub** | 6 pts | 3 pts |
| **Tower Level 1** | 10 pts | 10 pts |
| **Tower Level 2** | N/A | 20 pts |
| **Tower Level 3** | N/A | 30 pts |

### Ranking Points
1. **Match Result:** Win (2 RP), Tie (1 RP).
2. **Fuel Threshold RP:** Scoring a cumulative amount of Fuel (threshold varies by week/event).
3. **Tower RP:** Achieving a combined Tower score or specific number of Level 3 climbs.

---

## 3. Technical Constraints & Field Elements
- **Robot Dimensions:** Max 110" perimeter, **30" height cap** (rigid constraint).
- **Weight Limit:** 115 lbs.
- **Expansion:** Max 12" in one horizontal direction.
- **Field Features:**
    - **Hubs:** Hexagonal, 72" high, 41" wide opening.
    - **Trenches:** Low-clearance paths for robots under 24".
    - **Bumps:** Obstacles requiring robust drivetrains.
    - **AprilTags:** Extensive placement for high-fidelity odometry.

---

## 4. Tactical Deep Dive (FRC Tactic Supervisor Analysis)

### A. Hub Management & "Active Hub" Strategy
The alternating Hub mechanism is the core tactical challenge.
- **Reaction Time:** Alliances must monitor the pulsing lights on the Hub. Transitioning to defense or repositioning for the next cycle *before* the Hub deactivates is critical.
- **Cycle Timing:** "Wasteful" shooting into an inactive Hub can lose matches. Precision vision tracking (AprilTags) is mandatory.

### B. Fuel Logistics
- **Unlimited Capacity:** Unlike previous "5-ball" games, robots can hold many Fuel pieces.
- **Intake Speed:** Open Alliance teams (e.g., FRC 5951, 694) are prioritizing wide "over-the-bumper" intakes to vacuum Fuel quickly.
- **Magazine Design:** Spinning magazines or "active hoppers" are being used to prevent jamming of the high-volume Fuel pieces.

### C. Defense & Navigation
- **No Protected Zones:** This makes offensive cycles vulnerable to T-bone and pinning defense.
- **Agility:** Swerve drive is the standard for high-tier play to navigate around Bumps and Trenches while evading defenders.
- **Trench Utility:** Teams with low-profile robots can bypass field congestion via Trenches, though this limits intake height.

### D. The Tower Climb (Endgame)
- **Level 3 Priority:** The 30-point Level 3 climb is a game-changer.
- **Safety:** Protected zones apply only once a robot is *connected* to the Tower.
- **Buddy Climbing:** Prohibited this year; teams must be self-sufficient or use mechanical synchronization (rare).

---

## 5. Insights from Chief Delphi & Open Alliance
- **Chief Delphi Consensus:** The "Fuel Threshold" RP is harder than it looks due to Hub downtime. Teams are debating the "Pure Scorer" vs "Climb Specialist" archetypes.
- **Open Alliance Highlights:**
    - **FRC 5951:** Testing high-speed magazines to manage the "unlimited" Fuel capacity.
    - **FRC 694 (StuyPulse):** Focusing on a 4-wheel swerve with integrated intake to maintain a low 30" profile while maximizing floor intake area.
    - **FRC 525:** Prototypes show that "lobbing" fuel into the 72" Hub requires high-exit velocity to overcome defender interference.

---

## 6. Supervisor Recommendations
1. **Focus on Autonomous:** Winning the "First Active Hub" advantage in Teleop is a massive momentum swing.
2. **Vision Reliability:** Invest heavily in AprilTag alignment to ensure every Fuel piece scores during the limited "Active" windows.
3. **Endgame Speed:** A 5-second Level 3 climb allows for more Teleop scoring time, which is crucial given the 4-minute match duration.

*Document compiled by FRC Tactic Supervisor AI.*

# 🤖 FRC 2026 REBUILT: Dashboard & Match Simulator

![Status](https://img.shields.io/badge/Status-Beta-blue)
![Python](https://img.shields.io/badge/Python-3.10+-yellow)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red)

Welcome to the **FRC 2026 REBUILT Dashboard**. This is a powerful, data-driven tool designed for FRC teams to dominate the competition through advanced analytics and simulation.

Based on **The Blue Alliance (TBA)** API and inspired by modern competitive strategy, this dashboard combines live event data with a **Monte Carlo Match Simulator** to help you predict outcomes, optimize strategies, and make smarter alliance selections.

---

## 🌟 Key Features

### 1. 🏟️ Event Center
Your command center for real-time competition data.
- **Live Rankings**: OPR, DPR, CCWM, and RP breakdowns.
- **Match Schedule**: Up-to-the-minute scores and upcoming matches.
- **Team Quick-Look**: Instant scouting profiles with recent match history.
- **Alliance Bracket**: Track playoff progression.

### 2. 🎮 Monte Carlo Match Simulator
Go beyond simple averages. Simulate thousands of matches to predict win probabilities.
- **Archetype Modeling**: Define robots by their capabilities (e.g., "Elite Turret", "Defense Bot").
- **Closed-Loop Physics**: Models fuel recycling, Hub congestion, and transit delays.
- **Strategy Presets**: Test "Full Offense", "Surge", "Deny & Score", and more against specific opponents.

### 3. 🎯 Strategy Advisor
AI-powered recommendations for your next match.
- **Matchup Analysis**: Input your alliance and opponent to see win % and expected RP.
- **Optimal Strategy**: The system tests 25+ strategy combinations to recommend the best tactical approach.
- **"What If" Explorer**: Compare how different strategies might change the outcome.

### 4. 🤝 Alliance Picker
Dominate alliance selection with data-backed picks.
- **Candidate Ranking**: Automatically ranks available teams by their compatibility with your capiton.
- **Role Suggestions**: Identifies the best role (Primary Scorer, Defender, Support) for each partner.
- **Synergy checks**: Avoid picking incompatible robots.

### 5. 🎨 Customization & Accessibility
- **Dark Mode**: Fully supported, high-contrast UI for competition environments.
- **Custom Branding**: Add your team's logo for a personalized dashboard.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- A free [The Blue Alliance API Key](https://www.thebluealliance.com/account).

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-username/frc-2026-rebuilt.git
    cd frc-2026-rebuilt
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the app**:
    ```bash
    streamlit run ui.py
    ```

4.  **Configure API Key**:
    - Open the app in your browser.
    - Go to the **Sidebar** > **TBA API Configuration**.
    - Paste your API key to unlock live data features.

---

## 🔮 Future Roadmap

We are constantly improving the dashboard. Planned updates include:

-   **Enhanced Physics Engine**: More granular simulation of defense effects and field congestion.
-   **Mobile Optimization**: Better responsive design for scouting on tablets/phones.
-   **Scouting Integration**: Import custom scouting data (CSV/Excel) to refine archetype accuracy.
-   **Predictive Match Scheduling**: AI-based predictions for match timing and turnaround.

---

## 📄 Deployment

Want to host this online for your team? See our [GitHub Deployment Guide](GH_DEPLOYMENT.md) for step-by-step instructions on deploying to Streamlit Community Cloud.

---

*Inspired by The Blue Alliance and built for the FRC community.*

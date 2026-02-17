# FRC 2026 REBUILT — Project Fix Plan

> Agent-ready task list. Work through each phase in order.
> Each task has: what to do, which files to touch, acceptance criteria, and verification steps.

---

## Phase 1: TBA Client Module + API Key Setup

**Goal:** Create a reusable Blue Alliance API client that all other features depend on.

### Task 1.1 — Add `requests` dependency
- **File:** `requirements.txt`
- **Action:** Add `requests` to the dependency list.

### Task 1.2 — Create `src/tba_client.py`
- **File:** `[NEW] src/tba_client.py`
- **Action:** Build a TBA API v3 client class with the following methods:

```python
class TBAClient:
    BASE_URL = "https://www.thebluealliance.com/api/v3"

    def __init__(self, api_key: str): ...

    # Core endpoints
    def get_team(self, team_number: int) -> dict:             # GET /team/frc{num}
    def get_team_events(self, team_number: int, year: int) -> list:  # GET /team/frc{num}/events/{year}
    def get_event_teams(self, event_key: str) -> list:        # GET /event/{key}/teams
    def get_event_matches(self, event_key: str) -> list:      # GET /event/{key}/matches
    def get_event_oprs(self, event_key: str) -> dict:         # GET /event/{key}/oprs
    def get_event_rankings(self, event_key: str) -> dict:     # GET /event/{key}/rankings
    def get_event_alliances(self, event_key: str) -> list:    # GET /event/{key}/alliances
    def get_events_by_year(self, year: int) -> list:          # GET /events/{year}
    def get_team_matches_at_event(self, team_number: int, event_key: str) -> list:  # GET /team/frc{num}/event/{key}/matches
```

- **Requirements:**
  - All methods must set the `X-TBA-Auth-Key` header.
  - All methods must handle HTTP errors gracefully (return `None` or raise a descriptive `TBAError`).
  - Add a `@st.cache_data(ttl=300)` compatible caching wrapper (or standalone `functools.lru_cache`) so repeated calls don't hammer TBA.
  - Include docstrings with example return shapes.

### Task 1.3 — Create `src/tba_mapper.py`
- **File:** `[NEW] src/tba_mapper.py`
- **Action:** Build a module that maps real team TBA data to simulation archetypes.

```python
def map_team_to_archetype(opr: float, climb_data: dict = None) -> str:
    """
    Map a real team's OPR + climb stats to the closest archetype key.
    
    Heuristic tiers (adjust as needed):
      OPR >= 80  → "elite_turret"
      OPR >= 60  → "elite_multishot"
      OPR >= 45  → "strong_scorer"
      OPR >= 30  → "everybot"
      OPR >= 15  → "kitbot_plus"
      OPR < 15   → "kitbot_base"
    
    If climb_data shows no climb capability and OPR > 30, consider "defense_bot".
    
    Returns: archetype key string (e.g. "elite_turret")
    """
```

- Also include:
```python
def get_team_summary(tba_client, team_number: int, event_key: str) -> dict:
    """
    Fetch team info + OPR + ranking from TBA for a given event.
    Returns dict with keys: name, number, opr, ccwm, dpr, rank, record, archetype.
    """
```

### Task 1.4 — Add API key input to the sidebar
- **File:** `ui.py`
- **Action:** At the top of the sidebar (before Alliance Configuration), add:
  - `st.sidebar.text_input("TBA API Key", type="password", key="tba_api_key")`
  - Store in `st.session_state.tba_api_key`
  - Show a small success/error indicator after first API call
  - Link to https://www.thebluealliance.com/account for key signup

### Verification — Phase 1
1. `pip install -r requirements.txt` succeeds without errors.
2. Run `streamlit run ui.py` — app loads, API key field is visible in sidebar.
3. Manually enter a valid TBA API key → call `get_team(254)` in a test script → returns `{'team_number': 254, 'nickname': 'The Cheesy Poofs', ...}`.
4. Call `get_event_oprs("2024casj")` → returns OPR dict with team keys.
5. `map_team_to_archetype(opr=85.0)` returns `"elite_turret"`.
6. Write unit tests in `tests/test_tba_client.py` that mock HTTP responses using `unittest.mock.patch` on `requests.get` — no real API calls in tests.

---

## Phase 2: Event Center Tab (Replace Teams History)

**Goal:** Replace the fake-data "Teams History" tab with a real "Event Center" powered by TBA.

### Task 2.1 — Build 🏟️ Event Center tab
- **File:** `ui.py`
- **Action:** Replace `tab_history` content (lines 405-419) with:

1. **Event Selector:**
   - Year selector (`st.selectbox`, default current year)
   - Event dropdown (populated via `tba_client.get_events_by_year(year)`)
   - Filter events by week, district, or region (optional)

2. **Event Rankings Table:**
   - Fetch `get_event_rankings(event_key)` and `get_event_oprs(event_key)`
   - Show table columns: Rank, Team #, Team Name, Record (W-L-T), RP, OPR, DPR, CCWM
   - Sortable via `st.dataframe`
   - Color-code OPR column (high = green, low = red)

3. **Match Schedule:**
   - Fetch `get_event_matches(event_key)`
   - Show completed matches: Match #, Red 1/2/3, Blue 1/2/3, Red Score, Blue Score
   - Show upcoming matches where scores are null: highlight "Next" match
   - Sort by match time

4. **Alliance Bracket:**
   - Fetch `get_event_alliances(event_key)`
   - Show 8 alliance captains + picks in a visual bracket/table
   - Mark available teams (not yet picked) for Phase 4

5. **Team Quick-Look:**
   - Text input for team number
   - Show: Team name, OPR, rank, record, assigned archetype, recent match scores
   - Button: "Use this team in Simulator" → pre-fills sidebar

### Task 2.2 — Rename the tab
- **File:** `ui.py`
- **Action:** In the `st.tabs()` call (line 189), rename `"📁 Teams History"` to `"🏟️ Event Center"`.

### Task 2.3 — Graceful degradation (no API key)
- **File:** `ui.py`
- **Action:** If `st.session_state.tba_api_key` is empty, show a friendly message:
  > "Enter your TBA API key in the sidebar to view live event data. Get a free key at thebluealliance.com/account."

### Verification — Phase 2
1. Run `streamlit run ui.py` without API key → Event Center shows a clear help message.
2. Enter API key → select year 2024, event "2024casj" → rankings table loads with real team data.
3. Match schedule shows completed matches with real scores.
4. Click "Use this team in Simulator" → sidebar alliance dropdowns do not break.
5. Write integration tests in `tests/test_event_center.py` using mocked TBA responses.

---

## Phase 3: Strategy Advisor Tab

**Goal:** Surface `select_counter_strategy()` as an interactive tool. Merge static strategy content into this tab.

### Task 3.1 — Build 🎯 Strategy Advisor tab
- **File:** `ui.py`
- **Action:** Replace `tab_strat` content (lines 387-400) with:

1. **Match Setup Panel:**
   - "My Alliance" — 3× team number inputs (e.g., `st.number_input("My R1 Team #", value=7130)`)
   - "Opponent Alliance" — 3× team number inputs
   - Event selector (auto-inherited from Event Center if set)
   - Button: "Analyze Match"

2. **Auto-Archetype Assignment:**
   - When "Analyze Match" is clicked:
     - Fetch OPR for all 6 teams from TBA
     - Map each to closest archetype via `map_team_to_archetype()`
     - Show a card for each team: `Team 254 → Elite Turret (OPR: 87.3)`
     - Allow user to override archetype if their scouting says otherwise

3. **Strategy Recommendation:**
   - Call `select_counter_strategy(our_alliance, opponent_archetypes)`
   - Show recommended strategy with explanation from `STRATEGY_DETAILS` and `STRATEGY_TIPS`
   - Run a quick Monte Carlo sim (50 iterations) with recommended strategy
   - Show expected win probability and RP

4. **"What If" Explorer:**
   - Dropdown to manually select a different strategy for your alliance
   - Re-run sim on change → show updated win probability side-by-side
   - Compare current strategy vs 4 alternatives

5. **Strategy Reference (collapsed):**
   - Move the existing strategy expanders into a collapsed section at the bottom
   - Keep the "Hub Shift Meta" section as an educational callout

### Verification — Phase 3
1. Enter team numbers `254, 1678, 118` vs `971, 973, 5026` → archetypes are auto-assigned.
2. Strategy recommendation appears (e.g., "Full Offense").
3. Override one archetype → recommendation updates.
4. "What If" dropdown changes to "Surge" → new win probability appears.
5. Strategy reference expanders still work.

---

## Phase 4: Alliance Recommendation Engine

**Goal:** Help teams pick the best alliance partners during alliance selection.

### Task 4.1 — Add Alliance Picker section to Strategy Advisor tab
- **File:** `ui.py` (inside the Strategy Advisor tab, as a new section)
- **Action:**

1. **Setup:**
   - "Your Team #" input
   - "Already Picked" — multiselect of teams already in alliances (auto-populated from TBA alliance bracket)
   - Event key (inherited from Event Center)

2. **Candidate Ranking:**
   - For each available team:
     - Map to archetype via OPR
     - Simulate a 3-team alliance: [your team, candidate, best remaining]
     - Record expected RP and win %
   - Sort candidates by expected RP (descending)

3. **Output Table:**
   - Columns: Rank, Team #, Name, Mapped Archetype, OPR, Expected RP, Win %, Suggested Role
   - Top 5 highlighted in green
   - "Simulate with this pick" button → runs full sim and shows results in the simulator tab

4. **Role Balance Warning:**
   - If all top candidates map to the same archetype, show a warning:
     > "⚠️ Top candidates are all scorers. Consider picking a defender for strategic flexibility."

### Verification — Phase 4
1. Select event → enter your team number → candidate list populates.
2. Top candidates have highest expected RP.
3. "Simulate with this pick" runs and displays results.
4. Role balance warning appears when appropriate.

---

## Phase 5: UX Polish & Tab Restructure

**Goal:** Clean up the UI, remove dead tabs, improve usability.

### Task 5.1 — Restructure tabs
- **File:** `ui.py`
- **Action:** Change the 7-tab layout to 5 tabs:

```python
tab_event, tab_sim, tab_strat, tab_arch, tab_rules = st.tabs([
    "🏟️ Event Center",
    "📊 Match Simulator",
    "🎯 Strategy Advisor",
    "🤖 Robot Database",
    "📜 Rules & About",
])
```

### Task 5.2 — Merge Settings into sidebar
- **File:** `ui.py`
- **Action:**
  - Move theme selector to the bottom of the sidebar: `st.sidebar.radio("Theme", [...], key="theme")`
  - Remove the dedicated Settings tab
  - Remove disabled checkboxes (or implement them)

### Task 5.3 — Merge Simulation Workflow into "Rules & About"
- **File:** `ui.py`
- **Action:**
  - Move the architecture Graphviz diagram into `tab_rules` under an expander: `with st.expander("How the Simulator Works"):`
  - Remove the dedicated Simulation Workflow tab

### Task 5.4 — Sidebar simplification
- **File:** `ui.py`
- **Action:**
  - Default to Quick Mode (already done, just confirm)
  - Add "🎲 Randomize" button to sidebar that shuffles archetype selections
  - Use `st.sidebar.expander("Advanced: Custom Subsystems")` instead of the radio toggle

### Task 5.5 — Results interpretation
- **File:** `ui.py`
- **Action:** After simulation results display, add a plain-English summary panel:
  - Generate a text summary from the stats dict
  - Include: dominant alliance, key factor, recommended counter-strategy
  - Use `st.info()` or `st.success()` for visual distinction

### Task 5.6 — Contextual help tooltips
- **File:** `ui.py`
- **Action:** Add `help=` parameter to all metric displays:
  - "Energized %" → "Percentage of matches where this alliance scored 100+ fuel points (earns 1 bonus RP)."
  - "OPR" → "Offensive Power Rating. Estimates a team's average contribution to their alliance score."
  - "CCWM" → "Calculated Contribution to Winning Margin. Positive = the team makes their alliance win by more."

### Verification — Phase 5
1. App loads with 5 tabs (not 7).
2. Theme selector is in sidebar, no Settings tab exists.
3. Architecture diagram is inside "Rules & About" under an expander.
4. Randomize button shuffles archetypes.
5. Results interpretation panel appears after running a simulation.
6. Hover over any metric → tooltip appears.

---

## Phase 6 (Future / Nice-to-Have)

These are NOT blocking. Implement only after Phases 1–5 are complete and verified.

- [ ] Match replay timeline (tick-by-tick visualization of a single sim)
- [ ] Export results to CSV/JSON download button
- [ ] QR code config sharing between devices
- [ ] Multi-event OPR comparison chart
- [ ] Pit scouting form with local storage
- [ ] "Next match in X minutes" notification from TBA schedule
- [ ] Scouting data override panel (custom accuracy, cycle time per team)
- [ ] Mobile-responsive layout testing and fixes

---

## File Change Summary

| File | Action | Phase |
|---|---|---|
| `requirements.txt` | Add `requests` | 1 |
| `src/tba_client.py` | **[NEW]** TBA API client class | 1 |
| `src/tba_mapper.py` | **[NEW]** OPR→archetype mapping | 1 |
| `tests/test_tba_client.py` | **[NEW]** Unit tests with mocked HTTP | 1 |
| `tests/test_event_center.py` | **[NEW]** Integration tests with mocked TBA | 2 |
| `ui.py` | Add API key input (sidebar) | 1 |
| `ui.py` | Replace Teams History → Event Center | 2 |
| `ui.py` | Replace Strategy Insights → Strategy Advisor | 3 |
| `ui.py` | Add Alliance Picker section | 4 |
| `ui.py` | Restructure to 5 tabs, merge Settings/Workflow | 5 |
| `ui.py` | Sidebar simplification, tooltips, results panel | 5 |

---

## Key Dependencies & Ordering

```
Phase 1 (TBA client)
   ↓
Phase 2 (Event Center)  ← needs TBA client
   ↓
Phase 3 (Strategy Advisor)  ← needs TBA client + archetype mapper
   ↓
Phase 4 (Alliance Recommender)  ← needs Strategy Advisor + Event Center data
   ↓
Phase 5 (UX Polish)  ← needs all tabs finalized before restructure
```

> [!IMPORTANT]
> Do NOT skip phases. Phase 1 is the foundation. Without `tba_client.py`, Phases 2-4 cannot function.

> [!NOTE]
> The TBA API key is free. Register at https://www.thebluealliance.com/account.
> Rate limit: 100 requests/min per IP. Use caching (`@st.cache_data(ttl=300)`) to stay well under.

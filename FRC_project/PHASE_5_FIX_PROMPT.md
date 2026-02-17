# Phase 5 — Fix Prompt: Randomize Alliance Bug + Missing Goals

> Agent-ready fix list for Phase 5 issues. Work through each fix in order.
> Primary file: `ui.py`

---

## Bug #1 (CRITICAL): Randomize Alliances Button Does NOT Visually Update Selectboxes

### Problem Description

When the user clicks "🎲 Randomize Alliances" in the sidebar, the page reruns but the **selectbox dropdowns still show the old/default archetype values** instead of the newly randomized ones. The randomization logic runs, but the UI never reflects the result.

### Root Cause

Streamlit's widget state management conflicts with the current approach. The code at lines 241-249 does this:

1. Stores randomized archetypes in `st.session_state.randomized_red` / `randomized_blue`
2. Deletes widget keys (`red_q1`, `red_q2`, etc.) from `st.session_state`
3. Calls `st.rerun()`
4. On rerun, `_build_quick_alliance()` reads randomized values, converts to indices, deletes them, then creates selectboxes with those indices

**The bug:** Streamlit's internal `WidgetManager` caches widget values independently of `st.session_state`. When you `del st.session_state["red_q1"]` and call `st.rerun()`, Streamlit's internal registry may **re-inject the old widget value** before the script renders the selectbox with the new `index`. The `index` parameter is only used when NO prior state exists for that key — but Streamlit's internal cache still holds the old value, so `index` is ignored.

### Fix: Directly SET Widget Keys Instead of Deleting Them

**Replace the entire randomize handler block (lines 238-249) with:**

```python
# Randomize button MUST come before alliance building
randomize_clicked = st.sidebar.button(
    "🎲 Randomize Alliances",
    help="Randomly shuffle archetype selections for quick testing",
    use_container_width=True
)

if randomize_clicked and not is_custom:
    # Directly set the widget keys to randomized archetype VALUES
    # This overwrites Streamlit's internal widget state correctly
    st.session_state.red_q1 = random.choice(ARCHETYPES)
    st.session_state.red_q2 = random.choice(ARCHETYPES)
    st.session_state.red_q3 = random.choice(ARCHETYPES)
    st.session_state.blue_q1 = random.choice(ARCHETYPES)
    st.session_state.blue_q2 = random.choice(ARCHETYPES)
    st.session_state.blue_q3 = random.choice(ARCHETYPES)
    st.rerun()
```

**AND simplify `_build_quick_alliance()` (lines 214-236) — remove the `randomized_key` lookup entirely:**

```python
def _build_quick_alliance(prefix, color_divider, default_indices, strat_key):
    st.sidebar.subheader(f"{prefix} Alliance", divider=color_divider)

    idx1, idx2, idx3 = default_indices

    a1 = st.sidebar.selectbox(
        f"{prefix} R1", ARCHETYPES, index=idx1,
        format_func=lambda x: ARCHETYPE_LABELS[x],
        key=f"{prefix.lower()}_q1"
    )
    a2 = st.sidebar.selectbox(
        f"{prefix} R2", ARCHETYPES, index=idx2,
        format_func=lambda x: ARCHETYPE_LABELS[x],
        key=f"{prefix.lower()}_q2"
    )
    a3 = st.sidebar.selectbox(
        f"{prefix} R3", ARCHETYPES, index=idx3,
        format_func=lambda x: ARCHETYPE_LABELS[x],
        key=f"{prefix.lower()}_q3"
    )

    strat = st.sidebar.selectbox(
        f"{prefix} Strategy", STRATEGIES, index=0,
        format_func=lambda x: STRATEGY_LABELS[x],
        key=strat_key
    )
    auto_preset = st.sidebar.selectbox(
        f"{prefix} Auto Plan", list(AUTO_PRESET_LABELS.keys()), index=0,
        format_func=lambda x: AUTO_PRESET_LABELS[x],
        key=f"{prefix.lower()}_auto"
    )

    return [a1, a2, a3], strat, auto_preset
```

### Why This Fix Works

When you directly assign `st.session_state.red_q1 = "defense_bot"`, Streamlit treats this as the **canonical widget value**. On the next `st.rerun()`, the selectbox with `key="red_q1"` reads its value from `st.session_state["red_q1"]` and displays the correct randomized archetype. The `index` parameter is only used as a fallback when no session state value exists for that key.

### Also Remove Dead Session State Init

Remove this block if it exists (near top of file):

```python
# DELETE THIS — no longer needed
if "randomize_trigger" not in st.session_state:
    st.session_state.randomize_trigger = 0
```

### Acceptance Criteria

- [ ] Click "🎲 Randomize Alliances" → all 6 selectboxes (Red R1/R2/R3 + Blue R1/R2/R3) immediately show NEW random archetypes
- [ ] Each click produces a DIFFERENT randomized combination
- [ ] The randomized values persist in the dropdowns (user can see what was randomized and manually change individual slots)
- [ ] Running a simulation after randomizing uses the randomized archetypes (not defaults)
- [ ] Randomize button is disabled / has no effect when in Custom (Subsystem) mode

---

## Bug #2 (MINOR): Randomize Button Active in Custom Mode Shows No Feedback

### Problem

When the user is in "Custom (Subsystem)" mode and clicks Randomize, nothing happens and there's no feedback. The `if randomize_clicked and not is_custom:` guard silently swallows the click.

### Fix

Show a toast or warning when randomize is clicked in custom mode:

```python
if randomize_clicked:
    if not is_custom:
        # ... randomize logic ...
        st.rerun()
    else:
        st.sidebar.warning("⚠️ Randomize only works in Quick (Archetype) mode.")
```

### Acceptance Criteria

- [ ] Clicking Randomize in Custom mode shows a warning message in the sidebar
- [ ] Warning disappears on next interaction

---

## Missing Goal #1: Replace Config Mode Radio with Expander

### Spec Reference (Task 5.4)

> "Use `st.sidebar.expander('Advanced: Custom Subsystems')` instead of the radio toggle"

### Current Code (lines 192-198)

```python
config_mode = st.sidebar.radio(
    "Configuration Mode",
    ["Quick (Archetype)", "Custom (Subsystem)"],
    key="config_mode",
    help="Quick mode uses balanced presets. Custom mode allows tuning..."
)
is_custom = config_mode.startswith("Custom")
```

### Required Change

Replace the radio toggle with a **default-collapsed expander**. Quick Mode should be the default (no toggle needed). Custom Mode only activates when the user explicitly opens the expander:

```python
# Default: Quick Mode is always active
# Custom mode is behind an expander
with st.sidebar.expander("⚙️ Advanced: Custom Subsystems", expanded=False):
    enable_custom = st.checkbox(
        "Enable Custom Subsystem Tuning",
        value=False,
        key="enable_custom",
        help="Override archetype presets with manual subsystem sliders for each robot."
    )

is_custom = st.session_state.get("enable_custom", False)
```

**Alternative approach** (simpler — use expander visibility as the toggle):

```python
# Quick mode selectboxes always render
# Custom overrides are inside a collapsible section
# The is_custom flag determines which config feeds the simulation

use_custom = st.sidebar.checkbox(
    "🔧 Use Custom Subsystems",
    value=False,
    key="use_custom_mode",
    help="Enable manual tuning of each robot's subsystems instead of using archetype presets."
)
is_custom = use_custom

if is_custom:
    with st.sidebar.expander("⚙️ Custom Subsystem Configuration", expanded=True):
        # ... custom robot builders ...
```

### Acceptance Criteria

- [ ] No radio button for "Configuration Mode" in the sidebar
- [ ] Quick Mode is the default experience — user sees archetype selectboxes immediately
- [ ] Custom subsystem controls are hidden inside an expander or behind a checkbox
- [ ] Switching to custom mode does not break simulation
- [ ] Switching back to quick mode restores archetype-based behavior

---

## Missing Goal #2: Randomize Should Also Shuffle Strategy & Auto Plan (Enhancement)

### Spec Reference (Task 5.4)

> "Add '🎲 Randomize' button to sidebar that shuffles archetype selections"

The spec only mentions archetypes, but for a complete "quick testing" experience, consider also randomizing:

- **Strategy** for each alliance (from the 5 available strategies)
- **Auto Plan** for each alliance (from the 4 available presets)

### Optional Enhancement

```python
if randomize_clicked and not is_custom:
    # Randomize archetypes
    st.session_state.red_q1 = random.choice(ARCHETYPES)
    st.session_state.red_q2 = random.choice(ARCHETYPES)
    st.session_state.red_q3 = random.choice(ARCHETYPES)
    st.session_state.blue_q1 = random.choice(ARCHETYPES)
    st.session_state.blue_q2 = random.choice(ARCHETYPES)
    st.session_state.blue_q3 = random.choice(ARCHETYPES)

    # Optionally also randomize strategy and auto plan
    st.session_state.rs = random.choice(STRATEGIES)
    st.session_state.bs = random.choice(STRATEGIES)
    st.session_state.red_auto = random.choice(list(AUTO_PRESET_LABELS.keys()))
    st.session_state.blue_auto = random.choice(list(AUTO_PRESET_LABELS.keys()))

    st.rerun()
```

### Acceptance Criteria

- [ ] Randomize shuffles strategies and auto plans alongside archetypes (if implemented)
- [ ] All randomized values are visible in the sidebar dropdowns after clicking

---

## Missing Goal #3: Visual Confirmation of Randomization

### Problem

After clicking Randomize, there's no visual confirmation that randomization occurred. The selectboxes change, but the user might not notice which values changed.

### Fix: Add a Toast Notification

```python
if randomize_clicked and not is_custom:
    # ... set randomized values ...
    st.session_state._randomize_toast = True
    st.rerun()

# After rerun, show toast
if st.session_state.get("_randomize_toast"):
    st.sidebar.success("🎲 Alliances randomized!")
    del st.session_state._randomize_toast
```

### Acceptance Criteria

- [ ] A brief success message appears after randomization
- [ ] Message disappears on next interaction

---

## Verification Checklist — Complete Phase 5 Compliance

Run through this checklist after applying all fixes:

### Core Functionality
- [ ] App loads with exactly 5 tabs: Event Center, Match Simulator, Strategy Advisor, Robot Database, Rules & About
- [ ] Event Center is the FIRST tab (dashboard-first approach)
- [ ] Theme selector is in the sidebar (not a separate Settings tab)
- [ ] Architecture diagram is inside "Rules & About" under a collapsible expander
- [ ] Simulation Workflow content is merged into "Rules & About"

### Randomize Alliance (Bug Fix)
- [ ] "🎲 Randomize Alliances" button visible in sidebar
- [ ] Click → ALL 6 archetype selectboxes update to show new random values
- [ ] Randomized values are VISIBLE in the dropdown (user can see what was picked)
- [ ] Clicking multiple times produces different combinations each time
- [ ] Running simulation after randomizing uses the randomized archetypes
- [ ] Randomize has no effect (or shows warning) in Custom mode

### Results & UX
- [ ] Plain-English results interpretation panel appears after simulation
- [ ] Interpretation identifies dominant alliance, key factors, and counter-strategy tips
- [ ] Contextual help tooltips appear on hover for all key metrics (OPR, DPR, CCWM, RP, etc.)
- [ ] At least 16 tooltip instances across the UI
- [ ] No Settings tab exists
- [ ] No Simulation Workflow dedicated tab exists

### Regression Check
- [ ] Quick Mode simulation runs correctly
- [ ] Custom Mode simulation runs correctly
- [ ] Find Best Strategy runs and shows the 5×5 strategy matrix
- [ ] TBA API key input works and shows success/error indicator
- [ ] Event Center loads data when API key is provided
- [ ] Strategy Advisor provides recommendations
- [ ] Dark Mode theme applies correctly
- [ ] High Contrast theme applies correctly

---

## File Change Summary

| File | Lines | Change | Priority |
|------|-------|--------|----------|
| `ui.py` | 238-249 | Replace randomize handler — set widget keys directly | 🔴 Critical |
| `ui.py` | 214-236 | Simplify `_build_quick_alliance()` — remove randomized_key lookup | 🔴 Critical |
| `ui.py` | 192-198 | Replace config radio with expander/checkbox | 🟡 Medium |
| `ui.py` | ~241 | Add custom mode warning for randomize | 🟢 Low |
| `ui.py` | ~250 | Add randomize toast notification | 🟢 Low |
| `ui.py` | ~243 | Optionally randomize strategy/auto plan too | 🟢 Low |

---

## Technical Notes

### Streamlit Widget State Behavior

Streamlit selectboxes with a `key` parameter behave as follows:

1. **First render (no session state for key):** Uses `index` parameter to determine initial value
2. **Subsequent renders (session state exists for key):** IGNORES `index`, uses `st.session_state[key]` as the value
3. **`del st.session_state[key]`:** Removes from Python dict, BUT Streamlit's internal `WidgetManager` may re-inject the value on `st.rerun()` before the widget renders — this is the source of the bug
4. **Direct assignment `st.session_state[key] = value`:** Overwrites both Python dict AND Streamlit's internal tracking — this is the reliable approach

### Key Insight

The pattern `del st.session_state[widget_key]` + `st.rerun()` is **unreliable** for programmatically changing widget values in Streamlit >= 1.20. Always use direct assignment instead.

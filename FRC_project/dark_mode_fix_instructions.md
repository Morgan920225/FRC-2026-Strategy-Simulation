# Dark Mode UI Fix Instructions

## Problem
When users select "Dark Mode" in the Settings tab, the tab labels and some UI elements become difficult or impossible to read due to insufficient color contrast against the dark background.

## Root Cause
The current dark mode CSS injection (lines 42-52 in `ui.py`) only targets tab labels with `button[data-baseweb="tab"] p` but doesn't handle all necessary UI elements that need color adjustments in dark mode.

## Solution
Expand the dark mode CSS to include additional selectors for better text visibility:

### Changes Required in `ui.py`

**Location:** Lines 42-52 (Dark Mode theme injection)

**Current Code:**
```python
if theme == "Dark Mode":
    st.markdown("""
        <style>
        .stApp { background-color: #0E1117; color: #FAFAFA; }
        .stMetric { color: #FAFAFA; }
        /* Fix Tab Label Colors */
        button[data-baseweb="tab"] p { color: #FAFAFA !important; }
        .stExpander { background-color: #1E2127; border-color: #3E4147; }
        .stMarkdown { color: #FAFAFA; }
        </style>
    """, unsafe_allow_html=True)
```

**Fixed Code:**
```python
if theme == "Dark Mode":
    st.markdown("""
        <style>
        .stApp { background-color: #0E1117; color: #FAFAFA; }
        .stMetric { color: #FAFAFA; }
        .stMetricLabel { color: #FAFAFA !important; }
        .stMetricValue { color: #FAFAFA !important; }
        /* Fix Tab Label Colors - Multiple selectors for robustness */
        button[data-baseweb="tab"] p { color: #FAFAFA !important; }
        button[data-baseweb="tab"] { color: #FAFAFA !important; }
        button[data-baseweb="tab"] div { color: #FAFAFA !important; }
        button[data-baseweb="tab"][aria-selected="true"] { 
            border-bottom-color: #3498db !important; 
        }
        /* Fix Expanders */
        .stExpander { background-color: #1E2127; border-color: #3E4147; }
        .stExpander summary { color: #FAFAFA !important; }
        /* Fix Markdown and Text */
        .stMarkdown { color: #FAFAFA; }
        .stMarkdown p { color: #FAFAFA; }
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #FAFAFA; }
        /* Fix Dataframe Headers */
        .stDataFrame { color: #FAFAFA; }
        /* Fix Select Boxes and Inputs */
        .stSelectbox label { color: #FAFAFA !important; }
        .stNumberInput label { color: #FAFAFA !important; }
        .stTextInput label { color: #FAFAFA !important; }
        .stSlider label { color: #FAFAFA !important; }
        .stRadio label { color: #FAFAFA !important; }
        /* Fix Captions */
        .stCaptionContainer { color: #B0B0B0 !important; }
        </style>
    """, unsafe_allow_html=True)
```

## Additional Improvements

### For "FRC Blue (TBA)" Theme
Consider adding light theme-specific overrides to ensure proper contrast:

```python
elif theme == "FRC Blue (TBA)":
    st.markdown("""
        <style>
        /* Ensure dark text on light background */
        button[data-baseweb="tab"] p { color: #1E1E1E !important; }
        button[data-baseweb="tab"] div { color: #1E1E1E !important; }
        button[data-baseweb="tab"][aria-selected="true"] { 
            border-bottom-color: #0277BD !important; 
        }
        </style>
    """, unsafe_allow_html=True)
```

## Verification Steps

1. Run `streamlit run ui.py`
2. Navigate to the "⚙️ Settings" tab
3. Select "Dark Mode" from the theme radio buttons
4. Verify the following elements are **clearly visible** with white/light text:
   - [ ] All tab labels (📊 Match Simulator, 📜 Game Rules, etc.)
   - [ ] Active tab indicator (should have blue underline)
   - [ ] Metric labels and values in the Match Simulator
   - [ ] Expander titles
   - [ ] All form labels (selectbox, slider, number input)
   - [ ] Headers (h1, h2, h3)
   - [ ] Paragraph text
   - [ ] Captions
5. Switch back to "FRC Blue (TBA)" and verify light text is not broken
6. Switch to "High Contrast" and verify yellow text is preserved

## Files to Modify
- `ui.py` (lines 42-52, and optionally add FRC Blue override after line 62)

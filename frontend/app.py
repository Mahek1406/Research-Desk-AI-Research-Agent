"""
ResearchDesk - Professional AI Research Agent Workspace.
Human-designed interface with session authentication, interactive controls,
evidence grounding, robust Soft Light and Dark themes, and a right-side slide-out toolbar.
"""

import json
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import requests
import streamlit as st
import streamlit.components.v1 as components

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="ResearchDesk | AI Research Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------
# Theme Initialization & Query Param Persistence
# ---------------------------------------------------------------------
query_params = st.query_params
if "theme" in query_params and "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = query_params["theme"]
elif "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "light"

# Ensure query parameter stays in sync
st.query_params["theme"] = st.session_state["theme_mode"]

# ---------------------------------------------------------------------
# Session & State Initialization
# ---------------------------------------------------------------------
DEMO_USER = "researcher@startup.io"
DEMO_PASS = "ResearchDesk#2026"

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_email" not in st.session_state:
    st.session_state["user_email"] = ""
if "research_question" not in st.session_state:
    st.session_state["research_question"] = ""
if "query_history" not in st.session_state:
    st.session_state["query_history"] = []
if "last_result" not in st.session_state:
    st.session_state["last_result"] = None
if "auto_run" not in st.session_state:
    st.session_state["auto_run"] = False
if "show_right_drawer" not in st.session_state:
    st.session_state["show_right_drawer"] = False

# ---------------------------------------------------------------------
# Semantic Theme Tokens (Soft Light & Cohesive Dark)
# ---------------------------------------------------------------------
is_dark = (st.session_state["theme_mode"] == "dark")

if is_dark:
    # Cohesive Dark Theme Palette
    app_bg = "#17191F"
    surface_bg = "#20232B"
    surface_elevated = "#282C36"
    text_primary = "#ECECF1"
    text_secondary = "#B0B4C0"
    text_muted = "#898E9D"
    border_color = "#383D49"
    input_bg = "#252934"
    input_text = "#ECECF1"
    input_placeholder = "#898E9D"
    button_bg = "#282C36"
    button_text = "#ECECF1"
    accent_color = "#939CE8"
    accent_hover = "#A6AEF0"
    sidebar_bg = "#20232B"
    badge_bg = "#282C36"
    badge_fg = "#939CE8"
    badge_border = "#383D49"
    overlay_bg = "rgba(0, 0, 0, 0.65)"
else:
    # Soft, Low-Glare Light Theme Palette
    app_bg = "#F4F1EB"
    surface_bg = "#FAF8F4"
    surface_elevated = "#FDFBF7"
    text_primary = "#302F2B"
    text_secondary = "#69665F"
    text_muted = "#858176"
    border_color = "#DED9CF"
    input_bg = "#EEEAE2"
    input_text = "#302F2B"
    input_placeholder = "#858176"
    button_bg = "#FAF8F4"
    button_text = "#302F2B"
    accent_color = "#5B65A8"
    accent_hover = "#4D568F"
    sidebar_bg = "#FAF8F4"
    badge_bg = "#EEEAE2"
    badge_fg = "#5B65A8"
    badge_border = "#DED9CF"
    overlay_bg = "rgba(48, 47, 43, 0.45)"

THEME_CSS = f"""
<style>
    /* =========================================================
       1. Base Reset & Streamlit Chrome Removal
       ========================================================= */
    [data-testid="stDeployButton"], 
    .stDeployButton, 
    #MainMenu, 
    footer,
    header[data-testid="stHeader"] {{
        display: none !important;
        visibility: hidden !important;
    }}
    
    /* =========================================================
       2. Centralized CSS Custom Properties (Theme Tokens)
       ========================================================= */
    :root {{
        --app-bg: {app_bg};
        --surface-bg: {surface_bg};
        --surface-elevated: {surface_elevated};
        --text-primary: {text_primary};
        --text-secondary: {text_secondary};
        --text-muted: {text_muted};
        --border-color: {border_color};
        --input-bg: {input_bg};
        --input-text: {input_text};
        --input-placeholder: {input_placeholder};
        --button-bg: {button_bg};
        --button-text: {button_text};
        --accent-color: {accent_color};
        --accent-hover: {accent_hover};
        --sidebar-bg: {sidebar_bg};
        --badge-bg: {badge_bg};
        --badge-fg: {badge_fg};
        --badge-border: {badge_border};
        --overlay-bg: {overlay_bg};
    }}

    /* Global Application Containers Background & Foreground */
    .stApp, 
    [data-testid="stAppViewContainer"], 
    [data-testid="stMain"],
    section.main {{
        background-color: var(--app-bg) !important;
        color: var(--text-primary) !important;
    }}
    
    /* Left Sidebar container */
    [data-testid="stSidebar"], 
    [data-testid="stSidebarContent"],
    section[data-testid="stSidebar"] {{
        background-color: var(--sidebar-bg) !important;
        color: var(--text-primary) !important;
        border-right: 1px solid var(--border-color) !important;
    }}

    /* All Typography Elements */
    h1, h2, h3, h4, h5, h6, p, span, label, div, strong, b, em, li {{
        color: var(--text-primary) !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", sans-serif;
    }}
    
    /* Subtitles and Muted Labels */
    .theme-muted {{
        color: var(--text-muted) !important;
    }}
    .theme-secondary {{
        color: var(--text-secondary) !important;
    }}

    /* Form Inputs & Textareas */
    .stTextArea textarea, 
    .stTextInput input {{
        background-color: var(--input-bg) !important;
        color: var(--input-text) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
    }}
    .stTextArea textarea:focus, 
    .stTextInput input:focus {{
        border-color: var(--accent-color) !important;
        box-shadow: 0 0 0 2px rgba(91, 101, 168, 0.25) !important;
    }}
    .stTextArea textarea::placeholder, 
    .stTextInput input::placeholder {{
        color: var(--input-placeholder) !important;
    }}

    /* Buttons */
    .stButton button {{
        background-color: var(--button-bg) !important;
        color: var(--button-text) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        transition: all 0.15s ease-in-out;
    }}
    .stButton button:hover {{
        border-color: var(--accent-color) !important;
        color: var(--accent-color) !important;
    }}
    
    /* Primary Call to Action Button */
    .stButton button[kind="primary"] {{
        background-color: var(--accent-color) !important;
        color: #FFFFFF !important;
        border: 1px solid var(--accent-hover) !important;
    }}
    .stButton button[kind="primary"]:hover {{
        background-color: var(--accent-hover) !important;
        color: #FFFFFF !important;
    }}

    /* Tabs Styling */
    button[data-baseweb="tab"] {{
        color: var(--text-secondary) !important;
        background: transparent !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: var(--accent-color) !important;
        border-bottom-color: var(--accent-color) !important;
        font-weight: 600 !important;
    }}

    /* Expanders */
    [data-testid="stExpander"] {{
        background-color: var(--surface-bg) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
        margin-bottom: 0.75rem !important;
    }}
    [data-testid="stExpander"] summary {{
        color: var(--text-primary) !important;
    }}

    /* Workspace Header */
    .workspace-banner {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 1rem;
        margin-bottom: 1.5rem;
    }}
    .brand-name {{
        font-size: 1.65rem;
        font-weight: 700;
        color: var(--text-primary) !important;
        letter-spacing: -0.03em;
        margin: 0;
    }}
    .brand-desc {{
        font-size: 0.95rem;
        color: var(--text-muted) !important;
        margin-top: 0.2rem;
    }}

    /* Cards */
    .summary-card {{
        background: var(--surface-bg);
        border: 1px solid var(--border-color);
        border-left: 4px solid var(--accent-color);
        padding: 1.25rem 1.5rem;
        border-radius: 4px;
        font-size: 1.05rem;
        line-height: 1.65;
        color: var(--text-primary);
        margin-bottom: 1.5rem;
    }}
    
    .finding-card {{
        background: var(--surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        padding: 1.15rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}

    .login-container-card {{
        background: var(--surface-bg);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 2rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }}
    
    .demo-info-card {{
        background: var(--surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        padding: 1rem;
        margin-top: 1rem;
    }}

    /* Source Badge Tag */
    .source-badge {{
        background-color: var(--badge-bg);
        color: var(--badge-fg) !important;
        border: 1px solid var(--badge-border);
        border-radius: 4px;
        padding: 0.2rem 0.5rem;
        font-size: 0.78rem;
        font-weight: 600;
        margin-left: 0.4rem;
        display: inline-block;
    }}
    
    /* Confidence Tags */
    .conf-high {{
        background-color: rgba(46, 125, 50, 0.15);
        color: {"#81C784" if is_dark else "#2E7D32"} !important;
        border: 1px solid rgba(46, 125, 50, 0.3);
        padding: 0.25rem 0.65rem;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }}
    .conf-medium {{
        background-color: rgba(180, 83, 9, 0.15);
        color: {"#FCD34D" if is_dark else "#B45309"} !important;
        border: 1px solid rgba(180, 83, 9, 0.3);
        padding: 0.25rem 0.65rem;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }}
    .conf-low {{
        background-color: rgba(198, 40, 40, 0.15);
        color: {"#EF5350" if is_dark else "#C62828"} !important;
        border: 1px solid rgba(198, 40, 40, 0.3);
        padding: 0.25rem 0.65rem;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }}

    /* User Profile Card */
    .user-profile-box {{
        background: var(--surface-elevated);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        padding: 0.85rem 1rem;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }}
    .avatar-circle {{
        width: 36px;
        height: 36px;
        background-color: var(--accent-color);
        color: #FFFFFF !important;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.95rem;
    }}
    
    {"" if is_dark else """
    /* =========================================================
       Light Theme ONLY: Specific Login Visibility Fixes
       ========================================================= */
    /* 1. Sign In Button: Contrasting background color with readable text */
    [data-testid="stFormSubmitButton"] button,
    .stFormSubmitButton button,
    form[data-testid="stForm"] [data-testid="stFormSubmitButton"] button,
    form button[kind="secondaryFormSubmit"],
    form button[kind="primaryFormSubmit"] {
        background-color: #5B65A8 !important;
        color: #FFFFFF !important;
    }
    [data-testid="stFormSubmitButton"] button:hover,
    .stFormSubmitButton button:hover,
    form button[kind="secondaryFormSubmit"]:hover,
    form button[kind="primaryFormSubmit"]:hover {
        background-color: #4D568F !important;
        color: #FFFFFF !important;
    }

    /* 2. Password Visibility Eye Icon: Contrasting background color on button/container */
    [data-testid="stTextInput"]:has(input[type="password"]) button,
    .stTextInput:has(input[type="password"]) button,
    [data-testid="stTextInput"] button[aria-label*="password" i],
    [data-testid="stTextInput"] button[aria-label*="Show password" i],
    [data-testid="stTextInput"] button[aria-label*="Hide password" i],
    .stTextInput div[data-baseweb="input"] button {
        background-color: #5B65A8 !important;
        color: #FFFFFF !important;
    }
    [data-testid="stTextInput"]:has(input[type="password"]) button:hover,
    .stTextInput:has(input[type="password"]) button:hover,
    [data-testid="stTextInput"] button[aria-label*="password" i]:hover {
        background-color: #4D568F !important;
    }
    [data-testid="stTextInput"]:has(input[type="password"]) button *,
    .stTextInput:has(input[type="password"]) button *,
    [data-testid="stTextInput"] button[aria-label*="password" i] * {
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
    }
    """}
</style>
"""

st.markdown(THEME_CSS, unsafe_allow_html=True)


def check_backend_health() -> Optional[Dict[str, Any]]:
    """Checks whether the FastAPI backend is running."""
    try:
        resp = requests.get(f"{BACKEND_URL}/api/health", timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        return None
    return None


def execute_research_request(question: str, max_sources: int, include_scraping: bool) -> Optional[Dict[str, Any]]:
    """Submits inquiry to backend."""
    payload = {
        "question": question,
        "max_sources": max_sources,
        "include_web_scraping": include_scraping,
    }
    try:
        resp = requests.post(f"{BACKEND_URL}/api/research", json=payload, timeout=75)
        if resp.status_code == 200:
            return resp.json()
        else:
            try:
                err_detail = resp.json().get("detail", resp.text)
            except Exception:
                err_detail = resp.text
            st.error(f"Research server notification: {err_detail}")
            return None
    except requests.exceptions.ConnectionError:
        st.error(
            f"Unable to reach the research service at `{BACKEND_URL}`. "
            "Please ensure the backend is started in your terminal (`uvicorn backend.main:app --reload --port 8000`)."
        )
        return None
    except Exception as e:
        st.error(f"Network error during research execution: {str(e)}")
        return None


def generate_markdown_export(res: Dict[str, Any]) -> str:
    """Formats current research result as clean Markdown for export."""
    lines = [
        f"# ResearchDesk Investigation Report",
        f"**Question:** {res.get('question', '')}",
        f"**Confidence Level:** {res.get('confidence_level', 'Medium')} — {res.get('confidence_explanation', '')}",
        "",
        "---",
        "## Executive Summary",
        res.get("short_answer", ""),
        "",
        "---",
        "## Key Findings",
    ]
    for idx, f in enumerate(res.get("key_findings", []), 1):
        sources_str = ", ".join(f.get("supporting_source_ids", []))
        lines.append(f"### {idx}. {f.get('claim', '')} {f'({sources_str})' if sources_str else ''}")
        lines.append(f.get("detail", ""))
        lines.append("")

    lines.append("---")
    lines.append("## Detailed Analysis")
    lines.append(res.get("detailed_analysis", ""))
    lines.append("")

    lines.append("---")
    lines.append("## Sources & Citations")
    for s in res.get("sources_used", []):
        lines.append(f"- **{s.get('id', '')}**: [{s.get('title', '')}]({s.get('url', '')}) ({s.get('domain', '')}) — *Status: {s.get('retrieval_status', '')}*")
        if s.get("snippet"):
            lines.append(f"  > {s.get('snippet')}")

    lines.append("")
    lines.append("---")
    lines.append("## Assumptions & Limitations")
    lines.append("### Assumptions")
    for a in res.get("assumptions", []):
        lines.append(f"- {a}")
    lines.append("### Limitations")
    for l in res.get("limitations", []):
        lines.append(f"- {l}")
    lines.append("### Suggested Next Steps")
    for step in res.get("suggested_next_steps", []):
        lines.append(f"1. {step}")

    return "\n".join(lines)


# ---------------------------------------------------------------------
# 1. LOGIN SCREEN WITH REPAIRED THEME STYLING
# ---------------------------------------------------------------------
if not st.session_state["authenticated"]:
    # Theme switcher available right on login page
    top_col_space, top_col_theme = st.columns([6, 2])
    with top_col_theme:
        login_theme_label = " Soft Light" if is_dark else " Dark Mode"
        if st.button(f" {login_theme_label}", key="login_theme_btn", use_container_width=True):
            st.session_state["theme_mode"] = "light" if is_dark else "dark"
            st.query_params["theme"] = st.session_state["theme_mode"]
            st.rerun()

    col_spacer_left, col_card, col_spacer_right = st.columns([1, 2, 1])
    with col_card:
        st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="login-container-card">
                <h2 style="margin-top: 0; color: var(--text-primary); font-size: 1.7rem; font-weight: 700;">ResearchDesk</h2>
                <p style="color: var(--text-secondary); margin-bottom: 1.5rem; line-height: 1.5;">
                    Sign in to your AI Research Agent workspace. Investigate technical inquiries, crawl verified web documentation, and inspect grounded citations.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            user_input = st.text_input("Work Email or Username", placeholder="e.g. researcher@startup.io")
            pass_input = st.text_input("Password", type="password", placeholder="Enter password")
            submit = st.form_submit_button("Sign In to ResearchDesk", use_container_width=True)

            if submit:
                if (user_input.strip() in (DEMO_USER, "admin")) and (pass_input.strip() == DEMO_PASS):
                    st.session_state["authenticated"] = True
                    st.session_state["user_email"] = user_input.strip()
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please enter the valid username and password provided below.")

        st.markdown(
            f"""
            <div class="demo-info-card">
                <strong style="color: var(--text-primary); font-size: 0.95rem;">Demo Credentials:</strong><br/>
                <span style="color: var(--text-secondary); font-size: 0.9rem;">
                    • <strong>Username:</strong> <code>{DEMO_USER}</code> (or <code>admin</code>)<br/>
                    • <strong>Password:</strong> <code>{DEMO_PASS}</code>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Auto-Fill & Sign In with Demo Account", type="secondary", use_container_width=True):
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = DEMO_USER
            st.rerun()

    st.stop()


# ---------------------------------------------------------------------
# 2. LOGGED-IN WORKSPACE & FUNCTIONAL LEFT SIDEBAR
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f"""
        <div class="user-profile-box">
            <div class="avatar-circle">RD</div>
            <div>
                <strong style="font-size: 0.95rem; color: var(--text-primary);">Lead Researcher</strong><br/>
                <span style="font-size: 0.8rem; color: var(--text-muted);">{st.session_state.get('user_email', DEMO_USER)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Sign Out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["last_result"] = None
        st.rerun()

    st.markdown(f"<hr style='border-color: var(--border-color);'>", unsafe_allow_html=True)
    
    st.subheader("Appearance & Tools")
    theme_btn_text = "☀️ Soft Light" if is_dark else "🌙 Dark Theme"
    if st.button(f"🍾 {theme_btn_text}", key="sidebar_theme_toggle", use_container_width=True, help="Toggle between Soft Light and Cohesive Dark mode"):
        st.session_state["theme_mode"] = "light" if is_dark else "dark"
        st.query_params["theme"] = st.session_state["theme_mode"]
        st.rerun()

    if st.button("⚙️ Open Quick Tools Drawer", key="open_quick_tools_sidebar", use_container_width=True):
        st.session_state["show_right_drawer"] = True
        st.rerun()

    st.markdown(f"<hr style='border-color: var(--border-color);'>", unsafe_allow_html=True)
    st.subheader("Research Parameters")

    max_sources = st.slider(
        "Source Evidence Depth",
        min_value=2,
        max_value=8,
        value=5,
        help="Target number of distinct sources to incorporate into synthesis.",
    )

    include_scraping = st.checkbox(
        "Deep Webpage Crawling",
        value=True,
        help="When checked, visits candidate URLs and extracts body paragraphs beyond search snippets.",
    )

    research_mode = st.radio(
        "Synthesis Mode",
        options=["Comprehensive Analysis", "Executive Brief"],
        index=0,
        help="Controls the density of the structured report.",
    )

    st.markdown(f"<hr style='border-color: var(--border-color);'>", unsafe_allow_html=True)
    if st.session_state["query_history"]:
        st.subheader("Recent Inquiries")
        for q_hist in st.session_state["query_history"][-3:]:
            if st.button(f"🔍 {q_hist[:28]}...", key=f"hist_{q_hist[:10]}", use_container_width=True):
                st.session_state["research_question"] = q_hist
                st.session_state["auto_run"] = True
                st.rerun()

    if st.button("Clear Workspace & Results", use_container_width=True):
        st.session_state["last_result"] = None
        st.session_state["research_question"] = ""
        st.session_state["auto_run"] = False
        st.rerun()


# ---------------------------------------------------------------------
# 3. MAIN HEADER & RIGHT-SIDE SLIDE-OUT MENU BUTTON
# ---------------------------------------------------------------------
head_col1, head_col2, head_col3 = st.columns([5, 2, 1.8])
with head_col1:
    st.markdown(
        f"""
        <div class="workspace-banner" style="border-bottom: none; margin-bottom: 0; padding-bottom: 0.5rem;">
            <div>
                <h1 class="brand-name">ResearchDesk</h1>
                <p class="brand-desc">Autonomous multi-tool research agent with explicit planning, live verification, and citation audits.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with head_col2:
    st.markdown("<div style='height: 0.6rem;'></div>", unsafe_allow_html=True)
    header_theme_label = "🍾 Soft Light ☀️" if is_dark else "🍾 Dark Mode 🌙"
    if st.button(header_theme_label, key="header_theme_toggle", use_container_width=True):
        st.session_state["theme_mode"] = "light" if is_dark else "dark"
        st.query_params["theme"] = st.session_state["theme_mode"]
        st.rerun()
with head_col3:
    st.markdown("<div style='height: 0.6rem;'></div>", unsafe_allow_html=True)
    # Right-side sidebar trigger button
    drawer_btn_label = "✖ Close Tools" if st.session_state.get("show_right_drawer", False) else "☰ Quick Tools"
    if st.button(drawer_btn_label, key="toggle_right_drawer_btn", type="secondary", use_container_width=True):
        st.session_state["show_right_drawer"] = not st.session_state.get("show_right_drawer", False)
        st.rerun()

st.markdown(f"<hr style='margin-top: 0.3rem; margin-bottom: 1.5rem; border-color: var(--border-color);'>", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# 4. RIGHT-SIDE SLIDE-OUT SIDEBAR (QUICK TOOLS)
# ---------------------------------------------------------------------
if st.session_state.get("show_right_drawer", False):
    # Render the right slide-out panel directly
    with st.container():
        st.markdown(
            f"""
            <div style="background-color: var(--surface-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 4px 15px rgba(0,0,0,0.08);">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 0.75rem; margin-bottom: 1rem;">
                    <div style="font-size: 1.2rem; font-weight: 700; color: var(--text-primary);">
                        ⚡ Quick Tools (Right Drawer)
                    </div>
                    <span style="font-size: 0.85rem; color: var(--text-muted);">Slide-out menu</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        rcol_appear, rcol_rec, rcol_actions = st.columns([1, 1.2, 1.2])

        # --- Section 1: Appearance ---
        with rcol_appear:
            st.markdown(f"**Appearance**")
            st.caption(f"Active Theme: **{'Cohesive Dark' if is_dark else 'Soft Light'}**")
            drawer_theme_txt = "Switch to Soft Light" if is_dark else "Switch to Dark Mode"
            if st.button(f"🍾 {drawer_theme_txt}", key="drawer_theme_switch_btn", use_container_width=True):
                st.session_state["theme_mode"] = "light" if is_dark else "dark"
                st.query_params["theme"] = st.session_state["theme_mode"]
                st.rerun()

        # --- Section 2: Screen Recording Tool ---
        with rcol_rec:
            st.markdown(f"**Screen Recording**")
            # Interactive HTML5 MediaRecorder embedded component
            components.html(
                f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: {surface_elevated}; border: 1px solid {border_color}; border-radius: 6px; padding: 0.75rem; color: {text_primary};">
                    <div style="display: flex; gap: 0.5rem; margin-bottom: 0.5rem;">
                        <button id="startBtn" style="flex: 1; background: {accent_color}; color: #ffffff; border: none; padding: 0.45rem 0.6rem; border-radius: 4px; font-weight: 600; cursor: pointer; font-size: 0.82rem;">
                            ⏺ Start Recording
                        </button>
                        <button id="stopBtn" disabled style="flex: 1; background: #64748B; color: #ffffff; border: none; padding: 0.45rem 0.6rem; border-radius: 4px; font-weight: 600; cursor: not-allowed; font-size: 0.82rem;">
                            ⏹ Stop
                        </button>
                    </div>
                    <div id="statusDiv" style="font-size: 0.8rem; color: {text_muted}; margin-bottom: 0.4rem;">
                        Status: Ready (Select screen/window to capture)
                    </div>
                    <div id="timerDiv" style="font-size: 0.85rem; font-weight: 600; color: {text_primary}; display: none;">
                        Duration: <span id="timeVal">00:00</span>
                    </div>
                    <div id="downloadArea" style="margin-top: 0.5rem; display: none;">
                        <a id="downloadLink" style="display: inline-block; background: #2E7D32; color: #ffffff; text-decoration: none; padding: 0.35rem 0.75rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600;" download="research_session.webm">
                            📥 Download Recording (.webm)
                        </a>
                    </div>
                </div>

                <script>
                let mediaRecorder;
                let recordedChunks = [];
                let startTime;
                let timerInterval;

                const startBtn = document.getElementById("startBtn");
                const stopBtn = document.getElementById("stopBtn");
                const statusDiv = document.getElementById("statusDiv");
                const timerDiv = document.getElementById("timerDiv");
                const timeVal = document.getElementById("timeVal");
                const downloadArea = document.getElementById("downloadArea");
                const downloadLink = document.getElementById("downloadLink");

                function updateTimer() {{
                    const elapsed = Math.floor((Date.now() - startTime) / 1000);
                    const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
                    const secs = String(elapsed % 60).padStart(2, '0');
                    timeVal.innerText = mins + ":" + secs;
                }}

                startBtn.onclick = async () => {{
                    try {{
                        const stream = await navigator.mediaDevices.getDisplayMedia({{
                            video: {{ mediaSource: "screen" }},
                            audio: true
                        }});

                        recordedChunks = [];
                        mediaRecorder = new MediaRecorder(stream, {{ mimeType: "video/webm; codecs=vp9" }});
                        
                        mediaRecorder.ondataavailable = (event) => {{
                            if (event.data.size > 0) {{
                                recordedChunks.push(event.data);
                            }}
                        }};

                        mediaRecorder.onstop = () => {{
                            clearInterval(timerInterval);
                            const blob = new Blob(recordedChunks, {{ type: "video/webm" }});
                            const url = URL.createObjectURL(blob);
                            downloadLink.href = url;
                            downloadArea.style.display = "block";
                            statusDiv.innerText = "Status: Recording finished. File ready for download.";
                            startBtn.disabled = false;
                            stopBtn.disabled = true;
                            stopBtn.style.background = "#64748B";
                            stopBtn.style.cursor = "not-allowed";
                            
                            // Stop all video tracks
                            stream.getTracks().forEach(track => track.stop());
                        }};

                        // When user clicks browser's native 'Stop sharing'
                        stream.getVideoTracks()[0].onended = () => {{
                            if (mediaRecorder && mediaRecorder.state !== "inactive") {{
                                mediaRecorder.stop();
                            }}
                        }};

                        mediaRecorder.start(1000);
                        startTime = Date.now();
                        timerInterval = setInterval(updateTimer, 1000);

                        startBtn.disabled = true;
                        stopBtn.disabled = false;
                        stopBtn.style.background = "#C62828";
                        stopBtn.style.cursor = "pointer";
                        statusDiv.innerText = "Status: 🔴 Recording display active...";
                        timerDiv.style.display = "block";
                        downloadArea.style.display = "none";
                    }} catch (err) {{
                        statusDiv.innerText = "Error / Cancelled: " + err.message;
                        console.error(err);
                    }}
                }};

                stopBtn.onclick = () => {{
                    if (mediaRecorder && mediaRecorder.state !== "inactive") {{
                        mediaRecorder.stop();
                    }}
                }};
                </script>
                """,
                height=165,
            )

        # --- Section 3: Quick Actions (Export & Copy) ---
        with rcol_actions:
            st.markdown(f"**Quick Actions**")
            cur_res = st.session_state.get("last_result")
            if cur_res:
                # 1. Export Markdown file
                md_data = generate_markdown_export(cur_res)
                st.download_button(
                    label="📥 Export Result (.md)",
                    data=md_data,
                    file_name="research_investigation_report.md",
                    mime="text/markdown",
                    use_container_width=True,
                    help="Download complete formatted Markdown report",
                )

                # 2. Copy Answer to Clipboard
                ans_text = f"{cur_res.get('short_answer', '')}\n\n{cur_res.get('detailed_analysis', '')}"
                escaped_ans = json.dumps(ans_text)
                components.html(
                    f"""
                    <button id="copyBtn" style="width: 100%; background: {surface_elevated}; color: {text_primary}; border: 1px solid {border_color}; padding: 0.45rem 0.6rem; border-radius: 6px; font-weight: 500; font-size: 0.82rem; cursor: pointer;">
                        📋 Copy Answer to Clipboard
                    </button>
                    <div id="copyNotice" style="font-size: 0.78rem; color: #2E7D32; margin-top: 0.3rem; display: none; text-align: center;">
                        ✓ Answer copied to clipboard!
                    </div>
                    <script>
                    document.getElementById("copyBtn").onclick = async () => {{
                        const text = {escaped_ans};
                        try {{
                            await navigator.clipboard.writeText(text);
                            const n = document.getElementById("copyNotice");
                            n.style.display = "block";
                            setTimeout(() => {{ n.style.display = "none"; }}, 3000);
                        }} catch (err) {{
                            alert("Clipboard access error: " + err);
                        }}
                    }};
                    </script>
                    """,
                    height=65,
                )
            else:
                st.info("Run an inquiry to enable Export & Copy actions.")

        st.markdown(f"<hr style='border-color: var(--border-color); margin-top: 0.5rem;'>", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# 5. SAMPLE RESEARCH QUESTIONS (CLICK TO RUN)
# ---------------------------------------------------------------------
EXAMPLE_QUESTIONS = [
    "Compare the top three open-source vector databases for a startup building RAG products.",
    "Find five Indian B2B SaaS startups in HR technology and summarize their positioning.",
    "Explain the advantages and disadvantages of multi-agent architecture for customer support automation.",
    "Compare different approaches to implementing memory in an AI support agent.",
]

st.markdown("**Sample Research Inquiries:** *(Click any inquiry to immediately populate and launch research)*")
cols = st.columns(len(EXAMPLE_QUESTIONS))
for idx, ex_q in enumerate(EXAMPLE_QUESTIONS):
    with cols[idx]:
        if st.button(ex_q[:34] + "...", key=f"btn_ex_{idx}", help=ex_q, use_container_width=True):
            st.session_state["research_question"] = ex_q
            st.session_state["auto_run"] = True
            st.rerun()

# Inquiry Input Box
user_question = st.text_area(
    "What topic or technical question would you like to investigate?",
    value=st.session_state.get("research_question", ""),
    height=90,
    placeholder="e.g. Compare the latency, indexing algorithms, and deployment trade-offs of Qdrant and Milvus for production RAG.",
    key="input_text_box",
)

col_run, col_clear_input, col_spacer = st.columns([1.5, 1.5, 5])
with col_run:
    run_btn = st.button("Conduct Research", type="primary", use_container_width=True)
with col_clear_input:
    if st.button("Clear Input Text", use_container_width=True):
        st.session_state["research_question"] = ""
        st.session_state["auto_run"] = False
        st.rerun()

# Trigger search either by manual button click or by auto_run from sample question click
should_execute = run_btn or st.session_state.get("auto_run", False)

# ---------------------------------------------------------------------
# 6. WORKFLOW EXECUTION
# ---------------------------------------------------------------------
if should_execute:
    st.session_state["auto_run"] = False
    
    q_to_run = (user_question or st.session_state.get("research_question", "")).strip()
    if not q_to_run:
        st.warning("Please type a research question or select one of the suggested inquiries above.")
    elif len(q_to_run) < 5:
        st.warning("Please enter a question with at least 5 characters.")
    else:
        st.session_state["research_question"] = q_to_run
        
        if q_to_run not in st.session_state["query_history"]:
            st.session_state["query_history"].append(q_to_run)

        with st.status("Conducting Grounded Research Workflow...", expanded=True) as status_box:
            st.write("• Analyzing inquiry and formulating structured research plan...")
            time.sleep(0.3)
            st.write("• Selecting research tools and dispatching targeted queries...")
            time.sleep(0.3)
            st.write("• Retrieving external evidence and parsing candidate web pages...")

            result = execute_research_request(
                question=q_to_run,
                max_sources=max_sources,
                include_scraping=include_scraping,
            )

            if result:
                st.write("• Filtering duplicates, stripping tracking tokens, and ranking sources...")
                st.write("• Auditing citation grounding and assembling final report...")
                status_box.update(label="Research Complete", state="complete", expanded=False)
                st.session_state["last_result"] = result
            else:
                status_box.update(label="Research Incomplete", state="error", expanded=True)


# ---------------------------------------------------------------------
# 7. RESULTS PRESENTATION
# ---------------------------------------------------------------------
if st.session_state.get("last_result"):
    res = st.session_state["last_result"]
    st.markdown("---")

    # Executive Summary Card
    st.markdown("### Executive Summary")
    st.markdown(f'<div class="summary-card">{res.get("short_answer", "")}</div>', unsafe_allow_html=True)

    # Confidence and Evidence Quality Rating
    conf = res.get("confidence_level", "Medium")
    conf_class = f"conf-{conf.lower()}"
    st.markdown(
        f"""
        <div style="margin-bottom: 1.5rem; display: flex; align-items: baseline; gap: 0.75rem;">
            <strong>Confidence Assessment:</strong>
            <span class="{conf_class}">{conf} Confidence</span>
            <span style="color: var(--text-muted); font-size: 0.95rem;">{res.get('confidence_explanation', '')}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Key Findings Cards with Source Tokens
    findings = res.get("key_findings", [])
    if findings:
        st.subheader("Key Findings")
        for f in findings:
            tags_html = "".join([f'<span class="source-badge">{s_id}</span>' for s_id in f.get("supporting_source_ids", [])])
            st.markdown(
                f"""
                <div class="finding-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                        <strong style="font-size: 1.05rem; color: var(--text-primary);">{f.get('claim')}</strong>
                        <div>{tags_html}</div>
                    </div>
                    <div style="line-height: 1.55; font-size: 0.98rem; color: var(--text-primary);">
                        {f.get('detail')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # In-Depth Analysis (Markdown, tables, structured prose)
    st.subheader("Detailed Analysis")
    st.markdown(res.get("detailed_analysis", ""))

    # Tabbed Deep-Dives
    st.markdown("---")
    tab_sources, tab_plan, tab_limits, tab_trace = st.tabs([
        f"Verified Sources ({len(res.get('sources_used', []))})",
        "Research Plan",
        "Assumptions & Limitations",
        "Execution Trace",
    ])

    with tab_sources:
        sources = res.get("sources_used", [])
        if sources:
            for s in sources:
                with st.expander(f"{s.get('id')} — {s.get('title')} ({s.get('domain')})"):
                    st.markdown(f"**Source URL:** [{s.get('url')}]({s.get('url')})")
                    st.markdown(f"**Retrieval Status:** `{s.get('retrieval_status')}`")
                    st.markdown(f"**Relevance:** {s.get('relevance_note') or 'Verified topical match'}")
                    if s.get("snippet"):
                        st.markdown(f"**Search Snippet:**  \n> {s.get('snippet')}")
                    if s.get("extracted_text"):
                        st.markdown("**Extracted Content Excerpt:**")
                        st.text(s.get("extracted_text")[:2500] + ("..." if len(s.get("extracted_text")) > 2500 else ""))
        else:
            st.info("No external sources were retained for this inquiry.")

    with tab_plan:
        plan = res.get("research_plan", {})
        st.markdown(f"**Objective:** {plan.get('objective', '')}")
        subqs = plan.get("subquestions", [])
        if subqs:
            st.markdown("**Subquestions:**")
            for sq in subqs:
                st.markdown(f"- {sq}")

        steps = plan.get("steps", [])
        if steps:
            st.markdown("**Workflow Steps:**")
            for step in steps:
                st.markdown(
                    f"**Step {step.get('step_number')}: {step.get('title')}** `[{step.get('status', 'completed')}]`  \n"
                    f"*{step.get('description')}* (Tool: `{step.get('tool_to_use') or 'N/A'}`)"
                )

    with tab_limits:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Assumptions Made:**")
            for a in res.get("assumptions", []):
                st.markdown(f"- {a}")
        with col_b:
            st.markdown("**Identified Limitations:**")
            for limit in res.get("limitations", []):
                st.markdown(f"- {limit}")

        st.markdown("**Suggested Follow-Up Steps:**")
        for step in res.get("suggested_next_steps", []):
            st.markdown(f"1. {step}")

        warnings = res.get("warnings", [])
        if warnings:
            st.warning("**Execution Notices:**  \n" + "\n".join([f"- {w}" for w in warnings]))

    with tab_trace:
        trace = res.get("execution_trace", [])
        if trace:
            trace_table = [
                {
                    "Stage": t.get("stage"),
                    "Status": t.get("status"),
                    "Detail": t.get("message"),
                    "Duration (ms)": t.get("duration_ms"),
                    "Timestamp": t.get("timestamp"),
                }
                for t in trace
            ]
            st.dataframe(trace_table, use_container_width=True)
        else:
            st.caption("No execution trace available.")

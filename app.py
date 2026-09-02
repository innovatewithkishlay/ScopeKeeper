"""ScopeKeeper - a small UI on top of the same agent used in the notebook.

Run with:
    streamlit run app.py

This does not duplicate any agent logic - it just calls ScopeKeeperAgent()
from src/agent.py, the exact same class the notebook demo uses.
"""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from agent import ScopeKeeperAgent  # noqa: E402

st.set_page_config(page_title="ScopeKeeper", page_icon=None, layout="wide")

# ---------------------------------------------------------------------------
# Styling - same palette as the architecture diagram in the notebook, so the
# UI and the diagram read as one product instead of two disconnected pieces.
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@600;700&display=swap');

    :root {
        --paper: #f5f1e8;
        --ink: #2a2a28;
        --muted: #7a7468;
        --blue: #1a4fa0;
        --purple: #6b2fb3;
        --teal: #177a56;
        --orange: #c9701a;
        --red: #b23b2f;
        --hair: #e2dcc8;
    }

    .stApp { background: var(--paper); color: var(--ink); }
    #MainMenu, footer, header { visibility: hidden; }

    h1.sk-title {
        font-family: 'Source Serif 4', Georgia, serif;
        font-weight: 700;
        font-size: 2.1rem;
        margin-bottom: 0;
        color: var(--ink);
    }
    p.sk-tagline {
        color: var(--muted);
        font-size: 1.02rem;
        margin-top: 4px;
        margin-bottom: 22px;
    }
    hr.sk-rule { border: none; border-top: 1.5px solid var(--ink); margin: 0 0 26px 0; width: 220px; }

    .sk-card {
        background: white;
        border: 1.6px solid var(--hair);
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 14px;
    }
    .sk-card.blue { border-color: var(--blue); }
    .sk-card.purple { border-color: var(--purple); }

    .sk-label {
        font-size: 0.72rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        font-weight: 600;
        margin-bottom: 6px;
    }

    .sk-badge {
        display: inline-block;
        padding: 5px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.03em;
    }
    .sk-badge.LOW { background: #e4f2ea; color: var(--teal); }
    .sk-badge.MODERATE { background: #fdf1de; color: var(--orange); }
    .sk-badge.HIGH { background: #fbe4d9; color: #b2531a; }
    .sk-badge.CRITICAL { background: #fbe3e0; color: var(--red); }

    .sk-metric-row {
        display: flex;
        justify-content: space-between;
        padding: 7px 0;
        border-bottom: 1px solid var(--hair);
        font-size: 0.92rem;
    }
    .sk-metric-row:last-child { border-bottom: none; }
    .sk-metric-row .v { font-weight: 700; font-variant-numeric: tabular-nums; }

    .sk-bubble-client {
        background: #fdf3e8;
        border-left: 3px solid var(--purple);
        border-radius: 0 8px 8px 0;
        padding: 10px 14px;
        margin: 10px 0 4px 0;
        font-size: 0.92rem;
    }
    .sk-bubble-agent {
        background: white;
        border-left: 3px solid var(--orange);
        border-radius: 0 8px 8px 0;
        padding: 10px 14px;
        margin: 4px 0 14px 0;
        font-size: 0.92rem;
    }
    .sk-chip {
        font-size: 0.68rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--muted);
        font-weight: 700;
        margin-bottom: 4px;
    }

    /* Keep the right-hand status panel in view as the left conversation
       column grows and the page scrolls, instead of it sliding out of
       sight above the fold. align-self:flex-start is required alongside
       position:sticky here - without it Streamlit stretches the column to
       match the taller sibling, which leaves no scroll room for "sticky"
       to actually stick within. */
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-of-type(2) {
        position: sticky;
        top: 1rem;
        align-self: flex-start;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<h1 class="sk-title">ScopeKeeper</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="sk-tagline">Tell it the deal. It watches every request after that for scope creep.</p>',
    unsafe_allow_html=True,
)
st.markdown('<hr class="sk-rule">', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "agent" not in st.session_state:
    st.session_state.agent = None
if "log" not in st.session_state:
    st.session_state.log = []  # list of (role, text) tuples

# ---------------------------------------------------------------------------
# Setup form (only shown before a project exists)
# ---------------------------------------------------------------------------
if st.session_state.agent is None:
    saved_projects = ScopeKeeperAgent.list_saved_projects()
    if saved_projects:
        st.markdown('<div class="sk-card purple">', unsafe_allow_html=True)
        st.markdown('<div class="sk-label">Resume a previous project</div>', unsafe_allow_html=True)
        st.caption("These were saved to a real database file (scopekeeper.db) - they survive closing this app completely.")
        for row in saved_projects:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(
                    f"**{row['name']}** &middot; {row['currency']} {row['budget']:,.0f} "
                    f"&middot; {row['request_count']} request(s) logged &middot; "
                    f"<span style='color:var(--muted)'>saved {row['created_at']}</span>",
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("Resume", key=f"resume_{row['id']}"):
                    try:
                        agent = ScopeKeeperAgent()
                    except RuntimeError as exc:
                        st.error(str(exc))
                        st.stop()
                    agent.load_project(row["id"])
                    st.session_state.agent = agent
                    st.session_state.log = []
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="sk-card blue">', unsafe_allow_html=True)
    st.markdown('<div class="sk-label">Or start a new project</div>', unsafe_allow_html=True)

    with st.form("setup_form"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Project name", "Restaurant marketing website")
            budget = st.number_input("Budget (INR)", min_value=0, value=80000, step=1000)
        with col2:
            hours = st.number_input("Estimated hours", min_value=1, value=20, step=1)
            currency = st.text_input("Currency", "INR")

        deliverables = st.text_area(
            "Deliverables (one per line)",
            "Home page\nAbout page\nMenu page\nContact page\nGallery page",
            height=110,
        )
        exclusions = st.text_area(
            "Explicitly excluded (one per line)",
            "online ordering\nuser accounts\npayment processing\nstaff or admin tools",
            height=90,
        )
        submitted = st.form_submit_button("Start project")

    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        try:
            agent = ScopeKeeperAgent()
        except RuntimeError as exc:
            st.error(str(exc))
            st.stop()
        agent.start_project(
            name=name,
            objective=name,
            budget=budget,
            estimated_hours=hours,
            currency=currency,
            deliverables=[d.strip() for d in deliverables.splitlines() if d.strip()],
            exclusions=[e.strip() for e in exclusions.splitlines() if e.strip()],
        )
        st.session_state.agent = agent
        st.session_state.log = []
        st.rerun()

    st.stop()

# ---------------------------------------------------------------------------
# Main view - project is running
# ---------------------------------------------------------------------------
agent = st.session_state.agent
state = agent.state

left, right = st.columns([2, 1], gap="large")

with left:
    st.markdown('<div class="sk-label">Conversation</div>', unsafe_allow_html=True)

    for role, text in st.session_state.log:
        if role == "client":
            st.markdown(f'<div class="sk-chip">Client request</div><div class="sk-bubble-client">{text}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="sk-chip">Agent</div><div class="sk-bubble-agent">{text}</div>', unsafe_allow_html=True)

    with st.form("request_form", clear_on_submit=True):
        user_input = st.text_input("New client request, or ask a question like 'are we drifting?'", "")
        col_send, col_proposal = st.columns([1, 1])
        send = col_send.form_submit_button("Send")
        draft = col_proposal.form_submit_button("Draft a change-order proposal instead")

    if (send or draft) and (user_input.strip() or draft):
        if draft:
            message = (
                "Draft a short, professional change-order proposal for the client, based on the "
                "actual requests and numbers logged so far - not a hypothetical."
            )
            st.session_state.log.append(("client", "(requested a change-order proposal)"))
        else:
            message = user_input.strip()
            if message.lower().startswith(("new client", "add ", "can ")):
                message = f"New client request: {message}"
            st.session_state.log.append(("client", user_input.strip()))

        with st.spinner("Thinking..."):
            answer = agent.run(message)
        st.session_state.log.append(("agent", answer))
        st.rerun()

with right:
    st.markdown('<div class="sk-card">', unsafe_allow_html=True)
    st.markdown('<div class="sk-label">The deal</div>', unsafe_allow_html=True)
    st.markdown(f"**{state.name}**")
    st.markdown(f"{state.currency} {state.budget:,.0f} &middot; {state.estimated_hours}h estimated", unsafe_allow_html=True)
    st.markdown("Included: " + ", ".join(state.deliverables))
    st.markdown("Excluded: " + ", ".join(state.exclusions))
    st.markdown("</div>", unsafe_allow_html=True)

    status = agent.tools.get_scope_status()
    cumulative = status["cumulative"]
    level = cumulative["drift_level"]

    st.markdown('<div class="sk-card">', unsafe_allow_html=True)
    st.markdown('<div class="sk-label">Scope status</div>', unsafe_allow_html=True)
    st.markdown(f'<span class="sk-badge {level}">{level} DRIFT</span>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    rows = [
        ("Requests logged", cumulative["total_requests"]),
        ("Extra hours", cumulative["extra_hours"]),
        ("Over original estimate", f"{cumulative['percentage_increase']:.0f}%"),
        ("Out of scope", cumulative["out_of_scope_count"]),
        ("Partially in scope", cumulative["partially_in_scope_count"]),
        ("Needs clarification", cumulative["needs_clarification_count"]),
        ("Drift score", f"{cumulative['drift_score']:.1f} / 100"),
    ]
    for label, value in rows:
        st.markdown(
            f'<div class="sk-metric-row"><span>{label}</span><span class="v">{value}</span></div>',
            unsafe_allow_html=True,
        )
    if cumulative["capability_groups"]:
        st.markdown('<div class="sk-label" style="margin-top:12px;">New capabilities introduced</div>', unsafe_allow_html=True)
        st.markdown(", ".join(cumulative["capability_groups"]))
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Start a new project"):
        st.session_state.agent = None
        st.session_state.log = []
        st.rerun()

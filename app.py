import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import anthropic
import os
import numpy as np
import random
from datetime import datetime, timedelta

# ── AUTO-GENERATE DATABASE IF IT DOESN'T EXIST ───────────────────────────────
def generate_database():
    np.random.seed(42)
    random.seed(42)
    START_DATE = datetime(2024, 1, 1)
    END_DATE   = datetime(2024, 12, 31)
    NUM_SHIPMENTS = 1200

    carriers = [
        {"carrier_id": "C001", "name": "Atlas Freight",     "type": "Full Truckload", "region": "National"},
        {"carrier_id": "C002", "name": "Maple Express",     "type": "LTL",            "region": "Eastern"},
        {"carrier_id": "C003", "name": "Northern Logistics","type": "Full Truckload", "region": "National"},
        {"carrier_id": "C004", "name": "Swift Carriers",    "type": "LTL",            "region": "Western"},
        {"carrier_id": "C005", "name": "Coastal Transport", "type": "Intermodal",     "region": "Atlantic"},
    ]
    routes = [
        {"route_id": "R001", "origin": "Toronto, ON",   "destination": "Montreal, QC",      "distance_km": 541,  "region": "Eastern"},
        {"route_id": "R002", "origin": "Vancouver, BC", "destination": "Calgary, AB",        "distance_km": 970,  "region": "Western"},
        {"route_id": "R003", "origin": "Montreal, QC",  "destination": "Halifax, NS",        "distance_km": 1139, "region": "Atlantic"},
        {"route_id": "R004", "origin": "Toronto, ON",   "destination": "Winnipeg, MB",       "distance_km": 2093, "region": "Central"},
        {"route_id": "R005", "origin": "Calgary, AB",   "destination": "Edmonton, AB",       "distance_km": 300,  "region": "Western"},
        {"route_id": "R006", "origin": "Halifax, NS",   "destination": "Charlottetown, PEI", "distance_km": 277,  "region": "Atlantic"},
        {"route_id": "R007", "origin": "Ottawa, ON",    "destination": "Toronto, ON",        "distance_km": 448,  "region": "Eastern"},
        {"route_id": "R008", "origin": "Winnipeg, MB",  "destination": "Regina, SK",         "distance_km": 573,  "region": "Central"},
    ]
    product_categories = ["Grocery", "Electronics", "Apparel", "Home & Garden", "Pharmacy", "Frozen Foods"]
    carrier_profiles = {
        "C001": {"otd_base": 0.92, "cost_base": 2.10, "delay_hours_mean": 3},
        "C002": {"otd_base": 0.85, "cost_base": 1.75, "delay_hours_mean": 6},
        "C003": {"otd_base": 0.95, "cost_base": 2.40, "delay_hours_mean": 2},
        "C004": {"otd_base": 0.88, "cost_base": 1.90, "delay_hours_mean": 5},
        "C005": {"otd_base": 0.78, "cost_base": 1.60, "delay_hours_mean": 9},
    }
    def random_date(start, end):
        return start + timedelta(days=random.randint(0, (end - start).days))

    shipments = []
    for i in range(1, NUM_SHIPMENTS + 1):
        carrier   = random.choice(carriers)
        route     = random.choice(routes)
        profile   = carrier_profiles[carrier["carrier_id"]]
        ship_date = random_date(START_DATE, END_DATE)
        transit_days   = max(1, int(route["distance_km"] / 600))
        sched_delivery = ship_date + timedelta(days=transit_days)
        anomaly_period = datetime(2024, 3, 4) <= ship_date <= datetime(2024, 3, 17)
        is_anomaly     = anomaly_period and carrier["carrier_id"] == "C005" and route["region"] == "Atlantic"
        otd_rate  = 0.45 if is_anomaly else profile["otd_base"]
        on_time   = np.random.rand() < otd_rate
        delay_hours = 0
        if not on_time:
            delay_multiplier = 3.5 if is_anomaly else 1.0
            delay_hours = max(1, int(np.random.exponential(profile["delay_hours_mean"] * delay_multiplier)))
        actual_delivery = sched_delivery + timedelta(hours=delay_hours)
        base_cost   = route["distance_km"] * profile["cost_base"]
        weight_kg   = random.randint(100, 5000)
        cost_noise  = np.random.normal(1.0, 0.08)
        total_cost  = round(base_cost * cost_noise * (1 + weight_kg / 20000), 2)
        cost_per_km = round(total_cost / route["distance_km"], 4)
        dwell_hours = round(max(0.5, np.random.exponential(4) + (8 if is_anomaly else 0)), 1)
        shipments.append({
            "shipment_id": f"SHP{i:04d}", "carrier_id": carrier["carrier_id"],
            "route_id": route["route_id"], "product_category": random.choice(product_categories),
            "ship_date": ship_date.strftime("%Y-%m-%d"), "ship_month": ship_date.strftime("%Y-%m"),
            "scheduled_delivery": sched_delivery.strftime("%Y-%m-%d"),
            "actual_delivery": actual_delivery.strftime("%Y-%m-%d"),
            "on_time": int(on_time), "delay_hours": delay_hours, "weight_kg": weight_kg,
            "total_cost_cad": total_cost, "cost_per_km": cost_per_km,
            "dwell_hours": dwell_hours, "is_anomaly_period": int(is_anomaly), "status": "Delivered",
        })
    df_shipments = pd.DataFrame(shipments)
    scorecards = []
    for (carrier_id, month), grp in df_shipments.groupby(["carrier_id", "ship_month"]):
        scorecards.append({
            "carrier_id": carrier_id, "month": month,
            "total_shipments": len(grp), "otd_rate": round(grp["on_time"].mean(), 4),
            "avg_delay_hours": round(grp["delay_hours"].mean(), 2),
            "avg_cost_per_km": round(grp["cost_per_km"].mean(), 4),
            "avg_dwell_hours": round(grp["dwell_hours"].mean(), 2),
            "total_cost_cad": round(grp["total_cost_cad"].sum(), 2),
        })
    conn = sqlite3.connect("transportation.db")
    pd.DataFrame(carriers).to_sql("carriers",             conn, if_exists="replace", index=False)
    pd.DataFrame(routes).to_sql("routes",                 conn, if_exists="replace", index=False)
    df_shipments.to_sql("shipments",                      conn, if_exists="replace", index=False)
    pd.DataFrame(scorecards).to_sql("carrier_scorecards", conn, if_exists="replace", index=False)
    conn.close()

if not os.path.exists("transportation.db"):
    generate_database()

st.set_page_config(
    page_title="Transportation Intelligence Assistant",
    page_icon="🚚",
    layout="wide",
)

# ── GLOBAL CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .section-label {
    font-size: 11px; font-weight: 600; color: #888; text-transform: uppercase;
    letter-spacing: 0.07em; margin-bottom: 12px; margin-top: 8px;
  }
  .snap-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 28px; }
  .snap-card {
    background: #1e1e1e; border: 0.5px solid #333; border-radius: 10px; padding: 14px 16px;
  }
  .snap-label { font-size: 11px; color: #888; margin-bottom: 4px; }
  .snap-val { font-size: 22px; font-weight: 600; color: #f0f0f0; line-height: 1.1; }
  .snap-delta { font-size: 11px; margin-top: 3px; }

  .scorecard-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 16px; }
  .carrier-card {
    background: #1a1a1a; border: 0.5px solid #333;
    border-radius: 0 10px 10px 0; padding: 14px;
  }
  .carrier-card.green { border-left: 3px solid #639922; }
  .carrier-card.amber { border-left: 3px solid #EF9F27; }
  .carrier-card.red   { border-left: 3px solid #E24B4A; }
  .carrier-name { font-size: 12px; font-weight: 600; color: #e0e0e0; margin-bottom: 4px; }
  .status-pill {
    font-size: 10px; font-weight: 600; padding: 2px 8px;
    border-radius: 20px; display: inline-block; margin-bottom: 10px;
  }
  .pill-green { background: #1a2e0a; color: #8dc63f; }
  .pill-amber { background: #2e1f0a; color: #f5a623; }
  .pill-red   { background: #2e0a0a; color: #e24b4a; }
  .otd-big { font-size: 28px; font-weight: 700; line-height: 1; margin-bottom: 4px; }
  .otd-bar-bg { height: 4px; background: #333; border-radius: 2px; margin-bottom: 12px; }
  .otd-bar-fill { height: 4px; border-radius: 2px; }
  .stat-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 4px 0; border-bottom: 0.5px solid #2a2a2a;
  }
  .stat-row:last-child { border-bottom: none; }
  .stat-label { font-size: 11px; color: #777; }
  .stat-val   { font-size: 12px; font-weight: 500; color: #ccc; }

  .alert-bar {
    background: #1f0a0a; border: 0.5px solid #5a1a1a; border-radius: 8px;
    padding: 12px 16px; display: flex; align-items: flex-start; gap: 10px; margin-bottom: 24px;
  }
  .alert-icon { font-size: 16px; color: #e24b4a; margin-top: 1px; flex-shrink: 0; }
  .alert-title { font-size: 13px; font-weight: 600; color: #e24b4a; }
  .alert-text  { font-size: 12px; color: #b06060; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

DB_PATH = "transportation.db"

@st.cache_data
def get_db_schema():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    schema_parts = []
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        cols = [f"  {r[1]} ({r[2]})" for r in cur.fetchall()]
        schema_parts.append(f"TABLE {t}:\n" + "\n".join(cols))
    conn.close()
    return "\n\n".join(schema_parts)

def run_query(sql):
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql(sql, conn)
    finally:
        conn.close()
    return df

def get_claude_client():
    api_key = os.getenv("ANTHROPIC_API_KEY") or st.session_state.get("api_key", "")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)

def ask_claude(system_prompt, user_message, max_tokens=1000):
    client = get_claude_client()
    if not client:
        return "Please enter your Anthropic API key in the sidebar."
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return msg.content[0].text

def nl_to_sql(question):
    schema = get_db_schema()
    system = f"""You are a SQL expert for a Canadian transportation analytics database.
Convert the user's question into a valid SQLite SQL query.
Return ONLY the SQL query — no explanation, no markdown, no backticks.

Database schema:
{schema}

Key rules:
- on_time = 1 means delivered on time, 0 means late
- OTD rate = AVG(on_time) * 100 as a percentage
- cost_per_km is in CAD
- ship_month format is 'YYYY-MM'
- Always JOIN carriers and routes tables when names are needed
"""
    sql = ask_claude(system, question).strip()
    if sql.startswith("```"):
        sql = "\n".join(sql.split("\n")[1:-1])
    return sql

def explain_result(question, sql, df):
    system = """You are a senior transportation analyst.
Write 2-3 clear plain-English sentences of insight about the results.
Focus on operational meaning. Be specific with numbers. Do not restate the question."""
    user = f"Question: {question}\nSQL: {sql}\nResults:\n{df.head(10).to_string(index=False)}"
    return ask_claude(system, user, max_tokens=300)

def explain_anomaly(df_anomaly):
    system = """You are a senior transportation analyst. A statistical anomaly has been detected.
Write 2-3 sentences explaining what this anomaly looks like and suggest 2 likely operational causes.
Be direct and specific."""
    return ask_claude(system, df_anomaly.to_string(index=False), max_tokens=300)

def generate_sop(process_description):
    system = """You are a transportation operations manager writing Standard Operating Procedures.
Format as a clean SOP with:
- Purpose
- Scope
- Roles and Responsibilities
- Step-by-step Procedure (numbered)
- Key Metrics / Acceptance Criteria
Use clear, concise language."""
    return ask_claude(system, process_description, max_tokens=600)

def status_class(otd):
    if otd >= 90:   return "green", "pill-green", "On track"
    elif otd >= 85: return "amber", "pill-amber", "Watch"
    else:           return "red",   "pill-red",   "At risk"

def otd_color(otd):
    if otd >= 90:   return "#8dc63f"
    elif otd >= 85: return "#f5a623"
    else:           return "#e24b4a"

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Configuration")
    api_key_input = st.text_input("Anthropic API Key", type="password",
                                   help="Get yours at console.anthropic.com")
    if api_key_input:
        st.session_state["api_key"] = api_key_input
        st.success("API key saved")
    st.markdown("---")
    st.caption("1,200 shipments · 5 carriers · 8 routes · 2024")
    st.markdown("---")
    st.markdown("**Built by:** Your Name")
    st.markdown("**Stack:** Python · Streamlit · Claude API · SQLite")

# ── HEADER ────────────────────────────────────────────────────────────────────
st.title("Transportation Intelligence Assistant")
st.caption("Ask questions in plain English — powered by Claude AI")

tab1, tab2, tab3, tab4 = st.tabs(["KPI Dashboard", "AI Query", "Anomaly Detection", "SOP Generator"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — KPI DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:

    df_all = run_query("SELECT * FROM shipments")
    otd_pct     = df_all["on_time"].mean() * 100
    total       = len(df_all)
    avg_delay   = df_all[df_all["delay_hours"] > 0]["delay_hours"].mean()
    avg_cost    = df_all["cost_per_km"].mean()
    total_spend = df_all["total_cost_cad"].sum()

    # ── SECTION 1: NETWORK SNAPSHOT ───────────────────────────────────────────
    delta_color = "#8dc63f" if otd_pct >= 85 else "#e24b4a"
    delta_sign  = "+" if otd_pct >= 85 else ""
    st.markdown(f"""
    <div class="section-label">Network snapshot — 2024</div>
    <div class="snap-grid">
      <div class="snap-card">
        <div class="snap-label">Overall OTD rate</div>
        <div class="snap-val">{otd_pct:.1f}%</div>
        <div class="snap-delta" style="color:{delta_color};">{delta_sign}{otd_pct-85:.1f}% vs 85% target</div>
      </div>
      <div class="snap-card">
        <div class="snap-label">Total shipments</div>
        <div class="snap-val">{total:,}</div>
        <div class="snap-delta" style="color:#888;">Jan – Dec 2024</div>
      </div>
      <div class="snap-card">
        <div class="snap-label">Avg delay (when late)</div>
        <div class="snap-val">{avg_delay:.1f} hrs</div>
        <div class="snap-delta" style="color:#888;">Late shipments only</div>
      </div>
      <div class="snap-card">
        <div class="snap-label">Avg cost / km</div>
        <div class="snap-val">${avg_cost:.2f}</div>
        <div class="snap-delta" style="color:#888;">CAD</div>
      </div>
      <div class="snap-card">
        <div class="snap-label">Total freight spend</div>
        <div class="snap-val">${total_spend/1e6:.2f}M</div>
        <div class="snap-delta" style="color:#888;">CAD 2024</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── SECTION 2: CARRIER SCORECARD ──────────────────────────────────────────
    df_sc = run_query("""
        SELECT c.name as carrier,
               ROUND(AVG(s.on_time)*100,1)    as otd_pct,
               ROUND(AVG(s.delay_hours),1)    as avg_delay,
               ROUND(AVG(s.cost_per_km),2)    as cost_per_km,
               ROUND(AVG(s.dwell_hours),1)    as avg_dwell,
               COUNT(*)                        as shipments,
               ROUND(SUM(s.total_cost_cad),0) as total_spend
        FROM shipments s JOIN carriers c ON s.carrier_id=c.carrier_id
        GROUP BY c.name ORDER BY otd_pct DESC
    """)

    cards_html = '<div class="section-label">Carrier scorecard</div><div class="scorecard-grid">'
    for _, row in df_sc.iterrows():
        card_cls, pill_cls, label = status_class(row["otd_pct"])
        color = otd_color(row["otd_pct"])
        otd_color_val = "#e24b4a" if card_cls == "red" else "#f0f0f0"
        cards_html += f"""
        <div class="carrier-card {card_cls}">
          <div class="carrier-name">{row['carrier']}</div>
          <span class="status-pill {pill_cls}">{label}</span>
          <div class="otd-big" style="color:{otd_color_val};">{row['otd_pct']}%</div>
          <div class="otd-bar-bg">
            <div class="otd-bar-fill" style="width:{row['otd_pct']}%; background:{color};"></div>
          </div>
          <div class="stat-row"><span class="stat-label">Cost / km</span><span class="stat-val">${row['cost_per_km']}</span></div>
          <div class="stat-row"><span class="stat-label">Avg delay</span><span class="stat-val">{row['avg_delay']} hrs</span></div>
          <div class="stat-row"><span class="stat-label">Shipments</span><span class="stat-val">{int(row['shipments']):,}</span></div>
        </div>"""
    cards_html += "</div>"

    worst = df_sc.iloc[-1]
    gap   = round(85 - worst["otd_pct"], 1)
    cards_html += f"""
    <div class="alert-bar">
      <div class="alert-icon">⚠</div>
      <div>
        <div class="alert-title">Action required — {worst['carrier']}</div>
        <div class="alert-text">OTD at {worst['otd_pct']}% is {gap} points below the 85% network target.
        Average delay of {worst['avg_delay']} hrs. Recommend scheduling a performance review.</div>
      </div>
    </div>"""

    st.markdown(cards_html, unsafe_allow_html=True)

    # ── SECTION 3: CHARTS ROW 1 ───────────────────────────────────────────────
    st.markdown('<div class="section-label">Performance vs target</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)

    df_trend = run_query("""
        SELECT STRFTIME('%Y-%m', ship_date) as month,
               ROUND(AVG(on_time)*100,1)    as network_otd,
               ROUND(SUM(total_cost_cad),0) as monthly_spend
        FROM shipments GROUP BY month ORDER BY month
    """)

    with col_a:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_trend["month"], y=df_trend["network_otd"],
            mode="lines+markers", name="OTD rate",
            line=dict(color="#378ADD", width=2), marker=dict(size=5)
        ))
        fig.add_hline(y=85, line_dash="dash", line_color="#e24b4a",
                      annotation_text="85% target", annotation_position="bottom right",
                      annotation_font_color="#e24b4a")
        fig.update_layout(
            title="Network OTD rate vs 85% target",
            yaxis=dict(range=[70, 100], title="OTD %"),
            xaxis_title="", margin=dict(l=0,r=0,t=40,b=0), height=280,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", title_font_color="#e0e0e0"
        )
        fig.update_xaxes(gridcolor="#2a2a2a")
        fig.update_yaxes(gridcolor="#2a2a2a")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        fig2 = go.Figure(go.Bar(
            x=df_trend["month"], y=df_trend["monthly_spend"],
            marker_color="#378ADD", opacity=0.85
        ))
        fig2.update_layout(
            title="Monthly freight spend (CAD)",
            yaxis_title="CAD", xaxis_title="",
            margin=dict(l=0,r=0,t=40,b=0), height=280,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", title_font_color="#e0e0e0"
        )
        fig2.update_xaxes(gridcolor="#2a2a2a")
        fig2.update_yaxes(gridcolor="#2a2a2a")
        st.plotly_chart(fig2, use_container_width=True)

    # ── SECTION 4: CHARTS ROW 2 ───────────────────────────────────────────────
    st.markdown('<div class="section-label">Value for money & delay patterns</div>', unsafe_allow_html=True)
    col_c, col_d = st.columns(2)

    with col_c:
        fig3 = px.scatter(
            df_sc, x="cost_per_km", y="otd_pct", text="carrier", size="shipments",
            color="otd_pct", color_continuous_scale="RdYlGn",
            labels={"cost_per_km": "Avg cost per km (CAD)", "otd_pct": "OTD rate (%)"},
        )
        fig3.add_hline(y=85, line_dash="dash", line_color="#555",
                       annotation_text="85% target", annotation_font_color="#888")
        fig3.update_traces(textposition="top center", textfont_color="#ccc")
        fig3.update_layout(
            title="Cost per km vs OTD rate",
            coloraxis_showscale=False,
            margin=dict(l=0,r=0,t=40,b=0), height=300,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", title_font_color="#e0e0e0"
        )
        fig3.update_xaxes(gridcolor="#2a2a2a")
        fig3.update_yaxes(gridcolor="#2a2a2a")
        st.plotly_chart(fig3, use_container_width=True)
        st.caption("Ideal: top-left (low cost, high OTD). Bubble size = shipment volume.")

    with col_d:
        df_heat = run_query("""
            SELECT c.name as carrier, r.region,
                   ROUND(AVG(s.delay_hours),1) as avg_delay
            FROM shipments s
            JOIN carriers c ON s.carrier_id=c.carrier_id
            JOIN routes r ON s.route_id=r.route_id
            WHERE s.delay_hours > 0
            GROUP BY c.name, r.region
        """)
        df_pivot = df_heat.pivot(index="carrier", columns="region", values="avg_delay").fillna(0)
        fig4 = px.imshow(df_pivot, color_continuous_scale="Reds",
                         labels=dict(color="Avg delay (hrs)"), aspect="auto")
        fig4.update_layout(
            title="Delay heatmap — carrier vs region",
            margin=dict(l=0,r=0,t=40,b=0), height=300,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", title_font_color="#e0e0e0",
            xaxis_title="", yaxis_title=""
        )
        st.plotly_chart(fig4, use_container_width=True)
        st.caption("Darker = longer average delays. Shows where each carrier struggles geographically.")

    # ── SECTION 5: ROUTE TABLE ────────────────────────────────────────────────
    st.markdown('<div class="section-label">Route performance</div>', unsafe_allow_html=True)
    df_routes = run_query("""
        SELECT r.origin || ' → ' || r.destination as route,
               r.region,
               COUNT(*)                           as shipments,
               ROUND(AVG(s.on_time)*100,1)        as otd_pct,
               ROUND(AVG(s.cost_per_km),2)        as cost_per_km,
               ROUND(AVG(s.delay_hours),1)        as avg_delay_hrs,
               r.distance_km
        FROM shipments s JOIN routes r ON s.route_id=r.route_id
        GROUP BY r.route_id ORDER BY otd_pct ASC
    """)
    st.dataframe(df_routes, use_container_width=True, hide_index=True)

    # ── SECTION 6: AI EXECUTIVE SUMMARY ──────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-label">AI executive summary</div>', unsafe_allow_html=True)
    st.caption("Claude reads all KPIs and writes a management briefing in seconds.")
    if st.button("Generate executive summary", type="primary"):
        summary_data = f"""
Network OTD: {otd_pct:.1f}% | Target: 85% | Shipments: {total:,} | Spend: ${total_spend:,.0f}
Carrier scorecards:
{df_sc[['carrier','otd_pct','cost_per_km','avg_delay','shipments']].to_string(index=False)}
Route performance:
{df_routes[['route','otd_pct','cost_per_km','avg_delay_hrs']].to_string(index=False)}
"""
        with st.spinner("Writing executive summary..."):
            summary = ask_claude(
                """You are a senior transportation analyst writing a weekly executive briefing.
Write a concise 4-5 sentence management summary covering:
1. Overall network health
2. Top performing carrier and why they stand out
3. Carrier requiring immediate attention and recommended action
4. Most problematic route
5. One strategic recommendation
Be direct, specific with numbers, and executive in tone.""",
                summary_data, max_tokens=400
            )
        st.info(summary)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — AI QUERY
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Ask your data anything")
    st.caption("Type a question in plain English — Claude converts it to SQL and explains the answer.")

    example_qs = [
        "Which carrier had the worst on-time rate in Q3?",
        "Top 3 most expensive routes by cost per km?",
        "Compare dwell time across all carriers",
        "How many shipments were delayed over 24 hours?",
        "Which product category had the most late deliveries?",
    ]
    st.markdown("**Try an example:**")
    cols = st.columns(len(example_qs))
    for i, q in enumerate(example_qs):
        if cols[i].button(q, key=f"ex_{i}"):
            st.session_state["nl_question"] = q

    question = st.text_input("Your question",
                              value=st.session_state.get("nl_question", ""),
                              placeholder="e.g. Which carrier had the worst on-time rate last quarter?")
    if st.button("Run query", type="primary") and question:
        with st.spinner("Converting to SQL..."):
            sql = nl_to_sql(question)
        st.markdown("**Generated SQL:**")
        st.code(sql, language="sql")
        try:
            df_result = run_query(sql)
            st.markdown("**Results:**")
            st.dataframe(df_result, use_container_width=True)
            with st.spinner("Generating insight..."):
                st.success(explain_result(question, sql, df_result))
        except Exception as e:
            st.error(f"SQL error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ANOMALY DETECTION
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Anomaly detection")
    st.caption("Statistical outliers in carrier performance — Claude explains likely causes.")

    df_monthly = run_query("""
        SELECT c.name as carrier, cs.month, cs.otd_rate, cs.avg_delay_hours,
               cs.avg_cost_per_km, cs.total_shipments
        FROM carrier_scorecards cs JOIN carriers c ON cs.carrier_id=c.carrier_id
        ORDER BY carrier, month
    """)

    anomalies = []
    for carrier, grp in df_monthly.groupby("carrier"):
        mean = grp["otd_rate"].mean()
        std  = grp["otd_rate"].std()
        if std == 0:
            continue
        for _, row in grp.iterrows():
            z = (row["otd_rate"] - mean) / std
            if abs(z) > 1.5:
                anomalies.append({**row.to_dict(), "z_score": round(z, 2)})

    if anomalies:
        df_anom = pd.DataFrame(anomalies)
        st.markdown(f"**{len(df_anom)} anomalies detected**")
        fig = px.scatter(df_monthly, x="month", y="otd_rate", color="carrier",
                         title="Monthly OTD rates — anomalies flagged in red")
        fig.add_scatter(x=df_anom["month"], y=df_anom["otd_rate"],
                        mode="markers", marker=dict(color="red", size=12, symbol="x"),
                        name="Anomaly")
        fig.update_layout(
            margin=dict(l=0,r=0,t=40,b=0), height=320,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", title_font_color="#e0e0e0"
        )
        fig.update_xaxes(gridcolor="#2a2a2a")
        fig.update_yaxes(gridcolor="#2a2a2a")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            df_anom[["carrier","month","otd_rate","avg_delay_hours","total_shipments","z_score"]],
            use_container_width=True
        )
        if st.button("AI: explain these anomalies", type="primary"):
            with st.spinner("Analysing..."):
                st.info(explain_anomaly(
                    df_anom[["carrier","month","otd_rate","avg_delay_hours","z_score"]]
                ))

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — SOP GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("SOP generator")
    st.caption("Describe a process — Claude formats a Standard Operating Procedure.")

    examples = {
        "Carrier escalation": "When a carrier's on-time delivery rate drops below 80% for two consecutive weeks, the transportation analyst should flag the carrier, notify the account manager, schedule a performance review call, and document the corrective action plan.",
        "New carrier onboarding": "When adding a new carrier, collect insurance documents, set up their profile in Salesforce, assign user permissions, run a pilot shipment on a low-risk route, and review their first 30-day performance scorecard.",
        "Shipment delay response": "When a shipment is flagged as delayed more than 12 hours, identify the cause, contact the carrier dispatcher, update the customer ETA, and log the delay reason code for monthly reporting.",
    }
    ex_cols = st.columns(3)
    for i, (label, text) in enumerate(examples.items()):
        if ex_cols[i].button(label, key=f"sop_{i}"):
            st.session_state["sop_input"] = text

    process_text = st.text_area(
        "Describe the process",
        value=st.session_state.get("sop_input", ""),
        height=150,
        placeholder="Describe the transportation process in plain language...",
    )
    if st.button("Generate SOP", type="primary") and process_text:
        with st.spinner("Generating SOP..."):
            sop = generate_sop(process_text)
        st.markdown("---")
        st.markdown(sop)
        st.download_button("Download SOP (.txt)", sop, file_name="SOP_draft.txt")

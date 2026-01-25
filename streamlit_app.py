"""
Worksuite Marketing Dashboard
=============================

An all-in-one marketing analytics dashboard for Worksuite.

Integrates:
- Google Ads
- LinkedIn Ads
- Attio CRM
- HubSpot Marketing
- LLM Search Results Tracking

Run with: streamlit run streamlit_app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from typing import Optional

# Import marketing modules
from marketing.config import get_config, MarketingConfig
from marketing.demo_data import generate_all_demo_data

# Page configuration
st.set_page_config(
    page_title="Worksuite Marketing Dashboard",
    page_icon="W",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* Metric cards */
    [data-testid="metric-container"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 1rem;
    }

    /* Headers */
    h1 {
        color: #1a1a2e;
        font-weight: 600;
    }

    h2 {
        color: #2d3748;
        font-size: 1.5rem;
        font-weight: 500;
        margin-top: 2rem;
    }

    h3 {
        color: #4a5568;
        font-size: 1.1rem;
        font-weight: 500;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }

    /* Integration status badges */
    .integration-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
        display: inline-block;
        margin: 0.25rem;
    }

    .badge-connected {
        background-color: #d4edda;
        color: #155724;
    }

    .badge-demo {
        background-color: #fff3cd;
        color: #856404;
    }

    .badge-disconnected {
        background-color: #f8d7da;
        color: #721c24;
    }

    /* Campaign table */
    .campaign-row {
        padding: 0.75rem;
        border-bottom: 1px solid #e9ecef;
    }

    /* Insight cards */
    .insight-card {
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }

    .insight-opportunity {
        background-color: #e7f5ff;
        border-left: 4px solid #339af0;
    }

    .insight-strength {
        background-color: #d3f9d8;
        border-left: 4px solid #40c057;
    }

    .insight-threat {
        background-color: #ffe3e3;
        border-left: 4px solid #fa5252;
    }
</style>
""", unsafe_allow_html=True)


def format_number(num: float, prefix: str = "", suffix: str = "") -> str:
    """Format large numbers with K/M suffixes"""
    if num >= 1_000_000:
        return f"{prefix}{num/1_000_000:.1f}M{suffix}"
    elif num >= 1_000:
        return f"{prefix}{num/1_000:.1f}K{suffix}"
    else:
        return f"{prefix}{num:.0f}{suffix}"


def format_currency(amount: float) -> str:
    """Format as currency"""
    return format_number(amount, prefix="$")


def get_integration_status_html(config: MarketingConfig) -> str:
    """Generate HTML for integration status badges"""
    status = config.get_status()

    badges = []

    integrations = [
        ("Google Ads", status["google_ads"]),
        ("LinkedIn Ads", status["linkedin_ads"]),
        ("Attio", status["attio"]),
        ("HubSpot", status["hubspot"]),
        ("LLM Tracking", status["llm_tracking"]),
    ]

    for name, is_connected in integrations:
        if status["demo_mode"]:
            badge_class = "badge-demo"
            icon = "Demo"
        elif is_connected:
            badge_class = "badge-connected"
            icon = "Connected"
        else:
            badge_class = "badge-disconnected"
            icon = "Not Connected"

        badges.append(f'<span class="integration-badge {badge_class}">{name}: {icon}</span>')

    return " ".join(badges)


def render_sidebar():
    """Render the sidebar with filters and settings"""
    st.sidebar.image("https://worksuite.com/wp-content/uploads/2023/06/worksuite-logo-dark.svg",
                     width=180, use_container_width=False)

    st.sidebar.markdown("---")

    # Date range filter
    st.sidebar.subheader("Date Range")

    date_preset = st.sidebar.selectbox(
        "Quick Select",
        ["Last 7 days", "Last 30 days", "Last 90 days", "Last 6 months", "Custom"],
        index=3
    )

    today = date.today()

    if date_preset == "Last 7 days":
        start_date = today - timedelta(days=7)
        end_date = today
    elif date_preset == "Last 30 days":
        start_date = today - timedelta(days=30)
        end_date = today
    elif date_preset == "Last 90 days":
        start_date = today - timedelta(days=90)
        end_date = today
    elif date_preset == "Last 6 months":
        start_date = today - timedelta(days=180)
        end_date = today
    else:
        col1, col2 = st.sidebar.columns(2)
        start_date = col1.date_input("Start", today - timedelta(days=30))
        end_date = col2.date_input("End", today)

    st.sidebar.markdown("---")

    # Channel filter
    st.sidebar.subheader("Channels")

    channels = {
        "Google Ads": st.sidebar.checkbox("Google Ads", value=True),
        "LinkedIn Ads": st.sidebar.checkbox("LinkedIn Ads", value=True),
        "Attio CRM": st.sidebar.checkbox("Attio CRM", value=True),
        "HubSpot": st.sidebar.checkbox("HubSpot Marketing", value=True),
        "LLM Tracking": st.sidebar.checkbox("LLM Search Tracking", value=True),
    }

    st.sidebar.markdown("---")

    # Settings
    st.sidebar.subheader("Settings")

    config = get_config()

    demo_mode = st.sidebar.toggle(
        "Demo Mode",
        value=config.demo_mode,
        help="Use sample data when integrations are not configured"
    )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "channels": channels,
        "demo_mode": demo_mode,
    }


def render_header(config: MarketingConfig):
    """Render the page header"""
    col1, col2 = st.columns([3, 1])

    with col1:
        st.title("All-in-one Marketing Dashboard")
        st.markdown(
            "Track performance across all marketing channels in one place. "
            "Compare data from Google Ads, LinkedIn Ads, HubSpot, Attio CRM, and AI search visibility."
        )

    with col2:
        if config.demo_mode:
            st.info("Running in Demo Mode")

    # Integration status
    st.markdown(get_integration_status_html(config), unsafe_allow_html=True)


def render_summary_metrics(data: dict):
    """Render the top-level summary metrics"""
    st.markdown("## All Channels")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Users",
            value=format_number(data["summary"]["total_users"]),
            delta="+12.3%",
        )

    with col2:
        st.metric(
            label="Total Revenue",
            value=format_currency(data["summary"]["total_revenue"]),
            delta="+8.7%",
        )

    with col3:
        total_spend = data["summary"]["total_ad_spend"]
        st.metric(
            label="Total Ad Spend",
            value=format_currency(total_spend),
            delta="-3.2%",
        )

    with col4:
        # Calculate ROAS
        if total_spend > 0:
            roas = data["summary"]["total_revenue"] / total_spend
            st.metric(
                label="ROAS",
                value=f"{roas:.1f}x",
                delta="+0.3x",
            )
        else:
            st.metric(label="ROAS", value="N/A")


def render_users_revenue_chart(data: dict):
    """Render the combined users and revenue chart"""
    users_df = pd.DataFrame(data["daily_metrics"]["users"])
    revenue_df = pd.DataFrame(data["daily_metrics"]["revenue"])

    # Merge dataframes
    df = users_df.merge(revenue_df, on="date", suffixes=("_users", "_revenue"))
    df["date"] = pd.to_datetime(df["date"])

    # Create figure with secondary y-axis
    fig = go.Figure()

    # Users bars
    fig.add_trace(go.Bar(
        x=df["date"],
        y=df["value_users"],
        name="Total Users",
        marker_color="#4285F4",
        yaxis="y"
    ))

    # Revenue line
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["value_revenue"],
        name="Total Revenue",
        line=dict(color="#DB4437", width=2),
        yaxis="y2"
    ))

    fig.update_layout(
        title="Users & Revenue Over Time",
        xaxis_title="",
        yaxis=dict(
            title="Users",
            side="left",
            showgrid=True,
            gridcolor="#f0f0f0",
        ),
        yaxis2=dict(
            title="Revenue ($)",
            side="right",
            overlaying="y",
            showgrid=False,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        hovermode="x unified",
        plot_bgcolor="white",
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_traffic_sources(data: dict):
    """Render the traffic sources pie chart"""
    sources = data["traffic_sources"]

    df = pd.DataFrame(sources)

    fig = px.pie(
        df,
        values="value",
        names="name",
        hole=0.6,
        color_discrete_sequence=["#4285F4", "#B8442E", "#D4A84B", "#6CB043", "#8884d8", "#82ca9d"]
    )

    fig.update_layout(
        title="Top Traffic Sources",
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05
        ),
        height=350,
    )

    fig.update_traces(
        textposition='inside',
        textinfo='percent',
        hovertemplate='<b>%{label}</b><br>%{percent}<extra></extra>'
    )

    st.plotly_chart(fig, use_container_width=True)


def render_paid_channels(data: dict, channels: dict):
    """Render the paid channels section"""
    st.markdown("## Paid Channels")

    if channels.get("Google Ads", True):
        with st.expander("Google Ads", expanded=True):
            google_data = data["google_ads"]

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Spend", format_currency(google_data["summary"]["total_spend"]))
            with col2:
                st.metric("Clicks", format_number(google_data["summary"]["total_clicks"]))
            with col3:
                st.metric("Conversions", format_number(google_data["summary"]["total_conversions"]))
            with col4:
                st.metric("Avg CTR", f"{google_data['summary']['avg_ctr']:.2f}%")

            # Campaigns table
            st.markdown("### Campaigns")
            campaigns_df = pd.DataFrame(google_data["campaigns"])
            campaigns_df = campaigns_df[["name", "status", "impressions", "clicks", "spend", "conversions", "ctr"]]
            campaigns_df.columns = ["Campaign", "Status", "Impressions", "Clicks", "Spend ($)", "Conversions", "CTR (%)"]
            st.dataframe(campaigns_df, use_container_width=True, hide_index=True)

    if channels.get("LinkedIn Ads", True):
        with st.expander("LinkedIn Ads", expanded=True):
            linkedin_data = data["linkedin_ads"]

            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Spend", format_currency(linkedin_data["summary"]["total_spend"]))
            with col2:
                st.metric("Clicks", format_number(linkedin_data["summary"]["total_clicks"]))
            with col3:
                st.metric("Conversions", format_number(linkedin_data["summary"]["total_conversions"]))
            with col4:
                st.metric("Leads", format_number(linkedin_data["summary"]["total_leads"]))

            # Campaigns table
            st.markdown("### Campaigns")
            campaigns_df = pd.DataFrame(linkedin_data["campaigns"])
            campaigns_df = campaigns_df[["name", "status", "impressions", "clicks", "spend", "leads", "ctr"]]
            campaigns_df.columns = ["Campaign", "Status", "Impressions", "Clicks", "Spend ($)", "Leads", "CTR (%)"]
            st.dataframe(campaigns_df, use_container_width=True, hide_index=True)


def render_crm_section(data: dict, channels: dict):
    """Render the CRM and Marketing sections"""
    col1, col2 = st.columns(2)

    with col1:
        if channels.get("Attio CRM", True):
            st.markdown("## Attio CRM")
            attio_data = data["attio_crm"]

            # Metrics
            m1, m2 = st.columns(2)
            with m1:
                st.metric("New Contacts", format_number(attio_data["new_contacts"]))
                st.metric("New Companies", format_number(attio_data["new_companies"]))
            with m2:
                st.metric("New Deals", format_number(attio_data["new_deals"]))
                st.metric("Deal Value", format_currency(attio_data["deal_value"]))

            # Pipeline chart
            pipeline_df = pd.DataFrame(attio_data["pipeline_stages"])
            fig = px.funnel(pipeline_df, x="count", y="stage", title="Sales Pipeline")
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if channels.get("HubSpot", True):
            st.markdown("## HubSpot Marketing")
            hubspot_data = data["hubspot"]

            # Metrics
            m1, m2 = st.columns(2)
            with m1:
                st.metric("Emails Sent", format_number(hubspot_data["emails_sent"]))
                st.metric("Form Submissions", format_number(hubspot_data["form_submissions"]))
            with m2:
                st.metric("New Contacts", format_number(hubspot_data["new_contacts"]))
                open_rate = hubspot_data["emails_opened"] / hubspot_data["emails_sent"] * 100 if hubspot_data["emails_sent"] > 0 else 0
                st.metric("Email Open Rate", f"{open_rate:.1f}%")

            # Lifecycle stages chart
            lifecycle_df = pd.DataFrame(hubspot_data["lifecycle_stages"])
            fig = px.bar(lifecycle_df, x="stage", y="count", title="Contact Lifecycle Stages")
            fig.update_layout(height=300, xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)


def render_llm_tracking(data: dict, channels: dict):
    """Render the LLM search tracking section"""
    if not channels.get("LLM Tracking", True):
        return

    st.markdown("## AI Search Visibility")
    st.markdown("Track how Worksuite appears in AI-powered search results (Perplexity, ChatGPT, Claude)")

    llm_data = data["llm_tracking"]

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Queries Tracked",
            llm_data["total_queries_tracked"]
        )

    with col2:
        st.metric(
            "Brand Mention Rate",
            f"{llm_data['mention_rate']}%",
            help="Percentage of tracked queries where Worksuite was mentioned"
        )

    with col3:
        st.metric(
            "Positive Sentiment",
            f"{llm_data['positive_sentiment_rate']}%",
            help="Percentage of mentions with positive sentiment"
        )

    with col4:
        avg_pos = llm_data.get("avg_position")
        st.metric(
            "Avg Position",
            f"#{avg_pos:.1f}" if avg_pos else "N/A",
            help="Average position when mentioned in lists"
        )

    # Two columns for competitors and insights
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Top Competitors in AI Search")
        competitors_df = pd.DataFrame(llm_data["top_competitors"])
        fig = px.bar(
            competitors_df,
            x="mentions",
            y="name",
            orientation="h",
            title="Competitor Mentions"
        )
        fig.update_layout(height=250, yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### AI Insights")
        for insight in llm_data["insights"]:
            insight_type = insight["type"]
            icon = {"opportunity": "eye", "strength": "check-circle", "threat": "exclamation-triangle"}.get(insight_type, "info")
            color = {"opportunity": "blue", "strength": "green", "threat": "red"}.get(insight_type, "gray")

            st.markdown(
                f"""
                <div class="insight-card insight-{insight_type}">
                    <strong>{insight_type.title()}</strong><br>
                    {insight["message"]}
                </div>
                """,
                unsafe_allow_html=True
            )

    # Query results table
    with st.expander("View Tracked Queries"):
        results_df = pd.DataFrame(llm_data["results"])
        results_df["brand_mentioned"] = results_df["brand_mentioned"].apply(lambda x: "Yes" if x else "No")
        results_df["competitors"] = results_df["competitors_mentioned"].apply(lambda x: ", ".join(x) if x else "-")
        results_df = results_df[["query", "platform", "brand_mentioned", "brand_position", "sentiment", "competitors"]]
        results_df.columns = ["Query", "Platform", "Mentioned", "Position", "Sentiment", "Competitors"]
        st.dataframe(results_df, use_container_width=True, hide_index=True)


def render_configuration_guide():
    """Render a configuration guide in the sidebar"""
    with st.sidebar.expander("Configuration Guide"):
        st.markdown("""
        ### Setting Up Integrations

        Create a `.env` file with your API credentials:

        **Google Ads:**
        ```
        GOOGLE_ADS_DEVELOPER_TOKEN=xxx
        GOOGLE_ADS_CLIENT_ID=xxx
        GOOGLE_ADS_CLIENT_SECRET=xxx
        GOOGLE_ADS_REFRESH_TOKEN=xxx
        GOOGLE_ADS_CUSTOMER_ID=xxx
        ```

        **LinkedIn Ads:**
        ```
        LINKEDIN_ADS_ACCESS_TOKEN=xxx
        LINKEDIN_ADS_ACCOUNT_ID=xxx
        ```

        **Attio CRM:**
        ```
        ATTIO_API_KEY=xxx
        ```

        **HubSpot:**
        ```
        HUBSPOT_API_KEY=xxx
        ```

        **LLM Tracking:**
        ```
        PERPLEXITY_API_KEY=xxx
        OPENAI_API_KEY=xxx
        ANTHROPIC_API_KEY=xxx
        ```

        Set `MARKETING_DEMO_MODE=false` to use real data.
        """)


def main():
    """Main dashboard entry point"""
    config = get_config()

    # Render sidebar and get filters
    filters = render_sidebar()

    # Render configuration guide
    render_configuration_guide()

    # Render header
    render_header(config)

    st.markdown("---")

    # Load data (demo or real)
    data = generate_all_demo_data(
        start_date=filters["start_date"],
        end_date=filters["end_date"]
    )

    # Render summary metrics
    render_summary_metrics(data)

    st.markdown("---")

    # Main content area - Users/Revenue chart and Traffic sources
    col1, col2 = st.columns([2, 1])

    with col1:
        render_users_revenue_chart(data)

    with col2:
        render_traffic_sources(data)

    st.markdown("---")

    # Paid channels section
    render_paid_channels(data, filters["channels"])

    st.markdown("---")

    # CRM and Marketing section
    render_crm_section(data, filters["channels"])

    st.markdown("---")

    # LLM Search Tracking section
    render_llm_tracking(data, filters["channels"])

    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888; padding: 1rem;'>"
        "Worksuite Marketing Dashboard v1.0 | "
        f"Data refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        "Powered by Streamlit"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

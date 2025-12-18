import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import urllib.request
import ssl
import certifi
import io
from PIL import Image

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
Y_STRETCH = 1.75

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(
    layout="wide",
    page_title="9.6 Acres Plot Dashboard"
)

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------
@st.cache_data(ttl=1800)
def load_data():
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    url = (
        "https://docs.google.com/spreadsheets/d/"
        "1ADwkUAqU01wxVoYEnJh2hhZVdeqaFcaOAgeUZP5P-kw"
        "/export?format=csv"
    )

    with urllib.request.urlopen(url, context=ssl_context) as response:
        csv_bytes = response.read()

    df = pd.read_csv(io.BytesIO(csv_bytes))

    df["Plot_Number"] = df["Plot_Number"].astype(str)
    df["Plot_Size"] = pd.to_numeric(df["Plot_Size"], errors="coerce")
    df["Sold_Amount"] = pd.to_numeric(df["Sold_Amount"], errors="coerce").fillna(0)
    df["X_pct"] = pd.to_numeric(df["X_pct"], errors="coerce") * (3742 / 4425)
    df["Y_pct"] = pd.to_numeric(df["Y_pct"], errors="coerce") * Y_STRETCH
    df["Sold_Date"] = pd.to_datetime(df["Sold_Date"], format="%d/%m/%y", errors="coerce")

    return df


df = load_data()

# -------------------------------------------------
# DATE FILTER (GLOBAL)
# -------------------------------------------------
sold_dates = df["Sold_Date"].dropna()

min_date = sold_dates.min()
max_date = sold_dates.max()

# -------------------------------------------------
# IMAGE
# -------------------------------------------------
bg_image = Image.open("9.6_ACRES.jpg")

# -------------------------------------------------
# OWNER COLORS
# -------------------------------------------------
owner_palette = {
    "BRINDAVAN ASSETS HOLDINGS": "#1f77b4",
    "SAUKHYADA INFRA LLP": "#ff7f0e",
    "S.V. INFRA": "#2ca02c"
}

df["Owner_Color"] = df["Owner_Name"].map(owner_palette).fillna("#999999")
owner_counts = df["Owner_Name"].value_counts().to_dict()

# -------------------------------------------------
# PAGE TITLE (TOP CENTER)
# -------------------------------------------------
total_land_all = df["Plot_Size"].sum()
sold_land_all = df[df["Status"] == "Sold"]["Plot_Size"].sum()
sold_pct_all = 0 if total_land_all == 0 else (sold_land_all / total_land_all) * 100

st.markdown(
    f"""
    <h2 style="text-align:center; margin-bottom:20px;">
        Plot 1 – 9.6 Acres – Total Percentage of Land Sold {sold_pct_all:.2f}%
    </h2>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------
# LAYOUT
# -------------------------------------------------
plot_col, legend_col = st.columns([8, 2])

# -------------------------------------------------
# LEGEND + DATE FILTER
# -------------------------------------------------
with legend_col:
    st.markdown("### Filter by Sold Date")

    date_range = st.slider(
        "Sold Date Range",
        min_value=min_date.date(),
        max_value=max_date.date(),
        value=(min_date.date(), max_date.date())
    )

    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

    st.markdown("---")
    st.markdown("### Legend")
    st.markdown("**Owner (toggle visibility)**")

    selected_owners = []

    for owner, color in owner_palette.items():
        total_plots = owner_counts.get(owner, 0)

        dot_col, check_col = st.columns([1, 6])

        with dot_col:
            st.markdown(
                f"""
                <div style="
                    width:14px;
                    height:14px;
                    background:{color};
                    border-radius:50%;
                    margin-top:6px;">
                </div>
                """,
                unsafe_allow_html=True
            )

        with check_col:
            if st.checkbox(f"{owner} ({total_plots})", value=True, key=f"owner_{owner}"):
                selected_owners.append(owner)

    st.markdown("---")
    st.markdown("**Status**")
    st.markdown(
        """
        <div style="display:flex; align-items:center;">
            <span style="font-size:18px; font-weight:bold; color:#8B0000; margin-right:8px;">✖</span>
            <span>Sold Plot</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")
    # -------------------------------------------------
    # SOLD SUMMARY TABLE (INCLUDES ZERO ROWS)
    # -------------------------------------------------
    st.markdown("**Sold Summary (Live)**")

    # Base table = all selected owners
    base = pd.DataFrame({"Owner": selected_owners})

    # Sold-only aggregation
    sold_agg = (
        df[
            (df["Status"] == "Sold") &
            (df["Owner_Name"].isin(selected_owners))
        ]
        .groupby("Owner_Name", as_index=False)
        .agg(
            Sold_Plots=("Plot_Number", "count"),
            Total_Sold_Amount=("Sold_Amount", "sum")
        )
        .rename(columns={"Owner_Name": "Owner"})
    )

    # Left join so unsold owners remain
    summary = base.merge(sold_agg, on="Owner", how="left")

    summary["Sold_Plots"] = summary["Sold_Plots"].fillna(0).astype(int)
    summary["Total_Sold_Amount"] = summary["Total_Sold_Amount"].fillna(0)

    # TOTAL ROW
    total_row = pd.DataFrame({
        "Owner": ["TOTAL"],
        "Sold_Plots": [summary["Sold_Plots"].sum()],
        "Total_Sold_Amount": [summary["Total_Sold_Amount"].sum()]
    })

    summary = pd.concat([summary, total_row], ignore_index=True)

    # Formatting
    summary["Total_Sold_Amount"] = summary["Total_Sold_Amount"].map(
        lambda x: f"₹{x:,.0f}"
    )

    st.dataframe(summary, hide_index=True, width='stretch')

# -------------------------------------------------
# APPLY DATE + OWNER FILTERS
# -------------------------------------------------
df_filtered = df[
    (
        (df["Sold_Date"].isna()) |
        ((df["Sold_Date"] >= start_date) & (df["Sold_Date"] <= end_date))
    ) &
    (df["Owner_Name"].isin(selected_owners))
]

# -------------------------------------------------
# SCATTER PLOT
# -------------------------------------------------
with plot_col:
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df_filtered["X_pct"],
            y=df_filtered["Y_pct"],
            mode="markers",
            marker=dict(
                size=df_filtered["Plot_Size"] / 40,
                color=df_filtered["Owner_Color"],
                opacity=0.75,
                line=dict(width=1, color="white")
            ),
            customdata=df_filtered[
                ["Plot_Number", "Plot_Size", "Owner_Name", "Status", "Sold_Date", "Sold_Amount"]
            ],
            hovertemplate=(
                "<b>Plot %{customdata[0]}</b><br>"
                "Size: %{customdata[1]} sft<br>"
                "Owner: %{customdata[2]}<br>"
                "Status: %{customdata[3]}<br>"
                "Sold Date: %{customdata[4]|%d %b %Y}<br>"
                "Sold Amount: ₹%{customdata[5]:,.0f}"
                "<extra></extra>"
            ),
            showlegend=False
        )
    )

    sold = df_filtered[df_filtered["Status"] == "Sold"]

    fig.add_trace(
        go.Scatter(
            x=sold["X_pct"],
            y=sold["Y_pct"],
            mode="markers",
            marker=dict(
                symbol="x",
                size=10,
                color="#8B0000",
                line=dict(width=3)
            ),
            hoverinfo="skip",
            showlegend=False
        )
    )

    fig.update_layout(
        xaxis=dict(range=[0, 100], visible=False, fixedrange=True),
        yaxis=dict(range=[0, 100 * Y_STRETCH], visible=False, fixedrange=True),
        images=[
            dict(
                source=bg_image,
                xref="x",
                yref="y",
                x=0,
                y=100 * Y_STRETCH,
                sizex=100,
                sizey=100 * Y_STRETCH,
                layer="below"
            )
        ],
        height=1500,
        margin=dict(l=0, r=0, t=10, b=0)
    )

    st.plotly_chart(fig, width='stretch')

# # -------------------------------------------------
# # REFRESH
# # -------------------------------------------------
# if st.button("🔄 Refresh data"):
#     st.cache_data.clear()
#     st.experimental_rerun()

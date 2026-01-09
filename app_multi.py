import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import urllib.request
import ssl
import certifi
import io
from PIL import Image

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(
    layout="wide",
    page_title="Plot Dashboards"
)

# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------
@st.cache_data(ttl=1800)
def load_data(sheet_gid=None):
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        # Base URL with optional sheet ID
        if sheet_gid:
            url = (
                f"https://docs.google.com/spreadsheets/d/"
                f"1ADwkUAqU01wxVoYEnJh2hhZVdeqaFcaOAgeUZP5P-kw"
                f"/export?format=csv&gid={sheet_gid}"
            )
        else:
            url = (
                "https://docs.google.com/spreadsheets/d/"
                "1ADwkUAqU01wxVoYEnJh2hhZVdeqaFcaOAgeUZP5P-kw"
                "/export?format=csv"
            )

        # Add timeout and retry logic
        max_retries = 3
        timeout = 30  # seconds
        
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(url, context=ssl_context, timeout=timeout) as response:
                    csv_bytes = response.read()
                break  # Success, exit retry loop
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < max_retries - 1:
                    st.warning(f"⏳ Connection attempt {attempt + 1} failed, retrying...")
                    continue
                else:
                    raise Exception(
                        f"Failed after {max_retries} attempts. "
                        f"Please check your internet connection or try again later. "
                        f"Error: {str(e)}"
                    )

        df = pd.read_csv(io.BytesIO(csv_bytes))

        # Validate required columns
        required_cols = ["Plot_Number", "Plot_Size", "Sold_Amount", "X_pixel", "Y_pixel", "Sold_Date", "Owner_Name", "Status"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            st.error(f"Missing columns in Google Sheet: {', '.join(missing_cols)}")
            st.stop()

        df["Plot_Number"] = df["Plot_Number"].astype(str)
        df["Plot_Size"] = pd.to_numeric(df["Plot_Size"], errors="coerce")
        df["Sold_Amount"] = pd.to_numeric(df["Sold_Amount"], errors="coerce").fillna(0)
        df["X_pixel"] = pd.to_numeric(df["X_pixel"], errors="coerce")
        df["Y_pixel"] = pd.to_numeric(df["Y_pixel"], errors="coerce")
        df["Sold_Date"] = pd.to_datetime(df["Sold_Date"], format="%d/%m/%y", errors="coerce")

        return df
    except Exception as e:
        st.error(f"❌ Failed to load data from Google Sheets: {str(e)}")
        st.info("💡 **Troubleshooting tips:**\n"
                "- Check your internet connection\n"
                "- Verify the Google Sheet is publicly accessible\n"
                "- Try refreshing the page\n"
                "- Check if Google services are available in your region")
        st.stop()


# -------------------------------------------------
# DASHBOARD FUNCTION
# -------------------------------------------------
def render_dashboard(df, bg_image_path, plot_title, owner_palette):
    """Render the complete dashboard for a given dataset"""
    
    # -------------------------------------------------
    # IMAGE + DIMENSIONS (CRITICAL)
    # -------------------------------------------------
    try:
        bg_image = Image.open(bg_image_path)
        img_width, img_height = bg_image.size
    except FileNotFoundError:
        st.error(f"❌ Background image '{bg_image_path}' not found in the project directory.")
        st.stop()

    # Convert image coords → plot coords
    df = df.copy()
    df["X_plot"] = df["X_pixel"]
    df["Y_plot"] = img_height - df["Y_pixel"]

    # -------------------------------------------------
    # PLOT SIZE RANGE
    # -------------------------------------------------
    min_plot_size = df["Plot_Size"].min()
    max_plot_size = df["Plot_Size"].max()

    # -------------------------------------------------
    # DATE FILTER
    # -------------------------------------------------
    sold_dates = df["Sold_Date"].dropna()
    if len(sold_dates) == 0:
        st.warning("No sold plots with dates found.")
        return
    min_date = sold_dates.min()
    max_date = sold_dates.max()

    # -------------------------------------------------
    # OWNER COLORS
    # -------------------------------------------------
    df["Owner_Color"] = df["Owner_Name"].map(owner_palette).fillna("#999999")
    owner_counts = df["Owner_Name"].value_counts().to_dict()

    # -------------------------------------------------
    # PAGE HEADER
    # -------------------------------------------------
    total_land = df["Plot_Size"].sum()
    sold_land = df[df["Status"] == "Sold"]["Plot_Size"].sum()
    sold_pct = 0 if total_land == 0 else (sold_land / total_land) * 100

    # Try to load logo
    try:
        logo_image = Image.open("Gemini_Generated_logo.png")
        logo_col, title_col = st.columns([1, 9])
        with logo_col:
            st.image(logo_image, width=120)
        with title_col:
            st.markdown(
                f"""
                <h2 style="text-align:center; margin-bottom:20px; margin-top:30px;">
                    {plot_title} – Total Percentage of Land Sold {sold_pct:.2f}%
                </h2>
                """,
                unsafe_allow_html=True
            )
    except FileNotFoundError:
        # If logo not found, just show title
        st.markdown(
            f"""
            <h2 style="text-align:center; margin-bottom:20px;">
                {plot_title} – Total Percentage of Land Sold {sold_pct:.2f}%
            </h2>
            """,
            unsafe_allow_html=True
        )

    # -------------------------------------------------
    # QUICK STATS (HORIZONTAL)
    # -------------------------------------------------
    total_plots = len(df)
    sold_plots = len(df[df["Status"] == "Sold"])
    unsold_plots = total_plots - sold_plots
    sold_land_area = df[df["Status"] == "Sold"]["Plot_Size"].sum()
    remaining_land_area = df["Plot_Size"].sum() - sold_land_area

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Total Plots", total_plots)
    with col2:
        st.metric("✅ Sold Plots", sold_plots)
    with col3:
        st.metric("🟢 Available Plots", unsold_plots)
    with col4:
        st.metric("📐 Remaining Land", f"{remaining_land_area:,.0f} sft")

    st.markdown("---")

    # -------------------------------------------------
    # LAYOUT
    # -------------------------------------------------
    plot_col, legend_col = st.columns([8, 2])

    # -------------------------------------------------
    # LEGEND + FILTERS
    # -------------------------------------------------
    with legend_col:
        st.markdown("### 🔍 Filters")
        
        # Reset filters button
        if st.button("🔄 Reset All Filters", use_container_width=True, key=f"reset_{plot_title}"):
            st.rerun()
        
        st.markdown("**Sold Date Range**")
        date_range = st.slider(
            "Sold Date Range",
            min_value=min_date.date(),
            max_value=max_date.date(),
            value=(min_date.date(), max_date.date()),
            label_visibility="collapsed",
            key=f"date_range_{plot_title}"
        )
        
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        st.caption(f"📅 {start_date.date()} to {end_date.date()}")
        
        st.markdown("**Plot Size Range (sft)**")
        size_range = st.slider(
            "Plot Size Range",
            min_value=float(min_plot_size),
            max_value=float(max_plot_size),
            value=(float(min_plot_size), float(max_plot_size)),
            label_visibility="collapsed",
            key=f"size_range_{plot_title}"
        )
        
        min_size, max_size = size_range
        st.caption(f"📐 {min_size:,.0f} to {max_size:,.0f} sft")
        
        st.markdown("**Include Unsold Plots**")
        include_unsold = st.checkbox("Show unsold (available) plots", value=True, key=f"unsold_{plot_title}")

        st.markdown("---")
        st.markdown("### 🏷️ Legend")
        st.markdown("**Owners (toggle visibility)**")

        selected_owners = []

        for owner, color in owner_palette.items():
            count = owner_counts.get(owner, 0)

            dot_col, chk_col = st.columns([1, 6])

            with dot_col:
                st.markdown(
                    f"""
                    <div style="width:14px;height:14px;
                    background:{color};border-radius:50%;margin-top:6px;"></div>
                    """,
                    unsafe_allow_html=True
                )

            with chk_col:
                if st.checkbox(f"{owner} ({count})", value=True, key=f"own_{owner}_{plot_title}"):
                    selected_owners.append(owner)

        st.markdown("---")
        st.markdown("**Plot Status**")
        st.markdown(
            """
            <div style="display:flex;align-items:center;margin-bottom:8px;">
                <span style="font-size:18px;font-weight:bold;color:#8B0000;margin-right:8px;">✖</span>
                <span>Sold Plot</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # -------------------------------------------------
    # APPLY FILTERS
    # -------------------------------------------------
    # Build filter conditions
    date_filter = (
        (df["Sold_Date"].isna() & include_unsold) |
        ((df["Sold_Date"] >= start_date) & (df["Sold_Date"] <= end_date))
    )

    owner_filter = df["Owner_Name"].isin(selected_owners)
    size_filter = (df["Plot_Size"] >= min_size) & (df["Plot_Size"] <= max_size)

    df_filtered = df[date_filter & owner_filter & size_filter]

    # -------------------------------------------------
    # SCATTER + IMAGE (PIXEL PERFECT)
    # -------------------------------------------------
    with plot_col:
        fig = go.Figure()
        
        # Dynamic marker size scaling - larger sizes to remain visible when zoomed
        if len(df_filtered) > 0:
            # Use square root scaling for better visibility range
            min_marker = 12
            max_marker = 40
            size_range_val = df_filtered["Plot_Size"].max() - df_filtered["Plot_Size"].min()
            if size_range_val > 0:
                normalized_sizes = (df_filtered["Plot_Size"] - df_filtered["Plot_Size"].min()) / size_range_val
                marker_sizes = min_marker + (normalized_sizes ** 0.5) * (max_marker - min_marker)
            else:
                marker_sizes = [30] * len(df_filtered)
        else:
            marker_sizes = []

        fig.add_trace(
            go.Scatter(
                x=df_filtered["X_plot"],
                y=df_filtered["Y_plot"],
                mode="markers",
                marker=dict(
                    size=marker_sizes,
                    color=df_filtered["Owner_Color"],
                    opacity=0.75,
                    line=dict(width=2, color="white"),
                    sizemode='diameter'
                ),
                customdata=df_filtered[
                    ["Plot_Number", "Plot_Size", "Owner_Name", "Status", "Sold_Date", "Sold_Amount"]
                ],
                hovertemplate=(
                    "<b>Plot %{customdata[0]}</b><br>"
                    "Size: %{customdata[1]:.0f} sft<br>"
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
                x=sold["X_plot"],
                y=sold["Y_plot"],
                mode="markers",
                marker=dict(
                    symbol="x",
                    size=9,
                    color="#8B0000",
                    line=dict(width=2)
                ),
                hoverinfo="skip",
                showlegend=False
            )
        )

        fig.update_layout(
            xaxis=dict(range=[0, img_width], visible=False, fixedrange=False),
            yaxis=dict(
                range=[0, img_height],
                visible=False,
                fixedrange=False,
                scaleanchor="x"
            ),
            images=[
                dict(
                    source=bg_image,
                    x=0,
                    y=img_height,
                    sizex=img_width,
                    sizey=img_height,
                    xref="x",
                    yref="y",
                    sizing="contain",
                    layer="below"
                )
            ],
            height=900,
            margin=dict(l=0, r=0, t=10, b=0)
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "responsive": True,
                "scrollZoom": False,
                "displayModeBar": True,
                "modeBarButtonsToRemove": [
                    "lasso2d",
                    "select2d"
                ],
                "doubleClick": "reset",
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": f"plot_dashboard_{plot_title}",
                    "height": 900,
                    "width": 1600,
                    "scale": 1
                }
            }
        )
        st.caption("💡 Use **scroll to pan** | **two-finger pinch to zoom** | **double-click to reset**")

    # -------------------------------------------------
    # SOLD SUMMARY TABLE (BELOW IMAGE)
    # -------------------------------------------------
    st.markdown("---")
    st.markdown("### 💰 Sold Summary (Live)")

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
    total_sold_amount = summary["Total_Sold_Amount"].sum()
    total_row = pd.DataFrame({
        "Owner": ["**TOTAL**"],
        "Sold_Plots": [int(summary["Sold_Plots"].sum())],
        "Total_Sold_Amount": [total_sold_amount]
    })

    summary = pd.concat([summary, total_row], ignore_index=True)

    # Formatting
    summary["Total_Sold_Amount"] = summary["Total_Sold_Amount"].map(
        lambda x: f"₹{x:,.0f}"
    )

    st.dataframe(summary, hide_index=True, use_container_width=True)


# -------------------------------------------------
# MAIN APP WITH TABS
# -------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "📍 Plot 1 – 9.6 Acres", 
    "📍 Plot 2 – 9.66 Acres",
    "📍 Plot 3 – 9.01 Acres",
    "📍 Plot 4 – 30.85 Acres"
])

with tab1:
    # Load data for Plot 1 (first/default sheet)
    with st.spinner("📊 Loading Plot 1 data from Google Sheets..."):
        df1 = load_data()
    
    owner_palette_1 = {
        "BRINDAVAN ASSETS HOLDINGS": "#1f77b4",
        "SAUKHYADA INFRA LLP": "#ff7f0e",
        "S.V. INFRA": "#2ca02c"
    }
    
    render_dashboard(df1, "9.6_ACRES.jpg", "Plot 1 – 9.6 Acres", owner_palette_1)

with tab2:
    # Load data for Plot 2 (9.66 Acres sheet)
    with st.spinner("📊 Loading Plot 2 data from Google Sheets..."):
        df2 = load_data(sheet_gid="723093039")
    
    owner_palette_2 = {
        "SAUKHYADA INFRA LLP": "#ff7f0e"
    }
    
    render_dashboard(df2, "9.66.jpg", "Plot 2 – 9.66 Acres", owner_palette_2)

with tab3:
    # Load data for Plot 3 (9.01 Acres sheet)
    with st.spinner("📊 Loading Plot 3 data from Google Sheets..."):
        df3 = load_data(sheet_gid="2020669099")
    
    owner_palette_3 = {
        "SAUKHYADA INFRA LLP": "#ff7f0e"
    }
    
    render_dashboard(df3, "9.01_arunmugam.jpg", "Plot 3 – 9.01 Acres", owner_palette_3)

with tab4:
    # Load data for Plot 4 (30.85 Acres sheet)
    with st.spinner("📊 Loading Plot 4 data from Google Sheets..."):
        df4 = load_data(sheet_gid="203489306")
    
    owner_palette_4 = {
        "SAUKHYADA INFRA LLP": "#ff7f0e",
        "BRINDAVAN ASSETS HOLDINGS": "#1f77b4",
        "BRINDAVAN BULIDERS PVT LTD": "#2ca02c",
        "VIRUPAKSHA INFRA": "#d62728",
        "CHANDRAMOULISWAR REDDY": "#9467bd",
        "SREEKARI DEVELOPERS": "#8c564b",
        "N.V.RAMANA RAO": "#e377c2",
        "SREE KAMAKSHI VENTURES": "#7f7f7f"
    }
    
    render_dashboard(df4, "30.85.jpg", "Plot 4 – 30.85 Acres", owner_palette_4)

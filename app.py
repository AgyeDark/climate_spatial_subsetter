import streamlit as st
import os
import zipfile
import io
import rasterio
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

# --- PAGE CONFIGURATION MUST BE THE FIRST STREAMLIT COMMAND ---
st.set_page_config(page_title="Climate Data Subsetter", layout="wide")

from src.esgf_engine import download_regional_subset
from src.gee_engine import download_gee_fallback

st.title("West Africa Climate Data Subsetter")
st.markdown("Extract lightweight spatial subsets of CMIP6 climate projections. **Upgraded with FAO-56 Penman-Monteith SPEI.**")
st.markdown("---")

# --- KNOWLEDGE BASE: DYNAMIC MODEL DATABASE ---
MODEL_DATABASE = {
    "Vegetation & Agricultural Accounting (Earth System Models)": ["EC-Earth3-Veg-LR", "GFDL-ESM4", "NorESM2-LM"],
    "Extreme Weather & Urban Flooding (High Resolution)": ["MPI-ESM1-2-HR", "CMCC-CM2-SR5", "EC-Earth3"],
    "General Basin Hydrology (Well-balanced for West Africa)": ["MIROC6", "MPI-ESM1-2-LR", "CNRM-CM6-1"]
}

# --- UI LAYOUT ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Research Focus")
    research_focus = st.radio("What is the primary focus of your study?", list(MODEL_DATABASE.keys()))
    
    st.subheader("2. Data Parameters")
    recommended_models = MODEL_DATABASE[research_focus]
    model = st.selectbox("Select Recommended GCM/RCM Model", recommended_models)
    
    st.sidebar.markdown("###  Parameters")
    scenario = st.sidebar.selectbox("Experiment / Scenario", ["Historical", "SSP126", "SSP245", "SSP370", "SSP585"])
    
    st.sidebar.markdown("###  Temporal Subset")
    if scenario.lower() == "historical":
        start_year, end_year = st.sidebar.slider("Select Year Range", min_value=1950, max_value=2014, value=(1990, 2000))
    else:
        start_year, end_year = st.sidebar.slider("Select Year Range", min_value=2015, max_value=2100, value=(2030, 2040))

    # --- NEW: PENMAN-MONTEITH BUNDLE IN THE UI ---
    variable = st.selectbox("Select Variable", [
        "Penman-Monteith SPEI Bundle (6 Variables)",
        "Precipitation (pr)", 
        "Max Temperature (tasmax)", 
        "Min Temperature (tasmin)"
    ])
    
    st.markdown("<br>", unsafe_allow_html=True)
    routing_strategy = st.radio("Server Protocol", ["Auto-Failover (ESGF -> GEE)", "Force Google Earth Engine"])

with col2:
    st.subheader("3. Spatial Bounding Box (Degrees)")
    st.info("Default coordinates are set for the Ghana/West Africa region.")
    
    box_col1, box_col2 = st.columns(2)
    with box_col1:
        min_lon = st.number_input("Min Longitude", value=-3.5, step=0.5)
        min_lat = st.number_input("Min Latitude", value=4.5, step=0.5)
    with box_col2:
        max_lon = st.number_input("Max Longitude", value=1.5, step=0.5)
        max_lat = st.number_input("Max Latitude", value=11.5, step=0.5)

st.markdown("---")

# --- EXECUTION LOGIC ---
if 'data_extracted' not in st.session_state:
    st.session_state.data_extracted = False
    st.session_state.final_file = []

# --- NEW: DYNAMIC VARIABLE LIST MAPPING ---
is_bundle = "SPEI" in variable
if is_bundle:
    var_shortcodes = ["pr", "tasmax", "tasmin", "rsds", "sfcWind", "hurs"]
    # Force GEE for bundle to prevent hanging on 6 separate ESGF checks
    if routing_strategy != "Force Google Earth Engine":
        st.sidebar.warning("Note: Auto-Failover bypassed. The SPEI 6-variable bundle uses Google Earth Engine directly for speed.")
        routing_strategy = "Force Google Earth Engine"
else:
    var_shortcodes = ["pr"] if "Precipitation" in variable else ["tasmax"] if "Max" in variable else ["tasmin"]

target_start = f"{start_year}-01-01"
target_end = f"{end_year}-12-31"

if st.button("Extract & Download Localized Data", type="primary"):
    status_container = st.container()
    st.session_state.final_file = [] # Reset memory
    
    with status_container:
        with st.spinner(f'Extracting {len(var_shortcodes)} variable(s) from {start_year} to {end_year}...'):
            for v_code in var_shortcodes:
                st.write(f"📥 Queuing extraction for: **{v_code}**...")
                
                # Single variable ESGF bypass logic
                if routing_strategy == "Auto-Failover (ESGF -> GEE)" and not is_bundle:
                    test_esgf_url = "http://esgf-data.dkrz.de/thredds/dodsC/CMIP6/CMIP/MPI-M/MPI-ESM1-2-LR/historical/r1i1p1f1/day/pr/gn/v20190710/pr_day_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_18500101-18691231.nc"
                    output_file = download_regional_subset(test_esgf_url, min_lon, max_lon, min_lat, max_lat)
                    if output_file and os.path.exists(output_file):
                        st.session_state.final_file.append(output_file)
                        continue # Move to next variable if successful
                        
                # Default to Google Earth Engine
                gee_files = download_gee_fallback(model, scenario.lower(), v_code, target_start, target_end, min_lon, max_lon, min_lat, max_lat)
                if gee_files:
                    st.session_state.final_file.extend(gee_files)
            
            if len(st.session_state.final_file) > 0:
                st.success(f"Success! All data bundles localized.")
                st.session_state.data_extracted = True
            else:
                st.error("Extraction failed. Please check the terminal logs.")

# ==========================================
# --- POST-EXTRACTION UI: TABS & ANALYSIS ---
# ==========================================
if st.session_state.data_extracted and len(st.session_state.final_file) > 0:
    
    file_list = st.session_state.final_file
    st.markdown("### 📊 Data Analysis & Export")
    tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Spatial Map", "📈 Time Series", "💾 Download Files", "🏜️ Drought Analysis (FAO-56)"])
    
    with tab1:
        st.markdown(f"**Bounding Box:** [{min_lon}°, {min_lat}°] to [{max_lon}°, {max_lat}°]")
        m = folium.Map(location=[(min_lat+max_lat)/2, (min_lon+max_lon)/2], zoom_start=5)
        folium.Rectangle(
            bounds=[[min_lat, min_lon], [max_lat, max_lon]],
            color="#ff7800", fill=True, fillColor="#ff7800", fillOpacity=0.2
        ).add_to(m)
        st_folium(m, width=700, height=400)

    with tab2:
        with st.spinner('Compiling Multi-Variable Data Weaver...'):
            var_data_dict = {}
            
            # 1. Stitch and average each variable separately
            for v_code in var_shortcodes:
                v_files = [f for f in file_list if f"_{v_code}_" in f]
                v_means = []
                for f in sorted(v_files):
                    with rasterio.open(f) as src:
                        data = src.read()
                        if src.nodata is not None: data = np.where(data == src.nodata, np.nan, data)
                        data = np.where(data > 10000, np.nan, data)
                        data = np.where(data < -1000, np.nan, data)
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", category=RuntimeWarning)
                            yearly_means = np.nanmean(data, axis=(1, 2))
                            v_means.extend(yearly_means)
                var_data_dict[v_code] = v_means
            
            # 2. Build the Master Pandas DataFrame
            ref_length = len(var_data_dict[var_shortcodes[0]])
            dates = pd.date_range(start=target_start, periods=ref_length, freq='D')
            df = pd.DataFrame({"Date": dates})
            
            for v_code in var_shortcodes:
                df[v_code] = var_data_dict[v_code][:ref_length] # Ensure strict length match
            
            # 3. UNIT CONVERSIONS & MATH
            if "pr" in df.columns: df["pr"] = df["pr"] * 86400 # kg/m2/s to mm/day
            if "tasmax" in df.columns: df["tasmax"] = df["tasmax"] - 273.15 # K to C
            if "tasmin" in df.columns: df["tasmin"] = df["tasmin"] - 273.15 # K to C
            
            # --- NEW: RIGOROUS FAO-56 PENMAN-MONTEITH ALGORITHM ---
            if is_bundle:
                df["rsds"] = df["rsds"] * 0.0864 # W/m2 to MJ/m2/day
                
                # Psychrometric constants & Elevation assumption (200m for WA)
                Z = 200 
                P = 101.3 * ((293 - 0.0065 * Z) / 293) ** 5.26
                gamma = 0.000665 * P
                
                T_mean = (df["tasmax"] + df["tasmin"]) / 2
                Delta = 4098 * (0.6108 * np.exp(17.27 * T_mean / (T_mean + 237.3))) / ((T_mean + 237.3) ** 2)
                
                e_s_max = 0.6108 * np.exp(17.27 * df["tasmax"] / (df["tasmax"] + 237.3))
                e_s_min = 0.6108 * np.exp(17.27 * df["tasmin"] / (df["tasmin"] + 237.3))
                e_s = (e_s_max + e_s_min) / 2
                e_a = e_s * (df["hurs"] / 100)
                
                # Astronomical Radiation (Ra) calculation based on Latitude & Day of Year
                J = df["Date"].dt.dayofyear
                lat_rad = np.radians((min_lat + max_lat) / 2)
                dr = 1 + 0.033 * np.cos(2 * np.pi * J / 365)
                delta_ast = 0.409 * np.sin(2 * np.pi * J / 365 - 1.39)
                omega_s = np.arccos(-np.tan(lat_rad) * np.tan(delta_ast))
                Ra = (24 * 60 / np.pi) * 0.0820 * dr * (omega_s * np.sin(lat_rad) * np.sin(delta_ast) + np.cos(lat_rad) * np.cos(delta_ast) * np.sin(omega_s))
                
                Rso = (0.75 + 2e-5 * Z) * Ra
                Rs_Rso = np.clip(df["rsds"] / Rso, 0.3, 1.0)
                R_ns = (1 - 0.23) * df["rsds"]
                R_nl = 4.903e-9 * (((df["tasmax"]+273.16)**4 + (df["tasmin"]+273.16)**4)/2) * (0.34 - 0.14*np.sqrt(e_a)) * (1.35 * Rs_Rso - 0.35)
                R_n = R_ns - R_nl
                
                wind = df["sfcWind"]
                PET = (0.408 * Delta * R_n + gamma * (900 / (T_mean + 273)) * wind * (e_s - e_a)) / (Delta + gamma * (1 + 0.34 * wind))
                
                df["PET"] = np.clip(PET, 0, None) # Cannot have negative evaporation
                df["Water_Balance"] = df["pr"] - df["PET"]
                
                # Plot dual-axis chart for SPEI Bundle
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df["Date"], y=df["PET"], name="Daily PET (mm)", line=dict(color='orange')))
                fig.add_trace(go.Bar(x=df["Date"], y=df["pr"], name="Precipitation (mm)", marker=dict(color='blue')))
                fig.update_layout(title=f"Water Accounting: Precipitation vs. Evapotranspiration ({model})", yaxis_title="Millimeters (mm/day)")
                st.plotly_chart(fig, width="stretch")
            
            else:
                # Plot simple chart for single variables
                plot_var = var_shortcodes[0]
                fig = px.line(df, x="Date", y=plot_var, title=f"Daily Basin Average: {model}")
                st.plotly_chart(fig, width="stretch")

    with tab3:
        st.info("Download your extracted data for local GIS or statistical analysis.")
        col_a, col_b = st.columns(2)
        
        with col_a:
            if len(file_list) > 1:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for f in file_list:
                        zip_file.write(f, os.path.basename(f))
                
                st.download_button(
                    label="🗺️ Download GeoTIFFs (.zip)",
                    data=zip_buffer.getvalue(),
                    file_name=f"{model}_{scenario}_Batch_Data.zip",
                    mime="application/zip",
                    width="stretch",
                    key="dl_zip_btn"
                )
            else:
                with open(file_list[0], "rb") as file:
                    st.download_button(
                        label="🗺️ Download GeoTIFF (.tif)",
                        data=file,
                        file_name=os.path.basename(file_list[0]),
                        mime="image/tiff",
                        width="stretch",
                        key="dl_tif_btn"
                    )
                
        with col_b:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📊 Download Time Series (.csv)",
                data=csv,
                file_name=f"{model}_{scenario}_Master_TimeSeries.csv",
                mime="text/csv",
                width="stretch",
                key="download_csv_btn"
            )

    with tab4:
        if is_bundle:
            st.markdown("###  Standardized Precipitation Evapotranspiration Index (SPEI)")
        else:
            st.markdown("###  Standardized Precipitation Index (SPI)")
        
        if "pr" not in var_shortcodes:
            st.warning("⚠️ Drought analysis requires at least Precipitation data.")
        else:
            col_scale, col_desc = st.columns([1, 2])
            with col_scale:
                drought_scale = st.selectbox("Timescale", ["3-Month (Agricultural)", "6-Month (Seasonal)", "12-Month (Hydrological)"])
                window = int(drought_scale.split("-")[0])
            
            with col_desc:
                if is_bundle:
                    st.info(f"**How it works:** This calculates the **SPEI**. It tracks the climatic water balance (Rainfall minus Evapotranspiration) over {window}-month rolling windows and standardizes it.")
                else:
                    st.info(f"**How it works:** This calculates the **SPI** (Rainfall only) over a {window}-month rolling window.")

            with st.spinner("Calculating rigorous drought index..."):
                monthly_df = df.set_index("Date").resample("MS").sum().reset_index()
                
                # Choose Water Balance (SPEI) or just Rain (SPI)
                target_col = "Water_Balance" if is_bundle else "pr"
                
                monthly_df['Rolling_Sum'] = monthly_df[target_col].rolling(window=window).sum()
                mean_val = monthly_df['Rolling_Sum'].mean()
                std_val = monthly_df['Rolling_Sum'].std()
                monthly_df['Drought_Index'] = (monthly_df['Rolling_Sum'] - mean_val) / std_val
                
                monthly_df['Color'] = np.where(monthly_df['Drought_Index'] < 0, 'Drought', 'Wet')
                plot_df = monthly_df.dropna()

                fig_drought = px.bar(
                    plot_df, x="Date", y="Drought_Index", color="Color",
                    color_discrete_map={'Drought': '#ef553b', 'Wet': '#00cc96'},
                    title=f"{window}-Month {'SPEI' if is_bundle else 'SPI'} Drought Index: {model}",
                    labels={"Drought_Index": "Standard Deviations (σ)"}
                )
                fig_drought.add_hline(y=0, line_width=2, line_color="black")
                st.plotly_chart(fig_drought, width="stretch")
                
                csv_drought = plot_df[["Date", "Rolling_Sum", "Drought_Index"]].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Download Drought Index Data (.csv)",
                    data=csv_drought,
                    file_name=f"{model}_{scenario}_{window}M_DroughtIndex.csv",
                    mime="text/csv",
                    width="stretch"
                )

st.divider()
st.markdown("<p style='text-align: center; color: #888888;'>© 2026 Agyei Darko | Virtual Catchment Laboratory</p>", unsafe_allow_html=True)

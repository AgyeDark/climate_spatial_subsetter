import streamlit as st

import os


# --- PAGE CONFIGURATION MUST BE THE FIRST STREAMLIT COMMAND ---

st.set_page_config(page_title="Climate Data Subsetter", layout="wide")



# Now it is safe to import your custom engines

from src.esgf_engine import download_regional_subset

from src.gee_engine import download_gee_fallback



st.title("West Africa Climate Data Subsetter")

st.markdown("Extract lightweight spatial subsets of CMIP6 climate projections without downloading global datasets.")

st.markdown("---")

# --- KNOWLEDGE BASE: DYNAMIC MODEL DATABASE ---
# These exact string names are verified to match the NASA NEX-GDDP-CMIP6 Earth Engine catalog.
MODEL_DATABASE = {
    "Vegetation & Agricultural Accounting (Earth System Models)": [
        "EC-Earth3-Veg-LR", # Fixed naming
        "GFDL-ESM4",        # Replaced CESM2 with an available NASA Earth System Model
        "NorESM2-LM"
    ],
    "Extreme Weather & Urban Flooding (High Resolution)": [
        "MPI-ESM1-2-HR", 
        "CMCC-CM2-SR5",     # Replaced HR4 with SR5, which is available in GDDP
        "EC-Earth3"         # Base EC-Earth3 is available
    ],
    "General Basin Hydrology (Well-balanced for West Africa)": [
        "MIROC6", 
        "MPI-ESM1-2-LR", 
        "CNRM-CM6-1"
    ]
}

# --- UI LAYOUT ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Research Focus")
    # Ask the user what they are studying
    research_focus = st.radio(
        "What is the primary focus of your study?", 
        list(MODEL_DATABASE.keys())
    )
    
    st.subheader("2. Data Parameters")
    # Dynamically pull the list of models based on their answer above
    recommended_models = MODEL_DATABASE[research_focus]
    
    model = st.selectbox("Select Recommended GCM/RCM Model", recommended_models)
    scenario = st.selectbox("Select Scenario", ["Historical", "SSP245", "SSP585"])
    scenario = st.sidebar.selectbox("Experiment / Scenario", ["Historical", "SSP126", "SSP245", "SSP370", "SSP585"])
    
    st.sidebar.markdown("### 📅 Temporal Subset")
    if scenario.lower() == "historical":
        # CMIP6 historical runs end in 2014
        start_year, end_year = st.sidebar.slider(
            "Select Year Range", 
            min_value=1950, max_value=2014, value=(1990, 2000)
        )
    else:
        # SSP scenarios start in 2015
        start_year, end_year = st.sidebar.slider(
            "Select Year Range", 
            min_value=2015, max_value=2100, value=(2030, 2040)
        )
 
    variable = st.selectbox("Select Variable", ["Precipitation (pr)", "Max Temperature (tasmax)", "Min Temperature (tasmin)"])
    
    st.markdown("<br>", unsafe_allow_html=True) # Adds a little visual spacing
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

import rasterio
import numpy as np
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium

# --- EXECUTION LOGIC ---

# 1. Give the app a memory (Session State)
if 'data_extracted' not in st.session_state:
    st.session_state.data_extracted = False
    st.session_state.final_file = None

# Calculate variables outside the button so the UI can always see them
var_shortcode = "pr" if "Precipitation" in variable else "tasmax" if "Max" in variable else "tasmin"
# Dynamically create the start and end dates based on the slider
target_start = f"{start_year}-01-01"
target_end = f"{end_year}-12-31"

if st.button("Extract & Download Localized Data", type="primary"):
    
    test_esgf_url = "http://esgf-data.dkrz.de/thredds/dodsC/CMIP6/CMIP/MPI-M/MPI-ESM1-2-LR/historical/r1i1p1f1/day/pr/gn/v20190710/pr_day_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_18500101-18691231.nc"
    status_container = st.container()
    
    with status_container:
        if routing_strategy == "Auto-Failover (ESGF -> GEE)":
            with st.spinner('Attempting connection to primary ESGF node...'):
                output_file = download_regional_subset(test_esgf_url, min_lon, max_lon, min_lat, max_lat)
                
                if output_file and os.path.exists(output_file):
                    st.success(f"Success! Data localized via ESGF OPeNDAP.")
                    # Save to memory!
                    st.session_state.final_file = output_file
                    st.session_state.data_extracted = True
                else:
                    st.warning("ESGF Node Timeout. Rerouting query to Google Earth Engine API...")
                    with st.spinner('Querying Google Earth Engine...'):
                        gee_file = download_gee_fallback(model, scenario.lower(), var_shortcode, target_start, target_end, min_lon, max_lon, min_lat, max_lat)
                        if gee_file:
                            st.success(f"Success! Data retrieved via Earth Engine Fallback.")
                            # Save to memory!
                            st.session_state.final_file = gee_file
                            st.session_state.data_extracted = True

        elif routing_strategy == "Force Google Earth Engine":
            with st.spinner('Bypassing ESGF. Querying Google Earth Engine directly...'):
                gee_file = download_gee_fallback(model, scenario.lower(), var_shortcode, target_start, target_end, min_lon, max_lon, min_lat, max_lat)
                if gee_file:
                    st.success(f"Success! Data retrieved via Earth Engine.")
                    # Save to memory!
                    st.session_state.final_file = gee_file
                    st.session_state.data_extracted = True

# ==========================================
# --- POST-EXTRACTION UI: TABS & ANALYSIS ---
# ==========================================
# Notice this is OUTSIDE the button block now! It checks the "memory" instead.
if st.session_state.data_extracted and st.session_state.final_file and os.path.exists(st.session_state.final_file):
    
    final_file = st.session_state.final_file
    st.markdown("### 📊 Data Analysis & Export")
    
    tab1, tab2, tab3 = st.tabs(["🗺️ Spatial Map", "📈 Time Series", "💾 Download Files"])
    
    with tab1:
        st.markdown(f"**Bounding Box:** [{min_lon}°, {min_lat}°] to [{max_lon}°, {max_lat}°]")
        m = folium.Map(location=[(min_lat+max_lat)/2, (min_lon+max_lon)/2], zoom_start=5)
        folium.Rectangle(
            bounds=[[min_lat, min_lon], [max_lat, max_lon]],
            color="#ff7800", fill=True, fillColor="#ff7800", fillOpacity=0.2
        ).add_to(m)
        st_folium(m, width=700, height=400)
        
    with tab2:
        with st.spinner('Calculating spatial averages...'):
            with rasterio.open(final_file) as src:
                data = src.read()
                
                # 1. Filter out standard nodata values (if present in metadata)
                if src.nodata is not None:
                    data = np.where(data == src.nodata, np.nan, data)
                
                # 2. Catch massive positive Fill Values (like 1e19 or 1e20 from CMIP6)
                data = np.where(data > 10000, np.nan, data)
                
                # 3. Catch rogue Earth Engine negative masks (like -9999)
                data = np.where(data < -1000, np.nan, data)
                
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    daily_means = np.nanmean(data, axis=(1, 2))
                
                dates = pd.date_range(start=target_start, periods=len(daily_means), freq='D')
                df = pd.DataFrame({"Date": dates, variable: daily_means})
                
                fig = px.line(df, x="Date", y=variable, title=f"Daily Basin Average: {model} ({scenario.upper()})")
                st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.info("Download your extracted data for local GIS or statistical analysis.")
        col_a, col_b = st.columns(2)
        
        with col_a:
            with open(final_file, "rb") as file:
                st.download_button(
                    label="🗺️ Download GeoTIFF (.tif)",
                    data=file,
                    file_name=os.path.basename(final_file),
                    mime="image/tiff",
                    use_container_width=True,
                    key="download_tif_btn"  # <--- ADD THIS UNIQUE KEY
                )
                
        with col_b:
            with rasterio.open(final_file) as src:
                csv_data = src.read()
                
                if src.nodata is not None:
                    csv_data = np.where(csv_data == src.nodata, np.nan, csv_data)
                    
                # The same massive positive/negative filters for the CSV
                csv_data = np.where(csv_data > 10000, np.nan, csv_data)
                csv_data = np.where(csv_data < -1000, np.nan, csv_data)
                
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=RuntimeWarning)
                    csv_means = np.nanmean(csv_data, axis=(1, 2))
                    
                csv_dates = pd.date_range(start=target_start, periods=len(csv_means), freq='D')
                csv_df = pd.DataFrame({"Date": csv_dates, variable: csv_means})
                
            csv = csv_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📊 Download Time Series (.csv)",
                data=csv,
                file_name=f"{model}_{scenario}_{var_shortcode}_timeseries.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_csv_btn"
            )
        with col_b:
            # Generate the CSV data right here so it's always ready to download
            with rasterio.open(final_file) as src:
                csv_data = src.read()
                csv_data = np.where(csv_data == src.nodata, np.nan, csv_data)
                csv_means = np.nanmean(csv_data, axis=(1, 2))
                csv_dates = pd.date_range(start=target_start, periods=len(csv_means), freq='D')
                csv_df = pd.DataFrame({"Date": csv_dates, variable: csv_means})
                
            csv = csv_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📊 Download Time Series (.csv)",
                data=csv,
                file_name=f"{model}_{scenario}_{var_shortcode}_timeseries.csv",
                mime="text/csv",
                use_container_width=True
            )

st.divider()
st.markdown("<p style='text-align: center; color: #888888;'>© 2026 Agyei Darko | Virtual Catchment Laboratory</p>", unsafe_allow_html=True)

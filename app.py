import streamlit as st
import os

from src.esgf_engine import download_regional_subset
from src.gee_engine import download_gee_fallback

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Climate Data Subsetter", layout="wide")

st.title("West Africa Climate Data Subsetter")
st.markdown("Extract lightweight spatial subsets of CMIP6 climate projections without downloading global datasets.")
st.markdown("---")

# --- KNOWLEDGE BASE: DYNAMIC MODEL DATABASE ---
# You can expand these lists later with as many models as you want!
MODEL_DATABASE = {
    "Vegetation & Agricultural Accounting (Earth System Models)": ["EC-Earth3-Veg", "CESM2", "NorESM2-LM"],
    "Extreme Weather & Urban Flooding (High Resolution)": ["MPI-ESM1-2-HR", "CMCC-CM2-HR4", "EC-Earth3-HR"],
    "General Basin Hydrology (Well-balanced for West Africa)": ["MIROC6", "MPI-ESM1-2-LR", "CNRM-CM6-1"]
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

# --- EXECUTION LOGIC ---
if st.button("Extract & Download Localized Data", type="primary"):
    
    var_shortcode = "pr" if "Precipitation" in variable else "tasmax" if "Max" in variable else "tasmin"
    
    # MVP test URL (We will make this dynamic in the final phase)
    test_esgf_url = "http://esgf-data.dkrz.de/thredds/dodsC/CMIP6/CMIP/MPI-M/MPI-ESM1-2-LR/historical/r1i1p1f1/day/pr/gn/v20190710/pr_day_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_18500101-18691231.nc"
    
    status_container = st.container()
    
    with status_container:
        if routing_strategy == "Auto-Failover (ESGF -> GEE)":
            with st.spinner('Attempting connection to primary ESGF node...'):
                output_file = download_regional_subset(test_esgf_url, min_lon, max_lon, min_lat, max_lat)
                
                if output_file and os.path.exists(output_file):
                    st.success(f"Success! Data localized via ESGF OPeNDAP and saved to `data/raw/`.")
                else:
                    st.warning("ESGF Node Timeout or Error. Rerouting query to Google Earth Engine API...")
                    with st.spinner('Querying Google Earth Engine...'):
                        gee_file = download_gee_fallback(
                            model, scenario.lower(), var_shortcode, 
                            '2030-01-01', '2030-12-31', 
                            min_lon, max_lon, min_lat, max_lat
                        )
                        if gee_file:
                            st.success(f"Success! Data retrieved via Earth Engine Fallback and saved to `data/raw/`.")
                        else:
                            st.error("Extractions failed. Check your terminal for logs.")

        elif routing_strategy == "Force Google Earth Engine":
            with st.spinner('Bypassing ESGF. Querying Google Earth Engine directly...'):
                gee_file = download_gee_fallback(
                    model, scenario.lower(), var_shortcode, 
                    '2030-01-01', '2030-12-31', 
                    min_lon, max_lon, min_lat, max_lat
                )
                if gee_file:
                    st.success(f"Success! Data retrieved via Earth Engine and saved to `data/raw/`.")
                else:
                    st.error("Earth Engine extraction failed. Have you run `earthengine authenticate`?")

    st.divider()
st.markdown("<p style='text-align: center; color: #888888;'>© 2026 Agyei Darko | Virtual Catchment Laboratory</p>", unsafe_allow_html=True)

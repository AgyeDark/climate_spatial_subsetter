import ee
import streamlit as st
import os
import requests
import json
from google.oauth2 import service_account

# ==========================================
# 1. AUTHENTICATION SETUP
# ==========================================
def initialize_gee():
    try:
        # Check if we are on Streamlit Cloud and have secrets
        if "GOOGLE_CREDENTIALS" in st.secrets:
            # Safely decode the raw JSON string
            secret_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
            
            # --- CRITICAL FIX: Tell Google we want Earth Engine access ---
            ee_scopes = [
                'https://www.googleapis.com/auth/earthengine',
                'https://www.googleapis.com/auth/cloud-platform'
            ]
            credentials = service_account.Credentials.from_service_account_info(
                secret_dict, 
                scopes=ee_scopes
            )
            # -------------------------------------------------------------
            
            ee.Initialize(credentials)
        else:
            # Fallback for local testing
            print("WARNING: GOOGLE_CREDENTIALS not found in Streamlit Secrets.")
            ee.Initialize()
    except Exception as e:
        print("Earth Engine not authorized.")
        raise e
        
# ==========================================
# 2. DOWNLOAD FUNCTION
# ==========================================
def download_gee_fallback(model, scenario, variable, target_start, target_end, min_lon, max_lon, min_lat, max_lat, output_dir="data/raw"):
    initialize_gee()
    os.makedirs(output_dir, exist_ok=True)
    
    region = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
    
    # GEE exact naming map
    model_map = {
        "EC-Earth3-Veg-LR": "EC-Earth3-Veg-LR", "GFDL-ESM4": "GFDL-ESM4", "NorESM2-LM": "NorESM2-LM",
        "MPI-ESM1-2-HR": "MPI-ESM1-2-HR", "CMCC-CM2-SR5": "CMCC-CM2-SR5", "EC-Earth3": "EC-Earth3",
        "MIROC6": "MIROC6", "MPI-ESM1-2-LR": "MPI-ESM1-2-LR", "CNRM-CM6-1": "CNRM-CM6-1"
    }
    gee_model = model_map.get(model, model)

    collection = ee.ImageCollection("NASA/GDDP-CMIP6") \
        .filter(ee.Filter.eq('model', gee_model)) \
        .filter(ee.Filter.eq('scenario', scenario)) \
        .select(variable)

    # --- NEW: BATCH CHUNKING BY YEAR ---
    start_year = int(target_start.split('-')[0])
    end_year = int(target_end.split('-')[0])
    
    downloaded_files = []
    
    print(f"Starting batch extraction: {start_year} to {end_year}")
    
    for year in range(start_year, end_year + 1):
        print(f"Fetching data for {year}...")
        year_start = f"{year}-01-01"
        year_end = f"{year}-12-31"
        
        year_col = collection.filterDate(year_start, year_end)
        
        # Check if Google actually has data for this year before downloading
        count = year_col.size().getInfo()
        if count == 0:
            print(f"No data found for {year}, skipping...")
            continue
            
        clipped_image = year_col.toBands().clip(region)
        
        try:
            url = clipped_image.getDownloadURL({
                'scale': 27750,
                'crs': 'EPSG:4326',
                'region': region,
                'format': 'GEO_TIFF'
            })
            
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            
            filepath = os.path.join(output_dir, f"{model}_{scenario}_{variable}_{year}.tif")
            with open(filepath, 'wb') as f:
                f.write(response.content)
                
            downloaded_files.append(filepath)
            print(f"Success! {year} saved.")
            
        except Exception as e:
            print(f"Failed on year {year}: {e}")

    # Return the LIST of files, not just one string
    if not downloaded_files:
        return None
        
    return downloaded_files

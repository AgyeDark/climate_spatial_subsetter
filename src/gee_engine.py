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
def download_gee_fallback(model, scenario, variable, start_date, end_date, min_lon, max_lon, min_lat, max_lat, output_dir="data/raw"):
    """
    Queries the NASA-NEX CMIP6 collection on GEE, clips it to the bounding box,
    and downloads it as a GeoTIFF.
    """
    initialize_gee()
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n--- GEE Fallback Triggered ---")
    print(f"Querying {model} | {scenario} | {variable} via Earth Engine...")

    region = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])

    collection = (
        ee.ImageCollection("NASA/GDDP-CMIP6")
        .filter(ee.Filter.eq('model', model))
        .filter(ee.Filter.eq('scenario', scenario))
        .filterDate(start_date, end_date)
        .select(variable)
    )

    count = collection.size().getInfo()
    if count == 0:
        raise ValueError("No data found in GEE for these parameters.")
    
    print(f"Found {count} daily records. Processing spatial clip...")

    clipped_image = collection.mean().clip(region)

    print("Generating direct download URL...")
    try:
        download_url = clipped_image.getDownloadURL({
            'scale': 27750,
            'crs': 'EPSG:4326',
            'region': region,
            'format': 'GEO_TIFF'
        })
        
        print("Downloading lightweight GeoTIFF to server...")
        response = requests.get(download_url)
        
        filename = f"{model}_{scenario}_{variable}_subset.tif"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
            
        print(f"Success! GEE Fallback saved to: {filepath}")
        return filepath

    except Exception as e:
        print(f"GEE Download failed: {e}")
        return None

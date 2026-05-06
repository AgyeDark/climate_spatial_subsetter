import xarray as xr
import os

def download_regional_subset(url, min_lon, max_lon, min_lat, max_lat, output_dir="data/raw"):
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Attempting to connect to ESGF OPeNDAP URL: {url}")
    
    try:
        # 1. The Safety Net: Try to open the dataset
        ds = xr.open_dataset(url, engine='netcdf4')
        print("Connected! Subsetting data...")
        
        # 2. The Subsetting Math (Your actual working code)
        subset = ds.sel(lon=slice(min_lon, max_lon), lat=slice(min_lat, max_lat))
        
        # 3. Saving the File
        filename = "esgf_subset.nc"
        filepath = os.path.join(output_dir, filename)
        subset.to_netcdf(filepath)
        
        print(f"Success! ESGF NetCDF saved to {filepath}")
        return filepath
        
    except Exception as e:
        # 4. The Fallback Trigger: Catch HTML webpages and Timeouts safely
        print(f"ESGF Data Error (Likely HTML Redirect or Timeout): {e}")
        return None



# ==========================================

# TEST RUN

# ==========================================

if __name__ == "__main__":

    # A real OPeNDAP test URL from an ESGF node (MPI-ESM1-2-LR, Historical, Daily Precipitation)

    test_url = "http://esgf-data.dkrz.de/thredds/dodsC/CMIP6/CMIP/MPI-M/MPI-ESM1-2-LR/historical/r1i1p1f1/day/pr/gn/v20190710/pr_day_MPI-ESM1-2-LR_historical_r1i1p1f1_gn_18500101-18691231.nc"

    

    # Rough Bounding Box for Ghana

    ghana_min_lon = -3.5

    ghana_max_lon = 1.5

    ghana_min_lat = 4.5

    ghana_max_lat = 11.5

    

    # Notice the output path now points to our new data/raw/ folder

    download_regional_subset(

        opendap_url=test_url,

        min_lon=ghana_min_lon,

        max_lon=ghana_max_lon,

        min_lat=ghana_min_lat,

        max_lat=ghana_max_lat,

        output_filename="data/raw/ghana_historical_pr.nc"

    )

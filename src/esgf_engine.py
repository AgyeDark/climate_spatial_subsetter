import xarray as xr

def download_regional_subset(opendap_url, min_lon, max_lon, min_lat, max_lat, output_filename="data/raw/subset_data.nc"):
    """
    Connects to an ESGF OPeNDAP URL, subsets the data spatially, and saves it locally.
    """
    print("1. Connecting to OPeNDAP server (loading metadata only)...")
    
    try:
        # We open the dataset lazily. No massive download happens here.
        ds = xr.open_dataset(opendap_url, engine='netcdf4')
        
        # ---------------------------------------------------------
        # GEOGRAPHIC FIX: The Prime Meridian Problem
        # If the model uses 0-360 longitudes, West Africa gets split.
        # We will roll the entire coordinate system to standard -180 to 180.
        # ---------------------------------------------------------
        if ds.lon.max() > 180:
            print("2. Detected 0-360 longitude format. Realigning to -180 to 180...")
            ds = ds.assign_coords(lon=(((ds.lon + 180) % 360) - 180))
            ds = ds.sortby('lon') # Sort so the slice function works correctly
        else:
            print("2. Longitude format is already -180 to 180. Proceeding...")

        print(f"3. Slicing bounding box: Lat[{min_lat} to {max_lat}], Lon[{min_lon} to {max_lon}]")
        
        # Perform the spatial cut
        # Note: Some models order latitudes descending. We handle both cases.
        if ds.lat[0] > ds.lat[-1]:
            subset = ds.sel(lon=slice(min_lon, max_lon), lat=slice(max_lat, min_lat))
        else:
            subset = ds.sel(lon=slice(min_lon, max_lon), lat=slice(min_lat, max_lat))
            
        print("4. Executing network download and saving to disk...")
        # THIS is the only time data actually travels over the internet
        subset.to_netcdf(output_filename)
        
        print(f"\nSuccess! File saved as: {output_filename}")
        
        # Be a good citizen and close the dataset connection
        ds.close()
        return output_filename
        
    except Exception as e:
        print(f"Connection or extraction failed: {e}")
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

def validate_coordinates(min_lon, max_lon, min_lat, max_lat):
    """
    Ensures the user hasn't put in mathematically impossible coordinates.
    """
    errors = []
    
    if min_lon >= max_lon:
        errors.append("Minimum Longitude must be less than Maximum Longitude.")
    if min_lat >= max_lat:
        errors.append("Minimum Latitude must be less than Maximum Latitude.")
        
    if not (-180 <= min_lon <= 180) or not (-180 <= max_lon <= 180):
        errors.append("Longitudes must be between -180 and 180 degrees.")
    if not (-90 <= min_lat <= 90) or not (-90 <= max_lat <= 90):
        errors.append("Latitudes must be between -90 and 90 degrees.")
        
    return errors

def check_bounding_box_size(min_lon, max_lon, min_lat, max_lat, max_area_deg=400):
    """
    Calculates the rough area in square degrees to prevent users from 
    crashing the server by requesting massive global chunks.
    (e.g., A 20x20 degree box is 400 sq degrees).
    """
    width = abs(max_lon - min_lon)
    height = abs(max_lat - min_lat)
    area = width * height
    
    if area > max_area_deg:
        return False, f"Bounding box is too large ({area} sq degrees). Please select a smaller region."
    return True, f"Bounding box size is acceptable ({area} sq degrees)."

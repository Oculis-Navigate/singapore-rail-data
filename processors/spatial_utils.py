import math

def calculate_centroid(coords_list):
    if not coords_list: return None
    lat = sum(p['lat'] for p in coords_list) / len(coords_list)
    lng = sum(p['lng'] for p in coords_list) / len(coords_list)
    return {"lat": lat, "lng": lng}

def haversine_distance(p1, p2):
    R = 6371000  # Radius of Earth in meters
    phi1, phi2 = math.radians(p1['lat']), math.radians(p2['lat'])
    dphi = math.radians(p2['lat'] - p1['lat'])
    dlng = math.radians(p2['lng'] - p1['lng'])
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c
